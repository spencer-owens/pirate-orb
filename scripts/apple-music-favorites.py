#!/usr/bin/env python3
"""Apple Music favorites -> MusicSeerr album requests.

Reads favorited tracks/albums from the local Music.app library (iCloud-synced
from all devices) via AppleScript, resolves each NEW favorite to a MusicBrainz
release-group, and files an album request with MusicSeerr — which rides the
existing pipeline: monitor-only-that-album in Lidarr -> Soularr/slskd ->
hal9000 -> Plex.

State: .apple-music-favorites-state.json alongside this script.
Unresolved favorites land in .apple-music-favorites-unresolved.json for review.
First run baselines (records existing favorites, requests nothing) and writes
.apple-music-favorites-backfill.txt for cherry-picking.

Designed as a silent-on-idle cron job: prints only when it does something.
"""

import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

HERE = Path(__file__).resolve().parent
STATE = HERE / ".apple-music-favorites-state.json"
UNRESOLVED = HERE / ".apple-music-favorites-unresolved.json"
BACKFILL = HERE / ".apple-music-favorites-backfill.txt"

MUSICSEERR = "http://localhost:3333"
CREDS = HERE.parent / "musicseerr" / "admin-credentials.txt"
EMAIL = "spencer.m.owens@gmail.com"

MB = "https://musicbrainz.org/ws/2"
UA = "pirate-orb-favorites-sync/1.0 (spencer.m.owens@gmail.com)"

PLEX = "http://localhost:32400"
PLEX_MUSIC_SECTION = "4"


def _plex_token() -> str:
    import os
    tok = os.environ.get("PLEX_TOKEN")
    if tok:
        return tok
    for line in (HERE.parent / ".env").read_text().splitlines():
        if line.startswith("PLEX_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("PLEX_TOKEN not found in env or repo .env")

SEP = "|||"
SUFFIX_RE = re.compile(
    r"\s*(?:- (?:Single|EP)|[(\[][^)\]]*(?:Deluxe|Remaster|Anniversary|Expanded|"
    r"Bonus|Special|Digital|Edition|Version|Mix)[^)\]]*[)\]])\s*$",
    re.I,
)


def osascript(script: str, retries: int = 2) -> str:
    for attempt in range(retries + 1):
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=900)
        if r.returncode == 0:
            return r.stdout
        if "timed out" in r.stderr and attempt < retries:
            time.sleep(30)  # Music.app busy (e.g. iCloud sync churn); retry
            continue
        raise RuntimeError(f"osascript failed: {r.stderr.strip()}")


def dump_favorites() -> list:
    """All favorited tracks + tracks of favorited albums, with persistent IDs."""
    out = osascript(f'''
    with timeout of 600 seconds
    tell application "Music"
        set res to ""
        repeat with t in (every track of library playlist 1 whose favorited is true or album favorited is true)
            set res to res & (persistent ID of t) & "{SEP}" & (artist of t) & "{SEP}" & (album of t) & "{SEP}" & (name of t) & linefeed
        end repeat
        return res
    end tell
    end timeout''')
    favs = []
    for line in out.splitlines():
        parts = line.split(SEP)
        if len(parts) == 4 and parts[0].strip():
            favs.append(dict(zip(("id", "artist", "album", "track"), (p.strip() for p in parts))))
    return favs


def clean_album(name: str) -> tuple[str, bool]:
    """Strip edition suffixes. Returns (cleaned, was_single_or_ep)."""
    single = bool(re.search(r"- (Single|EP)\s*$", name, re.I))
    prev = None
    while prev != name:
        prev, name = name, SUFFIX_RE.sub("", name)
    return name.strip(), single


def mb_get(path: str, params: dict) -> dict:
    url = f"{MB}{path}?{urllib.parse.urlencode({**params, 'fmt': 'json'})}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    time.sleep(1.1)  # MB rate limit: 1 req/s
    return data


def lucene_escape(s: str) -> str:
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)', r"\\\1", s)


def resolve(artist: str, album: str, track: str) -> Optional[Tuple[str, str]]:
    """Favorite -> (release-group MBID, resolved title). Albums > EPs > singles."""
    cleaned, is_single = clean_album(album)

    if is_single:
        # Find the studio album containing this song
        q = f'recording:"{lucene_escape(track)}" AND artist:"{lucene_escape(artist)}"'
        try:
            recs = mb_get("/recording", {"query": q, "limit": 10}).get("recordings", [])
            for rec in recs:
                if int(rec.get("score", 0)) < 90:
                    continue
                for rel in rec.get("releases", []):
                    rg = rel.get("release-group", {})
                    if rg.get("primary-type") == "Album" and not rg.get("secondary-types"):
                        return rg["id"], rg.get("title", cleaned)
        except Exception:
            pass  # fall through to release-group search on the single itself

    q = f'releasegroup:"{lucene_escape(cleaned)}" AND artist:"{lucene_escape(artist)}"'
    try:
        rgs = mb_get("/release-group", {"query": q, "limit": 10}).get("release-groups", [])
    except Exception:
        return None
    scored = [rg for rg in rgs if int(rg.get("score", 0)) >= 90]
    for want in ("Album", "EP", "Single"):
        for rg in scored:
            if rg.get("primary-type") == want and not rg.get("secondary-types"):
                return rg["id"], rg.get("title", cleaned)
    return (scored[0]["id"], scored[0].get("title", cleaned)) if scored else None


def musicseerr_token() -> str:
    pw = CREDS.read_text().strip()
    req = urllib.request.Request(
        f"{MUSICSEERR}/api/v1/auth/login", method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": EMAIL, "password": pw}).encode(),
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["token"]


def request_album(token: str, mbid: str, artist: str, album: str) -> str:
    req = urllib.request.Request(
        f"{MUSICSEERR}/api/v1/requests/new", method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        data=json.dumps({"musicbrainz_id": mbid, "artist": artist, "album": album}).encode(),
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("message", "?")


# --- trigger-track rating: 5-star the song that caused each album request ---

def plex_get(path: str, params: dict) -> dict:
    qs = urllib.parse.urlencode({**params, "X-Plex-Token": _plex_token()})
    req = urllib.request.Request(f"{PLEX}{path}?{qs}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def rate_trigger_track(artist: str, track: str) -> bool:
    """Find track in Plex music library and set userRating=10 (5 stars).
    Returns True when rated (or already rated), False when not found yet."""
    data = plex_get(f"/library/sections/{PLEX_MUSIC_SECTION}/all",
                    {"type": "10", "title": track})
    for m in data.get("MediaContainer", {}).get("Metadata", []):
        if _norm(m.get("grandparentTitle", "")) != _norm(artist):
            continue
        if _norm(m.get("title", "")) != _norm(track):
            continue
        if m.get("userRating") == 10:
            return True
        qs = urllib.parse.urlencode({
            "identifier": "com.plexapp.plugins.library", "key": m["ratingKey"],
            "rating": "10", "X-Plex-Token": _plex_token()})
        req = urllib.request.Request(f"{PLEX}/:/rate?{qs}", method="PUT")
        with urllib.request.urlopen(req, timeout=30):
            pass
        return True
    return False


def reconcile_trigger_ratings(state: dict) -> None:
    """5-star pending trigger tracks whose albums have since landed in Plex.
    pending_ratings: [{artist, track, album, mbid, requested_at}]"""
    pending = state.get("pending_ratings", [])
    if not pending:
        return
    still = []
    for p in pending:
        try:
            done = rate_trigger_track(p["artist"], p["track"])
        except Exception as e:
            print(f"RATING CHECK FAILED (kept pending): {p['artist']} — {p['track']}: {e}",
                  file=sys.stderr)
            still.append(p)
            continue
        if done:
            print(f"RATED ★★★★★ trigger track: {p['artist']} — {p['track']} "
                  f"(reason album '{p['album']}' was requested)")
        else:
            still.append(p)  # album not imported/scanned yet; retry next run
    state["pending_ratings"] = still


def main() -> None:
    favs = dump_favorites()
    if not favs:
        print("WARNING: Music.app returned zero favorites — library unavailable?", file=sys.stderr)
        sys.exit(1)

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    seen = set(state.get("seen_ids", []))
    requested = set(state.get("requested_mbids", []))

    if not state:  # first run: baseline, no requests
        albums = sorted({f"{f['artist']} — {f['album']}" for f in favs})
        BACKFILL.write_text("\n".join(albums) + "\n")
        STATE.write_text(json.dumps({"seen_ids": [f["id"] for f in favs], "requested_mbids": []}))
        print(f"Baselined {len(favs)} favorites ({len(albums)} unique albums). "
              f"Backfill candidates: {BACKFILL}")
        return

    new = [f for f in favs if f["id"] not in seen]
    if not new:
        reconcile_trigger_ratings(state)
        STATE.write_text(json.dumps(state))
        return  # silent unless reconcile printed

    # Dedupe multiple new favorites from the same album
    by_album: dict[tuple, dict] = {(f["artist"].lower(), f["album"].lower()): f for f in new}

    token = musicseerr_token()
    unresolved = json.loads(UNRESOLVED.read_text()) if UNRESOLVED.exists() else []
    pending = state.get("pending_ratings", [])
    for f in by_album.values():
        hit = resolve(f["artist"], f["album"], f["track"])
        if not hit:
            unresolved.append({k: f[k] for k in ("artist", "album", "track")})
            print(f"UNRESOLVED: {f['artist']} — {f['album']} ({f['track']})")
            continue
        mbid, title = hit
        if mbid in requested:
            continue
        msg = request_album(token, mbid, f["artist"], title)
        requested.add(mbid)
        print(f"REQUESTED: {f['artist']} — {title} [{mbid}]: {msg}")
        print(f"  trigger track: “{f['track']}” (will be 5-starred in Plex once imported)")
        pending.append({"artist": f["artist"], "track": f["track"], "album": title,
                        "mbid": mbid, "requested_at": time.strftime("%Y-%m-%dT%H:%M:%S")})

    seen.update(f["id"] for f in new)
    state["seen_ids"] = sorted(seen)
    state["requested_mbids"] = sorted(requested)
    state["pending_ratings"] = pending
    reconcile_trigger_ratings(state)
    STATE.write_text(json.dumps(state))
    UNRESOLVED.write_text(json.dumps(unresolved, indent=1))


def lidarr_albums_on_disk() -> set:
    """foreignAlbumIds (release-group MBIDs) that already have files."""
    import os
    key = os.environ.get("LIDARR_API_KEY")
    if not key:
        xml = (HERE.parent / "lidarr" / "config" / "config.xml").read_text()
        key = re.search(r"<ApiKey>([^<]+)</ApiKey>", xml).group(1)
    req = urllib.request.Request("http://localhost:8686/api/v1/album",
                                 headers={"X-Api-Key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        return {a["foreignAlbumId"] for a in json.load(r)
                if (a.get("statistics") or {}).get("trackFileCount", 0) > 0}


def backfill(limit: int) -> None:
    """Request up to `limit` albums from the EXISTING favorites baseline.

    Resumable: processed albums are recorded in state (backfilled_keys), so
    successive runs continue where the last stopped. Albums already on disk
    or already requested don't consume limit slots.
    """
    favs = dump_favorites()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    requested = set(state.get("requested_mbids", []))
    done = set(state.get("backfilled_keys", []))

    try:
        on_disk = lidarr_albums_on_disk()
    except Exception as e:
        print(f"WARNING: Lidarr pre-check unavailable ({e}); proceeding without it", file=sys.stderr)
        on_disk = set()

    by_album = {}
    for f in favs:
        by_album.setdefault(f"{f['artist'].lower()}|{f['album'].lower()}", f)

    token = musicseerr_token()
    unresolved = json.loads(UNRESOLVED.read_text()) if UNRESOLVED.exists() else []
    n_req = n_skip = n_unres = 0
    for key in sorted(by_album):
        if n_req >= limit:
            break
        if key in done:
            continue
        f = by_album[key]
        done.add(key)
        hit = resolve(f["artist"], f["album"], f["track"])
        if not hit:
            unresolved.append({k: f[k] for k in ("artist", "album", "track")})
            print(f"UNRESOLVED: {f['artist']} — {f['album']} ({f['track']})")
            n_unres += 1
            continue
        mbid, title = hit
        if mbid in requested or mbid in on_disk:
            n_skip += 1
            continue
        msg = request_album(token, mbid, f["artist"], title)
        requested.add(mbid)
        n_req += 1
        print(f"REQUESTED {n_req}/{limit}: {f['artist']} — {title}: {msg}")
        state.setdefault("pending_ratings", []).append(
            {"artist": f["artist"], "track": f["track"], "album": title,
             "mbid": mbid, "requested_at": time.strftime("%Y-%m-%dT%H:%M:%S")})

    state["requested_mbids"] = sorted(requested)
    state["backfilled_keys"] = sorted(done)
    STATE.write_text(json.dumps(state))
    UNRESOLVED.write_text(json.dumps(unresolved, indent=1))
    print(f"batch done: {n_req} requested, {n_skip} already had/requested, "
          f"{n_unres} unresolved, {len(by_album) - len(done)} albums remaining")


def star_backfill(dry_run: bool = False) -> None:
    """Retroactively 5-star every track-level Apple Music favorite that exists
    in Plex. This applies the trigger-track pattern to ALL albums the pipeline
    (or anything else) already landed — not just post-feature requests.
    Only touches tracks with NO existing rating (never clobbers manual stars)."""
    out = osascript(f'''
    with timeout of 600 seconds
    tell application "Music"
        set res to ""
        repeat with t in (every track of library playlist 1 whose favorited is true)
            set res to res & (artist of t) & "{SEP}" & (album of t) & "{SEP}" & (name of t) & linefeed
        end repeat
        return res
    end tell
    end timeout''')
    favs = []
    for line in out.splitlines():
        parts = line.split(SEP)
        if len(parts) == 3 and parts[0].strip():
            favs.append(tuple(p.strip() for p in parts))
    favs = sorted(set(favs))
    print(f"{len(favs)} track-level favorites in Apple Music")

    starred = already = missing = 0
    missing_list = []
    for artist, album, track in favs:
        try:
            data = plex_get(f"/library/sections/{PLEX_MUSIC_SECTION}/all",
                            {"type": "10", "title": track})
        except Exception as e:
            print(f"PLEX LOOKUP FAILED: {artist} — {track}: {e}", file=sys.stderr)
            continue
        hit = None
        for m in data.get("MediaContainer", {}).get("Metadata", []):
            if _norm(m.get("grandparentTitle", "")) == _norm(artist) \
               and _norm(m.get("title", "")) == _norm(track):
                hit = m
                break
        if hit is None:
            missing += 1
            missing_list.append(f"{artist} — {track}  [album: {album}]")
            continue
        if hit.get("userRating") is not None:
            already += 1
            continue
        if not dry_run:
            qs = urllib.parse.urlencode({
                "identifier": "com.plexapp.plugins.library", "key": hit["ratingKey"],
                "rating": "10", "X-Plex-Token": _plex_token()})
            req = urllib.request.Request(f"{PLEX}/:/rate?{qs}", method="PUT")
            with urllib.request.urlopen(req, timeout=30):
                pass
        starred += 1
        print(f"{'WOULD STAR' if dry_run else 'RATED ★★★★★'}: {artist} — {track}")

    (HERE / ".apple-music-favorites-not-in-plex.txt").write_text(
        "\n".join(missing_list) + "\n" if missing_list else "")
    print(f"\ndone: {starred} {'would be ' if dry_run else ''}starred, "
          f"{already} already had a rating (untouched), {missing} not in Plex "
          f"(list: .apple-music-favorites-not-in-plex.txt)")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backfill", type=int, metavar="N",
                    help="request up to N albums from the existing-favorites baseline")
    ap.add_argument("--star-backfill", action="store_true",
                    help="5-star every Apple Music track-favorite that exists in Plex")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --star-backfill: report without rating")
    args = ap.parse_args()
    if args.star_backfill:
        star_backfill(dry_run=args.dry_run)
    elif args.backfill:
        backfill(args.backfill)
    else:
        main()
