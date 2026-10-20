#!/usr/bin/env python3
"""Gather and rank baseball stories for a month/day from Wikipedia and Wikidata.

Gentle on Wikimedia: one request at a time, a pause between requests, backoff
on 429, batched titles, and a disk cache keyed by URL.
Failures are counted and reported, never silently swallowed.
"""
import argparse
import calendar
import hashlib
import html
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
UA = {"User-Agent": "this-day-in-baseball/1.0 (mgbiuso@gmail.com)"}
PAUSE = 0.5
FIRST_YEAR, LAST_YEAR = 1871, 2025
BASEBALL = "Q5369"
STATS = {"net": 0, "cached": 0, "failed": []}
MONTHS = {m: i for i, m in enumerate(calendar.month_name) if m}


def get(url):
    CACHE.mkdir(exist_ok=True)
    key = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".json")
    if key.exists():
        STATS["cached"] += 1
        return json.loads(key.read_text())
    delay = 5
    for _ in range(5):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = json.load(r)
            STATS["net"] += 1
            key.write_text(json.dumps(data))
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  429, waiting {delay}s", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            STATS["failed"].append(f"HTTP {e.code} {url[:90]}")
            return None
        except Exception as e:
            time.sleep(2)
            last = str(e)
    STATS["failed"].append(f"gave up {url[:90]} ({last})")
    return None


def trim(text, limit=420):
    """Cut at a sentence end under the limit; otherwise at a word with an ellipsis."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    ends = [m.end() for m in re.finditer(r"(?<![A-Z])(?<!\bSt)(?<!\bMr)(?<!\bJr)[.!?](?=\s+[A-Z\"“])", cut)]
    if ends and ends[-1] > limit * 0.5:
        return cut[:ends[-1]].strip()
    return cut.rsplit(" ", 1)[0].rstrip(",;:") + "…"


YEAR_TEMPLATES = r"(?:baseball year|by|mlby|wsy|alcsy|nlcsy|alds?y|nlds?y|mlb year)"


def expand_templates(s):
    """Keep the text of the few templates that carry content (years, fractions, conversions); the rest are dropped."""
    s = re.sub(r"\{\{\s*" + YEAR_TEMPLATES + r"\s*\|\s*(\d{4})[^{}]*\}\}", r"\1", s, flags=re.I)
    s = re.sub(r"\{\{\s*(?:fraction|frac)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\}\}", r"\1 \2/\3", s, flags=re.I)
    s = re.sub(r"\{\{\s*(?:fraction|frac)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\}\}", r"\1/\2", s, flags=re.I)
    s = re.sub(r"\{\{\s*convert\s*\|\s*([\d.,]+)\s*\|\s*([A-Za-z]+)[^{}]*\}\}", r"\1 \2", s, flags=re.I)
    return s


def strip_wiki(s):
    s = expand_templates(s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"'{2,}", "", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip(" *–-")


def wiki_links(s):
    return [l.strip().replace("_", " ") for l in re.findall(r"\[\[([^|\]#]+)", s)]


OBIT = re.compile(r"^[^,.]{3,45}, \d{2,3}, ")  # "Name, 86, pitcher ..."


# ---------- source 1: "YYYY in baseball" pages ----------

def year_pages():
    """Yield (title, wikitext) for every 'YYYY in baseball' page. Same URLs for every date, so cached once."""
    titles = [f"{y} in baseball" for y in range(FIRST_YEAR, LAST_YEAR + 1)]
    for i in range(0, len(titles), 20):
        r = get("https://en.wikipedia.org/w/api.php?action=query&format=json&redirects=1&prop=revisions&rvprop=content&rvslots=main&titles="
                + urllib.parse.quote("|".join(titles[i:i + 20])))
        for p in (r or {}).get("query", {}).get("pages", {}).values():
            if "revisions" in p:
                yield p["title"], p["revisions"][0]["slots"]["main"]["*"]


def parse_year_page(title, text, month, day):
    """Dated lines for month/day. Skips Births sections. Handles 'March 15-16 –' ranges."""
    mname = calendar.month_name[month]
    pat = re.compile(rf"^\*+\s*{mname} (\d{{1,2}})(?:\s*[–-]\s*(\d{{1,2}}))?\s*[–:—-]\s*(.+)", re.I)
    heading, out = "", []
    for line in text.split("\n"):
        h = re.match(r"^=+\s*([^=]+?)\s*=+\s*$", line)
        if h:
            heading = h.group(1).lower()
            continue
        if "birth" in heading:
            continue
        m = pat.match(line.strip())
        if not m or int(m.group(1)) != day:
            continue
        body = strip_wiki(m.group(3))
        if len(body) < 25:
            continue
        is_death = "death" in heading or bool(OBIT.match(body))
        out.append({"src": "yearpage", "kind": "death" if is_death else "event",
                    "year": title[:4], "text": trim(body), "links": wiki_links(m.group(3))[:3]})
    return out


# ---------- source 2: On This Day feed ----------

def wikidata_claims(qids):
    claims = {}
    qids = list(qids)
    for i in range(0, len(qids), 50):
        r = get("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims&ids=" + "|".join(qids[i:i + 50]))
        if r:
            claims.update({q: e.get("claims", {}) for q, e in r.get("entities", {}).items()})
    return claims


def is_baseball(claims):
    vals = {x["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for x in claims.get("P641", [])}
    return BASEBALL in vals


def onthisday(month, day):
    d = get(f"https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/{month:02d}/{day:02d}")
    if d is None:
        return []
    items = []
    for k in ("events", "deaths"):  # births deliberately excluded
        for e in d.get(k, []):
            p = e["pages"][0] if e.get("pages") else None
            if p and p.get("wikibase_item"):
                items.append((k, e, p))
    claims = wikidata_claims({p["wikibase_item"] for _, _, p in items})
    out = []
    for k, e, p in items:
        if is_baseball(claims.get(p["wikibase_item"], {})):
            out.append({"src": "onthisday", "kind": "death" if k == "deaths" else "event", "year": str(e["year"]),
                        "text": trim(strip_wiki(e["text"])), "links": [p["titles"]["normalized"]]})
    return out


# ---------- source 3: sentences from baseball articles that state the date ----------

def article_sentences(month, day, max_pages=40):
    mname = calendar.month_name[month]
    queries = [f'"opened on {mname} {day}" baseball', f'"on {mname} {day}" ballpark', f'"on {mname} {day}" "Major League Baseball"',
               f'"founded on {mname} {day}" baseball', f'"on {mname} {day}" franchise baseball']
    titles = {}
    for q in queries:
        r = get("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=30&srnamespace=0&srsearch=" + urllib.parse.quote(q))
        for x in (r or {}).get("query", {}).get("search", []):
            titles[x["title"]] = 1
    titles = list(titles)
    qid = {}
    for i in range(0, len(titles), 50):
        r = get("https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageprops&ppprop=wikibase_item&redirects=1&titles="
                + urllib.parse.quote("|".join(titles[i:i + 50])))
        q = (r or {}).get("query", {})
        redir = {x["to"]: x["from"] for x in q.get("redirects", [])}
        for p in q.get("pages", {}).values():
            w = p.get("pageprops", {}).get("wikibase_item")
            if w:
                qid[w] = redir.get(p["title"], p["title"])
    claims = wikidata_claims(qid)
    keep = [t for q, t in qid.items() if is_baseball(claims.get(q, {}))][:max_pages]
    pat = re.compile(rf"[^.\n]*\b{mname} {day}, (\d{{4}})[^.\n]*\.")
    out = []
    for t in keep:
        r = get("https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&format=json&titles=" + urllib.parse.quote(t))
        ex = next(iter((r or {}).get("query", {}).get("pages", {}).values()), {}).get("extract", "")
        m = pat.search(ex)
        sent = m.group(0).strip() if m else ""
        title_words = [w for w in re.sub(r"\(.*?\)", "", t).split() if len(w) > 2]
        if (m and len(sent) >= 50 and not NOISE.search(sent) and not PRONOUN.match(sent)
                and any(w in sent for w in title_words)):
            out.append({"src": "article", "kind": "event", "year": m.group(1), "text": trim(m.group(0).strip()),
                        "links": [t], "about": t})
    return out


PRONOUN = re.compile(r"^(He|She|It|They|His|Her|Its|Their|This|That|These|Those|Finally|Henderson|Alexander)\b")
NOISE = re.compile(r"\b(schedule|announced that|NYCFC|soccer|attendance|concert|perform|musician|orchestra|logos?|uniforms?|interviewed|resident of|struck and killed|unveiled)\b", re.I)


# ---------- ranking ----------

def pageviews(titles):
    titles = list(dict.fromkeys(t for t in titles if t))
    out = {}
    for i in range(0, len(titles), 50):
        r = get("https://en.wikipedia.org/w/api.php?action=query&format=json&redirects=1&prop=pageviews&pvipdays=60&titles="
                + urllib.parse.quote("|".join(titles[i:i + 50])))
        q = (r or {}).get("query", {})
        back = {n["to"]: n["from"] for n in q.get("normalized", [])}
        redir = {x["to"]: x["from"] for x in q.get("redirects", [])}
        for p in q.get("pages", {}).values():
            total = sum(v or 0 for v in (p.get("pageviews") or {}).values())
            t = p.get("title")
            for name in {t, redir.get(t), back.get(redir.get(t, t))}:
                if name:
                    out[name] = total
    return out


KEYWORDS = {"world series": 40, "perfect game": 40, "no-hitter": 35, "hall of fame": 30, "record": 25, "retire": 25,
            "mvp": 25, "cy young": 25, "home run": 20, "strike": 15, "trade": 15, "acquire": 12, "manager": 12,
            "stadium": 15, "ballpark": 15, "franchise": 15, "league": 10, "pennant": 25, "champion": 25}
DEATH_MIN_VIEWS = 100  # 60-day views; baseball players' pages are small
MIN_EVENT_CHARS = 60
STRONG = 25
MAX_ARTICLE = 6
TEAM_CLASSES = {"Q13027888", "Q847017", "Q12973014", "Q17156793"}  # baseball team, sports club, sports team, baseball club


SEASONISH = re.compile(r"(\bseason$|Championship Series|^World Series$|^Major League Baseball$)", re.I)


def team_titles(titles):
    """Subset of titles that are teams/clubs on Wikidata (their pageviews say nothing about the event)."""
    qid = {}
    titles = list(dict.fromkeys(titles))
    for i in range(0, len(titles), 50):
        r = get("https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageprops&ppprop=wikibase_item&redirects=1&titles="
                + urllib.parse.quote("|".join(titles[i:i + 50])))
        q = (r or {}).get("query", {})
        redir = {x["to"]: x["from"] for x in q.get("redirects", [])}
        for p in q.get("pages", {}).values():
            w = p.get("pageprops", {}).get("wikibase_item")
            if w:
                qid[w] = (p["title"], redir.get(p["title"]))
    teams = set()
    for q, claims in wikidata_claims(qid).items():
        classes = {x["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for x in claims.get("P31", [])}
        if classes & TEAM_CLASSES:
            teams.update(t for t in qid[q] if t)
    return teams


def names(text):
    return {w for w in re.findall(r"\b[A-Z][a-z]{2,}\b", text)} - {"The", "In", "On", "After", "When", "With", "Game", "World", "Series"}


def merge_early_series(rows):
    """Fold terse pre-1900 'series' result lines into one story, keeping the most informative."""
    early = [r for r in rows if r["kind"] == "event" and r["src"] == "yearpage" and int(r["year"]) < 1900
             and re.search(r"\bseries\b", r["text"], re.I)]
    if len(early) < 2:
        return rows
    best = max(early, key=lambda r: len(r["text"]))
    years = sorted({r["year"] for r in early})
    best["merged"] = True
    best["text"] = best["text"] + f" (World Series results are also recorded for {', '.join(y for y in years if y != best['year'])}.)"
    return [r for r in rows if r not in early or r is best]


def dedupe_articles(rows):
    """Cluster article sentences by year plus shared names; keep the longest of each cluster."""
    arts = sorted((r for r in rows if r["src"] == "article"), key=lambda r: -len(r["text"]))
    kept = []
    for r in arts:
        if any(k["year"] == r["year"] and len(names(k["text"]) & names(r["text"])) >= 2 for k in kept):
            continue
        kept.append(r)
    return [r for r in rows if r["src"] != "article"] + kept


DANGLING = re.compile(r"\s+(a|an|the|of|to|in|on|at|is|are|was|were|and|or|with|by|for|from|his|her|their|its|as|that|who|which|after|over|into)$", re.I)


def headline(text, limit=70):
    """Fallback headline: whole clause, no ellipsis. Cut at ';', then at the last ', ' or ' and/but/as/after' under the limit,
    else at the last word. The AI headlines (write_headlines.py) replace these when available."""
    t = re.sub(r"^On [A-Z][a-z]+ \d{1,2}, \d{4},? ", "", text.strip(" ."))
    t = t[:1].upper() + t[1:]
    first = t.split(";")[0].strip(" .,")
    def tidy(h):
        h = h.strip(" .,;:")
        while DANGLING.search(h):
            h = DANGLING.sub("", h).strip(" .,;:")
        return h
    if len(first) <= limit:
        return tidy(first)
    window = first[:limit]
    cuts = [m.start() for m in re.finditer(r", | and | but | as | after | while | with ", window) if m.start() >= 30]
    if cuts:
        return tidy(window[:cuts[-1]])
    return tidy(window.rsplit(" ", 1)[0])


def dedupe_by_subject(rows):
    best = {}
    for r in rows:
        if r["kind"] == "death" and r["links"]:
            k = (r["year"], r["links"][0])
            if k not in best or len(r["text"]) > len(best[k]["text"]):
                best[k] = r
    out = []
    for r in rows:
        if r["links"] and (r["year"], r["links"][0]) in best:
            if r is best[(r["year"], r["links"][0])]:
                out.append(r)
        else:
            out.append(r)
    return out


def rank(rows):
    rows = dedupe_by_subject(rows)
    rows = merge_early_series(rows)
    rows = dedupe_articles(rows)
    seen, kept = set(), []
    deaths = [r for r in rows if r["kind"] == "death"]
    events = [r for r in rows if r["kind"] != "death"]
    teams = team_titles([l for r in events for l in r["links"]])
    views = pageviews([r["links"][0] for r in deaths if r["links"]] + [l for r in events for l in r["links"] if l not in teams])
    for r in rows:
        key = re.sub(r"\W+", "", r["text"].lower())[:40]
        if key in seen:
            continue
        seen.add(key)
        low = r["text"].lower()
        if r["kind"] == "death":
            v = views.get(r["links"][0], 0) if r["links"] else 0
            if v < DEATH_MIN_VIEWS and "hall of fame" not in low:
                continue
            r["score"] = 20 + v / 2000
        else:
            kw = sum(w for k, w in KEYWORDS.items() if k in low)
            if len(r["text"]) < MIN_EVENT_CHARS:
                continue
            fame = max([views.get(l, 0) for l in r["links"] if l not in teams] or [0])
            r["score"] = 10 + kw + min(math.log10(fame + 1) * 5, 25)
        kept.append(r)
    kept.sort(key=lambda r: -r["score"])
    arts = [r for r in kept if r["src"] == "article"][MAX_ARTICLE:]
    kept = [r for r in kept if r not in arts]
    for r in kept:
        cands = [r["about"]] if r.get("about") else []
        people = sorted((l for l in r["links"] if l not in teams and l not in cands),
                        key=lambda l: (bool(SEASONISH.search(l)), -views.get(l, 0)))
        cands += people + [l for l in r["links"] if l in teams and l not in cands]
        r["abouts"] = cands[:3]
        r["about"] = r["abouts"][0] if r["abouts"] else None
        r["headline"] = headline(r["text"])
    lead, rest = kept[:1], kept[1:]
    rest.sort(key=lambda r: r["year"], reverse=True)  # newest year first
    if lead:
        lead[0]["lead"] = True
    return lead + rest


# ---------- photos: Wikipedia image -> Commons search -> (typographic panel in the page) ----------

OK_LICENSE = re.compile(r"^(CC[ -]|Public domain|PD|No restrictions|Attribution|GFDL|Copyrighted free use)", re.I)
THUMB_W = 960  # Wikimedia only serves standard thumbnail widths (250, 330, 500, 960, 1280, ...)


def thumb_url(original, width=THUMB_W, orig_width=None):
    original = original.split("?")[0]
    if orig_width and orig_width <= width:
        return original
    m = re.match(r"(https://upload\.wikimedia\.org/wikipedia/commons)/([0-9a-f]/[0-9a-f]{2})/(.+)$", original)
    if not m or original.lower().endswith((".svg", ".tif", ".tiff")):
        return original
    return f"{m.group(1)}/thumb/{m.group(2)}/{m.group(3)}/{width}px-{m.group(3)}"


def clean_html(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def clean(text, limit):
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def commons_info(file_titles):
    """License and credit for Commons files. Returns {title: {...}} only for freely licensed files."""
    out = {}
    file_titles = list(dict.fromkeys(file_titles))
    for i in range(0, len(file_titles), 40):
        r = get("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=extmetadata|url|size&titles="
                + urllib.parse.quote("|".join(file_titles[i:i + 40])))
        for p in (r or {}).get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            md = ii.get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "")
            nonfree = md.get("NonFree", {}).get("value", "").lower() == "true"
            if lic and OK_LICENSE.match(lic) and not nonfree:
                out[p["title"]] = {"license": lic, "credit": clean_html(md.get("Artist", {}).get("value", "")) or "Wikimedia Commons",
                                   "page": ii.get("descriptionurl", ""), "url": ii.get("url", ""), "width": ii.get("width", 0)}
    return out


def commons_file_from_url(src):
    m = re.match(r"https://upload\.wikimedia\.org/wikipedia/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+)", src or "")
    return "File:" + urllib.parse.unquote(m.group(1)).replace("_", " ") if m else None


def commons_search(title):
    """Best Commons photo whose file name contains every word of the page title (guards against look-alike names)."""
    r = get("https://commons.wikimedia.org/w/api.php?action=query&format=json&list=search&srnamespace=6&srlimit=10&srsearch="
            + urllib.parse.quote(f"{title} baseball filetype:bitmap"))
    words = [w.lower() for w in re.sub(r"\(.*?\)", "", title).split() if len(w) > 2]
    if len(words) < 2:  # too generic ("AL West") to find a trustworthy photo by name
        return None
    for x in (r or {}).get("query", {}).get("search", []):
        t = x["title"]
        low = t.lower().replace("_", " ")
        if low.endswith((".jpg", ".jpeg", ".png")) and words and all(w in low for w in words):
            return t
    return None


BASEBALLISH = re.compile(r"baseball|ballpark|\bMLB\b|Major League|\bNL\b|\bAL\b|softball|umpire", re.I)


def is_baseball_summary(sm):
    return bool(sm) and bool(BASEBALLISH.search((sm.get("description") or "") + " " + (sm.get("extract") or "")[:300]))


def add_photos(stories):
    """Fills in story['image'] and story['extract']; leaves image=None when nothing freely licensed is found.
    A candidate page is used only if its Wikipedia summary is about baseball (guards against namesakes)."""
    trusted = set()
    for st in stories:
        st["image"], st["extract"], st["page"] = None, "", ""
    for level in range(3):
        todo = [st for st in stories if not st["image"] and len(st.get("abouts", [])) > level]
        summaries = {}
        for t in dict.fromkeys(st["abouts"][level] for st in todo):
            r = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(t.replace(" ", "_"), safe=""))
            summaries[t] = r or {}
            if is_baseball_summary(r):
                trusted.add(t)
        wanted = {t: commons_file_from_url((sm.get("originalimage") or {}).get("source")) for t, sm in summaries.items()}
        info = commons_info([f for f in wanted.values() if f])
        for st in todo:
            t = st["abouts"][level]
            sm = summaries.get(t, {})
            if t not in trusted:
                continue
            if not st["extract"]:
                st["extract"] = clean(sm.get("extract", ""), 320)
                st["page"] = (sm.get("content_urls") or {}).get("desktop", {}).get("page", "")
            f = wanted.get(t)
            if f and f in info:
                i = info[f]
                st["image"] = {"url": thumb_url(sm["originalimage"]["source"], orig_width=sm["originalimage"].get("width")), "credit": i["credit"], "license": i["license"],
                               "page": i["page"], "alt": sm.get("description") or t, "source": "wikipedia", "of": t}
    # second chance: search Commons for stories still without a photo
    for st in stories:
        if st["image"] or not st.get("about") or st["about"] not in trusted:
            continue
        f = commons_search(st["about"])
        if not f:
            continue
        i = commons_info([f]).get(f)
        if i and i["url"]:
            st["image"] = {"url": thumb_url(i["url"], orig_width=i.get("width")), "credit": i["credit"], "license": i["license"], "page": i["page"],
                           "alt": st["about"], "source": "commons", "of": st["about"]}
    return stories


def pick_lead(stories):
    """Lead = the strongest non-obituary story that has a real photo; the rest run newest year first."""
    pool = [x for x in stories if x.get("image") and x["kind"] != "death" and not x.get("merged")] or stories
    if not pool:
        return stories
    lead = max(pool, key=lambda x: x["score"])
    for x in stories:
        x.pop("lead", None)
    lead["lead"] = True
    rest = sorted((x for x in stories if x is not lead), key=lambda x: x["year"], reverse=True)
    return [lead] + rest


def stories_for(month, day, pages):
    rows = []
    for title, text in pages:
        rows += parse_year_page(title, text, month, day)
    rows += onthisday(month, day)
    rows += article_sentences(month, day)
    return rank(rows)


def write_rss():
    """RSS feed for today's date, built from the already-written data/days file."""
    import datetime
    from email.utils import format_datetime
    from xml.sax.saxutils import escape
    today = datetime.datetime.now(datetime.timezone.utc)
    f = ROOT / "data" / "days" / f"{today.month:02d}-{today.day:02d}.json"
    if not f.exists():
        print("no data file for today, skipping RSS:", f.name)
        return
    site = os.environ.get("SITE_URL", "http://localhost:8765/").rstrip("/") + "/"
    stories = json.loads(f.read_text())["stories"]
    items = []
    for i, st in enumerate(stories):
        credit = f" Photo: {st['image']['credit']} ({st['image']['license']})." if st.get("image") else ""
        desc = escape(st["text"] + credit)
        items.append(f"<item><title>{escape(st['year'] + ': ' + (st.get('headline') or st['text'][:80]))}</title>"
                     f"<link>{escape(st.get('page') or site)}</link>"
                     f"<guid isPermaLink=\"false\">{today:%m-%d}-{i}-{st['year']}</guid>"
                     f"<pubDate>{format_datetime(today)}</pubDate><description>{desc}</description></item>")
    feed = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f"<title>This Day in Baseball</title><link>{escape(site)}</link>"
            f"<description>Baseball history for {calendar.month_name[today.month]} {today.day}.</description>"
            f"<language>en-us</language><lastBuildDate>{format_datetime(today)}</lastBuildDate>{''.join(items)}</channel></rss>")
    (ROOT / "this-day-in-baseball.xml").write_text(feed, encoding="utf-8")
    print(f"wrote this-day-in-baseball.xml with {len(items)} items")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="*", help="MM/DD (omit with --all)")
    ap.add_argument("--write", action="store_true", help="write data/days/MM-DD.json")
    ap.add_argument("--all", action="store_true", help="every day of the year (366 dates, slow; the cache makes reruns fast)")
    ap.add_argument("--rss", action="store_true", help="write this-day-in-baseball.xml for today from data/days")
    a = ap.parse_args()
    if a.all:
        a.dates = [f"{m:02d}/{d:02d}" for m in range(1, 13) for d in range(1, calendar.monthrange(2024, m)[1] + 1)]
    if a.rss and not a.dates:
        write_rss()
        return
    pages = list(year_pages())
    print(f"loaded {len(pages)} 'YYYY in baseball' pages")
    for d in a.dates:
        month, day = map(int, d.split("/"))
        s = stories_for(month, day, pages)
        if a.write:
            add_photos(s)
            s = pick_lead(s)
        by = {}
        for r in s:
            by[r["src"] + "/" + r["kind"]] = by.get(r["src"] + "/" + r["kind"], 0) + 1
        print(f"\n=== {calendar.month_name[month]} {day}: {len(s)} stories {by}")
        for r in s:
            print(f"  {r['year']} [{r['src']}/{r['kind']}] {r['text'][:130]}")
        if a.write:
            (ROOT / "data" / "days").mkdir(parents=True, exist_ok=True)
            (ROOT / "data" / "days" / f"{month:02d}-{day:02d}.json").write_text(
                json.dumps({"month": month, "day": day, "stories": s}, ensure_ascii=False, indent=1))
    if a.rss:
        write_rss()
    print("\nrequests:", {"net": STATS["net"], "cached": STATS["cached"], "failed": len(STATS["failed"])})
    for f in STATS["failed"]:
        print("  FAILED", f)


if __name__ == "__main__":
    main()
