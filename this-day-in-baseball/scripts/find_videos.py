#!/usr/bin/env python3
"""Find an official YouTube video for the top stories of each day.

For each day file: the lead plus the next top-scoring stories (default 6 in all, obituaries skipped).
1. Claude (Haiku, text only) writes a short YouTube search query for each story.
2. YouTube Data API search (100 quota units each; the free quota is about 10,000 a day), embeddable videos only.
3. Only videos from an allowlist of official channels (MLB and the clubs) survive, and only if they are public,
   embeddable and not longer than 15 minutes (one cheap videos.list call checks this).
4. Claude judges whether the best remaining video really shows this event; anything doubtful is dropped.

Safeguards
- Keys come from the environment or .env and are never printed or logged.
- Results (including "nothing found") are cached in data/videos.json, so reruns cost nothing and a story is
  never searched twice. Edit data/video_overrides.json to force a video ("storykey": "videoId") or block one (null).
- --dry-run shows how many searches and how much quota a run would use, without calling anything.
- A run never makes more than --max-searches searches (default 100, which is 10,000 units: a full free day).
  If YouTube says the quota is used up, the run stops cleanly; rerun tomorrow and it resumes.
"""
import argparse
import html
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
import build_days as b  # noqa: E402  (story_key, ROOT)
import write_headlines as wh  # noqa: E402  (load_env)

ROOT = b.ROOT
DAYS = ROOT / "data" / "days"
CACHE_FILE = ROOT / "data" / "videos.json"
OVERRIDES_FILE = ROOT / "data" / "video_overrides.json"
YT = "https://www.googleapis.com/youtube/v3"
API = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-5-5"
MAX_SECONDS = 15 * 60

# Official channels, compared in lower case against the channel title YouTube reports.
TEAMS = [
    "Arizona Diamondbacks", "Atlanta Braves", "Baltimore Orioles", "Boston Red Sox", "Chicago Cubs", "Chicago White Sox",
    "Cincinnati Reds", "Cleveland Guardians", "Cleveland Indians", "Colorado Rockies", "Detroit Tigers", "Houston Astros",
    "Kansas City Royals", "Los Angeles Angels", "Los Angeles Dodgers", "Miami Marlins", "Milwaukee Brewers",
    "Minnesota Twins", "New York Mets", "New York Yankees", "Oakland Athletics", "Philadelphia Phillies",
    "Pittsburgh Pirates", "San Diego Padres", "San Francisco Giants", "Seattle Mariners", "St. Louis Cardinals",
    "Tampa Bay Rays", "Texas Rangers", "Toronto Blue Jays", "Washington Nationals",
]
OFFICIAL = {t.lower() for t in TEAMS} | {"mlb", "mlb vault", "mlb network", "mlb.com", "national baseball hall of fame and museum",
                                          "baseball hall of fame", "major league baseball"}

QUERY_SYSTEM = """You write YouTube search queries to find an official highlight or classic clip of a baseball event.
For each story write a query of 4 to 8 words: the key team or person names, the year, and what happened (for example
"Kirk Gibson walk-off home run 1988 World Series Game 1"). Use only names and facts in the story text.
Return only JSON: {"queries": [{"id": "...", "query": "..."}]}"""

JUDGE_SYSTEM = """You decide whether a YouTube video shows a specific baseball story. You get the story (year and text) and a numbered list of
candidate videos (title, channel, publish date, description start). Pick the one video that is clearly footage or an official recap
of THIS event, in that year (or an official retrospective of it). Reject other seasons, other players, generic season recaps, previews,
predictions, interviews unrelated to the event, and fan-made content. If none clearly fits, pick none.
Return only JSON: {"pick": <number or null>, "reason": "<short reason>"}"""


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1))


def day_files(dates, all_days):
    if all_days or not dates:
        return sorted(DAYS.glob("*.json"))
    return [DAYS / f"{int(d.split('/')[0]):02d}-{int(d.split('/')[1]):02d}.json" for d in dates]


def targets(stories, top):
    """The lead plus the highest-scoring living stories, up to `top` in all."""
    living = [s for s in stories if s["kind"] != "death"]
    living.sort(key=lambda s: -s.get("score", 0))
    return living[:top]


class QuotaUsed(Exception):
    pass


def http_json(url, body=None, headers=None):
    """GET or POST JSON with a few retries. Never prints the URL (it can hold the API key)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    delay = 4
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            try:
                err = json.load(e).get("error", {})
            except Exception:
                err = {}
            reasons = {x.get("reason") for x in err.get("errors", [])}
            if e.code == 403 and reasons & {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"}:
                raise QuotaUsed()
            if e.code in (429, 500, 502, 503, 529):
                time.sleep(delay)
                delay *= 2
                continue
            sys.exit(f"HTTP {e.code}: {str(err.get('message', ''))[:160]}")
        except (urllib.error.URLError, TimeoutError):
            time.sleep(delay)
            delay *= 2
    sys.exit("Gave up after repeated network errors.")


def claude(system, content, max_tokens=1500):
    body = {"model": MODEL, "max_tokens": max_tokens, "thinking": {"type": "disabled"}, "system": system,
            "messages": [{"role": "user", "content": content}]}
    hdr = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"}
    data = http_json(API, body, hdr)
    text = "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)), data.get("usage", {})
    except (AttributeError, ValueError):
        return {}, data.get("usage", {})


def parse_duration(iso):
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 10 ** 6
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def search(query, key):
    qs = urllib.parse.urlencode({"part": "snippet", "type": "video", "videoEmbeddable": "true", "maxResults": 10,
                                 "relevanceLanguage": "en", "q": query, "key": key})
    return http_json(f"{YT}/search?{qs}").get("items", [])


def details(ids, key):
    qs = urllib.parse.urlencode({"part": "contentDetails,status", "id": ",".join(ids), "key": key})
    return {i["id"]: i for i in http_json(f"{YT}/videos?{qs}").get("items", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="*", help="MM/DD (default: every day file)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--top", type=int, default=6, help="stories per day to look for a video (lead included)")
    ap.add_argument("--max-searches", type=int, default=100, help="stop after this many searches (100 units each)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    wh.load_env()
    cache = load_json(CACHE_FILE, {})
    overrides = load_json(OVERRIDES_FILE, {})
    files = [f for f in day_files(a.dates, a.all) if f.exists()]
    todo = []  # (file, [stories without a cached answer])
    total = 0
    for f in files:
        stories = json.loads(f.read_text())["stories"]
        want = [s for s in targets(stories, a.top) if s["key"] not in cache and s["key"] not in overrides]
        total += len(targets(stories, a.top))
        if want:
            todo.append((f, want))
    n = sum(len(w) for _, w in todo)
    print(f"{len(files)} day files, {total} target stories, {total - n} already answered, {n} need a search")
    print(f"quota: {n * 100 + len(todo)} units for this run ({a.max_searches} searches max; the free quota is about 10,000 a day)")
    if a.dry_run or not n:
        return
    for k in ("YOUTUBE_API_KEY", "ANTHROPIC_API_KEY"):
        if not os.environ.get(k):
            sys.exit(f"{k} is missing. Add it to .env (see SETUP.md).")
    key = os.environ["YOUTUBE_API_KEY"]

    searches = found = 0
    tok_in = tok_out = 0
    try:
        for f, want in todo:
            if searches + len(want) > a.max_searches:
                want = want[: max(0, a.max_searches - searches)]
            if not want:
                break
            items = [{"id": s["key"], "year": s["year"], "text": s["text"][:400]} for s in want]
            qd, u = claude(QUERY_SYSTEM, json.dumps(items, ensure_ascii=False))
            tok_in += u.get("input_tokens", 0)
            tok_out += u.get("output_tokens", 0)
            queries = {q.get("id"): str(q.get("query", "")) for q in qd.get("queries", [])}
            for s in want:
                q = queries.get(s["key"]) or f"{s['year']} {s.get('about', '')} baseball"
                results = search(q, key)
                searches += 1
                cands = [r for r in results if r["snippet"]["channelTitle"].strip().lower() in OFFICIAL]
                ok = []
                if cands:
                    det = details([r["id"]["videoId"] for r in cands], key)
                    for r in cands:
                        d = det.get(r["id"]["videoId"])
                        if d and d["status"].get("embeddable") and d["status"].get("privacyStatus") == "public" \
                                and parse_duration(d["contentDetails"].get("duration")) <= MAX_SECONDS:
                            ok.append(r)
                entry = None
                reason = "no official embeddable video"
                if ok:
                    listing = "\n".join(
                        f"{i + 1}. \"{html.unescape(r['snippet']['title'])}\" | {r['snippet']['channelTitle']} | {r['snippet']['publishedAt'][:10]} | {r['snippet']['description'][:160]}"
                        for i, r in enumerate(ok))
                    verdict, u = claude(JUDGE_SYSTEM, f"Story ({s['year']}): {s['text'][:500]}\n\nCandidates:\n{listing}", 300)
                    tok_in += u.get("input_tokens", 0)
                    tok_out += u.get("output_tokens", 0)
                    pick = verdict.get("pick")
                    reason = str(verdict.get("reason", ""))[:160]
                    if isinstance(pick, int) and 1 <= pick <= len(ok):
                        r = ok[pick - 1]
                        entry = {"id": r["id"]["videoId"], "title": html.unescape(r["snippet"]["title"]), "channel": html.unescape(r["snippet"]["channelTitle"]),
                                 "published": r["snippet"]["publishedAt"][:10], "reason": reason, "query": q}
                cache[s["key"]] = entry or {"none": reason, "query": q}
                save_cache(cache)
                if entry:
                    found += 1
                print(f"[{searches}] {s['year']} {s['text'][:50]!r}: " + (f"VIDEO {entry['title'][:60]!r} ({entry['channel']})" if entry else f"none ({reason[:60]})"))
    except QuotaUsed:
        print("YouTube quota is used up for today. Everything found so far is saved; rerun tomorrow to continue.")
    print(f"done: {searches} searches, {found} videos found; Claude tokens {tok_in:,} in, {tok_out:,} out")


if __name__ == "__main__":
    main()
