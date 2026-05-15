#!/bin/bash
set -e

# ManageWorks Ubuntu Server Deployment Script
# Installs: Python/Django backend, Vue3/Vite/UnoCSS frontend, PostgreSQL, Nginx
# Repo: https://github.com/krishangopalsharma-tech/ManageWorks (update if different)

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
echo "================================================"
echo "   ManageWorks Deployment Script"
echo "================================================"
echo ""

# ── Collect inputs ────────────────────────────────────────────────────────────

read -rp "GitHub repo URL (e.g. https://github.com/user/ManageWorks): " REPO_URL
[[ -z "$REPO_URL" ]] && error "Repo URL required."

read -rp "Server IP / domain (used for Nginx server_name, e.g. 192.168.1.10): " SERVER_IP
[[ -z "$SERVER_IP" ]] && error "Server IP required."

read -rp "OS username to run the app (default: $USER): " APP_USER
APP_USER="${APP_USER:-$USER}"

read -rp "Deploy directory (default: /home/$APP_USER/ManageWorks): " DEPLOY_DIR
DEPLOY_DIR="${DEPLOY_DIR:-/home/$APP_USER/ManageWorks}"

echo ""
info "--- Django Admin Credentials ---"
read -rp "Admin username: " ADMIN_USER
[[ -z "$ADMIN_USER" ]] && error "Admin username required."

read -rp "Admin email: " ADMIN_EMAIL
[[ -z "$ADMIN_EMAIL" ]] && error "Admin email required."

read -rsp "Admin password: " ADMIN_PASSWORD
echo ""
[[ -z "$ADMIN_PASSWORD" ]] && error "Admin password required."

echo ""
info "--- PostgreSQL Database ---"
read -rp "DB name (default: manageworks): " DB_NAME
DB_NAME="${DB_NAME:-manageworks}"

read -rp "DB user (default: managework): " DB_USER
DB_USER="${DB_USER:-managework}"

read -rsp "DB password: " DB_PASSWORD
echo ""
[[ -z "$DB_PASSWORD" ]] && error "DB password required."

echo ""
info "--- SMTP Email Settings ---"
read -rp "SMTP host (e.g. smtp.gmail.com): " SMTP_HOST
read -rp "SMTP port (default: 587): " SMTP_PORT
SMTP_PORT="${SMTP_PORT:-587}"
read -rp "SMTP username (email address): " SMTP_USER
read -rsp "SMTP password / app password: " SMTP_PASSWORD
echo ""
read -rp "Default from-email (default: $SMTP_USER): " FROM_EMAIL
FROM_EMAIL="${FROM_EMAIL:-$SMTP_USER}"

echo ""
info "--- Django Secret Key ---"
SECRET_KEY=$(python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%^&*(-_=+)') for _ in range(50)))" 2>/dev/null || \
             openssl rand -base64 37 | tr -d '\n=+/')
echo "  Generated secret key."

echo ""
echo "================================================"
echo "  Summary"
echo "================================================"
echo "  Repo:       $REPO_URL"
echo "  Deploy to:  $DEPLOY_DIR"
echo "  Server IP:  $SERVER_IP"
echo "  App user:   $APP_USER"
echo "  DB:         $DB_NAME @ localhost (user: $DB_USER)"
echo "  SMTP:       $SMTP_HOST:$SMTP_PORT as $SMTP_USER"
echo "================================================"
read -rp "Proceed? [y/N]: " CONFIRM
[[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]] && { echo "Aborted."; exit 0; }

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

# ── Node.js (LTS via NodeSource) ──────────────────────────────────────────────

if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d 'v') -lt 20 ]]; then
    info "Installing Node.js 20 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - > /dev/null 2>&1
    sudo apt-get install -y nodejs > /dev/null
    success "Node.js $(node -v) installed."
else
    success "Node.js $(node -v) already present."
fi

# ── Clone repo ────────────────────────────────────────────────────────────────

if [[ -d "$DEPLOY_DIR/.git" ]]; then
    warn "Repo already exists at $DEPLOY_DIR — pulling latest..."
    git -C "$DEPLOY_DIR" pull
else
    info "Cloning repo to $DEPLOY_DIR..."
    git clone "$REPO_URL" "$DEPLOY_DIR"
    success "Repo cloned."
fi

# ── PostgreSQL setup ──────────────────────────────────────────────────────────

info "Setting up PostgreSQL database..."
sudo systemctl enable postgresql --now > /dev/null 2>&1

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" > /dev/null
success "PostgreSQL ready: $DB_NAME / $DB_USER"

# ── Python venv + pip install ─────────────────────────────────────────────────

BACKEND_DIR="$DEPLOY_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"

info "Creating Python virtualenv..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
success "Venv created."

info "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -r "$BACKEND_DIR/requirements.txt" -q
success "Python packages installed."

# ── Django env file ───────────────────────────────────────────────────────────

ENV_FILE="$BACKEND_DIR/.env"
info "Writing $ENV_FILE ..."
cat > "$ENV_FILE" <<EOF
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=$SERVER_IP,localhost,127.0.0.1

DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=localhost
DB_PORT=5432

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=$SMTP_HOST
EMAIL_PORT=$SMTP_PORT
EMAIL_USE_TLS=True
EMAIL_HOST_USER=$SMTP_USER
EMAIL_HOST_PASSWORD=$SMTP_PASSWORD
DEFAULT_FROM_EMAIL=$FROM_EMAIL
EOF
chmod 600 "$ENV_FILE"
success ".env written."

# ── Update prod settings to read .env (if not already) ───────────────────────
# Inject python-dotenv loading at top of prod.py if missing
if ! grep -q "dotenv" "$BACKEND_DIR/config/settings/prod.py"; then
    info "Installing python-dotenv and patching prod.py..."
    "$VENV_DIR/bin/pip" install python-dotenv -q
    PROD_PY="$BACKEND_DIR/config/settings/prod.py"
    TMPFILE=$(mktemp)
    cat > "$TMPFILE" <<'PYEOF'
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')
PYEOF
    cat "$PROD_PY" >> "$TMPFILE"
    mv "$TMPFILE" "$PROD_PY"
    success "prod.py patched to load .env"
fi

# ── Django migrate + static + superuser ──────────────────────────────────────

info "Running Django migrations..."
cd "$BACKEND_DIR"
DJANGO_SETTINGS_MODULE=config.settings.prod "$VENV_DIR/bin/python" manage.py migrate --noinput

info "Collecting static files..."
DJANGO_SETTINGS_MODULE=config.settings.prod "$VENV_DIR/bin/python" manage.py collectstatic --noinput -v 0

info "Creating Django superuser..."
DJANGO_SETTINGS_MODULE=config.settings.prod "$VENV_DIR/bin/python" manage.py shell -c "
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

FRONTEND_DIR="$DEPLOY_DIR/frontend"
info "Installing Node packages (npm ci)..."
cd "$FRONTEND_DIR"
npm ci --silent
success "Node packages installed."

info "Building frontend (vite build)..."
npm run build
success "Frontend built → $FRONTEND_DIR/dist"

# ── Systemd service ───────────────────────────────────────────────────────────

SERVICE_FILE="/etc/systemd/system/manageworks.service"
info "Writing systemd service to $SERVICE_FILE ..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
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

# ── Nginx config ──────────────────────────────────────────────────────────────

NGINX_CONF="/etc/nginx/sites-available/manageworks"
info "Writing Nginx config..."
sudo tee "$NGINX_CONF" > /dev/null <<EOF
server {
    listen 80;
    server_name $SERVER_IP;

    client_max_body_size 50m;

    location / {
        root $FRONTEND_DIR/dist;
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias $BACKEND_DIR/staticfiles/;
    }
}
EOF

sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/manageworks
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
success "Nginx configured and restarted."

# ── Firewall (ufw) ────────────────────────────────────────────────────────────

if command -v ufw &>/dev/null; then
    info "Opening ports 22, 80 in ufw..."
    sudo ufw allow 22/tcp   > /dev/null
    sudo ufw allow 80/tcp   > /dev/null
    sudo ufw --force enable > /dev/null
    success "ufw rules applied."
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "================================================"
echo -e "  ${GREEN}Deployment complete!${NC}"
echo "================================================"
echo "  App:    http://$SERVER_IP"
echo "  Admin:  http://$SERVER_IP/admin"
echo "  User:   $ADMIN_USER"
echo ""
echo "  Check backend:  sudo systemctl status manageworks"
echo "  Check nginx:    sudo systemctl status nginx"
echo "  Backend logs:   sudo journalctl -u manageworks -f"
echo "================================================"
