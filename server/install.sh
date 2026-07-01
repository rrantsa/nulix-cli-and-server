#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${NULIX_INSTALL_DIR:-/opt/nulix}"
SERVICE_USER="${NULIX_SERVICE_USER:-nulix}"
ENV_FILE="/etc/nulix-api.env"
MODEL_PROVIDER="${NULIX_MODEL_PROVIDER:-ollama}"
MODEL_NAME="${NULIX_MODEL_NAME:-llama3.2:3b}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root." >&2
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip curl ca-certificates

if [[ "${MODEL_PROVIDER}" == "ollama" ]]; then
  if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
  fi

  systemctl enable ollama
  systemctl restart ollama
  ollama pull "${MODEL_NAME}"
fi

if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --home "${INSTALL_DIR}" --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" "${INSTALL_DIR}"
install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" "${INSTALL_DIR}/server"
install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" "${INSTALL_DIR}/venv"
install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" "${INSTALL_DIR}/scripts"

install -m 0644 "${ROOT_DIR}/server/app.py" "${INSTALL_DIR}/server/app.py"
install -m 0644 "${ROOT_DIR}/server/knowledge.py" "${INSTALL_DIR}/server/knowledge.py"
install -m 0644 "${ROOT_DIR}/server/model_provider.py" "${INSTALL_DIR}/server/model_provider.py"
install -m 0644 "${ROOT_DIR}/server/prompt.py" "${INSTALL_DIR}/server/prompt.py"
install -m 0644 "${ROOT_DIR}/server/validator.py" "${INSTALL_DIR}/server/validator.py"
install -m 0644 "${ROOT_DIR}/server/requirements.txt" "${INSTALL_DIR}/server/requirements.txt"
install -m 0644 "${ROOT_DIR}/scripts/train_kb.py" "${INSTALL_DIR}/scripts/train_kb.py"

python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/server/requirements.txt"

if [[ ! -f "${INSTALL_DIR}/api_keys.txt" ]]; then
  install -m 0640 -o "${SERVICE_USER}" -g "${SERVICE_USER}" \
    "${ROOT_DIR}/server/api_keys.txt.example" \
    "${INSTALL_DIR}/api_keys.txt"
fi

cat > "${ENV_FILE}" <<EOF
NULIX_API_KEYS_FILE=${INSTALL_DIR}/api_keys.txt
NULIX_MODEL_PROVIDER=${MODEL_PROVIDER}
NULIX_MODEL_NAME=${MODEL_NAME}
NULIX_MODEL_TIMEOUT_SECONDS=${NULIX_MODEL_TIMEOUT_SECONDS:-20}
OLLAMA_URL=http://127.0.0.1:11434
NULIX_EXTERNAL_API_BASE_URL=${NULIX_EXTERNAL_API_BASE_URL:-}
NULIX_EXTERNAL_API_KEY=${NULIX_EXTERNAL_API_KEY:-}
NULIX_EXTERNAL_API_PATH=${NULIX_EXTERNAL_API_PATH:-/chat/completions}
NULIX_KB_ENABLED=${NULIX_KB_ENABLED:-true}
NULIX_KB_PATH=${NULIX_KB_PATH:-${INSTALL_DIR}/knowledge.db}
NULIX_SERVER_HOST=127.0.0.1
NULIX_SERVER_PORT=8000
EOF

install -d /etc/systemd/system
install -m 0644 "${ROOT_DIR}/systemd/nulix-api.service" /etc/systemd/system/nulix-api.service

chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"

systemctl daemon-reload
systemctl enable nulix-api
systemctl restart nulix-api

echo "Server files installed in ${INSTALL_DIR}."
echo "Model provider: ${MODEL_PROVIDER}"
