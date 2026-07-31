#!/usr/bin/env python3
"""
One-time fix for shop photos that got a phantom ".jpg" baked into the
filename before their real extension - a common result of Windows hiding
known file extensions while renaming (e.g. anand-chemist.jpg.jfif should
just be anand-chemist.jfif -> anand-chemist.jpg).

Run this from INSIDE your images/ folder:

    cd C:\\Users\\Aayush Desai\\Desktop\\Malviya2\\images
    python fix_images.py

It only touches files matching the broken pattern; anything already named
correctly is left alone.
"""
import re
from pathlib import Path

FOLDER = Path(__file__).parent

# name.jpg.<realext>  ->  name.<normalized ext>
DOUBLE_EXT = re.compile(r"^(.+)\.jpg\.(jpg|jpeg|png|webp|jfif)$", re.IGNORECASE)
# a lone .jfif with no phantom .jpg in front of it
BARE_JFIF = re.compile(r"^(.+)\.jfif$", re.IGNORECASE)

NORMALIZE = {"jpeg": "jpg", "jfif": "jpg"}

fixed = 0
skipped = 0

for f in sorted(FOLDER.iterdir()):
    if not f.is_file():
        continue

    m = DOUBLE_EXT.match(f.name)
    if m:
        base, real_ext = m.group(1), m.group(2).lower()
    else:
        m = BARE_JFIF.match(f.name)
        if m:
            base, real_ext = m.group(1), "jfif"
        else:
            continue

    new_ext = NORMALIZE.get(real_ext, real_ext)
    new_name = f"{base}.{new_ext}"
    new_path = f.parent / new_name

    if new_path.exists() and new_path != f:
        print(f"  ! skipped {f.name} -> {new_name} (target already exists)")
        skipped += 1
        continue

    f.rename(new_path)
    print(f"  {f.name}  ->  {new_name}")
    fixed += 1

print(f"\nDone. Fixed {fixed} file(s), skipped {skipped}.")
