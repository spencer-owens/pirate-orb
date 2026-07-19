#!/usr/bin/env python3
"""Raiju staging cleanup — reusable, with queue-protection.

Categories:
  A) qbit ghost entries (missingFiles): remove entry only, no data exists
  B) qbit stalled seeds: remove torrent + data ONLY IF no pending *arr queue
     import references the series/movie (LESSON Jul 2026: partially-imported
     season packs still need their staging data — deleting it orphaned ~140
     queued episodes across ThunderCats/Rocket Power/TMNT/X-Men TAS)
  C) failed_imports graveyard: purge

Default is DRY RUN. Pass --execute to act.
"""
import argparse
import json
import os
import shutil
import subprocess
import urllib.request

RAIJU = "/Volumes/Raiju/downloads"
QBIT = "http://localhost:8085/api/v2"
SONARR = "http://localhost:8989/api/v3"
RADARR = "http://localhost:7878/api/v3"
HERE = os.path.dirname(os.path.abspath(__file__))


def _key(app):
    xml = open(os.path.join(HERE, "..", app, "config", "config.xml")).read()
    import re
    return re.search(r"<ApiKey>([^<]+)</ApiKey>", xml).group(1)


def arr_get(base, key, path):
    req = urllib.request.Request(f"{base}{path}", headers={"X-Api-Key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def qbit_req(path, data=None):
    cmd = f"curl -s -X POST '{QBIT}/{path}'" + (f" -d '{data}'" if data else "")
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def protected_paths():
    """Staging paths referenced by pending imports in Sonarr/Radarr queues."""
    paths = set()
    sk, rk = _key("sonarr"), _key("radarr")
    for base, key in ((SONARR, sk), (RADARR, rk)):
        q = arr_get(base, key, "/queue?pageSize=250")
        for r in q.get("records", []):
            op = r.get("outputPath") or ""
            if op:
                paths.add(op.replace("/downloads", RAIJU))
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true", help="act (default: dry run)")
    args = ap.parse_args()
    dry = not args.execute
    tag = "DRY-RUN " if dry else ""
    prot = protected_paths()
    print(f"{len(prot)} staging paths protected by pending queue imports")

    torrents = json.loads(subprocess.run(
        f"curl -s '{QBIT}/torrents/info'", shell=True, capture_output=True, text=True).stdout)

    ghosts = [t for t in torrents if t["state"] == "missingFiles"]
    if ghosts:
        print(f"{tag}A) removing {len(ghosts)} ghost entries (no data)")
        if not dry:
            qbit_req("torrents/delete",
                     f"hashes={'|'.join(t['hash'] for t in ghosts)}&deleteFiles=false")

    stalled = [t for t in torrents if t["state"] in ("stalledUP", "uploading", "queuedUP")]
    kill, keep = [], []
    for t in stalled:
        cp = t.get("content_path") or t.get("save_path", "")
        if any(p.startswith(cp) or cp.startswith(p) for p in prot if p):
            keep.append(t)
        else:
            kill.append(t)
    gb = sum(t["size"] for t in kill) / (1024**3)
    print(f"{tag}B) removing {len(kill)} stalled seeds + data ({gb:.0f}GB); "
          f"{len(keep)} PROTECTED by queue imports")
    for t in keep:
        print(f"   protected: {t['name'][:60]}")
    if not dry and kill:
        qbit_req("torrents/delete",
                 f"hashes={'|'.join(t['hash'] for t in kill)}&deleteFiles=true")

    fi = f"{RAIJU}/complete/soulseek/failed_imports"
    if os.path.isdir(fi):
        sz = subprocess.run(f"du -sg '{fi}'", shell=True, capture_output=True,
                            text=True).stdout.split()[0]
        print(f"{tag}C) purging failed_imports ({sz}GB)")
        if not dry:
            shutil.rmtree(fi)
            os.makedirs(fi, exist_ok=True)

    if dry:
        print("\ndry run complete — re-run with --execute to act")


if __name__ == "__main__":
    main()
