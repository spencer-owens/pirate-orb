# Lidarr Metadata Issues & Fixes

## Known Issues

### 1. MusicBrainz Non-Audio Media Filter
**Status**: Open PR #4124 (marked "Don't Merge" by maintainers)

**Problem**: Lidarr filters out releases where MusicBrainz marks the media type as non-audio (DVD, Blu-ray, etc.). This hides legitimate audio releases that happen to be sourced from Blu-ray Audio or concert DVDs.

**Workaround**: None officially supported. The PR exists but maintainers are hesitant to merge due to concerns about ISO/directory support.

**Impact**: ~5-10% of releases may be hidden, especially:
- High-resolution Blu-ray Audio releases
- Concert audio rips
- Vinyl-only releases (sometimes miscategorized)

### 2. LidarrAPI Server Issues (api.lidarr.audio)
**Status**: Intermittent - Issue #5498

**Problem**: The Lidarr metadata proxy server occasionally returns 500 errors or times out.

**Symptoms**:
- "Unable to communicate with LidarrAPI"
- "HTTP Request Timeout"
- Artist searches returning empty

**Workaround**: 
- Wait and retry (usually clears within an hour)
- Restart Lidarr container to clear connection pools
- Check https://api.lidarr.audio/api/v0.4/search?type=all&query=test directly

### 3. Sync Timing
**How it works**: Lidarr→MusicBrainz sync runs hourly at :05

**Workaround**: If a release exists on MusicBrainz but not Lidarr:
1. Wait up to 1 hour for sync
2. Or manually trigger refresh: System → Tasks → Refresh All Artists

## Diagnostic Commands

```bash
# Check Lidarr API directly
curl "https://api.lidarr.audio/api/v0.4/search?type=all&query=artist_name"

# Check local Lidarr health
curl "http://localhost:8686/api/v1/health?apikey=YOUR_KEY"

# Force refresh all metadata
curl -X POST "http://localhost:8686/api/v1/command?apikey=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"RefreshArtist"}'

# Run full diagnostics
./scripts/lidarr-diagnostics.sh
```

## Alternative Approaches

### Option A: Direct MusicBrainz Queries
For critical lookups, you can query MusicBrainz directly:
```bash
# Find artist by name
curl "https://musicbrainz.org/ws/2/artist/?query=artist_name&fmt=json"

# Get releases for artist
curl "https://musicbrainz.org/ws/2/release-group?artist=MBID&fmt=json"
```

### Option B: Manual Import
If Lidarr can't find a release:
1. Download the release manually
2. Use Manual Import in Lidarr
3. Search by MusicBrainz Release Group ID if available

### Option C: Lidarr Extended (Community Fork)
Some users maintain forks with additional fixes. Check r/Lidarr for current recommendations.

## Monitoring

The health monitor script checks:
- Container status
- VPN connectivity  
- Disk usage
- Lidarr API availability

Run: `./scripts/health-monitor.sh`

Schedule via cron:
```bash
# Every 15 minutes
*/15 * * * * /Users/spencer/projects/pirate-orb/scripts/health-monitor.sh
```

## Resources

- [Lidarr GitHub Issues](https://github.com/Lidarr/Lidarr/issues)
- [Servarr Wiki - Lidarr FAQ](https://wiki.servarr.com/lidarr/faq)
- [TRaSH Guides](https://trash-guides.info/Lidarr/)
- [r/Lidarr](https://reddit.com/r/Lidarr)
