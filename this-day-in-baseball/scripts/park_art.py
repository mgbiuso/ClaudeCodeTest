#!/usr/bin/env python3
"""Make one ballpark picture in the site's newsprint-drawing style, so every park matches.

Input is a line drawing of the park (made in a free AI tool from a public-domain photo, see
art/ballparks/PROMPT.md). The script repaints it in the site's exact ink and paper colors, adds paper
grain, a faint grid, a double frame and a title block (park name, city, years), and saves a small WebP.
With --photo it instead traces a real photo into lines itself (rougher, but needs no AI tool).

Usage:  python3 scripts/park_art.py NYC14 art/ballparks/source/NYC14.png --note "Drawn from a 1913 photograph, Library of Congress"
Writes: images/ballparks/NYC14.webp  (park codes come from Retrosheet/Lahman and never change when a park is renamed)
Needs:  Pillow (python3 -m pip install --user Pillow) and the park lists in .cache/ (lahman/Parks.csv, retrosheet/analysis/ballparks0.csv)
"""
import argparse
import csv
import datetime
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
LAHMAN = ROOT / ".cache" / "lahman" / "Parks.csv"
RETRO = ROOT / ".cache" / "retrosheet" / "analysis" / "ballparks0.csv"
OUT_DIR = ROOT / "images" / "ballparks"

W, H = 1200, 675               # 16:9, a little smaller than a header on a wide screen
TITLE_H = 92                   # height of the title box at the bottom
PAPER = (0xE2, 0xDF, 0xD2)     # --paper in style.css
INK = (0x0F, 0x15, 0x19)       # --ink in style.css
TITLE_FONT = "/System/Library/Fonts/Supplemental/Copperplate.ttc"
SMALL_FONT = "/System/Library/Fonts/Supplemental/Courier New.ttf"


def park_info(code):
    """Name, place and years for a park code, from the cached Lahman and Retrosheet lists."""
    info = {}
    with open(LAHMAN, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["parkkey"] == code:
                info = {"name": r["parkname"], "place": f"{r['city']}, {r['state']}"}
    if not info:  # a few MLB parks are in Retrosheet's list but not Lahman's
        with open(RETRO, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["site"] == code and r["name"]:
                    info = {"name": r["name"], "place": f"{r['city']}, {r['state']}"}
    if not info:
        sys.exit(f"Park code {code} is not in {LAHMAN.name}. Check the spelling (for example NYC14).")
    with open(RETRO, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["site"] == code:
                first, last = int(r["first_g"][:4]), int(r["last_g"][:4])
                info["years"] = f"Since {first}" if last >= datetime.date.today().year - 1 else f"{first} to {last}"
    return info


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:  # not on a Mac: use Pillow's own font so the script still works
        return ImageFont.load_default(size)


def lines_from_drawing(img, cut=200):
    """A line drawing in any colors to dark-lines-on-white. Works for white-on-blue drawings too."""
    g = ImageOps.autocontrast(ImageOps.fit(img, (W, H), Image.LANCZOS).convert("L"), cutoff=1)
    if sum(g.resize((40, 22)).getdata()) / (40 * 22) < 128:  # mostly dark: lines are light, so flip it
        g = ImageOps.invert(g)
    return g.point(lambda v: 255 if v >= cut else int(255 * (v / cut) ** 2))


def lines_from_photo(photo, median=3, radius=10, cut=225):
    """Trace a photo into pencil-like lines ("color dodge"). Done at double size, then shrunk, for thin lines."""
    g = ImageOps.autocontrast(ImageOps.fit(photo, (W * 2, H * 2), Image.LANCZOS).convert("L"), cutoff=1)
    g = g.filter(ImageFilter.MedianFilter(median))  # calms crowds and film grain
    blur = ImageOps.invert(g).filter(ImageFilter.GaussianBlur(radius))
    out = Image.new("L", g.size)
    gp, bp, op = g.load(), blur.load(), out.load()
    for y in range(g.height):
        for x in range(g.width):
            b = bp[x, y]
            op[x, y] = 255 if b == 255 else min(255, gp[x, y] * 255 // (255 - b))
    out = out.point(lambda v: 255 if v >= cut else int(255 * (v / cut) ** 2))
    return out.resize((W, H), Image.LANCZOS)


def paint(lines):
    """Dark-lines image to ink on paper, with a little grain."""
    img = Image.composite(Image.new("RGB", (W, H), INK), Image.new("RGB", (W, H), PAPER), ImageOps.invert(lines))
    noise = Image.effect_noise((W, H), 6).convert("RGB")
    return ImageChops.add(img, noise, scale=1.0, offset=-128)  # noise is centered on 128


def decorate(img, title, sub, note):
    d = ImageDraw.Draw(img, "RGBA")
    faint = INK + (22,)
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=faint, width=1)
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=faint, width=1)
    d.rectangle([14, 14, W - 15, H - 15], outline=INK, width=2)
    d.rectangle([22, 22, W - 23, H - 23], outline=INK, width=1)
    bh = TITLE_H
    d.rectangle([22, H - 23 - bh, W - 23, H - 23], fill=PAPER + (240,), outline=INK, width=1)
    d.text((W // 2, H - 23 - bh + 34), title.upper(), font=font(TITLE_FONT, 46), fill=INK, anchor="mm")
    d.text((W // 2, H - 23 - 22), sub.upper(), font=font(TITLE_FONT, 20), fill=INK, anchor="mm")
    if note:
        nf = font(SMALL_FONT, 14)
        nw = d.textlength(note.upper(), font=nf)
        d.rectangle([22, 22, 22 + nw + 24, 46], fill=PAPER + (240,), outline=INK, width=1)
        d.text((34, 34), note.upper(), font=nf, fill=INK, anchor="lm")


def main():
    ap = argparse.ArgumentParser(description="Make one ballpark picture in the site's newsprint style.")
    ap.add_argument("code", help="park code, for example NYC14 (Polo Grounds V)")
    ap.add_argument("src", help="the line drawing (or, with --photo, a photo)")
    ap.add_argument("--photo", action="store_true", help="src is a photo: trace it here instead of using an AI drawing")
    ap.add_argument("--crop", default="", help="crop src first: left,top,right,bottom in pixels")
    ap.add_argument("--title", default="", help="name to print, if the list's name is not the one fans know")
    ap.add_argument("--note", default="", help="small credit line at top left, for example where the photo came from")
    ap.add_argument("--out", default="", help="where to save (default images/ballparks/CODE.webp)")
    a = ap.parse_args()

    info = park_info(a.code)
    src = Image.open(a.src)
    if a.crop:
        src = src.crop(tuple(int(v) for v in a.crop.split(",")))
    img = paint(lines_from_photo(src) if a.photo else lines_from_drawing(src))
    sub = " · ".join(x for x in (info["place"], info.get("years", "")) if x)
    decorate(img, a.title or info["name"], sub, a.note)

    out = Path(a.out) if a.out else OUT_DIR / f"{a.code}.webp"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "WEBP", quality=72, method=6)
    print(f"saved {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
