# Nulix User Guide

## Overview

Nulix turns a natural-language Linux intent into exactly one shell line.

Normal usage:

```bash
nulix "list files sorted by size"
```

Admin usage can also memorize new KB rules:

```bash
nulix memorize "restart nginx" "systemctl restart nginx" --alias "nginx restart"
```

## Environment

### Normal usage

```bash
export NULIX_API_URL="https://nulix.example.com"
export NULIX_API_KEY="client-device-key"
```

### Memorize usage

```bash
export NULIX_ADMIN_API_KEY="admin-console-key"
```

`memorize` uses the same `NULIX_API_URL` and the same `X-API-Key` header on the wire, but it requires an admin key on the client side.

## Generate Commands

```bash
nulix "show disk usage of current directory"
```

Output example:

```bash
du -sh .
```

## Memorize Commands

### Basic rule

```bash
nulix memorize "restart nginx" "systemctl restart nginx"
```

### Rule with aliases

```bash
nulix memorize "restart nginx" "systemctl restart nginx" \
  --alias "restart nginx service" \
  --alias "nginx restart"
```

This stores multiple intent phrasings for the same command so the current lexical SQLite search can find the command through more than one wording.

## Notes

- Memorized commands are stored in the SQLite `rules` table with category `user-added`.
- The server never writes directly to `rules_fts`; SQLite triggers keep the search index updated automatically.
- Dangerous or invalid commands are rejected instead of being memorized.
