#!/usr/bin/env python3
"""Fetch every feed in feeds.opml and write normalized items to data/items.json."""
import hashlib
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_ITEMS = 500
MAX_BYTES = 3_000_000
TIMEOUT = 20
UA = "Mozilla/5.0 (compatible; rss-reader-bot/1.0)"
ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
DC_DATE = "{http://purl.org/dc/elements/1.1/}date"


def load_feeds():
    tree = ET.parse(ROOT / "feeds.opml")
    feeds = []

    def walk(node, category):
        for o in node.findall("outline"):
            url = o.get("xmlUrl")
            if url:
                feeds.append({"title": o.get("text") or o.get("title") or url,
                              "url": url, "category": category})
            else:
                walk(o, o.get("text") or category)

    walk(tree.getroot().find("body"), "Uncategorized")
    return feeds


def clean(text, limit=300):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def text_of(el, *tags):
    for tag in tags:
        child = el.find(tag)
        if child is not None and (child.text or "").strip():
            return child.text
    return ""


def atom_link(entry):
    links = entry.findall(ATOM + "link")
    for link in links:
        if link.get("rel", "alternate") == "alternate" and link.get("href"):
            return link.get("href")
    return links[0].get("href", "") if links else ""


def parse_feed(data):
    root = ET.fromstring(data)
    items = []
    if root.tag == ATOM + "feed":
        for e in root.findall(ATOM + "entry"):
            items.append({
                "title": text_of(e, ATOM + "title"),
                "link": atom_link(e),
                "guid": text_of(e, ATOM + "id"),
                "date": text_of(e, ATOM + "published", ATOM + "updated"),
                "summary": text_of(e, ATOM + "summary", ATOM + "content"),
            })
    else:
        for e in root.iter("item"):
            items.append({
                "title": text_of(e, "title"),
                "link": text_of(e, "link"),
                "guid": text_of(e, "guid"),
                "date": text_of(e, "pubDate", DC_DATE),
                "summary": text_of(e, "description", CONTENT),
            })
    return items


def fetch(feed):
    try:
        req = urllib.request.Request(feed["url"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read(MAX_BYTES)
        raw = parse_feed(data)
    except Exception as exc:  # one bad feed must not fail the run
        print(f"FAIL {feed['title']}: {exc}", file=sys.stderr)
        return feed, []
    out = []
    for r in raw:
        link = r["link"].strip()
        # Only http(s) links; anything else (javascript:, data:) is dropped.
        if not link.lower().startswith(("http://", "https://")) or not r["title"].strip():
            continue
        dt = parse_date(r["date"])
        key = r["guid"].strip() or link
        out.append({
            "id": hashlib.sha1(key.encode()).hexdigest()[:12],
            "feed": feed["title"],
            "category": feed["category"],
            "title": clean(r["title"], 200),
            "link": link,
            "date": dt.isoformat() if dt else None,
            "summary": clean(r["summary"]),
        })
    print(f"ok   {feed['title']}: {len(out)} items")
    return feed, out


def main():
    feeds = load_feeds()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fetch, feeds))
    now = datetime.now(timezone.utc).isoformat()
    seen, items = set(), []
    for _, feed_items in results:
        for it in feed_items:
            if it["id"] not in seen:
                seen.add(it["id"])
                items.append(it)
    items.sort(key=lambda i: i["date"] or "", reverse=True)
    items = items[:MAX_ITEMS]
    if not items:
        sys.exit("No items fetched; leaving items.json untouched")
    ok = [f["title"] for f, fi in results if fi]
    payload = {"generated": now, "feeds": [
        {"title": f["title"], "category": f["category"], "url": f["url"]} for f in feeds if f["title"] in ok],
        "items": items}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "items.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(items)} items from {len(ok)}/{len(feeds)} feeds")


if __name__ == "__main__":
    main()
