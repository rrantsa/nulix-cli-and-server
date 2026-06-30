from __future__ import annotations

import re
import shlex
from dataclasses import dataclass


DANGEROUS_MARKER = "#DANGEROUS"
UNKNOWN_MARKER = "#UNKNOWN"

MULTI_COMMAND_TOKENS = ("&&", "||", ";", "\n", "\r")

DANGEROUS_PATTERNS = [
    re.compile(r"\brm\s+-[^\n]*\brf\b[^\n]*(?:^|\s)/(?=\s|$)", re.IGNORECASE),
    re.compile(r"\bmkfs(?:\.[a-z0-9_+-]+)?\b", re.IGNORECASE),
    re.compile(r"\bdd\b", re.IGNORECASE),
    re.compile(r"chmod\s+-R\s+777\s+/", re.IGNORECASE),
    re.compile(r"chown\s+-R\b[^\n]*\s+/", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\|:&\s*;\s*\}\s*;", re.IGNORECASE),
    re.compile(r"/dev/sd[a-z][a-z0-9]*", re.IGNORECASE),
    re.compile(r"/dev/nvme\d+n\d+(?:p\d+)?", re.IGNORECASE),
]


@dataclass(frozen=True)
class ValidationResult:
    command: str
    dangerous: bool


def shell_echo(payload: str) -> str:
    return f"echo {shlex.quote(payload)}"


def normalize_model_output(raw_output: str) -> str:
    text = raw_output.strip()
    text = text.replace("```bash", "").replace("```sh", "").replace("```", "").strip()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return UNKNOWN_MARKER
    if len(lines) > 1:
        return UNKNOWN_MARKER

    line = lines[0]
    if line.startswith("- "):
        return UNKNOWN_MARKER
    if line.startswith("1. "):
        return UNKNOWN_MARKER
    return line


def looks_dangerous(command: str) -> bool:
    normalized = command.strip()
    return any(pattern.search(normalized) for pattern in DANGEROUS_PATTERNS)


def is_single_command(command: str) -> bool:
    if not command.strip():
        return False
    return not any(token in command for token in MULTI_COMMAND_TOKENS)


def dangerous_response(original_command: str) -> ValidationResult:
    detail = f"{DANGEROUS_MARKER} {original_command.strip()}".strip()
    return ValidationResult(command=shell_echo(detail), dangerous=True)


def unknown_response() -> ValidationResult:
    return ValidationResult(command=shell_echo(UNKNOWN_MARKER), dangerous=False)


def validate_generated_command(raw_output: str) -> ValidationResult:
    command = normalize_model_output(raw_output)
    upper = command.upper().replace(" ", "")

    if command.startswith("# DANGEROUS") or command.startswith(DANGEROUS_MARKER) or upper.startswith(DANGEROUS_MARKER):
        return dangerous_response("blocked-by-model")

    if command.startswith("# UNKNOWN") or command.startswith(UNKNOWN_MARKER) or upper.startswith(UNKNOWN_MARKER):
        return unknown_response()

    if not is_single_command(command):
        return unknown_response()

    if looks_dangerous(command):
        return dangerous_response(command)

    return ValidationResult(command=command, dangerous=False)
