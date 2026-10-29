#!/usr/bin/env python3
"""Rank every game played on one calendar day: postseason first (World Series on top), then stars and big lines, then drama.
Usage: python3 scripts/rank_games.py MMDD   (reads the Retrosheet CSV zips in .cache/retrosheet/csv/)
Prints the top 50 and writes .cache/rank_MMDD.json."""
import csv, io, json, sys, zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / ".cache" / "retrosheet" / "csv"
TIER = {"worldseries": 5, "lcs": 4, "divisionseries": 4, "wildcard": 4, "playoff": 4, "championship": 4, "allstar": 3, "regular": 2, "exhibition": 1}


def read(zname, member):
    with zipfile.ZipFile(CSV / zname) as z, z.open(member) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, "utf-8"))


def n(x):
    return int(x) if x not in ("", None) else 0


def rank(mmdd):
    games = {r["gid"]: r for r in read("gameinfo.zip", "gameinfo.csv") if r["date"].endswith(mmdd) and r["gametype"] != "exhibition"}
    stars = defaultdict(int)
    outs = defaultdict(int)  # outs recorded by each team's pitchers; the larger count gives the innings played
    for r in read("batting.zip", "batting.csv"):
        if r["gid"] not in games:
            continue
        h, hr, rbi = n(r["b_h"]), n(r["b_hr"]), n(r["b_rbi"])
        stars[r["gid"]] += (2 * (h - 3) if h >= 4 else 0) + 3 * hr + (5 if hr >= 3 else 0) + (rbi - 3 if rbi >= 4 else 0)
    for r in read("pitching.zip", "pitching.csv"):
        if r["gid"] not in games:
            continue
        k, h, runs = n(r["p_k"]), n(r["p_h"]), n(r["p_r"])
        outs[(r["gid"], r["team"])] += n(r["p_ipouts"])
        complete = r["p_cg"] not in ("", "0")
        stars[r["gid"]] += (k - 9 if k >= 10 else 0) + (6 if complete and runs == 0 else 0) + (20 if complete and h == 0 else 0)
    out = []
    for gid, g in games.items():
        v, h = n(g["vruns"]), n(g["hruns"])
        innings = max(outs[(gid, g["visteam"])], outs[(gid, g["hometeam"])]) // 3
        extra = max(0, (n(g["innings"]) or innings) - 9)
        drama = 2 * extra + (3 if abs(v - h) == 1 else 0) + (1 if abs(v - h) == 0 else 0)
        out.append({"gid": gid, "type": g["gametype"], "tier": TIER.get(g["gametype"], 2), "stars": stars[gid], "drama": drama, "inn": n(g["innings"]) or innings, "v": g["visteam"], "h": g["hometeam"], "vr": v, "hr": h, "att": n(g["attendance"])})
    out.sort(key=lambda x: (x["tier"], x["stars"], x["drama"], x["att"]), reverse=True)
    return out[:50]


if __name__ == "__main__":
    top = rank(sys.argv[1])
    (ROOT / ".cache" / ("rank_%s.json" % sys.argv[1])).write_text(json.dumps(top))
    for i, g in enumerate(top, 1):
        print(i, g["gid"], g["type"], g["v"], g["vr"], g["h"], g["hr"], "stars", g["stars"], "drama", g["drama"], "inn", g["inn"])
