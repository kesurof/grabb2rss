# Changelog

All notable changes to Grab2RSS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.6.0] - 2026-01-20

### Added
- **LinuxServer.io-style Permission Management**
  - PUID/PGID environment variables for user/group ID mapping
  - Custom entrypoint script for proper permission handling
  - User 'abc' runs the application with host-mapped permissions
  - Ensures files created by container have correct ownership on host

- **Improved Docker Configuration**
  - New `entrypoint.sh` script with colored output
  - TZ (timezone) environment variable support
  - `/config` volume for future configuration persistence
  - Enhanced healthcheck with start period
  - Better organized environment variables in docker-compose.yml

- **Documentation Overhaul**
  - Complete README.md rewrite inspired by LinuxServer.io standards
  - Removed historical correction notes and changelog from README
  - Added CHANGELOG.md (this file) for version history
  - Simplified and modernized documentation structure
  - Added architecture diagrams
  - Enhanced troubleshooting section

### Changed
- **Container runs as non-root user** by default (user 'abc')
- Updated Dockerfile labels with OpenContainer standards
- Reorganized docker-compose.yml with better categorization
- Enhanced .env.example with clear sections and better comments
- Version bump to 2.6.0

### Removed
- Obsolete documentation files:
  - `docs/CHANGEMENTS_v2.5.md` (historical changes)
  - `docs/MIGRATION_v2.5.md` (migration guide)
  - `docs/DOCKER_FIX.md` (fix documentation)
  - `docs/RSS_FIX.md` (fix documentation)
  - `docs/REBUILD_GUIDE.md` (rebuild guide)
- Removed `.env` file mount in docker-compose (use environment variables)

### Security
- Better permission handling following LinuxServer.io best practices
- Container no longer runs as root user
- Proper file ownership management

---

## [2.5.0] - Previous Release

### Added
- Admin interface tab with system statistics
- Radarr/Sonarr integration for intelligent filtering
- Cache management endpoints
- Database VACUUM optimization
- Enhanced logging system

### Fixed
- Torrent file parsing errors (bencode validation)
- HTML file detection (404 errors from trackers)
- Sync status tracking improvements

---

## Version History

For versions prior to 2.5.0, see git commit history.
