#!/bin/bash
# Pirate Orb Health Monitor
# Run via cron: */15 * * * * /Users/spencer/projects/pirate-orb/scripts/health-monitor.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/health.log"
ALERT_FILE="$PROJECT_DIR/logs/alerts.json"

mkdir -p "$PROJECT_DIR/logs"

# Timestamp
TS=$(date '+%Y-%m-%d %H:%M:%S')

# Check functions
check_container() {
    local name=$1
    docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null
}

check_vpn() {
    docker exec qbittorrent curl -s --max-time 10 ifconfig.me 2>/dev/null
}

check_disk() {
    local mount=$1
    local threshold=$2
    local usage=$(df "$mount" 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ -n "$usage" ] && [ "$usage" -gt "$threshold" ]; then
        echo "$usage"
    fi
}

check_lidarr_api() {
    curl -s --max-time 15 "https://api.lidarr.audio/api/v0.4/search?type=all&query=test" | grep -q "artist" && echo "ok" || echo "fail"
}

# Initialize status
STATUS="ok"
ALERTS=()

echo "[$TS] Health check starting..." >> "$LOG_FILE"

# Check all containers
CONTAINERS=(sabnzbd prowlarr radarr sonarr lidarr jellyseerr whisparr gluetun qbittorrent ngrok)
for container in "${CONTAINERS[@]}"; do
    running=$(check_container "$container")
    if [ "$running" != "true" ]; then
        ALERTS+=("{\"type\":\"container_down\",\"service\":\"$container\",\"ts\":\"$TS\"}")
        STATUS="critical"
        echo "[$TS] ALERT: $container is DOWN" >> "$LOG_FILE"
    fi
done

# Check VPN
VPN_IP=$(check_vpn)
if [ -z "$VPN_IP" ]; then
    ALERTS+=("{\"type\":\"vpn_down\",\"ts\":\"$TS\"}")
    STATUS="critical"
    echo "[$TS] ALERT: VPN is DOWN or unreachable" >> "$LOG_FILE"
else
    echo "[$TS] VPN IP: $VPN_IP" >> "$LOG_FILE"
fi

# Check disk usage (alert at 85%)
HAL_USAGE=$(check_disk "/Volumes/hal9000" 85)
if [ -n "$HAL_USAGE" ]; then
    ALERTS+=("{\"type\":\"disk_warning\",\"mount\":\"hal9000\",\"usage\":$HAL_USAGE,\"ts\":\"$TS\"}")
    STATUS="warning"
    echo "[$TS] WARNING: hal9000 at ${HAL_USAGE}% usage" >> "$LOG_FILE"
fi

LEV_USAGE=$(check_disk "/Volumes/Leviathan" 90)
if [ -n "$LEV_USAGE" ]; then
    ALERTS+=("{\"type\":\"disk_warning\",\"mount\":\"Leviathan\",\"usage\":$LEV_USAGE,\"ts\":\"$TS\"}")
    STATUS="warning"
    echo "[$TS] WARNING: Leviathan at ${LEV_USAGE}% usage" >> "$LOG_FILE"
fi

# Check Lidarr API (the problematic one)
LIDARR_API=$(check_lidarr_api)
if [ "$LIDARR_API" != "ok" ]; then
    ALERTS+=("{\"type\":\"lidarr_api_issue\",\"ts\":\"$TS\"}")
    echo "[$TS] WARNING: Lidarr metadata API may be having issues" >> "$LOG_FILE"
fi

# Write alerts if any
if [ ${#ALERTS[@]} -gt 0 ]; then
    echo "[$(IFS=,; echo "${ALERTS[*]}")]" > "$ALERT_FILE"
    echo "[$TS] Status: $STATUS - ${#ALERTS[@]} alert(s)" >> "$LOG_FILE"
else
    echo "[]" > "$ALERT_FILE"
    echo "[$TS] Status: OK - All systems healthy" >> "$LOG_FILE"
fi

# Output for cron/notification systems
if [ "$STATUS" = "critical" ]; then
    echo "🚨 PIRATE ORB CRITICAL: ${#ALERTS[@]} issues detected"
    exit 1
elif [ "$STATUS" = "warning" ]; then
    echo "⚠️ PIRATE ORB WARNING: ${#ALERTS[@]} issues detected"
    exit 0
fi

echo "✅ Pirate Orb healthy"
exit 0
