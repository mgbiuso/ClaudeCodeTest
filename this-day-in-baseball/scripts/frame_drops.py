#!/usr/bin/env python3
"""Frame every new drawing in Desktop/ballpark art/Drop drawings here, all at once.

Each file must be named after its park as written on the park list (for example "Polo Grounds V.png").
For each new file this trims Gemini's border, repaints it in the site's ink and paper, and adds the park name,
city, years and a source line (taken from the first free photo found for that park). Results go to:
  images/ballparks/CODE.webp                       for the site
  Desktop/ballpark art/Finished/Park Name.webp     a copy to look at
Files already framed are skipped unless you pass --redo.
Usage: python3 scripts/frame_drops.py
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_park_photos as fp  # noqa: E402
import park_art as pa  # noqa: E402

TRIM = 0.014  # Gemini draws its own thin border; cut 1.4% off every edge so it does not fight our frame
FINISHED = fp.FOLDER / "Finished"


def source_line(cache, code, n=1):
    """Source credit from the n-th photo on the park list (Photo 1 unless the file name ends in 2, 3 or 4)."""
    photos = cache.get(code, {}).get("photos", [])
    if len(photos) < n:
        return "Drawn from a photograph, Wikimedia Commons"
    p = photos[n - 1]
    year = re.search(r"\b(1[89]\d\d|20\d\d)\b", p.get("date", ""))
    credit = p.get("credit", "")
    credit = credit if credit and len(credit) < 40 else "Wikimedia Commons"
    return f"Drawn from a {year.group(1)} photograph, {credit}" if year else f"Drawn from a photograph, {credit}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--redo", action="store_true", help="frame files again even if already framed")
    a = ap.parse_args()

    parks = fp.load_parks()
    by_name = {}
    for p in parks:
        by_name[fp.norm(p["name"])] = p
        by_name.setdefault(fp.norm(p["code"]), p)
    cache = json.loads(fp.CACHE.read_text(encoding="utf-8")) if fp.CACHE.exists() else {}
    FINISHED.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in fp.DROP.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")) if fp.DROP.exists() else []
    made = skipped = 0
    for f in files:
        park, n = by_name.get(fp.norm(f.stem)), 1
        if not park:  # "Polo Grounds V 2.png" means the drawing came from Photo 2 on the list
            m = re.match(r"(.*\S)\s+([2-4])$", f.stem)
            if m:
                park, n = by_name.get(fp.norm(m.group(1))), int(m.group(2))
        if not park:
            print(f"  ? {f.name}: no park by that name. Rename it exactly like the list (for example Polo Grounds V.png)")
            continue
        out = pa.OUT_DIR / f"{park['code']}.webp"
        if out.exists() and not a.redo:
            skipped += 1
            continue
        img = Image.open(f).convert("RGB")
        dx, dy = int(img.width * TRIM), int(img.height * TRIM)
        img = img.crop((dx, dy, img.width - dx, img.height - dy))
        framed = pa.paint(pa.lines_from_drawing(img))
        info = pa.park_info(park["code"])
        sub = " · ".join(x for x in (info["place"], info.get("years", "")) if x)
        pa.decorate(framed, pa.clean_title(park["name"]) if hasattr(pa, "clean_title") else fp.clean_name(park["name"]), sub, source_line(cache, park["code"], n))
        out.parent.mkdir(parents=True, exist_ok=True)
        framed.save(out, "WEBP", quality=72, method=6)
        shutil.copy(out, FINISHED / f"{park['name']}.webp")
        made += 1
        print(f"  framed {park['name']} -> images/ballparks/{out.name} ({out.stat().st_size // 1024} KB)")
    print(f"{made} new, {skipped} already done, {len(files) - made - skipped} need a rename")


if __name__ == "__main__":
    main()
