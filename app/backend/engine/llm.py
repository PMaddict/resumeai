"""Thin client for a local Ollama server.

Every call in this app that needs the LLM to return structured data uses
`generate_json`, which asks Ollama for JSON-mode output and parses it. If the
model returns something that isn't valid JSON, we raise -- callers must
handle that explicitly rather than silently falling back to invented data.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .config import get_settings

logger = logging.getLogger("resumeai.llm")


class LLMError(RuntimeError):
    pass


def _endpoint(path: str) -> str:
    host = get_settings()["llm"]["host"].rstrip("/")
    return f"{host}{path}"


def is_available() -> bool:
    try:
        r = requests.get(_endpoint("/"), timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


def generate_json(system_prompt: str, user_prompt: str, *, retries: int = 1, num_predict: int = 4096) -> Any:
    """Call the local model and parse its reply as JSON.

    Raises LLMError if the server is unreachable or the model never returns
    parseable JSON after `retries` attempts. `num_predict` is set generously
    by default because the small local model will silently truncate long
    JSON extractions under Ollama's default output-length cap, which looks
    exactly like the model "forgetting" items rather than an obvious error.
    """
    settings = get_settings()["llm"]
    payload = {
        "model": settings["model"],
        "system": system_prompt,
        "prompt": user_prompt,
        "format": "json",
        "stream": False,
        "options": {"temperature": settings.get("temperature", 0.1), "num_predict": num_predict},
    }

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                _endpoint("/api/generate"),
                json=payload,
                timeout=settings.get("request_timeout_seconds", 180),
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
            return json.loads(raw)
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("LLM request failed (attempt %s): %s", attempt, exc)
        except json.JSONDecodeError as exc:
            last_error = exc
            logger.warning("LLM returned invalid JSON (attempt %s): %s", attempt, exc)

    raise LLMError(
        f"Local model at {settings['host']} did not return usable JSON "
        f"after {retries + 1} attempt(s): {last_error}"
    )
