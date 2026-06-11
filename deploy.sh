#!/bin/bash
set -e

# ManageWorks Ubuntu Server Deployment Script
# Stack  : Python/Django 6, Vue3/Vite/UnoCSS, PostgreSQL, Nginx
# Services: manageworks (Django backend) + manageworks-bot (Telegram Bot)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "========================================================"
echo "   ManageWorks Deployment Script"
echo "========================================================"
echo ""

# ── Inputs ────────────────────────────────────────────────────────────────────

read -rp "GitHub repo URL (e.g. https://github.com/user/ManageWorks): " REPO_URL
[[ -z "$REPO_URL" ]] && error "Repo URL required."

read -rp "Server IP(s) / domain(s) for Nginx (space-separated, e.g. 192.168.1.10 example.com): " SERVER_NAMES
[[ -z "$SERVER_NAMES" ]] && error "At least one IP or domain required."

read -rp "OS username to run the app (default: $USER): " APP_USER
APP_USER="${APP_USER:-$USER}"

read -rp "Deploy directory (default: /home/$APP_USER/ManageWorks): " DEPLOY_DIR
DEPLOY_DIR="${DEPLOY_DIR:-/home/$APP_USER/ManageWorks}"

echo ""
info "--- Django Admin ---"
read -rp "Admin username: " ADMIN_USER
[[ -z "$ADMIN_USER" ]] && error "Admin username required."
read -rp "Admin email: " ADMIN_EMAIL
[[ -z "$ADMIN_EMAIL" ]] && error "Admin email required."
read -rsp "Admin password: " ADMIN_PASSWORD
echo ""
[[ -z "$ADMIN_PASSWORD" ]] && error "Admin password required."

echo ""
info "--- PostgreSQL ---"
read -rp "DB name (default: manageworks): " DB_NAME
DB_NAME="${DB_NAME:-manageworks}"
read -rp "DB user (default: managework): " DB_USER
DB_USER="${DB_USER:-managework}"
read -rsp "DB password: " DB_PASSWORD
echo ""
[[ -z "$DB_PASSWORD" ]] && error "DB password required."

echo ""
info "--- Telegram Bot (optional) ---"
read -rp "Enable Telegram Bot service? [y/N]: " ENABLE_BOT
ENABLE_BOT="${ENABLE_BOT,,}"   # lowercase

echo ""
info "--- Django Secret Key ---"
SECRET_KEY=$(python3 -c \
  "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits+'!@#\$%^&*(-_=+)') for _ in range(50)))" \
  2>/dev/null || openssl rand -base64 37 | tr -d '\n=+/')
echo "  Generated."

echo ""
echo "========================================================"
echo "  Summary"
echo "========================================================"
echo "  Repo       : $REPO_URL"
echo "  Deploy dir : $DEPLOY_DIR"
echo "  Server     : $SERVER_NAMES"
echo "  App user   : $APP_USER"
echo "  DB         : $DB_NAME @ localhost (user: $DB_USER)"
echo "  Telegram   : $([ "$ENABLE_BOT" = "y" ] && echo "enabled" || echo "skipped")"
echo "========================================================"
read -rp "Proceed? [y/N]: " CONFIRM
[[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]] && { echo "Aborted."; exit 0; }

# ── Derived paths ─────────────────────────────────────────────────────────────

BACKEND_DIR="$DEPLOY_DIR/backend"
FRONTEND_DIR="$DEPLOY_DIR/frontend"
VENV_DIR="$BACKEND_DIR/venv"
ENV_FILE="$BACKEND_DIR/.env"
DJANGO="DJANGO_SETTINGS_MODULE=config.settings.prod $VENV_DIR/bin/python manage.py"

# ── System packages ───────────────────────────────────────────────────────────

info "Updating apt and installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    git curl wget build-essential \
    python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib libpq-dev \
    nginx \
    ca-certificates gnupg lsb-release \
    > /dev/null
success "System packages installed."

# ── Node.js 20 LTS ────────────────────────────────────────────────────────────

if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d 'v') -lt 20 ]]; then
    info "Installing Node.js 20 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - > /dev/null 2>&1
    sudo apt-get install -y nodejs > /dev/null
    success "Node.js $(node -v) installed."
else
    success "Node.js $(node -v) already present."
fi

# ── Clone or update repo ──────────────────────────────────────────────────────

if [[ -d "$DEPLOY_DIR/.git" ]]; then
    warn "Repo already exists at $DEPLOY_DIR — pulling latest..."
    git -C "$DEPLOY_DIR" pull
else
    info "Cloning repo to $DEPLOY_DIR..."
    git clone "$REPO_URL" "$DEPLOY_DIR"
    success "Repo cloned."
fi

# ── PostgreSQL ────────────────────────────────────────────────────────────────

info "Setting up PostgreSQL..."
sudo systemctl enable postgresql --now > /dev/null 2>&1

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" > /dev/null
success "PostgreSQL ready: $DB_NAME / $DB_USER"

# ── Python venv + packages ────────────────────────────────────────────────────

info "Creating Python virtualenv..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
success "Venv ready."

info "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -r "$BACKEND_DIR/requirements.txt" -q
success "Python packages installed."

# ── .env file (read by systemd EnvironmentFile, not by Python directly) ───────

info "Writing $ENV_FILE ..."
cat > "$ENV_FILE" <<EOF
SECRET_KEY=$SECRET_KEY
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=localhost
DB_PORT=5432
EOF
chmod 600 "$ENV_FILE"
success ".env written."

# ── Patch prod.py: read SECRET_KEY from env (one-time, idempotent) ─────────────

PROD_PY="$BACKEND_DIR/config/settings/prod.py"
if ! grep -q "SECRET_KEY.*os.environ" "$PROD_PY"; then
    info "Patching prod.py to override SECRET_KEY from environment..."
    # Append after the 'import os' and 'from .base import *' block
    printf "\nSECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)\n" >> "$PROD_PY"
    success "prod.py patched."
else
    success "prod.py already reads SECRET_KEY from env."
fi

# ── Django: migrate, collectstatic, superuser ─────────────────────────────────

info "Running migrations..."
cd "$BACKEND_DIR"
DB_PASSWORD="$DB_PASSWORD" $DJANGO migrate --noinput

info "Collecting static files..."
DB_PASSWORD="$DB_PASSWORD" $DJANGO collectstatic --noinput -v 0

info "Creating superuser (if not exists)..."
DB_PASSWORD="$DB_PASSWORD" $DJANGO shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$ADMIN_USER').exists():
    User.objects.create_superuser('$ADMIN_USER', '$ADMIN_EMAIL', '$ADMIN_PASSWORD')
    print('Superuser created.')
else:
    print('Superuser already exists.')
"
success "Django setup done."

# ── Frontend build ────────────────────────────────────────────────────────────

info "Installing Node packages..."
cd "$FRONTEND_DIR"
# Use npm ci if lockfile present (faster, exact), otherwise npm install
if [[ -f "package-lock.json" ]]; then
    npm ci --silent
else
    npm install --silent
fi
success "Node packages installed."

info "Building frontend..."
npm run build
success "Frontend built → $FRONTEND_DIR/dist"

# ── Systemd: manageworks (Django backend) ────────────────────────────────────

info "Writing manageworks.service..."
sudo tee /etc/systemd/system/manageworks.service > /dev/null <<EOF
[Unit]
Description=ManageWorks Django Backend
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=$ENV_FILE
Environment=DJANGO_SETTINGS_MODULE=config.settings.prod
ExecStart=$VENV_DIR/bin/python manage.py runserver 127.0.0.1:8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable manageworks
sudo systemctl restart manageworks
success "manageworks service started."

# ── Systemd: manageworks-bot (Telegram Bot) ───────────────────────────────────

if [[ "$ENABLE_BOT" == "y" ]]; then
    info "Writing manageworks-bot.service..."
    sudo tee /etc/systemd/system/manageworks-bot.service > /dev/null <<EOF
[Unit]
Description=ManageWorks Telegram Bot
After=network.target postgresql.service manageworks.service
Requires=postgresql.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=$ENV_FILE
Environment=DJANGO_SETTINGS_MODULE=config.settings.prod
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV_DIR/bin/python -u manage.py run_telegram_bot
Restart=always
RestartSec=10
StandardOutput=append:$BACKEND_DIR/telegram_bot.out
StandardError=append:$BACKEND_DIR/telegram_bot.out

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable manageworks-bot
    sudo systemctl restart manageworks-bot
    success "manageworks-bot service started."
    warn "Configure the Telegram bot token via Django Admin → Telegram Settings after deployment."
else
    info "Telegram bot service skipped. Enable later with:"
    info "  sudo systemctl enable --now manageworks-bot"
fi

# ── Nginx ─────────────────────────────────────────────────────────────────────

NGINX_CONF="/etc/nginx/sites-available/manageworks"
info "Writing Nginx config..."
sudo tee "$NGINX_CONF" > /dev/null <<EOF
server {
    listen 80;
    server_name $SERVER_NAMES;

    client_max_body_size 50m;

    # Frontend (Vue SPA)
    location / {
        root $FRONTEND_DIR/dist;
        try_files \$uri \$uri/ /index.html;
        expires 1h;
        add_header Cache-Control "public";
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    # Django Admin
    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Django collected static files
    location /static/ {
        alias $BACKEND_DIR/staticfiles/;
        expires 7d;
        add_header Cache-Control "public";
    }
}
EOF

sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/manageworks
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
success "Nginx configured and restarted."

# ── Firewall ──────────────────────────────────────────────────────────────────

if command -v ufw &>/dev/null; then
    info "Opening firewall ports 22 (SSH) and 80 (HTTP)..."
    sudo ufw allow 22/tcp  > /dev/null
    sudo ufw allow 80/tcp  > /dev/null
    sudo ufw --force enable > /dev/null
    success "ufw rules applied."
fi

# ── Verify services ───────────────────────────────────────────────────────────

echo ""
info "Verifying services..."
sleep 3

VERIFY_OK=true

if systemctl is-active --quiet manageworks; then
    success "manageworks      — running"
else
    warn "manageworks      — NOT running  (check: sudo journalctl -u manageworks -n 50)"
    VERIFY_OK=false
fi

if systemctl is-active --quiet nginx; then
    success "nginx            — running"
else
    warn "nginx            — NOT running  (check: sudo journalctl -u nginx -n 20)"
    VERIFY_OK=false
fi

if [[ "$ENABLE_BOT" == "y" ]]; then
    if systemctl is-active --quiet manageworks-bot; then
        success "manageworks-bot  — running"
    else
        warn "manageworks-bot  — NOT running  (check: sudo journalctl -u manageworks-bot -n 50)"
        VERIFY_OK=false
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "========================================================"
if [[ "$VERIFY_OK" == "true" ]]; then
    echo -e "  ${GREEN}Deployment complete — all services running!${NC}"
else
    echo -e "  ${YELLOW}Deployment done — some services need attention (see warnings above).${NC}"
fi
echo "========================================================"
echo "  App URL   :  http://$(echo $SERVER_NAMES | awk '{print $1}')"
echo "  Admin     :  http://$(echo $SERVER_NAMES | awk '{print $1}')/admin"
echo "  Admin user:  $ADMIN_USER"
echo ""
echo "  Post-deployment steps:"
echo "    1. Log into Django Admin and configure:"
echo "       - SMTP Settings  (Admin → Smtp settings)"
if [[ "$ENABLE_BOT" == "y" ]]; then
echo "       - Telegram Token (Admin → Telegram settings)"
fi
echo "    2. Create user accounts and assign roles (Admin → Users)"
echo ""
echo "  Service commands:"
echo "    sudo systemctl status manageworks"
echo "    sudo systemctl status nginx"
if [[ "$ENABLE_BOT" == "y" ]]; then
echo "    sudo systemctl status manageworks-bot"
echo "    tail -f $BACKEND_DIR/telegram_bot.out"
fi
echo ""
echo "  Logs:"
echo "    sudo journalctl -u manageworks -f"
echo "    sudo journalctl -u nginx -f"
echo ""
echo "  Re-deploy after code update:"
echo "    git -C $DEPLOY_DIR pull"
echo "    cd $FRONTEND_DIR && npm install && npm run build"
echo "    sudo systemctl restart manageworks"
if [[ "$ENABLE_BOT" == "y" ]]; then
echo "    sudo systemctl restart manageworks-bot"
fi
echo "========================================================"
