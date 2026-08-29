#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root on the production host." >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_config="$script_dir/nginx.backoffice.lecrownproperties.com.conf"
site_name="backoffice.lecrownproperties.com.conf"
available_path="/etc/nginx/sites-available/$site_name"
enabled_path="/etc/nginx/sites-enabled/$site_name"

test -f "$source_config"
install -d /etc/nginx/sites-available /etc/nginx/sites-enabled /var/www/letsencrypt
install -m 0644 "$source_config" "$available_path"
ln -sfn "$available_path" "$enabled_path"
nginx -t
systemctl reload nginx

echo "Installed and reloaded nginx for backoffice.lecrownproperties.com."
echo "After DNS resolves, issue TLS with:"
echo "  certbot --nginx -d backoffice.lecrownproperties.com"
