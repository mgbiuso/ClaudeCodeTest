#!/usr/bin/env python3
"""Find free photos of every ballpark and build a clickable checklist page.

For each park in the Lahman list (345 parks since 1871) this asks Wikimedia Commons for photos,
keeps only freely licensed ones (public domain first, Creative Commons as backups), and writes:
  .cache/park_photos.json        the answers, so reruns cost nothing (delete a park's entry to redo it)
  ~/Desktop/ballpark art/Park list.html   a plain running list you open in your browser

Polite to Wikimedia: one request at a time, a pause between requests, retries with waiting, cached results.
Usage:
  python3 scripts/find_park_photos.py --limit 5        try five parks first
  python3 scripts/find_park_photos.py                  all parks (about 10 minutes, safe to stop and rerun)
  python3 scripts/find_park_photos.py --page-only      rebuild the page from the cache, no internet
"""
import argparse
import csv
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAHMAN = ROOT / ".cache" / "lahman" / "Parks.csv"
RETRO = ROOT / ".cache" / "retrosheet" / "analysis" / "ballparks0.csv"
CACHE = ROOT / ".cache" / "park_photos.json"
FOLDER = Path.home() / "Desktop" / "ballpark art"
PAGE = FOLDER / "Park list.html"
DROP = FOLDER / "Drop drawings here"
PROMPT_FILE = ROOT / "art" / "ballparks" / "PROMPT.md"
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "this-day-in-baseball/1.0 (hobby baseball history site; reads Commons politely)"}
PAUSE = 1.0
KEEP = 4
BAD_FILE = re.compile(r"(logo|icon|flag|\bmap\b|seating|diagram|\bplan\b|symbol|signature|ticket|stamp|banner|\.svg$|\.gif$|\.tiff?$|\.pdf$|\.webm$|\.ogv$|\.ogg$)", re.I)
PD = re.compile(r"(public domain|^pd\b|pd-|cc0|no restrictions|no known)", re.I)
CC = re.compile(r"^cc[ -]by", re.I)
STOP = {"park", "field", "stadium", "grounds", "the", "of", "at", "new", "old", "ii", "iii", "iv", "v", "vi", "vii", "i"}


# MLB parks that Retrosheet has but the Lahman list lacks (found by checking Retrosheet's game records)
EXTRA_MLB = ("WAS08",)


def load_parks():
    dates, retro = {}, {}
    with open(RETRO, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            retro[r["site"]] = r
            dates[r["site"]] = (int(r["first_g"][:4]), int(r["last_g"][:4]), int(r["last_g"]) - int(r["first_g"]))
    parks = []
    with open(LAHMAN, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            d = dates.get(r["parkkey"])
            parks.append({
                "code": r["parkkey"], "name": r["parkname"], "alias": r["parkalias"],
                "city": r["city"], "state": r["state"], "country": r["country"],
                "first": d[0] if d else None, "last": d[1] if d else None,
                "oneoff": bool(d and d[0] == d[1] and d[2] < 200),
            })
    for code in EXTRA_MLB:
        r, d = retro[code], dates[code]
        parks.append({"code": code, "name": r["name"], "alias": "", "city": r["city"], "state": r["state"], "country": "US",
                      "first": d[0], "last": d[1], "oneoff": False})
    parks.sort(key=lambda p: (p["first"] or 9999, p["name"]))
    return parks


def clean_name(name):
    name = re.sub(r"\(.*?\)", "", name)
    return re.sub(r"\s+(I{1,3}|IV|V|VI{0,3})$", "", name.strip()).strip()


def ask(params):
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def search(query):
    data = ask({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 12, "gsrsearch": query,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 360,
        "iiextmetadatafilter": "LicenseShortName|Artist|DateTimeOriginal|ImageDescription",
    })
    return list((data.get("query") or {}).get("pages", {}).values())


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def norm(s):
    return " " + re.sub(r"[^a-z0-9]+", " ", s.lower()).strip() + " "


def pick(pages, park):
    # a photo must contain the park's whole name (or an alias) as a phrase: "Eastern Park" must not match "Eastern bluebird in Prospect Park"
    phrases = [norm(clean_name(n)) for n in [park["name"]] + [a for a in park["alias"].split(";") if a.strip()]]
    phrases = [p for p in phrases if len(p.strip()) > 3]
    city = norm(park["city"])
    out = []
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        title = p.get("title", "")
        meta = info.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        if BAD_FILE.search(title) or info.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
            continue
        tier = "pd" if PD.search(lic) else "cc" if CC.search(lic) else None
        if not tier:
            continue
        text = norm(title + " " + strip_tags((meta.get("ImageDescription", {}) or {}).get("value", "")))
        hit = sum(2 for ph in phrases if ph in norm(title)) + sum(1 for ph in phrases if ph in text)
        if hit == 0:
            continue  # the park's name is not in the file's name or description
        city_ok = city in text
        out.append({
            "city_ok": city_ok,
            "title": title.removeprefix("File:"),
            "page": info.get("descriptionurl", ""),
            "thumb": info.get("thumburl", ""),
            "w": info.get("width", 0), "h": info.get("height", 0),
            "license": lic, "tier": tier,
            "credit": strip_tags((meta.get("Artist", {}) or {}).get("value", ""))[:80],
            "date": strip_tags((meta.get("DateTimeOriginal", {}) or {}).get("value", ""))[:30],
            "score": hit + (3 if info.get("width", 0) >= 1000 else 0),
        })
    if any(r["city_ok"] for r in out):  # drop look-alikes from other cities when the right city is confirmed
        out = [r for r in out if r["city_ok"]]
    out.sort(key=lambda r: (not r["city_ok"], r["tier"] != "pd", -r["score"]))
    return out[:KEEP]


def find(park):
    place = park["city"]
    queries = [f'{clean_name(park["name"])} {place}']
    if park["alias"]:
        queries.append(f'{clean_name(park["alias"].split(";")[0])} {place}')
    for i, q in enumerate(queries):
        found = pick(search(q), park)
        if found or i == len(queries) - 1:
            return found
        time.sleep(PAUSE)
    return []


def links(park):
    q = urllib.parse.quote_plus(f'{clean_name(park["name"])} {park["city"]}')
    return {
        "commons": f"https://commons.wikimedia.org/w/index.php?search={q}&ns6=1&ns14=1",
        "loc": f"https://www.loc.gov/pictures/search/?q={q}",
        "wiki": f"https://en.wikipedia.org/w/index.php?search={q}",
    }


def done_codes(parks):
    """Parks that already have a finished drawing in the drop folder (file named after the park or its code)."""
    stems = set()
    if DROP.exists():
        stems = {norm(f.stem) for f in DROP.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")}
    return {p["code"] for p in parks if norm(p["code"]) in stems or norm(p["name"]) in stems or norm(clean_name(p["name"])) in stems}


def build_page(parks, cache):
    """A plain running list: one line per park, a photo link or two, a check mark when its drawing is in the drop folder."""
    done = done_codes(parks)
    esc = html.escape
    items = []
    for p in sorted(parks, key=lambda p: (norm(clean_name(p["name"])), p["first"] or 0)):
        yrs = "" if not p["first"] else (str(p["first"]) if p["first"] == p["last"] else f'{p["first"]} to {p["last"]}')
        where = ", ".join(x for x in (p["city"], yrs) if x)
        if p["code"] in done:
            items.append(f'<li class="done"><label><input type="checkbox" data-code="{esc(p["code"])}" checked> <b>{esc(p["name"])}</b> ({esc(where)}) framed and done</label></li>')
            continue
        shots = []
        for i, ph in enumerate(cache.get(p["code"], {}).get("photos", [])[:2], 1):
            note = ("" if ph["city_ok"] else " (check the city)") + (" (public domain)" if ph["tier"] == "pd" else " (needs credit, see page)")
            shots.append(f'<a href="{esc(ph["page"])}" target="_blank" rel="noopener">Photo {i}</a>{note}')
        if not shots:
            q = links(p)["commons"]
            shots.append(f'no photo found. <a href="{esc(q)}" target="_blank" rel="noopener">Search for one</a>')
        tag = " (one-time site)" if p["oneoff"] else ""
        items.append(f'<li><label><input type="checkbox" data-code="{esc(p["code"])}"> <b>{esc(p["name"])}</b></label> ({esc(where)}){tag}: {" or ".join(shots)}</li>')
    page = PAGE_TEMPLATE.replace("__ITEMS__", "\n".join(items)).replace("__DONE__", str(len(done))).replace("__TOTAL__", str(len(parks)))
    page = page.replace("__PROMPT__", esc(prompt_text()))
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(page, encoding="utf-8")


def prompt_text():
    if PROMPT_FILE.exists():
        m = re.search(r"```\n(Redraw.*?)```", PROMPT_FILE.read_text(encoding="utf-8"), re.S)
        if m:
            return m.group(1).strip()
    return ""


PAGE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ballpark park list</title>
<style>
body{max-width:820px;margin:24px auto;padding:0 16px;background:#e2dfd2;color:#0f1519;font:17px/1.5 Georgia,serif}
h1{font:700 28px "Arial Narrow",Arial,sans-serif;text-transform:uppercase;margin:0 0 4px}
ol,ul{padding-left:0;list-style:none}li{padding:6px 0;border-bottom:1px solid #b9b5a4}
input[type=checkbox]{width:18px;height:18px;vertical-align:-3px;margin-right:6px;cursor:pointer}li.ticked{color:#5a6166}li.ticked a{color:#5a6166}
a{color:#1f4e8c}.done{color:#5a6166}.box{background:#f1eee3;border:2px solid #0f1519;padding:10px 14px;margin:14px 0}
pre{white-space:pre-wrap;margin:6px 0 0;font:14px/1.4 Menlo,monospace}
</style></head><body>
<h1>Ballpark park list</h1>
<p><b>__DONE__ of __TOTAL__ done.</b> Click a photo link, download the photo, make the drawing in Gemini, then save it in the folder
<b>Drop drawings here</b>, named after the park exactly as written below (for example <b>Polo Grounds V.png</b>). Then tick the box. Ticks are saved in this browser.</p>
<div class="box"><b>The prompt to paste into Gemini</b><pre>__PROMPT__</pre></div>
<ul>
__ITEMS__
</ul>
<script>
let ticks = {};
try { ticks = JSON.parse(localStorage.getItem("ballparkTicks") || "{}"); } catch (e) { ticks = {}; }
document.querySelectorAll("input[data-code]").forEach((box) => {
  const li = box.closest("li"), code = box.dataset.code;
  if (ticks[code]) box.checked = true;
  li.classList.toggle("ticked", box.checked);
  box.addEventListener("change", () => {
    li.classList.toggle("ticked", box.checked);
    if (box.checked) ticks[code] = 1; else delete ticks[code];
    try { localStorage.setItem("ballparkTicks", JSON.stringify(ticks)); } catch (e) { /* the list still works */ }
  });
});
</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only search this many parks that are not cached yet")
    ap.add_argument("--only", default="", help="search just this park code, for example WAS08")
    ap.add_argument("--page-only", action="store_true", help="rebuild the page from the cache without asking Wikimedia")
    a = ap.parse_args()

    parks = load_parks()
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    if not a.page_only:
        todo = [p for p in parks if p["code"] not in cache and (not a.only or p["code"] == a.only)]
        if a.limit:
            todo = todo[: a.limit]
        print(f"{len(parks)} parks, {len(cache)} already searched, searching {len(todo)} now", flush=True)
        for i, p in enumerate(todo, 1):
            try:
                cache[p["code"]] = {"photos": find(p)}
            except Exception as e:  # keep going; this park is retried next run
                print(f"  {p['code']} {p['name']}: skipped ({e})", flush=True)
                continue
            CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
            n = len(cache[p["code"]]["photos"])
            print(f"  [{i}/{len(todo)}] {p['code']} {p['name']}: {n} photo(s)", flush=True)
            time.sleep(PAUSE)
    build_page(parks, cache)
    got = sum(1 for p in parks if cache.get(p["code"], {}).get("photos"))
    DROP.mkdir(parents=True, exist_ok=True)
    print(f"list: {PAGE}  ({got} of {len(parks)} parks have at least one free photo)")


if __name__ == "__main__":
    sys.exit(main())
