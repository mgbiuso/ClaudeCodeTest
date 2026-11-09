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
import difflib
import json
import re
import shutil
import sys
import time
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_park_photos as fp  # noqa: E402
import park_art as pa  # noqa: E402

TRIM = 0.014  # Gemini draws its own thin border; cut 1.4% off every edge so it does not fight our frame
FINISHED = fp.FOLDER / "Finished"
EDITED = fp.FOLDER / "Edited sources"  # a touched-up copy of a drawing (same file name) is used instead of the original; the original is never changed
STATE = fp.ROOT / ".cache" / "frame_state.json"  # which file became which numbered picture


def source_line(cache, code, n=1):
    """Source credit from the n-th photo on the park list (Photo 1 unless the file name ends in 2, 3 or 4)."""
    photos = cache.get(code, {}).get("photos", [])
    if n is None or len(photos) < n:
        return "Drawn from a photograph, Wikimedia Commons"
    p = photos[n - 1]
    year = re.search(r"\b(1[89]\d\d|20\d\d)\b", p.get("date", ""))
    credit = p.get("credit", "")
    half = len(credit) // 2
    if half and credit[:half] == credit[half:]:  # Wikimedia sometimes stores the name twice
        credit = credit[:half]
    credit = credit if credit and len(credit) < 40 and "unknown" not in credit.lower() else "Wikimedia Commons"
    return f"Drawn from a {year.group(1)} photograph, {credit}" if year else f"Drawn from a photograph, {credit}"


ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}


def place_above_title(img):
    """Shrink the whole drawing (nothing cropped) to fit the space above the title box, centered, on paper-colored margins.
    That way the title box never covers the field."""
    top, bottom = 28, pa.H - 23 - pa.TITLE_H - 8
    art = ImageOps.contain(img, (pa.W - 56, bottom - top), Image.LANCZOS)
    canvas = Image.new("RGB", (pa.W, pa.H), img.getpixel((0, 0)))  # the drawing's own background color, so the margins blend in
    canvas.paste(art, ((pa.W - art.width) // 2, top))
    return canvas


def find_park(stem, parks, by_name):
    """Match a file name to a park. Returns (park, version, reason_if_not_found).
    The number you put at the end of a file name is the VERSION of the picture ("Astrodome III" is the third drawing of the Astrodome).
    A name that is exactly a park on the list wins first, so "Polo Grounds V" is that park, not version 5 of "Polo Grounds".
    Forgiving about capitals, spaces, "(1)" endings and small typos. Version is None when the name carries no number."""
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem).strip()          # "Polo Grounds V (1)" from a repeat download
    brackets = re.match(r"(.*?\S)\s*\(([^)]*)\)\s*$", stem)
    if brackets:  # "Athletic Park (Milwaukee, 1935 to 1949)", copied from the list: the first word in the brackets is the city
        base, city = brackets.group(1), fp.norm(brackets.group(2).split(",")[0])
        hits = [p for p in parks if fp.norm(p["city"]) == city and fp.norm(fp.clean_name(p["name"])) == fp.norm(fp.clean_name(base))]
        if len(hits) == 1:
            return hits[0], None, ""
        stem = base if hits else stem
    key = fp.norm(stem)

    def exact(k):
        hits = by_name.get(k, [])
        if len(hits) > 1:
            return None, "several parks share this name: " + ", ".join(f'{h["name"]} ({h["city"]})' for h in hits) + ". Add the city to the file name, for example " + f'"{hits[0]["name"]} {hits[0]["city"]}.png".'
        return (hits[0] if hits else None), ""

    def fuzzy(k):
        scored = sorted(((max(difflib.SequenceMatcher(None, k, x).ratio() for x in (fp.norm(p["name"]), fp.norm(fp.clean_name(p["name"])), fp.norm(p["name"] + " " + p["city"]))), p) for p in parks), key=lambda t: -t[0])
        if scored[0][0] >= 0.85 and scored[0][0] - scored[1][0] >= 0.06:
            return scored[0][1], ""
        close = ", ".join(f'{p["name"]} ({p["city"]})' for sc, p in scored[:2] if sc >= 0.6)
        return None, "I can't tell which park this is." + (f" Closest: {close}. Rename it to one of those." if close else " Rename it to a park name from the list.")

    park, why = exact(key)
    if park or why:
        return park, None, why
    for p in parks:  # name plus city, for example "Wrigley Field Chicago"
        if key == fp.norm(p["name"] + " " + p["city"]):
            return p, None, ""
    m = re.match(r"(.*\S)[\s_-]+(i{1,3}|iv|v|vi{0,3}|ix|x|\d{1,2})$", stem, re.I)
    if m:  # a number on the end: the version
        v = int(m.group(2)) if m.group(2).isdigit() else ROMAN[m.group(2).lower()]
        rest = fp.norm(m.group(1))
        park, why = exact(rest)
        if park or why:
            return park, v, why
        park, why2 = fuzzy(rest)
        if park:
            return park, v, ""
    park, why = fuzzy(key)
    return park, None, why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--redo", action="store_true", help="frame files again even if already framed")
    ap.add_argument("--only", default="", help="frame again just the files whose name contains this text")
    a = ap.parse_args()

    parks = fp.load_parks()
    by_name = {}
    for p in parks:
        by_name.setdefault(fp.norm(p["name"]), []).append(p)
        by_name.setdefault(fp.norm(p["code"]), []).append(p)
    cache = json.loads(fp.CACHE.read_text(encoding="utf-8")) if fp.CACHE.exists() else {}
    FINISHED.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in fp.DROP.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")) if fp.DROP.exists() else []
    made = skipped = 0
    unmatched = []
    # Several drawings of one stadium are all kept. Each file remembers its number (1, 2, 3...) so adding a file never reshuffles the others.
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    files.sort(key=lambda f: (f.stat().st_mtime, f.name))  # oldest first, so the first drawing of a park stays number 1
    for f in files:
        if time.time() - f.stat().st_mtime < 10:  # still being saved: the next run will pick it up
            continue
        park, version, why = find_park(f.stem, parks, by_name)
        if not park:
            print(f"  ? {f.name}: {why}")
            unmatched.append(f"{f.name}\n    {why}")
            continue
        if a.only and a.only.lower() not in f.name.lower():
            continue
        code = park["code"]
        entry = state.get(f.name)
        prev = dict(entry) if entry else {}
        force = False
        if version is not None:  # you numbered it: that number is the picture's number, whatever order files arrived in
            k = version
            owner = next((name for name, e in state.items() if e["code"] == code and e["variant"] == k and name != f.name and (fp.DROP / name).exists()), None)
            if owner:
                print(f"  ? {f.name}: {owner} is already version {k} of this park")
                unmatched.append(f"{f.name}\n    {owner} is already version {k} of this park. Give one of them a different number.")
                continue
            force = bool(entry) and entry["variant"] != k  # it was filed under another number before: frame it again
            state[f.name] = {"code": code, "variant": k}
        elif entry and entry["code"] == code:
            k = entry["variant"]
        else:
            used = {e["variant"] for e in state.values() if e["code"] == code}
            k = 1 if (not used and (pa.OUT_DIR / f"{code}.webp").exists()) else next(i for i in range(1, 99) if i not in used)
            legacy = k == 1 and (pa.OUT_DIR / f"{code}.webp").exists() and not used  # framed before this numbering existed
            state[f.name] = {"code": code, "variant": k}
            if legacy:
                skipped += 1
                continue
        out = pa.OUT_DIR / (f"{code}.webp" if k == 1 else f"{code}_{k}.webp")
        if out.exists() and not a.redo and not a.only and not force:
            skipped += 1
            continue
        img = Image.open(EDITED / f.name if (EDITED / f.name).exists() else f).convert("RGB")
        dx, dy = int(img.width * TRIM), int(img.height * TRIM)
        img = img.crop((dx, dy, img.width - dx, img.height - dy))
        framed = pa.paint(pa.lines_from_drawing(place_above_title(img)))
        info = pa.park_info(code)
        sub = " \u00b7 ".join(x for x in (info["place"], info.get("years", "")) if x)
        # Version 1 is credited to Photo 1 on the park list. Other versions get a plain credit, since they probably used another photo.
        photo = 1 if k == 1 else None
        # A credit line or title you fixed by hand is remembered in the state file and reused when pictures are framed again.
        title = prev.get("title") or fp.clean_name(park["name"])
        note = prev.get("note") or source_line(cache, code, photo)
        state[f.name] = {**state[f.name], "title": title, "note": note}
        pa.decorate(framed, title, sub, note)
        out.parent.mkdir(parents=True, exist_ok=True)
        framed.save(out, "WEBP", quality=72, method=6)
        label = park["name"] + (f" ({park['city']})" if len(by_name.get(fp.norm(park["name"]), [])) > 1 else "")  # shared names (two Athletic Parks) get the city
        shutil.copy(out, FINISHED / (f"{label}.webp" if k == 1 else f"{label} ({k}).webp"))
        made += 1
        print(f"  framed {park['name']} #{k} -> images/ballparks/{out.name} ({out.stat().st_size // 1024} KB)")
    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    note = fp.FOLDER / "Needs a better name.txt"  # a plain note you can open, since nobody is watching a screen
    note.write_text("These drawings in 'Drop drawings here' could not be matched to a park.\nRename each one to a park name from the list, and it will be framed on its own.\n\n" + "\n\n".join(unmatched) + "\n" if unmatched else "Nothing needs a new name right now.\n", encoding="utf-8")
    print(f"{made} new, {skipped} already done, {len(unmatched)} need a rename")


if __name__ == "__main__":
    main()
