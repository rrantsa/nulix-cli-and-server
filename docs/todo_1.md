> Todo 1 covers the admin-backed `nulix memorize` flow, role separation through API keys, and alias-based retrieval for user-added rules.

## Phase 1 - Admin Auth And API Contract
- [x] Add `NULIX_ADMIN_API_KEYS_FILE` with default path `/opt/nulix/admin_api_keys.txt`.
- [x] Keep using the existing `X-API-Key` header for both normal and admin requests.
- [x] Implement role rules so normal keys can call normal endpoints only, while admin keys can call both normal and admin endpoints.
- [x] Add an admin-only endpoint `POST /rules` to append user-added rules into the KB.
- [x] Define the admin request body for `intent`, `command`, optional `aliases`, and server-side default category `user-added`.
- [x] Document the detailed proposal in [[nulix-memorize-admin-design]].

## Phase 2 - Safe KB Writes
- [x] Validate memorized commands before insert using the existing command validator.
- [x] Insert only into `rules`, never directly into `rules_fts`, so SQLite triggers keep search indexes in sync.
- [x] Make insertion idempotent on `(intent, command)` so repeated memorization remains safe.
- [x] Decide the server response contract for created, duplicate, and validation-rejected rules.
- [x] Add clear failure responses for missing admin key, invalid admin key, and malformed payloads.

## Phase 3 - CLI Memorize UX
- [x] Add a CLI command `nulix memorize "intent" "command"` that calls the admin endpoint.
- [x] Add optional alias support for v1 through repeated flags or a compact input shape, while keeping the main command simple.
- [x] Reuse the same API base URL as the current CLI flow.
- [x] Use a dedicated admin key on the client side for memorize operations.
- [x] Keep the standard generation flow unchanged for non-admin users.

## Phase 4 - Retrieval Quality For User-Added Rules
- [x] Support multiple intent aliases for the same command so one memorized command can be found through several phrasings.
- [x] Store each alias as its own `(intent, command, category)` rule entry to work with the current lexical SQLite search design.
- [x] Ensure new and updated rules remain searchable immediately through existing SQLite FTS triggers.
- [x] Keep v1 retrieval lexical and explicit, without claiming semantic understanding across unrelated phrasings.
- [x] Add examples showing when multiple aliases should be memorized for the same command.

## Phase 5 - Verification
- [x] Add tests covering admin key authorization and admin-implies-user behavior.
- [x] Add tests covering successful rule creation, duplicate rule submission, and validation rejection.
- [x] Add tests covering direct intent match and alternate alias phrasing match.
- [x] Add tests confirming new rows are searchable immediately after insertion.
- [x] Run local client tests and Python syntax checks; full server endpoint execution remains blocked in this workspace until `fastapi` is installed locally.

## Ending Todo 1 - Update PRD, README and User Guide

- [x] Update the PRD to reflect todo 1 changes
- [x] Update the README to reflect todo 1 changes
- [x] Update the User Guide to reflect todo 1 changes
