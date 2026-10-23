#!/usr/bin/env python3
"""More facts for each calendar date, from Retrosheet, the Lahman database and Retrosheet's Negro Leagues files.

  python3 scripts/more_facts.py 07/04 10/04 10/22 03/15     just these dates (the sample)
  python3 scripts/more_facts.py                             every date that has a data/days file

Writes data/more/MM-DD.json (one per date) and data/more/global.json (charts that are the same on every date).
No AI and no network: plain counting and templates. Needs the files from fetch_retrosheet.py, the Lahman files from
extras.py --fetch-lahman (plus HallOfFame, AwardsPlayers, CollegePlaying, Schools and Teams), and
.cache/retrosheet/negro/negroleagues.zip.

Game log fields used beyond retro_facts.py (1-based): 2 game number (1 and 2 mean a doubleheader), 13 day or night,
15 forfeit, 106-132 visitor starting lineup (id, name, position times nine), 133-159 home starting lineup.

The information used here was obtained free of charge from and is copyrighted by Retrosheet.
Interested parties may contact Retrosheet at www.retrosheet.org.
Lahman Baseball Database: created by Sean Lahman, maintained by SABR. Negro Leagues statistics there come from Seamheads.com.
"""
import argparse
import collections
import csv
import datetime
import io
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retro_facts as rf  # noqa: E402
import extras  # noqa: E402

ROOT = rf.ROOT
CROWD_AVG = {}  # average crowd per season, filled in by main()
CACHE = rf.CACHE
LAHMAN = ROOT / ".cache" / "lahman"
OUT = ROOT / "data" / "more"
NEGRO = CACHE / "negro" / "negroleagues.zip"
MONTHS = rf.MONTHS
AWARDS = {"Most Valuable Player": "MVP", "Cy Young Award": "Cy Young", "Rookie of the Year": "Rookie of the Year"}
NEGRO_KINDS = {"championship": "Negro League World Series", "lcs": "Negro League playoff", "divisionseries": "Negro League playoff",
               "playoff": "Negro League playoff", "allstar": "East-West All-Star Game", "regular": "League game", "exhibition": "Exhibition game"}


def lrows(name):
    with open(LAHMAN / name, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def ordinal_age(birth, on):
    """Age in whole years on a date; both YYYYMMDD strings."""
    by, bm, bd, y, m, d = int(birth[:4]), int(birth[4:6]), int(birth[6:8]), int(on[:4]), int(on[4:6]), int(on[6:8])
    return y - by - ((m, d) < (bm, bd))


def mdy(date):
    return f"{MONTHS[int(date[4:6]) - 1]} {int(date[6:8])}, {date[:4]}"


# ---------- things that need every game ever played (done once) ----------

def scan_all(teams):
    """Home runs per game by year, the first night game and the last game at every ballpark."""
    hr, games = collections.Counter(), collections.Counter()
    crowd_sum, crowd_n = collections.Counter(), collections.Counter()
    first_night, last_game = {}, {}
    z = zipfile.ZipFile(CACHE / "gl1871_2025.zip")
    for name in sorted(n for n in z.namelist() if re.fullmatch(r"gl\d{4}\.txt", n)):
        for row in csv.reader(io.StringIO(z.read(name).decode("latin-1"))):
            if len(row) < 20:
                continue
            y, park = int(row[0][:4]), row[16]
            a, b = rf.to_int(row[25]), rf.to_int(row[53])
            if a is not None and b is not None and a >= 0 and b >= 0:
                hr[y] += a + b
                games[y] += 1
            att = rf.to_int(row[17])
            if att and att > 0:
                crowd_sum[y] += att
                crowd_n[y] += 1
            if row[12] == "N" and park not in first_night:
                first_night[park] = row[0]
            last_game[park] = (row[0], row)
    return hr, games, first_night, last_game, {y: crowd_sum[y] / crowd_n[y] for y in crowd_n}


def global_charts(hr, games):
    """Charts that are the same on every date: offense, foreign-born share, colleges, complete games."""
    out = {"hrPerGame": [[y, round(hr[y] / games[y], 2)] for y in sorted(games) if games[y] > 100]}
    # share of players born outside the 50 states, by the decade of their debut
    by_dec = collections.defaultdict(lambda: [0, 0])
    people = {}
    for r in lrows("People.csv"):
        people[r["playerID"]] = r
        if r.get("debut") and r.get("birthCountry"):
            dec = int(r["debut"][:4]) // 10 * 10
            by_dec[dec][0] += 1
            by_dec[dec][1] += r["birthCountry"] != "USA"
    out["foreignBorn"] = [[d, round(100 * f / n, 1), n] for d, (n, f) in sorted(by_dec.items()) if n >= 100]
    # colleges: players per school, by the decade they played in college
    schools = {r["schoolID"]: r["name_full"] for r in lrows("Schools.csv")}
    seen = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in lrows("CollegePlaying.csv"):
        if r.get("yearID") and r["playerID"] in people and people[r["playerID"]].get("debut"):
            seen[int(r["yearID"]) // 10 * 10][r["schoolID"]].add(r["playerID"])
    out["colleges"] = {str(d): [[schools.get(s, s), len(p)] for s, p in sorted(v.items(), key=lambda kv: -len(kv[1]))[:5]]
                       for d, v in sorted(seen.items()) if d >= 1950 and sum(len(p) for p in v.values()) > 200}
    # complete games per team season
    cg, ts = collections.Counter(), collections.Counter()
    for r in lrows("Teams.csv"):
        if r.get("CG") not in (None, ""):
            d = int(r["yearID"]) // 10 * 10
            cg[d] += int(float(r["CG"]))
            ts[d] += 1
    out["teamNames"] = {fr: rf.team_name(rf.load_teams(), fr, 2025) for fr in sorted(rf.ACTIVE)}
    out["completeGames"] = [[d, round(cg[d] / ts[d], 1)] for d in sorted(ts) if d >= 1900]
    return out, people


# ---------- one date ----------

def named(g, parks):
    return {"year": g.year, "visitor": g.v, "home": g.h, "vs": g.vs, "hs": g.hs,
            "park": parks[g.park][0] if g.park in parks else None, "city": parks[g.park][1] if g.park in parks else None, "event": g.label}


def game_records(gs, parks):
    valid = [g for g in gs if g.ok]
    if not valid:
        return {}
    out = {}
    timed = [g for g in valid if g.minutes > 60]
    if timed:
        g = max(timed, key=lambda g: g.minutes)
        out["longest"] = dict(named(g, parks), minutes=g.minutes, innings=g.innings)
    crowd = [g for g in valid if g.crowd > 0]
    if crowd:
        g = max(crowd, key=lambda g: g.crowd)
        avg = CROWD_AVG.get(g.year)
        out["crowd"] = dict(named(g, parks), crowd=g.crowd, seasonAvg=round(avg) if avg else None)
    g = max(valid, key=lambda g: g.vs + g.hs)
    out["runs"] = dict(named(g, parks), total=g.vs + g.hs)
    g = max(valid, key=lambda g: abs(g.vs - g.hs))
    out["blowout"] = dict(named(g, parks), margin=abs(g.vs - g.hs))
    g = max(valid, key=lambda g: g.innings)
    if g.innings >= 12:
        out["marathon"] = dict(named(g, parks), innings=g.innings)
    ties = [g for g in valid if g.vs == g.hs]
    if ties:
        out["ties"] = {"count": len(ties), "latest": named(max(ties, key=lambda g: g.year), parks)}
    forf = [g for g in valid if g.raw[14].strip()]
    if forf:
        out["forfeits"] = {"count": len(forf), "latest": named(max(forf, key=lambda g: g.year), parks)}
    return out


def duel(gs, parks):
    """Both starters finished the game (each team used one pitcher) and the game was low-scoring."""
    c = [g for g in gs if g.ok and g.vpit == 1 and g.hpit == 1 and g.outs >= 51 and g.vsp and g.hsp and g.vs != g.hs and g.vs + g.hs <= 3]
    if not c:
        return None
    g = min(c, key=lambda g: (g.vs + g.hs, -g.year))
    return dict(named(g, parks), vpitcher=g.vsp, hpitcher=g.hsp, count=len(c))


def firsts(gs, parks, mmdd, first_night, last_game, teams):
    out = {}
    nights = []
    for park, date in first_night.items():
        if date[4:] == mmdd and int(date[:4]) >= 1935:
            nights.append({"year": int(date[:4]), "park": parks.get(park, (park,))[0], "city": parks.get(park, (None, ""))[1]})
    if nights:
        out["firstNight"] = sorted(nights, key=lambda x: x["year"])
    dh = [g for g in gs if g.raw[1] in ("1", "2")]
    if dh:
        out["doubleheaders"] = len(dh) // 2
    last = []
    for park, (date, row) in last_game.items():
        if date[4:] == mmdd and int(date[:4]) < 2024 and park in parks:
            g = rf.Game(row, "", teams)
            if g.ok:
                last.append(dict(named(g, parks), crowd=g.crowd or None))
    if last:
        out["lastGames"] = sorted(last, key=lambda x: x["year"])
    return out


def team_day(gs, teams):
    """Every current franchise's all-time record on this date, best win and worst loss."""
    rec = collections.defaultdict(lambda: {"w": 0, "l": 0, "t": 0, "first": 9999, "best": None, "worst": None})
    for g in gs:
        if not g.ok:
            continue
        for code, own, opp, name in ((g.vcode, g.vs, g.hs, g.h), (g.hcode, g.hs, g.vs, g.v)):
            fr = rf.FRANCHISE.get(code, code)
            if fr not in rf.ACTIVE:
                continue
            r = rec[fr]
            r["first"] = min(r["first"], g.year)
            if own > opp:
                r["w"] += 1
                if not r["best"] or own - opp > r["best"][0]:
                    r["best"] = (own - opp, f"{own}-{opp} over the {name}", g.year)
            elif own < opp:
                r["l"] += 1
                if not r["worst"] or opp - own > r["worst"][0]:
                    r["worst"] = (opp - own, f"{own}-{opp} to the {name}", g.year)
            else:
                r["t"] += 1
    return {fr: {"name": rf.team_name(teams, fr, 2025), "w": r["w"], "l": r["l"], "t": r["t"], "first": r["first"],
                 "best": r["best"] and {"score": r["best"][1], "year": r["best"][2]},
                 "worst": r["worst"] and {"score": r["worst"][1], "year": r["worst"][2]}}
            for fr, r in rec.items()}


def ages(gs, bio, mmdd):
    """Youngest and oldest players who started a game on this date."""
    rows = []
    for g in gs:
        r = g.raw
        for team, start, pit in ((g.v, 105, 101), (g.h, 132, 103)):
            ids = [(r[start + 3 * i], r[start + 3 * i + 1]) for i in range(9)] + [(r[pit], r[pit + 1])]
            for pid, name in ids:
                b = bio.get(pid)
                if b and len(b["birth"]) == 8:
                    age = ordinal_age(b["birth"], g.date)
                    if 15 <= age <= 55:
                        rows.append((age, g.year, name, team, pid))
    if not rows:
        return None
    seen, uniq = set(), []
    for t in sorted(rows):
        if (t[2], t[1]) not in seen:
            seen.add((t[2], t[1]))
            uniq.append(t)
    mk = lambda t: {"name": t[2], "age": t[0], "year": t[1], "team": t[3]}
    return {"youngest": mk(uniq[0]), "oldest": mk(uniq[-1])}


def load_bio():
    z = zipfile.ZipFile(CACHE / "biodata.zip")
    bio = {}
    for r in csv.DictReader(io.StringIO(z.read("biofile0.csv").decode("latin-1"))):
        bio[r["id"]] = {"birth": r["birthdate"], "debut": r["debut_p"], "last": r["last_p"], "name": r["fullname"] or f"{r['usename']} {r['lastname']}",
                        "short": f"{r['usename']} {r['lastname']}", "hof": bool(r["HOF"]), "country": r["birthcountry"]}
    rel = collections.defaultdict(list)
    for r in csv.DictReader(io.StringIO(z.read("relatives.csv").decode("latin-1"))):
        rel[r["id1"]].append((r["relation"], r["id2"]))
    return bio, rel


class Lah:
    """People, awards, Hall of Fame and one-game lines from the Lahman files."""

    def __init__(self, people):
        self.people = people
        self.hof = {r["playerID"] for r in lrows("HallOfFame.csv") if r["inducted"] == "Y" and r["category"] == "Player"}
        self.hof_year = {r["playerID"]: r["yearid"] for r in lrows("HallOfFame.csv") if r["inducted"] == "Y" and r["category"] == "Player"}
        self.awards = collections.defaultdict(list)
        for r in lrows("AwardsPlayers.csv"):
            if r["awardID"] in AWARDS:
                self.awards[r["playerID"]].append((AWARDS[r["awardID"]], r["yearID"]))
        self.bat1, self.pit1 = {}, {}
        counts = collections.Counter()
        for r in lrows("Batting.csv"):
            counts[r["playerID"]] += 1
            self.bat1[r["playerID"]] = r
        for r in lrows("Pitching.csv"):
            counts[r["playerID"]] += 1
            self.pit1[r["playerID"]] = r
        self.stints = counts
        self.died = collections.defaultdict(list)
        for r in people.values():
            if r.get("deathYear") and r.get("deathMonth") and r.get("deathDay"):
                self.died[(int(r["deathYear"]), int(r["deathMonth"]), int(r["deathDay"]))].append(r)
        extras.load_lahman()

    def name(self, r):
        return f"{r['nameFirst']} {r['nameLast']}".strip()

    def place(self, r):
        bits = [r.get("birthCity"), r.get("birthState") if r.get("birthCountry") == "USA" else r.get("birthCountry")]
        return ", ".join(b for b in bits if b)

    def one_game_line(self, pid):
        b, p = self.bat1.get(pid), self.pit1.get(pid)
        if p and int(float(p.get("G") or 0)) == 1 and int(float(p.get("IPouts") or 0)) > 0 or (p and not b):
            outs = int(float(p.get("IPouts") or 0))
            ip = f"{outs // 3}" + {0: "", 1: " 1/3", 2: " 2/3"}[outs % 3]
            return f"pitched {ip.strip() or '0'} inning{'s' if outs != 3 else ''}, allowed {p.get('R') or 0} run{'s' if str(p.get('R')) != '1' else ''}"
        if b and int(float(b.get("G") or 0)) == 1:
            ab, h = int(float(b.get("AB") or 0)), int(float(b.get("H") or 0))
            hr = int(float(b.get("HR") or 0))
            s = f"went {h} for {ab}" if ab else "did not bat"
            return s + (f", with {hr} home run{'s' if hr > 1 else ''}" if hr else "")
        return None


def people_block(month, day, lah, bio, rel):
    pe = lah.people
    born = [r for r in pe.values() if r.get("birthMonth") == str(month) and r.get("birthDay") == str(day) and r.get("birthYear")]
    rank = lambda r: (r["playerID"] in lah.hof, bool(lah.awards.get(r["playerID"])), lah.stints[r["playerID"]])
    top = sorted(born, key=rank, reverse=True)
    born_rows = []
    for r in top:
        line = extras.career_line(r["playerID"])
        if line or r["playerID"] in lah.hof:
            born_rows.append({"name": lah.name(r), "year": int(r["birthYear"]), "place": lah.place(r), "career": line,
                              "hof": r["playerID"] in lah.hof})
        if len(born_rows) == 6:
            break
    hof = []
    for r in born:
        if r["playerID"] in lah.hof:
            hof.append({"name": lah.name(r), "kind": "Born", "year": int(r["birthYear"]), "inducted": lah.hof_year[r["playerID"]]})
    for r in pe.values():
        if r["playerID"] in lah.hof:
            if r.get("debut", "")[5:] == f"{month:02d}-{day:02d}":
                hof.append({"name": lah.name(r), "kind": "Debuted", "year": int(r["debut"][:4]), "inducted": lah.hof_year[r["playerID"]]})
            if r.get("deathMonth") == str(month) and r.get("deathDay") == str(day) and r.get("deathYear"):
                hof.append({"name": lah.name(r), "kind": "Died", "year": int(r["deathYear"]), "inducted": lah.hof_year[r["playerID"]]})
    hof.sort(key=lambda x: (x["kind"], x["year"]))
    winners = []
    for r in born:
        aw = lah.awards.get(r["playerID"])
        if aw:
            winners.append({"name": lah.name(r), "year": int(r["birthYear"]), "awards": [{"award": a, "year": int(y)} for a, y in sorted(set(aw), key=lambda t: t[1])]})
    winners.sort(key=lambda w: -len(w["awards"]))
    # coincidences
    co = {"bornCount": len(born)}
    names = collections.defaultdict(list)
    for r in born:
        names[(r["nameFirst"], r["nameLast"])].append(int(r["birthYear"]))
    same = [(n, ys) for n, ys in names.items() if len(set(ys)) > 1]
    if same:
        (f, l), ys = max(same, key=lambda t: len(t[1]))
        co["sameName"] = {"name": f"{f} {l}", "years": sorted(ys)}
    circle = []
    for r in pe.values():
        d = r.get("debut", "")
        if d[5:] == f"{month:02d}-{day:02d}":
            for dead in lah.died.get((int(d[:4]), month, day), []):
                if dead["playerID"] != r["playerID"]:
                    circle.append({"year": int(d[:4]), "debut": lah.name(r), "died": lah.name(dead),
                                   "weight": (dead["playerID"] in lah.hof) * 2 + (r["playerID"] in lah.hof)})
    if circle:
        co["fullCircle"] = max(circle, key=lambda c: (c["weight"], c["year"]))
        co["fullCircle"].pop("weight")
    # one-game wonders who debuted (and ended) on this date
    ones = []
    for r in pe.values():
        d = r.get("debut", "")
        if d and d == r.get("finalGame") and d[5:] == f"{month:02d}-{day:02d}":
            line = lah.one_game_line(r["playerID"])
            if line:
                ones.append({"name": lah.name(r), "year": int(d[:4]), "line": line, "place": lah.place(r)})
    ones.sort(key=lambda o: -o["year"])
    # families: a relative pair where one member debuted on this date
    fam = []
    bydeb = {pid: b for pid, b in bio.items() if b["debut"][4:] == f"{month:02d}{day:02d}"}
    for pid, b in bydeb.items():
        for kind, other in rel.get(pid, []):
            if kind in ("Father", "Son") and other in bio and bio[other]["debut"]:
                fa, so = (pid, other) if kind == "Father" else (other, pid)
                fam.append({"father": bio[fa]["short"], "fatherDebut": int(bio[fa]["debut"][:4]), "son": bio[so]["short"], "sonDebut": int(bio[so]["debut"][:4])})
    fam = list({(f["father"], f["son"]): f for f in fam}.values())
    return {"born": born_rows, "hof": hof[:8], "awardWinners": winners[:5], "coincidences": co, "oneGame": ones[:3], "families": fam[:2]}


# ---------- Negro Leagues ----------

class Negro:
    def __init__(self):
        self.z = zipfile.ZipFile(NEGRO)
        b = zipfile.ZipFile(CACHE / "biodata.zip")
        self.teams = {r["team"]: f"{r['city']} {r['nickname']}".strip() for r in csv.DictReader(io.StringIO(b.read("teams0.csv").decode("latin-1")))}
        self.parks = {r["site"]: (r["name"], r["city"], r["state"]) for r in csv.DictReader(io.StringIO(b.read("ballparks0.csv").decode("latin-1")))}
        self.games = list(self.rd("gameinfo.csv"))
        self.names = {r["id"]: f"{r['first']} {r['last']}".strip() for r in self.rd("allplayers.csv")}
        self._bat = self._pit = None

    def rd(self, name):
        return csv.DictReader(io.TextIOWrapper(self.z.open(name), encoding="utf-8-sig"))

    def lines(self, gids):
        if self._bat is None:
            self._bat = collections.defaultdict(list)
            for r in self.rd("batting.csv"):
                self._bat[r["gid"]].append(r)
            self._pit = collections.defaultdict(list)
            for r in self.rd("pitching.csv"):
                self._pit[r["gid"]].append(r)
        return self._bat, self._pit

    def day(self, month, day, parks_unused=None):
        mmdd = f"{month:02d}{day:02d}"
        gs = [g for g in self.games if g["date"][4:] == mmdd and g["vruns"] != "" and g["hruns"] != ""]
        if not gs:
            return None
        gids = {g["gid"] for g in gs}
        bat, pit = self.lines(gids)
        weight = {"championship": 5, "lcs": 4, "divisionseries": 4, "playoff": 4, "allstar": 4, "regular": 2, "exhibition": 0}

        def score(g):
            return (weight.get(g["gametype"], 0), bool(g["box"]), len(bat.get(g["gid"], [])) > 12, bool(g["attendance"]), int(g["season"]))
        t = lambda c: self.teams.get(c, c)
        ranked = sorted(gs, key=score, reverse=True)
        top = [g for g in ranked if weight.get(g["gametype"], 0) == weight.get(ranked[0]["gametype"], 0) and g["box"]] or ranked[:1]
        best = max(top[:25], key=lambda g: (len(self.stars(g, bat, pit, t)), score(g)))
        park = self.parks.get(best["site"])
        stars = self.stars(best, bat, pit, t)
        others = []
        for g in ranked:
            if g is best or len(others) == 6:
                continue
            others.append({"year": int(g["season"]), "text": f"{t(g['visteam'])} {g['vruns']}, {t(g['hometeam'])} {g['hruns']}", "kind": NEGRO_KINDS.get(g["gametype"], "Game")})
        return {"count": len(gs), "years": [min(int(g["season"]) for g in gs), max(int(g["season"]) for g in gs)],
                "withBox": sum(1 for g in gs if g["box"]),
                "game": {"year": int(best["season"]), "kind": NEGRO_KINDS.get(best["gametype"], "Game"), "visitor": t(best["visteam"]), "home": t(best["hometeam"]),
                         "vs": int(best["vruns"]), "hs": int(best["hruns"]), "park": park and park[0].strip(), "city": park and ", ".join(x for x in park[1:] if x),
                         "crowd": int(best["attendance"]) if best["attendance"] and int(best["attendance"]) > 0 else None, "stars": stars, "hasBox": bool(best["box"])},
                "others": others}

    def stars(self, best, bat, pit, t):
        stars = []
        for r in bat.get(best["gid"], []):
            if r["stattype"] != "value":
                continue
            h, hr, rbi, ab = (int(float(r[k] or 0)) for k in ("b_h", "b_hr", "b_rbi", "b_ab"))
            if h >= 3 or hr >= 1 or rbi >= 3:
                approx = any(x["id"] == r["id"] and x["stattype"] in ("lower", "upper") for x in bat[best["gid"]])
                bits = [f"{h} for {ab}" if ab else f"{h} hits"] + ([f"{hr} HR"] if hr else []) + ([f"{rbi} RBI"] if rbi else [])
                stars.append({"player": self.names.get(r["id"], r["id"]), "team": t(r["team"]), "line": ", ".join(bits), "approx": approx, "rank": h + 3 * hr + rbi})
        for r in pit.get(best["gid"], []):
            if r["stattype"] != "value":
                continue
            outs, k, er = (int(float(r[x] or 0)) for x in ("p_ipouts", "p_k", "p_er"))
            if outs >= 21 or k >= 8:
                approx = any(x["id"] == r["id"] and x["stattype"] in ("lower", "upper") for x in pit[best["gid"]])
                ip = f"{outs // 3}" + {0: "", 1: ".1", 2: ".2"}[outs % 3]
                stars.append({"player": self.names.get(r["id"], r["id"]), "team": t(r["team"]), "line": f"{ip} IP" + (f", {k} K" if r["p_k"] != "" else "") + (f", {r['p_r']} R" if r["p_r"] != "" else ""), "approx": approx, "rank": outs / 3 + k})
        stars = sorted(stars, key=lambda s: -s["rank"])[:4]
        for s_ in stars:
            s_.pop("rank")
        return stars


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="*", help="MM/DD (default: every date that has a data/days file)")
    a = ap.parse_args()
    dates = [tuple(map(int, d.split("/"))) for d in a.dates] or sorted((int(p.stem[:2]), int(p.stem[3:])) for p in (ROOT / "data" / "days").glob("*.json"))
    teams, parks = rf.load_teams(), rf.load_parks()
    print("scanning every game log once ...")
    hr, games, first_night, last_game, crowd_avg = scan_all(teams)
    CROWD_AVG.update(crowd_avg)
    glob, people = global_charts(hr, games)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "global.json").write_text(json.dumps(glob, ensure_ascii=False, separators=(",", ":")))
    lah, (bio, rel), negro = Lah(people), load_bio(), Negro()
    got = rf.collect([f"{m:02d}{d:02d}" for m, d in dates])
    for month, day in dates:
        mmdd = f"{month:02d}{day:02d}"
        gs = []
        for row, label in got.get(mmdd, []):
            g = rf.Game(row, label, teams)
            g.raw = row
            gs.append(g)
        rec = {"month": month, "day": day, "records": game_records([g for g in gs if g.ok], parks) if gs else {}, "duel": duel(gs, parks),
               "firsts": firsts(gs, parks, mmdd, first_night, last_game, teams), "ages": ages(gs, bio, mmdd), "teams": team_day(gs, teams),
               "people": people_block(month, day, lah, bio, rel), "negro": negro.day(month, day)}
        (OUT / f"{month:02d}-{day:02d}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        p, n = rec["people"], rec["negro"]
        print(f"{MONTHS[month - 1]} {day}: {len(gs)} games, records {len(rec['records'])}, duel {bool(rec['duel'])}, firsts {list(rec['firsts'])}, "
              f"ages {bool(rec['ages'])}, born {len(p['born'])}, hof {len(p['hof'])}, awards {len(p['awardWinners'])}, one-game {len(p['oneGame'])}, "
              f"families {len(p['families'])}, negro {n and n['count']}")


if __name__ == "__main__":
    main()
