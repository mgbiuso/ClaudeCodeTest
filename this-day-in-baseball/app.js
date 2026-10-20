"use strict";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
                "September", "October", "November", "December"];
const DAYS_IN = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const ACCENTS = ["var(--red)", "var(--navy)", "var(--green)", "var(--gold)", "var(--plum)"];

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

function kickerFor(story, tag) {
  const k = el("div", "kicker");
  k.append(el("span", "yr", story.year), el("span", "tag", tag));
  return k;
}

function bodyFor(story, { background }) {
  const body = el("div", "body");
  body.append(el("p", "", story.text));
  if (background && story.extract && story.kind !== "death" && !story.text.includes(story.extract.slice(0, 40))) {
    body.append(el("p", "bg", story.extract));
  }
  if (story.page) {
    const more = el("p", "more");
    const a = el("a", "", "Read more on Wikipedia");
    a.href = story.page;
    a.rel = "noopener noreferrer";
    more.append(a);
    body.append(more);
  }
  return body;
}

function card(story, { tag, accent, background, cls }) {
  const node = el("article", `story ${cls || ""}${story.kind === "death" ? " death" : ""}`);
  node.style.setProperty("--accent", accent);
  const head = el("div", "head");
  head.append(kickerFor(story, tag), el("h3", "headline", story.headline || story.text));
  node.append(head);
  if (story.image) node.append(figureFor(story, accent));
  node.append(bodyFor(story, { background }));
  return node;
}

function brief(story, accent) {
  const li = el("li");
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

function render(data, when) {
  const wrap = $("stories");
  wrap.replaceChildren();
  const stories = data.stories || [];

  const head = el("div", "date-head");
  head.append(el("div", "when", `${MONTHS[when.month - 1]} ${when.day}`));
  const years = stories.map((s) => +s.year).filter(Boolean);
  head.append(el("div", "count", years.length ? `${stories.length} stories · ${Math.min(...years)} to ${Math.max(...years)}` : ""));
  wrap.append(head);
  if (!stories.length) return;

  // Tiers: the lead, then photo stories (side column first, then the grid), obituaries, then text-only briefs.
  const [lead, ...rest] = stories;
  const deaths = rest.filter((s) => s.kind === "death");
  const living = rest.filter((s) => s.kind !== "death");
  const photo = living.filter((s) => s.image);
  const text = living.filter((s) => !s.image);
  const sideStories = photo.slice(0, 2);
  const gridStories = photo.slice(2);
  let n = 0;
  const nextAccent = () => ACCENTS[n++ % ACCENTS.length];

  const top = el("section", sideStories.length ? "top" : "top no-side");
  const leadNode = card(lead, { tag: "Top story", accent: nextAccent(), background: true, cls: `lead${lead.image ? " has-photo" : ""}` });
  top.append(leadNode);
  if (sideStories.length) {
    const side = el("aside", "side");
    sideStories.forEach((s) => side.append(card(s, { tag: "On this date", accent: nextAccent(), background: true })));
    top.append(side);
  }
  wrap.append(top);

  if (gridStories.length) {
    const grid = el("section", "std-grid");
    gridStories.forEach((s) => grid.append(card(s, { tag: "On this date", accent: nextAccent(), background: false })));
    wrap.append(grid);
  }

  if (deaths.length) {
    const box = el("section", "memoriam");
    box.append(el("h2", "reverse-head", "In memoriam"));
    const grid = el("div", "memoriam-grid");
    deaths.forEach((s) => grid.append(card(s, { tag: "Remembered", accent: nextAccent(), background: false })));
    box.append(grid);
    wrap.append(box);
  }

  if (text.length) {
    const box = el("section", "briefs");
    box.append(el("h2", "reverse-head", "In brief"));
    const list = el("ul", "briefs-list");
    text.forEach((s) => list.append(brief(s, nextAccent())));
    box.append(list);
    wrap.append(box);
  }
}

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
    $("status").hidden = true;
    render(data, when);
    $("colophon").hidden = false;
  } catch (err) {
    $("status").textContent = `The ${label} edition has not gone to press yet. Try the previous or next day.`;
    $("colophon").hidden = false;
  }
}

window.addEventListener("hashchange", () => { load(); window.scrollTo({ top: 0 }); });
load();
