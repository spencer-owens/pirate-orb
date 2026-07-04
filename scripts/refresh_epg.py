#!/usr/bin/env python3
"""Refresh IPTV EPG data from Xtreme HD provider and deploy to Threadfin."""
import xml.etree.ElementTree as ET
import urllib.request
import re
import os
import shutil
from datetime import datetime

# Credentials come from the environment (or repo .env, which is gitignored):
#   IPTV_USER, IPTV_PASS, PLEX_TOKEN (+ optional IPTV_HOST, PLEX_DVR_ID)
def _load_env():
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_file):
        for line in open(env_file):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
_load_env()

def _require(name):
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"Missing env var {name} (set it in the repo .env)")
    return v

IPTV_HOST = os.environ.get("IPTV_HOST", "http://xtremehd.cc")
EPG_URL = f"{IPTV_HOST}/xmltv.php?username={_require('IPTV_USER')}&password={_require('IPTV_PASS')}"
PLEX_TOKEN = _require("PLEX_TOKEN")
PLEX_DVR_URL = f"http://127.0.0.1:32400/livetv/dvrs/{os.environ.get('PLEX_DVR_ID', '29')}"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT = os.path.join(REPO, "threadfin/config/data/minimal_epg.xml")
XEPG = os.path.join(REPO, "threadfin/config/xepg.json")

def get_channel_numbers():
    """EPG id -> channel number, from Threadfin's xepg.json."""
    import json
    try:
        d = json.load(open(XEPG))
        return {v['x-mapping']: v['tvg-chno'] for v in d.values()
                if v.get('x-mapping') and v.get('tvg-chno')}
    except Exception as e:
        print(f"  (no channel numbers: {e})")
        return {}

def get_our_epg_ids():
    """Get channel EPG IDs from Plex DVR config (stripping any NNN. sort prefix)."""
    resp = urllib.request.urlopen(f"{PLEX_DVR_URL}?X-Plex-Token={PLEX_TOKEN}")
    data = resp.read().decode()
    keys = re.findall(r'channelKey="([^"]+)"', data)
    return set(re.sub(r'^\d{3}\.', '', k) for k in keys if not k.startswith('id-'))

def get_existing_icons():
    """Get channel icons from existing EPG (keys are base ids, prefix stripped)."""
    if not os.path.exists(OUTPUT):
        return {}
    tree = ET.parse(OUTPUT)
    icons = {}
    for ch in tree.getroot().findall('channel'):
        icon = ch.find('icon')
        if icon is not None:
            base = re.sub(r'^\d{3}\.', '', ch.get('id', ''))
            icons[base] = icon.get('src', '')
    return icons

def main():
    print(f"[{datetime.now().isoformat()}] Refreshing EPG...")
    
    our_ids = get_our_epg_ids()
    print(f"  {len(our_ids)} channel IDs from Plex")
    
    icons = get_existing_icons()
    print(f"  {len(icons)} existing channel icons")

    chnos = get_channel_numbers()
    print(f"  {len(chnos)} channel numbers from Threadfin")
    
    # Download fresh EPG
    print("  Downloading fresh EPG from provider...")
    tmp = "/tmp/fresh_epg.xml"
    urllib.request.urlretrieve(EPG_URL, tmp)
    size_mb = os.path.getsize(tmp) / 1024 / 1024
    print(f"  Downloaded: {size_mb:.1f} MB")
    
    # Parse and filter
    tree = ET.parse(tmp)
    root = tree.getroot()
    
    new_root = ET.Element('tv')
    new_root.set('generator-info-name', 'iptv-fix')
    
    # Deduplicate channels. Rewrite ids to NNN.baseid so Plex's alphabetical
    # guide sort follows our channel numbers (zero-padded => numeric order).
    seen = set()
    ch_count = 0
    for ch in root.findall('channel'):
        cid = ch.get('id', '')
        if cid in our_ids and cid not in seen:
            seen.add(cid)
            if cid in icons:
                icon = ch.find('icon')
                if icon is None:
                    icon = ET.SubElement(ch, 'icon')
                icon.set('src', icons[cid])
            if cid in chnos:
                ch.set('id', f"{int(chnos[cid]):03d}.{cid}")
            # DO NOT add/reorder channel child elements — Plex's XMLTV parser is
            # DTD-strict (display-name+ then icon; no <lcn>). Violations empty the guide.
            new_root.append(ch)
            ch_count += 1
    
    # Deduplicate programmes (channel attr must match the rewritten ids)
    id_rewrite = {cid: f"{int(chnos[cid]):03d}.{cid}" for cid in seen if cid in chnos}
    seen_progs = set()
    prog_count = 0
    for prog in root.findall('programme'):
        ch = prog.get('channel', '')
        if ch in our_ids:
            key = (ch, prog.get('start', ''))
            if key not in seen_progs:
                seen_progs.add(key)
                if ch in id_rewrite:
                    prog.set('channel', id_rewrite[ch])
                new_root.append(prog)
                prog_count += 1
    
    print(f"  Filtered: {ch_count} channels, {prog_count} programmes")
    
    # Write
    new_tree = ET.ElementTree(new_root)
    ET.indent(new_tree, space='  ')
    new_tree.write(OUTPUT, encoding='UTF-8', xml_declaration=True)
    print(f"  Written: {os.path.getsize(OUTPUT)/1024:.0f} KB")
    
    # Trigger Plex guide reload
    req = urllib.request.Request(
        f"{PLEX_DVR_URL}/reloadGuide?X-Plex-Token={PLEX_TOKEN}",
        method='POST'
    )
    resp = urllib.request.urlopen(req)
    print(f"  Plex guide reload: {resp.status}")
    
    # Cleanup
    os.remove(tmp)
    print("  Done!")

if __name__ == '__main__':
    main()
