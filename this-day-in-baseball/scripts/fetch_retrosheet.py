#!/usr/bin/env python3
"""Download Retrosheet's game logs into .cache/retrosheet/ (git-ignored). Run once; reruns skip files already there.

The data is free to use when this credit is shown: "The information used here was obtained free of charge from
and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at www.retrosheet.org."
Files are fetched one at a time with a pause, with a descriptive User-Agent. About 40 MB in total (game logs, people and
ballparks, ejections, transactions).
"""
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / ".cache" / "retrosheet"
BASE = "https://www.retrosheet.org/"
FILES = ["gamelogs/gl1871_2025.zip", "gamelogs/glws.zip", "gamelogs/gldv.zip", "gamelogs/gllc.zip",
         "gamelogs/glwc.zip", "gamelogs/glas.zip", "TEAMABR.TXT",
         "downloads/biodata.zip", "ejections.zip", "transactions/tranDB.zip"]
# Retrosheet's own lists of feats and milestones (small web pages), saved in .cache/retrosheet/lists/.
LISTS = ["cycles.htm", "TriplePlays.htm", "hr4cons.htm", "forfeits.htm", "Hidden%20Ball%20Tricks.htm", "miles-h.htm", "miles-hr.htm",
         "miles-sb.htm", "miles-w.htm", "miles-k.htm", "miles-sv.htm"]
UA = "ThisDayInBaseball/1.0 (personal history site; retrosheet game logs)"


def fetch(rel, out):
    req = urllib.request.Request(BASE + rel, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    out.write_bytes(data)
    return data


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "lists").mkdir(exist_ok=True)
    for rel in LISTS:
        out = DEST / "lists" / rel.replace("%20", "_")
        if out.exists() and out.stat().st_size > 0:
            print(f"have lists/{out.name}")
            continue
        data = fetch(rel, out)
        print(f"got lists/{out.name} ({len(data):,} bytes)")
        time.sleep(2)
    for rel in FILES:
        out = DEST / Path(rel).name
        if out.exists() and out.stat().st_size > 0:
            print(f"have {out.name}")
            continue
        req = urllib.request.Request(BASE + rel, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        out.write_bytes(data)
        if out.suffix == ".zip":
            zipfile.ZipFile(out).testzip()  # raises if the download is damaged
        print(f"got {out.name} ({len(data):,} bytes)")
        time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
