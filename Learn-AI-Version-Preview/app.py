from __future__ import annotations

import atexit
import mimetypes
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, send_file

BASE_DIR = Path(__file__).resolve().parent
VERSIONS_DIR = BASE_DIR / "Versions"
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


def ensure_versions_dir() -> None:
    VERSIONS_DIR.mkdir(exist_ok=True)


def safe_version_dir(version_name: str) -> Path:
    target = (VERSIONS_DIR / version_name).resolve()
    try:
        target.relative_to(VERSIONS_DIR.resolve())
    except ValueError as exc:
        raise FileNotFoundError from exc
    if not target.exists() or not target.is_dir():
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
        return content[:MAX_TEXT_LENGTH] + "\n\n... Vorschau gekuerzt ..."
    return content


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
    return {"running": True, "port": port, "launch_url": url, "iframe_url": url, "last_error": LAST_START_ERRORS.get(version_name)}


def start_version_process(version_name: str) -> dict[str, Any]:
    version_dir = safe_version_dir(version_name)
    if not (version_dir / "app.py").exists():
        raise RuntimeError("In dieser Version wurde keine app.py gefunden.")

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
            env={**os.environ, "PYTHONUTF8": "1"},
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
        ensure_version_started(version_dir.name)


atexit.register(cleanup_all_processes)


def build_version_detail(version_dir: Path) -> dict[str, Any]:
    runtime = build_runtime_state(version_dir.name)
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
        "logs": RUNNING_APPS.get(version_dir.name, {}).get("logs", []),
        "is_runnable": (version_dir / "app.py").exists(),
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


def list_version_dirs() -> list[Path]:
    ensure_versions_dir()
    return sorted([path for path in VERSIONS_DIR.iterdir() if path.is_dir()], key=lambda path: path.stat().st_mtime, reverse=True)


@app.route("/")
def index() -> str:
    clean_dead_processes()
    versions = list_version_dirs()
    ensure_versions_started(versions)
    cards = [build_version_card(path) for path in versions]
    initial_detail = None
    return render_template("index.html", versions=cards, initial_detail=initial_detail, versions_dir=str(VERSIONS_DIR))


@app.route("/api/versions")
def versions_list():
    clean_dead_processes()
    versions = list_version_dirs()
    ensure_versions_started(versions)
    return jsonify([build_version_card(path) for path in versions])


@app.route("/api/versions/<path:version_name>")
def version_detail(version_name: str):
    try:
        ensure_version_started(version_name)
        version_dir = safe_version_dir(version_name)
    except FileNotFoundError:
        abort(404)
    return jsonify(build_version_detail(version_dir))


@app.route("/api/versions/<path:version_name>/restart", methods=["POST"])
def version_restart(version_name: str):
    try:
        version_dir = safe_version_dir(version_name)
    except FileNotFoundError:
        abort(404)
    stop_version_process(version_name)
    try:
        start_version_process(version_name)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(build_version_detail(version_dir))


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
    app.run(debug=False, port=5000, use_reloader=False)



