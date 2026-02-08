#!/bin/bash
# lidarr-add-quick.sh - Add first match directly (non-interactive)
# Usage: ./lidarr-add-quick.sh "Artist Name"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

LIDARR_URL="http://localhost:8686"
LIDARR_KEY=$(grep -o '<ApiKey>[^<]*' "$PROJECT_DIR/lidarr/config/config.xml" 2>/dev/null | sed 's/<ApiKey>//')

if [ -z "$1" ]; then
    echo "Usage: $0 'Artist Name'"
    exit 1
fi

QUERY="$*"
echo "🔍 Searching for: $QUERY"

# Search MusicBrainz
result=$(curl -s -H "User-Agent: PirateOrb/1.0" \
    "https://musicbrainz.org/ws/2/artist/?query=artist:$(echo "$QUERY" | sed 's/ /%20/g')&fmt=json&limit=1")

mbid=$(echo "$result" | jq -r '.artists[0].id // empty')
name=$(echo "$result" | jq -r '.artists[0].name // empty')

if [ -z "$mbid" ]; then
    echo "❌ No results found"
    exit 1
fi

echo "📀 Found: $name (MBID: $mbid)"

# Check if already exists
existing=$(curl -s "$LIDARR_URL/api/v1/artist?apikey=$LIDARR_KEY" | jq -r ".[] | select(.foreignArtistId == \"$mbid\") | .artistName")
if [ -n "$existing" ]; then
    echo "⚠️  Already in Lidarr"
    exit 0
fi

# Get Lidarr config
root=$(curl -s "$LIDARR_URL/api/v1/rootfolder?apikey=$LIDARR_KEY" | jq -r '.[0].path')
qp=$(curl -s "$LIDARR_URL/api/v1/qualityprofile?apikey=$LIDARR_KEY" | jq -r '.[0].id')
mp=$(curl -s "$LIDARR_URL/api/v1/metadataprofile?apikey=$LIDARR_KEY" | jq -r '.[0].id')

# Add artist
response=$(curl -s -X POST "$LIDARR_URL/api/v1/artist?apikey=$LIDARR_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"foreignArtistId\": \"$mbid\",
        \"artistName\": \"$name\",
        \"path\": \"$root/$name\",
        \"qualityProfileId\": $qp,
        \"metadataProfileId\": $mp,
        \"monitored\": true,
        \"monitorNewItems\": \"all\",
        \"addOptions\": {
            \"monitor\": \"all\",
            \"searchForMissingAlbums\": true
        }
    }")

if echo "$response" | jq -e '.id' > /dev/null 2>&1; then
    echo "✅ Added '$name' to Lidarr!"
else
    echo "❌ Failed: $(echo "$response" | jq -r '.[0].errorMessage // .message // "Unknown error"')"
fi
