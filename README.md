# Nulix

Nulix is a focused natural-language-to-Bash translator.

It accepts a short Linux intent, sends it to a self-hosted API, and returns exactly one Bash shell line. The CLI never executes the result automatically, so the user stays in control.

```bash
nulix "create a folder named photos"
mkdir photos

nulix "create a folder named photos" | bash
```

## Features

- FastAPI server protected by `X-API-Key`
- KB-first command generation with SQLite FTS intent search and template adaptation
- Configurable server-side model providers: local Ollama or external OpenAI-compatible APIs
- Second-pass validation for obviously dangerous commands
- CLI client that prints only the returned shell line
- Ubuntu-oriented install scripts for the server and the client
- Nginx reverse proxy and `systemd` service templates

## Repository layout

```text
server/
client/
systemd/
nginx/
memory/
scripts/
install.sh
```

## API

### `POST /generate`

Headers:

```text
X-API-Key: your-api-key
```

Body:

```json
{
  "text": "create a folder named photos"
}
```

Response:

```json
{
  "command": "mkdir photos",
  "dangerous": false
}
```

### `GET /health`

Response:

```json
{
  "status": "ok"
}
```

## Local development

### Server

The server can run in two modes:

- KB-first mode: search the local knowledge base, pick a command template, then adapt placeholders through the configured model provider
- Direct generation fallback: when KB is disabled or no rule matches, ask the configured model provider for one shell line directly

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r server/requirements.txt
cp server/api_keys.txt.example server/api_keys.txt
export NULIX_API_KEYS_FILE="$PWD/server/api_keys.txt"
uvicorn app:app --app-dir server --reload
```

### Client

```bash
export NULIX_API_URL="http://127.0.0.1:8000"
export NULIX_API_KEY="client-local-dev"
python3 client/nulix.py "list files sorted by size"
```

## Environment

### Server

- `NULIX_API_KEYS_FILE`
- `NULIX_MODEL_PROVIDER`
- `NULIX_MODEL_NAME`
- `NULIX_MODEL_TIMEOUT_SECONDS`
- `NULIX_KB_ENABLED`
- `NULIX_KB_PATH`
- `OLLAMA_URL`
- `NULIX_EXTERNAL_API_BASE_URL`
- `NULIX_EXTERNAL_API_KEY`
- `NULIX_EXTERNAL_API_PATH`
- `NULIX_SERVER_HOST`
- `NULIX_SERVER_PORT`

### Client

- `NULIX_API_URL`
- `NULIX_API_KEY`
- `NULIX_CLIENT_TIMEOUT_SECONDS`

## Installation

### Server

Run the root installer on Ubuntu with a public domain already pointing to the server:

```bash
sudo NULIX_DOMAIN=nulix.example.com NULIX_EMAIL=ops@example.com ./install.sh
```

That installs the KB-first server with local Ollama by default. You can also target an external OpenAI-compatible API:

```bash
sudo \
  NULIX_DOMAIN=nulix.example.com \
  NULIX_EMAIL=ops@example.com \
  NULIX_MODEL_PROVIDER=openai_compatible \
  NULIX_MODEL_NAME=gpt-4.1-mini \
  NULIX_EXTERNAL_API_BASE_URL=https://api.openai.com/v1 \
  NULIX_EXTERNAL_API_KEY=your-secret-key \
  ./install.sh
```

The installer:

- installs Ollama and pulls the configured local model when `NULIX_MODEL_PROVIDER=ollama`
- creates `/opt/nulix`
- installs Python dependencies
- installs the KB-first server modules and training script
- installs the API `systemd` service
- configures Nginx
- requests a Let's Encrypt certificate

### Client

```bash
sudo ./client/install.sh
```

Then configure:

```bash
export NULIX_API_URL="https://nulix.example.com"
export NULIX_API_KEY="client-raspberry-123"
```

## Security model

- The model is instructed to output one Linux shell line and nothing else.
- The server prefers the local KB first, then falls back to direct model generation when needed.
- The API performs a second validation pass before replying.
- Single-line pipelines or chaining are allowed when they are useful and not blocked by safety validation.
- The server can use either a local Ollama model or an external OpenAI-compatible API, depending on deployment configuration.
- Dangerous outputs are converted to a harmless echo command such as:

```bash
echo '#DANGEROUS rm -rf /'
```

- Unknown or unusable outputs become:

```bash
echo '#UNKNOWN'
```

This keeps `nulix "..." | bash` from executing blocked commands directly.

## Knowledge Base

- The local KB lives in SQLite and is accessed through [server/knowledge.py](server/knowledge.py).
- The server seeds default rules automatically when the KB is empty.
- [scripts/train_kb.py](scripts/train_kb.py) can be used to enrich the KB with additional curated intents.

## License

This repository currently ships with an `UNLICENSED` placeholder in [LICENSE](LICENSE). Replace it with your preferred license before distribution.
