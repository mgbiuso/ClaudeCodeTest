#!/usr/bin/env python3
"""Choose a photo for each story, checked by Claude, or choose none.

For every story: gather candidate photos from the event's own article, the pages the story links,
the ballpark and the teams; have Claude rank them from their Commons metadata (description, date,
categories); then have Claude LOOK at a small thumbnail of its top choices and confirm the match.
If nothing passes, the story gets no photo (the page shows it as a brief or a plate).

Standard (set by the user): accept a photo of the event itself, or of a team, ballpark or central
person from a fitting era (about 5 years). Reject namesakes, wrong eras and unrelated players.

Safeguards: key from .env and never printed; decisions cached in data/photos.json (reruns are free);
--dry-run shows counts and a token estimate; runs over --max-stories (default 150) are refused;
Wikimedia is asked politely (one request at a time, with a pause).
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_days as b  # noqa: E402
import write_headlines as wh  # noqa: E402

ROOT = b.ROOT
DAYS = ROOT / "data" / "days"
CACHE_FILE = ROOT / "data" / "photos.json"
MAX_CANDIDATES = 12
PER_PAGE = 5
BAD_FILE = re.compile(r"(logo|icon|flag|map\b|symbol|signature|commons-|question_book|edit-|ambox|crystal|nuvola|pictogram|stub|disambig|"
                      r"red_pog|folder|padlock|text_document|speaker|\.svg$|\.gif$|\.webm$|\.ogv$|\.ogg$|\.pdf$|\.tiff?$)", re.I)
EVENT_PAGES = [
    (r"\bNLCS\b", "{y} National League Championship Series"),
    (r"\bALCS\b", "{y} American League Championship Series"),
    (r"\bNLDS\b", "{y} National League Division Series"),
    (r"\bALDS\b", "{y} American League Division Series"),
    (r"\bWorld Series\b", "{y} World Series"),
    (r"\bAll-Star Game\b", "{y} Major League Baseball All-Star Game"),
]

JUDGE_SYSTEM = """You choose a photograph for one item on a baseball "on this day" newspaper page.
You get the story and candidate photos (id, file name, description, date, categories, and which Wikipedia article each came from).
Accept a photo only if it shows one of these:
 (a) the event itself;
 (b) the MAIN SUBJECT of the story, meaning the person the story is about. For the main subject, a clear photo of that person from their baseball career is fine at any point in it, as long as it is the right person. For obituaries, any career portrait of that person is fine;
 (c) a team that the story is about, from within about 5 years of the story's year;
 (d) the ballpark where the event happened.
A person who is only mentioned in passing is NOT the main subject (for example a player who hit a home run in a story about a team advancing to the World Series). Do not use that person's photo.
Reject: namesakes, other sports, minor-league or college photos unless the story is about them, the wrong team, a team photo from a different era, logos, signatures, maps, drawings, and crowds or scoreboards with no context.
A photo's date, description and categories are strong evidence: if they show a different person, team or level of play, reject it.
Return only JSON: {"ranked": [{"id": "c3", "tier": "event|person|team|venue", "confidence": 0.0, "reason": "short"}]}. ranked has at most 3 entries, best first, and is empty if no candidate qualifies."""

VISION_SYSTEM = """You verify a photograph for a baseball history page. Look at the image and read the story.
Say match=true if the photo plausibly shows the event, the main subject of the story (a person of the right name, per the file name and article it came from), a team of that period, or the ballpark. You cannot recognize faces, so rely on what is visible and on the file name; accept when nothing contradicts them. Do not reject a portrait of the right person only because it was taken at a different point in their career.
Say match=false for a different sport, a minor-league or college setting the story does not mention, a clearly wrong ballpark or team, a logo, a document, a map, a drawing, or a photo that has nothing to do with baseball.
Return only JSON: {"match": true, "shows": "what you see in 12 words or fewer", "reason": "short"}"""


def load_cache():
    try:
        return json.loads(CACHE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1))


# ---------- candidates ----------

def page_files(title):
    """Image files used on a Wikipedia article: the lead image first, then the others (jpg/png, no logos or icons)."""
    out = []
    sm = b.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_"), safe="")) or {}
    lead = b.commons_file_from_url((sm.get("originalimage") or {}).get("source"))
    if lead:
        out.append(lead)
    r = b.get("https://en.wikipedia.org/w/api.php?action=query&format=json&prop=images&imlimit=80&redirects=1&titles=" + urllib.parse.quote(title))
    for p in (r or {}).get("query", {}).get("pages", {}).values():
        for i in p.get("images", []):
            t = i["title"]
            if t.lower().endswith((".jpg", ".jpeg", ".png")) and not BAD_FILE.search(t) and t not in out:
                out.append(t)
    return out[:PER_PAGE]


def commons_meta(files):
    """Metadata for free-licensed Commons files, keyed by title. Non-Commons or non-free files are dropped."""
    out = {}
    files = list(dict.fromkeys(files))
    for i in range(0, len(files), 40):
        r = b.get("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=extmetadata|url|size&iiurlwidth=500&titles="
                  + urllib.parse.quote("|".join(files[i:i + 40])))
        for p in (r or {}).get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            md = ii.get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "")
            if not lic or not b.OK_LICENSE.match(lic) or md.get("NonFree", {}).get("value", "").lower() == "true":
                continue
            if (ii.get("width") or 0) < 400:
                continue
            val = lambda k: b.clean_html(md.get(k, {}).get("value", ""))  # noqa: E731
            out[p["title"]] = {
                "license": lic, "credit": b.clean_credit(md.get("Artist", {}).get("value", "")),
                "desc": val("ImageDescription")[:240], "date": (val("DateTimeOriginal") or val("DateTime"))[:30],
                "cats": val("Categories")[:200], "url": ii.get("url", ""), "thumb": ii.get("thumburl", ""),
                "page": ii.get("descriptionurl", ""), "w": ii.get("width"), "h": ii.get("height"),
            }
    return out


def candidate_pages(story):
    pages = []
    if story["kind"] != "death":  # an obituary is about the person, even if the text mentions a World Series
        for pat, tmpl in EVENT_PAGES:
            if re.search(pat, story["text"]):
                pages.append(tmpl.format(y=story["year"]))
    for t in (story.get("abouts") or []) + (story.get("links") or []):
        if t and t not in pages:
            pages.append(t)
    return pages[:8]


def commons_search_files(title, limit=6):
    """Photos found by searching Commons for the page title. File name must contain at least half of the title's words."""
    words = [w.lower() for w in re.sub(r"\(.*?\)", "", title).split() if len(w) > 2]
    if not words:
        return []
    r = b.get("https://commons.wikimedia.org/w/api.php?action=query&format=json&list=search&srnamespace=6&srlimit=10&srsearch="
              + urllib.parse.quote(f"{title} baseball filetype:bitmap"))
    out = []
    for x in (r or {}).get("query", {}).get("search", []):
        t = x["title"]
        low = t.lower().replace("_", " ")
        if t.lower().endswith((".jpg", ".jpeg", ".png")) and not BAD_FILE.search(t) and sum(w in low for w in words) >= max(1, (len(words) + 1) // 2):
            out.append(t)
    return out[:limit]


def candidates(story):
    files, source = [], {}
    pages = candidate_pages(story)
    for page in pages:
        for f in page_files(page):
            if f not in source:
                source[f] = page
                files.append(f)
        if len(files) >= MAX_CANDIDATES + 6:
            break
    meta = commons_meta(files)
    # If the main subject has no free photo of its own, search Commons for it by name.
    subject = pages[0] if pages else None
    if subject and not any(source.get(f) == subject for f in meta):
        extra = []
        for f in commons_search_files(subject):
            if f not in source:
                source[f] = subject + " (Commons search)"
                extra.append(f)
        meta.update(commons_meta(extra))
        files += extra
    cands = []
    ordered = sorted((f for f in files if f in meta), key=lambda f: 0 if source[f].startswith(subject or "\0") else 1)
    for f in ordered:
        cands.append({"id": f"c{len(cands) + 1}", "file": f, "from": source[f], **meta[f]})
        if len(cands) >= MAX_CANDIDATES:
            break
    return cands


# ---------- Claude ----------

def claude(model, system, content, max_tokens=700):
    body = {"model": model, "max_tokens": max_tokens, "thinking": {"type": "disabled"}, "system": system,
            "messages": [{"role": "user", "content": content}]}
    req = urllib.request.Request(wh.API, method="POST", data=json.dumps(body).encode(), headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    delay, last = 5, "unknown"
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
            if data.get("stop_reason") == "max_tokens":
                raise ValueError("reply cut off")
            text = "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text")
            return json.loads(re.search(r"\{.*\}", text, re.S).group(0)), data.get("usage", {})
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529):
                time.sleep(delay)
                delay *= 2
                continue
            try:
                msg = json.load(e).get("error", {}).get("message", "")[:200]
            except Exception:
                msg = ""
            sys.exit(f"Anthropic API error {e.code}: {msg}")
        except (ValueError, AttributeError, KeyError) as e:
            last = type(e).__name__
            time.sleep(2)
    sys.exit(f"Gave up after repeated errors ({last})")


def fetch_thumb(url):
    time.sleep(b.PAUSE)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=b.UA), timeout=60) as r:
            ctype = r.headers.get_content_type()
            data = r.read(2_000_000)
        if ctype in ("image/jpeg", "image/png"):
            return ctype, base64.b64encode(data).decode()
    except Exception:
        pass
    return None, None


def describe(story):
    kind = "obituary (the person died that year)" if story["kind"] == "death" else "event"
    return f'Story ({kind}, {story["year"]}): {story["text"]}'


def decide(story, models, usage):
    cands = candidates(story)
    if not cands:
        return {"image": None, "reason": "no free-licensed candidates"}
    listing = "\n".join(f'{c["id"]} | file: {c["file"][5:]} | description: {c["desc"] or "none"} | date: {c["date"] or "unknown"} | '
                        f'categories: {c["cats"] or "none"} | from article: {c["from"]}' for c in cands)
    out, u = claude(models["text"], JUDGE_SYSTEM, f"{describe(story)}\n\nCandidates:\n{listing}")
    usage["in"] += u.get("input_tokens", 0)
    usage["out"] += u.get("output_tokens", 0)
    by_id = {c["id"]: c for c in cands}
    last = "judge found no fitting photo"
    for pick in (out.get("ranked") or [])[:3]:
        c = by_id.get(pick.get("id"))
        if not c:
            continue
        if float(pick.get("confidence") or 0) < 0.3:  # weak pick: do not spend a vision check on it
            last = f'weak pick ({pick.get("confidence")}): {pick.get("reason", "")}'
            continue
        ctype, data = fetch_thumb(c["thumb"])
        if not data:
            last = f'could not fetch {c["file"][5:]}'
            continue
        content = [{"type": "image", "source": {"type": "base64", "media_type": ctype, "data": data}},
                   {"type": "text", "text": f'{describe(story)}\n\nThe photo is "{c["file"][5:]}" from the article "{c["from"]}".'}]
        v, u = claude(models["vision"], VISION_SYSTEM, content, max_tokens=300)
        usage["in"] += u.get("input_tokens", 0)
        usage["out"] += u.get("output_tokens", 0)
        usage["images"] += 1
        if v.get("match"):
            return {"image": {"url": b.thumb_url(c["url"], orig_width=c["w"]), "credit": c["credit"], "license": c["license"],
                              "page": c["page"], "alt": v.get("shows") or c["desc"][:100] or c["from"], "source": "checked",
                              "of": c["from"], "w": c["w"], "h": c["h"], "tier": pick.get("tier")},
                    "reason": f'{pick.get("tier")}: {v.get("shows", "")}'}
        last = f'rejected {c["file"][5:]}: {v.get("reason", "")}'
    return {"image": None, "reason": last}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="*", help="MM/DD (default: every day file)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default=wh.DEFAULT_MODEL, help="model for the text judge")
    ap.add_argument("--vision-model", default=None, help="model for the photo check (default: same as --model)")
    ap.add_argument("--max-stories", type=int, default=150)
    a = ap.parse_args()

    wh.load_env()
    models = {"text": a.model, "vision": a.vision_model or a.model}
    cache = load_cache()
    files = [f for f in wh.day_files(a.dates, a.all) if f.exists()]
    todo = []
    for f in files:
        for st in json.loads(f.read_text())["stories"]:
            if b.story_key(st["year"], st["text"]) not in cache:
                todo.append(st)
    print(f"{len(files)} day files, {len(todo)} stories need a photo decision ({len(cache)} already cached)")
    print(f"rough estimate: {len(todo) * 1700:,} input and {len(todo) * 120:,} output tokens (about 1.7k in and 120 out per story; measured values are printed after a run)")
    if a.dry_run or not todo:
        return
    if len(todo) > a.max_stories:
        sys.exit(f"Refusing: {len(todo)} stories, limit is {a.max_stories}. Rerun with --max-stories {len(todo)} to confirm.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is missing. Add it to .env (see SETUP.md).")

    usage = {"in": 0, "out": 0, "images": 0}
    before = {}
    for f in files:
        for st in json.loads(f.read_text())["stories"]:
            before[b.story_key(st["year"], st["text"])] = (st.get("image") or {}).get("of")
    for n, st in enumerate(todo, 1):
        key = b.story_key(st["year"], st["text"])
        d = decide(st, models, usage)
        cache[key] = {**d, "model": models["vision"]}
        save_cache(cache)
        was = before.get(key)
        now = (d["image"] or {}).get("of")
        flag = "same" if was == now else "CHANGED"
        print(f'[{n}/{len(todo)}] {st["year"]} {st["text"][:50]!r}  was: {was or "none"} -> now: {now or "none"}  ({flag}) {d["reason"][:110]}')
    changed = 0
    for f in files:
        data = json.loads(f.read_text())
        for st in data["stories"]:
            d = cache.get(b.story_key(st["year"], st["text"]))
            if d is not None:
                st["image"] = d["image"]
                changed += 1
        f.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"done. tokens used: {usage['in']:,} input, {usage['out']:,} output, {usage['images']} images checked")


if __name__ == "__main__":
    main()
