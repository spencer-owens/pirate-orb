#!/usr/bin/env python3
"""Patch Threadfin's generated threadfin.xml with channel logos from xepg.json.
Run after Threadfin starts/regenerates its XMLTV."""
import json, re, gzip, shutil

XEPG = "/Users/spencer/projects/pirate-orb/threadfin/config/xepg.json"
XML = "/Users/spencer/projects/pirate-orb/threadfin/config/data/threadfin.xml"

with open(XEPG) as f:
    xepg = json.load(f)

id_to_logo = {}
name_to_logo = {}
for v in xepg.values():
    logo = v.get("tvg-logo", "")
    if logo:
        cid = v.get("x-channelID", "")
        name = v.get("x-name", "") or v.get("name", "")
        if cid: id_to_logo[cid] = logo
        if name: name_to_logo[name] = logo

with open(XML) as f:
    xml = f.read()

patched = 0
def replace_icon(match):
    global patched
    cid = match.group(1)
    name_m = re.search(r'<display-name>([^<]+)</display-name>', match.group(0))
    name = name_m.group(1) if name_m else ''
    logo = id_to_logo.get(cid, '') or name_to_logo.get(name, '')
    if logo and '<icon src=""></icon>' in match.group(0):
        patched += 1
        return match.group(0).replace('<icon src=""></icon>', f'<icon src="{logo}"></icon>')
    return match.group(0)

xml = re.sub(r'<channel id="(\d+)">(.*?)</channel>', replace_icon, xml, flags=re.DOTALL)

with open(XML, 'w') as f:
    f.write(xml)
with open(XML, 'rb') as f_in:
    with gzip.open(XML + '.gz', 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

print(f"Patched {patched} channel icons")
