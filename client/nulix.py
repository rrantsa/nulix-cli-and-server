#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate natural language into one Bash shell line.")
    parser.add_argument("text", nargs="+", help="Linux intent in natural language")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_url = os.getenv("NULIX_API_URL")
    api_key = os.getenv("NULIX_API_KEY")
    timeout_seconds = float(os.getenv("NULIX_CLIENT_TIMEOUT_SECONDS", "15"))

    if not api_url:
        print("NULIX_API_URL is not set.", file=sys.stderr)
        return 1

    if not api_key:
        print("NULIX_API_KEY is not set.", file=sys.stderr)
        return 1

    try:
        response = requests.post(
            f"{api_url.rstrip('/')}/generate",
            headers={"X-API-Key": api_key},
            json={"text": " ".join(args.text).strip()},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    payload = response.json()
    command = payload.get("command")
    if not command:
        print("Invalid API response: missing command.", file=sys.stderr)
        return 1

    print(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
