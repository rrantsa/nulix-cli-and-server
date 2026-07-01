from __future__ import annotations

import os

import requests

from prompt import build_user_prompt, system_prompt


class ModelProviderConfigError(RuntimeError):
    pass


def get_model_provider() -> str:
    return os.getenv("NULIX_MODEL_PROVIDER", "ollama").strip().lower()


def get_timeout_seconds() -> float:
    return float(os.getenv("NULIX_MODEL_TIMEOUT_SECONDS", os.getenv("OLLAMA_TIMEOUT_SECONDS", "20")))


def get_model_name(default: str) -> str:
    return os.getenv("NULIX_MODEL_NAME", default).strip()


def request_ollama(system: str, prompt: str) -> str:
    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    model_name = get_model_name("llama3.2:3b")

    response = requests.post(
        f"{ollama_url.rstrip('/')}/api/generate",
        json={
            "model": model_name,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        },
        timeout=get_timeout_seconds(),
    )
    response.raise_for_status()

    payload = response.json()
    generated = payload.get("response", "").strip()
    if not generated:
        raise ModelProviderConfigError("Ollama returned an empty response")
    return generated


def request_openai_compatible(system: str, prompt: str) -> str:
    base_url = os.getenv("NULIX_EXTERNAL_API_BASE_URL", "").strip()
    api_key = os.getenv("NULIX_EXTERNAL_API_KEY", "").strip()
    api_path = os.getenv("NULIX_EXTERNAL_API_PATH", "/chat/completions").strip()
    model_name = get_model_name("gpt-4.1-mini")

    if not base_url:
        raise ModelProviderConfigError("NULIX_EXTERNAL_API_BASE_URL is required for openai_compatible provider")
    if not api_key:
        raise ModelProviderConfigError("NULIX_EXTERNAL_API_KEY is required for openai_compatible provider")

    path = api_path if api_path.startswith("/") else f"/{api_path}"
    response = requests.post(
        f"{base_url.rstrip('/')}{path}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        },
        timeout=get_timeout_seconds(),
    )
    response.raise_for_status()

    payload = response.json()
    choices = payload.get("choices") or []
    if not choices:
        raise ModelProviderConfigError("External API returned no choices")

    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        generated = "".join(text_parts).strip()
    else:
        generated = str(content).strip()

    if not generated:
        raise ModelProviderConfigError("External API returned an empty response")
    return generated


def generate_text_from_model(system: str, prompt: str) -> str:
    provider = get_model_provider()
    if provider == "ollama":
        return request_ollama(system, prompt)
    if provider == "openai_compatible":
        return request_openai_compatible(system, prompt)
    raise ModelProviderConfigError(f"Unsupported NULIX_MODEL_PROVIDER: {provider}")


def generate_command_from_model(user_text: str) -> str:
    return generate_text_from_model(system_prompt(), build_user_prompt(user_text))
