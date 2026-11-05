#!/usr/bin/env python3
"""Builds ONE self-contained, ADHD-friendly step-by-step guide (a single .html file) from a steps.json file.

Use:   python3 build_guide.py path/to/steps.json path/to/output.html
Needs: only Python 3 (nothing to install). Pictures and fonts are packed INTO the html, so it works offline
       and you can send it as one file.
"""
import base64, html, json, mimetypes, os, sys

CSS = r"""
:root{color-scheme:light dark;--bg:#f3f3f1;--card:#fff;--fg:#1b1c1e;--muted:#5d6066;--line:#dcdcd8;--accent:#c47f14;--accent-soft:#f6e6c9;--ok:#2f8f5b;--ok-soft:#dff3e8;--key:#f7f7f5;--shot:#141516;
--sans:"GuideSans",system-ui,-apple-system,"Segoe UI",sans-serif;--cond:"GuideCond","Arial Narrow",system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#141516;--card:#1c1d1f;--fg:#e6e6e3;--muted:#a0a3a8;--line:#33363a;--accent:#e3a23b;--accent-soft:#3a2c14;--ok:#5cc489;--ok-soft:#18301f;--key:#25272a;--shot:#0b0b0c}}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:84px}
body{margin:0;background:var(--bg);color:var(--fg);font:18px/1.55 var(--sans)}
.bar{position:sticky;top:0;z-index:10;background:var(--card);border-bottom:1px solid var(--line);padding:10px 16px}
.bar-in{max-width:900px;margin:0 auto;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.where-am-i{font:600 20px var(--cond);letter-spacing:.02em;white-space:nowrap}
.track{flex:1;min-width:120px;height:12px;background:var(--line);border-radius:99px;overflow:hidden}
.fill{height:100%;width:0;background:var(--ok);transition:width .3s}
.btn{font:600 16px var(--sans);border:2px solid var(--accent);background:var(--accent-soft);color:var(--fg);border-radius:10px;padding:8px 14px;cursor:pointer}
.btn:focus-visible,.did:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.wrap{max-width:900px;margin:0 auto;padding:28px 16px 80px;display:flex;flex-direction:column;gap:28px}
.eyebrow{font:600 13px var(--cond);letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
h1{margin:4px 0 8px;font:600 clamp(32px,6vw,48px)/1.05 var(--cond)}
.lede{margin:0;color:var(--muted);font-size:20px;max-width:34em}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:16px;font:600 15px var(--cond);letter-spacing:.06em;text-transform:uppercase}
.flow span{background:var(--card);border:1px solid var(--line);border-radius:99px;padding:5px 12px}.flow b{color:var(--muted)}
.time-all{margin-top:12px;color:var(--muted)}
.cheat{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px}
.cheat h2{margin:0 0 12px;font:600 15px var(--cond);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.keys{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
.k{display:flex;align-items:center;gap:12px}
kbd{font:600 20px var(--sans);background:var(--key);border:1px solid var(--line);border-bottom-width:3px;border-radius:8px;padding:5px 12px;min-width:2.4em;text-align:center;white-space:nowrap}
ol.steps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:24px}
.step{background:var(--card);border:2px solid var(--line);border-radius:16px;padding:20px;display:grid;grid-template-columns:58px minmax(0,1fr);gap:6px 16px;transition:opacity .2s,border-color .2s}
.step.done{opacity:.55;border-color:var(--ok)}
.num{width:52px;height:52px;border-radius:50%;background:var(--accent);color:#1a1306;font:600 26px var(--cond);display:flex;align-items:center;justify-content:center}
.step.done .num{background:var(--ok);color:#fff}
.body{display:flex;flex-direction:column;gap:8px;min-width:0}
.step h2{margin:4px 0 0;font:600 28px/1.15 var(--cond)}
.meta{display:flex;flex-wrap:wrap;gap:8px;font-size:14px}
.chip{border-radius:6px;padding:2px 9px;font:600 12px var(--cond);letter-spacing:.1em;text-transform:uppercase;background:var(--accent-soft);color:var(--fg)}
.chip.time{background:var(--key);border:1px solid var(--line)}.chip.new{background:var(--ok-soft);color:var(--ok)}
.where{margin:0;color:var(--muted);font-size:16px}
.do{margin:4px 0 0;padding-left:22px;display:flex;flex-direction:column;gap:8px;font-size:20px}
.see{margin:6px 0 0;padding:10px 14px;border-left:5px solid var(--ok);background:var(--ok-soft);border-radius:0 10px 10px 0;font-size:17px}
.tip{margin:4px 0 0;padding:10px 14px;border-left:5px solid var(--accent);background:var(--accent-soft);border-radius:0 10px 10px 0;font-size:17px}
figure{grid-column:1/-1;margin:12px 0 0;background:var(--shot);border-radius:12px;overflow:hidden;border:1px solid var(--line)}
figure img{display:block;width:100%;height:auto}figcaption{padding:8px 12px;font-size:14px;color:#c9c9c6}
figure img{cursor:zoom-in}
figure img.zoom{position:fixed;inset:0;z-index:50;width:100vw;height:100vh;object-fit:contain;background:rgba(0,0,0,.92);cursor:zoom-out;padding:12px}
.did{grid-column:1/-1;margin-top:14px;font:600 20px var(--sans);border:3px solid var(--ok);background:transparent;color:var(--fg);border-radius:12px;padding:14px;cursor:pointer}
.did:hover{background:var(--ok-soft)}.step.done .did{background:var(--ok);color:#fff}
.stuck{background:var(--card);border:2px solid var(--line);border-radius:16px;padding:6px 20px}
.stuck summary{cursor:pointer;font:600 26px var(--cond);padding:14px 0}
.stuck dl{margin:0 0 14px}.stuck dt{font-weight:600;margin-top:12px}.stuck dd{margin:2px 0 0;color:var(--muted)}
.finish{display:none;text-align:center;background:var(--ok-soft);border:3px solid var(--ok);border-radius:16px;padding:26px}
.finish.show{display:block}.finish h2{margin:0 0 6px;font:600 34px var(--cond)}
footer{text-align:center;color:var(--muted);font-size:15px}
@media (max-width:560px){.step{grid-template-columns:44px minmax(0,1fr);padding:14px}.num{width:40px;height:40px;font-size:20px}.step h2{font-size:24px}.do{font-size:19px}}
@media print{.bar,.did,.btn{display:none}.step{break-inside:avoid;opacity:1}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
"""

JS = r"""
const KEY='guide-progress-'+GUIDE_ID;let done=new Set(JSON.parse(localStorage.getItem(KEY)||'[]'));
const steps=[...document.querySelectorAll('.step')],N=steps.length;
function paint(){steps.forEach((s,i)=>{const d=done.has(i);s.classList.toggle('done',d);const b=s.querySelector('.did');b.setAttribute('aria-pressed',d);b.textContent=d?'Done. Tap to undo':'I did this step'});
 document.querySelector('.fill').style.width=(done.size/N*100)+'%';
 document.getElementById('count').textContent=done.size+' of '+N+' done';
 document.querySelector('.finish').classList.toggle('show',done.size===N);
 localStorage.setItem(KEY,JSON.stringify([...done]))}
steps.forEach((s,i)=>s.querySelector('.did').addEventListener('click',()=>{if(done.has(i))done.delete(i);else{done.add(i);const nx=steps.find((x,j)=>j>i&&!done.has(j));if(nx)setTimeout(()=>nx.scrollIntoView({behavior:'smooth',block:'start'}),250)}paint()}));
document.getElementById('resume').addEventListener('click',()=>{const nx=steps.find((x,j)=>!done.has(j));(nx||steps[0]).scrollIntoView({behavior:'smooth',block:'start'})});
document.getElementById('reset').addEventListener('click',()=>{if(confirm('Start over? This clears your ticks on this device.')){done=new Set();paint();window.scrollTo(0,0)}});
document.querySelectorAll('figure img').forEach(im=>im.addEventListener('click',()=>im.classList.toggle('zoom')));
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('img.zoom').forEach(i=>i.classList.remove('zoom'))});
paint();
"""

def esc(s): return html.escape(str(s), quote=True)

def data_uri(path):
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if path.endswith(".woff2"): mime = "font/woff2"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()

def build(cfg_path, out_path):
    base = os.path.dirname(os.path.abspath(cfg_path))
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    steps = cfg["steps"]
    fonts = ""
    for f in cfg.get("fonts", []):
        p = os.path.join(base, f["path"])
        fonts += f'@font-face{{font-family:"{f["family"]}";font-weight:{f.get("weight",400)};src:url({data_uri(p)}) format("woff2")}}\n'
    total = sum(s.get("minutes", 1) for s in steps)
    parts = []
    parts.append(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                 f'<title>{esc(cfg["title"])}</title><style>{fonts}{CSS}</style></head><body>')
    parts.append(f'<div class="bar"><div class="bar-in"><span class="where-am-i" id="count">0 of {len(steps)} done</span>'
                 f'<div class="track" aria-hidden="true"><div class="fill"></div></div><button class="btn" id="resume" type="button">Where was I?</button></div></div>')
    parts.append('<main class="wrap"><header>')
    parts.append(f'<div class="eyebrow">{esc(cfg.get("eyebrow",""))}</div><h1>{esc(cfg["title"])}</h1><p class="lede">{esc(cfg.get("lede",""))}</p>')
    if cfg.get("flow"):
        parts.append('<div class="flow">' + '<b>&rarr;</b>'.join(f'<span>{esc(x)}</span>' for x in cfg["flow"]) + '</div>')
    parts.append(f'<p class="time-all">{len(steps)} steps. About {total} minutes start to finish. You can stop any time. Your ticks are saved.</p></header>')
    if cfg.get("keys"):
        parts.append('<section class="cheat"><h2>Keys to remember</h2><div class="keys">' +
                     ''.join(f'<div class="k"><kbd>{esc(k["key"])}</kbd><span>{esc(k["does"])}</span></div>' for k in cfg["keys"]) + '</div></section>')
    parts.append('<ol class="steps">')
    for i, s in enumerate(steps, 1):
        chips = f'<span class="chip time">About {s.get("minutes",1)} min</span>'
        if s.get("new"): chips = '<span class="chip new">New</span>' + chips
        parts.append(f'<li class="step" id="step{i}"><div class="num">{i}</div><div class="body"><div class="meta">{chips}</div><h2>{esc(s["title"])}</h2>')
        if s.get("where"): parts.append(f'<p class="where"><b>Where:</b> {esc(s["where"])}</p>')
        parts.append('<ul class="do" style="list-style:decimal">' + ''.join(f'<li>{s_html}</li>' for s_html in (fmt(x) for x in s["do"])) + '</ul>')
        if s.get("see"): parts.append(f'<div class="see"><b>You will see:</b> {fmt(s["see"])}</div>')
        if s.get("tip"): parts.append(f'<div class="tip"><b>Tip:</b> {fmt(s["tip"])}</div>')
        parts.append('</div>')
        if s.get("image"):
            parts.append(f'<figure><img alt="{esc(s.get("alt", s["title"]))}" src="{data_uri(os.path.join(base, s["image"]))}">'
                         + (f'<figcaption>{esc(s["caption"])} Tap the picture to make it bigger.</figcaption>' if s.get("caption") else '') + '</figure>')
        parts.append('<button class="did" type="button" aria-pressed="false">I did this step</button></li>')
    parts.append('</ol>')
    parts.append(f'<section class="finish"><h2>{esc(cfg.get("finish_title","All done."))}</h2><p>{esc(cfg.get("finish_text","Nice work."))}</p></section>')
    if cfg.get("stuck"):
        parts.append('<details class="stuck" id="stuck"><summary>Stuck? Start here.</summary><dl>' +
                     ''.join(f'<dt>{esc(x["problem"])}</dt><dd>{fmt(x["fix"])}</dd>' for x in cfg["stuck"]) + '</dl></details>')
    parts.append(f'<footer>{esc(cfg.get("footer",""))}<br><button class="btn" id="reset" type="button">Start over (clear ticks)</button></footer></main>')
    gid = esc(cfg.get("id", cfg["title"]))
    parts.append(f'<script>const GUIDE_ID="{gid}";{JS}</script></body></html>')
    with open(out_path, "w", encoding="utf-8") as f: f.write("".join(parts))
    print(f"Built {out_path}  ({os.path.getsize(out_path)//1024} KB, {len(steps)} steps, about {total} min)")

def fmt(text):
    """**bold** and [[Key]] become <b> and <kbd>. Everything else is escaped."""
    t = esc(text)
    import re
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\[\[(.+?)\]\]", r"<kbd>\1</kbd>", t)
    return t

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Use: python3 build_guide.py steps.json output.html")
    build(sys.argv[1], sys.argv[2])
