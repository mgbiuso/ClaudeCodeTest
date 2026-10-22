#!/usr/bin/env python3
"""Optional extras for each day file. Used by build_days.py and enrich_days.py.

1. Career lines (Lahman Baseball Database): a short "Career: .303 average, 121 home runs" line for the players in
   "Debuts and farewells" and for the baseball people in "In memoriam".
2. "What the papers said" (Library of Congress, Chronicling America): printed newspaper pages that mention baseball
   on this date in past years, shown as links to the Library's own page. Nothing is copied from the pages.

Rules this file follows
- Everything is optional. If a data file or a website is missing, the day is built exactly as it was before.
- enrich() never raises into the build. A problem prints one warning line and the day goes on without that extra.
- Websites are asked politely: one request at a time, a pause between requests, a plain User-Agent, results cached.

Commands
  python3 scripts/extras.py --fetch-lahman            download the Lahman files once into .cache/lahman/
  python3 scripts/extras.py --fetch-lahman --source ~/Downloads/lahman   use files you downloaded by hand (zip or folder)
  python3 scripts/extras.py --check                   try the real sources once and say what works
  python3 scripts/extras.py --selftest                run the built-in tests (no network, no real data touched)

Credits: Lahman Baseball Database (created by Sean Lahman, maintained by SABR); Library of Congress, Chronicling America.
"""
import argparse
import io
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAHMAN_DIR = ROOT / ".cache" / "lahman"
PAPERS_DIR = ROOT / "data" / "papers"
LAHMAN_FILES = ("People.csv", "Batting.csv", "Pitching.csv")
LAHMAN_URL = "https://github.com/chadwickbureau/baseballdatabank/archive/refs/heads/master.zip"
LOC_URL = "https://www.loc.gov/collections/chronicling-america/"
UA = {"User-Agent": "this-day-in-baseball/1.0 (mgbiuso@gmail.com)"}
PAUSE = 4.0                                      # seconds between Library of Congress requests
MAX_YEARS = 6                                    # newspaper searches per day
FIRST_PAPER_YEAR, LAST_PAPER_YEAR = 1860, 1963   # the years the Library's newspaper collection covers for baseball
SPREAD_YEARS = [1958, 1948, 1934, 1920, 1905, 1890]  # used to fill up when a day has few old stories
MIN_AB, MIN_IP = 500, 150                        # careers shorter than this get no line


# ---------- Lahman: career lines ----------

def fetch_lahman(source=None):
    """Save People.csv, Batting.csv and Pitching.csv into .cache/lahman/.
    `source` may be a zip file or a folder you downloaded by hand; without it the files come from GitHub."""
    LAHMAN_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(source).expanduser() if source else None
    if src and src.is_dir():
        def get(name):
            return next((p.read_bytes() for p in sorted(src.rglob(name))), None)
    else:
        if src:
            data = src.read_bytes()
        else:
            with urllib.request.urlopen(urllib.request.Request(LAHMAN_URL, headers=UA), timeout=180) as r:
                data = r.read()
        zf = zipfile.ZipFile(io.BytesIO(data))
        names = zf.namelist()

        def get(name):
            hits = sorted((m for m in names if m == name or m.endswith("/" + name)), key=lambda m: ("core" not in m, len(m)))
            return zf.read(hits[0]) if hits else None
    for name in LAHMAN_FILES:
        blob = get(name)
        if not blob:
            raise RuntimeError(f"{name} was not found in the Lahman download")
        (LAHMAN_DIR / name).write_bytes(blob)
        print(f"saved {name} ({len(blob):,} bytes)")


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def norm(name):
    """Lowercase letters only, no accents or Jr/Sr/II, so 'José Rijo' and 'Jose Rijo' match."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s)
    return re.sub(r"[^a-z]+", "", s)


def _rows(name):
    with open(LAHMAN_DIR / name, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


_LAHMAN = None
_TRIED = False


def load_lahman():
    """The lookup tables, or None when the Lahman files have not been downloaded (career lines are then skipped)."""
    global _LAHMAN, _TRIED
    if _TRIED:
        return _LAHMAN
    _TRIED = True
    if not all((LAHMAN_DIR / n).exists() for n in LAHMAN_FILES):
        print("  note: career lines skipped, the Lahman files are not downloaded (run: python3 scripts/extras.py --fetch-lahman)", file=sys.stderr)
        return None
    debut, final, death, death_year = {}, {}, {}, {}
    debut_y, final_y = {}, {}  # (name, year) fallbacks when the exact date differs (some last games are postseason games)
    for r in _rows("People.csv"):
        pid = r.get("playerID")
        name = norm(f"{r.get('nameFirst', '')} {r.get('nameLast', '')}")
        if not pid or not name:
            continue
        if r.get("debut"):
            debut.setdefault((name, r["debut"][:10]), []).append(pid)
            debut_y.setdefault((name, r["debut"][:4]), []).append(pid)
        if r.get("finalGame"):
            final.setdefault((name, r["finalGame"][:10]), []).append(pid)
            final_y.setdefault((name, r["finalGame"][:4]), []).append(pid)
        dy, dm, dd = _int(r.get("deathYear")), _int(r.get("deathMonth")), _int(r.get("deathDay"))
        if dy and dm and dd:
            death.setdefault((name, dy, dm, dd), []).append(pid)
        elif dy:  # no month and day on file: the year alone has to do
            death_year.setdefault((name, dy), []).append(pid)
    bat, pit, last = {}, {}, 0
    for r in _rows("Batting.csv"):
        a = bat.setdefault(r["playerID"], {"g": 0, "ab": 0, "h": 0, "hr": 0, "sb": 0, "last": 0})
        a["g"] += _int(r.get("G"))
        a["ab"] += _int(r.get("AB"))
        a["h"] += _int(r.get("H"))
        a["hr"] += _int(r.get("HR"))
        a["sb"] += _int(r.get("SB"))
        a["last"] = max(a["last"], _int(r.get("yearID")))
        last = max(last, _int(r.get("yearID")))
    for r in _rows("Pitching.csv"):
        a = pit.setdefault(r["playerID"], {"w": 0, "l": 0, "g": 0, "sv": 0, "outs": 0, "er": 0, "so": 0, "no_er": False, "last": 0})
        a["w"] += _int(r.get("W"))
        a["l"] += _int(r.get("L"))
        a["g"] += _int(r.get("G"))
        a["sv"] += _int(r.get("SV"))
        a["outs"] += _int(r.get("IPouts"))
        a["er"] += _int(r.get("ER"))
        a["so"] += _int(r.get("SO"))
        a["no_er"] = a["no_er"] or r.get("ER", "") == ""  # earned runs missing in some seasons: no ERA line
        a["last"] = max(a["last"], _int(r.get("yearID")))
        last = max(last, _int(r.get("yearID")))
    _LAHMAN = {"debut": debut, "final": final, "debut_y": debut_y, "final_y": final_y, "death": death, "death_year": death_year, "bat": bat, "pit": pit, "last": last}
    return _LAHMAN


def career_line(pid):
    """'Career: .303 average, 121 home runs' or '144-98, 3.45 ERA, 1,234 strikeouts', or None for short careers."""
    L = load_lahman()
    if not L or not pid:
        return None
    b, p = L["bat"].get(pid), L["pit"].get(pid)
    ip = p["outs"] / 3 if p else 0
    ab = b["ab"] if b else 0
    parts = []
    if p and ip >= MIN_IP and (not b or ab < 3 * ip or p["g"] * 2 >= b["g"]):
        parts.append(f"{p['w']}-{p['l']}")
        if not p["no_er"]:
            parts.append(f"{9 * p['er'] / ip:.2f} ERA")
        if p["so"] >= 100:
            parts.append(f"{p['so']:,} strikeouts")
        if p["sv"] >= 100:
            parts.append(f"{p['sv']} saves")
    elif b and ab >= MIN_AB:
        parts.append(f"{b['h'] / ab:.3f}".lstrip("0") + " average")
        if b["hr"] >= 20:
            parts.append(f"{b['hr']:,} home runs")
        if b["h"] >= 1000:
            parts.append(f"{b['h']:,} hits")
        if b["sb"] >= 200:
            parts.append(f"{b['sb']} stolen bases")
    if not parts:
        return None
    through = max((b or {}).get("last", 0), (p or {}).get("last", 0))
    tail = f" (through {through})" if through and through >= L["last"] else ""  # still active in the newest season on file
    return "Career: " + ", ".join(parts) + tail


def _only(hits):
    hits = list(dict.fromkeys(hits))
    return hits[0] if len(hits) == 1 else None  # two namesakes on the same date: better to show nothing


def person_for_date(name, kind, year, month, day):
    """Lahman playerID for a debut (kind='debut') or final game (kind='final') on exactly this date, matched by name."""
    L = load_lahman()
    n, y = norm(name), f"{_int(year):04d}"
    exact, by_year = ("debut", "debut_y") if kind == "debut" else ("final", "final_y")
    return _only(L[exact].get((n, f"{y}-{month:02d}-{day:02d}"), [])) or _only(L[by_year].get((n, y), []))


def person_for_death(name, year, month, day):
    L = load_lahman()
    n = norm(re.sub(r"\(.*?\)", "", name or ""))
    if not n:
        return None
    return _only(L["death"].get((n, year, month, day), [])) or _only(L["death_year"].get((n, year), []))


def add_careers(rec):
    """Put 'career' on debut and farewell entries and on obituary stories. Returns how many lines were added."""
    if not load_lahman():
        return 0
    month, day, added = rec["month"], rec["day"], 0
    people = rec.get("people") or {}
    for key, kind in (("debuts", "debut"), ("farewells", "final")):
        for it in people.get(key) or []:
            pid = person_for_date(it.get("name", ""), kind, it.get("year"), month, day)
            line = career_line(pid)
            if line:
                it["career"] = line
                added += 1
            else:
                it.pop("career", None)
    for st in rec.get("stories") or []:
        if st.get("kind") != "death":
            continue
        line = career_line(person_for_death(st.get("about") or "", _int(st.get("year")), month, day))
        if line:
            st["career"] = line
            added += 1
        else:
            st.pop("career", None)
    return added


# ---------- Library of Congress: "What the papers said" ----------

def _loc_get(url):
    """One polite request. Returns the parsed JSON, or None if the Library could not be reached (nothing is cached then)."""
    delay = 20
    for _ in range(3):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  the Library of Congress asked us to slow down (429); waiting {delay}s", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            return None
        except Exception:
            time.sleep(2)
    return None


TITLE = re.compile(r"^Image (\d+) of (.+), ([A-Z][a-z]+ \d{1,2}, \d{4})")


def _paper_item(res, year):
    """One search result -> {year, paper, page, url}, or None. Only links that stay on loc.gov are kept."""
    m = TITLE.match(res.get("title") or "")
    url = (res.get("url") or res.get("id") or "").replace("http://", "https://", 1)
    if not m or str(year) not in m.group(3) or not url.startswith("https://www.loc.gov/"):
        return None
    return {"year": year, "paper": m.group(2), "page": int(m.group(1)), "url": url}


def pick_years(rec):
    """Years to search: the years of the day's own stories (lead first) that fall in the newspaper era, then a spread."""
    years = []
    for st in rec.get("stories") or []:
        y = _int(st.get("year"))
        if FIRST_PAPER_YEAR <= y <= LAST_PAPER_YEAR and y not in years:
            years.append(y)
    for y in SPREAD_YEARS:
        if len(years) >= MAX_YEARS:
            break
        if y not in years:
            years.append(y)
    return years[:MAX_YEARS]


def papers_for_day(month, day, years):
    """Returns (items, complete). complete is False if the Library could not be reached partway."""
    items = []
    for y in years:
        d = _loc_get(f"{LOC_URL}?q=baseball&dates={y:04d}-{month:02d}-{day:02d}&fo=json&c=3")
        if d is None:
            return items, False
        for res in d.get("results") or (d.get("content") or {}).get("results") or []:
            it = _paper_item(res, y)
            if it:
                items.append(it)
                break
    return sorted(items, key=lambda i: -i["year"]), True


def add_papers(rec, fetch=False):
    """Use data/papers/MM-DD.json if it exists; with fetch=True, ask the Library when it does not. Returns the item count."""
    f = PAPERS_DIR / f"{rec['month']:02d}-{rec['day']:02d}.json"
    data = None
    if f.exists():
        try:
            data = json.loads(f.read_text())
        except ValueError:
            data = None
    if data is None and fetch:
        items, complete = papers_for_day(rec["month"], rec["day"], pick_years(rec))
        data = {"items": items}
        if complete:  # a half-finished search is used this time but not saved, so the next run tries again
            PAPERS_DIR.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    items = (data or {}).get("items") or []
    if items:
        rec["papers"] = items
    else:
        rec.pop("papers", None)
    return len(items)


# ---------- the one call the build makes ----------

def enrich(rec, fetch_papers=False):
    """Add the optional extras to one day record, in place. Never raises."""
    for label, fn in (("career lines", lambda: add_careers(rec)), ("newspaper pages", lambda: add_papers(rec, fetch_papers))):
        try:
            fn()
        except Exception as e:  # an extra must never break the build
            print(f"  warning: {label} skipped ({type(e).__name__}: {e})", file=sys.stderr)
    return rec


# ---------- checks ----------

def selftest():
    """Tests on made-up data in a temporary folder. Nothing real is read or written."""
    import tempfile
    global LAHMAN_DIR, PAPERS_DIR, _LAHMAN, _TRIED
    old = (LAHMAN_DIR, PAPERS_DIR, _LAHMAN, _TRIED)
    tmp = Path(tempfile.mkdtemp())
    try:
        LAHMAN_DIR, PAPERS_DIR, _LAHMAN, _TRIED = tmp / "lahman", tmp / "papers", None, False
        LAHMAN_DIR.mkdir()
        (LAHMAN_DIR / "People.csv").write_text(
            "playerID,deathYear,deathMonth,deathDay,nameFirst,nameLast,debut,finalGame\n"
            "testbat01,1999,10,20,Pat,Tester,1954-10-20,1970-04-01\n"
            "testpit01,,,,Sam,Hurler,1960-04-10,1975-10-20\n"
            "testsmall01,,,,Joe,Brief,1935-10-20,1935-10-21\n"
            "testold01,1930,,,Old,Timer,1900-04-01,1910-09-01\n"
            "testlate01,,,,Late,Comer,1990-04-01,1991-04-01\n"
            "testmis01,,,,Zed,Mismatch,1975-04-01,1980-09-30\n", encoding="utf-8-sig")
        (LAHMAN_DIR / "Batting.csv").write_text(
            "playerID,yearID,stint,G,AB,H,HR,SB\n"
            "testbat01,1960,1,150,600,180,25,10\n"
            "testbat01,1961,1,100,400,120,10,5\n"
            "testpit01,1970,1,30,40,5,0,0\n"
            "testsmall01,1935,1,3,8,2,0,0\n"
            "testold01,1905,1,700,700,175,5,20\n"
            "testlate01,1990,1,100,300,90,2,1\n"
            "testmis01,1980,1,140,600,150,2,3\n")
        (LAHMAN_DIR / "Pitching.csv").write_text(
            "playerID,yearID,stint,W,L,G,SV,IPouts,ER,SO\n"
            "testpit01,1969,1,10,5,30,0,600,70,120\n"
            "testpit01,1970,1,12,8,32,0,540,60,130\n")
        rec = {"month": 10, "day": 20,
               "people": {"debuts": [{"year": 1954, "name": "Pat Tester"}, {"year": 1935, "name": "Joe Brief"}],
                          "farewells": [{"year": 1975, "name": "Sam Hurler"}, {"year": 1980, "name": "Zed Mismatch"}]},
               "stories": [{"kind": "death", "year": "1999", "about": "Pat Tester (baseball)"},
                           {"kind": "death", "year": "1930", "about": "Old Timer"},
                           {"kind": "event", "year": "1990", "about": "Pat Tester"}]}
        enrich(rec)
        want = {
            "debut Pat": (rec["people"]["debuts"][0].get("career"), "Career: .300 average, 35 home runs"),
            "debut Joe (short career)": (rec["people"]["debuts"][1].get("career"), None),
            "farewell Sam": (rec["people"]["farewells"][0].get("career"), "Career: 22-13, 3.08 ERA, 250 strikeouts"),
            "farewell Zed (date differs, year matches)": (rec["people"]["farewells"][1].get("career"), "Career: .250 average"),
            "obit Pat": (rec["stories"][0].get("career"), "Career: .300 average, 35 home runs"),
            "obit Old (year only)": (rec["stories"][1].get("career"), "Career: .250 average"),
            "event story untouched": (rec["stories"][2].get("career"), None),
        }
        bad = [k for k, (got, exp) in want.items() if got != exp]
        for k, (got, exp) in want.items():
            print(("ok   " if got == exp else "FAIL ") + f"{k}: {got}")
        item = _paper_item({"title": "Image 3 of The Pacific commercial advertiser (Honolulu, Hawaiian Islands), October 20, 1905",
                            "url": "http://www.loc.gov/resource/sn85047084/1905-10-20/ed-1/?sp=3&q=baseball"}, 1905)
        checks = {
            "paper item parsed": item == {"year": 1905, "paper": "The Pacific commercial advertiser (Honolulu, Hawaiian Islands)", "page": 3,
                                          "url": "https://www.loc.gov/resource/sn85047084/1905-10-20/ed-1/?sp=3&q=baseball"},
            "paper off loc.gov rejected": _paper_item({"title": "Image 1 of X (Y), October 20, 1905", "url": "https://example.com/x"}, 1905) is None,
            "paper wrong year rejected": _paper_item({"title": "Image 1 of X (Y), October 20, 1906", "url": "https://www.loc.gov/x"}, 1905) is None,
            "years picked": pick_years({"stories": [{"year": "1990"}, {"year": "1951"}, {"year": "1923"}, {"year": "1923"}, {"year": "1888"}]})
                            == [1951, 1923, 1888, 1958, 1948, 1934],
        }
        PAPERS_DIR.mkdir()
        (PAPERS_DIR / "10-20.json").write_text(json.dumps({"items": [item]}))
        rec2 = {"month": 10, "day": 20, "stories": []}
        add_papers(rec2)
        checks["papers read from cache"] = rec2.get("papers") == [item]
        rec3 = {"stories": []}   # missing keys must not raise
        enrich(rec3)
        checks["enrich never raises"] = True
        for k, v in checks.items():
            print(("ok   " if v else "FAIL ") + k)
            if not v:
                bad.append(k)
        print("\nALL TESTS PASSED" if not bad else f"\n{len(bad)} TEST(S) FAILED: {bad}")
        return not bad
    finally:
        LAHMAN_DIR, PAPERS_DIR, _LAHMAN, _TRIED = old


def check():
    """Try the real sources once. Run this on your own computer: it needs the internet."""
    ok = True
    if load_lahman():
        for pid, want in (("aaronha01", "755 home runs"), ("johnswa01", "417-279")):
            line = career_line(pid) or ""
            good = want in line
            ok = ok and good
            print(("ok   " if good else "FAIL ") + f"Lahman {pid}: {line or 'no line'}")
    else:
        print("skip Lahman files are not downloaded yet. Run: python3 scripts/extras.py --fetch-lahman")
        ok = False
    d = _loc_get(f"{LOC_URL}?q=baseball&dates=1905-10-20&fo=json&c=3")
    item = None
    if d:
        for res in d.get("results") or (d.get("content") or {}).get("results") or []:
            item = _paper_item(res, 1905)
            if item:
                break
    print(("ok   " if item else "FAIL ") + f"Library of Congress: {item or 'no result (blocked, offline, or the reply changed shape)'}")
    return ok and bool(item)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fetch-lahman", action="store_true", help="download the Lahman files into .cache/lahman/")
    ap.add_argument("--source", help="with --fetch-lahman: a Lahman zip or folder you already downloaded")
    ap.add_argument("--force", action="store_true", help="with --fetch-lahman: download again even if the files are already here")
    ap.add_argument("--selftest", action="store_true", help="run the built-in tests")
    ap.add_argument("--check", action="store_true", help="try the real data sources once")
    a = ap.parse_args()
    if a.selftest:
        return 0 if selftest() else 1
    if a.fetch_lahman:
        if not a.force and all((LAHMAN_DIR / n).exists() for n in LAHMAN_FILES):
            print("The Lahman files are already downloaded (add --force to download them again).")
            return 0
        fetch_lahman(a.source)
        return 0
    if a.check:
        return 0 if check() else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
