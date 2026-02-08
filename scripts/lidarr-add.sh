#!/bin/bash
# lidarr-add.sh - Add artists to Lidarr by searching MusicBrainz directly
# Bypasses broken Lidarr search by using MusicBrainz API + MBID lookup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Config
LIDARR_URL="http://localhost:8686"
LIDARR_KEY=$(grep -o '<ApiKey>[^<]*' "$PROJECT_DIR/lidarr/config/config.xml" 2>/dev/null | sed 's/<ApiKey>//')
MUSIC_PATH="/Volumes/hal9000/Music"  # Default root folder

if [ -z "$LIDARR_KEY" ]; then
    echo "Error: Could not find Lidarr API key"
    exit 1
fi

usage() {
    echo "Usage: $0 <artist name>"
    echo ""
    echo "Searches MusicBrainz for the artist, then adds to Lidarr via MBID"
    echo ""
    echo "Examples:"
    echo "  $0 'Aphex Twin'"
    echo "  $0 'Nine Inch Nails'"
    echo "  $0 'Amon Tobin'"
}

search_musicbrainz() {
    local query="$1"
    curl -s -H "User-Agent: PirateOrb/1.0 (music automation)" \
        "https://musicbrainz.org/ws/2/artist/?query=artist:$(echo "$query" | sed 's/ /%20/g')&fmt=json&limit=5" 2>/dev/null
}

get_lidarr_root_folders() {
    curl -s "$LIDARR_URL/api/v1/rootfolder?apikey=$LIDARR_KEY" | jq -r '.[0].path' 2>/dev/null
}

get_lidarr_quality_profile() {
    curl -s "$LIDARR_URL/api/v1/qualityprofile?apikey=$LIDARR_KEY" | jq -r '.[0].id' 2>/dev/null
}

get_lidarr_metadata_profile() {
    curl -s "$LIDARR_URL/api/v1/metadataprofile?apikey=$LIDARR_KEY" | jq -r '.[0].id' 2>/dev/null
}

add_artist_to_lidarr() {
    local mbid="$1"
    local name="$2"
    
    # Get Lidarr's version of the artist data
    local artist_data=$(curl -s "https://api.lidarr.audio/api/v0.4/artist/$mbid")
    
    if [ -z "$artist_data" ] || [ "$artist_data" = "null" ]; then
        echo "Error: Could not fetch artist data from Lidarr API"
        return 1
    fi
    
    local root_folder=$(get_lidarr_root_folders)
    local quality_profile=$(get_lidarr_quality_profile)
    local metadata_profile=$(get_lidarr_metadata_profile)
    
    # Build the add request
    local payload=$(jq -n \
        --arg mbid "$mbid" \
        --arg name "$name" \
        --arg path "$root_folder/$name" \
        --argjson qp "$quality_profile" \
        --argjson mp "$metadata_profile" \
        '{
            foreignArtistId: $mbid,
            artistName: $name,
            path: $path,
            qualityProfileId: $qp,
            metadataProfileId: $mp,
            monitored: true,
            monitorNewItems: "all",
            addOptions: {
                monitor: "all",
                searchForMissingAlbums: true
            }
        }')
    
    local response=$(curl -s -X POST "$LIDARR_URL/api/v1/artist?apikey=$LIDARR_KEY" \
        -H "Content-Type: application/json" \
        -d "$payload")
    
    if echo "$response" | jq -e '.id' > /dev/null 2>&1; then
        echo "✅ Added '$name' to Lidarr (ID: $(echo "$response" | jq -r '.id'))"
        return 0
    else
        local error=$(echo "$response" | jq -r '.[] | .errorMessage // .message // .' 2>/dev/null | head -1)
        echo "❌ Failed to add '$name': $error"
        return 1
    fi
}

# Main
if [ $# -eq 0 ]; then
    usage
    exit 1
fi

QUERY="$*"
echo "🔍 Searching MusicBrainz for: $QUERY"
echo ""

# Search MusicBrainz
results=$(search_musicbrainz "$QUERY")

if [ -z "$results" ] || [ "$(echo "$results" | jq '.artists | length')" = "0" ]; then
    echo "No results found on MusicBrainz"
    exit 1
fi

# Show results
echo "Found artists:"
echo ""
echo "$results" | jq -r '.artists[:5] | to_entries[] | "\(.key + 1)) \(.value.name) [\(.value.type // "Unknown")] - \(.value.disambiguation // "no description")"'
echo ""

# Select
read -p "Select artist (1-5) or 'q' to quit: " selection

if [ "$selection" = "q" ]; then
    exit 0
fi

if ! [[ "$selection" =~ ^[1-5]$ ]]; then
    echo "Invalid selection"
    exit 1
fi

idx=$((selection - 1))
mbid=$(echo "$results" | jq -r ".artists[$idx].id")
name=$(echo "$results" | jq -r ".artists[$idx].name")

echo ""
echo "Selected: $name (MBID: $mbid)"
echo ""

# Check if already in Lidarr
existing=$(curl -s "$LIDARR_URL/api/v1/artist?apikey=$LIDARR_KEY" | jq -r ".[] | select(.foreignArtistId == \"$mbid\") | .artistName")

if [ -n "$existing" ]; then
    echo "⚠️  '$name' is already in Lidarr"
    exit 0
fi

# Add to Lidarr
add_artist_to_lidarr "$mbid" "$name"
