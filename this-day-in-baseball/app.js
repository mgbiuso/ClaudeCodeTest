"use strict";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
                "September", "October", "November", "December"];
const DAYS_IN = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
// One accent: red carries the tags and links; everything else is ink on paper.
const ACCENTS = ["var(--red)"];

const $ = (id) => document.getElementById(id);
const monthSel = $("month");
const daySel = $("day");

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function pad(n) { return String(n).padStart(2, "0"); }

function parseHash() {
  const m = /^#?(\d{1,2})-(\d{1,2})$/.exec(location.hash);
  if (m) {
    const month = +m[1], day = +m[2];
    if (month >= 1 && month <= 12 && day >= 1 && day <= DAYS_IN[month - 1]) return { month, day };
  }
  const now = new Date();
  return { month: now.getMonth() + 1, day: now.getDate() };
}

function shift({ month, day }, by) {
  // 2024 is a leap year, so Feb 29 exists in the cycle.
  const d = new Date(2024, month - 1, day + by);
  return { month: d.getMonth() + 1, day: d.getDate() };
}

function go({ month, day }) { location.hash = `${pad(month)}-${pad(day)}`; }

function fillDays(month, keep) {
  daySel.replaceChildren();
  for (let d = 1; d <= DAYS_IN[month - 1]; d++) {
    const o = el("option", "", String(d));
    o.value = d;
    daySel.append(o);
  }
  daySel.value = Math.min(keep, DAYS_IN[month - 1]);
}

MONTHS.forEach((name, i) => {
  const o = el("option", "", name);
  o.value = i + 1;
  monthSel.append(o);
});

monthSel.addEventListener("change", () => { fillDays(+monthSel.value, +daySel.value); go({ month: +monthSel.value, day: +daySel.value }); });
daySel.addEventListener("change", () => go({ month: +monthSel.value, day: +daySel.value }));
$("today").addEventListener("click", () => { const n = new Date(); go({ month: n.getMonth() + 1, day: n.getDate() }); });

// ---------- pieces of a story ----------

function plateFor(story, accent) {
  const plate = el("div", "plate");
  plate.style.setProperty("--accent", accent);
  plate.append(el("span", "plate-year", story.year));
  if (story.about) plate.append(el("span", "plate-name", story.about));
  plate.setAttribute("role", "img");
  plate.setAttribute("aria-label", `${story.year}: ${story.about || "baseball history"}`);
  return plate;
}

function figureFor(story, accent) {
  const fig = el("figure", "media");
  const img = story.image;
  const pic = el("img", "photo");
  pic.src = img.url;
  pic.alt = img.alt || story.about || "";
  if (img.w && img.h) { pic.width = img.w; pic.height = img.h; }  // reserves the right shape before the photo loads
  pic.loading = "lazy";
  pic.decoding = "async";
  pic.addEventListener("error", () => { fig.replaceChildren(plateFor(story, accent)); });
  fig.append(pic);
  const cap = el("figcaption");
  cap.append(`${img.of || story.about || ""}. Photo: ${img.credit} (`);
  const link = el("a", "", img.license);
  link.href = img.page;
  link.rel = "noopener noreferrer";
  cap.append(link, ")");
  fig.append(cap);
  return fig;
}

// A video takes the photo's place: YouTube's still frame with a play badge that opens the video on YouTube.
// (MLB and the clubs do not let other sites play their videos inside a page, so there is no inline player.)
function videoFor(story) {
  const v = story.video;
  const fig = el("figure", "media video");
  const label = v.title || story.headline || "video";
  const link = el("a", "video-box");
  link.href = `https://www.youtube.com/watch?v=${v.id}`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.setAttribute("aria-label", `Watch on YouTube: ${label}`);
  const thumb = el("img", "video-thumb");
  thumb.src = `https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`;
  thumb.alt = "";
  thumb.loading = "lazy";
  thumb.width = 480;
  thumb.height = 360;
  link.append(thumb, el("span", "play-badge", "\u25B6"));
  fig.append(link);
  fig.append(el("figcaption", "", `Video: ${v.channel || "YouTube"}. ${label}`));
  return fig;
}

const hasVideo = (s) => s.video && /^[\w-]{11}$/.test(s.video.id);
const hasMedia = (s) => hasVideo(s) || s.image;

function kickerFor(story, tag) {
  const k = el("div", "kicker");
  k.append(el("span", "yr", story.year), el("span", "tag", tag));
  const ago = new Date().getFullYear() - (+story.year || 0);
  if (ago >= 25 && ago % 25 === 0) k.append(el("span", "anniv", `${ago} years ago`));
  return k;
}

function bodyFor(story) {
  const body = el("div", "body");
  body.append(el("p", "", story.text));
  if (story.page) {
    const more = el("p", "more");
    const a = el("a", "", "Read more");
    a.href = story.page;
    a.rel = "noopener noreferrer";
    more.append(a);
    body.append(more);
  }
  return body;
}

function card(story, { tag, accent, cls }) {
  const index = story.__i;
  const node = el("article", `story ${cls || ""}${story.kind === "death" ? " death" : ""}`);
  if (index != null) node.id = `story-${index}`;
  node.style.setProperty("--accent", accent);
  const head = el("div", "head");
  head.append(kickerFor(story, tag), el("h3", "headline", story.headline || story.text));
  node.append(head);
  if (hasVideo(story)) node.append(videoFor(story));
  else if (story.image) node.append(figureFor(story, accent));
  node.append(bodyFor(story));
  return node;
}

function brief(story, accent, tag = "li") {
  const li = el(tag, tag === "li" ? "" : "brief-item");
  li.style.setProperty("--accent", accent);
  li.append(el("span", "yr", story.year), `${story.text} `);
  if (story.page) {
    const a = el("a", "more", "More");
    a.href = story.page;
    a.rel = "noopener noreferrer";
    li.append(a);
  }
  return li;
}

// ---------- page ----------

const wide = window.matchMedia("(min-width: 900px)");
let columnJobs = [];   // each: { box, nodes } so columns can be rebuilt when the window changes

// Deal stories into columns like a newspaper, so the column bottoms line up as closely as the stories allow.
// Each story's height is measured once, then the best split into columns is searched for; inside a column
// the stories stay in their original (ranked) order.
function fillColumns({ box, nodes, fillers = [] }) {
  const count = wide.matches ? Math.min(3, nodes.length) : 1;  // fewer stories than columns: use fewer columns
  box.style.setProperty("--n", count);
  box.replaceChildren();
  const cols = Array.from({ length: count }, () => el("div", "col"));
  box.append(...cols);
  if (count === 1) { cols[0].append(...nodes); return; }

  const probe = cols[Math.min(1, count - 1)];  // a middle column has the narrowest text width, so measure there
  const heights = nodes.map((node) => { probe.append(node); return node.offsetHeight; });
  const spread = (sums) => Math.max(...sums) - Math.min(...sums);
  const sumsOf = (assign) => { const s = new Array(count).fill(0); assign.forEach((c, i) => { s[c] += heights[i]; }); return s; };

  // Start with tallest-first into the shortest column, then try single moves and swaps while they help.
  const order = nodes.map((_, i) => i).sort((x, y) => heights[y] - heights[x]);
  const assign = new Array(nodes.length).fill(0);
  const sums = new Array(count).fill(0);
  for (const i of order) { const c = sums.indexOf(Math.min(...sums)); assign[i] = c; sums[c] += heights[i]; }
  for (let pass = 0; pass < 50; pass++) {
    let best = spread(sumsOf(assign)), change = null;
    for (let i = 0; i < nodes.length; i++) {
      const was = assign[i];
      for (let c = 0; c < count; c++) {
        if (c === was) continue;
        assign[i] = c;
        const s = spread(sumsOf(assign));
        if (s < best) { best = s; change = [i, c, null]; }
        for (let j = i + 1; j < nodes.length; j++) {
          if (assign[j] !== c) continue;  // swap with a story that sits in the target column
          assign[j] = was;
          const s2 = spread(sumsOf(assign));
          if (s2 < best) { best = s2; change = [i, c, j]; }
          assign[j] = c;
        }
      }
      assign[i] = was;
    }
    if (!change) break;
    const [i, c, j] = change;
    const was = assign[i];
    assign[i] = c;
    if (j !== null) assign[j] = was;
  }
  nodes.forEach((node, i) => cols[assign[i]].append(node));

  // Short text-only items fill whatever is left at the bottom of the shorter columns.
  const labelled = new Set();
  for (const item of fillers) {
    const col = cols.reduce((x, y) => (x.offsetHeight <= y.offsetHeight ? x : y));
    if (!labelled.has(col)) { col.append(el("h3", "brief-label", "In brief")); labelled.add(col); }
    col.append(item);
  }
}

function columnBox(cls, nodes, fillers) {
  const box = el("div", `cols ${cls}`);
  columnJobs.push({ box, nodes, fillers });
  return box;
}

// ---------- Retrosheet extras ----------
// An almanac-style strip of Retrosheet facts about every game ever played on this date, then the game of the day,
// small charts by decade, team records and the record book. Everything is set with textContent / SVG built by hand.

const SVG_NS = "http://www.w3.org/2000/svg";
function svg(tag, attrs) {
  const n = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
  return n;
}

function barChart(rows, key, title, fmt) {
  const data = rows.filter((r) => r[key] != null);
  if (data.length < 3) return null;
  const fig = el("figure", "chart");
  const W = 320, H = 118, pad = { l: 4, r: 4, t: 14, b: 22 };
  const max = Math.max(...data.map((r) => r[key]));
  const bw = (W - pad.l - pad.r) / data.length;
  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${title}: ${data.map((r) => `${r.decade}s ${fmt(r[key])}`).join(", ")}` });
  const peak = data.reduce((a, b) => (b[key] > a[key] ? b : a));
  data.forEach((r, i) => {
    const h = Math.max(2, ((H - pad.t - pad.b) * r[key]) / max);
    const x = pad.l + i * bw;
    s.append(svg("rect", { x: x + 1.5, y: H - pad.b - h, width: Math.max(2, bw - 3), height: h, class: r === peak ? "bar peak" : "bar" }));
    if (i % 2 === 0 || data.length < 8) {
      const t = svg("text", { x: x + bw / 2, y: H - 7, "text-anchor": "middle", class: "tick" });
      t.textContent = i === 0 || r.decade % 100 === 0 ? String(r.decade) : `'${String(r.decade).slice(2)}`;
      s.append(t);
    }
  });
  const pk = svg("text", { x: pad.l + data.indexOf(peak) * bw + bw / 2, y: pad.t - 3, "text-anchor": "middle", class: "peak-label" });
  pk.textContent = fmt(peak[key]);
  s.append(pk);
  fig.append(s, el("figcaption", "", title));
  return fig;
}

function scoreboard(g) {
  const box = el("div", "gotd");
  const tbl = el("table", "linescore");
  const head = el("tr");
  head.append(el("th", "team", ""));
  for (let i = 1; i <= g.inn; i++) head.append(el("th", "", String(i)));
  for (const c of ["R", "H", "E"]) head.append(el("th", "tot", c));
  tbl.append(head);
  for (const [name, line, r, h, e] of [[g.visitor, g.vline, g.vr, g.vh, g.ve], [g.home, g.hline, g.hr, g.hh, g.he]]) {
    const row = el("tr", (r > (name === g.visitor ? g.hr : g.vr)) ? "win" : "");
    row.append(el("th", "team", name));
    line.forEach((x) => row.append(el("td", "", x)));
    for (const v of [r, h, e]) row.append(el("td", "tot", v == null ? "" : String(v)));
    tbl.append(row);
  }
  box.append(tbl);
  const bits = [`${g.year}`, g.park, g.crowd ? `${g.crowd.toLocaleString("en-US")} fans` : ""].filter(Boolean).join(", ");
  box.append(el("p", "gotd-cap", `${bits}${g.why ? `. ${g.why[0].toUpperCase()}${g.why.slice(1)}.` : ""}`));
  return box;
}

function thenNow(tn) {
  const box = el("div", "thennow");
  for (const [label, g] of [["First on record", tn.first], ["Latest", tn.latest]]) {
    const cell = el("div", "tn");
    const w = g.vs > g.hs ? [g.visitor, g.vs, g.home, g.hs] : [g.home, g.hs, g.visitor, g.vs];
    cell.append(el("div", "tn-year", String(g.year)), el("div", "tn-label", label));
    cell.append(el("div", "tn-score", `${w[0]} ${w[1]}, ${w[2]} ${w[3]}`));
    const where = [g.event, g.park, g.crowd ? `${g.crowd.toLocaleString("en-US")} fans` : ""].filter(Boolean).join(" \u00b7 ");
    if (where) cell.append(el("div", "tn-note", where));
    box.append(cell);
  }
  return box;
}

function teamsTable(t) {
  const box = el("div", "teamrec");
  for (const [label, rows] of [["Best on this date", t.best], ["Toughest on this date", t.worst]]) {
    const col = el("div", "tr-col");
    col.append(el("h4", "mini-head", label));
    for (const r of rows) {
      const line = el("div", "tr-row");
      const bar = el("span", "tr-bar");
      bar.style.width = `${Math.round(r.pct * 100)}%`;
      bar.setAttribute("aria-hidden", "true");
      line.append(el("span", "tr-team", r.team), el("span", "tr-rec", `${r.w}\u2013${r.l}`), bar);
      col.append(line);
    }
    box.append(col);
  }
  return box;
}

function numbersBox(numbers) {
  const box = el("section", "numbers");
  box.setAttribute("aria-label", "By the numbers");
  box.append(el("h2", "reverse-head", "By the numbers"));
  const row = el("div", "numbers-row");
  for (const item of numbers.items) {
    const cell = el("div", "num");
    cell.append(el("div", "num-value", item.value), el("div", "num-label", item.label), el("div", "num-note", item.note));
    row.append(cell);
  }
  box.append(row);

  const extras = el("div", "numbers-extra");
  if (numbers.gotd) {
    const c = el("div", "nx");
    c.append(el("h3", "mini-head", "Game of the day"), scoreboard(numbers.gotd));
    if (numbers.thenNow) c.append(el("h3", "mini-head", "Then and now"), thenNow(numbers.thenNow));
    extras.append(c);
  }
  const charts = [];
  if (numbers.eras) {
    const r = barChart(numbers.eras, "rpg", "Runs per game, by decade", (v) => v.toFixed(1));
    const a = barChart(numbers.eras, "crowd", "Average crowd, by decade", (v) => `${Math.round(v / 1000)}k`);
    if (r) charts.push(r);
    if (a) charts.push(a);
  }
  if (charts.length || numbers.teams) {
    const c = el("div", "nx");
    if (charts.length) c.append(el("h3", "mini-head", "Through the years"), ...charts);
    if (numbers.teams) c.append(el("h3", "mini-head", "Teams on this date"), teamsTable(numbers.teams));
    extras.append(c);
  }
  if (numbers.records && numbers.records.length) {
    const c = el("div", "nx");
    c.append(el("h3", "mini-head", "The record book"));
    const dl = el("dl", "recbook");
    for (const r of numbers.records) {
      const dt = el("dt", "", r.label);
      const dd = el("dd");
      dd.append(el("strong", "", r.value), ` ${r.note}`);
      dl.append(dt, dd);
    }
    c.append(dl);
    extras.append(c);
  }
  if (extras.children.length) box.append(extras);
  return box;
}

// The wire: transactions, debuts and farewells, ejections, set like the agate columns of a sports page.
function wireBox(data) {
  const cols = [];
  const star = (s) => {
    if (!s.star) return null;
    const m = el("span", "hof", "\u2605");
    m.title = "Hall of Famer";
    m.setAttribute("aria-label", "Hall of Famer");
    return m;
  };
  if (data.feats && data.feats.items && data.feats.items.length) {
    const c = el("div", "wire-col");
    c.append(el("h3", "mini-head", "Feats and milestones"));
    const bits = [];
    if (data.feats.cycles) bits.push(`${data.feats.cycles} cycle${data.feats.cycles === 1 ? "" : "s"}`);
    if (data.feats.milestones) bits.push(`${data.feats.milestones} milestone${data.feats.milestones === 1 ? "" : "s"}`);
    if (bits.length) c.append(el("p", "wire-sum", `On record for this date: ${bits.join(" and ")}.`));
    const ul = el("ul", "wire-list");
    for (const it of data.feats.items) {
      const li = el("li");
      li.append(el("span", "yr", String(it.year)), it.text);
      const s = star(it);
      if (s) li.append(" ", s);
      ul.append(li);
    }
    c.append(ul);
    cols.push(c);
  }
  if (data.wire && data.wire.count) {
    const c = el("div", "wire-col");
    c.append(el("h3", "mini-head", "The transaction wire"));
    const sum = el("p", "wire-sum", `${data.wire.count.toLocaleString("en-US")} moves on this date since 1873. ` +
      (data.wire.summary || []).filter((s) => s.label !== "Busiest year").map((s) => `${s.value} ${s.label.toLowerCase()}`).join("; ") + ".");
    c.append(sum);
    const ul = el("ul", "wire-list");
    for (const it of data.wire.items || []) {
      const li = el("li");
      li.append(el("span", "yr", String(it.year)), it.text);
      const s = star(it);
      if (s) li.append(" ", s);
      ul.append(li);
    }
    c.append(ul);
    cols.push(c);
  }
  const p = data.people;
  if (p && (p.debuts.length || p.farewells.length)) {
    const c = el("div", "wire-col");
    c.append(el("h3", "mini-head", "Debuts and farewells"));
    const people = (label, list, total) => {
      if (!list.length) return;
      c.append(el("h4", "mini-sub", `${label} (${total.toLocaleString("en-US")} on this date)`));
      const ul = el("ul", "wire-list");
      for (const it of list) {
        const li = el("li");
        li.append(el("span", "yr", String(it.year)), `${it.name}${it.seasons > 1 ? `, ${it.seasons} seasons` : ""}`);
        const s = star(it);
        if (s) li.append(" ", s);
        ul.append(li);
      }
      c.append(ul);
    };
    people("Major league debuts", p.debuts, p.debutCount);
    people("Final games", p.farewells, p.farewellCount);
    if (p.managerDebuts && p.managerDebuts.length) {
      c.append(el("h4", "mini-sub", "First game as manager"));
      const ul = el("ul", "wire-list");
      for (const it of p.managerDebuts) {
        const li = el("li");
        li.append(el("span", "yr", String(it.year)), it.name);
        const s = star(it);
        if (s) li.append(" ", s);
        ul.append(li);
      }
      c.append(ul);
    }
    cols.push(c);
  }
  if (data.ejections && data.ejections.count) {
    const c = el("div", "wire-col");
    c.append(el("h3", "mini-head", "Thrown out"));
    c.append(el("p", "wire-sum", `${data.ejections.count.toLocaleString("en-US")} ejections on this date, ${data.ejections.managers.toLocaleString("en-US")} of them managers.`));
    const ul = el("ul", "wire-list");
    for (const it of data.ejections.items || []) {
      const li = el("li");
      li.append(el("span", "yr", String(it.year)), it.text);
      const s = star(it);
      if (s) li.append(" ", s);
      ul.append(li);
    }
    c.append(ul);
    cols.push(c);
  }
  if (!cols.length) return null;
  const box = el("section", "wire");
  box.append(el("h2", "reverse-head", "Around the league"));
  const row = el("div", "wire-row");
  row.style.setProperty("--n", cols.length);
  cols.forEach((c) => row.append(c));
  box.append(row);
  return box;
}

// A thin ruler from the oldest to the newest year with one tick per story; a tick jumps to its story.
function ribbon(stories) {
  const years = stories.map((s) => +s.year).filter(Boolean);
  if (years.length < 3) return null;
  const min = Math.min(...years), max = Math.max(...years);
  const span = Math.max(1, max - min);
  const box = el("nav", "ribbon");
  box.setAttribute("aria-label", "Stories by year");
  const line = el("div", "ribbon-line");
  const first = Math.ceil(min / 10) * 10;
  for (let d = first; d <= max; d += 10) {
    const t = el("span", "ribbon-decade", `${d}`);
    t.style.left = `${((d - min) / span) * 100}%`;
    line.append(t);
  }
  stories.forEach((s, i) => {
    const y = +s.year;
    if (!y) return;
    const a = el("a", "ribbon-tick");
    a.href = `#story-${i}`;
    a.style.left = `${((y - min) / span) * 100}%`;
    a.title = `${y}: ${s.headline}`;
    a.setAttribute("aria-label", `${y}: ${s.headline}`);
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      const node = document.getElementById(`story-${i}`);
      if (node) { node.scrollIntoView({ behavior: "smooth", block: "center" }); node.classList.add("flash"); setTimeout(() => node.classList.remove("flash"), 1600); }
    });
    line.append(a);
  });
  box.append(el("span", "ribbon-end", String(min)), line, el("span", "ribbon-end", String(max)));
  return box;
}

// Year at a glance: one square per calendar day, shaded by how much Retrosheet knows about it.
let calendarData = null;
async function loadCalendar() {
  if (calendarData) return calendarData;
  try {
    const res = await fetch("data/retro/calendar.json", { cache: "no-cache" });
    calendarData = res.ok ? await res.json() : {};
  } catch (err) {
    calendarData = {};
  }
  return calendarData;
}

function calendarBox(cal, when) {
  const keys = Object.keys(cal).filter((k) => k !== "built");
  if (!keys.length) return null;
  const built = new Set(cal.built || []);
  const score = (v) => Math.log10(1 + v[0]) + 0.5 * Math.log10(1 + v[1]) + 0.5 * Math.log10(1 + v[2]) + 0.4 * Math.log10(1 + v[3]);
  const max = Math.max(...keys.map((k) => score(cal[k])));
  const box = el("section", "yearcal");
  box.append(el("h2", "reverse-head", "The year at a glance"));
  box.append(el("p", "yearcal-note", "Darker days have more games, moves and milestones on record. Outlined days are in this edition."));
  const grid = el("div", "yearcal-grid");
  MONTHS.forEach((name, mi) => {
    const rowEl = el("div", "yc-row");
    rowEl.append(el("span", "yc-month", name.slice(0, 3)));
    for (let d = 1; d <= DAYS_IN[mi]; d++) {
      const k = `${pad(mi + 1)}${pad(d)}`;
      const v = cal[k] || [0, 0, 0, 0];
      const level = Math.min(4, Math.round((score(v) / max) * 4));
      const a = el("a", `yc l${level}${built.has(k) ? " built" : ""}${mi + 1 === when.month && d === when.day ? " now" : ""}`);
      a.href = `#${pad(mi + 1)}-${pad(d)}`;
      a.title = `${name} ${d}: ${v[0].toLocaleString("en-US")} games, ${v[1].toLocaleString("en-US")} moves`;
      a.setAttribute("aria-label", a.title);
      rowEl.append(a);
    }
    grid.append(rowEl);
  });
  box.append(grid);
  return box;
}

function render(data, when) {
  const wrap = $("stories");
  wrap.replaceChildren();
  columnJobs = [];
  const stories = data.stories || [];
  stories.forEach((s, i) => { s.__i = i; });  // lets the year ribbon find each story

  const head = el("div", "date-head");
  head.append(el("div", "when", `${MONTHS[when.month - 1]} ${when.day}`));
  const years = stories.map((s) => +s.year).filter(Boolean);
  head.append(el("div", "count", years.length ? `${stories.length} stories · ${Math.min(...years)} to ${Math.max(...years)}` : ""));
  wrap.append(head);
  const rib = ribbon(stories);
  if (rib) wrap.append(rib);
  if (!stories.length) return;

  // Tiers: the lead, then photo stories (beside the lead first, then in columns), obituaries, then text-only briefs.
  const [lead, ...rest] = stories;
  const deaths = rest.filter((s) => s.kind === "death");
  const living = rest.filter((s) => s.kind !== "death");
  const photo = living.filter(hasMedia);
  const text = living.filter((s) => !hasMedia(s));
  let n = 0;
  const nextAccent = () => ACCENTS[n++ % ACCENTS.length];

  const top = el("section", "top");
  const leadNode = card(lead, { tag: "Top story", accent: nextAccent(), cls: `lead${hasMedia(lead) ? " has-photo" : ""}` });
  top.append(leadNode);
  wrap.append(top);
  if (data.numbers && data.numbers.items && data.numbers.items.length) wrap.append(numbersBox(data.numbers));

  // Beside the lead: add photo stories until that column is as tall as the lead (never leaving a gap under either).
  let pool = photo;
  if (photo.length) {
    const side = el("aside", "side");
    top.append(side);
    let used = 0;
    if (wide.matches) {
      while (used < photo.length) {
        const before = Math.abs(side.offsetHeight - leadNode.offsetHeight);
        const node = card(photo[used], { tag: "On this date", accent: nextAccent(), cls: "" });
        side.append(node);
        const after = Math.abs(side.offsetHeight - leadNode.offsetHeight);
        if (used > 0 && after >= before) { node.remove(); n--; break; }  // this story would make the columns less even
        used++;
        if (side.offsetHeight >= leadNode.offsetHeight) break;
      }
    } else {
      used = Math.min(2, photo.length);
      photo.slice(0, used).forEach((s) => side.append(card(s, { tag: "On this date", accent: nextAccent(), cls: "" })));
    }
    pool = photo.slice(used);
  } else {
    top.classList.add("no-side");
  }

  // On a wide screen the text-only briefs fill the bottoms of the columns; on a phone they get their own list.
  const inColumns = wide.matches && text.length > 0;
  if (pool.length || inColumns) {
    const nodes = pool.map((s) => card(s, { tag: "On this date", accent: nextAccent(), cls: "" }));
    const fillers = inColumns ? text.map((s) => brief(s, nextAccent(), "div")) : [];
    const grid = el("section", "std-grid");
    grid.append(columnBox("", nodes, fillers));
    wrap.append(grid);
  }

  const wire = wireBox(data);
  if (wire) wrap.append(wire);

  if (deaths.length) {
    const box = el("section", "memoriam");
    box.append(el("h2", "reverse-head", "In memoriam"));
    box.append(columnBox("memoriam-grid", deaths.map((s) => card(s, { tag: "Remembered", accent: nextAccent(), cls: "" }))));
    wrap.append(box);
  }

  if (text.length && !inColumns) {
    const box = el("section", "briefs");
    box.append(el("h2", "reverse-head", "In brief"));
    const list = el("ul", "briefs-list");
    text.forEach((s) => list.append(brief(s, nextAccent())));
    box.append(list);
    wrap.append(box);
  }

  const cal = calendarBox(calendarData || {}, when);
  if (cal) wrap.append(cal);

  columnJobs.forEach(fillColumns);
}

let current = null;
let lastWidth = window.innerWidth;

async function load() {
  const when = parseHash();
  monthSel.value = when.month;
  fillDays(when.month, when.day);
  const prev = shift(when, -1), next = shift(when, 1);
  for (const [id, d] of [["prev", prev], ["prev2", prev], ["next", next], ["next2", next]]) $(id).href = `#${pad(d.month)}-${pad(d.day)}`;
  const label = `${MONTHS[when.month - 1]} ${when.day}`;
  $("dateline-top").textContent = label;
  $("end-title").textContent = `That's all for ${label}`;
  document.title = `${label}: This Day in Baseball`;
  $("status").hidden = false;
  $("status").textContent = "Setting the type…";
  $("stories").replaceChildren();
  $("colophon").hidden = true;
  try {
    const res = await fetch(`data/days/${pad(when.month)}-${pad(when.day)}.json`, { cache: "no-cache" });
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    await loadCalendar();
    current = { data, when };
    $("status").hidden = true;
    render(data, when);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { if (current && current.data === data) render(data, when); });
    $("colophon").hidden = false;
  } catch (err) {
    $("status").textContent = `The ${label} edition has not gone to press yet. Try the previous or next day.`;
    $("colophon").hidden = false;
  }
}

// Column heights depend on the window width, so lay the page out again when it changes.
let resizeTimer = 0;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (window.innerWidth === lastWidth || !current) return;
    lastWidth = window.innerWidth;
    render(current.data, current.when);
  }, 200);
});

window.addEventListener("hashchange", () => { load(); window.scrollTo({ top: 0 }); });
load();
