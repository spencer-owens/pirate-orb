#!/bin/bash
# Post-import cleanup script for Pirate Orb
# Cleans up orphaned download files, failed folders, and stale queue entries
# Run periodically or via cron

DOWNLOADS="/Volumes/Raiju/downloads"
RADARR_KEY=$(sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /Users/spencer/projects/pirate-orb/radarr/config/config.xml)
SONARR_KEY=$(sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /Users/spencer/projects/pirate-orb/sonarr/config/config.xml)
LIDARR_KEY=$(sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /Users/spencer/projects/pirate-orb/lidarr/config/config.xml)

echo "=== Pirate Orb Cleanup $(date) ==="

# 1. Remove _FAILED_ and _UNPACK_ folders
echo "[1] Cleaning failed/unpack folders..."
find "$DOWNLOADS" -maxdepth 2 -type d -name "_FAILED_*" -exec rm -rf {} + 2>/dev/null
find "$DOWNLOADS" -maxdepth 2 -type d -name "_UNPACK_*" -exec rm -rf {} + 2>/dev/null

# 2. Remove orphaned metadata files without associated media
echo "[2] Cleaning orphaned metadata..."
find "$DOWNLOADS/complete" -maxdepth 2 -empty -type d -delete 2>/dev/null

# 3. Clear stale Radarr queue entries (completed + warning = already imported elsewhere)
echo "[3] Clearing stale Radarr queue..."
curl -s "http://localhost:7878/api/v3/queue?apikey=$RADARR_KEY&pageSize=100" | python3 -c "
import json,sys,subprocess
d=json.load(sys.stdin)
for r in d.get('records',[]):
    if r.get('status')=='completed' and r.get('trackedDownloadStatus')=='warning':
        qid=r['id']
        title=r.get('title','?')
        print(f'  Removing stale: {title}')
        subprocess.run(['curl','-s','-X','DELETE',
            f'http://localhost:7878/api/v3/queue/{qid}?apikey=$RADARR_KEY&removeFromClient=true&blocklist=true'],
            capture_output=True)
" 2>/dev/null

# 4. Clear stale Sonarr queue entries
echo "[4] Clearing stale Sonarr queue..."
curl -s "http://localhost:8989/api/v3/queue?apikey=$SONARR_KEY&pageSize=100" | python3 -c "
import json,sys,subprocess
d=json.load(sys.stdin)
for r in d.get('records',[]):
    if r.get('status')=='completed' and r.get('trackedDownloadStatus')=='warning':
        qid=r['id']
        title=r.get('title','?')
        print(f'  Removing stale: {title}')
        subprocess.run(['curl','-s','-X','DELETE',
            f'http://localhost:8989/api/v3/queue/{qid}?apikey=$SONARR_KEY&removeFromClient=true&blocklist=true'],
            capture_output=True)
" 2>/dev/null

# 5. Remove encrypted/paused SABnzbd items
echo "[5] Checking SABnzbd for encrypted items..."
SAB_KEY="b21ed82e1f7a434781416da73d772e6f"
curl -s "http://localhost:8080/api?mode=queue&output=json&apikey=$SAB_KEY" | python3 -c "
import json,sys,subprocess
d=json.load(sys.stdin)
for slot in d.get('queue',{}).get('slots',[]):
    labels=slot.get('labels',[])
    if 'ENCRYPTED' in labels:
        nzo=slot['nzo_id']
        print(f'  Removing encrypted: {slot[\"filename\"]}')
        subprocess.run(['curl','-s',
            f'http://localhost:8080/api?mode=queue&name=delete&value={nzo}&del_files=1&apikey=$SAB_KEY'],
            capture_output=True)
" 2>/dev/null

# 6. Disk usage report
echo "[6] Disk usage:"
df -h /Volumes/Raiju | awk 'NR==2 {print "  Raiju: "$3" used / "$2" total ("$5" full)"}'
df -h /Volumes/Leviathan 2>/dev/null | awk 'NR==2 {print "  Leviathan: "$3" used / "$2" total ("$5" full)"}'

echo "=== Cleanup complete ==="
