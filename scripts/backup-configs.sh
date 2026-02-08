#!/bin/bash
# Pirate Orb Config Backup
# Backs up all service configs to a timestamped archive
# Run weekly: 0 3 * * 0 /Users/spencer/projects/pirate-orb/scripts/backup-configs.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_NAME="pirate-orb-configs-$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

echo "📦 Backing up Pirate Orb configs..."

# Create temp directory
TEMP_DIR=$(mktemp -d)
mkdir -p "$TEMP_DIR/$BACKUP_NAME"

# Services to backup
SERVICES=(sabnzbd prowlarr radarr sonarr lidarr jellyseerr whisparr qbittorrent gluetun)

for service in "${SERVICES[@]}"; do
    CONFIG_PATH="$PROJECT_DIR/$service/config"
    if [ -d "$CONFIG_PATH" ]; then
        echo "  → Backing up $service..."
        # Use rsync to exclude cache directories
        rsync -a --exclude='MediaCover' --exclude='logs' --exclude='cache' \
              --exclude='*.db-shm' --exclude='*.db-wal' --exclude='Backups' \
              --exclude='ipc-socket' \
              "$CONFIG_PATH/" "$TEMP_DIR/$BACKUP_NAME/$service-config/"
    fi
done

# Also backup docker-compose and env
cp "$PROJECT_DIR/docker-compose.yml" "$TEMP_DIR/$BACKUP_NAME/"
cp "$PROJECT_DIR/.env" "$TEMP_DIR/$BACKUP_NAME/env.backup"

# Create archive
cd "$TEMP_DIR"
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" "$BACKUP_NAME"

# Cleanup temp
rm -rf "$TEMP_DIR"

# Keep only last 4 backups
cd "$BACKUP_DIR"
ls -t pirate-orb-configs-*.tar.gz | tail -n +5 | xargs -r rm

# Report
SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME.tar.gz" | cut -f1)
echo "✅ Backup complete: $BACKUP_NAME.tar.gz ($SIZE)"
echo "   Location: $BACKUP_DIR"

# List recent backups
echo ""
echo "📁 Recent backups:"
ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -4
