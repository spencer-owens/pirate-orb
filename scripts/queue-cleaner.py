#!/usr/bin/env python3
"""
Lidarr Queue Cleaner — detects and handles bad downloads.

Rules:
  - HARD REJECT: 1 audio file when album expects >1 track (single-file rip)
  - SOFT REJECT: file count is >2x or <0.5x expected track count (wrong edition)
  - AUTO-APPROVE: file count within tolerance (±50% of expected)

On reject: removes from queue, optionally blocklists, triggers re-search.
On approve: forces import via Lidarr API.

Usage:
  python3 queue-cleaner.py [--dry-run] [--lidarr-url URL] [--api-key KEY]
"""

import argparse
import json
import logging
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("queue-cleaner")

AUDIO_EXTENSIONS = {
    "flac", "alac", "wav", "aac", "ogg", "mp3", "m4a", "wma", "ape", "opus", "wv",
}


def api(base_url, api_key, method, path, body=None):
    """Simple Lidarr API helper."""
    url = f"{base_url}/api/v1/{path}"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            body = resp.read()
            if resp.status == 200 and body:
                return json.loads(body)
            return None
    except HTTPError as e:
        if e.code == 404:
            return None
        log.error(f"API error {e.code} for {method} {path}: {e.read().decode()[:200]}")
        raise


def count_audio_files(status_messages):
    """Count audio files mentioned in Lidarr queue status messages."""
    count = 0
    for msg in status_messages:
        title = msg.get("title", "")
        if "." in title:
            ext = title.rsplit(".", 1)[-1].lower()
            if ext in AUDIO_EXTENSIONS:
                count += 1
    return count


def get_album_track_count(base_url, api_key, album_id):
    """Get expected track count for an album via tracks endpoint."""
    tracks = api(base_url, api_key, "GET", f"track?albumId={album_id}")
    if tracks and isinstance(tracks, list):
        return len(tracks)
    return None


def remove_from_queue(base_url, api_key, record_id, blocklist=True):
    """Remove item from Lidarr queue."""
    path = f"queue/{record_id}?removeFromClient=true&blocklist={'true' if blocklist else 'false'}&skipRedownload=false"
    api(base_url, api_key, "DELETE", path)


def search_album(base_url, api_key, album_ids):
    """Trigger album search in Lidarr."""
    body = {"name": "AlbumSearch", "albumIds": album_ids}
    api(base_url, api_key, "POST", "command", body)


def attempt_clean_import(base_url, api_key, download_id, label):
    """Try a scripted manual import: only files that map cleanly (no rejections)
    to artist+album+tracks. Returns imported file count, or 0."""
    cands = api(base_url, api_key, "GET",
                f"manualimport?downloadId={download_id}&filterExistingFiles=true")
    if not cands or not isinstance(cands, list):
        return 0
    files = []
    for c in cands:
        if isinstance(c, dict) and c.get("artist") and c.get("album") and c.get("tracks") \
           and not c.get("rejections"):
            files.append({
                "path": c["path"], "artistId": c["artist"]["id"],
                "albumId": c["album"]["id"], "albumReleaseId": c["albumReleaseId"],
                "trackIds": [t["id"] for t in c["tracks"]],
                "quality": c["quality"], "downloadId": download_id,
                "disableReleaseSwitching": False,
            })
    if not files:
        return 0
    api(base_url, api_key, "POST", "command",
        {"name": "ManualImport", "files": files, "importMode": "move"})
    log.info(f"    📥 clean manual import: {len(files)} files ({label})")
    return len(files)


def process_queue(base_url, api_key, dry_run=False):
    """Main queue processing loop."""
    queue = api(base_url, api_key, "GET", "queue?page=1&pageSize=100&includeArtist=true&includeAlbum=true")
    if not queue:
        log.error("Failed to fetch queue")
        return

    total = queue.get("totalRecords", 0)
    log.info(f"Queue has {total} items")

    rejects = []
    approvals = []
    imported = []

    for record in queue.get("records", []):
        rid = record["id"]
        status = record.get("status", "")
        tracked = record.get("trackedDownloadStatus", "")
        artist_name = record.get("artist", {}).get("artistName", "Unknown")
        album_title = record.get("album", {}).get("title", "Unknown")
        album_id = record.get("albumId")
        label = f"{artist_name} — {album_title}"

        # Only process completed items with warnings (stuck imports)
        if status != "completed" or tracked != "warning":
            continue

        status_messages = record.get("statusMessages", [])
        audio_count = count_audio_files(status_messages)
        expected = get_album_track_count(base_url, api_key, album_id)

        if expected is None:
            log.warning(f"  [{label}] Could not determine expected track count, skipping")
            continue

        log.info(f"  [{label}] files={audio_count} expected={expected}")

        # Rule 1: Single-file rip
        if audio_count <= 1 and expected > 1:
            log.info(f"    ❌ HARD REJECT — single-file rip ({audio_count} file for {expected}-track album)")
            rejects.append({"id": rid, "album_id": album_id, "label": label, "reason": "single-file rip", "blocklist": True})
            continue

        # Rule 2: Wildly off count (>2x or <0.5x)
        ratio = audio_count / expected if expected > 0 else 0
        if ratio > 2.0:
            log.info(f"    ❌ SOFT REJECT — too many files ({audio_count} vs {expected} expected, ratio {ratio:.1f}x)")
            rejects.append({"id": rid, "album_id": album_id, "label": label, "reason": f"wrong edition ({audio_count} files vs {expected} expected)", "blocklist": True})
            continue

        if ratio < 0.5:
            log.info(f"    ❌ SOFT REJECT — too few files ({audio_count} vs {expected} expected, ratio {ratio:.1f}x)")
            rejects.append({"id": rid, "album_id": album_id, "label": label, "reason": f"incomplete ({audio_count} files vs {expected} expected)", "blocklist": True})
            continue

        # Rule 3: Within tolerance — try clean manual import, else escalate.
        log.info(f"    ✅ ACCEPTABLE — {audio_count} files for {expected}-track album (ratio {ratio:.1f}x)")
        download_id = record.get("downloadId")
        if dry_run or not download_id:
            approvals.append({"id": rid, "album_id": album_id, "label": label, "ratio": ratio})
            continue
        if attempt_clean_import(base_url, api_key, download_id, label):
            imported.append(label)
        else:
            # Complete download that Lidarr can't cleanly map (wrong edition /
            # bad tags / not-an-upgrade): blocklist + re-search a better release.
            msgs = json.dumps(record.get("statusMessages", []))
            if "Not an upgrade" in msgs:
                log.info("    🗑  removing (existing copy is better; no re-search)")
                remove_from_queue(base_url, api_key, rid, blocklist=True)
            else:
                log.info("    🗑  unmappable — blocklist + re-search")
                rejects.append({"id": rid, "album_id": album_id, "label": label,
                                "reason": "complete but unimportable (bad match/tags)", "blocklist": True})

    # Execute rejections
    if rejects:
        log.info(f"\n--- Rejecting {len(rejects)} items ---")
        album_ids_to_research = []
        for r in rejects:
            log.info(f"  🗑  {r['label']} — {r['reason']}")
            if not dry_run:
                remove_from_queue(base_url, api_key, r["id"], blocklist=r["blocklist"])
                album_ids_to_research.append(r["album_id"])
                time.sleep(0.5)  # Be gentle

        if album_ids_to_research and not dry_run:
            log.info(f"  🔍 Triggering re-search for {len(album_ids_to_research)} albums...")
            search_album(base_url, api_key, album_ids_to_research)
    else:
        log.info("No items to reject")

    # Report
    if imported:
        log.info(f"\n--- {len(imported)} items imported via clean manual import ---")
        for l in imported:
            log.info(f"  📥 {l}")
    if approvals:
        log.info(f"\n--- {len(approvals)} items within tolerance (manual import recommended) ---")
        for a in approvals:
            log.info(f"  📦 {a['label']} (ratio {a['ratio']:.1f}x)")

    if dry_run:
        log.info("\n🏜️  DRY RUN — no changes made")

    return {"rejected": len(rejects), "acceptable": len(approvals), "imported": len(imported)}


def main():
    parser = argparse.ArgumentParser(description="Lidarr Queue Cleaner")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    parser.add_argument("--lidarr-url", default=os.environ.get("LIDARR_URL", "http://localhost:8686"))
    parser.add_argument("--api-key", default=os.environ.get("LIDARR_API_KEY", ""))
    args = parser.parse_args()

    log.info(f"Lidarr Queue Cleaner starting (dry_run={args.dry_run})")
    result = process_queue(args.lidarr_url, args.api_key, args.dry_run)
    if result:
        log.info(f"Done: {result['rejected']} rejected, {result['imported']} imported, {result['acceptable']} left for manual review")


if __name__ == "__main__":
    main()
