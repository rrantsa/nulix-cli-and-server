from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import requests
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from knowledge import KnowledgeBase, get_knowledge_base
from prompt import (
    adaptation_system_prompt,
    build_adaptation_prompt,
    build_user_prompt,
    system_prompt,
)
from validator import ValidationResult, validate_generated_command


class GenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Natural-language Linux intent")


class GenerateResponse(BaseModel):
    command: str
    dangerous: bool


class HealthResponse(BaseModel):
    status: str


app = FastAPI(title="Nulix API", version="0.1.0")


def load_api_keys(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(f"API key file not found: {path}")

    keys = {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    return keys


def ensure_api_key(api_key: str | None, keys: Iterable[str]) -> None:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API key",
        )

    if api_key not in keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )


def _ollama_generate(system: str, prompt: str) -> str:
    """Call Ollama with the given system + user prompt and return the response text."""
    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")
    timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20"))

    response = requests.post(
        f"{ollama_url.rstrip('/')}/api/generate",
        json={
            "model": ollama_model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()

    payload = response.json()
    generated = payload.get("response", "").strip()
    if not generated:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ollama returned an empty response",
        )
    return generated


def generate_command_from_ollama(user_text: str) -> str:
    """Direct generation — used as fallback when KB has no good match."""
    return _ollama_generate(system_prompt(), build_user_prompt(user_text))


import re as _re


def _revert_hallucinated_placeholders(
    adapted: str, template: str, user_text: str
) -> str:
    """If Qwen invented values for placeholders the user didn't specify,
    put the original placeholders back."""
    import re as _re

    placeholders = _re.findall(r"\{(\w+)\}", template)
    if not placeholders:
        return adapted

    user_words = set(user_text.lower().split())

    for ph in placeholders:
        for token in adapted.split():
            clean = token.strip("\"';")
            if not clean:
                continue
            # Path-like tokens not in the user's original request
            # are almost certainly model hallucinations
            if clean.startswith("/") and clean.lower() not in user_words:
                if clean not in user_text and clean not in template:
                    if not clean.startswith("/dev/"):
                        adapted = adapted.replace(clean, "{" + ph + "}", 1)
                        break

    return adapted


def generate_command_with_kb(
    user_text: str,
    kb: KnowledgeBase,
) -> str:
    """KB-first generation: search KB, adapt best match with Qwen.

    Falls back to direct generation when the KB returns no results.
    If Qwen hallucinates placeholder values, those are reverted.
    """
    matches = kb.search(user_text, limit=3)
    if not matches:
        return generate_command_from_ollama(user_text)

    best = matches[0]
    template = best["command"]

    # Adaptation mode — ask Qwen to fill in template placeholders
    adapted = _ollama_generate(
        adaptation_system_prompt(),
        build_adaptation_prompt(template, user_text),
    )

    # Safety net: if Qwen hallucinated values, revert to placeholders
    if "{" not in adapted and "{" in template:
        adapted = _revert_hallucinated_placeholders(adapted, template, user_text)

    return adapted


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


_kb: KnowledgeBase | None = None


def _get_kb() -> KnowledgeBase | None:
    global _kb
    if _kb is None:
        import os as _os

        enabled = _os.getenv("NULIX_KB_ENABLED", "true").lower() not in ("0", "false", "no")
        if not enabled:
            return None
        _kb = get_knowledge_base()
    return _kb


@app.post("/generate", response_model=GenerateResponse)
def generate(
    request: GenerateRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> GenerateResponse:
    keys_file = Path(os.getenv("NULIX_API_KEYS_FILE", "/opt/nulix/api_keys.txt"))
    try:
        keys = load_api_keys(keys_file)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    ensure_api_key(x_api_key, keys)

    try:
        kb = _get_kb()
        if kb is not None:
            raw_command = generate_command_with_kb(request.text, kb)
        else:
            raw_command = generate_command_from_ollama(request.text)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollama request failed: {exc}",
        ) from exc

    result: ValidationResult = validate_generated_command(raw_command)
    return GenerateResponse(command=result.command, dangerous=result.dangerous)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.getenv("NULIX_SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("NULIX_SERVER_PORT", "8000")),
        reload=False,
    )
