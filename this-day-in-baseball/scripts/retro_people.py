"""People and paperwork from Retrosheet for one calendar date: the transaction wire, debuts and farewells, ejections.

Used by retro_facts.py. Reads biodata.zip (people), tranDB.zip (transactions 1873 to 2020, no longer updated) and
ejections.zip from .cache/retrosheet/. No network, no AI.

The information used here was obtained free of charge from and is copyrighted by Retrosheet.
"""
import collections
import csv
import io
import re
import zipfile
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / ".cache" / "retrosheet"
ID = re.compile(r"^[a-z][a-z'\-]{0,4}[a-z0-9]?\w{0,3}\d{3}$")


def load_context():
    z = zipfile.ZipFile(CACHE / "biodata.zip")
    bio = {r["id"]: r for r in csv.DictReader(io.StringIO(z.read("biofile0.csv").decode("latin-1")))}
    mgr = {r["id"]: r for r in csv.DictReader(io.StringIO(z.read("managers0.csv").decode("latin-1")))}
    hof = {i for i, r in bio.items() if r.get("HOF")}
    tran = collections.defaultdict(list)
    z = zipfile.ZipFile(CACHE / "tranDB.zip")
    for r in csv.reader(io.StringIO(z.read("tran.txt").decode("latin-1"))):
        if len(r) >= 12 and r[0][4:6] != "00" and r[0][6:8] != "00" and r[0][4:6] != "":
            tran[r[0][4:]].append(r)
    ej = collections.defaultdict(list)
    z = zipfile.ZipFile(CACHE / "ejections.zip")
    for r in csv.DictReader(io.StringIO(z.read("ejections.csv").decode("latin-1"))):
        ej[r["DATE"][:2] + r["DATE"][3:5]].append(r)
    deb, last = collections.defaultdict(list), collections.defaultdict(list)
    for i, r in bio.items():
        if len(r["debut_p"]) == 8:
            deb[r["debut_p"][4:]].append(i)
        if len(r["last_p"]) == 8:
            last[r["last_p"][4:]].append(i)
    mdeb, mlast = collections.defaultdict(list), collections.defaultdict(list)
    for i, r in mgr.items():
        if len(r["first_g"]) == 8:
            mdeb[r["first_g"][4:]].append(i)
        if len(r["last_g"]) == 8:
            mlast[r["last_g"][4:]].append(i)
    return {"bio": bio, "hof": hof, "tran": tran, "ej": ej, "deb": deb, "last": last, "mdeb": mdeb, "mlast": mlast, "mgr": mgr}


def name_of(ctx, pid):
    if " " in pid:
        return pid.strip()
    r = ctx["bio"].get(pid)
    if not r:
        return pid
    return f"{r['usename']} {r['lastname']}".strip()


def seasons(r):
    try:
        return int(r["last_p"][:4]) - int(r["debut_p"][:4]) + 1
    except (ValueError, KeyError):
        return 0


def join_names(names):
    names = list(dict.fromkeys(names))
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def transactions_for(month, day, ctx, teams, team_name):
    key = f"{month:02d}{day:02d}"
    rows = ctx["tran"].get(key, [])
    out = {"count": len(rows), "items": [], "summary": []}
    if not rows:
        return out
    tc = collections.Counter(r[7].strip() for r in rows)
    years = collections.Counter(int(r[0][:4]) for r in rows)
    free = [r for r in rows if r[7].strip() == "Fg"]
    if free:
        fy = collections.Counter(int(r[0][:4]) for r in free)
        y, n = fy.most_common(1)[0]
        out["summary"].append({"label": "Players granted free agency", "value": f"{len(free):,}", "note": f"most in {y} ({n})"})
    trades = tc.get("T", 0)
    if trades:
        out["summary"].append({"label": "Trades made", "value": f"{trades:,}", "note": "players moved"})
    sign = tc.get("F", 0) + tc.get("Fa", 0) + tc.get("Fo", 0)
    if sign:
        out["summary"].append({"label": "Signings", "value": f"{sign:,}", "note": "free agents and amateurs"})
    if tc.get("Da"):
        out["summary"].append({"label": "Draft picks", "value": f"{tc['Da']:,}", "note": "amateur draft"})
    top_year, top_n = years.most_common(1)[0]
    out["summary"].append({"label": "Busiest year", "value": str(top_year), "note": f"{top_n:,} transactions"})

    nm = lambda code, y: team_name(teams, code, y) if code in teams else None
    events = []
    trade_groups = collections.defaultdict(list)
    for r in rows:
        t = r[7].strip()
        y = int(r[0][:4])
        who, pid = name_of(ctx, r[6]) if r[6] else "", r[6]
        star = pid in ctx["hof"]
        if t == "T" and r[5]:
            trade_groups[(r[0], r[5])].append(r)
        elif t == "Fg" and who and nm(r[8], y):
            events.append((10 * star + 1.5, y, f"{who} becomes a free agent ({nm(r[8], y)})", star))
        elif t in ("F", "Fo") and who and nm(r[10], y):
            events.append((10 * star + 2, y, f"{who} signs with the {nm(r[10], y)}", star))
        elif t == "P" and who and nm(r[10], y):
            src = f" from the {nm(r[8], y)}" if nm(r[8], y) else ""
            events.append((10 * star + 2, y, f"{nm(r[10], y)} buy {who}{src}", star))
        elif t == "R" and who and nm(r[8], y):
            events.append((10 * star + 1, y, f"{nm(r[8], y)} release {who}", star))
        elif t == "Da" and who and nm(r[10], y) and r[13] == "1":
            events.append((2, y, f"{nm(r[10], y)} draft {who} in the first round", False))
    for (d, _), grp in trade_groups.items():
        y = int(d[:4])
        dirs = collections.defaultdict(list)
        star = False
        for r in grp:
            dirs[(r[8], r[10])].append(name_of(ctx, r[6]) if r[6] else "cash")
            star = star or r[6] in ctx["hof"]
        keys = list(dirs)
        if not keys or not nm(keys[0][0], y) or not nm(keys[0][1], y):
            continue
        a, b = keys[0]
        if (b, a) in dirs:
            text = f"{nm(a, y)} trade {join_names(dirs[(a, b)])} to the {nm(b, y)} for {join_names(dirs[(b, a)])}"
        else:
            text = f"{nm(a, y)} trade {join_names(dirs[(a, b)])} to the {nm(b, y)}"
        events.append((10 * star + 3 + 0.5 * min(len(grp), 4), y, text, star))
    events.sort(key=lambda e: (-e[0], -e[1]))
    chosen, per_year = [], collections.Counter()
    for sc, y, text, star in events:
        if per_year[y] >= 2:
            continue
        chosen.append({"year": y, "text": text, "star": star})
        per_year[y] += 1
        if len(chosen) >= 8:
            break
    chosen.sort(key=lambda e: -e["year"])
    out["items"] = chosen
    return out


def people_for(month, day, ctx):
    key = f"{month:02d}{day:02d}"

    def pick(ids, kind):
        rows = []
        for i in ids:
            r = ctx["bio"][i]
            y = int(r["debut_p"][:4]) if kind == "debut" else int(r["last_p"][:4])
            if kind == "last" and y > 2018:
                continue
            rows.append((10 ** 3 * (i in ctx["hof"]) + seasons(r), y, i))
        rows.sort(key=lambda x: (-x[0], -x[1]))
        out = []
        for _, y, i in rows[:6]:
            r = ctx["bio"][i]
            out.append({"year": y, "name": name_of(ctx, i), "star": i in ctx["hof"], "seasons": seasons(r)})
        out.sort(key=lambda x: -x["year"])
        return out

    deb_ids, last_ids = ctx["deb"].get(key, []), ctx["last"].get(key, [])
    res = {"debuts": pick(deb_ids, "debut") if deb_ids else [], "farewells": pick(last_ids, "last") if last_ids else [],
           "debutCount": len(deb_ids), "farewellCount": len([i for i in last_ids if int(ctx["bio"][i]["last_p"][:4]) <= 2018]),
           "hofDebuts": sum(1 for i in deb_ids if i in ctx["hof"])}
    mg = []
    for i in ctx["mdeb"].get(key, []):
        r = ctx["mgr"][i]
        mg.append({"year": int(r["first_g"][:4]), "name": f"{r['firstname']} {r['lastname']}".strip(), "star": i in ctx["hof"]})
    mg.sort(key=lambda x: (-x["star"], -x["year"]))
    res["managerDebuts"] = mg[:3]
    return res


def ejections_for(month, day, ctx):
    key = f"{month:02d}{day:02d}"
    rows = ctx["ej"].get(key, [])
    out = {"count": len(rows), "managers": sum(1 for r in rows if r["JOB"] == "M"), "items": []}
    if not rows:
        return out
    scored = []
    for r in rows:
        y = int(r["DATE"][-4:])
        star = r["EJECTEE"] in ctx["hof"]
        role = {"M": "manager", "P": "player", "C": "coach"}.get(r["JOB"], "")
        reason = (r["REASON"] or "").strip()
        who = r["EJECTEENAME"]
        text = f"{who}{' (' + role + ')' if role else ''} ejected by {r['UMPIRENAME']}" + (f": {reason.lower()}" if reason else "")
        scored.append((10 * star + (3 if r["JOB"] == "M" else 0) + (1 if reason else 0) + y / 3000, y, text, star))
    scored.sort(key=lambda s: -s[0])
    chosen = [{"year": y, "text": t, "star": st} for _, y, t, st in scored[:5]]
    chosen.sort(key=lambda e: -e["year"])
    out["items"] = chosen
    return out


def calendar_counts(ctx, games):
    """[games, transactions, ejections, debuts+farewells] for every calendar day."""
    import datetime
    d, out = datetime.date(2024, 1, 1), {}
    while d.year == 2024:
        k = d.strftime("%m%d")
        out[k] = [games.get(k, 0), len(ctx["tran"].get(k, [])), len(ctx["ej"].get(k, [])),
                  len(ctx["deb"].get(k, [])) + len(ctx["last"].get(k, []))]
        d += datetime.timedelta(1)
    return out
