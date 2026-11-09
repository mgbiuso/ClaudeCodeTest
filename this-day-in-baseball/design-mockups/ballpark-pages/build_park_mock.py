#!/usr/bin/env python3
"""Build the Polo Grounds park page mock (desktop and phone) from the cached Retrosheet game logs.

Every number on the page is computed here from .cache/retrosheet/gl1871_2025.zip. Nothing is typed in by hand
except the short captions. This is a design mock, not part of the live site.

Run:  python3 design-mockups/ballpark-pages/build_park_mock.py
Writes: polo-grounds-desktop.html and polo-grounds-phone.html next to this script.
"""
import base64
import collections
import csv
import html
import io
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LOGS = ROOT / ".cache" / "retrosheet" / "gl1871_2025.zip"
IMAGE = ROOT / "images" / "ballparks" / "NYC14.webp"
PARK = "NYC14"
MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]
TEAMS = {"BRO": "Dodgers", "NY1": "Giants", "SLN": "Cardinals", "CHN": "Cubs", "PIT": "Pirates", "PHI": "Phillies",
         "CIN": "Reds", "NYN": "Mets", "NYA": "Yankees", "SFN": "Giants", "BSN": "Braves", "PHA": "Athletics",
         "CLE": "Indians", "CHA": "White Sox"}


def nice_date(d):
    return f"{MONTHS[int(d[4:6]) - 1]} {int(d[6:])}, {d[:4]}"


def team(c):
    return TEAMS.get(c, c)


def load():
    """Return (games at the park, per-year league totals)."""
    league = collections.defaultdict(lambda: [0, 0, 0])
    mine = []
    with zipfile.ZipFile(LOGS) as z:
        for n in sorted(z.namelist()):
            if not n.lower().endswith(".txt"):
                continue
            for r in csv.reader(io.TextIOWrapper(z.open(n), encoding="latin-1")):
                if len(r) < 45:
                    continue
                try:
                    runs = int(r[9]) + int(r[10])
                    hr = int(r[25]) + int(r[42])
                except ValueError:
                    continue
                lg = league[r[0][:4]]
                lg[0] += 1
                lg[1] += runs
                lg[2] += hr
                if r[16] == PARK:
                    mine.append({"date": r[0], "away": r[3], "home": r[6], "ar": int(r[9]), "hr_": int(r[10]),
                                 "runs": runs, "hr": hr, "dn": r[12],
                                 "att": int(r[17]) if r[17].isdigit() else 0,
                                 "min": int(r[18]) if r[18].isdigit() else 0})
    return mine, league


def facts(mine, league):
    f = {}
    f["games"] = len(mine)
    att = [g["att"] for g in mine if g["att"] > 0]
    f["att_games"], f["att_sum"], f["att_avg"] = len(att), sum(att), sum(att) // len(att)
    f["first"], f["last"] = min(g["date"] for g in mine), max(g["date"] for g in mine)
    f["record"] = max(mine, key=lambda g: g["att"])
    timed = [g for g in mine if g["min"] > 0]
    f["longest"] = max(timed, key=lambda g: g["min"])
    f["fastest"] = min((g for g in timed if g["ar"] != g["hr_"]), key=lambda g: g["min"])
    top_runs = max(g["runs"] for g in mine)
    f["slug"] = [g for g in mine if g["runs"] == top_runs]
    f["homers"] = max(mine, key=lambda g: (g["hr"], g["date"]))
    f["night"] = sum(1 for g in mine if g["dn"] == "N")
    f["tenants"] = {}
    for g in mine:
        t = f["tenants"].setdefault(g["home"], [9999, 0, 0])
        t[0], t[1], t[2] = min(t[0], int(g["date"][:4])), max(t[1], int(g["date"][:4])), t[2] + 1
    years = collections.defaultdict(lambda: [0, 0, 0, 0])
    for g in mine:
        y = years[g["date"][:4]]
        y[0] += 1
        y[1] += g["hr"]
        if g["att"] > 0:
            y[2] += g["att"]
            y[3] += 1
    f["years"] = {y: {"hr": v[1] / v[0], "lg": league[y][2] / league[y][0],
                      "att": v[2] // v[3] if v[3] else 0} for y, v in sorted(years.items())}
    f["hitter_seasons"] = sum(1 for v in f["years"].values() if v["hr"] > v["lg"])
    return f


# ---------- charts (inline SVG, drawn to scale) ----------
def line_chart(f, w, h, fs):
    L, R, T, B = 38, 14, 16, 26
    ys = [int(y) for y in f["years"]]
    x0, x1 = 1911, 1963
    top = 1.6
    X = lambda y: L + (y - x0) / (x1 - x0) * (w - L - R)
    Y = lambda v: T + (1 - v / top) * (h - T - B)
    o = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-labelledby="t1">'
         '<title id="t1">Home runs per game at the Polo Grounds compared with all of baseball, 1911 to 1963</title>']
    for v in (0, 0.5, 1.0, 1.5):
        o.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>')
        o.append(f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" class="ax" font-size="{fs}">{v:.1f}</text>')
    for yr in (1920, 1930, 1940, 1950, 1960):
        o.append(f'<text x="{X(yr):.1f}" y="{h - 8}" text-anchor="middle" class="ax" font-size="{fs}">{yr}</text>')
    for key, cls in (("lg", "l-lg"), ("hr", "l-park")):
        segs, cur = [], []
        for y in ys:
            if cur and y - cur[-1][0] > 1:
                segs.append(cur)
                cur = []
            cur.append((y, f["years"][str(y)][key]))
        segs.append(cur)
        for s in segs:
            pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in s)
            o.append(f'<polyline points="{pts}" class="{cls}"/>')
    px, py = X(1962), Y(f["years"]["1962"]["hr"])
    o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.6" class="dot"/>')
    o.append(f'<text x="{px - 8:.1f}" y="{py - 8:.1f}" text-anchor="end" class="note" font-size="{fs}">1962: {f["years"]["1962"]["hr"]:.2f} here</text>')
    o.append(f'<text x="{X(1960):.1f}" y="{Y(1.0):.1f}" text-anchor="middle" class="note-soft" font-size="{fs - 1}">no games 1958 to 1961</text>')
    o.append(f'<text x="{X(1912):.1f}" y="{Y(0.05) - 6:.1f}" class="lab-soft" font-size="{fs}">All of baseball (dashed)</text>')
    o.append(f'<text x="{X(1920):.1f}" y="{Y(1.18):.1f}" class="lab" font-size="{fs}">Polo Grounds (solid)</text>')
    o.append("</svg>")
    return "".join(o)


def bar_chart(f, w, h, fs):
    L, R, T, B = 38, 14, 16, 26
    yrs = [(int(y), v["att"]) for y, v in f["years"].items() if v["att"]]
    x0, x1, top = 1911, 1963, 30000
    X = lambda y: L + (y - x0) / (x1 - x0) * (w - L - R)
    Y = lambda v: T + (1 - v / top) * (h - T - B)
    bw = max(3, (w - L - R) / 52 * 0.72)
    o = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-labelledby="t2">'
         '<title id="t2">Average crowd per game at the Polo Grounds by season</title>']
    for v in (0, 10000, 20000, 30000):
        o.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>')
        o.append(f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" class="ax" font-size="{fs}">{v // 1000}K</text>')
    for yr in (1920, 1930, 1940, 1950, 1960):
        o.append(f'<text x="{X(yr):.1f}" y="{h - 8}" text-anchor="middle" class="ax" font-size="{fs}">{yr}</text>')
    peak = max(yrs, key=lambda a: a[1])
    for yr, a in yrs:
        cls = "bar peak" if yr == peak[0] else "bar"
        o.append(f'<rect x="{X(yr) - bw / 2:.1f}" y="{Y(a):.1f}" width="{bw:.1f}" height="{Y(0) - Y(a):.1f}" class="{cls}"/>')
    o.append(f'<text x="{X(peak[0]) + 6:.1f}" y="{Y(peak[1]) - 6:.1f}" class="note" font-size="{fs}">{peak[0]}: {peak[1]:,}</text>')
    o.append("</svg>")
    return "".join(o)


# ---------- page ----------
CSS = """
:root {
  /* Layout: a 1999 sports-section "park file". Ruled newsprint columns, a typewriter label face for the data. */
  --paper: #e2dfd2;
  --paper-2: #d3cfbf;
  --ink: #0f1519;
  --ink-soft: #3b444a;
  --red: #b3202a;
  --sans: "Libre Franklin", "Franklin Gothic Medium", "Franklin Gothic", "Arial Narrow", Arial, sans-serif;
  --cond: "Bebas Neue", "League Gothic", "Franklin Gothic Condensed", "Arial Narrow", Impact, sans-serif;
  --type: "Courier New", Courier, monospace;
  color-scheme: light;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--sans); font-size: 16px; line-height: 1.5; }
.wrap { max-width: 1080px; margin: 0 auto; padding-block: 12px 40px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.phone .wrap { max-width: 430px; }
a { color: var(--ink); }
a:focus-visible { outline: 3px solid var(--red); outline-offset: 2px; }
.mock { font-family: var(--type); font-size: 12px; letter-spacing: .04em; text-transform: uppercase; background: var(--ink); color: var(--paper); padding: 6px 10px; margin-bottom: 12px; }
.mast { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; border-top: 4px solid var(--ink); border-bottom: 1px solid var(--ink); padding: 6px 0; font-family: var(--cond); font-size: 20px; letter-spacing: .08em; }
.mast span:last-child { font-family: var(--type); font-size: 13px; letter-spacing: 0; align-self: center; }
.hero { margin: 14px 0 6px; }
.hero img { display: block; width: 100%; height: auto; border: 1px solid var(--ink); }
.dateline { font-family: var(--type); font-size: 13px; color: var(--ink-soft); margin: 6px 0 18px; }
h1, h2 { font-family: var(--cond); font-weight: 400; letter-spacing: .03em; margin: 0; text-wrap: balance; }
h2 { font-size: 28px; line-height: 1.1; border-top: 3px solid var(--ink); padding-top: 6px; margin-bottom: 10px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.lede { font-size: 18px; line-height: 1.45; margin: 0 0 18px; max-width: 62ch; }
.lede b { color: var(--red); }
.stats { display: grid; grid-template-columns: repeat(2, 1fr); border-top: 1px solid var(--ink); border-left: 1px solid var(--ink); margin-bottom: 26px; }
.d .stats { grid-template-columns: repeat(4, 1fr); }
.stat { padding: 10px 12px 12px; border-right: 1px solid var(--ink); border-bottom: 1px solid var(--ink); min-width: 0; }
.stat .n { font-family: var(--cond); font-size: 44px; line-height: 1; display: block; }
.stat .l { font-family: var(--type); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; display: block; margin-top: 4px; }
.stat .s { font-size: 13px; color: var(--ink-soft); display: block; margin-top: 2px; }
.cols { display: grid; grid-template-columns: 1fr; gap: 26px; margin-bottom: 26px; }
.d .cols { grid-template-columns: 2fr 1fr; gap: 32px; }
.cols > * { min-width: 0; }
.chart { width: 100%; height: auto; display: block; margin: 4px 0 6px; }
.chart .grid { stroke: var(--ink); stroke-opacity: .25; stroke-width: 1; }
.chart .ax { fill: var(--ink-soft); font-family: var(--type); }
.chart .l-park { fill: none; stroke: var(--ink); stroke-width: 2.4; stroke-linejoin: round; }
.chart .l-lg { fill: none; stroke: var(--ink-soft); stroke-width: 1.6; stroke-dasharray: 5 4; }
.chart .dot { fill: var(--red); }
.chart .note { fill: var(--red); font-family: var(--type); font-weight: 700; }
.chart .note-soft, .chart .lab-soft { fill: var(--ink-soft); font-family: var(--type); }
.chart .lab { fill: var(--ink); font-family: var(--type); font-weight: 700; }
.chart .bar { fill: var(--ink); }
.chart .bar.peak { fill: var(--red); }
.cap { font-size: 14px; color: var(--ink-soft); margin: 0 0 22px; max-width: 62ch; }
.card { border: 1px solid var(--ink); background: var(--paper-2); padding: 12px 14px; margin-bottom: 18px; }
.card h3 { font-family: var(--type); font-size: 13px; text-transform: uppercase; letter-spacing: .06em; margin: 0 0 8px; border-bottom: 1px dashed var(--ink); padding-bottom: 6px; }
.row { display: flex; justify-content: space-between; gap: 12px; padding: 4px 0; font-size: 15px; border-bottom: 1px dotted var(--ink-soft); }
.row:last-child { border-bottom: 0; }
.row b { font-family: var(--type); font-size: 13px; white-space: nowrap; }
.days { border-top: 1px solid var(--ink); margin: 0 0 26px; padding: 0; list-style: none; }
.days li { display: grid; grid-template-columns: 1fr; gap: 2px 14px; padding: 10px 0; border-bottom: 1px solid var(--ink); }
.d .days li { grid-template-columns: 150px 150px 1fr; }
.days .when { font-family: var(--type); font-size: 14px; font-weight: 700; }
.days .tag { font-family: var(--cond); font-size: 20px; letter-spacing: .06em; color: var(--red); line-height: 1.2; }
.days .what { font-size: 16px; }
.days .what small { display: block; color: var(--ink-soft); font-size: 13px; }
.planned { border: 2px dashed var(--ink); padding: 16px; margin-bottom: 18px; font-size: 15px; }
.planned b { font-family: var(--type); text-transform: uppercase; font-size: 12px; letter-spacing: .06em; display: block; margin-bottom: 4px; color: var(--red); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 26px; padding: 0; list-style: none; }
.chips a { display: inline-block; border: 1px solid var(--ink); padding: 6px 10px; font-family: var(--type); font-size: 13px; text-decoration: none; background: var(--paper); }
.chips a:hover { background: var(--ink); color: var(--paper); }
.credits { border-top: 4px solid var(--ink); padding-top: 10px; font-size: 13px; color: var(--ink-soft); }
.credits p { margin: 0 0 6px; max-width: 80ch; }
@media (max-width: 720px) {
  .d .stats { grid-template-columns: repeat(2, 1fr); }
  .d .cols { grid-template-columns: 1fr; }
  .d .days li { grid-template-columns: 1fr; }
}
"""


def build(f, img_b64, phone):
    cw, ch, cfs = (360, 240, 11) if phone else (640, 260, 12)
    li = line_chart(f, cw, ch, cfs)
    bc = bar_chart(f, cw, ch, cfs)
    rec, lng, fast, hom = f["record"], f["longest"], f["fastest"], f["homers"]
    slug = f["slug"]
    mm = lambda m: f"{m // 60}:{m % 60:02d}"
    stats = [
        (f"{f['games']:,}", "Games on record", f"{nice_date(f['first'])} to {nice_date(f['last'])}"),
        (f"{f['att_avg']:,}", "Average crowd", f"{f['att_games']:,} games with a crowd on record"),
        (f"{rec['att']:,}", "Record crowd", f"{nice_date(rec['date'])}, {team(rec['away'])} at {team(rec['home'])}"),
        (mm(lng["min"]), "Longest game", f"{nice_date(lng['date'])}, {team(lng['away'])} {lng['ar']}, {team(lng['home'])} {lng['hr_']}"),
        (mm(fast["min"]), "Fastest game with a winner", f"{nice_date(fast['date'])}, {team(fast['away'])} {fast['ar']}, {team(fast['home'])} {fast['hr_']}"),
        (str(slug[0]["runs"]), "Most runs in a game", f"Reached {len(slug)} times"),
        (str(hom["hr"]), "Most home runs in a game", f"{nice_date(hom['date'])}, {team(hom['away'])} at {team(hom['home'])}"),
        (f"{round(100 * f['night'] / f['games'])}%", "Played under lights", f"{f['night']} night games"),
    ]
    stat_html = "".join(f'<div class="stat"><span class="n">{html.escape(n)}</span><span class="l">{html.escape(l)}</span>'
                        f'<span class="s">{html.escape(s)}</span></div>' for n, l, s in stats)
    names = {"NY1": "New York Giants", "NYA": "New York Yankees", "NYN": "New York Mets"}
    tenants = "".join(f'<div class="row"><span>{names[k]}</span><b>{v[0]} to {v[1]}</b></div>'
                      for k, v in sorted(f["tenants"].items(), key=lambda kv: kv[1][0]) if k in names)
    tenant_games = "".join(f'<div class="row"><span>{names[k]}</span><b>{v[2]:,} home games</b></div>'
                           for k, v in sorted(f["tenants"].items(), key=lambda kv: -kv[1][2]) if k in names)
    seasons = len(f["years"])
    y62 = f["years"]["1962"]
    slug_txt = " and ".join(f"{nice_date(g['date'])} ({team(g['away'])} {g['ar']}, {team(g['home'])} {g['hr_']})" for g in slug)
    days = [
        (nice_date(f["first"]), "First game on record", "The Polo Grounds opens its gates for the Giants.", "Retrosheet game log"),
        ("Oct. 3, 1951", "Pennant playoff, game 3", "Giants 5, Dodgers 4. The game that decided the National League pennant.", "34,320 in the stands. Links to the Oct. 3 page of the site."),
        (nice_date(rec["date"]), "Record crowd", f"{rec['att']:,} came to see the {team(rec['away'])} play the {team(rec['home'])}.", f"Giants won {rec['hr_']} to {rec['ar']}."),
        (nice_date(lng["date"]), "Longest game", f"Dodgers at Giants, {mm(lng['min'])} long. Giants won {lng['hr_']} to {lng['ar']}.", "Tied for longest with May 11, 1957, also Dodgers at Giants."),
        (nice_date(fast["date"]), "Fastest game with a winner", f"{team(fast['away'])} at {team(fast['home'])}, over in {fast['min']} minutes.", f"Giants won {fast['hr_']} to {fast['ar']}."),
        ("Both days", "Slugfest", f"{slug[0]['runs']} runs: {slug_txt}.", "Most runs in any game at the park."),
        (nice_date(f["last"]), "Last game on record", "The final major league game at the Polo Grounds.", "Retrosheet game log"),
    ]
    day_html = "".join(f'<li><span class="when">{html.escape(a)}</span><span class="tag">{html.escape(b)}</span>'
                       f'<span class="what">{html.escape(c)}<small>{html.escape(d)}</small></span></li>' for a, b, c, d in days)
    wide = "" if phone else "d"
    mode = "phone" if phone else "desktop"
    return f"""<title>Polo Grounds {'Phone' if phone else 'Desktop'}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>{CSS}</style>
<div class="{wide} {mode}" id="top">
<div class="wrap">
<div class="mock">Design mock. Numbers are computed from Retrosheet. Captions are drafts.</div>
<div class="mast"><span>THIS DAY IN BASEBALL &middot; BALLPARKS</span><span>Park file {PARK}</span></div>
<div class="hero"><img src="data:image/webp;base64,{img_b64}" width="1200" height="675" alt="Line drawing of the Polo Grounds grandstands and field, drawn from a 1913 photograph"></div>
<h1 class="sr">The Polo Grounds, New York, 1911 to 1963</h1>
<p class="dateline">{f['games']:,} major league games on record &middot; {nice_date(f['first'])} to {nice_date(f['last'])}</p>

<p class="lede">The Polo Grounds hosted the Giants for 47 seasons, the Yankees for 11 and the Mets for 2. It was a <b>home run park</b>: baseball's hitters out-homered the league average here in {f['hitter_seasons']} of {seasons} seasons.</p>

<h2>By the numbers</h2>
<div class="stats">{stat_html}</div>

<div class="cols">
<div>
<h2>Home runs per game</h2>
{li}
<p class="cap">Home runs per game, both teams combined, at this park and in all of baseball. In 1962 the Mets and their visitors hit {y62['hr']:.2f} a game here. The whole majors hit {y62['lg']:.2f}.</p>
<h2>Who came to watch</h2>
{bc}
<p class="cap">Average crowd per game, by season, for games with a crowd on record. Crowds peaked in the postwar years.</p>
</div>
<div>
<div class="card"><h3>Who played here</h3>{tenants}</div>
<div class="card"><h3>Home games</h3>{tenant_games}</div>
<div class="planned"><b>Planned</b>An ink street map of Coogan's Hollow and the Harlem River goes here. Coordinates come from Wikidata and need a hand check for every park.</div>
</div>
</div>

<h2>Big days at this park</h2>
<ul class="days">{day_html}</ul>

<h2>More New York parks</h2>
<ul class="chips">
<li><a href="#top">Shea Stadium 1964 to 2008</a></li>
<li><a href="#top">Ebbets Field 1913 to 1957</a></li>
<li><a href="#top">Yankee Stadium 1923 to 2008</a></li>
<li><a href="#top">Hilltop Park 1903 to 1912</a></li>
<li><a href="#top">All 264 parks</a></li>
</ul>

<div class="credits">
<p>The information used here was obtained free of charge from and is copyrighted by Retrosheet.</p>
<p>Drawing: redrawn from a 1913 photograph, Library of Congress, Chronicling America and Prints and Photographs Division (<a href="https://www.loc.gov">loc.gov</a>).</p>
<p>Crowd and game length figures are missing for some early games. Counts only include games where the number is on record.</p>
</div>
</div>
</div>"""


def main():
    mine, league = load()
    f = facts(mine, league)
    img_b64 = base64.b64encode(IMAGE.read_bytes()).decode()
    (HERE / "polo-grounds-desktop.html").write_text(build(f, img_b64, False), encoding="utf-8")
    (HERE / "polo-grounds-phone.html").write_text(build(f, img_b64, True), encoding="utf-8")
    print("games", f["games"], "hitter seasons", f["hitter_seasons"], "of", len(f["years"]))
    print("record", f["record"]["date"], f["record"]["att"], "longest", f["longest"]["date"], f["longest"]["min"],
          "fastest", f["fastest"]["date"], f["fastest"]["min"], "slug", [g["date"] for g in f["slug"]], f["slug"][0]["runs"])


if __name__ == "__main__":
    main()
