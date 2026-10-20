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

// ---------- rendering ----------

function mediaFor(story, accent) {
  const fig = el("figure", "media");
  const img = story.image;
  if (img) {
    const pic = el("img", "photo");
    pic.src = img.url;
    pic.alt = img.alt || story.about || "";
    pic.loading = "lazy";
    pic.decoding = "async";
    pic.addEventListener("error", () => pic.replaceWith(plateFor(story, accent)));
    fig.append(pic);
    const cap = el("figcaption");
    cap.append(`${img.of || story.about || ""}. Photo: ${img.credit} (`);
    const link = el("a", "", img.license);
    link.href = img.page;
    link.rel = "noopener noreferrer";
    cap.append(link, ")");
    fig.append(cap);
  } else {
    fig.append(plateFor(story, accent));
  }
  return fig;
}

function plateFor(story, accent) {
  const plate = el("div", "plate");
  plate.style.setProperty("--accent", accent);
  plate.append(el("span", "plate-year", story.year));
  if (story.about) plate.append(el("span", "plate-name", story.about));
  plate.setAttribute("role", "img");
  plate.setAttribute("aria-label", `${story.year}: ${story.about || "baseball history"}`);
  return plate;
}

function textFor(story, long) {
  const body = el("div", "body");
  const text = el("div", long ? "text-cols copy-text" : "copy-text");
  text.append(el("p", "", story.text));
  if (story.extract && !story.text.includes(story.extract.slice(0, 40)) && story.kind !== "death") {
    text.append(el("p", "bg", story.extract));
  }
  body.append(text);
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

function storyNode(story, layout, index) {
  const accent = ACCENTS[index % ACCENTS.length];
  const node = el("article", `story ${layout}${story.kind === "death" ? " death" : ""}`);
  node.style.setProperty("--accent", accent);

  const head = el("div", "head");
  const kicker = el("span", "kicker");
  kicker.append(el("span", "yr", story.year));
  kicker.append(el("span", "", layout === "lead" ? "Top story" : story.kind === "death" ? "In memoriam" : "On this date"));
  head.append(kicker, el("h3", "headline", story.headline || story.text));

  const text = textFor(story, layout === "wide");
  const media = mediaFor(story, accent);

  if (layout === "lead") {
    const left = el("div", "lead-media");
    left.append(media);
    const right = el("div", "lead-text");
    right.append(head, text);
    node.append(left, right);
  } else if (layout === "wide") {
    node.append(head, media, text);
  } else {
    const copy = el("div", "copy");
    copy.append(head, text);
    node.append(media, copy);
  }
  return node;
}

function render(data, when) {
  const wrap = $("stories");
  wrap.replaceChildren();
  const stories = data.stories || [];
  const head = el("div", "date-head");
  head.append(el("h2", "", `${MONTHS[when.month - 1]} ${when.day}`));
  const years = stories.map((s) => +s.year).filter(Boolean);
  const range = years.length ? `${stories.length} stories from ${Math.min(...years)} to ${Math.max(...years)}` : "";
  head.append(el("p", "", range));
  wrap.append(head);

  const rest = stories.slice(1);
  if (stories[0]) wrap.append(storyNode(stories[0], "lead", 0));

  // rhythm: wide, split, split (flipped), then a pair of two stories
  const rhythm = ["wide", "split", "split flip", "pair"];
  let i = 0, r = 0, n = 1;
  while (i < rest.length) {
    const kind = rhythm[r % rhythm.length];
    r++;
    if (kind === "pair") {
      if (i + 1 >= rest.length) { wrap.append(storyNode(rest[i], "split", n++)); i++; continue; }
      const pair = el("div", "pair");
      pair.append(storyNode(rest[i], "pair-item", n++), storyNode(rest[i + 1], "pair-item", n++));
      wrap.append(pair);
      i += 2;
    } else {
      wrap.append(storyNode(rest[i], kind, n++));
      i++;
    }
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
