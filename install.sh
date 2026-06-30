#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root." >&2
  exit 1
fi

if [[ -z "${NULIX_DOMAIN:-}" ]]; then
  echo "NULIX_DOMAIN is required." >&2
  exit 1
fi

if [[ -z "${NULIX_EMAIL:-}" ]]; then
  echo "NULIX_EMAIL is required." >&2
  exit 1
fi

export NULIX_DOMAIN
export NULIX_EMAIL
export NULIX_INSTALL_DIR="${NULIX_INSTALL_DIR:-/opt/nulix}"

bash "${ROOT_DIR}/server/install.sh"

apt-get update
apt-get install -y nginx certbot python3-certbot-nginx

install -d /etc/nginx/sites-available /etc/nginx/sites-enabled
sed "s/__SERVER_NAME__/${NULIX_DOMAIN}/g" \
  "${ROOT_DIR}/nginx/nulix.conf" \
  > /etc/nginx/sites-available/nulix.conf

ln -sfn /etc/nginx/sites-available/nulix.conf /etc/nginx/sites-enabled/nulix.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable nginx
systemctl restart nginx

certbot --nginx --non-interactive --agree-tos -m "${NULIX_EMAIL}" -d "${NULIX_DOMAIN}" --redirect

systemctl restart nginx
systemctl restart nulix-api

echo "Nulix server installed successfully."
echo "Add API keys to ${NULIX_INSTALL_DIR}/api_keys.txt before using the service."
