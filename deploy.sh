#!/usr/bin/env bash
# Armu production deployment script.
# Supports Ubuntu/Debian (apt) and Arch/CachyOS (pacman).
# Installs nginx, certbot, sets up a systemd service, and configures HTTPS.
set -euo pipefail

G='\033[0;32m'; B='\033[0;34m'; Y='\033[0;33m'; R='\033[0;31m'; W='\033[0m'
BOLD='\033[1m'
hr()  { printf "${B}────────────────────────────────────────────────────────${W}\n"; }
ok()  { printf "  ${G}✓${W} %s\n" "$*"; }
inf() { printf "  ${B}·${W} %s\n" "$*"; }
ask() { printf "  ${Y}?${W} %s " "$*"; }
err() { printf "  ${R}✗${W} %s\n" "$*" >&2; }
die() { err "$*"; exit 1; }

# ── Must run as root ──────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run this script as root: sudo bash deploy.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"
VENV="$SCRIPT_DIR/.venv"
ENV_FILE="$BACKEND/.env"

clear
printf "\n${BOLD}${G}  Armu — Production Deployment${W}\n\n"
hr
printf "  This script will:\n"
printf "    1. Run the app setup (if not done yet)\n"
printf "    2. Install nginx + certbot\n"
printf "    3. Configure nginx with your domain\n"
printf "    4. Get a free SSL certificate (Let's Encrypt)\n"
printf "    5. Create a systemd service for auto-start\n"
hr
printf "\n"

# ── Domain ────────────────────────────────────────────────────────────────────
ask "Your domain name (e.g. armu.myschool.com):"
read -r DOMAIN
[[ -n "$DOMAIN" ]] || die "Domain is required."

ask "Your email (for SSL certificate renewal notices):"
read -r EMAIL
[[ -n "$EMAIL" ]] || die "Email is required."

# Run as which user?
ask "Linux user that will run Armu [default: $SUDO_USER]:"
read -r RUN_USER
RUN_USER="${RUN_USER:-$SUDO_USER}"
[[ -n "$RUN_USER" ]] || die "Could not determine run user. Pass one explicitly."
id "$RUN_USER" &>/dev/null || die "User '$RUN_USER' does not exist."

printf "\n"
hr
printf "  ${BOLD}1. App setup${W}\n"
hr

if [[ ! -f "$ENV_FILE" ]]; then
    inf "Running setup.sh first…"
    sudo -u "$RUN_USER" bash "$SCRIPT_DIR/setup.sh"
else
    ok ".env already exists — skipping setup.sh."
fi

# Ensure DB is up to date
inf "Running database migrations…"
sudo -u "$RUN_USER" bash -c "cd '$BACKEND' && '$VENV/bin/flask' --app app db upgrade 2>&1" | grep -v UserWarning || true
ok "Database ready."

# ── Update CORS_ORIGINS in .env ───────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}2. Environment${W}\n"
hr

ORIGINS="https://${DOMAIN},http://${DOMAIN}"
if grep -q "^CORS_ORIGINS=" "$ENV_FILE"; then
    sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=${ORIGINS}|" "$ENV_FILE"
else
    echo "CORS_ORIGINS=${ORIGINS}" >> "$ENV_FILE"
fi
ok "CORS_ORIGINS set to $ORIGINS"

# ── nginx + certbot ───────────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}3. nginx + certbot${W}\n"
hr

inf "Detecting package manager…"
if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
    inf "Found apt (Debian/Ubuntu)"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    inf "Found pacman (Arch/CachyOS)"
else
    die "No supported package manager found (apt or pacman required)."
fi

inf "Installing nginx and certbot…"
if [[ "$PKG_MANAGER" == "apt" ]]; then
    apt-get update -qq
    apt-get install -y -qq nginx certbot python3-certbot-nginx
else
    pacman -Sy --noconfirm --needed nginx certbot certbot-nginx
fi
ok "nginx and certbot installed."

# Arch uses /etc/nginx/conf.d/ instead of sites-available/sites-enabled
if [[ "$PKG_MANAGER" == "apt" ]]; then
    NGINX_CONF="/etc/nginx/sites-available/armu"
    NGINX_CONF_LINK="/etc/nginx/sites-enabled/armu"
    mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
else
    NGINX_CONF="/etc/nginx/conf.d/armu.conf"
    NGINX_CONF_LINK=""
    mkdir -p /etc/nginx/conf.d
    # Arch nginx.conf doesn't include conf.d by default — add it if missing
    if ! grep -q "conf\.d/\*\.conf" /etc/nginx/nginx.conf; then
        sed -i 's|http {|http {\n    include /etc/nginx/conf.d/*.conf;|' /etc/nginx/nginx.conf
    fi
fi
mkdir -p /var/www/html

cat > "$NGINX_CONF" <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    # For certbot ACME challenge
    location /.well-known/acme-challenge/ { root /var/www/html; }

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
        client_max_body_size 20M;
    }
}
NGINX

if [[ "$PKG_MANAGER" == "apt" ]]; then
    ln -sf "$NGINX_CONF" "$NGINX_CONF_LINK"
    rm -f /etc/nginx/sites-enabled/default
fi

systemctl enable --now nginx
nginx -t && systemctl reload nginx
ok "nginx configured for $DOMAIN (HTTP)."

# ── SSL certificate ───────────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}4. SSL certificate${W}\n"
hr

inf "Requesting Let's Encrypt certificate for $DOMAIN…"
inf "(Make sure your domain's DNS A record points to this server's IP first!)"
printf "\n"
systemctl stop nginx
certbot certonly --standalone -d "$DOMAIN" \
    --non-interactive --agree-tos -m "$EMAIL"
ok "SSL certificate obtained."

# Rewrite nginx config with SSL
cat > "$NGINX_CONF" <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://\$host\$request_uri; }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name ${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
        client_max_body_size 20M;
    }
}
NGINX

nginx -t && systemctl restart nginx
ok "nginx updated for HTTPS."

# ── systemd service ───────────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}5. systemd service${W}\n"
hr

SERVICE_FILE="/etc/systemd/system/armu.service"
cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=Armu School Platform
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${BACKEND}
ExecStart=${VENV}/bin/python app.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable armu
systemctl restart armu
sleep 2
systemctl is-active --quiet armu && ok "armu.service is running." || {
    err "Service failed to start. Check logs: journalctl -u armu -n 50"
    exit 1
}

# ── Done ──────────────────────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}${G}Deployment complete!${W}\n"
hr
printf "\n"
printf "  Armu is live at ${B}https://${DOMAIN}${W}\n\n"
printf "  Useful commands:\n"
printf "    View logs:    ${BOLD}journalctl -u armu -f${W}\n"
printf "    Restart:      ${BOLD}systemctl restart armu${W}\n"
printf "    Stop:         ${BOLD}systemctl stop armu${W}\n"
printf "    Update:       Log in as admin → Settings → Software Update\n\n"
