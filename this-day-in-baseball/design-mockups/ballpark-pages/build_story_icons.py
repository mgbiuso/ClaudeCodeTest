#!/usr/bin/env python3
"""Mock only (not the live site): story datelines with small park icons, and the "This day at the ballpark" page.

Writes four files next to this script:
  story-icons-desktop.html / story-icons-phone.html        (home page stories with park icons)
  this-day-ballpark-desktop.html / this-day-ballpark-phone.html   (one page per park and calendar date, hash routed)
Run:  python3 build_story_icons.py [--urls urls.json]
Needs the same cached Retrosheet files as ballpark_data.py (about 40 seconds).
"""
import argparse
import base64
import collections
import csv
import io
import json
import re
import unicodedata
import zipfile
from pathlib import Path

import ballpark_data as bd
import build_ballpark_mocks as bm

HERE = Path(__file__).resolve().parent
ROOT = bd.ROOT
E = bm.E
DAYS = [("07-04", "July 4"), ("10-04", "Oct. 4"), ("10-19", "Oct. 19"), ("09-28", "Sept. 28")]
STORY_KINDS = {"opening", "closing", "milestone", "no-hitter", "perfect game", "cycle", "four homers", "marathon", "forfeit"}
POST = {"glws.zip": "World Series", "gldv.zip": "Division Series", "gllc.zip": "League Championship Series",
        "glwc.zip": "Wild Card Game", "glas.zip": "All-Star Game"}
# standings snapshots ("Cubs Lead Mets by Seven Games") get no park link (Mike, Nov. 9)
STANDINGS = re.compile(r"\bby [\w\u00bd -]{1,20}\bgames?\b|\bgames? (ahead|behind|back|up)\b|\bgames?\b.{0,12}\b(lead|edge)\b|\bhalf-game\b", re.I)
strip = lambda s: "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
norm = lambda s: bd.norm(strip(s))


# ---------------- game and story matching ----------------
def load_post():
    post = []
    for zname, label in POST.items():
        p = bd.RS / zname
        if not p.exists():
            continue
        with zipfile.ZipFile(p) as z:
            for n in sorted(z.namelist()):
                if not n.lower().endswith(".txt"):
                    continue
                for r in csv.reader(io.TextIOWrapper(z.open(n), encoding="latin-1")):
                    if len(r) < 45:
                        continue
                    num = lambda i: int(r[i]) if r[i].lstrip("-").isdigit() else 0
                    who = {bd.norm(r[i]) for i in [94, 96, 102, 104] + list(range(106, 159, 3)) if i < len(r) and r[i]}
                    post.append(dict(d=r[0], away=r[3], home=r[6], ar=num(9), hr_=num(10), park=r[16], att=num(17), who=who, series=label))
    # the logs list game number 0 for every playoff game, so count games inside each series instead
    groups = collections.defaultdict(list)
    for g in post:
        groups[(g["series"], g["d"][:4], frozenset((g["away"], g["home"])))].append(g)
    for (series, _y, _t), gs in groups.items():
        gs.sort(key=lambda g: g["d"])
        for i, g in enumerate(gs, 1):
            g["num"] = i if series != "All-Star Game" else 0
    return post


class Matcher:
    def __init__(self, D):
        self.D = D
        self.post = load_post()
        self.by_date = collections.defaultdict(list)
        for g in D.games + self.post:
            self.by_date[g["d"]].append(g)
        self.names = {}
        for code, m in D.meta.items():
            if m.get("name") and len(m["name"]) > 6 and code in D.by_park and len(D.by_park[code]) >= 3:
                self.names[norm(m["name"])] = code

    def match(self, s, mmdd):
        if not s["year"].isdigit() or int(s["year"]) > 2025:
            return None
        if STANDINGS.search(s.get("headline", "")):
            return None
        cands = self.by_date.get(f"{s['year']}{mmdd}", [])
        text = norm(s.get("text", "") + " " + s.get("headline", ""))
        as_text = lambda x: x if isinstance(x, str) else str((x or {}).get("title") or (x or {}).get("name") or "") if isinstance(x, dict) else ""
        names = set()
        for n in [s.get("about", "")] + list(s.get("abouts") or []) + list(s.get("links") or []):
            n = re.sub(r"\s*\(.*?\)", "", as_text(n))
            if n:
                names.add(norm(n))
        for pn, code in self.names.items():
            if re.search(r"\b" + re.escape(pn) + r"\b", text):
                gs = [g for g in cands if g["park"] == code]
                if gs:
                    return code
        best, bs = None, 0
        for g in cands:
            sc = 2 if any(n in g["who"] for n in names) else 0
            sc += sum(1 for c in (g["away"], g["home"]) if norm(self.D.nick(c, s["year"])) and re.search(r"\b" + re.escape(norm(self.D.nick(c, s["year"]))) + r"\b", text))
            if sc >= 2 and sc > bs:
                best, bs = g, sc
        return best["park"] if best else None


def day_stories(M, day):
    mmdd = day.replace("-", "")
    data = json.load(open(ROOT / "data" / "days" / f"{day}.json"))
    out, dropped = [], []
    for s in data["stories"]:
        if s.get("kind") != "event":
            continue
        if STANDINGS.search(s.get("headline", "")):
            dropped.append(s["headline"])
        s["park"] = M.match(s, mmdd)
        out.append(s)
    out.sort(key=lambda s: -s.get("score", 0))
    return out, dropped


def timeline(D, M, code, mmdd, stories):
    items, story_years = [], set()
    for s in stories:
        if s.get("park") == code:
            items.append((s["year"], "In the news", s["headline"], s.get("text", "")))
            story_years.add(s["year"])
    for e in D.events.get(mmdd, []):
        if e["park"] == code and e["kind"] in STORY_KINDS and (str(e["year"]) not in story_years or e["kind"] in ("opening", "closing")):
            items.append((str(e["year"]), bd.KIND_LABEL.get(e["kind"], e["kind"]), e["text"], ""))
    for g in M.post:
        if g["park"] == code and g["d"][4:] == mmdd and g["d"][:4] not in story_years:
            y = g["d"][:4]
            tag = g["series"] if g["series"] == "All-Star Game" else f"{g['series']}, game {g['num']}"
            items.append((y, tag, f"{D.nick(g['away'], y)} {g['ar']}, {D.nick(g['home'], y)} {g['hr_']}", ""))
    items.sort(key=lambda x: x[0])
    return items


def glance(D, code, mmdd):
    gs = [g for g in D.by_park.get(code, []) if g["d"][4:] == mmdd]
    rows = []
    if gs:
        yrs = sorted(g["d"][:4] for g in gs)
        rows.append((f"{len(gs)} game{'s' if len(gs) != 1 else ''}", f"played here on this date, {yrs[0]} to {yrs[-1]}" if yrs[0] != yrs[-1] else f"played here on this date, {yrs[0]}"))
        att = [g for g in gs if g["att"] > 0]
        if att:
            b = max(att, key=lambda g: g["att"]); y = b["d"][:4]
            rows.append((f"{b['att']:,}", f"biggest crowd on this date, {y}: {D.nick(b['away'], y)} at {D.nick(b['home'], y)}"))
        h = max(gs, key=lambda g: g["ar"] + g["hr_"]); y = h["d"][:4]
        rows.append((f"{h['ar'] + h['hr_']} runs", f"most on this date, {y}: {D.nick(h['away'], y)} {h['ar']}, {D.nick(h['home'], y)} {h['hr_']}"))
    return rows


# ---------------- pieces ----------------
STADIUM_SVG = ('<svg class="gen" viewBox="0 0 96 64" role="img" aria-label="Generic ballpark icon"><rect width="96" height="64" fill="none"/>'
               '<g fill="none" stroke="#1a1916" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round">'
               '<path d="M6 44 Q48 6 90 44"/><path d="M14 44 Q48 16 82 44" stroke-width="1.6"/><path d="M4 44 H92"/>'
               '<path d="M48 44 L30 58 H66 Z" fill="#c23b22" fill-opacity=".18"/><path d="M48 44 V30" stroke-width="1.6"/>'
               '<path d="M16 44 V14 M80 44 V14 M12 14 H20 M76 14 H84"/></g></svg>')

_thumbs = {}


def thumb(path, size=220):
    """Small copy of the drawing so the page stays light (about 6 to 10 KB each)."""
    if (path, size) not in _thumbs:
        from PIL import Image
        im = Image.open(path).convert("RGB"); im.thumbnail((size, size))
        buf = io.BytesIO(); im.save(buf, "WEBP", quality=70)
        _thumbs[(path, size)] = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    return _thumbs[(path, size)]


EXTRA_CSS = """
.stories { list-style:none; margin:0; padding:0; border-top:1px solid var(--ink); }
.st { display:grid; grid-template-columns:64px minmax(0,1fr) 112px; gap:4px 16px; padding:14px 0; border-bottom:1px solid var(--ink); align-items:start; }
.m .st { grid-template-columns:minmax(0,1fr) 84px; }
.m .st .yr { grid-column:1 / -1; }
.st.noicon { grid-template-columns:64px minmax(0,1fr); } .m .st.noicon { grid-template-columns:minmax(0,1fr); }
.st .yr { font:900 24px var(--hf); }
.st h3 { margin:0 0 4px; font:800 20px/1.2 var(--hf); }
.st p { margin:0; font:400 15.5px/1.45 var(--bf); max-width:64ch; }
.dl { font:900 11px var(--kf); letter-spacing:.14em; text-transform:uppercase; color:var(--red); }
.pi { display:block; text-decoration:none; text-align:center; border:2px solid var(--ink); background:rgba(255,255,255,.25); padding:4px; }
.pi img, .pi svg { display:block; width:100%; height:auto; aspect-ratio:3/2; object-fit:contain; }
.pi span { display:block; font:800 9.5px/1.2 var(--kf); letter-spacing:.08em; text-transform:uppercase; padding:4px 0 2px; }
.pi:hover, .pi:focus-visible { background:var(--ink); color:#f2ead0; } .pi:hover svg path, .pi:hover svg rect { stroke:#f2ead0; }
.legend { margin:12px 0 0; font:600 13px/1.4 var(--kf); color:var(--mut); }
.tdb .hero { margin-top:6px; } .gen-big { display:block; width:100%; max-width:420px; margin:6px 0; border:1px solid var(--ink); background:rgba(255,255,255,.2); padding:14px; }
.tl .tag { font:900 12px var(--kf); letter-spacing:.1em; text-transform:uppercase; color:var(--red); padding-top:5px; }
.tl .what b { display:block; font:800 19px/1.2 var(--hf); } .tl .what span { display:block; margin-top:3px; font:400 15.5px/1.45 var(--bf); }
.nav-note { font:600 13px var(--kf); color:var(--mut); margin:14px 0 0; }
.full { display:inline-block; margin-top:14px; font:900 12px var(--kf); letter-spacing:.12em; text-transform:uppercase; border:2px solid var(--ink); padding:8px 12px; text-decoration:none; }
.full.off { border-style:dashed; color:var(--mut); }
"""


def short(D, code):
    return D.name(code)


def dateline(D, code):
    m = D.meta.get(code, {})
    return (m.get("city") or "").upper()


def story_item(D, s, tdb_url):
    code = s.get("park")
    body = E(s.get("text", ""))
    head = E(s["headline"])
    if not code:
        return f'<li class="st noicon"><div class="yr">{E(s["year"])}</div><div><h3>{head}</h3><p>{body}</p></div></li>'
    nm = short(D, code); mmdd = s["_mmdd"]
    href = f"{tdb_url}#{code}-{mmdd}"
    files = D.drawings.get(code)
    art = f'<img src="{thumb(files[0])}" alt="Ink drawing of {E(nm)}" loading="lazy">' if files else bm_generic()
    dl = dateline(D, code)
    lead = f'<span class="dl">{E(dl)}.</span> ' if dl else ""
    return (f'<li class="st"><div class="yr">{E(s["year"])}</div><div><h3>{head}</h3><p>{lead}{body}</p></div>'
            f'<a class="pi" href="{E(href)}" aria-label="This day at {E(nm)}">{art}<span>This day at {E(nm)}</span></a></li>')


def bm_generic():
    return STADIUM_SVG


def home_page(D, M, phone, urls):
    mode = "m" if phone else "d"
    tdb = urls.get("tdb_phone" if phone else "tdb_desktop", "")
    panels, btns, report = [], [], {}
    for i, (day, label) in enumerate(DAYS):
        stories, dropped = day_stories(M, day)
        for s in stories:
            s["_mmdd"] = day.replace("-", "")
        shown = stories[:10]
        report[day] = dict(shown=len(shown), icons=sum(1 for s in shown if s["park"]), generic=sum(1 for s in shown if s["park"] and s["park"] not in D.drawings), dropped=dropped)
        items = "".join(story_item(D, s, tdb) for s in shown)
        panels.append(f'<div class="panel" data-day="{day}"{"" if i == 0 else " hidden"}><div class="sec"><h2>On This Date</h2><span>{E(label)}</span></div><ol class="stories">{items}</ol></div>')
        btns.append(f'<button type="button" data-day="{day}" aria-pressed="{"true" if i == 0 else "false"}">{E(label)}</button>')
    page = f"""<title>Story Park Icons {'Phone' if phone else 'Desktop'}</title>
<meta charset="utf-8">
<meta name="claude:viewport-fit-sides" content="cover">
{bm.FONTS}
<style>{bm.CSS}{EXTRA_CSS}</style>
<div class="{mode}"><div class="pg">{bm.GRAIN}
<div class="mock">Design mock. Stories come from the site's day files. Not the live site.</div>
<div class="plw"><div class="plate"><h1>This Day in Baseball</h1><p>Every game played on this date since 1871</p></div></div>
<div class="picker"><p>Mock only: pick a date</p><div class="btns" id="btns">{"".join(btns)}</div></div>
<p class="legend">A small park picture next to a story opens "This day at the ballpark" for that park and date. Parks without a drawing yet show a plain stadium sketch. Standings stories get no picture.</p>
{"".join(panels)}
<div class="foot"><p>{E(bm.RETRO)}</p><p>Park drawings are redrawn from public domain photographs (Library of Congress and Wikimedia Commons).</p></div>
</div></div>
<script>
(function () {{
  var btns = document.querySelectorAll('#btns button'), panels = document.querySelectorAll('.panel');
  btns.forEach(function (b) {{ b.addEventListener('click', function () {{
    btns.forEach(function (x) {{ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); }});
    panels.forEach(function (p) {{ p.hidden = p.getAttribute('data-day') !== b.getAttribute('data-day'); }});
  }}); }});
}})();
</script>"""
    return page, report


def tdb_section(D, M, code, mmdd, stories, parks_with_pages, parks_url, siblings):
    nm = short(D, code); pretty = f"{bd.MONTHS[int(mmdd[:2]) - 1]} {int(mmdd[2:])}"
    files = D.drawings.get(code)
    hero = (f'<img class="hero" src="{thumb(files[0], 900)}" alt="Ink drawing of {E(nm)}" loading="lazy">' if files
            else f'<div class="gen-big">{STADIUM_SVG}</div>')
    gl = glance(D, code, mmdd)
    stats = "".join(f'<div class="row"><b>{E(a)}</b><span>{E(b)}</span></div>' for a, b in gl)
    tl = timeline(D, M, code, mmdd, stories)
    lis = "".join(f'<li><div class="yr">{E(y)}</div><div class="tag">{E(t)}</div><div class="what"><b>{E(h)}</b>' + (f'<span>{E(x)}</span>' if x else "") + '</div></li>' for y, t, h, x in tl)
    tlhtml = f'<ul class="days tl">{lis}</ul>' if lis else '<p class="none-note">No standout events on record for this park on this date yet.</p>'
    full = (f'<a class="full" href="{E(parks_url)}#p-{code}">Full park page: stats, charts, biggest days</a>' if code in parks_with_pages
            else '<span class="full off">Full park page for this ballpark: not in the mock yet</span>')
    cur = ' aria-current="page"'
    sib = "".join(f'<li><a href="#{c}-{mmdd}"{cur if c == code else ""}>{E(short(D, c))}</a></li>' for c in siblings)
    where = ", ".join(x for x in (D.meta.get(code, {}).get("city"), D.meta.get(code, {}).get("state")) if x)
    return (f'<section class="pk tdb" id="{code}-{mmdd}" hidden><a class="back" href="#">Back to the stories</a>'
            f'<p class="where">This day at the ballpark &middot; {E(pretty)}</p><h1>{E(nm)}</h1><p class="where">{E(where)}</p>{hero}'
            f'<div class="box" style="margin-top:16px"><h3>At a glance</h3>{stats or "<div class=row>No games on record for this date.</div>"}</div>'
            f'<h2 class="s">Everything here on {E(pretty)}</h2>{tlhtml}{full}'
            f'<p class="nav-note">Mock only: other parks with stories on {E(pretty)}</p><ul class="chips">{sib}</ul></section>')


def tdb_page(D, M, phone, urls, day_data):
    mode = "m" if phone else "d"
    parks_url = urls.get("parks_phone" if phone else "parks_desktop", "")
    with_pages = set(re.findall(r'id="p-([A-Z0-9]+)"', (HERE / f"park-pages-{'phone' if phone else 'desktop'}.html").read_text()))
    secs, first = [], None
    for day, stories in day_data.items():
        mmdd = day.replace("-", "")
        parks = []
        for s in stories:
            if s.get("park") and s["park"] not in parks:
                parks.append(s["park"])
        counts = collections.Counter(e["park"] for e in D.events.get(mmdd, []) if e["kind"] in STORY_KINDS)
        for c, _ in counts.most_common(3):
            if c not in parks:
                parks.append(c)
        for c in parks:
            first = first or f"{c}-{mmdd}"
            secs.append(tdb_section(D, M, c, mmdd, stories, with_pages, parks_url, parks))
    page = f"""<title>This Day At The Ballpark {'Phone' if phone else 'Desktop'}</title>
<meta charset="utf-8">
<meta name="claude:viewport-fit-sides" content="cover">
{bm.FONTS}
<style>{bm.CSS}{EXTRA_CSS}</style>
<div class="{mode}"><div class="pg">{bm.GRAIN}
<div class="mock">Design mock. Numbers come from Retrosheet. Not the live site.</div>
<div class="plw"><div class="plate"><h1>This Day in Baseball</h1><p>This day at the ballpark</p></div></div>
{"".join(secs)}
<div class="foot"><p>{E(bm.RETRO)}</p><p>Park drawings are redrawn from public domain photographs (Library of Congress and Wikimedia Commons). Crowd and length figures are missing for some early games.</p></div>
</div></div>
<script>
(function () {{
  var secs = [].slice.call(document.querySelectorAll('.tdb')), home = {json.dumps(urls.get('home_phone' if phone else 'home_desktop', ''))};
  function show() {{
    var h = location.hash.replace('#', ''), hit = false;
    secs.forEach(function (s) {{ var on = s.id === h; s.hidden = !on; hit = hit || on; }});
    if (!hit) {{ secs[0].hidden = false; }}
    window.scrollTo(0, 0);
  }}
  document.querySelectorAll('.back').forEach(function (a) {{ if (home) a.setAttribute('href', home); }});
  window.addEventListener('hashchange', show); show();
}})();
</script>"""
    return page


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--urls", default="")
    a = ap.parse_args()
    urls = json.loads(Path(a.urls).read_text()) if a.urls and Path(a.urls).exists() else {}
    D = bd.build(); M = Matcher(D)
    for phone in (False, True):
        sfx = "phone" if phone else "desktop"
        home, report = home_page(D, M, phone, urls)
        (HERE / f"story-icons-{sfx}.html").write_text(home, encoding="utf-8")
        day_data = {}
        for day, _ in DAYS:
            st, _d = day_stories(M, day)
            for s in st:
                s["_mmdd"] = day.replace("-", "")
            day_data[day] = st
        (HERE / f"this-day-ballpark-{sfx}.html").write_text(tdb_page(D, M, phone, urls, day_data), encoding="utf-8")
    for day, r in report.items():
        print(day, {k: v for k, v in r.items() if k != "dropped"}, "standings dropped:", r["dropped"])


if __name__ == "__main__":
    main()
