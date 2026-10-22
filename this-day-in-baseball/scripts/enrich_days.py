#!/usr/bin/env python3
"""Add career lines and newspaper pages to day files that already exist, without rebuilding anything else.

  python3 scripts/enrich_days.py                  every file in data/days, career lines only (no internet needed)
  python3 scripts/enrich_days.py 10/20 10/21      just these dates
  python3 scripts/enrich_days.py --papers         also ask the Library of Congress (about 30 seconds per day)
  python3 scripts/enrich_days.py --dry-run        show what would change and write nothing

Only the new fields ("career", "papers") are touched. Stories, photos, videos and numbers stay exactly as they are.
Run scripts/extras.py --fetch-lahman once first so there are career statistics to use.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extras  # noqa: E402

DAYS = extras.ROOT / "data" / "days"


def count_careers(rec):
    n = sum(1 for k in ("debuts", "farewells") for it in (rec.get("people") or {}).get(k, []) if it.get("career"))
    return n + sum(1 for st in rec.get("stories", []) if st.get("career"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dates", nargs="*", help="MM/DD (default: every day file)")
    ap.add_argument("--papers", action="store_true", help="fetch newspaper pages that are not already saved in data/papers/")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.dates:
        files = [DAYS / f"{int(d.split('/')[0]):02d}-{int(d.split('/')[1]):02d}.json" for d in a.dates]
    else:
        files = sorted(DAYS.glob("*.json"))
    changed = 0
    for f in files:
        if not f.exists():
            print(f"{f.stem}: no day file, skipped")
            continue
        rec = json.loads(f.read_text())
        new = extras.enrich(copy.deepcopy(rec), fetch_papers=a.papers)
        same = new == rec
        print(f"{f.stem}: {count_careers(new)} career lines, {len(new.get('papers', []))} newspaper pages" + ("" if not same else " (no change)"))
        if not same:
            changed += 1
            if not a.dry_run:
                f.write_text(json.dumps(new, ensure_ascii=False, indent=1))
    print(f"\n{changed} file(s) {'would change' if a.dry_run else 'updated'}")


if __name__ == "__main__":
    main()
