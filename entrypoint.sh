#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}  Grab2RSS v2.6 - Container Init${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"

# Set default PUID/PGID if not provided
PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo -e "${GREEN}✓${NC} User configuration:"
echo -e "  PUID: ${YELLOW}${PUID}${NC}"
echo -e "  PGID: ${YELLOW}${PGID}${NC}"

# Create abc group if it doesn't exist
if ! getent group abc > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Creating group 'abc' with GID ${PGID}"
    groupadd -g "${PGID}" abc
else
    # Modify existing group
    echo -e "${GREEN}✓${NC} Modifying group 'abc' to GID ${PGID}"
    groupmod -o -g "${PGID}" abc
fi

# Create abc user if it doesn't exist
if ! id abc > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Creating user 'abc' with UID ${PUID}"
    useradd -u "${PUID}" -g abc -s /bin/bash -m abc
else
    # Modify existing user
    echo -e "${GREEN}✓${NC} Modifying user 'abc' to UID ${PUID}"
    usermod -o -u "${PUID}" abc
    usermod -g abc abc
fi

# Create necessary directories
echo -e "${GREEN}✓${NC} Creating directories"
mkdir -p /app/data/torrents
mkdir -p /config

# Set ownership and permissions
echo -e "${GREEN}✓${NC} Setting permissions"
chown -R abc:abc /app
chown -R abc:abc /config
chown -R abc:abc /app/data

# Set proper permissions for data directory
chmod -R 755 /app/data
chmod -R 755 /config

echo -e "${GREEN}✓${NC} Permissions configured successfully"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✓${NC} Starting Grab2RSS as user 'abc' (${PUID}:${PGID})"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""

# Drop privileges and execute main application as abc user
exec su-exec abc python /app/main.py
