#!/usr/bin/env python3
"""Build the mockups for "Ballparks on this date" (home page section) and the park pages. Mock only.

Writes four files next to this script:
  ballparks-day-desktop.html   ballparks-day-phone.html     (the home page section, with a date picker)
  park-pages-desktop.html      park-pages-phone.html        (one page per park, chosen by the #address)
The look copies the approved "Island paper" mock (Oct. 4): gray grain paper, Playfair Display headings,
Source Serif body, Libre Franklin labels, colored section bars.

Run:  python3 design-mockups/ballpark-pages/build_ballpark_mocks.py [--urls urls.json]
urls.json (optional) holds the published addresses so cards link to the park pages and back:
  {"parks_desktop": "...", "parks_phone": "...", "day_desktop": "...", "day_phone": "..."}
"""
import argparse
import base64
import html
import json
import math
import re
from pathlib import Path

import ballpark_data as bd

HERE = Path(__file__).resolve().parent
# date picker for the home page mock: (MMDD, label shown on the button)
DAYS = [("0704", "July 4"), ("1004", "Oct. 4"), ("1020", "Oct. 20"), ("1103", "Nov. 3"), ("1106", "Nov. 6")]
E = html.escape
RETRO = "The information used here was obtained free of charge from and is copyrighted by Retrosheet."

FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@500;600;800;900&family=Playfair+Display:ital,wght@0,700;0,800;0,900;1,700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&display=swap">'

CSS = """
:root { /* Layout: the Island paper newspaper look. Gray grain paper, colored section bars, boxed cards. */
  --paper:#dcdad3; --ink:#1a1916; --mut:#46433b; --red:#c23b22; --blue:#2554a5; --green:#1f6b4a; --ochre:#7a5200;
  --hf:'Playfair Display',Georgia,serif; --bf:'Source Serif 4',Georgia,serif; --kf:'Libre Franklin','Helvetica Neue',Arial,sans-serif;
  color-scheme: light; }
* { box-sizing:border-box; }
body { margin:0; background:var(--paper); color:var(--ink); font-family:var(--bf); font-size:16px; line-height:1.45; }
a { color:inherit; }
a:focus-visible, button:focus-visible { outline:3px solid var(--red); outline-offset:2px; }
.pg { position:relative; max-width:1200px; margin:0 auto; background:var(--paper); box-shadow:inset 0 0 110px rgba(70,58,36,.30);
  padding-block:14px 28px; padding-left:max(16px,env(safe-area-inset-left,0px)); padding-right:max(16px,env(safe-area-inset-right,0px)); }
.d .pg { padding-left:max(36px,env(safe-area-inset-left,0px)); padding-right:max(36px,env(safe-area-inset-right,0px)); }
.m .pg { max-width:430px; }
.tex { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; mix-blend-mode:multiply; opacity:.4; }
.mock { font:800 11px var(--kf); letter-spacing:.14em; text-transform:uppercase; background:var(--ink); color:#f2ead0; padding:6px 10px; margin-bottom:10px; }
.plw { border:2px solid var(--red); padding:4px; }
.plate { background:var(--blue); color:#fff; text-align:center; padding:12px 8px 14px; }
.plate h1 { margin:0; font:900 clamp(34px,8vw,84px)/1.15 var(--hf); }
.plate p { margin:8px 0 0; font:800 11px var(--kf); letter-spacing:.24em; text-transform:uppercase; }
.dline { display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap; font:600 12px var(--kf); letter-spacing:.14em; text-transform:uppercase; color:var(--mut); padding:9px 0 8px; border-bottom:1px solid var(--ink); }
.sec { background:var(--sc,var(--green)); color:#fff; display:flex; justify-content:space-between; align-items:baseline; gap:10px; flex-wrap:wrap; padding:12px 20px 10px; margin-top:28px; outline:1px solid rgba(255,255,255,.6); outline-offset:-5px; }
.sec h2 { margin:0; font:900 clamp(26px,5vw,38px)/1 var(--hf); }
.sec span { font:800 11px var(--kf); letter-spacing:.2em; text-transform:uppercase; }
.stub { margin-top:22px; padding:14px 20px; border:2px dashed var(--mut); color:var(--mut); display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; font:800 12px var(--kf); letter-spacing:.14em; text-transform:uppercase; }
.stub b { font:900 20px var(--hf); letter-spacing:0; text-transform:none; }
.picker { margin-top:22px; border:2px solid var(--ink); background:rgba(255,255,255,.2); padding:10px 12px; }
.picker p { margin:0 0 8px; font:800 11px var(--kf); letter-spacing:.14em; text-transform:uppercase; }
.picker .btns { display:flex; flex-wrap:wrap; gap:8px; }
.picker button { font:800 12px var(--kf); letter-spacing:.08em; text-transform:uppercase; padding:8px 12px; border:2px solid var(--ink); background:transparent; color:var(--ink); cursor:pointer; }
.picker button[aria-pressed="true"] { background:var(--ink); color:#f2ead0; }
.bp { display:grid; gap:16px; margin-top:16px; grid-template-columns:1fr; }
.d .bp.n3 { grid-template-columns:repeat(3,minmax(0,1fr)); }
.d .bp.n2 { grid-template-columns:repeat(2,minmax(0,1fr)); }
.bc { border:2px solid var(--ink); background:rgba(255,255,255,.2); display:flex; flex-direction:column; min-width:0; }
.bch { margin:0; background:var(--ink); color:#f2ead0; font:900 12px var(--kf); letter-spacing:.12em; text-transform:uppercase; padding:8px 12px; }
.bimg { display:block; border-bottom:4px solid var(--red); line-height:0; aspect-ratio:16/9; background:var(--paper); }
.bimg img { width:100%; height:100%; object-fit:contain; display:block; }
.ph0 { aspect-ratio:16/9; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; text-align:center; padding:12px;
  background:repeating-linear-gradient(45deg,rgba(26,25,22,.07) 0 8px,transparent 8px 16px); border-bottom:4px solid var(--red); line-height:1.3; }
.ph0 b { font:900 18px var(--hf); } .ph0 span { font:800 11px var(--kf); letter-spacing:.14em; text-transform:uppercase; color:var(--mut); }
.bbody { padding:10px 12px 12px; display:flex; flex-direction:column; flex:1; gap:2px; }
.k { margin:0; font:900 11px var(--kf); letter-spacing:.14em; text-transform:uppercase; color:var(--red); }
.bev { margin:2px 0 4px; font:800 21px/1.15 var(--hf); }
.bmeta { margin:0 0 8px; font:600 12px var(--kf); color:var(--mut); }
.rm { align-self:flex-start; margin-top:auto; font:900 10px var(--kf); letter-spacing:.12em; text-transform:uppercase; text-decoration:none; border-bottom:2px solid var(--red); padding-bottom:1px; }
.d .bp.n1 .bc { flex-direction:row; flex-wrap:wrap; }
.d .bp.n1 .bch { flex:1 0 100%; }
.d .bp.n1 .bimg, .d .bp.n1 .ph0 { flex:0 0 58%; border-bottom:0; border-right:4px solid var(--red); }
.d .bp.n1 .bbody { flex:1 1 0; justify-content:center; padding:16px 18px; }
.d .bp.n1 .bev { font-size:30px; }
.none-note { margin-top:16px; padding:18px 20px; border:2px dashed var(--mut); font:600 14px/1.45 var(--kf); color:var(--mut); }
.foot { margin-top:28px; border-top:5px solid var(--ink); padding-top:10px; font:500 12px/1.5 var(--kf); color:var(--mut); }
.foot p { margin:0 0 5px; }
/* park pages */
.back { display:inline-block; margin:2px 0 10px; font:900 11px var(--kf); letter-spacing:.12em; text-transform:uppercase; text-decoration:none; border-bottom:2px solid var(--red); }
.chips { display:flex; flex-wrap:wrap; gap:6px; margin:10px 0 0; padding:0; list-style:none; }
.chips a { display:inline-block; font:800 11px var(--kf); letter-spacing:.08em; text-transform:uppercase; border:1px solid var(--ink); padding:5px 9px; text-decoration:none; background:rgba(255,255,255,.25); }
.chips a[aria-current="page"] { background:var(--ink); color:#f2ead0; }
.pk h1 { margin:14px 0 2px; font:900 clamp(32px,7vw,64px)/1.05 var(--hf); text-transform:uppercase; letter-spacing:.005em; }
.pk .where { margin:0 0 12px; font:700 13px var(--kf); letter-spacing:.1em; text-transform:uppercase; color:var(--mut); }
.hero { display:block; width:100%; height:auto; border:1px solid var(--ink); border-bottom:4px solid var(--red); }
.gal { display:grid; gap:12px; margin-top:12px; grid-template-columns:1fr; }
.d .gal.g2 { grid-template-columns:1fr 1fr; }
.gal img { width:100%; height:auto; display:block; border:1px solid var(--ink); }
.lede { font-size:18px; line-height:1.5; margin:16px 0 4px; max-width:64ch; }
.today { margin-top:16px; border:2px solid var(--ink); background:rgba(194,59,34,.08); padding:10px 14px; }
.today h2 { margin:0 0 6px; font:900 12px var(--kf); letter-spacing:.14em; text-transform:uppercase; color:var(--red); }
.today p { margin:0 0 4px; font:600 15px/1.4 var(--bf); }
h2.s { margin:26px 0 8px; font:900 26px/1.1 var(--hf); border-top:4px solid var(--ink); padding-top:8px; }
.stats { display:grid; grid-template-columns:repeat(2,1fr); border-top:1px solid var(--ink); border-left:1px solid var(--ink); }
.d .stats { grid-template-columns:repeat(4,1fr); }
.stat { padding:10px 12px 12px; border-right:1px solid var(--ink); border-bottom:1px solid var(--ink); min-width:0; }
.stat .n { font:900 40px/1 var(--hf); display:block; color:var(--red); }
.stat .l { font:800 11px var(--kf); text-transform:uppercase; letter-spacing:.1em; display:block; margin-top:4px; }
.stat .s { font:500 12.5px/1.35 var(--kf); color:var(--mut); display:block; margin-top:2px; }
.cols { display:grid; grid-template-columns:1fr; gap:22px; }
.d .cols { grid-template-columns:2fr 1fr; gap:30px; }
.cols > * { min-width:0; }
.chart { width:100%; height:auto; display:block; margin:4px 0 6px; }
.chart .grid { stroke:var(--ink); stroke-opacity:.25; }
.chart .ax { fill:var(--mut); font-family:var(--kf); }
.chart .l-park { fill:none; stroke:var(--ink); stroke-width:2.4; stroke-linejoin:round; }
.chart .l-lg { fill:none; stroke:var(--mut); stroke-width:1.6; stroke-dasharray:5 4; }
.chart .dot { fill:var(--red); }
.chart .note { fill:var(--red); font-family:var(--kf); font-weight:800; }
.chart .lab { fill:var(--ink); font-family:var(--kf); font-weight:800; }
.chart .lab-soft { fill:var(--mut); font-family:var(--kf); }
.chart .bar { fill:var(--ink); } .chart .bar.peak { fill:var(--red); }
.cap { font:500 13px/1.45 var(--kf); color:var(--mut); margin:0 0 6px; }
.box { border:2px solid var(--ink); margin-bottom:14px; }
.box h3 { margin:0; background:var(--blue); color:#fff; font:900 12px var(--kf); letter-spacing:.14em; text-transform:uppercase; padding:6px 12px; }
.row { display:flex; justify-content:space-between; gap:10px; padding:6px 12px; border-bottom:1px dotted var(--ink); font:400 14.5px/1.3 var(--bf); }
.row:last-child { border-bottom:0; }
.row b { font:900 13px var(--kf); white-space:nowrap; color:var(--blue); }
.days { list-style:none; margin:0; padding:0; border-top:1px solid var(--ink); }
.days li { display:grid; grid-template-columns:1fr; gap:2px 14px; padding:10px 0; border-bottom:1px solid var(--ink); }
.d .days li { grid-template-columns:92px 190px 1fr; }
.days .yr { font:900 22px var(--hf); }
.days .tag { font:900 12px var(--kf); letter-spacing:.12em; text-transform:uppercase; color:var(--red); padding-top:5px; }
.days .what { font:400 16px/1.4 var(--bf); } .days .what small { display:block; font:500 12px var(--kf); color:var(--mut); }
@media (max-width:720px) { .d .bp.n3,.d .bp.n2 { grid-template-columns:1fr; } .d .bp.n1 .bc { flex-direction:column; }
  .d .bp.n1 .bimg,.d .bp.n1 .ph0 { flex:none; border-right:0; border-bottom:4px solid var(--red); } .d .stats { grid-template-columns:repeat(2,1fr); }
  .d .cols { grid-template-columns:1fr; } .d .days li { grid-template-columns:1fr; } .d .gal.g2 { grid-template-columns:1fr; } }
"""

GRAIN = ('<svg class="tex" aria-hidden="true" preserveAspectRatio="none"><defs><filter id="grain" x="0" y="0" width="100%" height="100%">'
         '<feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="7"/><feColorMatrix values="0 0 0 0 0.22  0 0 0 0 0.20  0 0 0 0 0.16  1.3 0 0 0 -0.52"/></filter>'
         '<filter id="blot" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.004 0.02" numOctaves="3" seed="3"/>'
         '<feColorMatrix values="0 0 0 0 0.45  0 0 0 0 0.38  0 0 0 0 0.24  0.9 0 0 0 -0.32"/></filter></defs>'
         '<rect width="100%" height="100%" filter="url(#blot)"/><rect width="100%" height="100%" filter="url(#grain)"/></svg>')

_b64 = {}


def data_uri(path):
    if path not in _b64:
        _b64[path] = "data:image/webp;base64," + base64.b64encode(Path(path).read_bytes()).decode()
    return _b64[path]


def years_text(D, code):
    gs = D.by_park[code]
    a, z = min(g["d"] for g in gs)[:4], max(g["d"] for g in gs)[:4]
    return a if a == z else f"{a} to {z}"


def place(D, code):
    m = D.meta.get(code, {})
    return ", ".join(x for x in (m.get("city"), m.get("state")) if x)


# ---------------- home page section ----------------
def card_title(D, e):
    """Card headline: 'On This Date: [superlative] in [park]'s history: [short detail]' (Mike's wording, Nov. 9)."""
    P = D.name(e["park"]); g = e["g"]; k = e["kind"]; y = g["d"][:4]
    nk = lambda c: D.nick(c, y)
    score = f"{nk(g['away'])} {g['ar']}, {nk(g['home'])} {g['hr_']}"
    at = f"{nk(g['away'])} at {nk(g['home'])}"
    t = e["text"]
    head = f"On This Date: %s in {P}'s history"
    if k == "opening":
        return head % "First game" + f": {score}"
    if k == "closing":
        return head % "Last game" + f": {score}"
    if k == "record crowd":
        return head % "Biggest crowd" + f": {g['att']:,}{' (est.)' if 'estimate' in t else ''}, {at}"
    if k == "filler" and t.startswith("Biggest crowd"):
        return head % "Biggest crowd for this date" + f": {g['att']:,}, {at}"
    if k == "filler":
        return head % "Highest scoring game for this date" + f": {score}"
    if k == "longest game":
        return head % "Longest game" + f": {g['mins'] // 60}:{g['mins'] % 60:02d}, {score}"
    if k == "most runs":
        return head % "Highest scoring game" + f": {score}"
    if k == "most homers":
        return head % "Most home runs in a game" + f": {g['hrs']}, {at}"
    if k == "marathon":
        return head % "Marathon" + f": {g['outs'] // 6} innings, {score}"
    if k == "forfeit":
        return head % "Forfeit" + f": {at}"
    if k == "cycle":
        return head % "Cycle" + ": " + t.replace(" hits for the cycle", "")
    if k in ("no-hitter", "perfect game"):
        who = re.sub(r" throws a (no-hitter|perfect game)$", "", t)
        return head % ("Perfect game" if k == "perfect game" else "No-hitter") + f": {who}"
    if k == "four homers":
        return head % "Four homers in a row" + ": " + t.replace("Four straight home runs: ", "")
    if k == "milestone":
        m = re.match(r"(.+?) gets his (.+)$", t) or re.match(r"(.+?) reaches (.+)$", t)
        return head % "Milestone" + (f": {m.group(1)}, {m.group(2)}" if m else f": {t}")
    return head % "Event" + f": {t}"


def card(D, e, parks_url):
    code = e["park"]; nm = D.name(code)
    href = f"{parks_url}#p-{code}" if parks_url else f"#p-{code}"
    files = D.drawings.get(code)
    if files:
        art = (f'<a class="bimg" href="{E(href)}" aria-label="Open the {E(nm)} page">'
               f'<img src="{data_uri(files[0])}" alt="Ink drawing of {E(nm)}" loading="lazy"></a>')
    else:
        art = f'<div class="ph0" role="img" aria-label="Drawing of {E(nm)} coming soon"><b>{E(nm)}</b><span>Drawing coming soon</span></div>'
    # kicker is just the year: the headline now says what happened (Mike's wording, Nov. 9)
    kicker = f'{e["year"]}'
    meta = " &middot; ".join(x for x in (E(place(D, code)), E(years_text(D, code))) if x)
    return (f'<article class="bc"><h3 class="bch">{E(nm)} - on this date</h3>{art}'
            f'<div class="bbody"><p class="k">{kicker}</p><p class="bev">{E(card_title(D, e))}</p>'
            f'<p class="bmeta">{meta}</p><a class="rm" href="{E(href)}">Visit the park page</a></div></article>')


def section_panel(D, day, label, parks_url, idx):
    picks = D.pick(day)
    n = len(picks)
    pretty = f"{bd.MONTHS[int(day[:2]) - 1]} {int(day[2:])}"
    if n == 0:
        body = (f'<div class="none-note">No park has a story on {E(pretty)}, so the Ballparks section is left out. '
                'The sections above and below it close up with no gap.</div>')
        head = ''
    else:
        head = (f'<div class="sec"><h2>Ballparks, on this date</h2><span>{E(pretty)} &middot; {n} park{"s" if n != 1 else ""}</span></div>')
        body = f'<div class="bp n{n}">' + "".join(card(D, e, parks_url) for e in picks) + "</div>"
    return f'<div class="panel" data-day="{day}"{"" if idx == 0 else " hidden"}>{head}{body}</div>', picks


def day_page(D, phone, urls):
    mode = "m" if phone else "d"
    parks_url = urls.get("parks_phone" if phone else "parks_desktop", "")
    panels, buttons, all_picks = [], [], {}
    for i, (day, label) in enumerate(DAYS):
        p, picks = section_panel(D, day, label, parks_url, i)
        panels.append(p); all_picks[day] = picks
        buttons.append(f'<button type="button" data-day="{day}" aria-pressed="{"true" if i == 0 else "false"}">{E(label)} &middot; {len(picks)} park{"s" if len(picks) != 1 else ""}</button>')
    first_label = DAYS[0][1]
    page = f"""<title>Ballparks On This Date {'Phone' if phone else 'Desktop'}</title>
<meta name="claude:viewport-fit-sides" content="cover">
{FONTS}
<style>{CSS}</style>
<div class="{mode}"><div class="pg">{GRAIN}
<div class="mock">Design mock. Numbers come from Retrosheet. Not the live site.</div>
<div class="plw"><div class="plate"><h1>This Day in Baseball</h1><p>Every game played on this date since 1871</p></div></div>
<div class="dline"><span id="dlab">{E(first_label)}</span><span>History Edition</span></div>
<div class="picker"><p>Mock only: pick a date to see how the section adjusts</p><div class="btns" id="btns">{"".join(buttons)}</div></div>
<div class="stub"><span>Section above</span><b>The Papers of the Day</b></div>
{"".join(panels)}
<div class="stub"><span>Section below</span><b>The Scoreboard</b></div>
<div class="foot"><p>{E(RETRO)}</p><p>Park drawings are redrawn from public domain photographs (Library of Congress and Wikimedia Commons).</p></div>
</div></div>
<script>
(function () {{
  var btns = document.querySelectorAll('#btns button'), panels = document.querySelectorAll('.panel'), lab = document.getElementById('dlab');
  btns.forEach(function (b) {{
    b.addEventListener('click', function () {{
      btns.forEach(function (x) {{ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); }});
      panels.forEach(function (p) {{ p.hidden = p.getAttribute('data-day') !== b.getAttribute('data-day'); }});
      lab.textContent = b.textContent.split(' \\u00b7 ')[0];
    }});
  }});
}})();
</script>"""
    return page, all_picks


# ---------------- park pages ----------------
def ticks(a, b):
    step = 10 if b - a >= 30 else 5 if b - a >= 12 else 2
    return [y for y in range((a // step + 1) * step, b, step)]


def line_chart(f, w, h, fs, uid):
    ys = [int(y) for y in f["years"]]
    L, R, T, B = 38, 14, 16, 26
    x0, x1 = min(ys), max(ys)
    peak = max(max(v["hr"], v["lg"]) for v in f["years"].values())
    top = max(1.0, math.ceil(peak * 2) / 2)
    X = lambda y: L + (y - x0) / max(1, x1 - x0) * (w - L - R)
    Y = lambda v: T + (1 - v / top) * (h - T - B)
    o = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-labelledby="{uid}"><title id="{uid}">Home runs per game at this park compared with all of baseball, {x0} to {x1}</title>']
    v = 0.0
    while v <= top + 0.001:
        o.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>')
        o.append(f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" class="ax" font-size="{fs}">{v:.1f}</text>')
        v += 0.5
    for yr in ticks(x0, x1):
        o.append(f'<text x="{X(yr):.1f}" y="{h - 8}" text-anchor="middle" class="ax" font-size="{fs}">{yr}</text>')
    for key, cls in (("lg", "l-lg"), ("hr", "l-park")):
        segs, cur = [], []
        for y in ys:
            if cur and y - cur[-1][0] > 1:
                segs.append(cur); cur = []
            cur.append((y, f["years"][str(y)][key]))
        segs.append(cur)
        for s in segs:
            if len(s) > 1:
                o.append(f'<polyline points="{" ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in s)}" class="{cls}"/>')
    pk = max(ys, key=lambda y: f["years"][str(y)]["hr"] - f["years"][str(y)]["lg"] if f["years"][str(y)]["games"] >= 30 else -9)
    pv = f["years"][str(pk)]
    if pv["games"] >= 30:
        px, py = X(pk), Y(pv["hr"]); anchor = "end" if px > w / 2 else "start"
        o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.6" class="dot"/>')
        o.append(f'<text x="{px + (-8 if anchor == "end" else 8):.1f}" y="{py - 8:.1f}" text-anchor="{anchor}" class="note" font-size="{fs}">{pk}: {pv["hr"]:.2f} here</text>')
    o.append(f'<text x="{L + 4}" y="{T + 8}" class="lab" font-size="{fs}">Solid: this park. Dashed: all of baseball</text>')
    o.append("</svg>")
    return "".join(o)


def bar_chart(f, w, h, fs, uid):
    yrs = [(int(y), v["att"]) for y, v in f["years"].items() if v["att"] and v["games"] >= 20]
    if len(yrs) < 3:
        return ""
    L, R, T, B = 40, 14, 16, 26
    x0, x1 = min(y for y, _ in yrs), max(y for y, _ in yrs)
    peak = max(a for _, a in yrs)
    top = max(10000, math.ceil(peak / 10000) * 10000)
    bw = max(2.5, (w - L - R) / max(8, x1 - x0 + 1) * 0.72)
    X = lambda y: L + bw / 2 + 3 + (y - x0) / max(1, x1 - x0) * (w - L - R - bw - 6)
    Y = lambda v: T + (1 - v / top) * (h - T - B)
    o = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-labelledby="{uid}"><title id="{uid}">Average crowd per game at this park by season</title>']
    step = top // 3 if top % 3000 == 0 and top > 12000 else 10000 if top <= 40000 else 20000
    v = 0
    while v <= top:
        o.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>')
        o.append(f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" class="ax" font-size="{fs}">{v // 1000}K</text>')
        v += step
    for yr in ticks(x0, x1):
        o.append(f'<text x="{X(yr):.1f}" y="{h - 8}" text-anchor="middle" class="ax" font-size="{fs}">{yr}</text>')
    pk = max(yrs, key=lambda a: a[1])
    for yr, a in yrs:
        o.append(f'<rect x="{X(yr) - bw / 2:.1f}" y="{Y(a):.1f}" width="{bw:.1f}" height="{Y(0) - Y(a):.1f}" class="bar{" peak" if yr == pk[0] else ""}"/>')
    px = X(pk[0]); anchor = "end" if px > w / 2 else "start"
    o.append(f'<text x="{px + (-6 if anchor == "end" else 6):.1f}" y="{Y(pk[1]) - 6:.1f}" text-anchor="{anchor}" class="note" font-size="{fs}">{pk[0]}: {pk[1]:,}</text>')
    o.append("</svg>")
    return "".join(o)


def mm(m):
    return f"{m // 60}:{m % 60:02d}"


def park_section(D, code, mock_parks, today, phone, urls, first, extra=""):
    nm = D.name(code); f = bd.park_facts(D, code)
    cw, ch, fs = (360, 240, 11) if phone else (640, 260, 12)
    team = D.team
    files = D.drawings.get(code, [])[:3]
    hero = ""
    if files:
        hero = f'<img class="hero" src="{data_uri(files[0])}" alt="Ink drawing of {E(nm)}">'
        if len(files) > 1:
            hero += f'<div class="gal g{len(files) - 1}">' + "".join(
                f'<img src="{data_uri(p)}" alt="Another ink drawing of {E(nm)}" loading="lazy">' for p in files[1:]) + "</div>"
    else:
        hero = f'<div class="ph0" role="img" aria-label="Drawing of {E(nm)} coming soon"><b>{E(nm)}</b><span>Drawing coming soon</span></div>'
    y0, y1 = f["first"][:4], f["last"][:4]
    tenants = ", ".join(f"{team(k, v[0])} ({v[0]} to {v[1]})" if v[0] != v[1] else f"{team(k, v[0])} ({v[0]})" for k, v in f["tenants"][:4])
    lede = f"{nm} hosted {f['games']:,} major league games between {y0} and {y1}."
    if tenants:
        lede += f" Home teams: {tenants}."
    if f["seasons"] >= 5:
        if f["above"] / f["seasons"] >= 0.65:
            lede += f" Hitters had the edge here: more home runs per game than the league average in {f['above']} of {f['seasons']} seasons."
        elif f["below"] / f["seasons"] >= 0.65:
            lede += f" Pitchers had the edge here: fewer home runs per game than the league average in {f['below']} of {f['seasons']} seasons."
    # on this date box (the reason the park is on the home page in the mock)
    tl = "".join(f'<p><b>{E(lab)}:</b> {E(str(e["year"]))}, {E(e["text"])}</p>' for lab, e in today.get(code, []))
    today_box = f'<div class="today"><h2>{E(nm)} - on this date</h2>{tl}</div>' if tl else ""
    stats = [(f"{f['games']:,}", "Games on record", f"{bd.nice_date(f['first'])} to {bd.nice_date(f['last'])}")]
    if f["att_games"] >= 20:
        stats.append((f"{f['att_avg']:,}", "Average crowd", f"{f['att_games']:,} games with a crowd on record"))
        r = f["record"]; stats.append((f"{r['att']:,}", "Record crowd", f"{bd.nice_date(r['d'])}, {team(r['away'], r['d'][:4])} at {team(r['home'], r['d'][:4])}"))
    if f["longest"]:
        g = f["longest"]; stats.append((mm(g["mins"]), "Longest game", f"{bd.nice_date(g['d'])}, {team(g['away'], g['d'][:4])} {g['ar']}, {team(g['home'], g['d'][:4])} {g['hr_']}"))
        g = f["fastest"]; stats.append((mm(g["mins"]), "Fastest game with a winner", f"{bd.nice_date(g['d'])}, {team(g['away'], g['d'][:4])} {g['ar']}, {team(g['home'], g['d'][:4])} {g['hr_']}"))
    g = f["slug"]; stats.append((str(g["ar"] + g["hr_"]), "Most runs in a game", f"{bd.nice_date(g['d'])}, {team(g['away'], g['d'][:4])} {g['ar']}, {team(g['home'], g['d'][:4])} {g['hr_']}"))
    g = f["homers"]
    if g["hrs"] >= 3:
        stats.append((str(g["hrs"]), "Most home runs in a game", f"{bd.nice_date(g['d'])}, {team(g['away'], g['d'][:4])} at {team(g['home'], g['d'][:4])}"))
    if f["night"]:
        stats.append((f"{round(100 * f['night'] / f['games'])}%", "Played under lights", f"{f['night']:,} night games"))
    stat_html = "".join(f'<div class="stat"><span class="n">{E(a)}</span><span class="l">{E(b)}</span><span class="s">{E(c)}</span></div>' for a, b, c in stats)
    charts = ""
    if f["seasons"] >= 3:
        lc = line_chart(f, cw, ch, fs, f"hr-{code}"); bc = bar_chart(f, cw, ch, fs, f"at-{code}")
        charts = (f'<h2 class="s">Home runs per game</h2>{lc}<p class="cap">Both teams combined, at this park and in all of baseball, by season.</p>'
                  + (f'<h2 class="s">Who came to watch</h2>{bc}<p class="cap">Average crowd per game, by season, for games with a crowd on record.</p>' if bc else ""))
    tenant_box = "".join(f'<div class="row"><span>{E(team(k, v[0]))}</span><b>{v[0]} to {v[1]}</b></div>' for k, v in f["tenants"][:5])
    side = (f'<div class="box"><h3>Who played here</h3>{tenant_box}</div>' if tenant_box else "")
    # big days: this park's highest scoring events
    seen, rows = set(), []
    evs = sorted((e for ev in D.events.values() for e in ev if e["park"] == code), key=lambda e: -e["score"])
    for e in evs:
        key = (e["date"], e["kind"])
        if key in seen:
            continue
        seen.add(key); rows.append(e)
        if len(rows) >= 8:
            break
    rows.sort(key=lambda e: e["date"])
    days = "".join(f'<li><span class="yr">{e["year"]}</span><span class="tag">{E(bd.KIND_LABEL[e["kind"]])}</span><span class="what">{E(e["text"])}<small>{E(bd.nice_date(e["date"]))}</small></span></li>' for e in rows)
    big = f'<h2 class="s">Big days at this park</h2><ul class="days">{days}</ul>' if days else ""
    cur = ' aria-current="page"'
    chips = "".join(f'<li><a href="#p-{c}"{cur if c == code else ""}>{E(D.name(c))}</a></li>' for c in mock_parks)
    back_url = urls.get("day_phone" if phone else "day_desktop", "")
    back = f'<a class="back" href="{E(back_url)}">Back to the day page</a>' if back_url else ""
    return (f'<section class="pk park" id="p-{code}"{"" if first else " hidden"}>{back}'
            f'<div class="mock">Design mock of a park page. Numbers come from Retrosheet.</div>{hero}'
            f'<h1>{E(nm)}</h1><p class="where">{E(place(D, code))} &middot; {E(years_text(D, code))}</p>'
            f'<p class="lede">{E(lede)}</p>{today_box}{extra}<h2 class="s">By the numbers</h2><div class="stats">{stat_html}</div>'
            f'<div class="cols"><div>{charts}</div><div style="padding-top:26px">{side}</div></div>{big}'
            f'<h2 class="s">More parks in this mock</h2><ul class="chips">{chips}</ul></section>')


def parks_page(D, phone, urls, all_picks):
    mode = "m" if phone else "d"
    mock_parks, today = [], {}
    for day, label in DAYS:
        pretty = f"{bd.MONTHS[int(day[:2]) - 1]} {int(day[2:])}"
        for e in all_picks[day]:
            if e["park"] not in mock_parks:
                mock_parks.append(e["park"])
            today.setdefault(e["park"], []).append((pretty, e))
    secs = "".join(park_section(D, c, mock_parks, today, phone, urls, i == 0) for i, c in enumerate(mock_parks))
    page = f"""<title>Park Pages {'Phone' if phone else 'Desktop'}</title>
<meta name="claude:viewport-fit-sides" content="cover">
{FONTS}
<style>{CSS}</style>
<div class="{mode}"><div class="pg">{GRAIN}
<div class="plw"><div class="plate"><h1>This Day in Baseball</h1><p>Ballparks</p></div></div>
{secs}
<div class="foot"><p>{E(RETRO)}</p><p>Drawings are redrawn from public domain photographs (Library of Congress and Wikimedia Commons). The source is printed in each drawing's corner.</p><p>Crowd and game length figures are missing for some early games. Counts only include games where the number is on record.</p></div>
</div></div>
<script>
(function () {{
  var secs = [].slice.call(document.querySelectorAll('.park'));
  function show() {{
    var h = location.hash.replace('#', ''), hit = false;
    secs.forEach(function (s) {{ var on = s.id === h; s.hidden = !on; hit = hit || on; }});
    if (!hit) {{ secs[0].hidden = false; }}
    window.scrollTo(0, 0);
  }}
  window.addEventListener('hashchange', show);
  show();
}})();
</script>"""
    return page, mock_parks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", default="")
    a = ap.parse_args()
    urls = json.loads(Path(a.urls).read_text()) if a.urls and Path(a.urls).exists() else {}
    D = bd.build()
    for phone in (False, True):
        day, picks = day_page(D, phone, urls)
        pk, mock_parks = parks_page(D, phone, urls, picks)
        suffix = "phone" if phone else "desktop"
        (HERE / f"ballparks-day-{suffix}.html").write_text(day, encoding="utf-8")
        (HERE / f"park-pages-{suffix}.html").write_text(pk, encoding="utf-8")
    for day, label in DAYS:
        print(label, [(D.name(e["park"]), e["kind"], e["year"]) for e in picks[day]])
    print("parks in the mock:", [D.name(c) for c in mock_parks])


if __name__ == "__main__":
    main()
