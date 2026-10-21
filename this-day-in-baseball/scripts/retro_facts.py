#!/usr/bin/env python3
"""Build "By the Numbers" facts for each calendar date from Retrosheet game logs.

Reads the zips that fetch_retrosheet.py saved in .cache/retrosheet/ and writes data/retro/MM-DD.json with, for every
game ever played on that month and day: how many games, the highest-scoring game, the biggest blowout, the longest
game, no-hitters and the biggest crowd. No AI and no network: plain counting.

Game log fields used (1-based, per Retrosheet's guide): 1 date, 4 visitor, 7 home, 10/11 scores, 12 length in outs,
18 attendance, 20/21 line scores, 23/51 hits. Postseason files carry the same layout.

The information used here was obtained free of charge from and is copyrighted by Retrosheet.
"""
import argparse
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "retrosheet"
OUT = ROOT / "data" / "retro"
POST = {"glws": "World Series", "gldv": "Division Series", "gllc": "League Championship Series",
        "glwc": "Wild Card Game", "glas": "All-Star Game"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def load_teams():
    """code -> [(first_year, last_year, nickname)]. Retrosheet's last year of 2021 means the team is still active."""
    teams = {}
    for row in csv.reader((CACHE / "TEAMABR.TXT").read_text(encoding="latin-1").splitlines()):
        if len(row) >= 6:
            teams.setdefault(row[0], []).append((int(row[4]), 9999 if int(row[5]) >= 2021 else int(row[5]), row[3]))
    return teams


# Retrosheet's team list lags behind a few renamings, so these are fixed here: (code, first year) -> nickname.
RENAMES = [("HOU", 1965, "Astros"), ("TBA", 2008, "Rays"), ("CLE", 2022, "Guardians"), ("OAK", 2025, "Athletics")]


def team_name(teams, code, year):
    for c, first, nick in RENAMES:
        if code == c and year >= first:
            return nick
    rows = teams.get(code, [])
    for first, last, nick in rows:
        if first <= year <= last:
            return nick
    return rows[0][2] if rows else code


def innings(line):
    """Number of innings in a Retrosheet line score such as '00010101101' or '10(12)0x'."""
    return len(re.findall(r"\(\d+\)|\d|x", line or ""))


def to_int(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def games(date_key):
    """Yield (row, label) for every game on this MMDD in every file."""
    z = zipfile.ZipFile(CACHE / "gl1871_2025.zip")
    for name in sorted(n for n in z.namelist() if re.fullmatch(r"gl\d{4}\.txt", n)):
        for row in csv.reader(io.StringIO(z.read(name).decode("latin-1"))):
            if len(row) >= 21 and row[0][4:] == date_key:
                yield row, ""
    for stem, label in POST.items():
        z = zipfile.ZipFile(CACHE / f"{stem}.zip")
        for row in csv.reader(io.StringIO(z.read(f"{stem}.txt").decode("latin-1"))):
            if len(row) >= 21 and row[0][4:] == date_key:
                yield row, label


def facts_for(month, day, teams):
    key = f"{month:02d}{day:02d}"
    n = 0
    best = {"runs": None, "margin": None, "long": None, "crowd": None}
    nohit = []
    years = set()
    for row, label in games(key):
        year = int(row[0][:4])
        vs, hs = to_int(row[9]), to_int(row[10])
        if vs is None or hs is None:
            continue
        n += 1
        years.add(year)
        v, h = team_name(teams, row[3], year), team_name(teams, row[6], year)
        g = {"year": year, "visitor": v, "home": h, "vs": vs, "hs": hs, "event": label}
        total, margin = vs + hs, abs(vs - hs)
        inn = max(innings(row[19]), innings(row[20]))
        crowd = to_int(row[17]) or 0
        if best["runs"] is None or total > best["runs"][0]:
            best["runs"] = (total, g)
        if best["margin"] is None or margin > best["margin"][0]:
            best["margin"] = (margin, g)
        if best["long"] is None or inn > best["long"][0]:
            best["long"] = (inn, g)
        if crowd and (best["crowd"] is None or crowd > best["crowd"][0]):
            best["crowd"] = (crowd, g)
        # A no-hitter: one side has 0 hits recorded (the field is blank in early years) in a full-length game.
        vh, hh = to_int(row[22]), to_int(row[50]) if len(row) > 50 else None
        outs = to_int(row[11]) or 0
        if outs >= 51:
            if vh == 0:
                nohit.append({**g, "by": h, "against": v})
            if hh == 0:
                nohit.append({**g, "by": v, "against": h})
    return n, years, best, nohit


def line(g):
    """'Cubs 26, Phillies 23' with the winner first."""
    a, b = (g["visitor"], g["vs"]), (g["home"], g["hs"])
    w, l = (a, b) if a[1] >= b[1] else (b, a)
    return f"{w[0]} {w[1]}, {l[0]} {l[1]}"


def build(month, day, teams):
    n, years, best, nohit = facts_for(month, day, teams)
    items = []
    if n:
        items.append({"label": "Games played on this date", "value": f"{n:,}", "note": f"since {min(years)}"})
    if best["runs"]:
        t, g = best["runs"]
        items.append({"label": "Most runs in a game", "value": f"{t}", "note": f"{line(g)} ({g['year']})"})
    if best["margin"] and best["margin"][0] > 0:
        m, g = best["margin"]
        items.append({"label": "Biggest blowout", "value": f"{m} runs", "note": f"{line(g)} ({g['year']})"})
    if best["long"] and best["long"][0] > 9:
        i, g = best["long"]
        items.append({"label": "Longest game", "value": f"{i} innings", "note": f"{g['visitor']} at {g['home']} ({g['year']})"})
    if nohit:
        nohit.sort(key=lambda x: x["year"])
        recent = nohit[-1]
        note = f"latest: {recent['by']} over {recent['against']} ({recent['year']})"
        items.append({"label": "No-hitters", "value": f"{len(nohit)}", "note": note})
    if best["crowd"]:
        c, g = best["crowd"]
        items.append({"label": "Biggest crowd", "value": f"{c:,}", "note": f"{g['visitor']} at {g['home']} ({g['year']})"})
    return {"month": month, "day": day, "games": n, "items": items,
            "nohitters": [{"year": x["year"], "by": x["by"], "against": x["against"]} for x in nohit]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="*", help="MM/DD (default: every date that has a data/days file)")
    a = ap.parse_args()
    if not (CACHE / "gl1871_2025.zip").exists():
        sys.exit("Run scripts/fetch_retrosheet.py first.")
    teams = load_teams()
    if a.dates:
        dates = [tuple(map(int, d.split("/"))) for d in a.dates]
    else:
        dates = sorted((int(p.stem[:2]), int(p.stem[3:])) for p in (ROOT / "data" / "days").glob("*.json"))
    OUT.mkdir(parents=True, exist_ok=True)
    for month, day in dates:
        out = build(month, day, teams)
        (OUT / f"{month:02d}-{day:02d}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print(f"{MONTHS[month - 1]} {day}: {out['games']:,} games, {len(out['items'])} facts, {len(out['nohitters'])} no-hitters")


if __name__ == "__main__":
    main()
