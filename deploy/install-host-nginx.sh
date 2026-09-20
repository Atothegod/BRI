#!/usr/bin/env sh
set -eu

SITE_NAME="${SITE_NAME:-bri}"
SOURCE_CONF="${SOURCE_CONF:-deploy/host-nginx-bri.conf}"
AVAILABLE_CONF="/etc/nginx/sites-available/${SITE_NAME}"
ENABLED_CONF="/etc/nginx/sites-enabled/${SITE_NAME}"

if [ ! -f "$SOURCE_CONF" ]; then
    echo "Missing $SOURCE_CONF. Run this script from the repository root." >&2
    exit 1
fi

sudo install -m 0644 "$SOURCE_CONF" "$AVAILABLE_CONF"
sudo ln -sf "$AVAILABLE_CONF" "$ENABLED_CONF"
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx

echo "Installed $SOURCE_CONF as $ENABLED_CONF"
