// Telephone dashboard. Plain ES modules, no build step.
// The server (telephone/dashboard/server.py) owns every number and every sentence about a
// result; this file lays them out and keeps the page in step with a running job.

import { guideHtml, KEY_INFO, STATIONS } from "./guide.js";

const main = document.getElementById("main");
const railFoot = document.getElementById("rail-foot");
const toasts = document.getElementById("toasts");

const state = { overview: null, job: null, cleanup: [], onJob: null, first: true };

// -- helpers ---------------------------------------------------------------------------------

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const icon = (name, cls = "") => `<svg class="icon ${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const money = (n) => usd.format(Number(n || 0));
const pct = (pos) => `${Math.round(pos * 100)}%`;
const int = new Intl.NumberFormat("en-GB");
const plural = (n, word) => `${int.format(n)} ${word}${n === 1 ? "" : "s"}`;
// Addresses from the server start with "/". They are used relative to the page instead, so
// the dashboard also works when it is served under a path prefix.
const rel = (url) => (url && url.startsWith("/") ? url.slice(1) : url);
const withW = (url, w) => (url ? `${rel(url)}${url.includes("?") ? "&" : "?"}w=${w}` : "");

function duration(seconds) {
  const s = Math.round(seconds);
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

function kb(n) {
  if (n == null) return "";
  return n >= 1e6 ? `${(n / 1e6).toFixed(1)}\u00a0MB` : `${Math.round(n / 1000)}\u00a0kB`;
}

async function api(path, body) {
  const res = await fetch(rel(path), body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) {
    const detail = data?.detail;
    const text = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map((d) => d.msg).join(" ")
      : `The dashboard server answered ${res.status}.`;
    throw new Error(text);
  }
  return data;
}

function toast(text) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = text;
  toasts.append(el);
  setTimeout(() => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 220);
  }, 6000);
}

function onCleanup(fn) { state.cleanup.push(fn); }

// -- shared pieces ---------------------------------------------------------------------------

const STEPS = Array.from({ length: 20 }, (_, i) => {
  const v = Math.round(244 - (i * (244 - 26)) / 19);
  return `<i style="background:rgb(${v} ${v} ${v})"></i>`;
}).join("");
const BAND_SHORT = { same: "Same", worn: "Close", drifting: "Far", different: "Different" };
const KEY_NAMES = { ANTHROPIC_API_KEY: "Claude", GEMINI_API_KEY: "Gemini", CLOUDFLARE_ACCOUNT_ID: "Cloudflare", CLOUDFLARE_API_TOKEN: "Cloudflare", REPLICATE_API_TOKEN: "Replicate", OPENAI_API_KEY: "OpenAI" };
const listWords = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`);

// The step wedge: drift as a position between the original and a different photograph.
function wedge(position, band, { compact = false } = {}) {
  const has = position != null;
  const label = has
    ? `Drift: ${pct(position)} of the way from the original to a different photograph. ${band?.label ?? ""}.`
    : "Drift was not measured.";
  const scale = compact ? "" : `
    <div class="wedge-scale" aria-hidden="true">${Object.entries(BAND_SHORT)
      .map(([k, v]) => `<span${has && band?.key === k ? ' aria-current="true"' : ""}>${v}</span>`).join("")}</div>
    <div class="wedge-ends" aria-hidden="true"><span>The original</span><span>A different photograph</span></div>`;
  const legend = !has && !compact && band === null;
  if (legend) return `<div class="wedge" role="img" aria-label="The scale: from the original on the left to a different photograph on the right, in four bands: same, close, far, different.">
    <div class="wedge-track"><div class="wedge-steps">${STEPS}</div></div>${scale}</div>`;
  return `<div class="wedge${compact ? " wedge-compact" : ""}${has ? "" : " wedge-none"}" role="img" aria-label="${esc(label)}">
    <div class="wedge-track"><div class="wedge-steps">${STEPS}</div>${
      has ? `<div class="wedge-mark"><i style="left:${(position * 100).toFixed(1)}%"></i></div>` : ""}</div>${scale}
  </div>`;
}

function loopChips(stations, generations) {
  const arrow = `<li class="sep" aria-hidden="true">${icon("arrow")}</li>`;
  const chips = stations.map((s) =>
    `<li><span class="patch" data-kind="${esc(s.kind)}"></span><span class="role">${esc(s.role)}</span></li>`).join(arrow);
  const tail = generations ? `<li class="sep" aria-hidden="true">${icon("loop")}</li><li>${plural(generations, "time")} round</li>` : "";
  return `<ul class="loop">${chips}${tail}</ul>`;
}

function loopDetail(stations) {
  return `<ul class="loop-detail">${stations.map((s) =>
    `<li><span class="patch" data-kind="${esc(s.kind)}"></span><span><b>${esc(s.role)}.</b> ${esc(s.text)}${
      s.model && s.kind !== "platform" ? ` <span class="muted">(${esc(s.model)})</span>` : ""}</span></li>`).join("")}</ul>`;
}

// The stations of one version, one line each, for places where the detail matters.
function stationLines(stations) {
  return `<span class="station-lines">${stations.map((s) =>
    `<span><span class="patch" data-kind="${esc(s.kind)}"></span><span><span class="role">${esc(s.role)}</span> ${esc(s.text)}</span></span>`).join("")}</span>`;
}

const simTag = () => `<span class="tag tag-sim">${icon("alert")}Simulation</span>`;

function simBanner() {
  return `<div class="banner banner-sim">${icon("alert")}<div>
    <p><b>This is a simulation.</b></p>
    <p>Stand-in models produced these pictures and descriptions. They show how the loop works. They are not results about real photographs.</p>
  </div></div>`;
}

function errorPanel(err) {
  return `<div class="page"><div class="banner banner-bad" role="alert">${icon("alert")}<div>
    <p><b>That did not work.</b></p><p>${esc(err.message)}</p>
    <p><button class="btn" data-action="reload">Try again</button></p></div></div></div>`;
}

function driftText(reading) {
  if (reading.trips === 0) return "Not run yet";
  if (reading.position == null) return "Drift not measured";
  return `${pct(reading.position)} · ${reading.band.label}`;
}

// -- rail ------------------------------------------------------------------------------------

function renderRail() {
  const ov = state.overview;
  if (!ov) return;
  const job = state.job;
  const sp = ov.spend;
  const used = sp.cap_usd ? Math.min(1, sp.paid_usd / sp.cap_usd) : 0;
  let run = "";
  if (job && job.status === "running") {
    const done = job.generations_total ? job.generations_done / job.generations_total : 0;
    run = `<a class="rail-run" href="#/run"><span><strong>Running</strong> · ${pct(Math.min(1, done))}</span>
      <span class="meter"><i style="transform:scaleX(${Math.min(1, done).toFixed(3)})"></i></span></a>`;
  }
  railFoot.innerHTML = `${run}
    <div><div>AI budget: <strong class="num">${money(sp.paid_usd)}</strong> of ${money(sp.cap_usd)} spent</div>
    <div class="meter" style="margin-top:6px" role="img" aria-label="${pct(used)} of the budget is spent"><i style="transform:scaleX(${used.toFixed(3)})"></i></div></div>`;
}

// -- job polling -----------------------------------------------------------------------------

let pollTimer = null;
function ensurePolling() {
  if (pollTimer || !state.job || state.job.status !== "running") return;
  pollTimer = setInterval(async () => {
    if (document.hidden) return;
    try {
      const { job } = await api("/api/runs/current");
      const was = state.job?.status;
      state.job = job;
      renderRail();
      state.onJob?.(job);
      if (!job || job.status !== "running") {
        clearInterval(pollTimer);
        pollTimer = null;
        if (was === "running" && job) {
          state.overview = await api("/api/overview");
          renderRail();
          if (!state.onJob) toast(job.status === "done" ? `${job.name}: the run has finished.` : `${job.name}: the run ${job.status}.`);
        }
      }
    } catch { /* the server went away; the next tick tries again */ }
  }, 1000);
}

// -- start page ------------------------------------------------------------------------------

function home(ov) {
  const real = ov.results.filter((r) => !r.simulation);
  const firstFree = ov.experiments.find((e) => e.modes.includes("free") && e.images > 0);
  const practice = ov.experiments.find((e) => e.uses_fixtures);
  const unloaded = ov.saved_results.filter((s) => !s.loaded);
  const noKeys = !Object.values(ov.keys).some(Boolean);
  let next;
  if (ov.job?.status === "running") {
    next = `<h2>A run is in progress</h2><p>${esc(ov.job.name)} is running now.</p>
      <div class="row"><a class="btn btn-primary" href="#/run">Watch the run</a></div>`;
  } else if (real.length) {
    next = `<h2>There are results to read</h2>
      <p>${real.map((r) => `“${esc(r.name)}” has been run on ${plural(r.photos, "photograph")}, ${plural(r.variants, "way")} each.`).join(" ")}</p>
      <div class="row"><a class="btn btn-primary" href="#/results/${encodeURIComponent(real[0].id)}">Read the results</a>
      <a class="btn" href="#/run">Run another experiment</a></div>`;
  } else if (firstFree) {
    next = `<h2>Start with the free experiment</h2>
      <p>${esc(firstFree.plain)} It runs on this computer and costs nothing.</p>
      <div class="row"><a class="btn btn-primary" href="#/run/${encodeURIComponent(firstFree.id)}">Set up the first run</a>
      ${practice ? `<a class="btn" href="#/run/${encodeURIComponent(practice.id)}">Try a practice run first</a>` : ""}
      ${unloaded.length ? `<button class="btn btn-quiet" data-action="load-saved" data-exp="${esc(unloaded[0].experiment)}">Load the saved numbers</button>` : ""}</div>
      ${unloaded.length ? `<p class="note">The numbers from an earlier run are saved in this project, without the pictures. Loading them shows results straight away.</p>` : ""}`;
  } else {
    next = `<h2>Add your photographs first</h2>
      <p>Put your own photographs in <code>data/originals/</code>. Name each one with its kind first, for example <code>street_brick_lane_01.jpg</code>. Until then, a practice run on made-up images shows how everything works.</p>
      <div class="row">${practice ? `<a class="btn btn-primary" href="#/run/${encodeURIComponent(practice.id)}">Try a practice run</a>` : ""}</div>`;
  }

  const photos = ov.photos.length ? `<ul class="photos">${ov.photos.map((p) => `
    <li class="photo">
      <div class="photo-frame"><img src="${withW(p.image, 640)}" width="${p.width}" height="${p.height}" alt="${esc(p.name)}, the original photograph" loading="lazy"></div>
      <h3>${esc(p.name)} <small>${esc(p.type)}</small></h3>
      ${p.furthest ? `<a class="photo-result" href="#/chain/${encodeURIComponent(p.furthest.key)}">
          ${wedge(p.furthest.position, p.furthest.band, { compact: true })}
          <span class="photo-result-text">Most changed so far: ${pct(p.furthest.position)} of the way (${esc(p.furthest.variant_label)})</span></a>`
        : `<p class="note muted">${p.chains ? "Run, but drift was not measured" : "Not run yet"}</p>`}
    </li>`).join("")}</ul>`
    : `<p class="note">There are no photographs in <code>data/originals/</code> yet.</p>`;

  return {
    title: "Start",
    html: `<div class="page">
    <header class="page-head">
      <h1>Telephone</h1>
      <p class="lead">The children’s game, played with a photograph. A photo is passed again and again through the systems that handle pictures online, and every pass is measured to see what survives.</p>
    </header>

    <section class="sheet next" aria-label="What to do next">${next}</section>

    <section class="section">
      <h2>The loop</h2>
      <ul class="stations">${STATIONS.map((s) => `<li><span class="patch swatch" data-kind="${s.kind}"></span><h3>${s.role}</h3><p>${s.text}</p></li>`).join("")}</ul>
      <p class="again">${icon("loop")}<span>The new picture goes back to the start, and round again.</span></p>
      <p class="note">One trip round the loop is a generation. After every trip two things are measured: drift (how far the picture has moved from the original) and survival (which facts about it are still true). <a href="#/guide">How it works</a> explains each step.</p>
      ${noKeys ? `<p class="status status-warn">${icon("info")}<span>No API keys are set, so the Reader and the Painter can only run as simulations. The compression experiment runs for real. <a href="#/setup">Setup</a> shows how to add a key.</span></p>` : ""}
    </section>

    <section class="section">
      <h2>The photographs</h2>
      ${ov.photos.some((p) => p.furthest) ? `<div class="legend"><p class="note">The marker under each photograph shows how far its most changed copy has moved, on this scale. The names are a rule of thumb for a model’s score.</p>${wedge(null, null)}</div>` : ""}
      ${photos}
    </section>
  </div>`,
  };
}

// -- run: list -------------------------------------------------------------------------------

function availability(e) {
  if (e.blocked) return `<p class="status">${icon("info")}<span>${esc(e.blocked)}</span></p>`;
  if (e.modes.includes("real") && e.has_models) return `<p class="status status-good">${icon("check")}<span>Ready for a real run. It uses your API keys and costs money; you see the estimate first.</span></p>`;
  if (e.modes.includes("free")) return `<p class="status status-good">${icon("check")}<span>Ready. Runs on this computer and costs nothing.</span></p>`;
  if (e.uses_fixtures) return `<p class="status status-good">${icon("check")}<span>Ready. A simulation on made-up images, free.</span></p>`;
  return `<p class="status status-warn">${icon("info")}<span>Simulation only for now. A real run needs ${e.missing_keys.length > 1 ? "keys" : "a key"} for ${esc(listWords([...new Set(e.missing_keys.map((k) => KEY_NAMES[k] ?? k))]))}. <a href="#/setup">Setup</a> shows how to add ${e.missing_keys.length > 1 ? "them" : "it"}.</span></p>`;
}

// Which stations an experiment uses at all, without implying one fixed order: its versions differ.
function usesLine(e) {
  const seen = new Map();
  e.variants.forEach((v) => v.stations.forEach((s) => { if (!seen.has(s.kind)) seen.set(s.kind, s.role); }));
  if (!seen.size) return "";
  const chips = [...seen].map(([kind, role]) => `<li><span class="patch" data-kind="${esc(kind)}"></span><span class="role">${esc(role)}</span></li>`).join("");
  return `<ul class="loop"><li>Uses</li>${chips}<li>· ${plural(e.variants.length, "version")} of the loop, ${plural(e.generations, "time")} round each</li></ul>`;
}

function runList(ov) {
  state.job = ov.job;
  const rows = ov.experiments.map((e) => `
    <li class="exp">
      <div class="exp-body">
        <h2>${esc(e.name)}</h2>
        <p>${esc(e.plain)}</p>
        ${usesLine(e)}
        ${availability(e)}
      </div>
      <div class="exp-side">
        ${e.modes.length ? `<a class="btn" href="#/run/${encodeURIComponent(e.id)}">Set up a run<span class="vh">: ${esc(e.name)}</span></a>` : ""}
      </div>
    </li>`).join("");
  return {
    title: "Run",
    html: `<div class="page">
      <header class="page-head">
        <h1>Run an experiment</h1>
        <p class="lead">Each experiment asks one question by sending the photographs round a version of the loop. Pick one, check the settings, and start it. Nothing that costs money starts without showing you the price.</p>
      </header>
      <section id="live" aria-label="Current run">${ov.job ? liveHtml(ov.job) : ""}</section>
      <ul class="exps">${rows}</ul>
    </div>`,
    after() {
      state.onJob = liveUpdate;
      onCleanup(() => { state.onJob = null; });
      if (ov.job) liveUpdate(ov.job);
      ensurePolling();
    },
  };
}

// -- run: live progress ----------------------------------------------------------------------

function liveHtml(job) {
  return `<div class="sheet live" data-job="${esc(job.id)}">
    <div class="live-head">
      <h2 id="live-title"></h2>
      <div class="row" id="live-actions"></div>
    </div>
    <div class="meter" id="live-meter" role="progressbar" aria-label="Progress of the run" aria-valuemin="0" aria-valuemax="100"><i style="transform:scaleX(0)"></i></div>
    <p class="live-now" id="live-now"></p>
    <div class="live-views" id="live-views" hidden>
      <figure><img id="live-g0" alt="" width="900" height="600"><figcaption>The original (generation 0)</figcaption></figure>
      <figure><img id="live-gn" alt="" width="900" height="600" hidden><div class="live-wait" id="live-wait">The first generation is on its way.</div><figcaption id="live-cap"></figcaption></figure>
    </div>
    <div class="log" role="log" tabindex="0" aria-label="What has happened so far"><ol id="live-log"></ol></div>
    <p class="vh" role="status" id="live-status"></p>
  </div>`;
}

const live = { key: null, gen: null, logged: "" };

function liveUpdate(job) {
  const host = document.getElementById("live");
  if (!host) return;
  if (!job) { host.innerHTML = ""; return; }
  if (host.firstElementChild?.dataset.job !== job.id) {
    host.innerHTML = liveHtml(job);
    Object.assign(live, { key: null, gen: null, logged: "" });
  }
  const running = job.status === "running";
  const frac = job.generations_total ? Math.min(1, job.generations_done / job.generations_total) : 0;
  const title = { running: "Running", done: "Finished", failed: "Stopped with an error", stopped: "Stopped" }[job.status];
  document.getElementById("live-title").innerHTML =
    `${title}: ${esc(job.name)} ${job.mode === "simulation" ? simTag() : ""}`;

  const meter = document.getElementById("live-meter");
  meter.setAttribute("aria-valuenow", String(Math.round(frac * 100)));
  meter.firstElementChild.style.transform = `scaleX(${(job.status === "done" ? 1 : frac).toFixed(3)})`;

  const now = document.getElementById("live-now");
  if (running && job.current) {
    const c = job.current;
    now.textContent = `Chain ${Math.min(job.chains_done + 1, job.chains_total)} of ${job.chains_total}: ${c.label}. Generation ${c.generation} of ${c.generations}.${job.stop_requested ? " Stopping…" : ""}`;
    if (job.generations_done <= 1 && job.seconds > 4) now.textContent += " Getting the comparison model ready. The first time, this can take a minute.";
  } else if (running) {
    now.textContent = "Starting…";
  } else {
    const failed = job.chains_failed ? ` ${plural(job.chains_failed, "chain")} did not finish.` : "";
    const cost = job.spent_usd > 0 ? ` It cost ${money(job.spent_usd)}.` : " It cost nothing.";
    now.textContent = job.status === "failed"
      ? job.error || "The run failed."
      : `${plural(job.chains_done, "chain")} in ${duration(job.seconds)}.${failed}${cost}`;
  }

  const actions = document.getElementById("live-actions");
  const want = running ? "running" : "finished";
  if (actions.dataset.mode !== want) {
    if (actions.dataset.mode === "running") document.getElementById("live-status").textContent = `${title}: ${job.name}. ${now.textContent}`;
    actions.dataset.mode = want;
    actions.innerHTML = running
      ? `<button class="btn btn-danger" data-action="stop-run">${icon("stop")}Stop the run</button>`
      : `${job.chains_done ? `<a class="btn btn-primary" href="#/results/${encodeURIComponent(job.result_experiment)}">Read the results</a>` : ""}
         <button class="btn" data-action="dismiss-run">Close</button>`;
  }

  if (job.latest && (job.latest.key !== live.key || job.latest.generation !== live.gen)) {
    const views = document.getElementById("live-views");
    const { key, generation } = job.latest;
    if (key !== live.key) {
      const g0 = document.getElementById("live-g0");
      g0.removeAttribute("width"); g0.removeAttribute("height");
      g0.alt = "The original of the current chain";
      g0.src = `api/image/chain/${encodeURIComponent(key)}/0?w=900`;
      views.hidden = false;
    }
    if (generation > 0) {
      const img = document.getElementById("live-gn");
      const next = new Image();
      next.onload = () => {
        img.src = next.src;
        img.width = next.naturalWidth; img.height = next.naturalHeight;
        img.alt = `Generation ${generation} of the current chain`;
        img.hidden = false;
        document.getElementById("live-wait").hidden = true;
      };
      next.src = `api/image/chain/${encodeURIComponent(key)}/${generation}?w=900&t=${generation}`;
      document.getElementById("live-cap").textContent = `Generation ${generation}${job.current?.key === key ? `, ${job.current.label}` : ""}`;
    }
    live.key = key;
    live.gen = generation;
  }

  const log = document.getElementById("live-log");
  const tail = job.log[job.log.length - 1];
  const stamp = tail ? `${job.log.length}:${tail.at}:${tail.text}` : "";
  if (stamp !== live.logged) {
    log.innerHTML = job.log.map((l) =>
      `<li data-tone="${esc(l.tone)}"><time>${duration(l.at)}</time><span>${esc(l.text)}</span></li>`).join("");
    log.parentElement.scrollTop = log.parentElement.scrollHeight;
    live.logged = stamp;
  }
}

// -- run: setup ------------------------------------------------------------------------------

const MODE_COPY = {
  real: ["Real run", "Uses the real models through your API keys. This costs money. The estimate is shown below before anything starts."],
  free: ["Free run", "Runs the compression for real on this computer. The survival form is skipped because it needs a vision model. No key, no cost."],
  simulation: ["Simulation", "Stand-in models take the place of the Reader and the Painter. Free. The pictures and descriptions are fake and stay labelled as a simulation."],
};

function runSetup(ov, id) {
  const e = ov.experiments.find((x) => x.id === id);
  if (!e) throw new Error(`There is no experiment called ${id}.`);
  const order = ["free", "simulation", "real"].filter((m) => e.modes.includes(m));
  const modes = order.map((m, i) => {
    let [name, text] = MODE_COPY[m];
    if (m === "simulation" && e.uses_fixtures) text = "Stand-in models and made-up test images. Free. It shows how a run works; the output is not a result.";
    if (m === "real" && !e.has_models) text = "Runs the compression and also fills in the survival form with a vision model. That costs a little. The estimate is shown below before anything starts.";
    return `<label class="choice"><input type="radio" name="mode" value="${m}"${i === 0 ? " checked" : ""}><span><b>${name}</b><small>${text}</small></span></label>`;
  }).join("");
  const photos = e.uses_fixtures ? "" : `
    <fieldset class="field"><legend>Photographs</legend>
      <div class="picks">${ov.photos.map((p) => `
        <label class="pick"><img src="${withW(p.image, 320)}" alt="" width="${p.width}" height="${p.height}" loading="lazy">
        <span><input type="checkbox" name="photo" value="${esc(p.stem)}" checked>${esc(p.name)}</span></label>`).join("")}</div>
    </fieldset>`;
  const versions = `
    <fieldset class="field"><legend>Versions of the loop</legend>
      <div class="choices">${e.variants.map((v) => `
        <label class="choice"><input type="checkbox" name="variant" value="${esc(v.name)}" checked>
        <span><b>${esc(v.label)}</b>${v.notes ? `<small>${esc(v.notes)}</small>` : ""}${stationLines(v.stations)}</span></label>`).join("")}</div>
    </fieldset>`;
  const clipNote = !ov.clip_ready
    ? `<p class="status status-warn">${icon("info")}<span>The comparison model (CLIP) is not installed, so drift will not be measured. Colour and pixel-structure measures still are.</span></p>`
    : !ov.clip_weights_cached
      ? `<p class="status">${icon("info")}<span>The first run downloads the comparison model, a few hundred megabytes, so it starts slowly.</span></p>`
      : "";

  return {
    title: `Set up: ${e.name}`,
    html: `<div class="page">
      <header class="page-head">
        <a class="crumb" href="#/run">${icon("back")}All experiments</a>
        <h1>${esc(e.name)}</h1>
        <p class="lead">${esc(e.plain)}</p>
        ${e.question ? `<p class="note">The question, as the experiment file puts it: ${esc(e.question)}</p>` : ""}
      </header>
      <form class="form" id="run-form" novalidate>
        ${order.length > 1 ? `<fieldset class="field"><legend>How to run it</legend><div class="choices">${modes}</div></fieldset>`
          : `<input type="hidden" name="mode" value="${order[0]}"><p class="status">${icon("info")}<span><b>${MODE_COPY[order[0]][0]}.</b> ${e.uses_fixtures ? "Stand-in models and made-up test images. Free. It shows how a run works; the output is not a result." : MODE_COPY[order[0]][1]}</span></p>`}
        ${photos}
        ${versions}
        <div class="field">
          <label class="legend" for="generations">Generations</label>
          <input class="input" id="generations" name="generations" type="number" inputmode="numeric" min="1" max="40" step="1" value="${e.generations}" autocomplete="off" aria-describedby="gen-hint">
          <p class="hint" id="gen-hint">One generation is one trip round the loop. This experiment was designed for ${e.generations}. Fewer is quicker.</p>
        </div>
        <div class="sheet summary" aria-live="polite">
          <p class="summary-line" id="sum-line">Working out what this run involves…</p>
          <div id="sum-extra"></div>
          ${clipNote}
          <div class="row"><button class="btn btn-primary" type="submit" id="start" disabled>Start the run</button><a class="btn btn-quiet" href="#/run">Cancel</a></div>
          <p class="status status-bad" id="run-error" role="alert" hidden></p>
        </div>
      </form>
    </div>`,
    after() {
      const form = document.getElementById("run-form");
      const start = document.getElementById("start");
      const line = document.getElementById("sum-line");
      const extra = document.getElementById("sum-extra");
      const errorEl = document.getElementById("run-error");
      let est = null;
      let timer = null;
      let seq = 0;

      const request = () => {
        const fd = new FormData(form);
        const req = { experiment: e.id, mode: fd.get("mode"), variants: fd.getAll("variant"), generations: Number(fd.get("generations")) || null };
        if (!e.uses_fixtures) req.photos = fd.getAll("photo");
        return req;
      };
      const showError = (msg) => {
        errorEl.hidden = !msg;
        errorEl.innerHTML = msg ? `${icon("alert")}<span>${esc(msg)}</span>` : "";
      };
      const refresh = async () => {
        const mine = ++seq;
        const req = request();
        start.disabled = true;
        if ((!e.uses_fixtures && !req.photos.length) || !req.variants.length) {
          est = null;
          line.textContent = !req.variants.length ? "Tick at least one version of the loop." : "Tick at least one photograph.";
          extra.innerHTML = "";
          return;
        }
        try {
          const d = await api("/api/estimate", req);
          if (mine !== seq) return;
          est = d;
          line.textContent = `${plural(d.chains, "chain")}, ${plural(d.generations, "generation")} in total. ${d.estimate_usd > 0 ? `Estimated cost: ${money(d.estimate_usd)}.` : "This run is free."}`;
          let html = `<p class="note">A chain is one photograph going round one version of the loop.</p>`;
          if (d.blocked) html += `<p class="status status-bad">${icon("alert")}<span>${esc(d.blocked)}</span></p>`;
          else if (d.needs_confirmation) {
            html += `<p class="note">You have ${money(d.remaining_usd)} left of the ${money(ov.spend.cap_usd)} budget. The estimate ignores anything already cached, so the real cost can be lower.</p>
              <label class="confirm"><input type="checkbox" id="confirm"><span>I want to spend about ${money(d.estimate_usd)} on this run.</span></label>`;
          }
          extra.innerHTML = html;
          showError("");
          start.disabled = Boolean(d.blocked) || d.needs_confirmation;
        } catch (err) {
          if (mine !== seq) return;
          est = null;
          line.textContent = "This run cannot start yet.";
          extra.innerHTML = "";
          showError(err.message);
        }
      };
      form.addEventListener("change", (ev) => {
        if (ev.target.id === "confirm") { start.disabled = !ev.target.checked; return; }
        clearTimeout(timer);
        timer = setTimeout(refresh, 120);
      });
      form.addEventListener("input", (ev) => {
        if (ev.target.name !== "generations") return;
        clearTimeout(timer);
        timer = setTimeout(refresh, 350);
      });
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        if (start.disabled || !est) return;
        const req = request();
        if (est.needs_confirmation) req.confirm_usd = est.estimate_usd;
        start.disabled = true;
        start.textContent = "Starting…";
        try {
          const { job } = await api("/api/runs", req);
          state.job = job;
          location.hash = "#/run";
        } catch (err) {
          showError(err.message);
          start.disabled = false;
          start.textContent = "Start the run";
        }
      });
      onCleanup(() => clearTimeout(timer));
      refresh();
    },
  };
}

// -- results: list ---------------------------------------------------------------------------

function resultsList(ov) {
  const unloaded = ov.saved_results.filter((s) => !s.loaded);
  const saved = unloaded.length ? `
    <section class="section">
      <h2>Saved in this project</h2>
      <p class="note">These are the numbers from earlier runs, stored in <code>data/results/</code>. Loading them brings in the measurements straight away. The pictures are not stored there; running the experiment again recreates them.</p>
      <ul class="exps">${unloaded.map((s) => `<li class="exp"><div class="exp-body"><h3>${esc(experimentName(ov, s.experiment))}</h3><p>${plural(s.rows, "row")} of measurements.</p></div>
        <div class="exp-side"><button class="btn" data-action="load-saved" data-exp="${esc(s.experiment)}">Load these numbers</button></div></li>`).join("")}</ul>
    </section>` : "";
  const list = ov.results.length ? `<ul class="exps">${ov.results.map((r) => `
      <li class="exp">
        <div class="exp-body">
          <h2><a href="#/results/${encodeURIComponent(r.id)}">${esc(r.name)}</a> ${r.simulation ? simTag() : ""}</h2>
          <p>${esc(r.plain)}</p>
          <p class="note">${plural(r.chains, "chain")} across ${plural(r.photos, "photograph")} and ${plural(r.variants, "version")} of the loop. ${plural(r.generations, "picture")} in all.${r.errors ? ` ${plural(r.errors, "generation")} failed and ${r.errors === 1 ? "is" : "are"} kept.` : ""}</p>
        </div>
        <div class="exp-side">${r.sample ? `<img class="exp-thumb" src="${withW(r.sample, 320)}" alt="" width="132" height="88" loading="lazy">` : ""}
          <a class="btn" href="#/results/${encodeURIComponent(r.id)}">Read the results<span class="vh">: ${esc(r.name)}</span></a></div>
      </li>`).join("")}</ul>`
    : `<div class="sheet next"><h2>No results yet</h2>
        <p>Results appear here after a run. Each run adds one picture per generation and a row of measurements for every picture.</p>
        <div class="row"><a class="btn btn-primary" href="#/run">Run an experiment</a></div></div>`;
  return {
    title: "Results",
    html: `<div class="page">
      <header class="page-head"><h1>Results</h1>
      <p class="lead">Every run is kept here. Open one to see the pictures, how far each drifted from its original, and which facts survived.</p></header>
      ${list}${saved}
    </div>`,
  };
}

function experimentName(ov, id) {
  const base = id.replace(/-mock$/, "");
  return ov.experiments.find((e) => e.id === base)?.name ?? id;
}

// -- results: one experiment -----------------------------------------------------------------

async function resultsExperiment(ov, id) {
  const d = await api(`/api/results/${encodeURIComponent(id)}`);
  const byCell = new Map();
  for (const c of d.chains) {
    const k = `${c.photo}|${c.variant}`;
    if (!byCell.has(k)) byCell.set(k, []);
    byCell.get(k).push(c);
  }
  const cell = (c) => `<a class="cell" href="#/chain/${encodeURIComponent(c.key)}">
      ${c.image_last ? `<img src="${withW(c.image_last, 320)}" alt="${esc(c.photo_label.name)} after ${plural(c.last_generation, "generation")}, ${esc(c.variant_label)}" width="240" height="160" loading="lazy">` : ""}
      ${wedge(c.reading.position, c.reading.band, { compact: true })}
      <span class="cell-text">${esc(driftText(c.reading))}${c.repeat ? ` · repeat ${c.repeat + 1}` : ""}${c.errors ? " · stopped early" : ""}</span></a>`;
  const grid = `<div class="grid-wrap" role="region" tabindex="0" aria-label="Where each photograph ended"><table class="grid">
    <caption class="vh">Where each photograph ended, for every version of the loop</caption>
    <thead><tr><th scope="col">Photograph</th>${d.variants.map((v) => `<th scope="col">${esc(v.label)}</th>`).join("")}</tr></thead>
    <tbody>${d.photos.map((p) => `<tr><th scope="row">${esc(p.name)}<small>${esc(p.type)}</small></th>${d.variants.map((v) =>
      `<td>${(byCell.get(`${p.stem}|${v.name}`) ?? []).map(cell).join("") || '<span class="muted">Not run</span>'}</td>`).join("")}</tr>`).join("")}</tbody>
  </table></div>`;

  const measured = d.chains.some((c) => c.drift.some((v, i) => i > 0 && v != null));
  const multiples = measured ? `
    <section class="section">
      <h2>Drift over the generations</h2>
      <p class="note" id="multiples-note">One small chart for each version of the loop, all on the same vertical scale. Each line is one photograph.</p>
      <div class="multiples" id="multiples">${d.variants.map((v, i) => `<div class="sheet multiple chart" data-variant="${i}"><h3>${esc(v.label)}</h3><div class="tip" hidden></div></div>`).join("")}</div>
    </section>` : "";

  const versions = `<section class="section"><h2>The versions of the loop</h2>
    <div class="choices">${d.variants.map((v) => `<div class="choice" style="cursor:default;grid-template-columns:minmax(0,1fr)"><span><b>${esc(v.label)}</b>${v.notes ? `<small>${esc(v.notes)}</small>` : ""}</span>${loopDetail(v.stations)}</div>`).join("")}</div></section>`;

  const figures = d.figures.length ? `<details class="more"><summary>Figures made for the research log (${d.figures.length})</summary><div class="more-body">
      <p class="note">These are the matplotlib charts written to <code>data/figures/</code> for the slides. They use their own colours and labels.</p>
      <div class="figs">${d.figures.map((f) => `<a href="${esc(rel(f))}" target="_blank" rel="noopener"><img src="${esc(rel(f))}" alt="Figure: ${esc(f.split("/").pop().replace(/[_.]/g, " "))}" loading="lazy"></a>`).join("")}</div></div></details>` : "";

  return {
    title: d.name,
    html: `<div class="page">
      <header class="page-head">
        <a class="crumb" href="#/results">${icon("back")}All results</a>
        <h1>${esc(d.name)}</h1>
        <p class="lead">${esc(d.plain)}</p>
      </header>
      ${d.simulation ? simBanner() : ""}
      ${!d.images_available ? `<div class="banner">${icon("info")}<div><p><b>The pictures are not on this computer.</b></p><p>These numbers were loaded from a saved file. Running the experiment again recreates every picture.</p><p><a class="btn" href="#/run/${encodeURIComponent(d.base)}">Set up the run</a></p></div></div>` : ""}
      <section class="section">
        <h2>What this run shows</h2>
        ${d.findings.length ? `<ul class="findings">${d.findings.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>` : `<p class="note">Nothing has been through the loop yet.</p>`}
      </section>
      ${versions}
      <section class="section">
        <h2>Where each photograph ended</h2>
        <p class="note">The marker shows how far the last generation is from its original. Choose a picture to see every generation.</p>
        <p class="note scroll-cue">Scroll the table sideways to see every version.</p>
        ${grid}
      </section>
      ${multiples}
      ${figures}
      <section class="section">
        <h2>Keep or reuse these results</h2>
        <div class="row">
          ${d.simulation ? "" : `<button class="btn" data-action="save-snapshot" data-exp="${esc(d.id)}">Save a snapshot</button>`}
          <button class="btn" data-action="figures" data-exp="${esc(d.id)}">Make figures</button>
          ${d.defined ? `<a class="btn" href="#/run/${encodeURIComponent(d.base)}">Run it again</a>` : ""}
        </div>
        <p class="note">${d.simulation ? "" : "A snapshot writes the measurements to <code>data/results/</code> so they can be committed to Git. "}Figures are the drift charts and contact sheets used in the research log, written to <code>data/figures/</code>.</p>
      </section>
    </div>`,
    after() {
      const host = document.getElementById("multiples");
      if (!host) return;
      const max = Math.max(...d.chains.flatMap((c) => c.drift.filter((v) => v != null)));
      document.getElementById("multiples-note").append(` The top of the scale, ${niceMax(max).toFixed(2)}, is ${pct(Math.min(1, niceMax(max) / ov.scale.different_photo))} of the way to a different photograph. Point at a line to see which photograph it is.`);
      host.querySelectorAll(".multiple").forEach((el) => {
        const v = d.variants[Number(el.dataset.variant)];
        const series = d.chains.filter((c) => c.variant === v.name).map((c) => ({
          name: c.photo_label.name + (c.repeat ? ` (repeat ${c.repeat + 1})` : ""),
          points: c.drift.map((y, x) => ({ x, y })),
        }));
        drawChart(el, { series, yMax: niceMax(max), width: 300, height: 170, many: true, yLabel: "" });
        const top = d.chains.filter((c) => c.variant === v.name && c.reading.drift != null).sort((a, b) => b.reading.drift - a.reading.drift)[0];
        if (top) el.insertAdjacentHTML("beforeend", `<p class="multiple-top">Highest line: ${esc(top.photo_label.name)}, ${pct(top.reading.position)} of the way</p>`);
      });
    },
  };
}

// -- results: one chain ----------------------------------------------------------------------

function fmtValue(v) {
  if (Array.isArray(v)) return v.length ? v.join(", ") : "none";
  if (typeof v === "boolean") return v ? "yes" : "no";
  return v == null || v === "" ? "none" : String(v);
}

async function chainView(ov, key, query) {
  const d = await api(`/api/chains/${encodeURIComponent(key)}`);
  const gens = d.generations;
  const ok = gens.filter((g) => !g.error);
  const last = ok[ok.length - 1].generation;
  const g0 = gens[0];
  const hasClip = ok.some((g) => g.generation > 0 && g.metrics.clip_dist_to_g0 != null);
  const hasSsim = ok.some((g) => g.generation > 0 && g.metrics.ssim_to_g0 != null);
  const anySurvival = ok.some((g) => g.survival);
  const anyCaption = ok.some((g) => g.caption);
  const labels = ov.field_labels;
  let sel = Math.min(last, Math.max(0, Number(query.get("g") ?? last) || 0));

  const numbers = `<div class="table-wrap" role="region" tabindex="0" aria-label="All the numbers"><table class="table" id="numbers">
    <caption class="vh">Every measurement for every generation</caption>
    <thead><tr><th scope="col" class="n">Generation</th><th scope="col" class="n">Drift</th><th scope="col" class="n">Of the way</th><th scope="col" class="n">Pixel structure (SSIM)</th><th scope="col" class="n">LPIPS</th><th scope="col" class="n">Colour distance</th><th scope="col" class="n">File size</th><th scope="col" class="n">Pixels</th>${anySurvival ? '<th scope="col" class="n">Facts kept</th>' : ""}</tr></thead>
    <tbody>${gens.map((g) => {
      const m = g.metrics;
      if (g.error) return `<tr data-g="${g.generation}"><th scope="row" class="n">${g.generation}</th><td colspan="${anySurvival ? 8 : 7}">Stopped: ${esc(g.error)}</td></tr>`;
      const f = (v, n = 3) => (v == null ? "" : v.toFixed(n));
      return `<tr data-g="${g.generation}"><th scope="row" class="n">${g.generation}</th><td class="n">${f(m.clip_dist_to_g0)}</td><td class="n">${g.position == null ? "" : pct(g.position)}</td><td class="n">${f(m.ssim_to_g0)}</td><td class="n">${f(m.lpips_to_g0)}</td><td class="n">${f(m.hist_dist_to_g0)}</td><td class="n">${kb(g.generation === 0 ? d.original_bytes ?? m.file_bytes : m.file_bytes)}</td><td class="n">${m.width ?? ""} × ${m.height ?? ""}</td>${anySurvival ? `<td class="n">${g.survival ? `${g.survival.alive_count} of ${g.survival.total}` : ""}</td>` : ""}</tr>`;
    }).join("")}</tbody></table></div>`;

  const models = Object.entries(d.models).map(([kind, m]) => `<dt>${esc(kind)}</dt><dd>${esc(m.provider)}${m.model ? ` / ${esc(m.model)}` : ""}</dd>`).join("");

  return {
    title: `${d.photo_label.name}, ${d.variant_label}`,
    html: `<div class="page">
      <header class="page-head">
        <a class="crumb" href="#/results/${encodeURIComponent(d.experiment_id)}">${icon("back")}${esc(d.experiment.name)}</a>
        <h1>${esc(d.photo_label.name)} <span class="muted">· ${esc(d.variant_label)}</span> ${d.reading.simulation ? simTag() : ""}</h1>
        <p class="lead">${esc(d.reading.headline)}</p>
        ${d.stations.length ? loopChips(d.stations, last) : ""}
      </header>
      ${d.reading.simulation ? simBanner() : ""}

      <section class="compare-band" aria-label="The original next to one generation">
        <div class="compare">
          <figure>${g0.image ? `<img src="${withW(g0.image, 1200)}" width="${g0.metrics.width}" height="${g0.metrics.height}" alt="${esc(d.photo_label.name)}, the original">` : `<div class="missing">The pictures for this chain are not on this computer. Run the experiment again to recreate them.</div>`}
            <figcaption><span>The original (generation 0)</span>${g0.file ? `<a href="${esc(rel(g0.file))}" target="_blank" rel="noopener">Open the actual file</a>` : ""}</figcaption></figure>
          <figure><div id="gen-slot"></div>
            <figcaption><span id="gen-cap"></span><a id="gen-file" target="_blank" rel="noopener">Open the actual file</a></figcaption></figure>
        </div>
        <div class="scrub">
          <button class="btn btn-icon" type="button" id="prev" aria-label="Previous generation">${icon("prev")}</button>
          <button class="btn btn-icon" type="button" id="next" aria-label="Next generation">${icon("next")}</button>
          <input type="range" id="range" min="0" max="${last}" step="1" value="${sel}" aria-label="Generation">
          <button class="btn" type="button" id="play" aria-pressed="false">${icon("run", "icon-fill")}<span>Play</span></button>
          <output id="gen-out" for="range"></output>
        </div>
        <div class="strip" id="strip" role="group" aria-label="All generations">${gens.map((g) => g.error ? "" : `
          <button type="button" data-g="${g.generation}" aria-pressed="false" aria-label="Generation ${g.generation}">${g.image ? `<img src="${withW(g.image, 180)}" alt="" width="72" height="48" loading="lazy">` : '<span class="blank"></span>'}<span>${g.generation}</span></button>`).join("")}</div>
      </section>

      <section class="section">
        <h2 id="where-title">Where this generation sits</h2>
        <div class="reading">
          <p class="reading-band" id="band"></p>
          <div id="wedge"></div>
          <p class="note">The position comes from CLIP, an image-recognition model. The four names are a rule of thumb for its score. They are not a judgement of how the picture looks, which is what the two pictures above are for.</p>
        </div>
      </section>

      ${anyCaption ? `<section class="section"><h2>What the Reader wrote</h2><div class="sheet caption"><blockquote id="caption"></blockquote></div></section>` : ""}

      ${anySurvival ? `<section class="section"><h2>The survival form</h2>
        <p class="note">A vision model answered the same questions about the original and about this generation. A fact counts as kept while the two answers still match.</p>
        <div class="table-wrap"><table class="table"><thead><tr><th scope="col">Fact</th><th scope="col">In the original</th><th scope="col">In this generation</th><th scope="col">Kept?</th></tr></thead><tbody id="survival"></tbody></table></div></section>` : ""}

      <section class="section">
        <h2>The whole chain</h2>
        ${d.reading.facts.length ? `<dl class="facts">${d.reading.facts.map((f) => `<div><dt>${esc(f.label)}</dt><dd class="value">${esc(f.value)}</dd><dd class="meaning">${esc(f.meaning)}</dd></div>`).join("")}</dl>` : ""}
        ${hasClip || hasSsim ? `<div class="sheet chart" id="chart"><h3>${hasClip ? "Drift from the original, generation by generation" : "Pixel structure kept (SSIM), generation by generation"}</h3><div class="tip" hidden></div></div>
          <p class="note">${hasClip ? "The vertical scale is zoomed to fit this chain. The step wedge above shows the same number on the full scale, where 0.43 is a different photograph." : "Drift was not measured in this run, so this chart shows pixel structure instead. 1 means identical to the original."}</p>` : ""}
      </section>

      <details class="more"><summary>All the numbers</summary><div class="more-body">${numbers}</div></details>
      <details class="more"><summary>How this chain was made</summary><div class="more-body">
        ${loopDetail(d.stations)}
        ${d.notes ? `<p class="note">${esc(d.notes)}</p>` : ""}
        <dl class="kv"><dt>Chain</dt><dd class="mono">${esc(d.chain_id)}</dd><dt>Seed</dt><dd>${esc(d.seed)}</dd>${models}<dt>Cost</dt><dd>${money(d.cost_usd)}</dd><dt>Fingerprint</dt><dd class="mono">${esc((d.config_sha || "").slice(0, 16))}</dd></dl>
      </div></details>
    </div>`,
    after() {
      const range = document.getElementById("range");
      const out = document.getElementById("gen-out");
      const slot = document.getElementById("gen-slot");
      const cap = document.getElementById("gen-cap");
      const file = document.getElementById("gen-file");
      const band = document.getElementById("band");
      const wedgeEl = document.getElementById("wedge");
      const captionEl = document.getElementById("caption");
      const survivalEl = document.getElementById("survival");
      const strip = document.getElementById("strip");
      const byGen = new Map(gens.map((g) => [g.generation, g]));
      let chart = null;

      const chartEl = document.getElementById("chart");
      if (chartEl) {
        const points = ok.map((g) => ({ x: g.generation, y: hasClip ? g.metrics.clip_dist_to_g0 : g.metrics.ssim_to_g0 }));
        const ys = points.map((p) => p.y).filter((v) => v != null);
        chart = drawChart(chartEl, {
          series: [{ name: hasClip ? "Drift" : "SSIM", points }],
          yMax: hasClip ? niceMax(Math.max(...ys)) : 1,
          yMin: hasClip ? 0 : [0.9, 0.8, 0.6, 0.5, 0.25, 0].find((b) => b <= Math.min(...ys)),
          width: 760, height: 250,
          tip: (p) => `Generation ${p.x} · ${p.y.toFixed(3)}${hasClip ? ` · ${pct(Math.min(1, p.y / ov.scale.different_photo))} of the way` : ""}`,
          onPick: (x) => select(x),
        });
      }

      function select(g, { fromUser = true } = {}) {
        const cur = byGen.get(g);
        if (!cur || cur.error) return;
        sel = g;
        range.value = String(g);
        out.textContent = `Generation ${g} of ${last}`;
        range.setAttribute("aria-valuetext", `Generation ${g} of ${last}`);
        const m = cur.metrics;
        if (cur.image) {
          let img = slot.querySelector("img");
          if (!img) { slot.innerHTML = "<img>"; img = slot.querySelector("img"); }
          img.width = m.width; img.height = m.height;
          img.alt = g === 0 ? `${d.photo_label.name}, the original` : `${d.photo_label.name} after ${plural(g, "generation")}`;
          img.src = withW(cur.image, 1200);
          file.href = rel(cur.file); file.hidden = false;
          const nextGen = byGen.get(g + 1);
          if (nextGen?.image) new Image().src = withW(nextGen.image, 1200);
        } else {
          slot.innerHTML = `<div class="missing">This picture is not on this computer.</div>`;
          file.hidden = true;
        }
        cap.textContent = g === 0 ? "Generation 0, the original again" : `Generation ${g} · ${kb(m.file_bytes)} · ${m.width} × ${m.height} px`;
        if (g === 0) {
          band.innerHTML = `The original <small>Generation 0 is the photograph before it enters the loop.</small>`;
          wedgeEl.innerHTML = wedge(0, null);
        } else {
          band.innerHTML = `${cur.position == null ? esc(cur.band.label) : `${pct(cur.position)} of the way to a different photograph`} <small>${cur.position == null ? "" : `${esc(cur.band.label)}. `}${esc(cur.band.meaning)}</small>`;
          wedgeEl.innerHTML = wedge(cur.position, cur.band);
        }
        if (captionEl) captionEl.textContent = cur.caption || (g === 0 ? "The original has no description: nothing has read it yet." : "No description was recorded for this generation.");
        if (survivalEl) {
          const order = Object.keys(labels);
          const rows = cur.survival ? Object.entries(cur.survival.fields).sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0])) : [];
          survivalEl.innerHTML = cur.survival ? rows.map(([k, f]) => `
            <tr><th scope="row">${esc(labels[k] ?? k)}</th><td>${esc(fmtValue(f.g0))}</td><td>${esc(fmtValue(f.now))}</td>
            <td>${f.alive ? `<span class="alive">${icon("check")}Kept</span>` : `<span class="dead">${icon("cross")}Lost</span>`}</td></tr>`).join("")
            : `<tr><td colspan="4">The form was not filled in for this generation.</td></tr>`;
        }
        strip.querySelectorAll("button").forEach((b) => {
          const on = Number(b.dataset.g) === g;
          b.setAttribute("aria-pressed", String(on));
          if (on && fromUser) b.scrollIntoView({ block: "nearest", inline: "nearest" });
        });
        document.querySelectorAll("#numbers tbody tr").forEach((tr) => {
          if (Number(tr.dataset.g) === g) tr.setAttribute("aria-current", "true"); else tr.removeAttribute("aria-current");
        });
        chart?.mark(g);
        const url = `#/chain/${encodeURIComponent(key)}?g=${g}`;
        if (location.hash !== url) history.replaceState(null, "", url);
      }

      let playing = null;
      const play = document.getElementById("play");
      const stop = () => {
        clearInterval(playing); playing = null;
        play.setAttribute("aria-pressed", "false");
        play.innerHTML = `${icon("run", "icon-fill")}<span>Play</span>`;
      };
      play.addEventListener("click", () => {
        if (playing) return stop();
        if (sel >= last) select(0);
        play.setAttribute("aria-pressed", "true");
        play.innerHTML = `${icon("pause")}<span>Pause</span>`;
        playing = setInterval(() => { if (sel >= last) return stop(); select(sel + 1); }, 800);
      });
      range.addEventListener("input", () => { stop(); select(Number(range.value)); });
      document.getElementById("prev").addEventListener("click", () => { stop(); select(Math.max(0, sel - 1)); });
      document.getElementById("next").addEventListener("click", () => { stop(); select(Math.min(last, sel + 1)); });
      strip.addEventListener("click", (ev) => {
        const b = ev.target.closest("button[data-g]");
        if (b) { stop(); select(Number(b.dataset.g)); }
      });
      onCleanup(stop);
      select(sel, { fromUser: false });
    },
  };
}

// -- charts: hand-written SVG ----------------------------------------------------------------

// Axis tops that divide into round steps: [top, step].
const NICE = [[0.02, 0.005], [0.04, 0.01], [0.06, 0.02], [0.08, 0.02], [0.1, 0.02], [0.15, 0.05], [0.2, 0.05], [0.3, 0.1], [0.4, 0.1], [0.5, 0.1], [0.75, 0.25], [1, 0.25]];
function niceMax(v) {
  if (!Number.isFinite(v) || v <= 0) return 0.04;
  return (NICE.find(([top]) => top >= v * 1.05) ?? NICE[NICE.length - 1])[0];
}
function ticksFor(yMin, yMax, few) {
  const span = yMax - yMin;
  let step = (NICE.find(([top]) => Math.abs(top - span) < 1e-9) ?? [span, span / 4])[1];
  if (few) step = span / 2;
  const out = [];
  for (let t = yMin; t <= yMax + 1e-9; t += step) out.push(Number(t.toFixed(4)));
  return out;
}

// One or more lines over generations, drawn in ink. Identity is carried by the title, the
// tooltip and the table next to it, so no series colour is needed.
function drawChart(el, { series, yMax, yMin = 0, width, height, many = false, yLabel = "", tip, onPick }) {
  const room = el.clientWidth - 32;
  const W = room > 0 ? Math.max(260, Math.min(width, room)) : width;
  const H = Math.round(Math.max(170, Math.min(height, W * 0.62)));
  const m = { l: 44, r: many ? 12 : 52, t: 10, b: 30 };
  const xs = series.flatMap((s) => s.points.map((p) => p.x));
  const x1 = Math.max(1, ...xs);
  const px = (x) => m.l + (x / x1) * (W - m.l - m.r);
  const py = (y) => m.t + (1 - (y - yMin) / (yMax - yMin || 1)) * (H - m.t - m.b);
  const ticksY = ticksFor(yMin, yMax, many);
  const stepX = x1 <= 6 ? 1 : x1 <= 12 ? 2 : x1 <= 24 ? 5 : 10;
  const ticksX = [];
  for (let x = 0; x <= x1; x += stepX) ticksX.push(x);
  const dec = ticksY.some((t) => Math.abs(t * 100 - Math.round(t * 100)) > 1e-6) ? 3 : 2;
  const path = (pts) => {
    let dstr = "", pen = false;
    for (const p of pts) {
      if (p.y == null) { pen = false; continue; }
      dstr += `${pen ? "L" : "M"}${px(p.x).toFixed(1)} ${py(p.y).toFixed(1)}`;
      pen = true;
    }
    return dstr;
  };
  const lastPoint = many ? null : [...series[0].points].reverse().find((p) => p.y != null);
  const svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(el.querySelector("h3")?.textContent ?? "Chart")}. The same numbers are in the table below.">
    ${ticksY.map((t) => `<line class="grid-line" x1="${m.l}" x2="${W - m.r}" y1="${py(t).toFixed(1)}" y2="${py(t).toFixed(1)}"/><text class="tick" x="${m.l - 8}" y="${(py(t) + 4).toFixed(1)}" text-anchor="end">${t.toFixed(dec)}</text>`).join("")}
    <line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${py(yMin)}" y2="${py(yMin)}"/>
    ${ticksX.map((x) => `<text class="tick" x="${px(x).toFixed(1)}" y="${H - m.b + 16}" text-anchor="middle">${x}</text>`).join("")}
    <text class="axis-label" x="${W - m.r}" y="${H - 2}" text-anchor="end">Generation</text>
    ${yLabel ? `<text class="axis-label" x="${m.l - 36}" y="${m.t + 2}" text-anchor="start">${esc(yLabel)}</text>` : ""}
    ${series.map((s, i) => `<path class="${many ? "line-many" : "line"}" data-i="${i}" d="${path(s.points)}"/>`).join("")}
    ${lastPoint ? `<text class="end-label" x="${px(lastPoint.x) + 8}" y="${py(lastPoint.y) + 4}">${lastPoint.y.toFixed(3)}</text>` : ""}
    <line class="cross" y1="${m.t}" y2="${H - m.b}" hidden/>
    <circle class="dot dot-mark" r="5" hidden/>
    <circle class="dot dot-hover" r="4" hidden/>
    <rect class="hit" x="${m.l}" y="0" width="${W - m.l - m.r}" height="${H - m.b}"/>
  </svg>`;
  el.insertAdjacentHTML("beforeend", svg);
  const root = el.querySelector("svg");
  const tipEl = el.querySelector(".tip");
  const cross = root.querySelector(".cross");
  const hover = root.querySelector(".dot-hover");
  const marker = root.querySelector(".dot-mark");
  const hit = root.querySelector(".hit");
  const paths = [...root.querySelectorAll("path")];

  const nearest = (ev) => {
    const r = root.getBoundingClientRect();
    const vx = ((ev.clientX - r.left) / r.width) * W;
    const vy = ((ev.clientY - r.top) / r.height) * H;
    const x = Math.max(0, Math.min(x1, Math.round(((vx - m.l) / (W - m.l - m.r)) * x1)));
    let best = null;
    series.forEach((s, i) => {
      const p = s.points.find((q) => q.x === x);
      if (!p || p.y == null) return;
      const dist = Math.abs(py(p.y) - vy);
      if (!best || dist < best.dist) best = { i, p, dist, name: s.name };
    });
    return best && { ...best, r };
  };
  const leave = () => {
    tipEl.hidden = true; cross.setAttribute("hidden", ""); hover.setAttribute("hidden", "");
    paths.forEach((p) => p.classList.remove("is-hot"));
  };
  hit.addEventListener("pointermove", (ev) => {
    const n = nearest(ev);
    if (!n) return leave();
    const cx = px(n.p.x), cy = py(n.p.y);
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.removeAttribute("hidden");
    hover.setAttribute("cx", cx); hover.setAttribute("cy", cy); hover.removeAttribute("hidden");
    paths.forEach((p, i) => p.classList.toggle("is-hot", many && i === n.i));
    const host = el.getBoundingClientRect();
    tipEl.textContent = tip ? tip(n.p) : `${n.name} · generation ${n.p.x} · ${n.p.y.toFixed(3)}`;
    tipEl.hidden = false;
    const left = n.r.left - host.left + (cx / W) * n.r.width;
    const half = tipEl.offsetWidth / 2;
    tipEl.style.left = `${Math.max(half + 4, Math.min(host.width - half - 4, left))}px`;
    tipEl.style.top = `${n.r.top - host.top + (cy / H) * n.r.height}px`;
  });
  hit.addEventListener("pointerleave", leave);
  if (onPick) hit.addEventListener("click", (ev) => { const n = nearest(ev); if (n) onPick(n.p.x); });

  return {
    mark(x) {
      const p = series[0].points.find((q) => q.x === x);
      if (!p || p.y == null) return marker.setAttribute("hidden", "");
      marker.setAttribute("cx", px(p.x)); marker.setAttribute("cy", py(p.y)); marker.removeAttribute("hidden");
    },
  };
}

// -- guide and setup -------------------------------------------------------------------------

function guide(ov, _arg, query) {
  return {
    title: "How it works",
    html: `<div class="page guide">${guideHtml()}</div>`,
    after() {
      const to = query.get("to");
      if (to) document.getElementById(to)?.scrollIntoView({ block: "start" });
    },
    keepScroll: Boolean(query.get("to")),
  };
}

function setup(ov) {
  const sp = ov.spend;
  const used = sp.cap_usd ? Math.min(1, sp.paid_usd / sp.cap_usd) : 0;
  const yes = (ok, a, b) => ok ? `<span class="alive">${icon("check")}${a}</span>` : `<span class="status status-warn" style="font-size:inherit">${icon("info")}<span>${b}</span></span>`;
  return {
    title: "Setup",
    html: `<div class="page">
      <header class="page-head"><h1>Setup</h1>
      <p class="lead">What this computer has, what it is missing, and how much of the budget is left. The free experiment needs nothing on this page.</p></header>

      <section class="section"><h2>Budget</h2>
        <div class="sheet budget">
          <p class="budget-figure num">${money(sp.remaining_usd)} <small>left of ${money(sp.cap_usd)}</small></p>
          <div class="meter" role="img" aria-label="${pct(used)} of the budget is spent"><i style="transform:scaleX(${used.toFixed(3)})"></i></div>
          <p class="note">${money(sp.paid_usd)} spent so far. Every paid call to a model is logged, and a call that would go over the cap is refused before it is made. Gemini is costed at ${esc(ov.gemini_billing)}.</p>
        </div>
      </section>

      <section class="section"><h2>API keys</h2>
        <p class="note">A key lets the project call a real model. Keys are never typed into this page and never shown by it. Only whether each one is set.</p>
        <div class="table-wrap"><table class="table"><thead><tr><th scope="col">Key</th><th scope="col">What it is for</th><th scope="col">Status</th></tr></thead>
        <tbody>${Object.entries(ov.keys).map(([k, ok]) => `<tr><th scope="row" class="mono">${esc(k)}</th><td>${esc(KEY_INFO[k] ?? "")}</td><td>${yes(ok, "Set", "Not set")}</td></tr>`).join("")}</tbody></table></div>
        <h3>To add a key</h3>
        <ol class="steps">
          <li><span>In the project folder, copy <code>.env.example</code> to a new file called <code>.env</code>.</span></li>
          <li><span>Open <code>.env</code> in a text editor and paste the key after the <code>=</code> on its line.</span></li>
          <li><span>Save the file, come back here and choose Check again.</span></li>
        </ol>
        <p class="note">The <code>.env</code> file is ignored by Git, so it is not uploaded with the project. ${ov.env_file_found ? "This project has one." : "This project does not have one yet."}</p>
        <div class="row"><button class="btn" data-action="recheck">Check again</button></div>
      </section>

      <section class="section"><h2>Tools on this computer</h2>
        <div class="table-wrap"><table class="table"><thead><tr><th scope="col">Package</th><th scope="col">Used for</th><th scope="col">Status</th></tr></thead>
        <tbody>${ov.packages.map((p) => `<tr><th scope="row" class="mono">${esc(p.name)}</th><td>${esc(p.used_for.charAt(0).toUpperCase() + p.used_for.slice(1))}</td><td>${yes(p.installed, "Installed", "Not installed")}</td></tr>`).join("")}
        <tr><th scope="row">CLIP model file</th><td>Measuring drift</td><td>${yes(ov.clip_weights_cached, "Downloaded", "Downloads on the first run")}</td></tr></tbody></table></div>
        <p class="note">A missing package switches off the one measurement it is used for. Everything else still runs.</p>
      </section>

      <section class="section"><h2>Files</h2>
        <dl class="kv"><dt>Project folder</dt><dd class="mono">${esc(ov.root)}</dd>
        <dt>Photographs</dt><dd>${plural(ov.photos.length, "photograph")} in <code>data/originals/</code></dd>
        <dt>Private photographs</dt><dd>${ov.private_photos} in <code>data/originals/private/</code>. They are never shown here, exported or uploaded.</dd></dl>
      </section>
    </div>`,
  };
}

// -- router ----------------------------------------------------------------------------------

const routes = [
  [/^\/$/, home, "home"],
  [/^\/run$/, runList, "run"],
  [/^\/run\/([^/]+)$/, runSetup, "run"],
  [/^\/results$/, resultsList, "results"],
  [/^\/results\/([^/]+)$/, resultsExperiment, "results"],
  [/^\/chain\/([^/]+)$/, chainView, "results"],
  [/^\/guide$/, guide, "guide"],
  [/^\/setup$/, setup, "setup"],
];

let navSeq = 0;
async function navigate() {
  const mine = ++navSeq;
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, qs = ""] = raw.split("?");
  const query = new URLSearchParams(qs);
  state.cleanup.splice(0).forEach((fn) => fn());
  const match = routes.map(([re, view, nav]) => ({ m: path.match(re), view, nav })).find((r) => r.m);
  document.querySelectorAll(".nav a").forEach((a) => {
    if (match && a.dataset.nav === match.nav) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  try {
    if (!match) throw new Error("There is no page at this address.");
    state.overview = await api("/api/overview");
    state.job = state.overview.job;
    const out = await match.view(state.overview, match.m[1] && decodeURIComponent(match.m[1]), query);
    if (mine !== navSeq) return;
    main.innerHTML = out.html;
    document.title = `${out.title} · Telephone`;
    renderRail();
    out.after?.();
    ensurePolling();
    if (!out.keepScroll) window.scrollTo(0, 0);
    if (!state.first) main.focus({ preventScroll: true });
  } catch (err) {
    if (mine !== navSeq) return;
    main.innerHTML = errorPanel(err);
    document.title = "Telephone";
  }
  state.first = false;
}

// -- actions ---------------------------------------------------------------------------------

const actions = {
  reload: () => navigate(),
  async "stop-run"(btn) {
    btn.disabled = true;
    const { job } = await api("/api/runs/current/stop", {});
    state.job = job;
    liveUpdate(job);
  },
  async "dismiss-run"() {
    await api("/api/runs/current/dismiss", {});
    state.job = null;
    liveUpdate(null);
    renderRail();
  },
  async "load-saved"(btn) {
    const { rows } = await api("/api/actions/load-saved", { experiment: btn.dataset.exp });
    toast(`Loaded ${plural(rows, "row")} of measurements.`);
    location.hash = `#/results/${encodeURIComponent(btn.dataset.exp)}`;
  },
  async "save-snapshot"(btn) {
    const d = await api("/api/actions/save-snapshot", { experiment: btn.dataset.exp });
    toast(`Saved ${plural(d.rows, "row")} to ${d.path}.`);
  },
  async figures(btn) {
    const d = await api("/api/actions/figures", { experiment: btn.dataset.exp });
    toast(`${plural(d.written.length, "figure")} written to data/figures/.`);
    navigate();
  },
  async recheck() {
    await api("/api/actions/recheck", {});
    toast("Checked again.");
    navigate();
  },
};

document.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("[data-action]");
  if (!btn || !actions[btn.dataset.action]) return;
  ev.preventDefault();
  const label = btn.textContent;
  const busy = btn.tagName === "BUTTON" && !["stop-run", "dismiss-run", "reload"].includes(btn.dataset.action);
  if (busy) { btn.disabled = true; btn.textContent = "Working…"; }
  try {
    await actions[btn.dataset.action](btn);
  } catch (err) {
    toast(err.message);
  } finally {
    if (busy && btn.isConnected) { btn.disabled = false; btn.textContent = label; }
  }
});

window.addEventListener("hashchange", navigate);
navigate();
