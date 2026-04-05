from __future__ import annotations

import atexit
import base64
import hashlib
import json
import mimetypes
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from flask import Flask, Response, abort, jsonify, render_template, request, send_file

BASE_DIR = Path(__file__).resolve().parent
VERSIONS_DIR = BASE_DIR / "Versions"
SETTINGS_FILE = BASE_DIR / "launcher_settings.json"
TEXT_EXTENSIONS = {".css", ".env", ".html", ".js", ".json", ".md", ".py", ".toml", ".txt", ".xml", ".yaml", ".yml"}
IMPORTANT_FILES = [
    "README.md",
    "app.py",
    "requirements.txt",
    "Dockerfile",
    "templates/index.html",
    "static/js/main.js",
    "static/css/context_menu.css",
]
MAX_TREE_ENTRIES = 80
MAX_TEXT_LENGTH = 12000
BASE_PORT = 5600
START_TIMEOUT_SECONDS = 18

app = Flask(__name__)
RUNNING_APPS: dict[str, dict[str, Any]] = {}
PROCESS_LOCK = threading.Lock()
LAST_START_ERRORS: dict[str, str] = {}
LOG_LIMIT = 500
DEFAULT_SETTINGS: dict[str, Any] = {"auto_start_folders": []}


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


PROXY_OPENER = urllib.request.build_opener(NoRedirectHandler)


def ensure_versions_dir() -> None:
    VERSIONS_DIR.mkdir(exist_ok=True)


def normalize_relative_path(path_value: str | None) -> str:
    if not path_value:
        return ""
    normalized = str(PurePosixPath(path_value.replace("\\", "/").strip()))
    if normalized in {".", "/"}:
        return ""
    normalized = normalized.lstrip("/")
    if normalized.startswith("..") or "/.." in normalized:
        raise FileNotFoundError
    return normalized


def safe_versions_child(relative_path: str | None) -> Path:
    safe_relative = normalize_relative_path(relative_path)
    target = (VERSIONS_DIR / safe_relative).resolve()
    try:
        target.relative_to(VERSIONS_DIR.resolve())
    except ValueError as exc:
        raise FileNotFoundError from exc
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError
    return target


def to_relative_path(target: Path) -> str:
    return target.relative_to(VERSIONS_DIR).as_posix()


def parse_env_files(*env_paths: Path) -> dict[str, str]:
    env_values: dict[str, str] = {}
    for env_path in env_paths:
        if not env_path.exists() or not env_path.is_file():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            value = value.strip().strip('"').strip("'")
            if key:
                env_values[key] = value
    return env_values


def load_shared_env() -> dict[str, str]:
    return parse_env_files(BASE_DIR / ".env", BASE_DIR / ".flaskenv")


def build_child_env(version_dir: Path) -> dict[str, str]:
    child_env = {
        **os.environ,
        **load_shared_env(),
        "PYTHONUTF8": "1",
        "FLASK_SKIP_DOTENV": "1",
    }

    # Many archived Flask versions share the same default secret key and cookie name.
    # That makes them read each other's session cookie on 127.0.0.1 and can trigger
    # broken state or 500 errors when switching between previews. Give each version a
    # stable per-project secret unless one was explicitly configured.
    if not child_env.get("SECRET_KEY"):
        secret_seed = f"{BASE_DIR.resolve()}::{version_dir.resolve()}"
        child_env["SECRET_KEY"] = hashlib.sha256(secret_seed.encode("utf-8")).hexdigest()

    if child_env.get("OPENAI_API_KEY") and not child_env.get("API_KEY"):
        child_env["API_KEY"] = child_env["OPENAI_API_KEY"]
    if child_env.get("API_KEY") and not child_env.get("OPENAI_API_KEY"):
        child_env["OPENAI_API_KEY"] = child_env["API_KEY"]

    if child_env.get("OPENAI_BASE_URL") and not child_env.get("BASE_URL"):
        child_env["BASE_URL"] = child_env["OPENAI_BASE_URL"]
    if child_env.get("BASE_URL") and not child_env.get("OPENAI_BASE_URL"):
        child_env["OPENAI_BASE_URL"] = child_env["BASE_URL"]

    if child_env.get("OPENAI_MODEL") and not child_env.get("MODEL"):
        child_env["MODEL"] = child_env["OPENAI_MODEL"]
    if child_env.get("MODEL") and not child_env.get("OPENAI_MODEL"):
        child_env["OPENAI_MODEL"] = child_env["MODEL"]

    return child_env


def safe_version_dir(version_name: str) -> Path:
    target = safe_versions_child(version_name)
    if not (target / "app.py").exists():
        raise FileNotFoundError
    return target


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def encode_version_token(version_name: str) -> str:
    return base64.urlsafe_b64encode(version_name.encode("utf-8")).decode("ascii").rstrip("=")


def decode_version_token(token: str) -> str:
    padded = token + "=" * (-len(token) % 4)
    try:
        return normalize_relative_path(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, base64.binascii.Error) as exc:
        raise FileNotFoundError from exc


def build_proxy_base_path(version_name: str) -> str:
    return f"/proxy/{encode_version_token(version_name)}"


def summarize_tree(version_dir: Path) -> tuple[list[dict[str, Any]], int, int, int]:
    tree: list[dict[str, Any]] = []
    file_count = 0
    dir_count = 0
    total_size = 0

    def walk(current: Path, depth: int) -> None:
        nonlocal file_count, dir_count, total_size
        if len(tree) >= MAX_TREE_ENTRIES:
            return
        children = sorted(current.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower()))
        for child in children:
            relative = child.relative_to(version_dir).as_posix()
            if child.is_dir():
                dir_count += 1
                tree.append({"type": "dir", "path": relative, "depth": depth})
                if len(tree) >= MAX_TREE_ENTRIES:
                    return
                walk(child, depth + 1)
            else:
                file_count += 1
                try:
                    size = child.stat().st_size
                except OSError:
                    size = 0
                total_size += size
                tree.append({"type": "file", "path": relative, "depth": depth, "size": human_size(size)})
                if len(tree) >= MAX_TREE_ENTRIES:
                    return

    walk(version_dir, 0)
    return tree, file_count, dir_count, total_size


def find_first(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def detect_stack(version_dir: Path) -> list[str]:
    tags: list[str] = []
    if (version_dir / "app.py").exists():
        tags.append("Flask")
    if (version_dir / "templates").exists() and (version_dir / "static").exists():
        tags.append("Web-App")
    if (version_dir / "requirements.txt").exists():
        tags.append("Python")
    if (version_dir / "Dockerfile").exists():
        tags.append("Docker")
    if (version_dir / ".env").exists():
        tags.append("Env")
    return tags or ["Projekt"]


def read_text_file(path: Path | None) -> str | None:
    if path is None or path.suffix.lower() not in TEXT_EXTENSIONS:
        return None
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = path.read_text(encoding="latin-1")
        except OSError:
            return None
    except OSError:
        return None
    if len(content) > MAX_TEXT_LENGTH:
        return content[:MAX_TEXT_LENGTH] + "\n\n... Vorschau gekürzt ..."
    return content


def load_launcher_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        settings = dict(DEFAULT_SETTINGS)
        save_launcher_settings(settings)
        return settings
    try:
        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        settings = dict(DEFAULT_SETTINGS)
        save_launcher_settings(settings)
        return settings

    auto_start_folders = []
    for folder in raw.get("auto_start_folders", []):
        try:
            auto_start_folders.append(normalize_relative_path(folder))
        except FileNotFoundError:
            continue
    settings = {"auto_start_folders": sorted(set(auto_start_folders))}
    if raw.get("auto_start_folders") != settings["auto_start_folders"]:
        save_launcher_settings(settings)
    return settings


def save_launcher_settings(settings: dict[str, Any]) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def get_auto_start_folders() -> set[str]:
    return set(load_launcher_settings().get("auto_start_folders", []))


def set_folder_auto_start(folder_path: str, enabled: bool) -> dict[str, Any]:
    safe_versions_child(folder_path)
    settings = load_launcher_settings()
    folders = set(settings.get("auto_start_folders", []))
    normalized = normalize_relative_path(folder_path)
    if enabled:
        folders.add(normalized)
    else:
        folders.discard(normalized)
    settings["auto_start_folders"] = sorted(folders)
    save_launcher_settings(settings)
    return settings


def is_version_dir(path: Path) -> bool:
    return (path / "app.py").exists()


def iter_container_dirs(folder_dir: Path) -> list[Path]:
    try:
        children = [child for child in folder_dir.iterdir() if child.is_dir()]
    except OSError:
        return []
    return sorted(children, key=lambda path: path.name.lower())


def list_all_version_dirs(root_dir: Path | None = None) -> list[Path]:
    current_root = root_dir or VERSIONS_DIR
    version_dirs: list[Path] = []
    for child in iter_container_dirs(current_root):
        if is_version_dir(child):
            version_dirs.append(child)
        else:
            version_dirs.extend(list_all_version_dirs(child))
    return version_dirs


def folder_contains_auto_start(folder_path: str, auto_start_folders: set[str]) -> bool:
    if not folder_path:
        return bool(auto_start_folders)
    prefix = f"{folder_path}/" if folder_path else ""
    for configured in auto_start_folders:
        if configured == folder_path:
            return True
        if folder_path and configured.startswith(prefix):
            return True
    return False


def should_auto_start_version(version_dir: Path, auto_start_folders: set[str] | None = None) -> bool:
    configured = auto_start_folders if auto_start_folders is not None else get_auto_start_folders()
    relative = to_relative_path(version_dir)
    parts = relative.split("/")
    folder_parts = parts[:-1]
    if not folder_parts:
        return "" in configured
    for length in range(len(folder_parts), 0, -1):
        candidate = "/".join(folder_parts[:length])
        if candidate in configured:
            return True
    return "" in configured


def clean_dead_processes() -> None:
    dead = []
    for version_name, state in RUNNING_APPS.items():
        process = state.get("process")
        if process is not None and process.poll() is not None:
            dead.append(version_name)
    for version_name in dead:
        RUNNING_APPS.pop(version_name, None)


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def allocate_port() -> int:
    used_ports = {state["port"] for state in RUNNING_APPS.values() if "port" in state}
    port = BASE_PORT
    while port in used_ports or is_port_in_use(port):
        port += 1
    return port


def wait_for_app(url: str, timeout_seconds: int = START_TIMEOUT_SECONDS) -> bool:
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if response.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.5)
    return False


def terminate_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=4)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def append_log(version_name: str, message: str) -> None:
    if not message:
        return
    state = RUNNING_APPS.get(version_name)
    if state is None:
        return
    logs = state.setdefault("logs", [])
    logs.extend([line for line in message.splitlines() if line.strip()])
    if len(logs) > LOG_LIMIT:
        del logs[:-LOG_LIMIT]


def stream_process_output(version_name: str, process: subprocess.Popen[Any]) -> None:
    def reader(pipe: Any) -> None:
        try:
            for line in iter(pipe.readline, ""):
                append_log(version_name, line.rstrip())
        finally:
            pipe.close()

    if process.stdout is not None:
        threading.Thread(target=reader, args=(process.stdout,), daemon=True).start()
    if process.stderr is not None:
        threading.Thread(target=reader, args=(process.stderr,), daemon=True).start()


def build_runtime_state(version_name: str) -> dict[str, Any]:
    state = RUNNING_APPS.get(version_name)
    if not state:
        return {"running": False, "port": None, "launch_url": None, "iframe_url": None, "last_error": LAST_START_ERRORS.get(version_name)}
    process = state.get("process")
    if process is None or process.poll() is not None:
        RUNNING_APPS.pop(version_name, None)
        return {"running": False, "port": None, "launch_url": None, "iframe_url": None, "last_error": LAST_START_ERRORS.get(version_name)}
    port = state["port"]
    url = f"http://127.0.0.1:{port}"
    return {
        "running": True,
        "port": port,
        "launch_url": url,
        "iframe_url": f"{build_proxy_base_path(version_name)}/",
        "last_error": LAST_START_ERRORS.get(version_name),
    }


def start_version_process(version_name: str) -> dict[str, Any]:
    version_dir = safe_version_dir(version_name)

    with PROCESS_LOCK:
        clean_dead_processes()
        current = build_runtime_state(version_name)
        if current["running"]:
            return current

        port = allocate_port()
        LAST_START_ERRORS.pop(version_name, None)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "flask",
                "--app",
                "app",
                "run",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-debugger",
                "--no-reload",
            ],
            cwd=str(version_dir),
            env=build_child_env(version_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        RUNNING_APPS[version_name] = {
            "process": process,
            "port": port,
            "started_at": datetime.now().isoformat(),
            "logs": [f"Starting {version_name} on port {port}..."],
        }
        stream_process_output(version_name, process)

    launch_url = f"http://127.0.0.1:{port}"
    if not wait_for_app(launch_url):
        with PROCESS_LOCK:
            state = RUNNING_APPS.pop(version_name, None)

        process = state.get("process") if state else None
        error_text = "Die Version konnte nicht gestartet werden."

        if process is not None and process.poll() is None:
            terminate_process(process)

        log_lines = state.get("logs", []) if state else []
        if log_lines:
            error_text = log_lines[-1]

        LAST_START_ERRORS[version_name] = error_text
        raise RuntimeError(error_text)

    return build_runtime_state(version_name)


def stop_version_process(version_name: str) -> None:
    with PROCESS_LOCK:
        clean_dead_processes()
        state = RUNNING_APPS.pop(version_name, None)
    if state:
        terminate_process(state.get("process"))


def cleanup_all_processes() -> None:
    for version_name in list(RUNNING_APPS.keys()):
        stop_version_process(version_name)


def ensure_version_started(version_name: str) -> None:
    try:
        version_dir = safe_version_dir(version_name)
    except FileNotFoundError:
        return
    if not (version_dir / "app.py").exists():
        return
    runtime = build_runtime_state(version_name)
    if runtime["running"]:
        return
    try:
        start_version_process(version_name)
    except RuntimeError:
        pass


def ensure_versions_started(version_dirs: list[Path]) -> None:
    for version_dir in version_dirs:
        ensure_version_started(to_relative_path(version_dir))


def start_versions_in_background(version_dirs: list[Path]) -> None:
    version_names = [to_relative_path(version_dir) for version_dir in version_dirs]

    def runner() -> None:
        for version_name in version_names:
            try:
                ensure_version_started(version_name)
            except BaseException:
                LAST_START_ERRORS[version_name] = "Die Version konnte im Hintergrund nicht gestartet werden."

    threading.Thread(target=runner, daemon=True).start()


def start_all_versions_on_boot() -> None:
    auto_start_folders = get_auto_start_folders()
    versions = [version_dir for version_dir in list_all_version_dirs() if should_auto_start_version(version_dir, auto_start_folders)]
    start_versions_in_background(versions)


atexit.register(cleanup_all_processes)


def build_version_detail(version_dir: Path) -> dict[str, Any]:
    version_path = to_relative_path(version_dir)
    runtime = build_runtime_state(version_path)
    tree, file_count, dir_count, total_size = summarize_tree(version_dir)
    stat = version_dir.stat()
    readme_path = find_first([version_dir / "README.md", version_dir / "readme.md"])
    preview_file = find_first([version_dir / rel for rel in IMPORTANT_FILES if (version_dir / rel).exists()])
    important_files = []
    for rel in IMPORTANT_FILES:
        path = version_dir / rel
        if path.exists() and path.is_file():
            important_files.append({"name": rel, "path": rel.replace("\\", "/")})

    return {
        "name": version_dir.name,
        "path": version_path,
        "folder_path": normalize_relative_path(str(PurePosixPath(version_path).parent)),
        "tags": detect_stack(version_dir),
        "updated_at": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
        "file_count": file_count,
        "dir_count": dir_count,
        "size": human_size(total_size),
        "tree": tree,
        "readme": read_text_file(readme_path),
        "preview_file": preview_file.relative_to(version_dir).as_posix() if preview_file else None,
        "preview_content": read_text_file(preview_file),
        "important_files": important_files,
        "logs": RUNNING_APPS.get(version_path, {}).get("logs", []),
        "is_runnable": True,
        **runtime,
    }


def build_version_card(version_dir: Path) -> dict[str, Any]:
    detail = build_version_detail(version_dir)
    description = "Keine README gefunden."
    if detail["readme"]:
        compact = " ".join(detail["readme"].split())
        description = compact[:120] + ("..." if len(compact) > 120 else "")
    return {
        "name": detail["name"],
        "path": detail["path"],
        "folder_path": detail["folder_path"],
        "tags": detail["tags"],
        "updated_at": detail["updated_at"],
        "file_count": detail["file_count"],
        "dir_count": detail["dir_count"],
        "size": detail["size"],
        "description": description,
        "is_runnable": detail["is_runnable"],
        "running": detail["running"],
        "launch_url": detail["launch_url"],
        "iframe_url": detail["iframe_url"],
        "last_error": detail["last_error"],
    }


def build_folder_node(folder_dir: Path, auto_start_folders: set[str], is_root: bool = False) -> dict[str, Any]:
    folder_path = "" if is_root else to_relative_path(folder_dir)
    child_folders: list[dict[str, Any]] = []
    versions: list[dict[str, Any]] = []

    for child in iter_container_dirs(folder_dir):
        if is_version_dir(child):
            versions.append(build_version_card(child))
        else:
            child_folders.append(build_folder_node(child, auto_start_folders))

    latest_timestamp = None
    try:
        latest_timestamp = folder_dir.stat().st_mtime
    except OSError:
        latest_timestamp = None

    for version in versions:
        parsed = datetime.strptime(version["updated_at"], "%d.%m.%Y %H:%M")
        candidate = parsed.timestamp()
        latest_timestamp = max(latest_timestamp or candidate, candidate)

    for child_folder in child_folders:
        raw = child_folder.get("updated_at_raw")
        if raw is not None:
            latest_timestamp = max(latest_timestamp or raw, raw)

    total_versions = len(versions) + sum(child["version_count_total"] for child in child_folders)

    return {
        "name": "Versions" if is_root else folder_dir.name,
        "path": folder_path,
        "is_root": is_root,
        "auto_start": folder_path in auto_start_folders,
        "auto_start_contains_selected": folder_contains_auto_start(folder_path, auto_start_folders),
        "updated_at": datetime.fromtimestamp(latest_timestamp).strftime("%d.%m.%Y %H:%M") if latest_timestamp else "-",
        "updated_at_raw": latest_timestamp,
        "folder_count": len(child_folders),
        "version_count": len(versions),
        "version_count_total": total_versions,
        "folders": child_folders,
        "versions": versions,
    }


def build_versions_tree() -> dict[str, Any]:
    ensure_versions_dir()
    return build_folder_node(VERSIONS_DIR, get_auto_start_folders(), is_root=True)


def rewrite_proxied_text(content: bytes, version_name: str, launch_url: str, content_type: str) -> bytes:
    if not content:
        return content

    try:
        text = content.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
            encoding = "latin-1"
        except UnicodeDecodeError:
            return content

    proxy_base = build_proxy_base_path(version_name)
    proxy_root = f"{proxy_base}/"
    absolute_root = f"{launch_url}/"

    replacements = [
        (absolute_root, proxy_root),
        (launch_url, proxy_base),
        ('href="/', f'href="{proxy_root}'),
        ("href='/", f"href='{proxy_root}"),
        ('src="/', f'src="{proxy_root}'),
        ("src='/", f"src='{proxy_root}"),
        ('action="/', f'action="{proxy_root}'),
        ("action='/", f"action='{proxy_root}"),
        ('fetch("/', f'fetch("{proxy_root}'),
        ("fetch('/", f"fetch('{proxy_root}"),
        ('url("/', f'url("{proxy_root}'),
        ("url('/", f"url('{proxy_root}"),
        ('location.href="/', f'location.href="{proxy_root}'),
        ("location.href='/", f"location.href='{proxy_root}"),
        ('location = "/', f'location = "{proxy_root}'),
        ("location = '/", f"location = '{proxy_root}"),
        ('XMLHttpRequest().open("GET", "/', f'XMLHttpRequest().open("GET", "{proxy_root}'),
        ("XMLHttpRequest().open('GET', '/", f"XMLHttpRequest().open('GET', '{proxy_root}"),
    ]

    for source, target in replacements:
        text = text.replace(source, target)

    if "javascript" in content_type or "json" in content_type:
        text = text.replace('"/', f'"{proxy_root}')
        text = text.replace("'/", f"'{proxy_root}")
        text = text.replace("`/", f"`{proxy_root}")

    if "text/html" in content_type:
        bridge_script = f"""
<script>
(() => {{
    const proxyRoot = {json.dumps(proxy_root)};
    const absolutize = (value) => {{
        if (typeof value !== "string") return value;
        if (value.startsWith(proxyRoot) || value.startsWith("http://") || value.startsWith("https://") || value.startsWith("//")) return value;
        if (value.startsWith("/")) return proxyRoot + value.slice(1);
        return value;
    }};

    const originalFetch = window.fetch?.bind(window);
    if (originalFetch) {{
        window.fetch = (input, init) => {{
            if (typeof input === "string") return originalFetch(absolutize(input), init);
            if (input instanceof Request) return originalFetch(new Request(absolutize(input.url), input), init);
            return originalFetch(input, init);
        }};
    }}

    const OriginalEventSource = window.EventSource;
    if (OriginalEventSource) {{
        window.EventSource = function(url, config) {{
            return new OriginalEventSource(absolutize(url), config);
        }};
        window.EventSource.prototype = OriginalEventSource.prototype;
    }}

    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {{
        return originalOpen.call(this, method, absolutize(url), ...rest);
    }};
}})();
</script>
"""
        if "</head>" in text:
            text = text.replace("</head>", bridge_script + "\n</head>", 1)
        else:
            text = bridge_script + text

    return text.encode(encoding)


def rewrite_proxy_header_value(header_value: str, version_name: str, launch_url: str) -> str:
    proxy_base = build_proxy_base_path(version_name)
    proxy_root = f"{proxy_base}/"
    rewritten = header_value.replace(f"{launch_url}/", proxy_root).replace(launch_url, proxy_base)

    if rewritten.startswith("/"):
        rewritten = f"{proxy_root}{rewritten.lstrip('/')}"

    rewritten = re.sub(r"(?i)\bPath=/((?=;)|$)", f"Path={proxy_root}", rewritten)
    return rewritten


@app.route("/")
def index() -> str:
    clean_dead_processes()
    folder_tree = build_versions_tree()
    initial_detail = None
    return render_template(
        "index.html",
        folder_tree=folder_tree,
        initial_detail=initial_detail,
        versions_dir=str(VERSIONS_DIR),
    )


@app.route("/version/<path:version_name>")
def version_page(version_name: str) -> str:
    try:
        normalized = normalize_relative_path(version_name)
        version_dir = safe_version_dir(normalized)
    except FileNotFoundError:
        abort(404)

    if not build_runtime_state(normalized)["running"]:
        try:
            start_version_process(normalized)
        except RuntimeError:
            pass

    detail = build_version_detail(version_dir)
    return render_template("version.html", detail=detail)


@app.route("/api/tree")
def versions_tree():
    clean_dead_processes()
    return jsonify(build_versions_tree())


@app.route("/api/versions/<path:version_name>")
def version_detail(version_name: str):
    try:
        version_dir = safe_version_dir(version_name)
    except FileNotFoundError:
        abort(404)
    return jsonify(build_version_detail(version_dir))


@app.route("/api/versions/<path:version_name>/start", methods=["POST"])
def version_start(version_name: str):
    try:
        version_dir = safe_version_dir(version_name)
        detail = start_version_process(normalize_relative_path(version_name))
    except FileNotFoundError:
        abort(404)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    payload = build_version_detail(version_dir)
    payload.update(detail)
    return jsonify(payload)


@app.route("/api/versions/<path:version_name>/restart", methods=["POST"])
def version_restart(version_name: str):
    try:
        normalized = normalize_relative_path(version_name)
        version_dir = safe_version_dir(normalized)
    except FileNotFoundError:
        abort(404)
    stop_version_process(normalized)
    try:
        start_version_process(normalized)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(build_version_detail(version_dir))


@app.route("/api/folders/autostart", methods=["POST"])
def folder_autostart():
    payload = request.get_json(silent=True) or {}
    folder_path = payload.get("folder_path", "")
    enabled = bool(payload.get("enabled"))
    try:
        settings = set_folder_auto_start(folder_path, enabled)
        folder_dir = safe_versions_child(folder_path)
    except FileNotFoundError:
        abort(404)
    if enabled:
        start_versions_in_background(
            [
                version_dir
                for version_dir in list_all_version_dirs(folder_dir)
                if should_auto_start_version(version_dir, set(settings["auto_start_folders"]))
            ]
        )
    return jsonify(build_versions_tree())


@app.route("/proxy/<version_token>/", defaults={"subpath": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@app.route("/proxy/<version_token>/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def proxy_version(version_token: str, subpath: str):
    try:
        normalized = decode_version_token(version_token)
        safe_version_dir(normalized)
    except FileNotFoundError:
        abort(404)

    runtime = build_runtime_state(normalized)
    if not runtime["running"]:
        try:
            runtime = start_version_process(normalized)
        except RuntimeError as exc:
            return Response(str(exc), status=502, mimetype="text/plain")

    target_url = runtime["launch_url"]
    if subpath:
        target_url = f"{target_url}/{subpath}"
    elif not request.path.endswith("/"):
        target_url = f"{target_url}/"

    if request.query_string:
        target_url = f"{target_url}?{request.query_string.decode('utf-8', errors='ignore')}"

    outgoing_headers = {}
    for header_name, header_value in request.headers.items():
        if header_name.lower() in {"host", "content-length"}:
            continue
        outgoing_headers[header_name] = header_value

    payload = request.get_data() if request.method in {"POST", "PUT", "PATCH", "DELETE"} else None
    proxy_request = urllib.request.Request(target_url, data=payload, headers=outgoing_headers, method=request.method)

    try:
        upstream = PROXY_OPENER.open(proxy_request, timeout=60)
    except urllib.error.HTTPError as error:
        upstream = error
    except urllib.error.URLError as error:
        return Response(f"Proxy-Fehler: {error.reason}", status=502, mimetype="text/plain")

    body = upstream.read()
    content_type = upstream.headers.get("Content-Type", "")
    lowered_type = content_type.lower()
    if any(token in lowered_type for token in ("text/html", "text/css", "javascript", "json", "svg", "xml")):
        body = rewrite_proxied_text(body, normalized, runtime["launch_url"], lowered_type)

    response = Response(body, status=getattr(upstream, "status", 200))
    excluded_headers = {"content-length", "transfer-encoding", "content-encoding", "connection"}
    for header_name, header_value in upstream.headers.items():
        if header_name.lower() in excluded_headers:
            continue
        if header_name.lower() == "set-cookie":
            continue
        if header_name.lower() == "location":
            header_value = rewrite_proxy_header_value(header_value, normalized, runtime["launch_url"])
        response.headers[header_name] = header_value

    for cookie_header in upstream.headers.get_all("Set-Cookie", []):
        response.headers.add("Set-Cookie", rewrite_proxy_header_value(cookie_header, normalized, runtime["launch_url"]))

    return response


@app.route("/api/versions/<path:version_name>/file/<path:file_path>")
def version_file(version_name: str, file_path: str):
    try:
        version_dir = safe_version_dir(version_name)
    except FileNotFoundError:
        abort(404)
    target = (version_dir / file_path).resolve()
    try:
        target.relative_to(version_dir)
    except ValueError:
        abort(404)
    if not target.exists() or not target.is_file():
        abort(404)
    content = read_text_file(target)
    if content is None:
        mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return jsonify({"name": file_path, "binary": True, "mime_type": mime_type})
    return jsonify({"name": file_path, "binary": False, "content": content})


@app.route("/preview/<path:version_name>/<path:file_path>")
def preview_asset(version_name: str, file_path: str):
    try:
        version_dir = safe_version_dir(version_name)
    except FileNotFoundError:
        abort(404)
    target = (version_dir / file_path).resolve()
    try:
        target.relative_to(version_dir)
    except ValueError:
        abort(404)
    if not target.exists() or not target.is_file():
        abort(404)
    return send_file(target)


if __name__ == "__main__":
    ensure_versions_dir()
    load_launcher_settings()
    start_all_versions_on_boot()
    app.run(debug=False, port=5000, use_reloader=False)



