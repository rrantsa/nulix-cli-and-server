# nulix-memorize-admin-design

## Summary

This note captures the technical proposal for an admin-backed `nulix memorize` feature that safely appends user-added rules into the SQLite knowledge base and makes them searchable immediately through the existing FTS-triggered indexing flow.

## Goals

- Add a simple admin UX: `nulix memorize "intent" "command"`.
- Keep non-admin generation behavior unchanged.
- Separate admin and non-admin access without inventing a heavy auth system.
- Reuse the current KB architecture instead of bypassing it.
- Improve retrieval quality for user-added commands by supporting explicit alias intents.

## Auth Design

### Key files

- Normal keys remain in `NULIX_API_KEYS_FILE`.
- Add a new environment variable `NULIX_ADMIN_API_KEYS_FILE`.
- Default admin file path: `/opt/nulix/admin_api_keys.txt`.

### Header

- Keep using the same header: `X-API-Key`.
- No second header is required for v1.

### Role rules

- A normal key can call normal endpoints only.
- An admin key can call both normal and admin endpoints.
- Admin therefore implies user access.

### Endpoint access

- `POST /generate`
  - Accept keys found in `NULIX_API_KEYS_FILE`
  - Accept keys found in `NULIX_ADMIN_API_KEYS_FILE`
- `POST /rules`
  - Accept keys found in `NULIX_ADMIN_API_KEYS_FILE` only

### Operational recommendation

- Use dedicated admin keys rather than reusing ordinary client keys.
- Keep admin keys off untrusted client devices.
- Restrict the admin key file with tight filesystem permissions on the server.

## API Proposal

### Route

- `POST /rules`

### Purpose

- Append one user-added command rule and optional alias intents into the KB.

### Request shape

```json
{
  "intent": "restart nginx",
  "command": "systemctl restart nginx",
  "aliases": [
    "restart nginx service",
    "nginx restart"
  ]
}
```

### Server-side rules

- `intent` is required.
- `command` is required.
- `aliases` is optional.
- `category` is not client-controlled in v1.
- The server sets `category` to `user-added`.

### Response ideas

```json
{
  "created": 3,
  "duplicates": 0,
  "category": "user-added"
}
```

Possible behaviors:

- New rule or alias inserted: success
- Duplicate `(intent, command)`: success with duplicate count instead of error
- Validation failure: reject with a clear client error

## Database Write Rules

- Write only to the `rules` table.
- Never write directly to `rules_fts`.
- Rely on existing SQLite triggers to mirror inserts, updates, and deletes into FTS.
- Keep insertion idempotent on `(intent, command)`.

This matches the current implementation model and avoids index drift.

## Searchability Strategy

### What is guaranteed

- A new row becomes searchable immediately after insertion because `rules_fts` is kept in sync through triggers.
- Queries that share meaningful words or prefixes with the stored intent are likely to match well.

### What is not guaranteed

- The current search is lexical, not semantic.
- One stored intent does not guarantee discovery through unrelated wording.

Example:

- Stored intent: `restart nginx`
- Likely matches:
  - `restart nginx`
  - `restart nginx service`
  - `nginx restart`
- Not reliably guaranteed:
  - `bounce web server`
  - `fix the reverse proxy daemon`

### Proposed v1 retrieval approach

- Support multiple explicit alias intents for the same command.
- Store each alias as its own `(intent, command, category)` row.
- Keep the command identical across aliases.

This works well with the current `tokenise + FTS prefix + LIKE fallback` search design and avoids pretending the KB has semantic retrieval when it does not.

## CLI Proposal

### Main command

```bash
nulix memorize "restart nginx" "systemctl restart nginx"
```

### Alias-capable variant

One possible v1 extension:

```bash
nulix memorize "restart nginx" "systemctl restart nginx" --alias "restart nginx service" --alias "nginx restart"
```

### Client behavior

- Send the request to the server admin endpoint.
- Reuse `NULIX_API_URL` for the base URL.
- Use a dedicated admin key for memorize operations.

One clean option:

- `NULIX_API_KEY` for normal generation
- `NULIX_ADMIN_API_KEY` for memorize operations

If `NULIX_ADMIN_API_KEY` is absent, the CLI should fail clearly for `memorize` rather than silently falling back to the normal key.

## Validation Proposal

- Reuse the current command validator before saving rules.
- Reject obviously dangerous or unusable commands from being memorized.
- Return a clear message explaining whether the command was rejected as dangerous or invalid.

This protects the KB from becoming a permanent store for bad rules.

## Error Handling

- Missing admin key: `403`
- Invalid admin key: `403`
- Missing required payload fields: `400`
- Validation-rejected command: `400`
- Unexpected storage failure: `500`

Duplicates should not be treated as failures if the exact `(intent, command)` already exists.

## Test Plan

- Admin key can call `/generate`
- Normal key cannot call `/rules`
- Admin key can call `/rules`
- Valid rule is inserted into `rules`
- Duplicate insert does not create duplicate rows
- Alias rows are inserted and searchable
- New rows are searchable immediately after insertion
- Validation-rejected command is not inserted

## References

- `server/app.py`
- `server/knowledge.py`
- `server/validator.py`
- `client/nulix.py`
