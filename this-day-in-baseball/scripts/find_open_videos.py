#!/usr/bin/env python3
"""Find open-license baseball film that can really be played on a page, and match it to the stories in data/days/.

Sources (all politely, one request at a time, cached in .cache/open_video/):
  ia       Internet Archive movies about baseball, 1895 to 1975
  commons  Wikimedia Commons baseball videos
  loc      Library of Congress film items (loc.gov)
  nara     US National Archives YouTube channel and Library of Congress YouTube channels (YouTube Data API, a few searches)

Steps (run in order; each is cached and safe to rerun):
  python3 scripts/find_open_videos.py catalog     build the candidate list (no AI)
  python3 scripts/find_open_videos.py match       Claude Haiku matches candidates to stories (small, text only)
  ... play every matched video in a real browser (scripts/playback_test.js) and save the result in .cache/open_video/playback.json
  python3 scripts/find_open_videos.py save        write data/open_videos.json with only the matches that played and are licensed

Rules: only public domain or Creative Commons material is kept, with its credit and license. Nothing else in the project is touched.
Keys come from the environment or .env and are never printed.
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_videos as fv  # noqa: E402  (claude(), http_json(), env loading)

ROOT = fv.ROOT
CACHE = ROOT / ".cache" / "open_video"
DAYS = ROOT / "data" / "days"
OUT = ROOT / "data" / "open_videos.json"
UA = {"User-Agent": "ThisDayInBaseball/1.0 (personal history site; open-license film search)"}
NARA, LOC_YT = "UCnAsiniI4DF7vAAe7omWWFQ", ("UCbObxjfi3W9YKnDS0PgadNA", "UCo39dY3z3bYt97wHvFvGX2Q")
PD_COLLECTIONS = {"prelinger", "usgovfilms", "FedFlix", "nasa", "us_army_films"}


def get_json(url, pause=1.0):
    delay = 8
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                data = json.load(r)
            time.sleep(pause)
            return data
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 520, 522, 524) and attempt < 3:
                time.sleep(delay)  # a busy server: wait and try again
                delay *= 2
                continue
            raise


def clean(s, n=320):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()[:n]


# ---------- catalogs ----------

def ia_license(d):
    lic = d.get("licenseurl") or ""
    cols = d.get("collection") or []
    cols = cols if isinstance(cols, list) else [cols]
    year = int(str(d.get("year") or 0)[:4] or 0)
    if "publicdomain" in lic or "creativecommons.org" in lic:
        return "Public domain" if "publicdomain" in lic else "Creative Commons", lic
    if set(cols) & PD_COLLECTIONS:
        return "Public domain (US government or Prelinger collection)", ""
    if 0 < year <= 1928:
        return "Public domain (published 1928 or earlier)", ""
    return None, ""


def catalog_ia():
    q = ('(title:(baseball OR "world series" OR "all-star game" OR yankees OR dodgers OR giants OR cubs OR "red sox") OR subject:(baseball) '
         'OR description:(baseball OR "world series")) AND mediatype:movies AND year:[1895 TO 1975]')
    fl = ("identifier", "title", "year", "collection", "licenseurl", "runtime", "description", "creator")
    qs = urllib.parse.urlencode([("q", q), ("rows", 1000), ("output", "json")] + [("fl[]", x) for x in fl])
    docs = get_json("https://archive.org/advancedsearch.php?" + qs)["response"]["docs"]
    out = []
    for d in docs:
        text = " ".join(str(d.get(k, "")) for k in ("title", "description")).lower()
        if not re.search(r"baseball|world series|all-star|pennant|home run|yankee|dodger|brooklyn|red sox|giants|cubs", text):
            continue
        lic, lic_url = ia_license(d)
        if not lic:
            continue
        out.append({"src": "ia", "id": d["identifier"], "title": clean(d.get("title"), 140), "year": int(str(d.get("year") or 0)[:4] or 0),
                    "desc": clean(d.get("description")), "license": lic, "licenseUrl": lic_url, "credit": clean(str(d.get("creator") or "Internet Archive"), 80),
                    "page": f"https://archive.org/details/{d['identifier']}", "runtime": d.get("runtime")})
    return out


def catalog_commons():
    out, cont = [], {}
    for _ in range(8):
        qs = {"action": "query", "format": "json", "generator": "search", "gsrsearch": "baseball filetype:video", "gsrnamespace": 6, "gsrlimit": 50,
              "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size", **cont}
        d = get_json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(qs))
        for p in (d.get("query", {}).get("pages", {}) or {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata", {})
            lic = (em.get("LicenseShortName") or {}).get("value", "")
            if not ii.get("url") or not re.match(r"(CC|Public domain|PD)", lic, re.I):
                continue
            date = clean((em.get("DateTimeOriginal") or {}).get("value", ""), 60)
            m = re.search(r"(1[89]\d\d|20\d\d)", date + " " + p["title"])
            out.append({"src": "commons", "id": p["title"], "title": clean(p["title"].replace("File:", ""), 140), "year": int(m.group(1)) if m else 0,
                        "desc": clean((em.get("ImageDescription") or {}).get("value", "")), "license": lic, "licenseUrl": "",
                        "credit": clean((em.get("Artist") or {}).get("value", "Wikimedia Commons"), 80), "url": ii["url"],
                        "page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_"))})
        cont = d.get("continue") or {}
        if not cont:
            break
    return out


def catalog_loc():
    out = []
    for q in ("baseball", "world series", "base ball"):
        d = get_json("https://www.loc.gov/film-and-videos/?" + urllib.parse.urlencode({"q": q, "fo": "json", "c": 50}))
        for r in d.get("results", []):
            rights = clean(str(r.get("rights_advisory") or r.get("rights") or ""), 200).lower()
            year = int(str(r.get("date") or 0)[:4] or 0)
            if not r.get("id") or r.get("access_restricted"):
                continue
            if not (0 < year <= 1928 or "no known" in rights or "public domain" in rights):
                continue
            out.append({"src": "loc", "id": r["id"], "title": clean(r.get("title"), 140), "year": year, "desc": clean(" ".join(r.get("description") or [])),
                        "license": "Public domain (Library of Congress)", "licenseUrl": "", "credit": "Library of Congress", "page": r["id"].replace("http://", "https://")})
    uniq = {c["id"]: c for c in out}
    return list(uniq.values())


def catalog_youtube():
    import os
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return []
    out = []
    jobs = [(NARA, q) for q in ("baseball", "World Series", "Babe Ruth", "Jackie Robinson", "ball park president throws first pitch")]
    jobs += [(c, q) for c in LOC_YT for q in ("baseball", "World Series")]
    for channel, q in jobs:
        qs = urllib.parse.urlencode({"part": "snippet", "type": "video", "channelId": channel, "q": q, "maxResults": 25, "key": key})
        try:
            d = get_json("https://www.googleapis.com/youtube/v3/search?" + qs, pause=0.5)
        except urllib.error.HTTPError as e:  # quota or a bad request: say why and stop politely
            body = e.read().decode("utf-8", "ignore")
            why = re.search(r'"reason":\s*"(\w+)"', body)
            print(f"  YouTube search stopped: HTTP {e.code} {why.group(1) if why else ''}")
            break
        for it in d.get("items", []):
            sn = it["snippet"]
            m = re.search(r"(1[89]\d\d|19\d\d)", sn["title"] + " " + sn["description"])
            out.append({"src": "youtube", "id": it["id"]["videoId"], "title": clean(html.unescape(sn["title"]), 140), "year": int(m.group(1)) if m else 0,
                        "desc": clean(sn["description"]), "license": "Public domain (US government)" if channel == NARA else "Library of Congress",
                        "licenseUrl": "", "credit": html.unescape(sn["channelTitle"]), "page": f"https://www.youtube.com/watch?v={it['id']['videoId']}"})
    return list({c["id"]: c for c in out}.values())


def cmd_catalog():
    CACHE.mkdir(parents=True, exist_ok=True)
    fv.wh.load_env()
    allc = []
    for name, fn in (("Internet Archive", catalog_ia), ("Wikimedia Commons", catalog_commons), ("Library of Congress", catalog_loc), ("YouTube (NARA, LoC)", catalog_youtube)):
        try:
            got = fn()
        except Exception as e:
            print(f"  {name}: failed ({type(e).__name__}: {str(e)[:80]})")
            got = []
        print(f"{name}: {len(got)} licensed candidates")
        allc += got
    (CACHE / "candidates.json").write_text(json.dumps(allc, ensure_ascii=False, indent=1))
    print("saved", len(allc), "candidates")


# ---------- matching ----------

JUDGE = """You match old baseball film to baseball history stories. For each story you get its year and text and a numbered list of candidate videos
(source, year, title, description). Choose a candidate ONLY if it clearly shows that same event, game, series or person in that same period.
Generic baseball footage, other seasons, other people, feature films and TV shows that are not about the event do not count. If none clearly fits, pick null.
Return only JSON: {"matches": [{"story": "<id>", "pick": <candidate number or null>, "reason": "<short reason>"}]}"""


def tokens(s):
    return {w for w in re.findall(r"[A-Za-z][A-Za-z'\-]{3,}", s)}


def preselect(story, cands):
    y = int(story["year"])
    names = {w.lower() for w in re.findall(r"\b[A-Z][a-z]{3,}\b", story["text"])} - {"world", "series", "baseball", "major", "league", "game", "american", "national"}
    out = []
    for c in cands:
        near = c["year"] and abs(c["year"] - y) <= 2
        shared = names & {w.lower() for w in tokens(c["title"] + " " + c["desc"])}
        if near or (len(shared) >= 2 and (not c["year"] or abs(c["year"] - y) <= 10)):
            out.append(c)
    return out[:8]


def cmd_match():
    fv.wh.load_env()
    cands = json.loads((CACHE / "candidates.json").read_text())
    cand_by = {i: c for i, c in enumerate(cands)}
    jobs = []
    for f in sorted(DAYS.glob("*.json")):
        for s in json.loads(f.read_text())["stories"]:
            if int(s["year"]) > 1975:
                continue
            pre = preselect(s, cands)
            if pre:
                jobs.append((s, pre))
    print(f"{len(jobs)} stories have at least one candidate by year or names; asking Claude Haiku (text only)")
    matches, tin, tout = {}, 0, 0
    for i in range(0, len(jobs), 12):
        chunk = jobs[i:i + 12]
        payload = []
        for s, pre in chunk:
            lines = [f"{n + 1}. [{c['src']}] {c['year'] or '?'} | {c['title']} | {c['desc'][:200]}" for n, c in enumerate(pre)]
            payload.append(f"STORY {s['key']} ({s['year']}): {s['text'][:300]}\nCANDIDATES:\n" + "\n".join(lines))
        data, usage = fv.claude(JUDGE, "\n\n".join(payload), 1800)
        tin += usage.get("input_tokens", 0)
        tout += usage.get("output_tokens", 0)
        by_story = {s["key"]: pre for s, pre in chunk}
        for m in data.get("matches", []):
            pick, pre = m.get("pick"), by_story.get(m.get("story"))
            if pre and isinstance(pick, int) and 1 <= pick <= len(pre):
                matches[m["story"]] = {"candidate": pre[pick - 1], "reason": str(m.get("reason", ""))[:200]}
    (CACHE / "matches.json").write_text(json.dumps(matches, ensure_ascii=False, indent=1))
    print(f"{len(matches)} matches; Claude tokens {tin:,} in, {tout:,} out; saved .cache/open_video/matches.json")


# ---------- save ----------

def cmd_save():
    matches = json.loads((CACHE / "matches.json").read_text())
    played = json.loads((CACHE / "playback.json").read_text()) if (CACHE / "playback.json").exists() else {}
    approved_file = CACHE / "approved.json"
    approved = set(json.loads(approved_file.read_text())) if approved_file.exists() else None  # story keys a person has checked
    keep = {}
    for key, m in matches.items():
        if approved is not None and key not in approved:
            continue
        c = m["candidate"]
        res = played.get(f"{c['src']}:{c['id']}")
        if res and res.get("ok"):
            keep[key] = {"source": c["src"], "id": c["id"], "url": res.get("url") or c.get("url"), "title": c["title"], "year": c["year"],
                         "duration": res.get("duration"), "license": c["license"], "credit": c["credit"], "page": c["page"],
                         "playedOk": True, "matchReason": m["reason"]}
    OUT.write_text(json.dumps(dict(sorted(keep.items())), ensure_ascii=False, indent=1))
    print(f"saved {len(keep)} playable matches (of {len(matches)} matched, {len(played)} tested) to {OUT.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["catalog", "match", "save"])
    {"catalog": cmd_catalog, "match": cmd_match, "save": cmd_save}[ap.parse_args().step]()


if __name__ == "__main__":
    main()
