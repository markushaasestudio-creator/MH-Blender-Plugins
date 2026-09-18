from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    pass


def normalize_endpoint(endpoint: str) -> str:
    value = (endpoint or "http://127.0.0.1:11434").strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = "http://" + value
    return value


def is_local_endpoint(endpoint: str) -> bool:
    parsed = urlparse(normalize_endpoint(endpoint))
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _request_json(endpoint: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    url = normalize_endpoint(endpoint) + path
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, method="GET" if payload is None else "POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        raise OllamaError(f"Ollama HTTP {exc.code}: {detail[:1000]}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise OllamaError(f"Could not reach Ollama at {normalize_endpoint(endpoint)}: {exc}") from exc
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise OllamaError(f"Ollama returned invalid JSON: {raw[:800]}") from exc


def list_models(endpoint: str, timeout: int = 20) -> list[dict[str, Any]]:
    payload = _request_json(endpoint, "/api/tags", None, timeout=timeout)
    return list(payload.get("models", []))


def show_model(endpoint: str, model: str, timeout: int = 30) -> dict[str, Any]:
    if not model.strip():
        raise OllamaError("No Ollama model name is configured")
    return _request_json(endpoint, "/api/show", {"model": model.strip()}, timeout=timeout)


def model_capabilities(endpoint: str, model: str, timeout: int = 30) -> list[str]:
    info = show_model(endpoint, model, timeout=timeout)
    caps = [str(v).lower() for v in (info.get("capabilities") or [])]
    if "vision" not in caps:
        projector = info.get("projector_info") or {}
        model_info = info.get("model_info") or {}
        if projector or any(".vision." in str(key).lower() for key in model_info):
            caps.append("vision")
    return caps


def _encode_image(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise OllamaError(f"Image not found: {p}")
    return base64.b64encode(p.read_bytes()).decode("ascii")


def _content_json(text: str) -> dict[str, Any]:
    content = (text or "").strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OllamaError(f"Model response was not valid structured JSON: {content[:1200]}") from exc
    if not isinstance(value, dict):
        raise OllamaError("Structured Ollama response must be a JSON object")
    return value


def chat_structured(
    endpoint: str,
    model: str,
    prompt: str,
    image_paths: list[str | Path],
    schema: dict[str, Any],
    *,
    system: str = "",
    timeout: int = 180,
    allow_remote: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    endpoint = normalize_endpoint(endpoint)
    if not allow_remote and not is_local_endpoint(endpoint):
        raise OllamaError(
            "Refusing to send studio images to a non-local Ollama endpoint. "
            "Enable 'Allow non-local endpoint' explicitly if this is intentional."
        )
    capabilities = model_capabilities(endpoint, model, timeout=min(timeout, 30))
    if "vision" not in capabilities:
        raise OllamaError(
            f"Model '{model}' does not advertise Ollama's 'vision' capability. "
            "Choose a Qwen/Qwen-VL model with vision support for floorplan semantics."
        )

    images = [_encode_image(path) for path in image_paths]
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt, "images": images})
    request_payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": schema,
        "options": {"temperature": 0},
    }
    response = _request_json(endpoint, "/api/chat", request_payload, timeout=timeout)
    content = str(response.get("message", {}).get("content", ""))
    return _content_json(content), response
