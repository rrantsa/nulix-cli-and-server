# Nulix

Nulix is a focused natural-language-to-Bash translator.

It accepts a short Linux intent, sends it to a self-hosted API backed by Ollama, and returns exactly one shell command. The CLI never executes the command automatically, so the user stays in control.

```bash
nulix "create a folder named photos"
mkdir photos

nulix "create a folder named photos" | bash
```

## Features

- FastAPI server protected by `X-API-Key`
- Ollama integration using `qwen3:0.6b` by default
- Second-pass validation for obviously dangerous commands
- CLI client that prints only the returned command
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
- `OLLAMA_URL`
- `OLLAMA_MODEL`
- `OLLAMA_TIMEOUT_SECONDS`
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

This script:

- installs Ollama and the `qwen3:0.6b` model
- creates `/opt/nulix`
- installs Python dependencies
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

- The model is instructed to output one Linux command and nothing else.
- The API performs a second validation pass before replying.
- Dangerous outputs are converted to a harmless echo command such as:

```bash
echo '#DANGEROUS rm -rf /'
```

- Unknown or unusable outputs become:

```bash
echo '#UNKNOWN'
```

This keeps `nulix "..." | bash` from executing blocked commands directly.

## License

This repository currently ships with an `UNLICENSED` placeholder in [LICENSE](LICENSE). Replace it with your preferred license before distribution.
