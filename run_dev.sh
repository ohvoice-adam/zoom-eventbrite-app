#!/bin/bash
# run_dev.sh - Simple development runner

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Zoom-Eventbrite App in development mode...${NC}"

# Check if .env exists
if [[ ! -f ".env" ]]; then
    echo -e "${YELLOW}No .env file found. Creating from template...${NC}"
    cp .env.example .env
    echo -e "${RED}Please edit .env and add your API credentials!${NC}"
    exit 1
fi

# Check if venv exists
if [[ ! -d "venv" ]]; then
    echo -e "${YELLOW}No virtual environment found. Creating...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Create necessary directories
mkdir -p data logs uploads downloads credentials

# Load environment variables from .env file
if [[ -f ".env" ]]; then
    export $(grep -v '^#' .env | xargs)
    echo -e "${GREEN}.env file loaded${NC}"
fi

# Force development environment (override .env settings)
export FLASK_ENV=development
export FLASK_DEBUG=True
export DATABASE_PATH=./data/app.db
export UPLOAD_FOLDER=./uploads
export DOWNLOAD_FOLDER=./downloads
export CREDENTIALS_FOLDER=./credentials
export LOG_FILE=./logs/app.log

# Set Flask to bind to all interfaces
export FLASK_HOST=0.0.0.0
export FLASK_PORT=5000

# Initialize database if it doesn't exist
if [[ ! -f "./data/app.db" ]]; then
    echo -e "${GREEN}Initializing database...${NC}"
    python scripts/init_db.py
fi

# Check for dummy values in .env
if grep -q "your_.*_here" .env; then
    echo -e "${YELLOW}Warning: Found placeholder values in .env file${NC}"
    echo -e "${YELLOW}The app will start but API functions won't work until you add real credentials${NC}"
    echo ""
fi

# Start the application
echo -e "${GREEN}Starting Flask application...${NC}"
echo -e "${GREEN}Access the app at: http://localhost:5000${NC}"
echo -e "${GREEN}Or remotely at: http://$(hostname -I | awk '{print $1}'):5000${NC}"
echo ""

# Set Flask to bind to all interfaces
export FLASK_HOST=0.0.0.0
export FLASK_PORT=5000

# Force development mode one more time before starting
export FLASK_ENV=development
export FLASK_DEBUG=True

python app_prod.py