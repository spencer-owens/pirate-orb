#!/usr/bin/env python3
"""Retry sweep: re-monitor favorites-backfill albums that Soularr failed out.

Soularr's remove_wanted_on_failure unmonitors an album after one fruitless
Soulseek search. Sources rotate as peers come/go, so a periodic re-monitor
gives failed albums another shot. Only touches albums we actually requested
(state file requested_mbids), incomplete on disk, currently unmonitored.
Artists are re-monitored too (Soularr gates on artist monitored).

Silent when there's nothing to retry — cron-friendly.
"""

import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / ".apple-music-favorites-state.json"
LIDARR = "http://localhost:8686/api/v1"
KEY = re.search(r"<ApiKey>([^<]+)</ApiKey>",
                (HERE.parent / "lidarr" / "config" / "config.xml").read_text()).group(1)


def api(path, method="GET", body=None):
    req = urllib.request.Request(
        f"{LIDARR}{path}", method=method,
        headers={"X-Api-Key": KEY, "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read()
        return json.loads(t) if t else None


def main():
    requested = set(json.loads(STATE.read_text()).get("requested_mbids", []))
    artists = {a["id"]: a for a in api("/artist")}

    stale = [a for a in api("/album")
             if a["foreignAlbumId"] in requested
             and not a["monitored"]
             and (a.get("statistics") or {}).get("percentOfTracks", 0) < 100]
    if not stale:
        return

    api("/album/monitor", "PUT", {"albumIds": [a["id"] for a in stale], "monitored": True})

    unmon_artists = {a["artistId"] for a in stale} & {
        aid for aid, art in artists.items() if not art["monitored"]}
    if unmon_artists:
        api("/artist/editor", "PUT", {"artistIds": sorted(unmon_artists),
                                      "monitored": True, "monitorNewItems": "none"})

    # Soulseek retry happens via Soularr's next cycle; this hits torrents+usenet
    api("/command", "POST", {"name": "AlbumSearch", "albumIds": [a["id"] for a in stale]})

    print(f"Re-monitored {len(stale)} albums ({len(unmon_artists)} artists re-flipped) "
          f"for another Soularr pass:")
    for a in sorted(stale, key=lambda x: x["title"]):
        print(f"  {artists.get(a['artistId'], {}).get('artistName', '?')} — {a['title']}")


if __name__ == "__main__":
    main()
