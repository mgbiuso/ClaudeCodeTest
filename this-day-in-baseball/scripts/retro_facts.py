#!/usr/bin/env python3
"""Build the Retrosheet-based extras for each calendar date: "By the Numbers", the game of the day, era charts,
team records, ballparks, the transaction wire, debuts and farewells, and ejections.

Reads the files that fetch_retrosheet.py saved in .cache/retrosheet/ and writes data/retro/MM-DD.json (one per date)
plus data/retro/calendar.json (activity counts for all 366 days, for the year-at-a-glance calendar).
No AI and no network: plain counting and templates.

Game log fields used (1-based, checked against the 1956 World Series perfect game):
  1 date, 4 visitor, 7 home, 10/11 scores, 12 length in outs, 17 park, 18 attendance, 19 minutes, 20/21 line scores,
  visitor batting 22-38 (23 hits, 26 HR, 30 HBP, 31 BB, 33 SO, 34 SB, 38 LOB), visitor pitchers used 39, visitor errors 46,
  home batting 50-66 (51 hits, 54 HR, 58 HBP, 59 BB, 61 SO, 62 SB, 66 LOB), home pitchers used 67, home errors 74,
  102/103 visitor starting pitcher id and name, 104/105 home starting pitcher.

The information used here was obtained free of charge from and is copyrighted by Retrosheet.
Interested parties may contact Retrosheet at www.retrosheet.org.
"""
import argparse
import collections
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retro_people import load_context, people_for, transactions_for, ejections_for, calendar_counts  # noqa: E402
from retro_feats import load_feats, feats_for  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "retrosheet"
OUT = ROOT / "data" / "retro"
POST = {"glws": "World Series", "gldv": "Division Series", "gllc": "League Championship Series",
        "glwc": "Wild Card Game", "glas": "All-Star Game"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

# Retrosheet's team list lags behind a few renamings, so these are fixed here: (code, first year) -> nickname.
RENAMES = [("HOU", 1965, "Astros"), ("TBA", 2008, "Rays"), ("CLE", 2022, "Guardians"), ("OAK", 2025, "Athletics")]
# Old franchise codes folded into today's franchise, for all-time records on a date.
FRANCHISE = {"BRO": "LAN", "NY1": "SFN", "BSN": "ATL", "MLN": "ATL", "PHA": "OAK", "KC1": "OAK", "SLA": "BAL", "WS1": "MIN",
             "WS2": "TEX", "MON": "WAS", "CAL": "ANA", "LAA": "ANA", "FLO": "MIA", "SE1": "MIL"}
ACTIVE = {"ANA", "ARI", "ATL", "BAL", "BOS", "CHA", "CHN", "CIN", "CLE", "COL", "DET", "HOU", "KCA", "LAN", "MIA", "MIL", "MIN",
          "NYA", "NYN", "OAK", "PHI", "PIT", "SDN", "SEA", "SFN", "SLN", "TBA", "TEX", "TOR", "WAS"}


def load_teams():
    teams = {}
    for row in csv.reader((CACHE / "TEAMABR.TXT").read_text(encoding="latin-1").splitlines()):
        if len(row) >= 6:
            teams.setdefault(row[0], []).append((int(row[4]), 9999 if int(row[5]) >= 2021 else int(row[5]), row[3]))
    return teams


def team_name(teams, code, year):
    for c, first, nick in RENAMES:
        if code == c and year >= first:
            return nick
    rows = teams.get(code, [])
    for first, last, nick in rows:
        if first <= year <= last:
            return nick
    return rows[0][2] if rows else code


def load_parks():
    parks = {}
    z = zipfile.ZipFile(CACHE / "biodata.zip")
    for r in csv.DictReader(io.StringIO(z.read("ballparks0.csv").decode("latin-1"))):
        parks[r["site"]] = (r["name"], r["city"], r["state"])
    return parks


def to_int(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def innings_of(line):
    return re.findall(r"\(\d+\)|\d|x", line or "")


def runs_in(tok):
    return 0 if tok == "x" else int(tok.strip("()"))


def collect(date_keys):
    """One pass over every game log: {MMDD: [(row, label)]} for the requested dates only."""
    want = set(date_keys)
    out = collections.defaultdict(list)
    z = zipfile.ZipFile(CACHE / "gl1871_2025.zip")
    for name in sorted(n for n in z.namelist() if re.fullmatch(r"gl\d{4}\.txt", n)):
        for row in csv.reader(io.StringIO(z.read(name).decode("latin-1"))):
            if len(row) > 105 and row[0][4:] in want:
                out[row[0][4:]].append((row, ""))
    for stem, label in POST.items():
        z = zipfile.ZipFile(CACHE / f"{stem}.zip")
        for row in csv.reader(io.StringIO(z.read(f"{stem}.txt").decode("latin-1"))):
            if len(row) > 105 and row[0][4:] in want:
                out[row[0][4:]].append((row, label))
    return out


class Game:
    """One parsed game-log row."""

    def __init__(self, row, label, teams):
        self.year = int(row[0][:4])
        self.date = row[0]
        self.label = label
        self.v, self.h = team_name(teams, row[3], self.year), team_name(teams, row[6], self.year)
        self.vcode, self.hcode = row[3], row[6]
        self.vs, self.hs = to_int(row[9]), to_int(row[10])
        self.outs = to_int(row[11]) or 0
        self.park = row[16]
        self.crowd = to_int(row[17]) or 0
        self.minutes = to_int(row[18]) or 0
        self.vline, self.hline = innings_of(row[19]), innings_of(row[20])
        g = lambda i: to_int(row[i - 1]) if len(row) >= i else None
        self.vh, self.hh = g(23), g(51)
        self.vhr, self.hhr = g(26), g(54)
        self.vso, self.hso = g(33), g(61)
        self.vsb, self.hsb = g(34), g(62)
        self.vbb, self.hbb = g(31), g(59)
        self.vhbp, self.hhbp = g(30), g(58)
        self.vlob, self.hlob = g(38), g(66)
        self.vpit, self.hpit = g(39), g(67)
        self.verr, self.herr = g(46), g(74)
        self.vsp, self.hsp = row[102], row[104]
        self.ok = self.vs is not None and self.hs is not None

    @property
    def innings(self):
        return max(len(self.vline), len(self.hline))

    def walkoff(self):
        if not self.ok or self.hs <= self.vs or not self.hline or self.hline[-1] == "x":
            return False
        last = runs_in(self.hline[-1])
        return last > 0 and (self.hs - last) <= self.vs

    def best_inning(self):
        return max((runs_in(t) for t in self.vline + self.hline), default=0)


def winner_first(g):
    a, b = (g.v, g.vs), (g.h, g.hs)
    w, l = (a, b) if a[1] >= b[1] else (b, a)
    return f"{w[0]} {w[1]}, {l[0]} {l[1]}"


def no_hitters(games):
    found = []
    for g in games:
        if not g.ok or g.outs < 51:
            continue
        for hitless, side in ((g.vh, "v"), (g.hh, "h")):
            if hitless != 0:
                continue
            by, against = (g.h, g.v) if side == "v" else (g.v, g.h)
            sp = g.hsp if side == "v" else g.vsp
            used = g.hpit if side == "v" else g.vpit
            bb, hbp, lob = (g.vbb, g.vhbp, g.vlob) if side == "v" else (g.hbb, g.hhbp, g.hlob)
            err = g.herr if side == "v" else g.verr
            perfect = bb == 0 and hbp == 0 and lob == 0 and err == 0 and used == 1
            found.append({"year": g.year, "by": by, "against": against, "pitcher": sp if used == 1 else None,
                          "combined": bool(used and used > 1), "perfect": perfect, "event": g.label})
    found.sort(key=lambda x: x["year"])
    return found


def decade(y):
    return y // 10 * 10


def build_numbers(games, parks, nohit):
    valid = [g for g in games if g.ok]
    if not valid:
        return None
    n = len(valid)
    by = lambda fn, items=valid: max(items, key=fn)
    years = sorted({g.year for g in valid})
    items, records = [], []
    items.append({"label": "Games played on this date", "value": f"{n:,}", "note": f"since {years[0]}"})
    top = by(lambda g: g.vs + g.hs)
    items.append({"label": "Most runs in a game", "value": str(top.vs + top.hs), "note": f"{winner_first(top)} ({top.year})"})
    blow = by(lambda g: abs(g.vs - g.hs))
    if abs(blow.vs - blow.hs) > 0:
        items.append({"label": "Biggest blowout", "value": f"{abs(blow.vs - blow.hs)} runs", "note": f"{winner_first(blow)} ({blow.year})"})
    long_g = by(lambda g: g.innings)
    if long_g.innings > 9:
        items.append({"label": "Longest game", "value": f"{long_g.innings} innings", "note": f"{long_g.v} at {long_g.h} ({long_g.year})"})
    wo = sorted((g for g in valid if g.walkoff()), key=lambda g: g.date)
    if wo:
        items.append({"label": "Walk-off wins", "value": f"{len(wo):,}", "note": f"latest: {winner_first(wo[-1])} ({wo[-1].year})"})
    if nohit:
        perfect = [x for x in nohit if x["perfect"]]
        last = nohit[-1]
        who = last["pitcher"] or last["by"]
        items.append({"label": "No-hitters" + (f" ({len(perfect)} perfect)" if perfect else ""), "value": str(len(nohit)),
                      "note": f"latest: {who} ({last['year']})"})
    crowds = [g for g in valid if g.crowd]
    if crowds:
        c = by(lambda g: g.crowd, crowds)
        items.append({"label": "Biggest crowd", "value": f"{c.crowd:,}", "note": f"{c.v} at {c.h} ({c.year})"})

    def add(label, value, note):
        records.append({"label": label, "value": value, "note": note})

    hrs = [g for g in valid if g.vhr is not None and g.hhr is not None]
    if hrs:
        g = by(lambda g: max(g.vhr, g.hhr), hrs)
        t, tm = (g.vhr, g.v) if g.vhr >= g.hhr else (g.hhr, g.h)
        if t >= 3:
            add("Most home runs by one team", str(t), f"{tm} ({g.year}); {winner_first(g)}")
    sos = [g for g in valid if g.vso is not None and g.hso is not None]
    if sos:
        g = by(lambda g: g.vso + g.hso, sos)
        add("Most strikeouts in a game", str(g.vso + g.hso), f"{winner_first(g)} ({g.year})")
    sbs = [g for g in valid if g.vsb is not None and g.hsb is not None]
    if sbs:
        g = by(lambda g: max(g.vsb, g.hsb), sbs)
        t = max(g.vsb, g.hsb)
        if t >= 4:
            add("Most steals by one team", str(t), f"{g.v if g.vsb >= g.hsb else g.h} ({g.year})")
    inn = by(lambda g: g.best_inning())
    if inn.best_inning() >= 6:
        add("Most runs in one inning", str(inn.best_inning()), f"{winner_first(inn)} ({inn.year})")
    mins = [g for g in valid if g.minutes and g.outs >= 51]
    if mins:
        a, b = min(mins, key=lambda g: g.minutes), max(mins, key=lambda g: g.minutes)
        add("Shortest and longest games", f"{a.minutes} and {b.minutes} min", f"{a.year} and {b.year}")
    decided = [g for g in valid if g.vs != g.hs]
    if len(decided) >= 20:
        hw = sum(1 for g in decided if g.hs > g.vs)
        add("Home team won", f"{round(100 * hw / len(decided))}%", f"of {len(decided):,} decided games")
    post = [g for g in valid if g.label]
    if post:
        names = collections.Counter(g.label for g in post)
        add("Postseason games", str(len(post)), ", ".join(f"{k} {v}" for k, v in names.most_common(3)))
    pk = collections.Counter(g.park for g in valid if g.park)
    if pk:
        top3 = [f"{parks.get(code, (code,))[0]} ({cnt})" for code, cnt in pk.most_common(3)]
        add("Ballparks that hosted games", str(len(pk)), "most games: " + "; ".join(top3))
    return {"items": items[:6], "records": records}


def game_of_day(games, parks):
    best, best_score = None, -1
    for g in games:
        if not g.ok or not g.vline or not g.hline:
            continue
        s = 0
        s += 9 if g.label == "World Series" else (5 if g.label else 0)
        s += max(0, g.innings - 9) * 1.2
        s += 2 if abs(g.vs - g.hs) == 1 else 0
        s += 2.5 if g.walkoff() else 0
        s += 4 if (g.vh == 0 or g.hh == 0) and g.outs >= 51 else 0
        s += min(2, g.crowd / 40000)
        s += min(2, (g.vs + g.hs) / 12)
        s += 0.002 * g.year
        if s > best_score:
            best, best_score = g, s
    if not best:
        return None
    g = best
    cols = max(len(g.vline), len(g.hline), 9)
    pad = lambda line: [("x" if t == "x" else t.strip("()")) for t in line] + [""] * (cols - len(line))
    why = []
    if g.label:
        why.append(g.label)
    if g.innings > 9:
        why.append(f"{g.innings} innings")
    if g.walkoff():
        why.append("walk-off")
    if (g.vh == 0 or g.hh == 0) and g.outs >= 51:
        why.append("no-hitter")
    if abs(g.vs - g.hs) == 1 and not why:
        why.append("one-run game")
    return {"year": g.year, "visitor": g.v, "home": g.h, "inn": cols, "vline": pad(g.vline), "hline": pad(g.hline),
            "vr": g.vs, "hr": g.hs, "vh": g.vh, "hh": g.hh, "ve": g.verr, "he": g.herr, "crowd": g.crowd or None,
            "park": parks.get(g.park, (None,))[0], "event": g.label, "why": ", ".join(why)}


def eras(games):
    buckets = collections.defaultdict(list)
    for g in games:
        if g.ok:
            buckets[decade(g.year)].append(g)
    rows = []
    for d in sorted(buckets):
        gs = buckets[d]
        cr = [g.crowd for g in gs if g.crowd]
        rows.append({"decade": d, "games": len(gs), "rpg": round(sum(g.vs + g.hs for g in gs) / len(gs), 2),
                     "crowd": round(sum(cr) / len(cr)) if len(cr) >= 3 else None})
    return rows if len(rows) >= 3 else []


def then_now(games, parks):
    valid = sorted((g for g in games if g.ok), key=lambda g: g.date)
    if len(valid) < 2:
        return None
    pack = lambda g: {"year": g.year, "visitor": g.v, "home": g.h, "vs": g.vs, "hs": g.hs, "crowd": g.crowd or None,
                      "park": parks.get(g.park, (None,))[0], "event": g.label}
    return {"first": pack(valid[0]), "latest": pack(valid[-1])}


def team_records(games, teams):
    rec = collections.defaultdict(lambda: [0, 0])
    for g in games:
        if not g.ok or g.vs == g.hs:
            continue
        for code, won in ((g.vcode, g.vs > g.hs), (g.hcode, g.hs > g.vs)):
            rec[FRANCHISE.get(code, code)][0 if won else 1] += 1
    rows = [{"team": team_name(teams, fr, 2025), "w": w, "l": l, "pct": round(w / (w + l), 3)}
            for fr, (w, l) in rec.items() if w + l >= 12 and fr in ACTIVE]
    if len(rows) < 6:
        return None
    rows.sort(key=lambda r: -r["pct"])
    return {"best": rows[:3], "worst": rows[-3:][::-1]}


def build_day(month, day, rows, teams, parks, ctx, feats):
    gs = [Game(r, lab, teams) for r, lab in rows]
    nh = no_hitters(gs)
    numbers = build_numbers(gs, parks, nh)
    rec = {"month": month, "day": day, "games": len([g for g in gs if g.ok])}
    if numbers:
        rec.update({"items": numbers["items"], "records": numbers["records"], "nohitters": nh, "gotd": game_of_day(gs, parks),
                    "eras": eras(gs), "thenNow": then_now(gs, parks), "teams": team_records(gs, teams)})
    else:
        rec.update({"items": [], "records": [], "nohitters": []})
    rec["wire"] = transactions_for(month, day, ctx, teams, team_name)
    rec["people"] = people_for(month, day, ctx)
    rec["ejections"] = ejections_for(month, day, ctx)
    rec["feats"] = feats_for(month, day, feats)
    return rec


def collect_counts():
    """Games per MMDD for all 366 days (cheap: counts only)."""
    c = collections.Counter()
    z = zipfile.ZipFile(CACHE / "gl1871_2025.zip")
    for name in sorted(n for n in z.namelist() if re.fullmatch(r"gl\d{4}\.txt", n)):
        for line in z.read(name).decode("latin-1").splitlines():
            if len(line) > 12:
                c[line[5:9]] += 1
    for stem in POST:
        z = zipfile.ZipFile(CACHE / f"{stem}.zip")
        for line in z.read(f"{stem}.txt").decode("latin-1").splitlines():
            if len(line) > 12:
                c[line[5:9]] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="*", help="MM/DD (default: every date that has a data/days file)")
    ap.add_argument("--calendar", action="store_true", help="also rebuild data/retro/calendar.json (all 366 days)")
    a = ap.parse_args()
    if not (CACHE / "gl1871_2025.zip").exists():
        sys.exit("Run scripts/fetch_retrosheet.py first.")
    if a.dates:
        dates = [tuple(map(int, d.split("/"))) for d in a.dates]
    else:
        dates = sorted((int(p.stem[:2]), int(p.stem[3:])) for p in (ROOT / "data" / "days").glob("*.json"))
    teams, parks, ctx = load_teams(), load_parks(), load_context()
    feats = load_feats(ctx, teams, team_name)
    games = collect([f"{m:02d}{d:02d}" for m, d in dates])
    OUT.mkdir(parents=True, exist_ok=True)
    for month, day in dates:
        rec = build_day(month, day, games.get(f"{month:02d}{day:02d}", []), teams, parks, ctx, feats)
        (OUT / f"{month:02d}-{day:02d}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        print(f"{MONTHS[month - 1]} {day}: {rec['games']:,} games, {len(rec['items'])} stats, {len(rec['nohitters'])} no-hitters, "
              f"wire {rec['wire'].get('count', 0):,}, debuts {len(rec['people'].get('debuts', []))}, ejections {rec['ejections'].get('count', 0)}, feats {rec['feats'].get('count', 0)}")
    if a.calendar:
        cal = calendar_counts(ctx, collect_counts())
        cal["built"] = sorted(p.stem.replace("-", "") for p in (ROOT / "data" / "days").glob("*.json"))
        (OUT / "calendar.json").write_text(json.dumps(cal, separators=(",", ":")))
        print("calendar.json:", len(cal), "days")


if __name__ == "__main__":
    main()
