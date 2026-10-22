"""Feats and milestones from Retrosheet's own lists (saved by fetch_retrosheet.py in .cache/retrosheet/lists/).

Parses, for every calendar date: career and season milestones (hits, home runs, steals, wins, strikeouts, saves), cycles,
four home runs in a row, hidden-ball tricks and forfeits. No network and no AI.

The information used here was obtained free of charge from and is copyrighted by Retrosheet.
"""
import collections
import html
import re
from pathlib import Path

LISTS = Path(__file__).resolve().parent.parent / ".cache" / "retrosheet" / "lists"
DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def read(name):
    return (LISTS / name).read_text(encoding="latin-1")


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        return f"{n:,}th"
    return f"{n:,}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


MILES = {
    "miles-h.htm": ("career hit", "hits in a season"),
    "miles-hr.htm": ("career home run", "home runs in a season"),
    "miles-sb.htm": ("career stolen base", "steals in a season"),
    "miles-w.htm": ("career win", "wins in a season"),
    "miles-k.htm": ("career strikeout", "strikeouts in a season"),
    "miles-sv.htm": ("career save", "saves in a season"),
}


def parse_milestones(feats, star_name):
    for fn, (career, season) in MILES.items():
        try:
            h = read(fn)
        except OSError:
            continue
        # tables are preceded by headings that end in "(Career)" or "(Season)"
        parts = re.split(r"(?i)<table", h)
        heading = "career"
        for i, part in enumerate(parts):
            before = clean(part[-400:]) if i == 0 else ""
            tail = clean(parts[i - 1][-600:]) if i else ""
            low = (tail + " " + before).lower()
            if "(season)" in low[-80:]:
                heading = "season"
            elif "(career)" in low[-80:]:
                heading = "career"
            if i == 0:
                continue
            thr = None
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", part, re.S | re.I):
                cells = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
                if not cells:
                    continue
                if cells[0].isdigit():
                    thr = int(cells[0])
                    continue
                m = next((DATE.fullmatch(c) for c in cells if DATE.fullmatch(c)), None)
                names = [c for c in cells if c and not DATE.fullmatch(c) and c != "\xa0"]
                if not m or not names or thr is None:
                    continue
                mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                name = names[0]
                if heading == "career":
                    text = f"{name} gets his {ordinal(thr)} {career}"
                    w = 90 + min(thr, 5000) / 100 if fn in ("miles-hr.htm", "miles-h.htm") else 80
                else:
                    text = f"{name} reaches {thr} {season}"
                    w = 55
                feats[f"{mo:02d}{d:02d}"].append({"year": y, "kind": "milestone", "text": text, "star": star_name(name), "w": w})


def parse_cycles(feats, teams, team_name, star_name):
    h = read("cycles.htm")
    m = re.search(r"(?is)<pre[^>]*>(.*?)</pre>", h)
    body = html.unescape(re.sub(r"<[^>]+>", "", m.group(1) if m else h))
    for line in body.splitlines():
        mm = re.match(r"\s*(\d\d)/(\d\d)/(\d{4})\s+(.+?)\s{2,}([A-Z0-9]{3})\s+(\w{2})\s+([A-Z0-9]{3})\s+([A-Z0-9]{3})\s+(.+?)\s*$", line)
        if not mm:
            continue
        mo, d, y, name, tm = int(mm.group(1)), int(mm.group(2)), int(mm.group(3)), mm.group(4).strip(), mm.group(5)
        team = team_name(teams, tm, y)
        park = mm.group(9).strip()
        feats[f"{mo:02d}{d:02d}"].append({"year": y, "kind": "cycle", "text": f"{name} hits for the cycle for the {team} ({park})",
                                          "star": star_name(name), "w": 40})


def parse_four_homers(feats, star_name):
    h = read("hr4cons.htm")
    lines = [re.sub(r"\s+", " ", l).strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", h)).splitlines() if l.strip()]
    for i, l in enumerate(lines):
        mm = DATE.fullmatch(l)
        if not mm:
            continue
        names = []
        for x in lines[i + 2:i + 8]:
            if DATE.fullmatch(x) or x.startswith("Note"):
                break
            names.append(re.sub(r"\s*\(.*$", "", x))
        if len(names) >= 4:
            mo, d, y = int(mm.group(1)), int(mm.group(2)), int(mm.group(3))
            feats[f"{mo:02d}{d:02d}"].append({"year": y, "kind": "hr4", "text": f"Four straight home runs: {', '.join(names[:3])} and {names[3]}",
                                              "star": any(star_name(n) for n in names), "w": 95})


def parse_hidden_ball(feats):
    h = read("Hidden_Ball_Tricks.htm")
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S | re.I):
        cells = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if len(cells) >= 7 and DATE.fullmatch(cells[0]):
            mm = DATE.fullmatch(cells[0])
            mo, d, y = int(mm.group(1)), int(mm.group(2)), int(mm.group(3))
            feats[f"{mo:02d}{d:02d}"].append({"year": y, "kind": "hidden", "text": f"{cells[3]} pulls off the hidden-ball trick on {cells[6]}",
                                              "star": False, "w": 25})


def parse_forfeits(feats):
    h = read("forfeits.htm")
    lines = [re.sub(r"\s+", " ", l).strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", h)).splitlines() if l.strip()]
    for i, l in enumerate(lines):
        mm = re.match(r"(\d\d)/(\d\d)/(\d{4}) - (.+? at .+)$", l)
        if mm and i + 1 < len(lines):
            mo, d, y = int(mm.group(1)), int(mm.group(2)), int(mm.group(3))
            feats[f"{mo:02d}{d:02d}"].append({"year": y, "kind": "forfeit", "text": f"Forfeit: {mm.group(4)}", "star": False, "w": 30})


def load_feats(ctx, teams, team_name):
    names = {}
    for i in ctx["hof"]:
        r = ctx["bio"][i]
        names[f"{r['usename']} {r['lastname']}".strip().lower()] = True
    star_name = lambda n: n.strip().lower() in names
    feats = collections.defaultdict(list)
    parse_milestones(feats, star_name)
    parse_cycles(feats, teams, team_name, star_name)
    parse_four_homers(feats, star_name)
    parse_hidden_ball(feats)
    parse_forfeits(feats)
    return feats


def feats_for(month, day, feats, limit=8):
    rows = feats.get(f"{month:02d}{day:02d}", [])
    if not rows:
        return {"count": 0, "items": []}
    scored = sorted(rows, key=lambda r: (-(r["w"] + (12 if r["star"] else 0)), -r["year"]))
    chosen, per_kind = [], collections.Counter()
    caps = {"milestone": 4, "cycle": 3, "hr4": 1, "hidden": 1, "forfeit": 1}
    for r in scored:
        if per_kind[r["kind"]] >= caps.get(r["kind"], 2):
            continue
        per_kind[r["kind"]] += 1
        chosen.append({"year": r["year"], "text": r["text"], "star": r["star"], "kind": r["kind"]})
        if len(chosen) >= limit:
            break
    chosen.sort(key=lambda r: -r["year"])
    kinds = collections.Counter(r["kind"] for r in rows)
    return {"count": len(rows), "items": chosen, "cycles": kinds.get("cycle", 0), "milestones": kinds.get("milestone", 0)}
