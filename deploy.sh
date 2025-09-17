#!/bin/bash
# deploy.sh - Simplified deployment script for SQLite-based app

set -e

echo "🚀 Starting Zoom-Eventbrite App Deployment..."

# Configuration from environment or defaults
APP_NAME="${APP_NAME:-zoom-eventbrite-app}"
APP_DIR="${APP_DIR:-/opt/$APP_NAME}"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups}"
USER="${USER:-appuser}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
    exit 1
}

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy the Zoom-Eventbrite app with SQLite backend.

OPTIONS:
    --docker          Use Docker deployment (default)
    --traditional     Use traditional systemd deployment
    --dev             Development deployment (local directories)
    --domain DOMAIN   Set the domain name for SSL
    --no-ssl          Skip SSL certificate setup
    --help            Show this help message

ENVIRONMENT VARIABLES:
    All configuration is read from .env file. See .env.example for template.

EXAMPLES:
    $0                                    # Docker deployment with current .env
    $0 --traditional --domain mysite.com # Traditional deployment with SSL
    $0 --dev                             # Development setup
    
EOF
}

# Parse command line arguments
DEPLOYMENT_TYPE="docker"
SETUP_SSL="true"
DOMAIN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)
            DEPLOYMENT_TYPE="docker"
            shift
            ;;
        --traditional)
            DEPLOYMENT_TYPE="traditional"
            shift
            ;;
        --dev)
            DEPLOYMENT_TYPE="development"
            shift
            ;;
        --domain)
            DOMAIN_OVERRIDE="$2"
            shift 2
            ;;
        --no-ssl)
            SETUP_SSL="false"
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            error "Unknown option: $1. Use --help for usage information."
            ;;
    esac
done

# Check if running as root for system deployments
if [[ "$DEPLOYMENT_TYPE" != "development" ]] && [[ $EUID -ne 0 ]]; then
   error "System deployment must be run as root (use sudo)"
fi

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    error "Environment file .env not found. Copy .env.example and fill in your values."
fi

# Source environment variables
set -a
source .env
set +a

# Override domain if provided
if [[ -n "$DOMAIN_OVERRIDE" ]]; then
    export DOMAIN="$DOMAIN_OVERRIDE"
fi

log "✅ Environment variables loaded from .env"

# Validate required environment variables
required_vars=(
    "ZOOM_API_KEY"
    "ZOOM_API_SECRET" 
    "ZOOM_ACCOUNT_ID"
    "EVENTBRITE_PRIVATE_TOKEN"
    "GOOGLE_SSO_CLIENT_ID"
    "GOOGLE_SSO_CLIENT_SECRET"
    "FLASK_SECRET_KEY"
)

for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        error "Required environment variable $var is not set in .env file"
    fi
done

log "✅ Required environment variables validated"

# =============================================================================
# FUNCTION DEFINITIONS - Define all functions before using them
# =============================================================================

setup_ssl_certificate() {
    log "🔒 Setting up SSL certificate for $DOMAIN..."
    
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        # For Docker, we need to configure external nginx or use a reverse proxy
        warn "SSL setup for Docker requires external reverse proxy configuration"
        warn "Consider using Traefik, nginx-proxy, or configure nginx manually"
        warn "Current setup provides HTTP only on port 80"
    else
        # Traditional deployment with certbot
        if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN"; then
            log "✅ SSL certificate configured successfully"
        else
            warn "SSL certificate setup failed - continuing without HTTPS"
        fi
    fi
}

create_systemd_service() {
    cat > /etc/systemd/system/"$APP_NAME".service << EOF
[Unit]
Description=Zoom-Eventbrite App
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/gunicorn --bind ${FLASK_HOST:-127.0.0.1}:${FLASK_PORT:-5000} --workers ${GUNICORN_WORKERS:-4} --timeout ${GUNICORN_TIMEOUT:-300} app_prod:app
Restart=always
RestartSec=10
EnvironmentFile=$APP_DIR/.env

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
}

setup_nginx_config() {
    log "🌐 Configuring Nginx..."
    
    FLASK_PORT="${FLASK_PORT:-5000}"
    FLASK_HOST="${FLASK_HOST:-127.0.0.1}"
    
    cat > /etc/nginx/sites-available/"$APP_NAME" << EOF
upstream ${APP_NAME}_app {
    server ${FLASK_HOST}:${FLASK_PORT};
}

server {
    listen 80;
    server_name ${DOMAIN:-_};
    
    client_max_body_size ${MAX_CONTENT_LENGTH:-100M};
    client_body_timeout 300s;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml+rss text/javascript;

    # Rate limiting for API endpoints
    limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/m;
    limit_req_zone \$binary_remote_addr zone=general:10m rate=100r/m;

    location /api/ {
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://${APP_NAME}_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        proxy_buffering off;
    }

    location / {
        limit_req zone=general burst=50 nodelay;
        
        proxy_pass http://${APP_NAME}_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        proxy_buffering off;
    }

    location /health {
        access_log off;
        return 200 "healthy\\n";
        add_header Content-Type text/plain;
    }

    location /static/ {
        alias $APP_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Block common attack patterns
    location ~ /\\.(ht|git|env) {
        deny all;
        access_log off;
        log_not_found off;
        return 404;
    }

    location ~ ~\$ {
        deny all;
        access_log off;
        log_not_found off;
        return 404;
    }
}
EOF

    # Enable site
    ln -sf /etc/nginx/sites-available/"$APP_NAME" /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test nginx config
    nginx -t || error "Nginx configuration test failed"
}

setup_maintenance_tasks() {
    log "⏰ Setting up maintenance tasks..."
    
    # Create cleanup script
    mkdir -p "$APP_DIR/scripts"
    cat > "$APP_DIR/scripts/cleanup.sh" << 'EOF'
#!/bin/bash
# Cleanup old files and optimize database

APP_DIR="/opt/zoom-eventbrite-app"
DAYS_TO_KEEP_DOWNLOADS=7
DAYS_TO_KEEP_LOGS=30

# Clean old downloads
find "$APP_DIR/downloads" -name "*.mp4" -mtime +$DAYS_TO_KEEP_DOWNLOADS -delete 2>/dev/null || true

# Clean old logs  
find "$APP_DIR/logs" -name "*.log" -mtime +$DAYS_TO_KEEP_LOGS -delete 2>/dev/null || true

# Vacuum SQLite database to reclaim space
sqlite3 "$APP_DIR/data/app.db" "VACUUM;" 2>/dev/null || true

# Clean expired processing jobs (older than 7 days)
sqlite3 "$APP_DIR/data/app.db" "DELETE FROM processing_jobs WHERE created_at < datetime('now', '-7 days');" 2>/dev/null || true

echo "$(date): Cleanup completed"
EOF
    
    chmod +x "$APP_DIR/scripts/cleanup.sh"
    chown -R "$USER:$USER" "$APP_DIR/scripts" 2>/dev/null || true
    
    # Setup cron job
    cat > /etc/cron.d/"$APP_NAME" << EOF
# Daily cleanup at 2 AM
0 2 * * * $USER $APP_DIR/scripts/cleanup.sh >> $APP_DIR/logs/cleanup.log 2>&1
EOF

    log "✅ Maintenance tasks configured"
}

check_existing_nginx() {
    log "🔍 Checking existing nginx configuration..."
    
    # Check if nginx is running and has existing configurations
    if systemctl is-active --quiet nginx 2>/dev/null; then
        log "✅ Nginx is already running"
        
        # Count existing site configurations
        EXISTING_SITES=$(find /etc/nginx/sites-enabled -name "*.conf" -o -name "*" ! -name "default" | wc -l)
        
        if [[ $EXISTING_SITES -gt 0 ]]; then
            log "📋 Found $EXISTING_SITES existing nginx site(s)"
            log "   The deploy script will create a separate config for this app"
        fi
        
        # Check if a domain was specified
        if [[ -z "$DOMAIN" ]] || [[ "$DOMAIN" == "localhost" ]]; then
            warn "⚠️  No domain specified! This could conflict with existing sites."
            warn "   Recommendation: Use --domain subdomain.yourdomain.com"
            echo
            echo "   Do you want to continue anyway? This will create a catch-all server block."
            echo "   Your existing sites should still work, but this is not recommended."
            echo
            read -p "   Continue? (y/N): " -r
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log "Deployment cancelled. Please specify a domain with --domain"
                exit 0
            fi
        else
            log "✅ Domain specified: $DOMAIN (this will not conflict with other sites)"
        fi
    else
        log "📦 Nginx not currently running - will set up fresh configuration"
    fi
}

# Development deployment
if [[ "$DEPLOYMENT_TYPE" == "development" ]]; then
    log "🛠️  Setting up development environment..."
    
    # Create local directories
    mkdir -p data logs uploads downloads credentials
    
    # Install Python requirements
    if [[ ! -d "venv" ]]; then
        log "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Initialize database
    log "Initializing SQLite database..."
    python -c "from app_prod import app; from models import init_db; app.app_context().push(); init_db()"
    
    log "🎉 Development setup complete!"
    echo
    echo "To start the development server:"
    echo "  source venv/bin/activate"
    echo "  export FLASK_ENV=development"
    echo "  python app_prod.py"
    echo
    exit 0
fi

# Create backup if app already exists
if [[ -d "$APP_DIR" ]]; then
    log "📦 Creating backup of existing installation..."
    mkdir -p "$BACKUP_DIR"
    tar -czf "$BACKUP_DIR/$APP_NAME-backup-$(date +%Y%m%d-%H%M%S).tar.gz" -C "$APP_DIR" . 2>/dev/null || true
    log "✅ Backup created in $BACKUP_DIR"
fi

# Docker deployment
if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
    log "🐳 Setting up Docker deployment..."
    
    # Install Docker if not present
    if ! command -v docker &> /dev/null; then
        log "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        systemctl enable docker
        systemctl start docker
    fi
    
    # Install Docker Compose if not present
    if ! command -v docker-compose &> /dev/null; then
        log "Installing Docker Compose..."
        curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    
    # Create application directory
    mkdir -p "$APP_DIR"
    
    # Copy application files
    log "📋 Copying application files..."
    cp -r . "$APP_DIR/"
    cd "$APP_DIR"
    
    # Remove existing Dockerfile to ensure we use the updated version
    if [[ -f "Dockerfile" ]]; then
        log "Removing existing Dockerfile to create updated version..."
        rm -f Dockerfile
    fi
    
    # Create updated Dockerfile
    log "Creating updated Dockerfile..."
    cat > Dockerfile << 'EOF'
FROM python:3.11-slim

# Set environment variables (only non-sensitive paths)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    nginx \
    supervisor \
    sqlite3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/logs /app/uploads /app/downloads /app/credentials \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app

# Copy configuration files (create them if they don't exist)
RUN if [ -f docker/nginx.conf ]; then cp docker/nginx.conf /etc/nginx/sites-available/default; else \
    echo 'upstream app { server 127.0.0.1:5000; } server { listen 80; location / { proxy_pass http://app; proxy_set_header Host $host; } location /health { return 200 "healthy\n"; add_header Content-Type text/plain; } }' > /etc/nginx/sites-available/default; fi

RUN if [ -f docker/supervisord.conf ]; then cp docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf; else \
    echo '[supervisord]\nnodaemon=true\n[program:nginx]\ncommand=/usr/sbin/nginx -g "daemon off;"\nautostart=true\nautorestart=true\n[program:flask-app]\ncommand=gunicorn --bind 127.0.0.1:5000 --workers 4 --timeout 300 app_prod:app\ndirectory=/app\nuser=appuser\nautostart=true\nautorestart=true' > /etc/supervisor/conf.d/supervisord.conf; fi

# Create startup script that initializes database at runtime
RUN cat > /app/startup.sh << 'STARTUP_EOF'
#!/bin/bash
set -e

echo "Starting Zoom-Eventbrite App..."

# Set default paths if not provided via environment
export DATABASE_PATH=${DATABASE_PATH:-/app/data/app.db}
export UPLOAD_FOLDER=${UPLOAD_FOLDER:-/app/uploads}
export DOWNLOAD_FOLDER=${DOWNLOAD_FOLDER:-/app/downloads}
export CREDENTIALS_FOLDER=${CREDENTIALS_FOLDER:-/app/credentials}
export LOG_FILE=${LOG_FILE:-/app/logs/app.log}

echo "Using DATABASE_PATH: $DATABASE_PATH"

# Ensure directories exist and have proper permissions
mkdir -p /app/data /app/logs /app/uploads /app/downloads /app/credentials
chown -R appuser:appuser /app/data /app/logs /app/uploads /app/downloads /app/credentials

# Initialize database if it doesn't exist
if [ ! -f "$DATABASE_PATH" ]; then
    echo "Initializing database at $DATABASE_PATH..."
    su appuser -c "cd /app && python scripts/init_db.py"
    echo "Database initialized successfully"
else
    echo "Database already exists at $DATABASE_PATH"
fi

echo "Starting services..."
# Start supervisord
exec /usr/bin/supervisord -n
STARTUP_EOF

RUN chmod +x /app/startup.sh

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Use startup script instead of direct supervisord
CMD ["/app/startup.sh"]
EOF
    
    # Create docker configuration directory and files if they don't exist
    if [[ ! -d "docker" ]]; then
        log "Creating docker configuration directory..."
        mkdir -p docker
    fi
    
    if [[ ! -f "docker/nginx.conf" ]]; then
        log "Creating docker/nginx.conf..."
        cat > docker/nginx.conf << 'EOF'
upstream app {
    server 127.0.0.1:5000;
}

server {
    listen 80 default_server;
    server_name _;

    client_max_body_size 100M;
    client_body_timeout 300s;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml+rss text/javascript;

    location / {
        proxy_pass http://app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        proxy_buffering off;
    }

    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    location /static/ {
        alias /app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
    fi
    
    if [[ ! -f "docker/supervisord.conf" ]]; then
        log "Creating docker/supervisord.conf..."
        cat > docker/supervisord.conf << 'EOF'
[supervisord]
nodaemon=true
user=root

[program:nginx]
command=/usr/sbin/nginx -g "daemon off;"
autostart=true
autorestart=true
stderr_logfile=/app/logs/nginx.error.log
stdout_logfile=/app/logs/nginx.access.log
redirect_stderr=true

[program:flask-app]
command=gunicorn --bind 127.0.0.1:5000 --workers %(ENV_GUNICORN_WORKERS)s --timeout %(ENV_GUNICORN_TIMEOUT)s --access-logfile /app/logs/gunicorn.access.log --error-logfile /app/logs/gunicorn.error.log app_prod:app
directory=/app
user=appuser
autostart=true
autorestart=true
environment=PATH="/usr/local/bin:/usr/bin:/bin"
redirect_stderr=true
stderr_logfile=/app/logs/flask-app.error.log
stdout_logfile=/app/logs/flask-app.log
EOF
    fi

    # Update docker-compose.yml if needed for Docker paths
    if [[ ! -f "docker-compose.yml" ]] || ! grep -q "DATABASE_PATH=/app/data/app.db" docker-compose.yml; then
        log "Creating/updating docker-compose.yml..."
        cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  web:
    build: .
    ports:
      - "${HOST_PORT:-80}:80"
      - "${HOST_SSL_PORT:-443}:443"
    environment:
      # Flask Configuration
      - FLASK_ENV=${FLASK_ENV:-production}
      - FLASK_DEBUG=${FLASK_DEBUG:-False}
      - FLASK_HOST=${FLASK_HOST:-0.0.0.0}
      - FLASK_PORT=${FLASK_PORT:-5000}
      - FLASK_SECRET_KEY=${FLASK_SECRET_KEY}
      
      # Database (SQLite - Docker paths)
      - DATABASE_PATH=/app/data/app.db
      
      # API Credentials
      - ZOOM_API_KEY=${ZOOM_API_KEY}
      - ZOOM_API_SECRET=${ZOOM_API_SECRET}
      - ZOOM_ACCOUNT_ID=${ZOOM_ACCOUNT_ID}
      - EVENTBRITE_PRIVATE_TOKEN=${EVENTBRITE_PRIVATE_TOKEN}
      
      # Google OAuth
      - GOOGLE_SSO_CLIENT_ID=${GOOGLE_SSO_CLIENT_ID}
      - GOOGLE_SSO_CLIENT_SECRET=${GOOGLE_SSO_CLIENT_SECRET}
      - ALLOWED_DOMAIN=${ALLOWED_DOMAIN:-ohvoice.org}
      
      # File Storage (Docker paths)
      - UPLOAD_FOLDER=/app/uploads
      - DOWNLOAD_FOLDER=/app/downloads
      - CREDENTIALS_FOLDER=/app/credentials
      - MAX_CONTENT_LENGTH=${MAX_CONTENT_LENGTH:-104857600}
      
      # YouTube
      - YOUTUBE_CHANNEL_ID=${YOUTUBE_CHANNEL_ID}
      - CHECK_EXISTING_VIDEOS=${CHECK_EXISTING_VIDEOS:-True}
      
      # Server Settings
      - GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}
      - GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-300}
      
      # Domain and SSL
      - DOMAIN=${DOMAIN:-localhost}
      - USE_SSL=${USE_SSL:-False}
      
      # Logging (Docker paths)
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - LOG_FILE=/app/logs/app.log
      
    volumes:
      - app_data:/app/data
      - app_uploads:/app/uploads
      - app_downloads:/app/downloads
      - app_credentials:/app/credentials
      - app_logs:/app/logs
      - ssl_certs:/etc/ssl/certs/custom
      
    restart: unless-stopped
    networks:
      - app-network

volumes:
  app_data:      # SQLite database and other data
  app_uploads:   # File uploads
  app_downloads: # Downloaded videos
  app_credentials: # API credentials and tokens
  app_logs:      # Application logs
  ssl_certs:     # SSL certificates

networks:
  app-network:
    driver: bridge
EOF
    fi
    
    log "🏗️  Building and starting Docker containers..."
    docker-compose down --remove-orphans 2>/dev/null || true
    docker-compose build --no-cache
    docker-compose up -d
    
    # Wait for application to be ready
    log "⏳ Waiting for application to start..."
    sleep 10
    
    # Test health endpoint
    for i in {1..30}; do
        if curl -f http://localhost/health >/dev/null 2>&1; then
            break
        fi
        if [[ $i -eq 30 ]]; then
            error "Application health check failed after 30 attempts"
        fi
        sleep 2
    done
    
    log "✅ Docker deployment completed"

# Traditional deployment  
else
    log "🔧 Setting up traditional deployment..."
    
    # Install system dependencies
    log "📥 Installing system dependencies..."
    apt-get update
    apt-get install -y \
        python3-pip \
        python3-venv \
        python3-dev \
        nginx \
        supervisor \
        sqlite3 \
        curl \
        certbot \
        python3-certbot-nginx \
        build-essential
    
    # Create application user if it doesn't exist
    if ! id "$USER" &>/dev/null; then
        log "👤 Creating application user: $USER"
        useradd -r -m -s /bin/bash "$USER"
        usermod -aG www-data "$USER"
    fi
    
    # Create application directory
    log "📁 Setting up application directory..."
    mkdir -p "$APP_DIR"
    mkdir -p "$APP_DIR"/{data,logs,uploads,downloads,credentials}
    
    # Copy application files
    log "📋 Copying application files..."
    cp -r . "$APP_DIR/"
    chown -R "$USER:$USER" "$APP_DIR"
    
    # Setup Python virtual environment
    log "🐍 Setting up Python virtual environment..."
    cd "$APP_DIR"
    sudo -u "$USER" python3 -m venv venv
    sudo -u "$USER" venv/bin/pip install --upgrade pip
    sudo -u "$USER" venv/bin/pip install -r requirements.txt
    
    # Initialize database
    log "🗃️ Initializing SQLite database..."
    sudo -u "$USER" bash -c "cd $APP_DIR && source venv/bin/activate && python -c 'from app_prod import app; from models import init_db; app.app_context().push(); init_db()'"
    
    # Setup systemd service
    log "⚙️ Setting up systemd service..."
    create_systemd_service
    
    # Setup nginx
    check_existing_nginx
    setup_nginx_config
    
    # Enable and start services
    systemctl daemon-reload
    systemctl enable "$APP_NAME"
    systemctl start "$APP_NAME"
    systemctl enable nginx
    systemctl restart nginx
    
    log "✅ Traditional deployment completed"
fi

# Setup SSL if requested
if [[ "$SETUP_SSL" == "true" ]] && [[ -n "$DOMAIN" ]] && [[ "$DOMAIN" != "localhost" ]]; then
    setup_ssl_certificate
fi

# Setup maintenance tasks
setup_maintenance_tasks

# Final status check
log "🔍 Checking deployment status..."
sleep 5

if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
    if docker-compose ps | grep -q "Up"; then
        log "✅ Docker services are running"
    else
        error "Docker services failed to start"
    fi
elif systemctl is-active --quiet "$APP_NAME"; then
    log "✅ Application service is running"
else
    error "Application service failed to start"
fi

# Display completion message
log "🎉 Deployment completed successfully!"
echo
echo "📋 Next Steps:"
if [[ -n "$DOMAIN" ]] && [[ "$DOMAIN" != "localhost" ]]; then
    echo "1. Update DNS to point $DOMAIN to this server"
    echo "2. Access the application at https://$DOMAIN"
else
    echo "1. Access the application at http://$(curl -s ifconfig.me)"
    echo "2. Set up a domain name and SSL certificate for production use"
fi
echo "3. Configure YouTube OAuth credentials in credentials/"
echo "4. Test Zoom and Eventbrite API connections"
echo
echo "📁 Application Directory: $APP_DIR"
echo "📊 Logs: $APP_DIR/logs/ (or docker-compose logs)"
echo "🔧 Config: $APP_DIR/.env"
echo "🗄️ Database: $APP_DIR/data/app.db"
echo