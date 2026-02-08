#!/bin/bash
# Lidarr Diagnostics & Metadata Refresh
# Helps diagnose and work around MusicBrainz metadata issues

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Get Lidarr API key
LIDARR_KEY=$(grep -o '<ApiKey>[^<]*' "$PROJECT_DIR/lidarr/config/config.xml" | sed 's/<ApiKey>//')
LIDARR_URL="http://localhost:8686"

echo "🎵 Lidarr Diagnostics"
echo "===================="
echo ""

# Test local Lidarr
echo "1. Local Lidarr Status:"
HEALTH=$(curl -s "$LIDARR_URL/api/v1/health?apikey=$LIDARR_KEY")
if echo "$HEALTH" | grep -q '\[\]'; then
    echo "   ✅ No health warnings"
else
    echo "   ⚠️  Health issues:"
    echo "$HEALTH" | jq -r '.[] | "   - \(.type): \(.message)"' 2>/dev/null
fi
echo ""

# Test Lidarr metadata API
echo "2. Lidarr Metadata API (api.lidarr.audio):"
API_TEST=$(curl -s --max-time 15 "https://api.lidarr.audio/api/v0.4/search?type=all&query=radiohead" 2>/dev/null)
if echo "$API_TEST" | grep -q "artistname"; then
    echo "   ✅ API responding normally"
else
    echo "   ❌ API may be having issues"
    echo "   Response: $(echo "$API_TEST" | head -c 200)"
fi
echo ""

# Library stats
echo "3. Library Statistics:"
ARTISTS=$(curl -s "$LIDARR_URL/api/v1/artist?apikey=$LIDARR_KEY" | jq 'length')
MISSING=$(curl -s "$LIDARR_URL/api/v1/wanted/missing?apikey=$LIDARR_KEY" | jq '.totalRecords')
QUEUE=$(curl -s "$LIDARR_URL/api/v1/queue?apikey=$LIDARR_KEY" | jq '.totalRecords')
echo "   Artists: $ARTISTS"
echo "   Missing albums: $MISSING"
echo "   In queue: $QUEUE"
echo ""

# Check for common issues
echo "4. Common Issues Check:"

# Check if metadata refresh is needed
echo "   Checking last metadata refresh..."
LAST_REFRESH=$(curl -s "$LIDARR_URL/api/v1/system/task?apikey=$LIDARR_KEY" | jq -r '.[] | select(.name=="RefreshArtist") | .lastExecution')
echo "   Last artist refresh: $LAST_REFRESH"
echo ""

# Options
echo "5. Available Actions:"
echo "   a) Refresh all artist metadata"
echo "   b) Force rescan library"  
echo "   c) Clear metadata cache (via API)"
echo "   d) Test specific artist search"
echo "   q) Quit"
echo ""

if [ "$1" = "--auto" ]; then
    echo "Running in auto mode - skipping interactive menu"
    exit 0
fi

read -p "Select action (a/b/c/d/q): " action

case $action in
    a)
        echo "Triggering metadata refresh for all artists..."
        curl -s -X POST "$LIDARR_URL/api/v1/command?apikey=$LIDARR_KEY" \
            -H "Content-Type: application/json" \
            -d '{"name":"RefreshArtist"}' | jq '.status'
        echo "Refresh command sent. Check Lidarr UI for progress."
        ;;
    b)
        echo "Triggering library rescan..."
        curl -s -X POST "$LIDARR_URL/api/v1/command?apikey=$LIDARR_KEY" \
            -H "Content-Type: application/json" \
            -d '{"name":"RescanFolders"}' | jq '.status'
        echo "Rescan command sent."
        ;;
    c)
        echo "Note: Full cache clear requires restarting Lidarr container."
        read -p "Restart Lidarr? (y/n): " restart
        if [ "$restart" = "y" ]; then
            docker restart lidarr
            echo "Lidarr restarted."
        fi
        ;;
    d)
        read -p "Enter artist name to search: " artist
        echo "Searching for '$artist'..."
        curl -s "https://api.lidarr.audio/api/v0.4/search?type=all&query=$(echo $artist | sed 's/ /%20/g')" | jq '.[:3] | .[] | {name: .artist.artistname, id: .artist.id}'
        ;;
    *)
        echo "Exiting."
        ;;
esac
