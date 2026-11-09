#!/usr/bin/env python3
"""Build the one-line-per-park ballpark art checklist.

Reads the park and photo data out of the OLD checklist (the backup copy), keeps the best free photo for each park,
and writes a compact page: one park per line, source next to it.

Run:  python3 art/ballparks/build_checklist.py
Writes: art/ballparks/checklist.html            (open this one on your Mac)
        the file given with --fragment          (the same page without the html wrapper, for publishing)
Finished pictures are detected from images/ballparks/*.webp. Checkmarks you click are kept in your browser.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OLD = ROOT / "_backup_before_changes" / "checklist.before_oneline.html"
OUT = ROOT / "art" / "ballparks" / "checklist.html"
IMAGES = ROOT / "images" / "ballparks"


def short_title(t):
    t = re.sub(r"\.(jpe?g|png|tiff?|gif)$", "", t, flags=re.I)
    t = re.sub(r"\s*LCCN\d+", "", t)
    t = re.sub(r"\s*\(baseball\)", "", t)
    t = re.sub(r"\s*\([\d.]+[A-Za-z.]*\)", "", t)
    t = t.replace("File:", "").strip()
    return t if len(t) <= 58 else t[:57].rstrip() + "..."


def best_photo(photos):
    """Prefer: right city, public domain, then the script's own score."""
    if not photos:
        return None
    return max(photos, key=lambda p: (p["city_ok"], p["tier"] == "pd", p.get("score", 0), p["w"] * p["h"]))


def load_data():
    s = OLD.read_text(encoding="utf-8")
    i = s.index("const D = ") + len("const D = ")
    d, _ = json.JSONDecoder().raw_decode(s[i:])
    return d


def compact(d):
    out = []
    for p in d["parks"]:
        b = best_photo(p["photos"])
        row = {"c": p["code"], "n": p["name"], "city": p["city"], "st": p["state"], "a": p.get("first"), "z": p.get("last"),
               "one": bool(p["oneoff"]), "more": max(0, len(p["photos"]) - 1), "L": p["links"]}
        if b:
            year = re.search(r"\b(1[89]\d\d|20\d\d)\b", b.get("date") or "")
            row["b"] = {"t": short_title(b["title"]), "pg": b["page"], "lic": "Public domain" if b["tier"] == "pd" else b["license"],
                        "pd": b["tier"] == "pd", "ok": b["city_ok"], "d": year.group(1) if year else ""}
        out.append(row)
    return out


CSS = """
:root { --paper:#e2dfd2; --paper-2:#d3cfbf; --ink:#0f1519; --soft:#3b444a; --red:#b3202a; --green:#1c6b3a; --amber:#7a4e00; --navy:#1f4e8c;
  --sans:"Franklin Gothic Medium","Franklin Gothic","Arial Narrow",Arial,sans-serif; --type:"Courier New",Courier,monospace; color-scheme:light; }
* { box-sizing:border-box; }
body { margin:0; background:var(--paper); color:var(--ink); font:15px/1.35 var(--sans); }
header { position:sticky; top:0; z-index:5; background:var(--paper); border-bottom:3px double var(--ink);
  padding-block:10px; padding-left:max(16px,env(safe-area-inset-left,0px)); padding-right:max(16px,env(safe-area-inset-right,0px)); }
h1 { margin:0 0 6px; font:700 24px/1.1 "Arial Narrow",Arial,sans-serif; text-transform:uppercase; letter-spacing:.5px; }
.bar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
input[type=search] { flex:1 1 200px; min-width:0; padding:7px 8px; border:2px solid var(--ink); background:#fff; font:inherit; }
button, select { padding:7px 10px; border:2px solid var(--ink); background:var(--paper-2); font:inherit; cursor:pointer; color:var(--ink); }
button:hover, select:hover { background:#fff; }
:focus-visible { outline:3px solid var(--red); outline-offset:2px; }
#count { color:var(--soft); font-size:14px; }
.how { margin:6px 0 0; font-size:13px; color:var(--soft); }
.how code, .cmd { font-family:var(--type); font-size:12px; }
main { padding-block:6px 40px; padding-left:max(16px,env(safe-area-inset-left,0px)); padding-right:max(16px,env(safe-area-inset-right,0px)); }
.park { display:grid; grid-template-columns:28px minmax(0,1fr); gap:2px 8px; padding:7px 0; border-bottom:1px solid var(--ink); align-items:start; }
.park.done { opacity:.5; }
.park input { width:20px; height:20px; margin:2px 0 0; }
.who { min-width:0; }
.nm { font-weight:700; text-transform:uppercase; letter-spacing:.2px; }
.meta { color:var(--soft); font-size:13px; }
.tag { border:1px solid var(--red); color:var(--red); font-size:11px; padding:0 4px; margin-left:6px; text-transform:uppercase; white-space:nowrap; }
.src { grid-column:2; min-width:0; font-size:14px; }
.src a { color:var(--navy); }
.badge { font-family:var(--type); font-size:12px; font-weight:700; margin-right:4px; }
.pd { color:var(--green); } .cc { color:var(--amber); } .bad { color:var(--red); }
.soft { color:var(--soft); }
.cmd { margin-left:6px; padding:1px 6px; }
@media (min-width:860px) {
  .park { grid-template-columns:28px minmax(0,2fr) minmax(0,3fr); }
  .src { grid-column:auto; }
}
"""

JS = """
const SAFE = /^https:\\/\\/(commons\\.wikimedia\\.org|upload\\.wikimedia\\.org|www\\.loc\\.gov|en\\.wikipedia\\.org)\\//;
let stored = {};
try { stored = JSON.parse(localStorage.getItem("ballparkDone") || "{}"); } catch (e) { stored = {}; }
const finished = new Set(D.finished);
const isDone = (c) => (c in stored ? !!stored[c] : finished.has(c));
function save() { try { localStorage.setItem("ballparkDone", JSON.stringify(stored)); } catch (e) { /* page still works */ } }
function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
function link(href, text) { const a = el("a", "", text); if (SAFE.test(href)) { a.href = href; a.target = "_blank"; a.rel = "noopener"; } return a; }
function years(p) { return p.a ? (p.a === p.z ? String(p.a) : p.a + " to " + p.z) : ""; }
function copy(btn, text, label) {
  const ok = () => { btn.textContent = "Copied"; setTimeout(() => { btn.textContent = label; }, 1400); };
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(ok, () => { btn.textContent = "Copy failed"; });
  else btn.textContent = "No copy";
}
function row(p) {
  const done = isDone(p.c);
  const r = el("div", "park" + (done ? " done" : ""));
  const cb = el("input"); cb.type = "checkbox"; cb.checked = done; cb.id = "c-" + p.c; cb.setAttribute("aria-label", "Drawing finished for " + p.n);
  cb.addEventListener("change", () => { stored[p.c] = cb.checked; save(); render(); });
  const who = el("div", "who"), nm = el("span", "nm", p.n);
  if (p.one) nm.append(el("span", "tag", "one-time site"));
  who.append(nm, el("div", "meta", [p.city + ", " + p.st, years(p), p.c].filter(Boolean).join("  \\u00b7  ")));
  const s = el("div", "src");
  if (p.b) {
    s.append(el("span", "badge " + (p.b.pd ? "pd" : "cc"), p.b.pd ? "PD" : p.b.lic));
    s.append(link(p.b.pg, p.b.t));
    const bits = [p.b.d, p.b.pd ? "" : "credit required"].filter(Boolean).join(", ");
    if (bits) s.append(el("span", "soft", "  " + bits));
    if (!p.b.ok) s.append(el("span", "bad", "  check the city"));
    if (p.more) { s.append(el("span", "soft", "  +" + p.more + " more: ")); s.append(link(p.L.commons, "Commons")); }
  } else {
    s.append(el("span", "bad", "No free photo found. Search: "));
    s.append(link(p.L.commons, "Commons"), document.createTextNode(" \\u00b7 "), link(p.L.loc, "LOC"), document.createTextNode(" \\u00b7 "), link(p.L.wiki, "Wikipedia"));
  }
  const b = el("button", "cmd", "copy command"); b.type = "button";
  b.addEventListener("click", () => copy(b, "python3 scripts/park_art.py " + p.c + " art/ballparks/source/" + p.c + ".png", "copy command"));
  s.append(b);
  r.append(cb, who, s);
  return r;
}
function render() {
  const q = document.getElementById("q").value.toLowerCase(), f = document.getElementById("f").value, list = document.getElementById("list");
  list.replaceChildren();
  let n = 0, total = 0;
  D.parks.forEach((p) => {
    const d = isDone(p.c); if (d) total++;
    if (q && !(p.n + " " + p.city + " " + p.c).toLowerCase().includes(q)) return;
    if (f === "todo" && d) return;
    if (f === "photo" && (d || !p.b)) return;
    if (f === "pd" && (d || !p.b || !p.b.pd)) return;
    if (f === "nophoto" && (d || p.b)) return;
    if (f === "done" && !d) return;
    list.append(row(p)); n++;
  });
  document.getElementById("count").textContent = n + " shown. " + total + " of " + D.parks.length + " finished.";
}
document.getElementById("q").addEventListener("input", render);
document.getElementById("f").addEventListener("change", render);
const pb = document.getElementById("copy");
pb.addEventListener("click", () => copy(pb, D.prompt, "Copy the AI prompt"));
render();
"""


def body(d, parks, finished):
    data = json.dumps({"parks": parks, "finished": finished, "prompt": d["prompt"]}, separators=(",", ":"))
    return f"""<style>{CSS}</style>
<header><h1>Ballpark art checklist</h1>
<div class="bar">
<label for="q" class="soft" style="position:absolute;left:-9999px">Search</label>
<input id="q" type="search" placeholder="Search a park, city or code (for example Ebbets)">
<label for="f" class="soft" style="position:absolute;left:-9999px">Show</label>
<select id="f"><option value="todo">Not done yet</option><option value="pd">Not done, public domain photo</option><option value="photo">Not done, has a photo</option><option value="nophoto">Not done, no photo found</option><option value="done">Done</option><option value="all">All parks</option></select>
<button id="copy" type="button">Copy the AI prompt</button>
<span id="count"></span></div>
<p class="how">PD = public domain, free to use. Anything else needs a credit line. Tick the box when the finished picture exists.</p></header>
<main id="list"></main>
<script>const D = {data};
{JS}</script>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fragment", help="also write the page without the html wrapper to this path")
    a = ap.parse_args()
    d = load_data()
    parks = compact(d)
    codes = {p["c"] for p in parks}
    finished = sorted({f.stem.split("_")[0] for f in IMAGES.glob("*.webp")} & codes)
    b = body(d, parks, finished)
    OUT.write_text('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n'
                   '<title>Ballpark art checklist</title></head><body>\n' + b + "\n</body></html>\n", encoding="utf-8")
    if a.fragment:
        Path(a.fragment).write_text('<title>Ballpark Art Checklist</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n' + b + "\n", encoding="utf-8")
    print(len(parks), "parks,", len(finished), "already finished,", sum(1 for p in parks if "b" in p), "with a photo")


if __name__ == "__main__":
    main()
