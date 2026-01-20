# 📡 Grab2RSS

[![Version](https://img.shields.io/badge/version-2.6.0-blue)](https://github.com/kesurof/grabb2rss)
[![Python](https://img.shields.io/badge/python-3.11+-green)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-supported-blue)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

**Prowlarr to RSS Converter** with multi-tracker support, intelligent filtering, and modern web interface.

Transform your Prowlarr grabs into RSS feeds for automatic seeding with your favorite torrent clients.

---

## ✨ Features

- 🔄 **Automatic Synchronization** - Fetch torrents from Prowlarr on a schedule
- 📡 **RSS Feeds** - Generate RSS/JSON feeds compatible with ruTorrent, qBittorrent, Transmission
- 🎯 **Smart Filtering** - Optional Radarr/Sonarr integration to show only grabbed torrents
- 🏷️ **Multi-Tracker Support** - Filter feeds by tracker
- 🔍 **Deduplication** - Intelligent duplicate detection
- 🗑️ **Auto-Purge** - Automatic cleanup of old torrents
- 💻 **Modern Web UI** - Dashboard with statistics, logs, and configuration
- 🐳 **Docker Ready** - LinuxServer.io-inspired permission management (PUID/PGID)

---

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Running Prowlarr instance
- (Optional) Radarr and/or Sonarr for filtering

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/kesurof/grabb2rss.git
cd grabb2rss
```

2. **Configure environment**

```bash
cp .env.example .env
nano .env
```

**Minimal configuration:**
```env
# User/Group IDs (run `id` on your host)
PUID=1000
PGID=1000

# Prowlarr (Required)
PROWLARR_URL=http://prowlarr:9696
PROWLARR_API_KEY=your_api_key_here

# Optional: Radarr/Sonarr filtering
RADARR_URL=http://radarr:7878
RADARR_API_KEY=your_api_key_here
```

3. **Start the container**

```bash
docker-compose up -d
```

4. **Access the interface**

Open http://localhost:8000 in your browser.

---

## 📖 Usage

### RSS Feeds

**Global feed (all trackers):**
```
http://localhost:8000/rss
```

**Filtered by tracker:**
```
http://localhost:8000/rss/tracker/YourTrackerName
```

**JSON format:**
```
http://localhost:8000/rss.json
```

### Configuration

All settings can be configured via:
- Environment variables in `.env`
- Web interface at http://localhost:8000 (Configuration tab)

### API Endpoints

- `GET /api/stats` - Statistics
- `GET /api/grabs` - List all grabs
- `GET /api/trackers` - Available trackers
- `POST /api/sync/trigger` - Manual sync
- `GET /health` - Health check

Full API documentation available in the web interface.

---

## ⚙️ Configuration

### User/Group IDs (PUID/PGID)

Following LinuxServer.io standards, you can set PUID and PGID to match your host user:

```bash
id $user
# uid=1000(user) gid=1000(user) groups=1000(user)
```

Then in `.env`:
```env
PUID=1000
PGID=1000
```

This ensures files created by the container have correct permissions on your host.

### Key Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | 1000 | User ID for file permissions |
| `PGID` | 1000 | Group ID for file permissions |
| `SYNC_INTERVAL` | 3600 | Sync interval in seconds (1 hour) |
| `RETENTION_HOURS` | 168 | Keep torrents for N hours (7 days) |
| `AUTO_PURGE` | true | Automatically remove old torrents |
| `DEDUP_HOURS` | 168 | Deduplication window |

See `.env.example` for full configuration options.

---

## 🐳 Docker Compose

### Standalone

```yaml
version: "3.8"

services:
  grab2rss:
    image: grab2rss:latest
    container_name: grab2rss
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Paris
      - PROWLARR_URL=http://prowlarr:9696
      - PROWLARR_API_KEY=your_key
    volumes:
      - ./config:/config
      - ./data:/app/data
    ports:
      - "8000:8000"
    restart: unless-stopped
```

### With Traefik

```yaml
version: "3.8"

services:
  grab2rss:
    image: grab2rss:latest
    container_name: grab2rss
    environment:
      - PUID=1000
      - PGID=1000
      - PROWLARR_URL=http://prowlarr:9696
      - PROWLARR_API_KEY=your_key
    volumes:
      - ./config:/config
      - ./data:/app/data
    networks:
      - traefik_proxy
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.grab2rss.rule=Host(`rss.example.com`)"
      - "traefik.http.routers.grab2rss.entrypoints=https"
      - "traefik.http.routers.grab2rss.tls.certresolver=letsencrypt"

networks:
  traefik_proxy:
    external: true
```

---

## 🔧 Building from Source

```bash
git clone https://github.com/kesurof/grabb2rss.git
cd grabb2rss
docker build -t grab2rss:latest .
```

---

## 📊 Architecture

```
┌─────────────┐
│  Prowlarr   │ ← Grabs torrents from indexers
└──────┬──────┘
       │ API
       ▼
┌─────────────┐
│  Grab2RSS   │ ← Fetches grabs, generates RSS
└──────┬──────┘
       │ RSS Feed
       ▼
┌─────────────┐
│   Torrent   │ ← Auto-downloads from RSS
│   Client    │   (ruTorrent, qBittorrent, etc.)
└─────────────┘
```

### Optional Filtering

```
┌──────────┐  ┌──────────┐
│  Radarr  │  │  Sonarr  │ ← Download clients
└────┬─────┘  └────┬─────┘
     │             │
     └─────┬───────┘
           │ API (filter grabbed torrents)
           ▼
     ┌─────────────┐
     │  Grab2RSS   │ ← Only shows grabbed torrents
     └─────────────┘
```

---

## 🛠️ Troubleshooting

### Container won't start

Check logs:
```bash
docker logs grab2rss
```

### Permission issues

Verify PUID/PGID match your user:
```bash
id $user
```

Update `.env` with correct values and recreate container:
```bash
docker-compose down
docker-compose up -d
```

### No torrents appearing

1. Verify Prowlarr API key is correct
2. Check Prowlarr has recent grabs (History page)
3. Trigger manual sync in web interface
4. Check logs in Admin tab

---

## 📚 Documentation

- [Installation Guide](docs/INSTALLATION.md) - Detailed installation instructions
- [Quick Start Guide](docs/QUICKSTART.md) - Get started in 5 minutes
- [qBittorrent Setup](docs/QBITTORRENT_SETUP.md) - Configure qBittorrent RSS
- [Network Setup](docs/NETWORK_SETUP.md) - Docker networking guide

---

## 🔐 Security

**⚠️ Important:** Never commit your `.env` file or API keys to version control.

If you accidentally expose API keys:
1. Regenerate all API keys in Prowlarr/Radarr/Sonarr
2. Update your `.env` file
3. Restart the container

See [SECURITY_INCIDENT.md](SECURITY_INCIDENT.md) for security incident history.

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📝 License

MIT License - See [LICENSE](LICENSE) file for details

---

## 🙏 Acknowledgments

- Inspired by [LinuxServer.io](https://www.linuxserver.io/) permission management standards
- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Uses [APScheduler](https://apscheduler.readthedocs.io/) for task scheduling

---

## 📞 Support

- 🐛 [Report Issues](https://github.com/kesurof/grabb2rss/issues)
- 💬 [Discussions](https://github.com/kesurof/grabb2rss/discussions)

---

**Made with ❤️ for the selfhosting community**
