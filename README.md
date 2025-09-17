# Zoom-Eventbrite Integration App

A web application that matches Zoom recordings with Eventbrite events and can upload them to YouTube, with intelligent duplicate detection.

## Features

- 🔐 **Google SSO Authentication** - Secure login with domain restrictions
- 📹 **Zoom Integration** - Fetch recordings from Zoom API
- 🎫 **Eventbrite Integration** - Match events with recordings by date
- 🔍 **YouTube Duplicate Detection** - Check for existing videos before upload
- ⬆️ **Automated Uploads** - Bulk process and upload to YouTube
- 📊 **Progress Tracking** - Real-time status updates
- 🗄️ **SQLite Database** - Simple, embedded database
- 🐳 **Docker Support** - Easy deployment with Docker
- 🔒 **Production Ready** - SSL, logging, monitoring included

## Quick Start

1. **Clone and Setup**:
   ```bash
   git clone <your-repo-url>
   cd zoom-eventbrite-app
   cp .env.example .env
   # Edit .env with your API credentials
   ```

2. **Deploy**:
   ```bash
   # Docker deployment (recommended)
   sudo ./deploy.sh --docker --domain your-domain.com
   
   # Traditional deployment
   sudo ./deploy.sh --traditional --domain your-domain.com
   
   # Development setup
   ./deploy.sh --dev
   ```

3. **Configure APIs**:
   - Set up Zoom Server-to-Server OAuth app
   - Get Eventbrite Private Token
   - Configure Google OAuth for SSO
   - (Optional) Set up YouTube Data API

## Usage

1. Sign in with your Google account
2. Select date range for Zoom recordings
3. Find matching Eventbrite events
4. Review YouTube duplicate warnings
5. Confirm matches and start processing

## Requirements

- Python 3.11+
- Google account with allowed domain
- API credentials for Zoom, Eventbrite, Google OAuth
- (Optional) YouTube Data API for video uploads

## Documentation

See the deployment script and configuration files for detailed setup instructions.

## License

[Your License Here]
