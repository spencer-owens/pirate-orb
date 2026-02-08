#!/bin/bash
# Queue Doctor - Automatically fixes common download pipeline issues
# Run periodically via cron or heartbeat

RADARR_KEY=$(sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /Users/spencer/projects/pirate-orb/radarr/config/config.xml)
SONARR_KEY=$(sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /Users/spencer/projects/pirate-orb/sonarr/config/config.xml)
WHISPARR_KEY=$(sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /Users/spencer/projects/pirate-orb/whisparr/config/config.xml)
SAB_KEY="b21ed82e1f7a434781416da73d772e6f"

FIXED=0

echo "=== Queue Doctor $(date) ==="

# --- SABnzbd: Remove encrypted items ---
encrypted=$(curl -s "http://localhost:8080/api?mode=queue&output=json&apikey=$SAB_KEY" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for slot in d.get('queue',{}).get('slots',[]):
    if 'ENCRYPTED' in slot.get('labels',[]):
        print(slot['nzo_id'])
" 2>/dev/null)

for nzo in $encrypted; do
    echo "[FIX] Removing encrypted SABnzbd item: $nzo"
    curl -s "http://localhost:8080/api?mode=queue&name=delete&value=$nzo&del_files=1&apikey=$SAB_KEY" > /dev/null
    FIXED=$((FIXED+1))
done

# --- Sonarr: Remove failed downloads, blocklist, trigger re-search ---
sonarr_failed=$(curl -s "http://localhost:8989/api/v3/queue?apikey=$SONARR_KEY&pageSize=200" | python3 -c "
import json,sys
d=json.load(sys.stdin)
series_ids=set()
for r in d.get('records',[]):
    if r.get('status')=='failed':
        print(f'REMOVE:{r[\"id\"]}')
        series_ids.add(str(r.get('seriesId','')))
for sid in series_ids:
    if sid: print(f'SEARCH:{sid}')
" 2>/dev/null)

echo "$sonarr_failed" | grep "^REMOVE:" | cut -d: -f2 | while read id; do
    [ -z "$id" ] && continue
    curl -s -X DELETE "http://localhost:8989/api/v3/queue/$id?apikey=$SONARR_KEY&removeFromClient=true&blocklist=true" -o /dev/null
    FIXED=$((FIXED+1))
    echo "[FIX] Removed failed Sonarr queue item: $id"
done

echo "$sonarr_failed" | grep "^SEARCH:" | cut -d: -f2 | while read sid; do
    [ -z "$sid" ] && continue
    curl -s -X POST "http://localhost:8989/api/v3/command?apikey=$SONARR_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"SeriesSearch\",\"seriesId\":$sid}" -o /dev/null
    echo "[FIX] Triggered re-search for Sonarr series: $sid"
done

# --- Sonarr: Remove completed/warning (import issues), blocklist ---
sonarr_warnings=$(curl -s "http://localhost:8989/api/v3/queue?apikey=$SONARR_KEY&pageSize=200" | python3 -c "
import json,sys
d=json.load(sys.stdin)
series_ids=set()
for r in d.get('records',[]):
    if r.get('status')=='completed' and r.get('trackedDownloadStatus')=='warning':
        print(f'REMOVE:{r[\"id\"]}')
        series_ids.add(str(r.get('seriesId','')))
for sid in series_ids:
    if sid: print(f'SEARCH:{sid}')
" 2>/dev/null)

echo "$sonarr_warnings" | grep "^REMOVE:" | cut -d: -f2 | while read id; do
    [ -z "$id" ] && continue
    curl -s -X DELETE "http://localhost:8989/api/v3/queue/$id?apikey=$SONARR_KEY&removeFromClient=true&blocklist=true" -o /dev/null
    FIXED=$((FIXED+1))
    echo "[FIX] Removed stale Sonarr warning item: $id"
done

echo "$sonarr_warnings" | grep "^SEARCH:" | cut -d: -f2 | while read sid; do
    [ -z "$sid" ] && continue
    curl -s -X POST "http://localhost:8989/api/v3/command?apikey=$SONARR_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"SeriesSearch\",\"seriesId\":$sid}" -o /dev/null
    echo "[FIX] Triggered re-search for Sonarr series: $sid"
done

# --- Radarr: Same treatment ---
radarr_issues=$(curl -s "http://localhost:7878/api/v3/queue?apikey=$RADARR_KEY&pageSize=100" | python3 -c "
import json,sys
d=json.load(sys.stdin)
movie_ids=set()
for r in d.get('records',[]):
    if r.get('status') in ('failed',) or (r.get('status')=='completed' and r.get('trackedDownloadStatus')=='warning'):
        print(f'REMOVE:{r[\"id\"]}')
        movie_ids.add(str(r.get('movieId','')))
for mid in movie_ids:
    if mid: print(f'SEARCH:{mid}')
" 2>/dev/null)

echo "$radarr_issues" | grep "^REMOVE:" | cut -d: -f2 | while read id; do
    [ -z "$id" ] && continue
    curl -s -X DELETE "http://localhost:7878/api/v3/queue/$id?apikey=$RADARR_KEY&removeFromClient=true&blocklist=true" -o /dev/null
    FIXED=$((FIXED+1))
    echo "[FIX] Removed Radarr issue item: $id"
done

echo "$radarr_issues" | grep "^SEARCH:" | cut -d: -f2 | while read mid; do
    [ -z "$mid" ] && continue
    curl -s -X POST "http://localhost:7878/api/v3/command?apikey=$RADARR_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"MoviesSearch\",\"movieIds\":[$mid]}" -o /dev/null
    echo "[FIX] Triggered re-search for Radarr movie: $mid"
done

# --- Cleanup failed folders ---
find /Volumes/Raiju/downloads -maxdepth 3 -type d -name "_FAILED_*" -exec rm -rf {} + 2>/dev/null
find /Volumes/Raiju/downloads -maxdepth 3 -type d -name "_UNPACK_*" -exec rm -rf {} + 2>/dev/null
find /Volumes/Raiju/downloads/complete -maxdepth 2 -empty -type d -delete 2>/dev/null

echo "=== Queue Doctor complete. Fixed: $FIXED issues ==="
