#!/usr/bin/env python3
"""Check whether the videos saved in data/videos.json can be played inside a web page.

Run:  python3 scripts/check_embeds.py
Needs YOUTUBE_API_KEY (in your environment or in the .env file). Costs about 2 quota units, so it is free.
It changes nothing. It only prints a report.
"""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def key():
    k = os.environ.get("YOUTUBE_API_KEY")
    if k:
        return k
    for name in (".env", "env"):
        p = ROOT / name
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("YOUTUBE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')
    return None


def main():
    k = key()
    if not k:
        raise SystemExit("No YOUTUBE_API_KEY found. Put it in the .env file first.")
    vids = json.loads((ROOT / "data" / "videos.json").read_text())
    ids = sorted({v["id"] for v in vids.values() if v and v.get("id")})
    ok, bad = [], []
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        qs = urllib.parse.urlencode({"part": "status,snippet", "id": ",".join(chunk), "key": k})
        with urllib.request.urlopen("https://www.googleapis.com/youtube/v3/videos?" + qs, timeout=30) as r:
            items = {x["id"]: x for x in json.load(r).get("items", [])}
        for vid in chunk:
            x = items.get(vid)
            if x and x["status"].get("embeddable") and x["status"].get("privacyStatus") == "public":
                ok.append(vid)
            else:
                bad.append((vid, "gone or private" if not x else "owner blocks embedding"))
    print(f"{len(ids)} videos checked: {len(ok)} can be embedded, {len(bad)} cannot.")
    for vid, why in bad:
        print(f"  {vid}: {why}")


if __name__ == "__main__":
    main()
