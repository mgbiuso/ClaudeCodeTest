#!/usr/bin/env python3
"""Data engine for the "Ballparks on this date" mock and the park pages (mock only, not the live site).

Reads the cached Retrosheet game logs and lists, scores park events, and picks up to three parks per calendar day.
Ranking (agreed with Mike, Nov. 9, 2026): park openings and closings first, then everything else by points.

Needs: .cache/retrosheet (game logs, lists), .cache/lahman, images/ballparks/*.webp, and scripts/retro_feats.py
Run a quick self-test:  python3 design-mockups/ballpark-pages/ballpark_data.py
"""
import calendar
import collections
import csv
import html
import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RS = ROOT / ".cache" / "retrosheet"
IMG_DIR = ROOT / "images" / "ballparks"
sys.path.insert(0, str(ROOT / "scripts"))
import retro_feats as rf  # noqa: E402  (the site's own readers for the milestone lists)

MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]
KIND_LABEL = {"opening": "Opens", "closing": "Closes", "perfect game": "Perfect game", "no-hitter": "No-hitter",
              "four homers": "Four homers in a row", "milestone": "Milestone", "record crowd": "Record crowd",
              "marathon": "Marathon", "cycle": "Cycle", "longest game": "Longest game", "most runs": "Most runs",
              "most homers": "Most home runs", "forfeit": "Forfeit", "filler": "Also on this date"}


def nice_date(d):
    return f"{MONTHS[int(d[4:6]) - 1]} {int(d[6:])}, {d[:4]}"


def norm(s):
    return re.sub(r"[^a-z ]", "", re.sub(r"\s+", " ", s).lower()).strip()


class Data:
    pass


def build():
    D = Data()
    # ---- which parks have drawings, and which files
    D.drawings = collections.defaultdict(list)
    for f in sorted(IMG_DIR.glob("*.webp")):
        code = f.stem.split("_")[0]
        D.drawings[code].append(f)
    for code in D.drawings:
        D.drawings[code].sort(key=lambda p: (p.stem != code, p.stem))
    imgs = set(D.drawings)

    # ---- park names and places (Mike's checklist data first, then Lahman and Retrosheet)
    D.meta = {}
    old = ROOT / "_backup_before_changes" / "checklist.before_oneline.html"
    if old.exists():
        s = old.read_text(encoding="utf-8"); i = s.index("const D = ") + 10
        for p in json.JSONDecoder().raw_decode(s[i:])[0]["parks"]:
            D.meta[p["code"]] = {"name": p["name"], "city": p["city"], "state": p["state"]}
    for r in csv.DictReader(open(RS / "analysis" / "ballparks0.csv", encoding="latin-1")):
        D.meta.setdefault(r["site"], {"name": r["name"] or r["site"], "city": r["city"], "state": r["state"]})
    for r in csv.DictReader(open(ROOT / ".cache/lahman/Parks.csv", encoding="utf-8-sig")):
        D.meta.setdefault(r["parkkey"], {"name": r["parkname"], "city": r["city"], "state": r["state"]})
    name = lambda p: D.meta.get(p, {}).get("name") or p
    D.name = name

    # ---- team names (Retrosheet's own list; a code can be reused in another era, so the year picks the row)
    rows = collections.defaultdict(list)
    for r in csv.reader(open(RS / "TEAMABR.TXT", encoding="latin-1")):
        if len(r) >= 6:
            rows[r[0]].append((int(r[4]), int(r[5]), f"{r[2]} {r[3]}".strip(), r[3].strip()))
    D.teams = rows

    def _row(c, y=None):
        opts = D.teams.get(c)
        if not opts:
            return None
        if y:
            for a, b, n, k in opts:
                if a <= int(y) <= b:
                    return (n, k)
        return (opts[-1][2], opts[-1][3])

    def team(c, y=None):
        r = _row(c, y)
        return r[0] if r else c

    def nick(c, y=None):
        r = _row(c, y)
        return r[1] if r else c
    D.team, D.nick = team, nick

    hof = set()
    people = {r["playerID"]: norm(r["nameFirst"] + " " + r["nameLast"]) for r in csv.DictReader(open(ROOT / ".cache/lahman/People.csv", encoding="utf-8-sig"))}
    for r in csv.DictReader(open(ROOT / ".cache/lahman/HallOfFame.csv", encoding="utf-8-sig")):
        if r["inducted"] == "Y" and r["category"] == "Player" and r["playerID"] in people:
            hof.add(people[r["playerID"]])

    # ---- games
    games, by_date = [], collections.defaultdict(list)
    league = collections.defaultdict(lambda: [0, 0, 0])
    with zipfile.ZipFile(RS / "gl1871_2025.zip") as z:
        for n in sorted(z.namelist()):
            if not n.lower().endswith(".txt"):
                continue
            for r in csv.reader(io.TextIOWrapper(z.open(n), encoding="latin-1")):
                if len(r) < 45:
                    continue
                num = lambda i: int(r[i]) if r[i].lstrip("-").isdigit() else 0
                who = {norm(r[i]) for i in [94, 96, 102, 104] + list(range(106, 159, 3)) if i < len(r) and r[i]}
                g = dict(d=r[0], away=r[3], home=r[6], ar=num(9), hr_=num(10), outs=num(11), dn=r[12], fx=r[14], park=r[16],
                         att=num(17), mins=num(18), hrs=num(25) + num(42), who=who,
                         sp=[norm(r[102]), norm(r[104])] if len(r) > 104 else [])
                games.append(g); by_date[g["d"]].append(g)
                lg = league[r[0][:4]]; lg[0] += 1; lg[1] += g["ar"] + g["hr_"]; lg[2] += g["hrs"]
    D.games, D.league = games, league
    by_park = collections.defaultdict(list)
    for g in games:
        by_park[g["park"]].append(g)
    D.by_park = by_park

    def fame(p):
        n = len(by_park[p]); return 10 if n >= 2000 else 5 if n >= 500 else 0

    events = collections.defaultdict(list)

    def add(g, d, kind, score, text):
        events[d[4:]].append(dict(park=g["park"], kind=kind, score=score, text=text, year=int(d[:4]), date=d, g=g))

    for p, gs in by_park.items():
        if len(gs) < 3:
            continue
        first = min(gs, key=lambda g: g["d"]); last = max(gs, key=lambda g: g["d"])
        small = len(gs) < 100
        add(first, first["d"], "opening", (150 if small else 200) + fame(p),
            f"First major league game: {team(first['away'], first['d'][:4])} {first['ar']}, {team(first['home'], first['d'][:4])} {first['hr_']}")
        if int(last["d"][:4]) < 2025:
            add(last, last["d"], "closing", (148 if small else 198) + fame(p),
                f"Last major league game: {team(last['away'], last['d'][:4])} {last['ar']}, {team(last['home'], last['d'][:4])} {last['hr_']}")
        att = [g for g in gs if g["att"] > 0]
        if len(att) >= 50:
            g = max(att, key=lambda g: g["att"])
            early = int(g["d"][:4]) < 1900 or (g["att"] % 1000 == 0 and int(g["d"][:4]) < 1920)
            add(g, g["d"], "record crowd", (45 if early else 75) + fame(p),
                f"Record crowd of {g['att']:,}{' (an estimate)' if early else ''} for {team(g['away'], g['d'][:4])} at {team(g['home'], g['d'][:4])}")
        timed = [g for g in gs if g["mins"] > 0]
        if len(timed) >= 50:
            g = max(timed, key=lambda g: g["mins"])
            add(g, g["d"], "longest game", 60 + fame(p), f"Longest game here, {g['mins']//60}:{g['mins']%60:02d}: {team(g['away'], g['d'][:4])} {g['ar']}, {team(g['home'], g['d'][:4])} {g['hr_']}")
        if len(gs) >= 50:
            g = max(gs, key=lambda g: g["ar"] + g["hr_"])
            add(g, g["d"], "most runs", 58 + fame(p), f"Most runs in a game here, {g['ar']+g['hr_']}: {team(g['away'], g['d'][:4])} {g['ar']}, {team(g['home'], g['d'][:4])} {g['hr_']}")
            g = max(gs, key=lambda g: (g["hrs"], g["d"]))
            add(g, g["d"], "most homers", 58 + fame(p), f"Most home runs in a game here, {g['hrs']}: {team(g['away'], g['d'][:4])} at {team(g['home'], g['d'][:4])}")
        for g in gs:
            if g["outs"] >= 120:
                add(g, g["d"], "marathon", 70 + fame(p), f"{g['outs']//6}-inning game: {team(g['away'], g['d'][:4])} {g['ar']}, {team(g['home'], g['d'][:4])} {g['hr_']}")
            if g["fx"] in ("V", "H"):
                add(g, g["d"], "forfeit", 45 + fame(p), f"Forfeit: {team(g['away'], g['d'][:4])} at {team(g['home'], g['d'][:4])}")

    # ---- cycles
    home_on = {(g["d"], g["home"]): g for g in games}
    h = open(RS / "lists" / "cycles.htm", encoding="latin-1").read()
    body = html.unescape(re.sub(r"<[^>]+>", "", re.search(r"(?is)<pre[^>]*>(.*?)</pre>", h).group(1)))
    for line in body.splitlines():
        m = re.match(r"\s*(\d\d)/(\d\d)/(\d{4})\s+(.+?)\s{2,}([A-Z0-9]{3})\s+(\w{2})\s+([A-Z0-9]{3})\s+([A-Z0-9]{3})\s+(.+?)\s*$", line)
        if not m:
            continue
        d = m.group(3) + m.group(1) + m.group(2); g = home_on.get((d, m.group(8)))
        if g:
            nm = m.group(4).strip()
            add(g, d, "cycle", 65 + (10 if norm(nm) in hof else 0) + fame(g["park"]), f"{nm} hits for the cycle")

    # ---- milestones and four straight homers
    feats = collections.defaultdict(list)
    rf.parse_milestones(feats, lambda n: False)
    rf.parse_four_homers(feats, lambda n: False)
    for key, items in feats.items():
        for it in items:
            if it["kind"] == "milestone":
                m = re.match(r"(.+?) (gets his|reaches)", it["text"]); who = [norm(m.group(1))] if m else []
            else:
                m = re.match(r"Four straight home runs: (.+?) and (.+)$", it["text"]); who = [norm(x) for x in re.split(r", | and ", m.group(1) + ", " + m.group(2))] if m else []
            if not who:
                continue
            d = f"{it['year']}{key}"
            for g in by_date.get(d, []):
                if any(w in g["who"] for w in who):
                    sc = min(it["w"], 97) + (8 if any(w in hof for w in who) else 0) + fame(g["park"])
                    add(g, d, "four homers" if it["kind"] == "hr4" else "milestone", sc, it["text"])
                    break

    # ---- no-hitters
    nh = html.unescape(open(RS / "lists" / "nohit_chrono.htm", encoding="latin-1").read())
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", nh, re.S | re.I):
        c = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if len(c) < 7 or not re.fullmatch(r"\d+/\d+/\d{4}", c[0]):
            continue
        mo, dd, yy = c[0].split("/"); d = f"{yy}{int(mo):02d}{int(dd):02d}"
        last, _, first = c[2].partition(", "); pit = norm(first + " " + last)
        for g in by_date.get(d, []):
            if pit in g["sp"] or pit in g["who"]:
                perfect = "perfect" in c[6].lower()
                add(g, d, "perfect game" if perfect else "no-hitter", (98 if perfect else 92) + fame(g["park"]),
                    f"{first} {last} throws a {'perfect game' if perfect else 'no-hitter'}")
                break
    D.events = events
    D.by_date = by_date
    D.imgs = imgs

    # ---- picks
    def real(day):
        best = {}
        for e in events.get(day, []):
            k = e["park"]
            if k not in best or e["score"] > best[k]["score"]:
                best[k] = e
        return sorted(best.values(), key=lambda e: (-e["score"], -len(by_park[e["park"]]), -e["year"]))

    def filler(day, taken):
        """Lower-key fillers: biggest crowd and highest-scoring game on this date at parks that have a drawing."""
        pool = []
        for y in range(1871, 2026):
            for g in by_date.get(f"{y}{day}", []):
                if g["park"] in imgs and g["park"] not in taken:
                    pool.append(g)
        out = []
        if pool:
            g = max(pool, key=lambda g: g["att"])
            if g["att"] > 0:
                out.append(dict(park=g["park"], kind="filler", score=10 + g["att"] / 10000, year=int(g["d"][:4]), date=g["d"], g=g,
                                text=f"Biggest crowd here on this date: {g['att']:,} saw {team(g['away'], g['d'][:4])} at {team(g['home'], g['d'][:4])}"))
            g2 = max(pool, key=lambda g: g["ar"] + g["hr_"])
            out.append(dict(park=g2["park"], kind="filler", score=9 + (g2["ar"] + g2["hr_"]) / 100, year=int(g2["d"][:4]), date=g2["d"], g=g2,
                            text=f"Highest-scoring game here on this date: {team(g2['away'], g2['d'][:4])} {g2['ar']}, {team(g2['home'], g2['d'][:4])} {g2['hr_']}"))
        return sorted(out, key=lambda e: -e["score"])

    def pick(day, n=3):
        chosen = real(day)[:n]
        if len(chosen) < n:
            taken = {e["park"] for e in chosen}
            for e in filler(day, taken):
                if len(chosen) >= n:
                    break
                if e["park"] not in taken:
                    chosen.append(e); taken.add(e["park"])
        return chosen
    D.pick, D.real = pick, real
    return D


# ---- per-park facts for the park pages
def park_facts(D, code):
    gs = D.by_park[code]
    f = {"games": len(gs), "first": min(g["d"] for g in gs), "last": max(g["d"] for g in gs)}
    att = [g["att"] for g in gs if g["att"] > 0]
    f["att_games"] = len(att); f["att_avg"] = sum(att) // len(att) if att else 0
    f["record"] = max(gs, key=lambda g: g["att"]) if att else None
    timed = [g for g in gs if g["mins"] > 0]
    f["longest"] = max(timed, key=lambda g: g["mins"]) if len(timed) >= 20 else None
    f["fastest"] = min((g for g in timed if g["ar"] != g["hr_"]), key=lambda g: g["mins"]) if len(timed) >= 20 else None
    f["slug"] = max(gs, key=lambda g: g["ar"] + g["hr_"])
    f["homers"] = max(gs, key=lambda g: (g["hrs"], g["d"]))
    f["night"] = sum(1 for g in gs if g["dn"] == "N")
    ten = {}
    for g in gs:
        t = ten.setdefault(g["home"], [9999, 0, 0]); y = int(g["d"][:4])
        t[0], t[1], t[2] = min(t[0], y), max(t[1], y), t[2] + 1
    f["tenants"] = sorted(((k, v) for k, v in ten.items() if v[2] >= 20), key=lambda kv: kv[1][0])
    yrs = collections.defaultdict(lambda: [0, 0, 0, 0])
    for g in gs:
        y = yrs[g["d"][:4]]; y[0] += 1; y[1] += g["hrs"]
        if g["att"] > 0:
            y[2] += g["att"]; y[3] += 1
    f["years"] = {y: {"games": v[0], "hr": v[1] / v[0], "lg": D.league[y][2] / D.league[y][0], "att": v[2] // v[3] if v[3] else 0}
                  for y, v in sorted(yrs.items())}
    full = [v for v in f["years"].values() if v["games"] >= 30]
    f["above"], f["below"], f["seasons"] = sum(1 for v in full if v["hr"] > v["lg"]), sum(1 for v in full if v["hr"] < v["lg"]), len(full)
    return f


if __name__ == "__main__":
    D = build()
    print(len(D.events), "event days;", len(D.drawings), "parks with drawings")
    for day in ("0704", "1004"):
        print("\n", day)
        for e in D.pick(day):
            print(f"  {e['score']:6.1f} {'art' if e['park'] in D.imgs else 'NO ART'} {D.name(e['park'])[:26]:26} {e['year']} {e['kind']:12} {e['text'][:70]}")
    # find natural examples of days that show 2, 1 and 0 parks
    cnt = collections.defaultdict(list)
    for m in range(1, 13):
        for d in range(1, calendar.monthrange(2024, m)[1] + 1):
            cnt[len(D.pick(f"{m:02d}{d:02d}"))].append(f"{m:02d}{d:02d}")
    print("\ndays by number of parks shown:", {k: len(v) for k, v in sorted(cnt.items())})
    for k in (1, 2):
        print(k, "park days:", cnt.get(k, [])[:12])
