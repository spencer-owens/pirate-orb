#!/bin/bash
# Organize Bang Casting collection to Leviathan/XXX/Bang Casting/
# Renames files to: Bang Casting - YYYY-MM-DD - Performer Name.ext
# Consolidates from hal9000 loose folders + main BANG! Casting dir

set -euo pipefail

DEST="/Volumes/Leviathan/XXX/Bang Casting"
SRC_MAIN="/Volumes/hal9000/XXX/BANG! Casting"
DRY_RUN="${1:-}"

mkdir -p "$DEST"

moved=0
skipped=0
dupes=0

rename_and_move() {
    local src="$1"
    local basename=$(basename "$src")
    local ext="${basename##*.}"
    ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
    
    # Parse scene-style filenames: Bang.Casting.YY.MM.DD.Performer.Name.XXX...
    # or: bangcast.YY.MM.DD.performer.name.ext
    local cleaned=$(echo "$basename" | sed -E '
        s/^[Bb]ang\.?[Cc]ast(ing)?\.//
        s/\.XXX.*//i
        s/\.[0-9]+p.*//i
        s/\.MP4.*//i
        s/\.SD.*//i
        s/\.XviD.*//i
        s/-Pornfuscated//i
    ')
    
    # Extract date parts (YY.MM.DD)
    local yy=$(echo "$cleaned" | cut -d. -f1)
    local mm=$(echo "$cleaned" | cut -d. -f2)
    local dd=$(echo "$cleaned" | cut -d. -f3)
    
    # Extract performer name (everything after the date), title case
    local performer=$(echo "$cleaned" | sed -E 's/^[0-9]+\.[0-9]+\.[0-9]+\.//' | sed 's/\./ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')
    
    # Build full year
    local year="20${yy}"
    
    # Build new filename
    local newname="Bang Casting - ${year}-${mm}-${dd} - ${performer}.${ext}"
    
    # Check for dupes
    if [ -f "$DEST/$newname" ]; then
        echo "  ⚠️  DUPE: $newname (skipping)"
        ((dupes++)) || true
        return
    fi
    
    if [ "$DRY_RUN" = "--dry-run" ]; then
        echo "  📦 $basename → $newname"
    else
        cp "$src" "$DEST/$newname"
        echo "  ✅ $newname"
    fi
    ((moved++)) || true
}

echo "=== Processing main BANG! Casting folder (45 files) ==="
for f in "$SRC_MAIN"/*.mp4; do
    [ -f "$f" ] && rename_and_move "$f"
done

echo ""
echo "=== Processing loose Bang Casting folders ==="

# Casey Calvert SD - skip, have 1080p
echo "  ⏭️  Skipping Casey Calvert SD (have 1080p version)"
((skipped++)) || true

# Rebel Lynn
f="/Volumes/hal9000/XXX/Bang Casting 16 05 27 Rebel Lynn XXX SD MP4-RARBG/Bang.Casting.16.05.27.Rebel.Lynn.XXX.SD.MP4-RARBG.mp4"
[ -f "$f" ] && rename_and_move "$f"

# Katerina Kay
f="/Volumes/hal9000/XXX/Bang Casting 16 06 20 Katerina Kay XXX SD MP4/Bang.Casting.16.06.20.Katerina.Kay.XXX.SD.MP4-RARBG.mp4"
[ -f "$f" ] && rename_and_move "$f"

# Alison Rey
f="/Volumes/hal9000/XXX/Bang Casting 16 11 25 Alison Rey XXX/bangcast.16.11.25.alison.rey.mp4"
[ -f "$f" ] && rename_and_move "$f"

# Lola Hunter
f="/Volumes/hal9000/XXX/newzNZB Bang Casting 16 12 03 Lola Hunter XXX/Bang.Casting.16.12.03.Lola.Hunter.XXX.XviD-newz[NZB].avi"
[ -f "$f" ] && rename_and_move "$f"

# Elektra Rose
f="/Volumes/hal9000/XXX/newzNZB Bang Casting 16 12 11 Elektra Rose XXX/Bang.Casting.16.12.11.Elektra.Rose.XXX.XviD-iPT.Team.avi"
[ -f "$f" ] && rename_and_move "$f"

# Naomi Alice - empty folder, skip
echo "  ⏭️  Skipping Naomi Alice (empty folder, no video file)"
((skipped++)) || true

echo ""
echo "=== Summary ==="
echo "  Moved/renamed: $moved"
echo "  Skipped: $skipped"
echo "  Duplicates: $dupes"

if [ "$DRY_RUN" = "--dry-run" ]; then
    echo ""
    echo "🏜️  DRY RUN — no files moved"
fi
