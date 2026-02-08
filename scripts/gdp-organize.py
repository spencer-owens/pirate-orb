#!/usr/bin/env python3
"""
GDP (GirlsDoPorn) File Organizer
=================================
Consolidates GDP files from multiple source directories into a single organized
structure compatible with Whisparr's scene naming format.

Usage:
    python3 gdp-organize.py                  # Dry run (default)
    python3 gdp-organize.py --execute        # Actually move/rename files
    python3 gdp-organize.py --summary        # Print metadata summary only
    python3 gdp-organize.py --export-meta    # Export gdp-metadata.json only
"""

import argparse
import csv
import json
import os
import re
import shutil
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# === Configuration ===

SITERIP_DIR = "/Volumes/Raiju/downloads/GirlsDoPorn SiteRip 1-203 XXX"
KTR_DIR = "/Volumes/Raiju/downloads/GirlsDoPorn.XXX.720P.WMV.PACK-KTR [NO RAR]"
CSV_PATH = os.path.expanduser("~/.openclaw/workspace/memory/gdp-episode-list.csv")
DEST_DIR = "/Volumes/Raiju/downloads/GirlsDoPorn"
METADATA_JSON = os.path.join(os.path.dirname(__file__), "gdp-metadata.json")

# Whisparr scene folder format: scenes/{Studio Title}/{Scene Title} - {Release Date}
# Since we don't have release dates for most, we'll use a flat structure under the studio
WHISPARR_STUDIO = "Girls Do Porn"

# === Data Classes ===

@dataclass
class Episode:
    number: int
    name: str = ""
    special: str = ""
    cheater: str = ""
    have: bool = False
    bts: bool = False
    toys: bool = False
    # Populated from file scan
    files: list = field(default_factory=list)
    selected_file: Optional[str] = None
    age_from_filename: Optional[int] = None

@dataclass
class SourceFile:
    path: str
    source: str  # "siterip" or "ktr"
    episode_num: int
    extension: str
    is_deleted_scene: bool = False
    is_internal: bool = False
    deleted_scene_num: Optional[int] = None
    age: Optional[int] = None
    tag: str = ""  # "Anal", "3-Some", etc.
    size_bytes: int = 0
    format_quality: str = ""  # "720p" etc.


def parse_csv(csv_path: str) -> dict[int, Episode]:
    """Parse the GDP episode list CSV into a dict of episodes keyed by number."""
    episodes = {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                num = int(row["EPISODE"])
            except (ValueError, KeyError):
                continue
            ep = Episode(
                number=num,
                name=row.get("NAME", "").strip(),
                special=row.get("SPECIAL", "").strip(),
                cheater=row.get("CHEATER", "").strip(),
                have=row.get("HAVE", "").strip().lower() == "x",
                bts=row.get("BTS", "").strip().lower() == "x",
                toys=row.get("Toys", "").strip().lower() == "x",
            )
            episodes[num] = ep
    return episodes


def scan_siterip(directory: str) -> list[SourceFile]:
    """Scan the SiteRip directory for episode files."""
    files = []
    if not os.path.isdir(directory):
        print(f"WARNING: SiteRip directory not found: {directory}", file=sys.stderr)
        return files

    pattern = re.compile(r"^E(\d+)\s*(.*?)\.(wmv|mp4)$", re.IGNORECASE)
    for fname in os.listdir(directory):
        m = pattern.match(fname)
        if not m:
            continue
        ep_num = int(m.group(1))
        tag = m.group(2).strip()
        ext = m.group(3).lower()
        fpath = os.path.join(directory, fname)
        sf = SourceFile(
            path=fpath,
            source="siterip",
            episode_num=ep_num,
            extension=ext,
            tag=tag,
            size_bytes=os.path.getsize(fpath) if os.path.isfile(fpath) else 0,
        )
        files.append(sf)
    return files


def scan_ktr(directory: str) -> list[SourceFile]:
    """Scan the KTR pack directory for episode files."""
    files = []
    if not os.path.isdir(directory):
        print(f"WARNING: KTR directory not found: {directory}", file=sys.stderr)
        return files

    # Deleted scenes: GirlsDoPorn.E01.Deleted.Scenes.18.Years.Old.XXX.720p.MP4-KTR.mp4
    deleted_pattern = re.compile(
        r"^GirlsDoPorn\.E(\d+)\.Deleted\.Scenes\.(\d+)\.Years?\.Old\.XXX\.(\d+p)\.(WMV|MP4)-KTR\.(wmv|mp4)$",
        re.IGNORECASE,
    )
    # Regular: GirlsDoPorn.E157.21.Years.Old.XXX.720p.WMV-KTR.wmv
    # Internal: GirlsDoPorn.E310.19.Years.Old.XXX.INTERNAL.720p.MP4-KTR.mp4
    # READ.NFO: GirlsDoPorn.E335.19.Years.Old.XXX.READ.NFO.720p.MP4-KTR.mp4
    regular_pattern = re.compile(
        r"^GirlsDoPorn\.E(\d+)\.(\d+)(?:\.And\.\d+)?\.Years?\.Old\.XXX\."
        r"(?:READ\.NFO\.)?"
        r"(INTERNAL\.)?"
        r"(\d+p)\.(WMV|MP4)-KTR\.(wmv|mp4)$",
        re.IGNORECASE,
    )

    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)
        if not os.path.isfile(fpath):
            continue

        m = deleted_pattern.match(fname)
        if m:
            sf = SourceFile(
                path=fpath,
                source="ktr",
                episode_num=int(m.group(1)),
                extension=m.group(5).lower(),
                is_deleted_scene=True,
                deleted_scene_num=int(m.group(1)),
                age=int(m.group(2)),
                format_quality=m.group(3),
                size_bytes=os.path.getsize(fpath),
            )
            files.append(sf)
            continue

        m = regular_pattern.match(fname)
        if m:
            sf = SourceFile(
                path=fpath,
                source="ktr",
                episode_num=int(m.group(1)),
                extension=m.group(6).lower(),
                is_internal=bool(m.group(3)),
                age=int(m.group(2)),
                format_quality=m.group(4),
                size_bytes=os.path.getsize(fpath),
            )
            files.append(sf)
            continue

    return files


def select_best_file(source_files: list[SourceFile]) -> Optional[SourceFile]:
    """Given multiple source files for the same episode, pick the best one.
    
    Priority:
    1. Non-INTERNAL over INTERNAL
    2. MP4 over WMV (newer format)
    3. Larger file size (proxy for quality)
    4. SiteRip over KTR for episodes in both (SiteRip is more complete/original)
    """
    if not source_files:
        return None
    if len(source_files) == 1:
        return source_files[0]

    def score(sf: SourceFile) -> tuple:
        return (
            0 if sf.is_internal else 1,       # prefer non-internal
            1 if sf.extension == "mp4" else 0,  # prefer mp4
            sf.size_bytes,                      # prefer larger
            1 if sf.source == "siterip" else 0, # prefer siterip
        )

    return max(source_files, key=score)


def generate_filename(ep: Episode, sf: SourceFile) -> str:
    """Generate the target filename for an episode.
    
    Format: GirlsDoPorn - E001 - Jenny.wmv
    If no name: GirlsDoPorn - E001.wmv
    """
    num_str = f"E{ep.number:03d}"
    parts = [WHISPARR_STUDIO.replace(" ", ""), num_str]

    # Build display name
    display_name = ep.name
    if not display_name and sf.age:
        display_name = f"{sf.age} Years Old"

    if display_name:
        # Clean name for filesystem
        clean = re.sub(r'[<>:"/\\|?*]', "", display_name)
        clean = clean.strip()
        if clean:
            parts.append(clean)

    # Add special tag if present
    if ep.special:
        parts.append(f"({ep.special})")

    return " - ".join(parts[:3]) + (f" ({ep.special})" if ep.special and len(parts) <= 3 else "") + f".{sf.extension}"


def generate_nfo(ep: Episode, sf: SourceFile) -> dict:
    """Generate metadata dict for an episode."""
    meta = {
        "episode": ep.number,
        "title": f"{WHISPARR_STUDIO} - Episode {ep.number}",
        "studio": WHISPARR_STUDIO,
    }
    if ep.name:
        meta["performer"] = ep.name
        meta["title"] = f"{WHISPARR_STUDIO} - Episode {ep.number} - {ep.name}"
    if ep.special:
        meta["tags"] = [t.strip() for t in ep.special.split(",")]
    if ep.cheater:
        meta["cheater_type"] = ep.cheater
    if sf.age:
        meta["age"] = sf.age
    meta["has_bts"] = ep.bts
    meta["has_toys"] = ep.toys
    meta["source"] = sf.source
    meta["source_file"] = os.path.basename(sf.path)
    meta["format"] = sf.extension.upper()
    if sf.format_quality:
        meta["quality"] = sf.format_quality
    meta["size_bytes"] = sf.size_bytes
    return meta


def run(args):
    # 1. Parse CSV
    csv_path = getattr(args, 'csv', CSV_PATH)
    dest_dir = getattr(args, 'dest', DEST_DIR)
    episodes = parse_csv(csv_path)
    print(f"Loaded {len(episodes)} episodes from CSV")

    # 2. Scan files
    siterip_files = scan_siterip(SITERIP_DIR)
    ktr_files = scan_ktr(KTR_DIR)
    all_files = siterip_files + ktr_files
    print(f"Found {len(siterip_files)} SiteRip files, {len(ktr_files)} KTR files")

    # Separate deleted scenes
    deleted_scenes = [f for f in all_files if f.is_deleted_scene]
    regular_files = [f for f in all_files if not f.is_deleted_scene]

    # 3. Map files to episodes
    file_map: dict[int, list[SourceFile]] = {}
    for sf in regular_files:
        file_map.setdefault(sf.episode_num, []).append(sf)

    # Select best file per episode
    operations = []  # (source_path, dest_path, episode, source_file)
    metadata_entries = {}

    for ep_num in sorted(file_map.keys()):
        sf = select_best_file(file_map[ep_num])
        if not sf:
            continue

        # Get or create episode entry
        ep = episodes.get(ep_num, Episode(number=ep_num))
        if sf.age:
            ep.age_from_filename = sf.age

        filename = generate_filename(ep, sf)
        dest_path = os.path.join(dest_dir, filename)
        operations.append((sf.path, dest_path, ep, sf))
        metadata_entries[ep_num] = generate_nfo(ep, sf)

    # Handle deleted scenes
    deleted_dir = os.path.join(dest_dir, "Deleted Scenes")
    for sf in deleted_scenes:
        fname = f"GirlsDoPorn - Deleted Scene {sf.deleted_scene_num:02d} ({sf.age}yo).{sf.extension}"
        dest_path = os.path.join(deleted_dir, fname)
        ep = Episode(number=-sf.deleted_scene_num, name=f"Deleted Scene {sf.deleted_scene_num}")
        operations.append((sf.path, dest_path, ep, sf))

    # 4. Summary
    total_csv = len(episodes)
    have_file = len(file_map)
    csv_have = sum(1 for e in episodes.values() if e.have)
    specials = {}
    for e in episodes.values():
        if e.special:
            for tag in e.special.split(","):
                tag = tag.strip()
                if tag:
                    specials[tag] = specials.get(tag, 0) + 1

    # Coverage gaps
    all_ep_nums = set(range(0, max(episodes.keys()) + 1))
    have_nums = set(file_map.keys())
    csv_nums = set(episodes.keys())
    csv_have_nums = {n for n, e in episodes.items() if e.have}
    missing_from_files = sorted(csv_have_nums - have_nums)

    summary = {
        "total_episodes_in_csv": total_csv,
        "csv_marked_as_have": csv_have,
        "unique_episodes_with_files": have_file,
        "deleted_scenes": len(deleted_scenes),
        "overlap_episodes": sorted(set(sf.episode_num for sf in siterip_files) & set(sf.episode_num for sf in regular_files if sf.source == "ktr")),
        "siterip_range": f"E1-E203 ({len(siterip_files)} files)",
        "ktr_range": f"E157-E336 ({len([f for f in ktr_files if not f.is_deleted_scene])} episodes + {len(deleted_scenes)} deleted scenes)",
        "specials_breakdown": specials,
        "episodes_marked_have_but_no_file": missing_from_files[:50],
        "total_missing_count": len(missing_from_files),
        "coverage_pct": round(have_file / total_csv * 100, 1) if total_csv else 0,
    }

    if args.summary:
        print("\n=== GDP Metadata Summary ===")
        print(json.dumps(summary, indent=2))
        return

    if args.export_meta:
        full_meta = {"summary": summary, "episodes": metadata_entries}
        with open(METADATA_JSON, "w") as f:
            json.dump(full_meta, f, indent=2)
        print(f"Exported metadata to {METADATA_JSON}")
        return

    # 5. Execute or dry run
    print(f"\n{'=' * 60}")
    print(f"{'EXECUTING' if args.execute else 'DRY RUN'}: {len(operations)} file operations")
    print(f"Destination: {dest_dir}")
    print(f"{'=' * 60}\n")

    if not args.execute:
        # Also export metadata on dry run
        full_meta = {"summary": summary, "episodes": metadata_entries}
        with open(METADATA_JSON, "w") as f:
            json.dump(full_meta, f, indent=2)
        print(f"Exported metadata to {METADATA_JSON}")

    for src, dst, ep, sf in operations:
        rel_src = os.path.basename(src)
        rel_dst = os.path.relpath(dst, dest_dir)

        if args.execute:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst):
                print(f"  SKIP (exists): {rel_dst}")
                continue
            shutil.copy2(src, dst)

            # Write per-episode NFO JSON
            if ep.number >= 0:
                nfo_path = os.path.splitext(dst)[0] + ".nfo.json"
                meta = metadata_entries.get(ep.number, {})
                if meta:
                    with open(nfo_path, "w") as f:
                        json.dump(meta, f, indent=2)

            print(f"  COPY: {rel_src} -> {rel_dst}")
        else:
            action = "COPY"
            extras = []
            if sf.is_internal:
                extras.append("INTERNAL")
            if len(file_map.get(sf.episode_num, [])) > 1 and not sf.is_deleted_scene:
                dupes = len(file_map[sf.episode_num])
                extras.append(f"BEST of {dupes}")
            extra_str = f" [{', '.join(extras)}]" if extras else ""
            print(f"  {action}: {rel_src} -> {rel_dst}{extra_str}")

    # Print skipped duplicates in dry run
    if not args.execute:
        print(f"\n--- Duplicate Resolution ---")
        for ep_num in sorted(file_map.keys()):
            if len(file_map[ep_num]) > 1:
                best = select_best_file(file_map[ep_num])
                print(f"  E{ep_num:03d}: {len(file_map[ep_num])} files")
                for sf in file_map[ep_num]:
                    marker = " ✓ SELECTED" if sf is best else "   skipped"
                    print(f"    {marker}: {os.path.basename(sf.path)} ({sf.source}, {sf.size_bytes:,} bytes)")

    print(f"\n=== Summary ===")
    print(f"Episodes in CSV: {total_csv}")
    print(f"Episodes with files: {have_file}")
    print(f"Coverage: {summary['coverage_pct']}%")
    print(f"Deleted scenes: {len(deleted_scenes)}")
    print(f"Missing (have in CSV, no file): {len(missing_from_files)}")
    if specials:
        print(f"Specials: {', '.join(f'{k}({v})' for k,v in sorted(specials.items()))}")


def main():
    parser = argparse.ArgumentParser(description="GDP File Organizer")
    parser.add_argument("--execute", action="store_true", help="Actually copy/rename files (default: dry run)")
    parser.add_argument("--summary", action="store_true", help="Print metadata summary only")
    parser.add_argument("--export-meta", action="store_true", help="Export metadata JSON only")
    parser.add_argument("--dest", default=DEST_DIR, help=f"Destination directory (default: {DEST_DIR})")
    parser.add_argument("--csv", default=CSV_PATH, help=f"Episode list CSV path")
    args = parser.parse_args()

    run(args)


if __name__ == "__main__":
    main()
