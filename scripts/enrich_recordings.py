#!/usr/bin/env python3
"""Enrich Plex DVR recordings in the Recordings library.

Plex types every XMLTV airing as a "movie" (our provider EPG has no episode
metadata) and the Recordings library is agent=none by design, so recordings
land as bare titles with no date/summary — and repeat recordings of the same
guide title ("College Football", "FIFA World Cup 2026") collide on disk AND
in Plex's DVR scheduler, which dedupes grabs by guide identity.

This script fixes all of that after the fact, for each completed recording:
  1. renames  Title/Title.ts  ->  "Title - YYYY-MM-DD HHMM/<same>.ts"
     (kills collisions, frees the guide identity so the next same-title
      airing can be scheduled)
  2. matches the recording to its airing in threadfin's minimal_epg.xml
     (title + timeslot) and pushes the EPG description into the summary
  3. sets a pretty display title "Title — YYYY-MM-DD HH:MM" and
     originallyAvailableAt so sorting/год display work

Idempotent: already-enriched items (dated filename) are skipped. Silent when
there is nothing to do (cron-friendly). Python 3.9 compatible.

Usage: enrich_recordings.py [--dry-run]
"""
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_env():
    env_file = os.path.join(REPO, ".env")
    if os.path.exists(env_file):
        for line in open(env_file):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


_load_env()
TOKEN = os.environ.get("PLEX_TOKEN")
if not TOKEN:
    raise SystemExit("Missing env var PLEX_TOKEN (set it in the repo .env)")

PLEX = "http://127.0.0.1:32400"
SECTION = "8"  # Recordings library
EPG_FILE = os.path.join(REPO, "threadfin/config/data/minimal_epg.xml")
ENRICHED_RE = re.compile(r" - \d{4}-\d{2}-\d{2} \d{4}$")
DRY_RUN = "--dry-run" in sys.argv


def api(path, method="GET", **params):
    params["X-Plex-Token"] = TOKEN
    url = "%s%s?%s" % (PLEX, path, urllib.parse.urlencode(params))
    req = urllib.request.Request(url, method=method, headers={"Accept": "application/json"})
    resp = urllib.request.urlopen(req, timeout=30)
    body = resp.read()
    if body and "json" in (resp.headers.get("Content-Type") or ""):
        return json.loads(body)
    return None


def utc_ts(xmltv_time):
    """'20260705200000 +0000' -> unix ts"""
    return datetime.strptime(xmltv_time.split()[0] + " +0000", "%Y%m%d%H%M%S %z").timestamp()


def load_epg():
    """[(title, start_ts, stop_ts, desc, channel_display)]"""
    if not os.path.exists(EPG_FILE):
        return []
    root = ET.parse(EPG_FILE).getroot()
    names = {}
    for ch in root.findall("channel"):
        dn = ch.find("display-name")
        names[ch.get("id", "")] = dn.text if dn is not None and dn.text else ch.get("id", "")
    progs = []
    for p in root.findall("programme"):
        try:
            progs.append((
                (p.findtext("title") or "").strip(),
                utc_ts(p.get("start", "")),
                utc_ts(p.get("stop", "")),
                (p.findtext("desc") or "").strip(),
                names.get(p.get("channel", ""), p.get("channel", "")),
            ))
        except (ValueError, IndexError):
            continue
    return progs


def match_airing(progs, title, rec_start, rec_end):
    """Best EPG programme with the same title overlapping the recording window."""
    best, best_overlap = None, 0
    for (t, start, stop, desc, ch) in progs:
        if t != title:
            continue
        overlap = min(rec_end, stop) - max(rec_start, start)
        if overlap > best_overlap:
            best, best_overlap = (start, stop, desc, ch), overlap
    return best if best_overlap > 300 else None  # >5 min overlap required


def round_to_half_hour(ts):
    dt = datetime.fromtimestamp(ts)
    minutes = dt.hour * 60 + dt.minute
    rounded = int(round(minutes / 30.0)) * 30
    return dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=rounded)


def wait_for_item(new_file, tries=24, delay=5):
    for _ in range(tries):
        d = api("/library/sections/%s/all" % SECTION) or {"MediaContainer": {}}
        for md in d["MediaContainer"].get("Metadata", []):
            for media in md.get("Media", []):
                for part in media.get("Part", []):
                    if part.get("file") == new_file:
                        return md["ratingKey"]
        time.sleep(delay)
    return None


def main():
    d = api("/library/sections/%s/all" % SECTION) or {"MediaContainer": {}}
    items = d["MediaContainer"].get("Metadata", [])
    todo = []
    for md in items:
        try:
            part = md["Media"][0]["Part"][0]
        except (KeyError, IndexError):
            continue
        f = part.get("file", "")
        base = os.path.splitext(os.path.basename(f))[0]
        if not f or "/.grab/" in f or ENRICHED_RE.search(base):
            continue
        if not os.path.exists(f):
            continue  # mid-move or stale; next run
        todo.append((md, f))

    if not todo:
        return  # silent — nothing to enrich

    progs = load_epg()
    for md, f in todo:
        title = md.get("title", os.path.splitext(os.path.basename(f))[0])
        duration_s = (md["Media"][0].get("duration") or 0) / 1000.0
        end_ts = os.path.getmtime(f)
        start_ts = end_ts - duration_s if duration_s else end_ts

        airing = match_airing(progs, title, start_ts, end_ts)
        if airing:
            a_start, a_stop, desc, channel = airing
            start_dt = datetime.fromtimestamp(a_start)
            summary_bits = [desc] if desc else []
            summary_bits.append("Recorded %s, %s–%s from %s." % (
                start_dt.strftime("%a %b %-d %Y"),
                start_dt.strftime("%-I:%M %p"),
                datetime.fromtimestamp(a_stop).strftime("%-I:%M %p"),
                channel,
            ))
            summary = "\n".join(summary_bits)
        else:
            start_dt = round_to_half_hour(start_ts)
            summary = "Recorded %s at %s." % (
                start_dt.strftime("%a %b %-d %Y"), start_dt.strftime("%-I:%M %p"))

        safe_title = re.sub(r'[/:\\]', "-", title)
        new_base = "%s - %s" % (safe_title, start_dt.strftime("%Y-%m-%d %H%M"))
        pretty = "%s — %s %s" % (title, start_dt.strftime("%Y-%m-%d"), start_dt.strftime("%H:%M"))

        rec_root = os.path.dirname(os.path.dirname(f))
        new_dir = os.path.join(rec_root, new_base)
        new_file = os.path.join(new_dir, new_base + os.path.splitext(f)[1])

        if DRY_RUN:
            print("[dry-run] %s\n  -> %s\n  title: %s\n  date:  %s\n  summary: %s" % (
                f, new_file, pretty, start_dt.strftime("%Y-%m-%d"), summary.replace("\n", " | ")))
            continue

        old_dir = os.path.dirname(f)
        os.makedirs(new_dir, exist_ok=True)
        shutil.move(f, new_file)
        if old_dir != rec_root and not os.listdir(old_dir):
            os.rmdir(old_dir)

        api("/library/sections/%s/refresh" % SECTION)
        rk = wait_for_item(new_file)
        if not rk:
            print("⚠️ %s: renamed but new item never appeared in Plex — will retry metadata next run" % new_base)
            continue

        api("/library/sections/%s/all" % SECTION, method="PUT", **{
            "type": "1", "id": rk,
            "title.value": pretty, "title.locked": "1",
            "titleSort.value": new_base, "titleSort.locked": "1",
            "originallyAvailableAt.value": start_dt.strftime("%Y-%m-%d"),
            "originallyAvailableAt.locked": "1",
            "summary.value": summary, "summary.locked": "1",
        })
        print("✅ enriched: %s" % pretty)

    if not DRY_RUN:
        # drop the stale pre-rename entries whose files are gone
        api("/library/sections/%s/emptyTrash" % SECTION, method="PUT")


if __name__ == "__main__":
    main()
