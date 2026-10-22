"""The current season's postseason games, from Wikipedia's series articles.

Retrosheet publishes a season's game logs only after it ends, and the official MLB data feed may not be used on a public
site, so for years after Retrosheet's last full season this reads Wikipedia's "{year} ... Series" articles. Each game there
has a {{linescore}} box (date, park, inning-by-inning runs, hits, errors, pitchers, home-run hitters, crowd, weather) and a
short write-up. Used by build_days.py (stories) and retro_facts.py (numbers). Text is CC BY-SA (Wikipedia).

Regular-season games of the current year are not covered: Wikipedia has no per-game data for them.
"""
import datetime
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / ".cache" / "wiki_post"
UA = "ThisDayInBaseball/1.0 (personal history site; contact via GitHub mgbiuso)"
_RETRO = Path(__file__).resolve().parent.parent / ".cache" / "retrosheet"
# The last season whose full game logs Retrosheet has published: 2025, or later if a glYYYY.zip has been downloaded.
RETRO_LAST_YEAR = max([2025] + [int(p.stem[2:6]) for p in _RETRO.glob("gl20[0-9][0-9].zip")])
SERIES = ["American League Wild Card Series", "National League Wild Card Series", "American League Division Series",
          "National League Division Series", "American League Championship Series", "National League Championship Series", "World Series"]
MONTHS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                          "October", "November", "December"])}
# Abbreviations used in the linescore boxes -> Retrosheet team codes
ABBR = {"TB": "TBA", "LAD": "LAN", "NYY": "NYA", "NYM": "NYN", "CHC": "CHN", "CWS": "CHA", "KC": "KCA", "LAA": "ANA", "SD": "SDN",
        "SF": "SFN", "STL": "SLN", "WSH": "WAS", "AZ": "ARI", "ATH": "OAK"}


def fetch(title, max_age_hours=6):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (re.sub(r"\W+", "_", title) + ".txt")
    if f.exists() and time.time() - f.stat().st_mtime < max_age_hours * 3600:
        return f.read_text()
    url = ("https://en.wikipedia.org/w/api.php?action=parse&format=json&formatversion=2&prop=wikitext&redirects=1&page="
           + urllib.parse.quote(title))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=40) as r:
            text = json.load(r)["parse"]["wikitext"]
    except Exception:
        return f.read_text() if f.exists() else ""
    f.write_text(text)
    time.sleep(1.2)
    return text


def wclean(s):
    s = re.sub(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\[\[(?:File|Image):[^\]]*(?:\[\[[^\]]*\]\][^\]]*)*\]\]", "", s)
    for _ in range(4):
        s = re.sub(r"\{\{\s*convert\s*\|\s*([\d.,]+)\s*\|\s*([A-Za-z]+)[^{}]*\}\}", r"\1°\2", s, flags=re.I)
        s = re.sub(r"\{\{\s*nbsp\s*\}\}", " ", s, flags=re.I)
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def template_at(text, start):
    """The {{...}} template that begins at text[start], with nested braces handled."""
    depth, i = 0, start
    while i < len(text) - 1:
        if text.startswith("{{", i):
            depth += 1
            i += 2
        elif text.startswith("}}", i):
            depth -= 1
            i += 2
            if depth == 0:
                return text[start:i]
        else:
            i += 1
    return text[start:]


def params(box):
    body = box[2:-2]
    body = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", body)
    body = re.sub(r"\{\{\s*convert\s*\|\s*([\d.,]+)\s*\|\s*([A-Za-z]+)[^{}]*\}\}", r"\1°\2", body, flags=re.I)
    body = re.sub(r"\{\{\s*nbsp\s*\}\}", " ", body, flags=re.I)
    out = {}
    for m in re.finditer(r"\|\s*([A-Za-z0-9]+)\s*=\s*((?:(?!\|\s*[A-Za-z0-9]+\s*=).)*)", body, re.S):
        out[m.group(1)] = re.sub(r"\s+", " ", m.group(2)).strip().strip("'")
    return out


def to_int(s):
    try:
        return int(re.sub(r"[^\d]", "", s))
    except (TypeError, ValueError):
        return None


def parse_series(year, series):
    text = fetch(f"{year} {series}")
    games = []
    for m in re.finditer(r"\n===\s*Game (\d+)[^=\n]*===\s*\n(.*?)(?=\n==|\Z)", text, re.S):
        n, body = int(m.group(1)), m.group(2)
        i = body.lower().find("{{linescore")
        if i < 0:
            continue
        box = template_at(body, i)
        p = params(box)
        d = re.match(r"([A-Za-z]+) (\d{1,2}),? (\d{4})", p.get("Date", ""))
        rr, hr = to_int(p.get("RR", "")), to_int(p.get("HR", ""))
        if not d or d.group(1) not in MONTHS or rr is None or hr is None:
            continue  # not played yet
        if rr == 0 and hr == 0 and not to_int(p.get("Attendance", "")):
            continue  # a placeholder box for a game still to come
        road, home = p.get("Road", "").strip("'"), p.get("Home", "").strip("'")
        rl = [p.get(f"R{k}", "") for k in range(1, 16) if p.get(f"R{k}", "") != ""]
        hl = [p.get(f"H{k}", "") for k in range(1, 16) if p.get(f"H{k}", "") != ""]
        prose = [wclean(x) for x in body[i + len(box):].split("\n\n") if x.strip() and not x.strip().startswith(("{{", "[[File", "|"))]
        prose = [x for x in prose if len(x) > 60]
        loc = p.get("Location", "")
        games.append({
            "year": int(d.group(3)), "month": MONTHS[d.group(1)], "day": int(d.group(2)), "series": series, "game": n,
            "road": road, "home": home, "roadAbr": p.get("RoadAbr", ""), "homeAbr": p.get("HomeAbr", ""),
            "rr": rr, "hr": hr, "rh": to_int(p.get("RH", "")), "hh": to_int(p.get("HH", "")), "re": to_int(p.get("RE", "")), "he": to_int(p.get("HE", "")),
            "rl": ["x" if x.upper() == "X" else re.sub(r"[^\dx]", "", x.lower()) or "0" for x in rl],
            "hl": ["x" if x.upper() == "X" else re.sub(r"[^\dx]", "", x.lower()) or "0" for x in hl],
            "park": re.split(r"\s+in\s+", loc)[0].strip(), "crowd": to_int(p.get("Attendance", "")),
            "weather": p.get("Other", ""), "roadHR": [x.strip() for x in re.sub(r"\(\d+\)", "", p.get("RoadHR", "")).split(",") if x.strip()],
            "homeHR": [x.strip() for x in re.sub(r"\(\d+\)", "", p.get("HomeHR", "")).split(",") if x.strip()],
            "prose": prose[:2], "title": f"{year} {series}",
        })
    return games


def games_for(month, day, year=None):
    """Postseason games of the post-Retrosheet years on this date (never later than today)."""
    today = datetime.date.today()
    out = []
    for y in range(RETRO_LAST_YEAR + 1, today.year + 1):
        if year and y != year:
            continue
        if (y, month, day) > (today.year, today.month, today.day):
            continue
        for s in SERIES:
            for g in parse_series(y, s):
                if g["month"] == month and g["day"] == day and g["year"] == y:
                    out.append(g)
    return out


def sentences(text, limit):
    out = ""
    for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
        if len(out) + len(s) > limit and out:
            break
        out = f"{out} {s}".strip()
    return out


def story_rows(month, day):
    """Story rows for build_days: one per game, shaped like the other sources' rows."""
    rows = []
    for g in games_for(month, day):
        if g["rr"] == g["hr"]:
            continue
        win, lose = (g["road"], g["home"]) if g["rr"] > g["hr"] else (g["home"], g["road"])
        ws, ls = max(g["rr"], g["hr"]), min(g["rr"], g["hr"])
        where = f" at {g['park']}" if g["park"] else ""
        lead = f"In Game {g['game']} of the {g['year']} {g['series']}{where}, {win} beat {lose} {ws}–{ls}."
        body = sentences(" ".join(g["prose"]), 330)
        rows.append({"src": "postseason", "kind": "event", "year": str(g["year"]), "text": f"{lead} {body}".strip(),
                     "links": [g["title"]], "about": g["title"]})
    return rows
