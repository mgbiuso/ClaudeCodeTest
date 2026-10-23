"use strict";
// The extra boxes built from data/more/MM-DD.json (see scripts/more_facts.py): named records, pitchers' duel, firsts and lasts,
// youngest and oldest, who was born today, Hall of Famers and award winners, oddities, a chart, the Negro Leagues band and the
// pick-your-team band. Uses el() and svg() from app.js. Every box is skipped when its data is missing.

const MORE_CHARTS = ["hrPerGame", "foreignBorn", "colleges", "completeGames"];
const fmtN = (n) => Number(n).toLocaleString("en-US");

function winnerFirst(g) {
  const v = [g.visitor, g.vs], h = [g.home, g.hs];
  const [w, l] = v[1] >= h[1] ? [v, h] : [h, v];
  return `${w[0]} ${w[1]}, ${l[0]} ${l[1]}`;
}

function whereWhen(g) {
  const place = [g.park, g.city && g.park && !g.park.includes(g.city) ? g.city : null].filter(Boolean).join(", ");
  return `${place ? `${place}, ` : ""}${g.year}`;
}

function listBox(title, intro) {
  const c = el("div", "agate");
  c.append(el("h3", "mini-head", title));
  if (intro) c.append(el("p", "wire-sum", intro));
  return c;
}

function rowsList(rows) {
  const ul = el("ul", "wire-list");
  for (const r of rows) {
    const li = el("li");
    if (r.year) li.append(el("span", "yr", String(r.year)));
    if (r.strong) li.append(el("strong", "", `${r.strong} `));
    li.append(r.text);
    if (r.star) {
      const m = el("span", "hof", "★");
      m.title = "Hall of Famer";
      m.setAttribute("role", "img");
      m.setAttribute("aria-label", "Hall of Famer");
      li.append(" ", m);
    }
    ul.append(li);
  }
  return ul;
}

function recordsBox(m) {
  const r = m.records || {};
  const rows = [];
  if (r.longest) rows.push({ year: r.longest.year, strong: `Longest game, ${Math.floor(r.longest.minutes / 60)}:${String(r.longest.minutes % 60).padStart(2, "0")}.`, text: `${winnerFirst(r.longest)}, ${r.longest.innings} innings${r.longest.park ? ` at ${r.longest.park}` : ""}.` });
  if (r.crowd) rows.push({ year: r.crowd.year, strong: `Biggest crowd, ${fmtN(r.crowd.crowd)}.`, text: `${winnerFirst(r.crowd)}${r.crowd.park ? ` at ${r.crowd.park}` : ""}${r.crowd.seasonAvg && r.crowd.crowd > r.crowd.seasonAvg * 1.5 ? `, ${(r.crowd.crowd / r.crowd.seasonAvg).toFixed(1)} times that season's average` : ""}.` });
  if (r.runs) rows.push({ year: r.runs.year, strong: `Most runs, ${r.runs.total}.`, text: `${winnerFirst(r.runs)}.` });
  if (r.blowout && (!r.runs || r.blowout.year !== r.runs.year || r.blowout.margin > 8)) rows.push({ year: r.blowout.year, strong: `Biggest blowout, ${r.blowout.margin} runs.`, text: `${winnerFirst(r.blowout)}.` });
  if (r.marathon && !(r.longest && r.longest.year === r.marathon.year && r.longest.innings === r.marathon.innings)) rows.push({ year: r.marathon.year, strong: `Marathon, ${r.marathon.innings} innings.`, text: `${winnerFirst(r.marathon)}.` });
  if (r.ties) rows.push({ year: r.ties.latest.year, strong: `${r.ties.count} tie${r.ties.count === 1 ? "" : "s"} on record.`, text: `Latest: ${r.ties.latest.visitor} ${r.ties.latest.vs}, ${r.ties.latest.home} ${r.ties.latest.hs}.` });
  if (r.forfeits) rows.push({ year: r.forfeits.latest.year, strong: `${r.forfeits.count} forfeit${r.forfeits.count === 1 ? "" : "s"}.`, text: `Latest: ${r.forfeits.latest.visitor} at ${r.forfeits.latest.home}.` });
  if (rows.length < 2) return null;
  const c = listBox("Games to remember");
  c.append(rowsList(rows.slice(0, 5)));
  return c;
}

function duelBox(m) {
  const d = m.duel;
  if (!d) return null;
  const c = listBox("Pitchers' duel");
  const big = el("p", "duel-line");
  big.append(el("strong", "", `${d.vpitcher} against ${d.hpitcher}`));
  c.append(big);
  c.append(el("p", "wire-sum", `${winnerFirst(d)}, ${whereWhen(d)}. Each starter went the distance, with no relief help on either side. ${d.count > 1 ? `One of ${d.count} such low-scoring complete games on this date.` : ""}`));
  return c;
}

function firstsBox(m) {
  const f = m.firsts || {};
  const rows = [];
  for (const n of f.firstNight || []) rows.push({ year: n.year, text: `First night game at ${n.park}${n.city ? `, ${n.city}` : ""}.` });
  for (const g of f.lastGames || []) rows.push({ year: g.year, strong: `Last game at ${g.park || "a ballpark"}${g.city ? `, ${g.city}` : ""}.`, text: `${winnerFirst(g)}${g.crowd ? `, before ${fmtN(g.crowd)}` : ""}.` });
  if (f.doubleheaders) rows.push({ text: `${fmtN(f.doubleheaders)} doubleheaders have been played on this date.` });
  if (!rows.length) return null;
  const c = listBox("Firsts and lasts");
  c.append(rowsList(rows.slice(0, 5)));
  return c;
}

function agesBox(m) {
  const a = m.ages;
  if (!a) return null;
  const c = listBox("Youngest and oldest");
  c.append(rowsList([
    { year: a.youngest.year, strong: `Youngest starter, ${a.youngest.age}.`, text: `${a.youngest.name}, ${a.youngest.team}.` },
    { year: a.oldest.year, strong: `Oldest starter, ${a.oldest.age}.`, text: `${a.oldest.name}, ${a.oldest.team}.` },
  ]));
  return c;
}

function bornBox(m) {
  const b = (m.people || {}).born || [];
  if (!b.length) return null;
  const c = listBox("Born on this date", `${fmtN(m.people.coincidences.bornCount)} players in the Lahman database share this birthday.`);
  c.append(rowsList(b.slice(0, 5).map((p) => ({ year: p.year, strong: p.name, text: `${p.place ? `${p.place}. ` : ""}${p.career || ""}`, star: p.hof }))));
  return c;
}

function honorsBox(m) {
  const p = m.people || {};
  const rows = [];
  for (const h of p.hof || []) rows.push({ year: h.year, strong: h.name, text: `${h.kind}. Elected to the Hall of Fame in ${h.inducted}.`, star: true });
  for (const w of p.awardWinners || []) {
    if ((p.hof || []).some((h) => h.name === w.name && h.kind === "Born")) continue;   // already listed above
    rows.push({ year: w.year, strong: w.name, text: `Born this day. ${w.awards.map((a) => `${a.award} ${a.year}`).join(", ")}.` });
  }
  if (!rows.length) return null;
  const c = listBox("Hall of Famers and award winners");
  c.append(rowsList(rows.slice(0, 5)));
  return c;
}

function oddBox(m) {
  const p = m.people || {};
  const co = p.coincidences || {};
  const rows = [];
  for (const o of p.oneGame || []) rows.push({ year: o.year, strong: `${o.name}, one-game wonder.`, text: `${o.name} played one major league game, this one, and ${o.line}. It was the only game of ${o.name.split(" ").slice(-1)[0]}'s career.` });
  for (const f of p.families || []) rows.push({ year: f.sonDebut, strong: "Father and son.", text: `${f.son} debuted this day. ${f.father} had debuted in ${f.fatherDebut}.` });
  if (co.fullCircle) rows.push({ year: co.fullCircle.year, strong: "Full circle.", text: `${co.fullCircle.debut} debuted on the day ${co.fullCircle.died} died.` });
  if (co.sameName) rows.push({ strong: "Same name, same birthday.", text: `${co.sameName.name} was born on this date in ${co.sameName.years.join(" and ")}.` });
  if (!rows.length) return null;
  const c = listBox("Oddities");
  c.append(rowsList(rows.slice(0, 4)));
  return c;
}

// ---------- charts ----------

function lineChart(points, title, marks, fmt) {
  const fig = el("figure", "chart");
  const W = 320, H = 170, pad = { l: 26, r: 6, t: 16, b: 26 };
  const xs = points.map((p) => p[0]), ys = points.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y1 = Math.max(...ys) * 1.05;
  const X = (x) => pad.l + ((x - x0) / (x1 - x0)) * (W - pad.l - pad.r);
  const Y = (y) => H - pad.b - (y / y1) * (H - pad.t - pad.b);
  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${title}, ${x0} to ${x1}: from ${fmt(ys[0])} to ${fmt(ys[ys.length - 1])}, peaking at ${fmt(Math.max(...ys))}` });
  for (const y of [0, y1 / 2]) {
    s.append(svg("line", { x1: pad.l, x2: W - pad.r, y1: Y(y), y2: Y(y), class: "grid" }));
    const t = svg("text", { x: pad.l - 3, y: Y(y) + 3, "text-anchor": "end", class: "tick" });
    t.textContent = fmt(y);
    s.append(t);
  }
  for (const yr of [x0, Math.round((x0 + x1) / 2 / 10) * 10, x1]) {
    const t = svg("text", { x: X(yr), y: H - 7, "text-anchor": yr === x0 ? "start" : yr === x1 ? "end" : "middle", class: "tick" });
    t.textContent = String(yr);
    s.append(t);
  }
  s.append(svg("polyline", { points: points.map((p) => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(" "), class: "trend" }));
  // one short red tick on the baseline for each year that has a story today (long lines buried the trend on busy days)
  for (const yr of new Set(marks)) {
    if (yr >= x0 && yr <= x1) s.append(svg("line", { x1: X(yr), x2: X(yr), y1: H - pad.b - 9, y2: H - pad.b, class: "mark" }));
  }
  const top = points.reduce((a, b) => (b[1] > a[1] ? b : a));
  const late = X(top[0]) > W * 0.7;   // near the right edge the label is right-aligned so it is not cut off
  const pk = svg("text", { x: late ? W - 4 : X(top[0]), y: Y(top[1]) - 4, "text-anchor": late ? "end" : "middle", class: "peak-label" });
  pk.textContent = `${fmt(top[1])} in ${top[0]}`;
  s.append(pk);
  fig.append(s, el("figcaption", "", title));
  return fig;
}

function colBars(rows, title, fmt) {
  const fig = el("figure", "chart");
  const W = 320, H = 20 * rows.length + 8, label = 150;
  const max = Math.max(...rows.map((r) => r[1]));
  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${title}: ${rows.map((r) => `${r[0]} ${fmt(r[1])}`).join(", ")}` });
  rows.forEach((r, i) => {
    const y = 4 + i * 20;
    const t = svg("text", { x: 0, y: y + 12, class: "tick bar-label" });
    t.textContent = r[0].replace("University of ", "").replace("University", "U.").replace("California State", "Cal State");
    s.append(t, svg("rect", { x: label, y: y + 2, width: Math.max(2, ((W - label - 26) * r[1]) / max), height: 12, class: i === 0 ? "bar peak" : "bar" }));
    const n = svg("text", { x: label + Math.max(2, ((W - label - 26) * r[1]) / max) + 3, y: y + 12, class: "tick" });
    n.textContent = fmt(r[1]);
    s.append(n);
  });
  fig.append(s, el("figcaption", "", title));
  return fig;
}

function chartBox(m, g, when, years) {
  if (!g) return null;
  const pick = MORE_CHARTS[(when.month * 31 + when.day) % MORE_CHARTS.length];
  const c = listBox("How the game changed");
  if (pick === "hrPerGame") {
    c.append(el("p", "wire-sum", "Home runs per game, both teams, since 1871. Red ticks along the bottom mark the years of today's stories."));
    c.append(lineChart(g.hrPerGame, "Home runs per game, by season", years, (v) => v.toFixed(1)));
  } else if (pick === "foreignBorn") {
    c.append(el("p", "wire-sum", "Share of new major leaguers born outside the 50 states, by the decade they debuted."));
    c.append(barChart(g.foreignBorn.map(([decade, pct]) => ({ decade, pct })), "pct", "Born outside the 50 states, by decade", (v) => `${Math.round(v)}%`));
  } else if (pick === "colleges") {
    const dec = Object.keys(g.colleges).slice(-1)[0];
    c.append(el("p", "wire-sum", `Colleges that sent the most players to the majors, among those who played there in the ${dec}s.`));
    c.append(colBars(g.colleges[dec], `Most big leaguers by school, ${dec}s`, (v) => String(v)));
  } else {
    c.append(el("p", "wire-sum", "Complete games per team, per season, by decade."));
    c.append(barChart(g.completeGames.map(([decade, cg]) => ({ decade, cg })), "cg", "Complete games per team season", (v) => String(Math.round(v))));
  }
  return c;
}

// ---------- the blocks handed to the page ----------

function moreBlocks(data, global, when) {
  const m = data.more;
  if (!m) return [];
  const years = (data.stories || []).map((s) => +s.year).filter(Boolean);
  return [recordsBox(m), duelBox(m), bornBox(m), firstsBox(m), honorsBox(m), agesBox(m), oddBox(m), chartBox(m, global, when, years)].filter(Boolean);
}

// ---------- Negro Leagues ----------

function negroBand(data) {
  const n = data.more && data.more.negro;
  if (!n) return null;
  const sec = el("section", "negro");
  sec.setAttribute("aria-label", "This day in Negro Leagues baseball");
  sec.append(el("h2", "reverse-head", "This day in Negro Leagues baseball"));
  const body = el("div", "negro-body");
  const g = n.game;
  const left = el("div", "negro-main");
  left.append(el("p", "negro-kind", `${g.kind}, ${g.year}`));
  const score = el("p", "negro-score");
  const v = [g.visitor, g.vs], h = [g.home, g.hs];
  const [w, l] = v[1] >= h[1] ? [v, h] : [h, v];
  score.append(el("strong", "", `${w[0]} ${w[1]}, ${l[0]} ${l[1]}`));
  left.append(score);
  const where = [g.park, g.city].filter(Boolean).join(", ");
  left.append(el("p", "wire-sum", `${where}${g.crowd ? `. Crowd: ${fmtN(g.crowd)}` : ""}.`));
  if (g.stars.length) {
    const t = el("table", "negro-table");
    const head = el("tr");
    ["Player", "Team", "Line"].forEach((x) => { const th = el("th", "", x); th.scope = "col"; head.append(th); });
    t.append(head);
    for (const s of g.stars) {
      const tr = el("tr");
      const line = el("td", "", `${s.line}${s.approx ? " ~" : ""}`);
      if (s.approx) line.append(el("span", "sr-only", " (estimate)"));
      tr.append(el("td", "", s.player), el("td", "", s.team), line);
      t.append(tr);
    }
    left.append(t);
    if (g.stars.some((s) => s.approx)) left.append(el("p", "negro-note", "A tilde (~) means the source marks that line as an estimate."));
  } else {
    left.append(el("p", "negro-note", g.hasBox ? "No standout individual lines were recorded for this game." : "Only the score and teams survive for this game. No box score has been found."));
  }
  body.append(left);
  const right = el("div", "negro-side");
  right.append(el("h3", "mini-head", `${n.count} game${n.count === 1 ? "" : "s"} on record`));
  right.append(el("p", "wire-sum", `${n.years[0] === n.years[1] ? n.years[0] : `${n.years[0]} to ${n.years[1]}`}. ${n.withBox} with a box score.`));
  if (n.others.length) right.append(rowsList(n.others.slice(0, 5).map((o) => ({ year: o.year, text: `${o.text}${o.kind !== "League game" ? ` (${o.kind})` : ""}` }))));
  body.append(right);
  sec.append(body);
  sec.append(el("p", "negro-note", "Negro Leagues records are incomplete, and many numbers are reconstructed from newspapers. Shown here are the games Retrosheet has found."));
  return sec;
}

// ---------- pick your team ----------

const TEAM_KEY = "tdib-team";
function savedTeam() { try { return localStorage.getItem(TEAM_KEY) || ""; } catch (e) { return ""; } }
function saveTeam(v) { try { if (v) localStorage.setItem(TEAM_KEY, v); else localStorage.removeItem(TEAM_KEY); } catch (e) { /* private window: the choice just is not remembered */ } }

function teamBand(data, when, global) {
  if (!data.more) return null;
  const teams = data.more.teams || {};   // empty on a date with no games: the band stays, so the pick still shows
  const band = el("section", "teamband");
  band.setAttribute("aria-label", "Your team on this date");
  const top = el("div", "teamband-top");
  const label = el("label", "teamband-label", "Your team");
  label.htmlFor = "pick-team";
  const sel = el("select");
  sel.id = "pick-team";
  sel.append(new Option("Pick a team", ""));
  const names = (global && global.teamNames) || Object.fromEntries(Object.entries(teams).map(([c, t]) => [c, t.name]));
  Object.entries(names).sort((a, b) => a[1].localeCompare(b[1])).forEach(([code, name]) => sel.append(new Option(name, code)));
  top.append(label, sel);
  const out = el("div", "teamband-out");
  const show = () => {
    out.replaceChildren();
    const t = teams[sel.value];
    if (!sel.value) { out.append(el("p", "wire-sum", "Pick a team to see its record on this date. Your choice is kept in this browser only, with no account.")); return; }
    const date = `${MONTHS[when.month - 1]} ${when.day}`;
    if (!t) { out.append(el("p", "wire-sum", `No ${names[sel.value]} games on record for ${date}.`)); return; }
    const rec = `${t.w}-${t.l}${t.t ? `-${t.t}` : ""}`;
    const dl = el("dl", "teamband-stats");
    const add = (k, v) => { dl.append(el("dt", "", k), el("dd", "", v)); };
    add(`All-time on ${date}`, `${rec}, since ${t.first}`);
    if (t.best) add("Biggest win", `${t.best.score}, ${t.best.year}`);
    if (t.worst) add("Worst loss", `${t.worst.score}, ${t.worst.year}`);
    out.append(dl);
  };
  sel.value = names[savedTeam()] ? savedTeam() : "";
  sel.addEventListener("change", () => { saveTeam(sel.value); show(); });
  show();
  band.append(top, out);
  return band;
}
