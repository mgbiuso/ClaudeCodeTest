#!/usr/bin/env python3
"""Write short newspaper headlines with Claude, one batch per day file.

Safeguards
- The key comes from the environment or .env and is never printed or logged.
- Headlines may use only facts that are in that story's text. Names and numbers are checked against
  the text, and anything that fails is retried once, then left to the rule-based fallback.
- Results are cached in data/headlines.json (key = hash of year + text), so reruns cost nothing
  and the file can be edited by hand.
- --dry-run shows counts and a token estimate without calling the API.
- A run that would need more headlines than --max-stories (default 250) is refused.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_days as b  # noqa: E402  (story_key, ROOT)

ROOT = b.ROOT
DAYS = ROOT / "data" / "days"
CACHE_FILE = ROOT / "data" / "headlines.json"
API = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-5-5"
BATCH = 25

SYSTEM = """You write headlines for the baseball "on this day" page of a newspaper.

Rules, all strict:
- Write each headline in sentence case: capitalize only the first word and proper names. (The page applies Title Case afterwards.) 35 to 65 characters, never over 70, no period, no ellipsis, no quotation marks, no exclamation mark.
- Newspaper voice: short, active, PRESENT tense for every event, even old ones. Never past tense. Drop filler words. A passive like "Boog Powell named AL MVP" is fine.
  Bad: "Yount threw out the first pitch before Game 7 of the National League". Good: "Yount throws out first pitch before Game 7".
  Bad: "The Dodgers advanced to the World Series with a 5-1 win". Good: "Dodgers beat Brewers 5-1, advance to World Series".
  Good: "Reds beat Oakland 2-1, complete stunning World Series sweep".
- Items marked "obituary" are about a person who died that year. Write only: Name, age, role. Example: "Derryl Cousins, 74, longtime MLB umpire". Never use die, died, dies, death, dead, passes, passed, late or remembered. Use only the role and age given in the text; if the age is not given, write "Name, role".
- Use ONLY facts, names and numbers that appear in that story's text. Never add a date, score, name, team, number or claim that is not in the text. Do not write "today" or "this day".
- Prefer the most interesting fact in the text. Keep it a complete thought, never cut off mid-phrase.
Return only JSON in this shape: {"headlines": [{"id": "...", "headline": "..."}]}"""

BANNED_OBIT = re.compile(r"\b(die[sd]?|death|dead|pass(?:es|ed)(?: away)?|late|remembered|rip)\b", re.I)


def load_env():
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        m = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line.strip())
        if m and m.group(1) not in os.environ and m.group(2).strip():
            os.environ[m.group(1)] = m.group(2).strip()


def load_cache():
    try:
        return json.loads(CACHE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1))


def day_files(dates, all_days):
    if all_days or not dates:
        return sorted(DAYS.glob("*.json"))
    return [DAYS / f"{int(d.split('/')[0]):02d}-{int(d.split('/')[1]):02d}.json" for d in dates]


def check(headline, text, obit=False):
    """Return None if the headline is acceptable, else the reason it is not."""
    h = headline.strip()
    if obit and BANNED_OBIT.search(h):
        return "an obituary headline must not say dies, died, death or similar"
    if not 20 <= len(h) <= 75:
        return "length"
    if "…" in h or "..." in h or h[-1] in ".,;:-" or h[0] in "\"'“‘" or "!" in h:
        return "punctuation"
    low = text.lower()
    for n in re.findall(r"\d[\d,.]*\d|\d", h):
        if n not in text:
            return f"number {n} is not in the text"
    words = re.findall(r"[A-Za-z][A-Za-z'’.\-]*", h)
    for w in words[1:]:
        core = w.strip(".'’-").lower()
        if w.isupper() and 2 <= len(core) <= 5:  # NLCS, ALCS, MLB, MVP: abbreviations are fine
            continue
        if w[0].isupper() and core and core not in low:
            return f"name {w} is not in the text"
    return None


def call_api(model, items, extra=""):
    body = {
        "model": model,
        "max_tokens": 3000,
        "thinking": {"type": "disabled"},  # headlines need no hidden reasoning; with it on, the token limit was used up and no text came back
        "system": SYSTEM,
        "messages": [{"role": "user", "content": json.dumps(items, ensure_ascii=False) + extra}],
    }
    req = urllib.request.Request(API, method="POST", data=json.dumps(body).encode(), headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    delay = 5
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
            # The reply can start with a "thinking" block; use only the text blocks.
            if data.get("stop_reason") == "max_tokens":
                raise ValueError("reply was cut off at the token limit")
            text = "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text")
            usage = data.get("usage", {})
            m = re.search(r"\{.*\}", text, re.S)
            return json.loads(m.group(0))["headlines"], usage
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529):
                print(f"  API busy ({e.code}), waiting {delay}s", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            try:
                msg = json.load(e).get("error", {}).get("message", "")[:200]
            except Exception:
                msg = ""
            sys.exit(f"Anthropic API error {e.code}: {msg}")
        except (ValueError, KeyError, AttributeError) as e:
            last = f"could not read the reply ({type(e).__name__})"
            time.sleep(2)
    sys.exit(f"Gave up after repeated errors: {last if 'last' in dir() else 'API busy'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="*", help="MM/DD (default: every day file that exists)")
    ap.add_argument("--all", action="store_true", help="every day file in data/days")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--redo", action="store_true", help="write new headlines even where one is cached (for a changed style)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-stories", type=int, default=250, help="refuse to run if more headlines than this are needed")
    a = ap.parse_args()

    load_env()
    cache = load_cache()
    files = [f for f in day_files(a.dates, a.all) if f.exists()]
    todo, total = [], 0
    for f in files:
        for st in json.loads(f.read_text())["stories"]:
            total += 1
            key = b.story_key(st["year"], st["text"])
            if a.redo or key not in cache:
                todo.append({"id": key, "year": st["year"], "type": "obituary" if st["kind"] == "death" else "event", "text": st["text"]})
    todo = list({t["id"]: t for t in todo}.values())
    chars = sum(len(t["text"]) + 60 for t in todo)
    batches = -(-len(todo) // BATCH)
    est_in = chars // 4 + batches * 330
    est_out = len(todo) * 25 + batches * 20
    print(f"{len(files)} day files, {total} stories, {total - len(todo)} already cached, {len(todo)} need headlines")
    print(f"{batches} requests, roughly {est_in:,} input and {est_out:,} output tokens (model {a.model})")
    if a.dry_run or not todo:
        return
    if len(todo) > a.max_stories:
        sys.exit(f"Refusing: {len(todo)} headlines needed, limit is {a.max_stories}. Rerun with --max-stories {len(todo)} to confirm.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is missing. Add it to .env (see SETUP.md).")

    if a.redo:  # drop the old style so a failed rewrite falls back to the rule-based headline, not the old one
        for item in todo:
            cache.pop(item["id"], None)
    used_in = used_out = rejected = 0
    by_id = {t["id"]: t for t in todo}
    retry = []
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        out, usage = call_api(a.model, chunk)
        used_in += usage.get("input_tokens", 0)
        used_out += usage.get("output_tokens", 0)
        got = {h.get("id"): str(h.get("headline", "")) for h in out}
        for t in chunk:
            h = got.get(t["id"], "")
            why = check(h, t["text"], t["type"] == "obituary") if h else "missing"
            if why:
                retry.append((t, h, why))
            else:
                cache[t["id"]] = b.title_case(h.strip())
        save_cache(cache)
        print(f"  {min(i + BATCH, len(todo))}/{len(todo)}")
    for t, h, why in retry:  # one stricter second try for each rejected headline
        note = f'\n\nYour earlier headline "{h}" was rejected because: {why}. Use only words and numbers that appear in the text.'
        out, usage = call_api(a.model, [t], note)
        used_in += usage.get("input_tokens", 0)
        used_out += usage.get("output_tokens", 0)
        h2 = str(out[0].get("headline", "")) if out else ""
        if h2 and not check(h2, t["text"], t["type"] == "obituary"):
            cache[t["id"]] = b.title_case(h2.strip())
        else:
            rejected += 1
            print(f"  kept rule-based headline for {t['year']}: {t['text'][:60]}...")
    save_cache(cache)

    changed = 0
    for f in files:
        data = json.loads(f.read_text())
        for st in data["stories"]:
            new = cache.get(b.story_key(st["year"], st["text"]))
            if new and st.get("headline") != new:
                st["headline"] = new
                changed += 1
        f.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"done: {len(todo) - rejected} headlines written, {rejected} left to the fallback, {changed} day-file headlines updated")
    print(f"tokens used: {used_in:,} input, {used_out:,} output")


if __name__ == "__main__":
    main()
