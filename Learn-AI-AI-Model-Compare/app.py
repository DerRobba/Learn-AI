import os
import json
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Thread

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, stream_with_context
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "learn-ai-model-compare")


def _clean_env(value: str | None, default: str = "") -> str:
    if value is None:
        return default
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned or default


def _float_env(name: str, default: float) -> float:
    raw_value = _clean_env(os.getenv(name))
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


APP_TITLE = _clean_env(os.getenv("APP_TITLE"), "Learn-AI Model Compare")
SYSTEM_PROMPT = _clean_env(
    os.getenv("SYSTEM_PROMPT"),
    "Du bist ein hilfreicher Assistent. Antworte auf Deutsch.",
)
REQUEST_TIMEOUT = _float_env("REQUEST_TIMEOUT", 90.0)

MODEL_CONFIGS = {
    "original": {
        "label": "Originalmodell",
        "base_url": _clean_env(os.getenv("ORIGINAL_BASE_URL"), "https://openrouter.ai/api/v1"),
        "model": _clean_env(os.getenv("ORIGINAL_MODEL")),
        "api_key": _clean_env(os.getenv("ORIGINAL_API_KEY")),
        "badge": "Base",
    },
    "tuned": {
        "label": "Fine-Tune",
        "base_url": _clean_env(os.getenv("TUNED_BASE_URL"), "https://openrouter.ai/api/v1"),
        "model": _clean_env(os.getenv("TUNED_MODEL")),
        "api_key": _clean_env(os.getenv("TUNED_API_KEY")),
        "badge": "Tuned",
    },
}


def _build_messages(system_prompt: str, history: list[dict], prompt: str) -> list[dict]:
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})

    for item in history:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": prompt.strip()})
    return messages


def _model_status(config: dict) -> dict:
    configured = bool(config["model"] and config["api_key"])
    return {
        "label": config["label"],
        "model": config["model"] or "Nicht gesetzt",
        "base_url": config["base_url"],
        "configured": configured,
        "badge": config["badge"],
    }


def _compare_summary(original_text: str, tuned_text: str) -> str:
    if original_text.strip() == tuned_text.strip():
        return "Beide Modelle haben inhaltlich sehr aehnlich geantwortet."

    original_length = len(original_text.split())
    tuned_length = len(tuned_text.split())

    if tuned_length > original_length:
        return "Der Fine-Tune antwortet ausfuehrlicher als das Originalmodell."
    if tuned_length < original_length:
        return "Das Originalmodell antwortet ausfuehrlicher als der Fine-Tune."
    return "Beide Antworten sind unterschiedlich formuliert, aber aehnlich lang."


def _extract_text_from_choice(choice) -> str:
    message = getattr(choice, "message", None)
    if message is not None:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text" and item.get("text"):
                        text_parts.append(str(item["text"]))
                else:
                    item_type = getattr(item, "type", None)
                    item_text = getattr(item, "text", None)
                    if item_type == "text" and item_text:
                        text_parts.append(str(item_text))
            if text_parts:
                return "\n".join(text_parts)

    text = getattr(choice, "text", None)
    if isinstance(text, str):
        return text

    return ""


def _extract_text_from_delta(delta) -> str:
    if delta is None:
        return ""

    content = getattr(delta, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    text_parts.append(str(item["text"]))
            else:
                item_type = getattr(item, "type", None)
                item_text = getattr(item, "text", None)
                if item_type == "text" and item_text:
                    text_parts.append(str(item_text))
        return "".join(text_parts)

    text = getattr(delta, "text", None)
    if isinstance(text, str):
        return text
    return ""


def _result_from_text(kind: str, text: str, duration_ms: int, usage) -> dict:
    config = MODEL_CONFIGS[kind]
    return {
        "kind": kind,
        "label": config["label"],
        "model": config["model"],
        "text": text,
        "duration_ms": duration_ms,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "word_count": len(text.split()),
        "char_count": len(text),
    }


def _request_completion(kind: str, messages: list[dict]) -> dict:
    config = MODEL_CONFIGS[kind]
    if not config["model"] or not config["api_key"]:
        raise ValueError(
            f"{config['label']} ist nicht vollstaendig konfiguriert. Bitte pruefe Modellname und API Key in der .env."
        )

    client = OpenAI(base_url=config["base_url"], api_key=config["api_key"], timeout=REQUEST_TIMEOUT)

    started = time.perf_counter()
    response = client.chat.completions.create(
        model=config["model"],
        messages=messages,
    )
    duration_ms = round((time.perf_counter() - started) * 1000)

    choices = getattr(response, "choices", None) or []
    if not choices:
        raise ValueError(f"{config['label']} hat keine Antwort geliefert.")

    content = _extract_text_from_choice(choices[0]).strip()
    if not content:
        raise ValueError(
            f"{config['label']} hat eine leere oder nicht kompatible Antwort geliefert. "
            f"Bitte pruefe, ob der Endpoint unter {config['base_url']} wirklich OpenAI-kompatibel ist."
        )

    usage = getattr(response, "usage", None)

    return _result_from_text(kind, content, duration_ms, usage)


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stream_model(kind: str, messages: list[dict], event_queue: Queue) -> None:
    config = MODEL_CONFIGS[kind]
    try:
        if not config["model"] or not config["api_key"]:
            raise ValueError(
                f"{config['label']} ist nicht vollstaendig konfiguriert. Bitte pruefe Modellname und API Key in der .env."
            )

        client = OpenAI(base_url=config["base_url"], api_key=config["api_key"], timeout=REQUEST_TIMEOUT)
        started = time.perf_counter()
        stream = client.chat.completions.create(
            model=config["model"],
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
        )

        text_parts = []
        usage = None

        for chunk in stream:
            if getattr(chunk, "usage", None) is not None:
                usage = chunk.usage

            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue

            choice = choices[0]
            delta = getattr(choice, "delta", None)
            text = _extract_text_from_delta(delta)
            if text:
                text_parts.append(text)
                event_queue.put(("chunk", {"kind": kind, "text": text}))

        full_text = "".join(text_parts).strip()
        duration_ms = round((time.perf_counter() - started) * 1000)

        if not full_text:
            raise ValueError(
                f"{config['label']} hat eine leere oder nicht kompatible Antwort geliefert. "
                f"Bitte pruefe, ob der Endpoint unter {config['base_url']} wirklich OpenAI-kompatibel ist."
            )

        event_queue.put(("done", {"kind": kind, "result": _result_from_text(kind, full_text, duration_ms, usage)}))
    except Exception as exc:
        event_queue.put(("error", {"kind": kind, "message": str(exc)}))


@app.get("/")
def index():
    statuses = {key: _model_status(config) for key, config in MODEL_CONFIGS.items()}
    return render_template(
        "index.html",
        app_title=APP_TITLE,
        system_prompt=SYSTEM_PROMPT,
        statuses=statuses,
    )


@app.get("/api/health")
def health():
    return jsonify(
        {
            "ok": True,
            "title": APP_TITLE,
            "models": {key: _model_status(config) for key, config in MODEL_CONFIGS.items()},
        }
    )


@app.post("/api/compare")
def compare():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or "").strip()
    system_prompt = (payload.get("system_prompt") or SYSTEM_PROMPT).strip()
    history = payload.get("history") or []

    if not prompt:
        return jsonify({"error": "Bitte gib zuerst einen Prompt ein."}), 400

    messages = _build_messages(system_prompt, history, prompt)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            original_future = executor.submit(_request_completion, "original", messages)
            tuned_future = executor.submit(_request_completion, "tuned", messages)
            original_result = original_future.result()
            tuned_result = tuned_future.result()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Die Anfrage an die Modelle ist fehlgeschlagen: {exc}"}), 502

    comparison = {
        "summary": _compare_summary(original_result["text"], tuned_result["text"]),
        "faster_model": (
            original_result["label"]
            if original_result["duration_ms"] < tuned_result["duration_ms"]
            else tuned_result["label"]
        ),
    }

    return jsonify(
        {
            "prompt": prompt,
            "system_prompt": system_prompt,
            "responses": {
                "original": original_result,
                "tuned": tuned_result,
            },
            "comparison": comparison,
        }
    )


@app.post("/api/compare/stream")
def compare_stream():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or "").strip()
    system_prompt = (payload.get("system_prompt") or SYSTEM_PROMPT).strip()
    history = payload.get("history") or []

    if not prompt:
        return jsonify({"error": "Bitte gib zuerst einen Prompt ein."}), 400

    messages = _build_messages(system_prompt, history, prompt)

    def generate():
        event_queue: Queue = Queue()
        results = {}

        threads = [
            Thread(target=_stream_model, args=("original", messages, event_queue), daemon=True),
            Thread(target=_stream_model, args=("tuned", messages, event_queue), daemon=True),
        ]

        for thread in threads:
            thread.start()

        completed = 0
        yield _sse_event("start", {"ok": True})

        while completed < 2:
            event_type, payload = event_queue.get()

            if event_type == "chunk":
                yield _sse_event("chunk", payload)
                continue

            if event_type == "done":
                results[payload["kind"]] = payload["result"]
                completed += 1
                yield _sse_event("done", payload)
                continue

            if event_type == "error":
                yield _sse_event("error", payload)
                return

        comparison = {
            "summary": _compare_summary(results["original"]["text"], results["tuned"]["text"]),
            "faster_model": (
                results["original"]["label"]
                if results["original"]["duration_ms"] < results["tuned"]["duration_ms"]
                else results["tuned"]["label"]
            ),
        }
        yield _sse_event(
            "complete",
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "responses": results,
                "comparison": comparison,
            },
        )

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True)
