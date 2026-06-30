#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${NULIX_CLIENT_INSTALL_DIR:-/opt/nulix-client}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root." >&2
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv

install -d "${INSTALL_DIR}"
python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install requests==2.32.5

install -m 0644 "${ROOT_DIR}/client/nulix.py" "${INSTALL_DIR}/nulix.py"

cat > /usr/local/bin/nulix <<EOF
#!/usr/bin/env bash
exec "${INSTALL_DIR}/venv/bin/python" "${INSTALL_DIR}/nulix.py" "\$@"
EOF

chmod 0755 /usr/local/bin/nulix

echo "Client installed. Set NULIX_API_URL and NULIX_API_KEY before use."
