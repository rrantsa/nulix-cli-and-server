#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys

import requests


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "memorize":
        parser = argparse.ArgumentParser(description="Store an admin-approved intent to command mapping.")
        parser.add_argument("mode", choices=["memorize"])
        parser.add_argument("intent", help="Primary natural-language intent to memorize")
        parser.add_argument("command", help="Shell command template to store")
        parser.add_argument(
            "--alias",
            action="append",
            default=[],
            help="Additional intent phrasing to store for the same command",
        )
        return parser.parse_args(argv)

    parser = argparse.ArgumentParser(description="Translate natural language into one Bash shell line.")
    parser.add_argument("text", nargs="+", help="Linux intent in natural language")
    args = parser.parse_args(argv)
    args.mode = "generate"
    return args


def _extract_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if detail:
            return str(detail)

    body = response.text.strip()
    return body or f"HTTP {response.status_code}"


def _post_json(
    api_url: str,
    api_key: str,
    path: str,
    payload: dict,
    timeout_seconds: float,
) -> requests.Response:
    response = requests.post(
        f"{api_url.rstrip('/')}{path}",
        headers={"X-API-Key": api_key},
        json=payload,
        timeout=timeout_seconds,
    )
    return response


def _run_generate(api_url: str, api_key: str, text: str, timeout_seconds: float) -> int:
    try:
        response = _post_json(
            api_url=api_url,
            api_key=api_key,
            path="/generate",
            payload={"text": text},
            timeout_seconds=timeout_seconds,
        )
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    if not response.ok:
        print(f"Request failed: {_extract_error_detail(response)}", file=sys.stderr)
        return 1

    payload = response.json()
    command = payload.get("command")
    if not command:
        print("Invalid API response: missing command.", file=sys.stderr)
        return 1

    print(command)
    return 0


def _run_memorize(
    api_url: str,
    admin_api_key: str,
    intent: str,
    command: str,
    aliases: list[str],
    timeout_seconds: float,
) -> int:
    try:
        response = _post_json(
            api_url=api_url,
            api_key=admin_api_key,
            path="/rules",
            payload={
                "intent": intent,
                "command": command,
                "aliases": aliases,
            },
            timeout_seconds=timeout_seconds,
        )
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    if not response.ok:
        print(f"Request failed: {_extract_error_detail(response)}", file=sys.stderr)
        return 1

    payload = response.json()
    print(
        "memorized"
        f" created={payload.get('created', 0)}"
        f" duplicates={payload.get('duplicates', 0)}"
        f" category={payload.get('category', 'user-added')}"
    )
    return 0


def main() -> int:
    args = parse_args()
    api_url = os.getenv("NULIX_API_URL")
    timeout_seconds = float(os.getenv("NULIX_CLIENT_TIMEOUT_SECONDS", "15"))

    if not api_url:
        print("NULIX_API_URL is not set.", file=sys.stderr)
        return 1

    if args.mode == "memorize":
        admin_api_key = os.getenv("NULIX_ADMIN_API_KEY")
        if not admin_api_key:
            print("NULIX_ADMIN_API_KEY is not set.", file=sys.stderr)
            return 1

        return _run_memorize(
            api_url=api_url,
            admin_api_key=admin_api_key,
            intent=args.intent,
            command=args.command,
            aliases=args.alias,
            timeout_seconds=timeout_seconds,
        )

    api_key = os.getenv("NULIX_API_KEY")
    if not api_key:
        print("NULIX_API_KEY is not set.", file=sys.stderr)
        return 1

    return _run_generate(
        api_url=api_url,
        api_key=api_key,
        text=" ".join(args.text).strip(),
        timeout_seconds=timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
