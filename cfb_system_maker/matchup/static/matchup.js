"use strict";
// Matchup page. All state lives in the URL query string, so a matchup is a bookmark.
// Views: slate (default), custom (team pickers), matchup (a + b set).

const app = document.getElementById("app");
const ET = "America/New_York";

// ---------- helpers ----------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const params = () => Object.fromEntries(new URLSearchParams(location.search));

function go(next, replace = false) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(next)) if (v !== undefined && v !== null && v !== "") q.set(k, v);
  history[replace ? "replaceState" : "pushState"](null, "", "?" + q);
  render();
}
window.addEventListener("popstate", render);

async function api(path, query = {}) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== "") q.set(k, v);
  const r = await fetch(path + "?" + q);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.message || `${r.status} ${r.statusText}`);
  }
  return r.json();
}

function num(v, kind, dp) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (kind === "pct") return (v * 100).toFixed(1) + "%";
  if (kind === "int") return Math.round(v).toLocaleString("en-US");
  const a = Math.abs(v);
  const s = dp !== null && dp !== undefined ? v.toFixed(dp)
    : a >= 100 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : a >= 1 ? v.toFixed(2) : v.toFixed(3);
  return kind === "signed" && v > 0 ? "+" + s : s;
}
const line = (v) => v === null || v === undefined ? "—" : v === 0 ? "PK" : v > 0 ? "+" + v : String(v);
const price = (p) => p === null || p === undefined ? "" : p > 0 ? "+" + p : String(p);
const neg = (v) => v === null || v === undefined ? null : -v;

function when(iso, opts) {
  return iso ? new Intl.DateTimeFormat("en-US", { timeZone: ET, ...opts }).format(new Date(iso)) : "—";
}
const kickoff = (iso, tbd) => tbd ? "TBD" : when(iso, { hour: "numeric", minute: "2-digit" });
const stampTime = (iso) => when(iso, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

function card(title, body, { stamps = [], footer = "", cls = "", note = "" } = {}) {
  const st = stamps.filter(Boolean).map((s) =>
    `<span class="stamp${s.stale ? " stale" : ""}">${esc(s.text)}</span>`).join("");
  return `<section class="card ${cls}"><header><h2>${esc(title)}</h2>${note}
    <span class="stamps">${st}</span></header><div class="body">${body}</div>
    ${footer ? `<footer>${footer}</footer>` : ""}</section>`;
}
const nodata = (why) => `<span class="nodata">no data (${esc(why)})</span>`;
const fail = (e) => { app.innerHTML = `<div class="error" role="alert">${esc(e.message)}</div>`; };

function navState(view) {
  document.querySelectorAll("[data-nav]").forEach((a) => {
    if (a.dataset.nav === view) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
}
const setSnap = (s) => {
  document.getElementById("snap").textContent =
    s && s.pulled_at ? `Odds snapshot ${stampTime(s.pulled_at)} ET` : "No odds snapshot";
};

function weekOptions(weeks, selected, { full = false } = {}) {
  const opts = weeks.map((w) => {
    const v = w.season_type === "regular" ? String(w.week) : `${w.season_type}:${w.week}`;
    const label = w.season_type === "regular" ? `Week ${w.week}` : `Postseason ${w.week}`;
    return `<option value="${esc(v)}"${String(selected) === v ? " selected" : ""}>${esc(label)}</option>`;
  });
  if (full) opts.push(`<option value="full"${selected === "full" ? " selected" : ""}>Full season (postgame)</option>`);
  return opts.join("");
}
function seasonOptions(selected, last) {
  let out = "";
  for (let y = last; y >= 2012; y--) out += `<option${y === Number(selected) ? " selected" : ""}>${y}</option>`;
  return out;
}

// ---------- render ----------
async function render() {
  const p = params();
  try {
    if (p.a && p.b) { navState(null); return await matchup(p); }
    if (p.view === "custom") { navState("custom"); return await custom(p); }
    navState("slate");
    return await slate(p);
  } catch (e) { fail(e); }
}

// ---------- slate ----------
function favorite(book, home, away) {
  if (!book || book.spread.home === null || book.spread.home === undefined) return "—";
  const h = book.spread.home;
  return h <= 0 ? `${home} ${line(h)}` : `${away} ${line(-h)}`;
}

async function slate(p) {
  app.innerHTML = `<p class="sub">Loading slate…</p>`;
  const [season_type, wk] = (p.week || "").includes(":") ? p.week.split(":") : ["regular", p.week];
  const d = await api("/api/slate", { season: p.season, week: wk, season_type });
  setSnap(d.snapshot);
  const all = p.all === "1";
  const confs = [...new Set(d.games.flatMap((g) => [g.home_conference, g.away_conference]).filter(Boolean))].sort();
  const games = d.games.filter((g) => (all ? g.home_fbs || g.away_fbs : g.lined)
    && (!p.conf || g.home_conference === p.conf || g.away_conference === p.conf));

  const days = new Map();
  for (const g of games) {
    const k = g.tbd ? "Time TBD" : when(g.start_date, { weekday: "long", month: "short", day: "numeric" });
    if (!days.has(k)) days.set(k, []);
    days.get(k).push(g);
  }
  const curWeek = d.season_type === "regular" ? String(d.week) : `${d.season_type}:${d.week}`;
  let html = `<h1>${d.season} ${d.season_type === "regular" ? "Week " + d.week : "Postseason"}</h1>
    <p class="sub">${games.length} of ${d.games.length} games shown${d.current.season === d.season && d.current.week === d.week ? " · current week" : ""}</p>
    <div class="controls">
      <label>Season<select id="s-season">${seasonOptions(d.season, d.current.season)}</select></label>
      <label>Week<select id="s-week">${weekOptions(d.weeks, curWeek)}</select></label>
      <label>Conference<select id="s-conf"><option value="">All</option>${confs.map((c) =>
        `<option${c === p.conf ? " selected" : ""}>${esc(c)}</option>`).join("")}</select></label>
      <label class="check"><input type="checkbox" id="s-all"${all ? " checked" : ""}> Show all FBS games</label>
    </div>`;
  if (!games.length) html += `<p class="nodata">No games match. ${all ? "" : "Lines may not be posted yet; try Show all FBS games."}</p>`;
  for (const [day, gs] of days) {
    html += `<div class="day">${esc(day)}</div><table class="slate"><thead><tr>
      <th>Kickoff</th><th>Matchup</th><th class="r">DK spread</th><th class="r">DK total</th>
      <th class="r">FD spread</th><th class="r">FD total</th><th class="r">Consensus close</th></tr></thead><tbody>`;
    for (const g of gs) {
      const dk = g.books.draftkings, fd = g.books.fanduel;
      const cls = !(g.home_fbs && g.away_fbs) ? ' class="dim"' : "";
      html += `<tr tabindex="0" data-a="${g.away_team_id}" data-b="${g.home_team_id}" data-game="${g.game_id}"${cls}>
        <td>${esc(kickoff(g.start_date, g.tbd))}</td>
        <td>${esc(g.away_team)} ${g.neutral ? "vs" : "@"} ${esc(g.home_team)}</td>
        <td class="r">${esc(favorite(dk, g.home_team, g.away_team))}</td><td class="r">${dk && dk.total ? dk.total : "—"}</td>
        <td class="r">${esc(favorite(fd, g.home_team, g.away_team))}</td><td class="r">${fd && fd.total ? fd.total : "—"}</td>
        <td class="r">${g.median_spread_close === null ? "—" : esc(favorite({ spread: { home: g.median_spread_close } }, g.home_team, g.away_team))}${g.median_total_close ? " / " + g.median_total_close : ""}</td></tr>`;
    }
    html += `</tbody></table>`;
  }
  app.innerHTML = html;

  const base = { season: d.season, week: curWeek, conf: p.conf, all: all ? "1" : "" };
  document.getElementById("s-season").onchange = (e) => go({ season: e.target.value });
  document.getElementById("s-week").onchange = (e) => go({ ...base, week: e.target.value });
  document.getElementById("s-conf").onchange = (e) => go({ ...base, conf: e.target.value });
  document.getElementById("s-all").onchange = (e) => go({ ...base, all: e.target.checked ? "1" : "" });
  app.querySelectorAll("tr[data-game]").forEach((tr) => {
    const open = () => go({ a: tr.dataset.a, b: tr.dataset.b, game_id: tr.dataset.game,
      season: d.season, week: curWeek });
    tr.onclick = open;
    tr.onkeydown = (e) => { if (e.key === "Enter") open(); };
  });
}

// ---------- custom ----------
async function custom(p) {
  app.innerHTML = `<p class="sub">Loading teams…</p>`;
  const d = await api("/api/teams", { season: p.season });
  const all = p.alldiv === "1";
  const pool = d.teams.filter((t) => all || t.fbs);
  const lastSeason = new Date().getMonth() >= 6 ? new Date().getFullYear() : new Date().getFullYear() - 1;
  app.innerHTML = `<h1>Custom matchup</h1><p class="sub">Any two teams, any season, as of any week.</p>
    <div class="controls">
      <label>Team A<input list="teams" id="c-a" autocomplete="off"></label>
      <label>Team B<input list="teams" id="c-b" autocomplete="off"></label>
      <label>Season<select id="c-season">${seasonOptions(d.season, Math.max(lastSeason, d.season))}</select></label>
      <label>As of<select id="c-week">${weekOptions(d.weeks, "1", { full: true })}</select></label>
      <label class="check"><input type="checkbox" id="c-all"${all ? " checked" : ""}> All divisions</label>
      <button id="c-go">Compare</button>
    </div>
    <datalist id="teams">${pool.map((t) => `<option value="${esc(t.school)}">`).join("")}</datalist>
    <p class="sub" id="c-msg"></p>`;
  const bySchool = new Map(d.teams.map((t) => [t.school, t.team_id]));
  document.getElementById("c-season").onchange = (e) => go({ view: "custom", season: e.target.value, alldiv: p.alldiv });
  document.getElementById("c-all").onchange = (e) => go({ view: "custom", season: d.season, alldiv: e.target.checked ? "1" : "" });
  document.getElementById("c-go").onclick = () => {
    const a = bySchool.get(document.getElementById("c-a").value.trim());
    const b = bySchool.get(document.getElementById("c-b").value.trim());
    if (!a || !b || a === b) {
      document.getElementById("c-msg").textContent = "Pick two different teams from the list.";
      return;
    }
    const w = document.getElementById("c-week").value;
    go({ a, b, season: d.season, week: w === "full" ? "" : w, mode: w === "full" ? "full" : "" });
  };
}

// ---------- matchup ----------
function side(s, win, prior, fmt, dp, align) {
  if (!s) return `<div class="side ${align}">${nodata("missing")}</div>`;
  const pct = s.rank && s.n > 1 ? Math.round(100 * (s.n - s.rank) / (s.n - 1)) : null;
  const title = s.conf_rank ? `#${s.conf_rank} of ${s.conf_n} in conference` : "";
  const rank = s.rank ? `<span class="rank" title="${esc(title)}">#${s.rank} / ${s.n}<span class="bar"><i style="width:${pct}%"></i></span></span>`
    : `<span class="rank"></span>`;
  const bits = [];
  if (s.games !== undefined) bits.push(`n=${s.games}`);
  if (prior && prior.value !== null && prior.value !== undefined)
    bits.push(`'${String(prior.season).slice(2)} ${num(prior.value, fmt, dp)}${prior.rank ? " #" + prior.rank : ""}`);
  const pv = bits.length ? `<span class="prior">${esc(bits.join(" · "))}</span>` : "";
  const val = s.value === null || s.value === undefined
    ? `<span class="val">${nodata("none")}${pv}</span>`
    : `<span class="val${win ? " win" : ""}">${num(s.value, fmt, dp)}${pv}</span>`;
  return `<div class="side ${align}">${align === "a" ? rank + val : val + rank}</div>`;
}

function tapeRow(r, label) {
  const pa = r.prior ? { ...r.prior.a, season: r.prior.season } : null;
  const pb = r.prior ? { ...r.prior.b, season: r.prior.season } : null;
  const tip = `${r.source} · ${r.verdict}${r.season ? " · " + r.season : ""}`;
  // PFF pairs put a different metric on each side, so fmt/dp can be [offense, defense].
  const pick = (v, i) => (Array.isArray(v) ? v[i] : v);
  return side(r.a, r.edge === "a", pa, pick(r.fmt, 0), pick(r.dp, 0), "a")
    + `<div class="label" title="${esc(tip)}">${label ?? esc(r.label)}</div>`
    + side(r.b, r.edge === "b", pb, pick(r.fmt, 1), pick(r.dp, 1), "b");
}

function pairBlocks(blocks, names, picks) {
  return blocks.map((bl) => `<div class="unit-block">
      <div class="unit-head"><span>${esc(names[bl.off])} offense</span><span>vs</span><span>${esc(names[bl.def])} defense</span></div>
      ${bl.groups.map((g) => `<h2 class="group">${esc(g.group)}</h2><div class="tape">${g.rows.map((c) => conceptRow(c, picks)).join("")}</div>`).join("")}
    </div>`).join("");
}

function pffSection(p, A, B, picks) {
  if (!p.available) return card("PFF grades", nodata(p.reason));
  const st = p.status, ga = st.games[A.team_id], gb = st.games[B.team_id];
  return card("PFF grades", pairBlocks(p.blocks, { [A.team_id]: A.school, [B.team_id]: B.school }, picks), {
    stamps: [{ text: `PFF through wk ${st.through_week ?? "—"} · games ${A.school} ${ga}, ${B.school} ${gb}`, stale: st.stale }, { text: "all plays" }],
    footer: "Player-week grades rolled up per team, weighted by the snaps each grade covers. Each PFF week is matched to its CFBD game, so the window cuts on kickoff. PFF's late-season weeks (15+) are left out of as-of windows. The dot marks the unit whose rank is better.",
  });
}

function specialTeamsSection(s, A, B, full) {
  if (!s.available && !s.paar.length) return card("Special teams", nodata("PFF grades start in 2019"));
  const paarNote = s.paar_basis === "prior_season" ? ` <small>PRIOR SEASON ${s.paar[0].season}</small>` : "";
  let html = card("Special teams", (s.available ? tape(s.rows) : nodata("PFF grades start in 2019"))
    + `<div class="tape">${tapeRow(s.paar[0], esc(s.paar[0].label) + paarNote)}</div>`, {
    footer: "PFF special-teams grades over the window. Kicker PAAR is a season-final snapshot, so as-of views show last season's.",
  });
  if (s.postgame) html += card(`Kicker PAAR, ${s.postgame[0].season} to date`, tape(s.postgame),
    { cls: "postgame", note: `<span class="postgame-note">Postgame · not knowable before kickoff</span>` });
  return html;
}

const pct1 = (w, l) => (w + l ? ` (${((100 * w) / (w + l)).toFixed(1)}%)` : "");
const recStr = (r, keys = 2) => r.slice(0, keys).join("-") + (r.slice(keys).some(Boolean) ? "-" + r.slice(keys).join("-") : "");

function bettingSection(bt, A, B) {
  const table = (t, p) => {
    const rowsHtml = [["All games", p.all], ...p.splits].map(([name, r]) => `<tr${r.n ? "" : ' class="dim"'}>
      <td>${esc(name)}</td><td class="r">${r.n}</td><td class="r">${recStr(r.su)}</td>
      <td class="r">${r.n_lined ? recStr(r.ats) + pct1(r.ats[0], r.ats[1]) : "—"}</td>
      <td class="r">${r.ou[0] + r.ou[1] ? recStr(r.ou) : "—"}</td>
      <td class="r">${r.avg_cover === null ? "—" : num(r.avg_cover, "signed", 1)}</td>
      <td class="r">${r.avg_spread === null ? "—" : line(Math.round(r.avg_spread * 10) / 10)}</td></tr>`).join("");
    return `<div><div class="team-h">${esc(t.school)}</div><table><thead><tr><th></th><th class="r">n</th><th class="r">SU</th>
      <th class="r">ATS</th><th class="r">O/U</th><th class="r">Avg cover</th><th class="r">Avg close</th></tr></thead><tbody>${rowsHtml}</tbody></table></div>`;
  };
  return card("Betting profile", `<div class="grid2">${table(A, bt.a)}${table(B, bt.b)}</div>`, {
    footer: "Completed games inside the window against the closing consensus median (core.v_game_book_median). FCS games stay in; a closing line is not a decision-time price.",
  });
}

function resultCell(g) {
  if (!g.past) return `<span class="dim">${g.completed ? "after cutoff" : "upcoming"}</span>`;
  const r = g.result;
  return `${r.su} ${g.pts}-${g.opp_pts}`;
}
const oppCell = (g) => `${g.neutral ? "vs " : g.is_home ? "" : "@ "}${g.opp_rank ? `#${g.opp_rank} ` : ""}${esc(g.opp)}`;

function scheduleSection(sc, A, B) {
  const table = (t, games) => `<div><div class="team-h">${esc(t.school)}</div><table class="sched"><thead><tr><th>Wk</th><th>Date</th><th>Opponent</th>
      <th>Result</th><th class="r">Close</th><th class="r">ATS</th><th class="r">Total</th><th class="r">O/U</th></tr></thead><tbody>
      ${games.map((g) => `<tr class="${g.opp_fbs ? "" : "dim"}${g.past ? "" : " dim"}">
        <td>${g.season_type === "regular" ? g.week : "P" + g.week}</td><td>${esc(when(g.start_date, { month: "short", day: "numeric" }))}</td>
        <td>${oppCell(g)}${g.conf ? ' <span class="tag">conf</span>' : ""}</td><td>${resultCell(g)}</td>
        <td class="r">${line(g.spread)}</td><td class="r">${g.result && g.result.ats ? g.result.ats + " " + num(g.result.cover, "signed", 1) : "—"}</td>
        <td class="r">${g.total ?? "—"}</td><td class="r">${g.result && g.result.ou ? g.result.ou : "—"}</td></tr>`).join("")}
    </tbody></table></div>`;
  const common = sc.common.length ? `<table><thead><tr><th>Common opponent</th><th>${esc(A.school)}</th><th class="r">ATS</th>
      <th>${esc(B.school)}</th><th class="r">ATS</th></tr></thead><tbody>${sc.common.map((c) => `<tr><td>${esc(c.opp)}</td>
      <td>${resultCell(c.a)}</td><td class="r">${c.a.result.ats ?? "—"}</td><td>${resultCell(c.b)}</td><td class="r">${c.b.result.ats ?? "—"}</td></tr>`).join("")}
    </tbody></table>` : nodata("no common opponents inside the window");
  return card("Schedule and results", `<div class="grid2">${table(A, sc.a)}${table(B, sc.b)}</div>
      <h2 style="margin:16px 0 4px">Common opponents</h2>${common}`, {
    footer: "Rank is the opponent's AP rank in the poll released before that game. Games at or after the cutoff show no score or line. Dimmed rows are FCS opponents or games outside the window.",
  });
}

function h2hSection(h, A, B) {
  if (!h.n) return card("Head-to-head", nodata("no meetings before this game"));
  const lead = h.series.a === h.series.b ? `Series tied ${h.series.a}-${h.series.b}`
    : `${h.series.a > h.series.b ? A.school : B.school} leads ${Math.max(h.series.a, h.series.b)}-${Math.min(h.series.a, h.series.b)}`;
  const body = `<p><strong>${esc(lead)}${h.series.t ? `-${h.series.t}` : ""}</strong> <span class="dim">n=${h.n} since ${h.first}</span></p>
    <table><thead><tr><th>Season</th><th>Site</th><th>Winner</th><th class="r">Score</th><th class="r">${esc(A.school)} close</th><th class="r">${esc(A.school)} ATS</th></tr></thead><tbody>
    ${h.games.map((g) => `<tr><td>${g.season}${g.season_type === "regular" ? "" : " (post)"}</td>
      <td>${g.neutral ? "Neutral" : g.a_home ? esc(A.school) : esc(B.school)}</td>
      <td>${g.winner === "a" ? esc(A.school) : g.winner === "b" ? esc(B.school) : "Tie"}</td>
      <td class="r">${g.a_points}-${g.b_points}</td><td class="r">${line(g.a_spread)}</td><td class="r">${g.a_ats ?? "—"}</td></tr>`).join("")}
    </tbody></table>`;
  return card("Head-to-head", body, { footer: "Every meeting since 1869 from core.fact_game_historical and core.fact_game; lines exist from 2012. The last 10 are listed; scores read A-B." });
}

// ---------- trends: inline SVG small multiples, A solid accent, B dashed grey ----------
function trendChart(title, series, fmt, dp) {
  const pts = series.flatMap((s) => s.points).filter((p) => p.y !== null && p.y !== undefined);
  if (!pts.length) return `<figure class="trend"><figcaption>${esc(title)}</figcaption>${nodata("no games")}</figure>`;
  const W = 300, H = 120, L = 44, T = 8, B = 20, R = 8;
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const px = (v) => L + ((v - x0) / (x1 - x0 || 1)) * (W - L - R);
  const py = (v) => T + ((y1 - v) / (y1 - y0 || 1)) * (H - T - B);
  const lines = series.map((s) => {
    const ok = s.points.filter((p) => p.y !== null && p.y !== undefined);
    return `<polyline class="${s.cls}" points="${ok.map((p) => `${px(p.x)},${py(p.y)}`).join(" ")}"/>`
      + ok.map((p) => `<circle class="${s.cls}" cx="${px(p.x)}" cy="${py(p.y)}" r="3"><title>${esc(`${s.name} · wk ${p.label}: ${num(p.y, fmt, dp)}`)}</title></circle>`).join("");
  }).join("");
  const weeks = [...new Set(xs)].sort((a, b) => a - b);
  return `<figure class="trend"><figcaption>${esc(title)}</figcaption>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)} by week">
      <text class="axis" x="${L - 6}" y="${py(y1) + 4}" text-anchor="end">${esc(num(y1, fmt, dp))}</text>
      <text class="axis" x="${L - 6}" y="${py(y0) + 4}" text-anchor="end">${esc(num(y0, fmt, dp))}</text>
      <line class="grid" x1="${L}" x2="${W - R}" y1="${py(y1)}" y2="${py(y1)}"/><line class="grid" x1="${L}" x2="${W - R}" y1="${py(y0)}" y2="${py(y0)}"/>
      ${weeks.map((w) => `<text class="axis" x="${px(w)}" y="${H - 4}" text-anchor="middle">${w > 16 ? "P" + (w - 16) : w}</text>`).join("")}
      ${lines}</svg></figure>`;
}

function trendsSection(tr, A, B) {
  const xOf = (r) => (r.season_type === "postseason" ? 16 + r.week : r.week);
  const cf = (t, key) => tr.teams[t.team_id].cfbd.map((r) => ({ x: xOf(r), y: r[key], label: `${r.week} vs ${r.opponent}` }));
  const pf = (t, key) => tr.teams[t.team_id].pff[key].map((r) => ({ x: r.week ?? 16 + r.pff_week, y: r.value, label: String(r.week ?? "late") }));
  const pair = (f, key) => [{ name: A.school, cls: "sa", points: f(A, key) }, { name: B.school, cls: "sb", points: f(B, key) }];
  const charts = [
    trendChart("Offense PPA per play", pair(cf, "offense_ppa"), "signed", 3),
    trendChart("Defense PPA allowed", pair(cf, "defense_ppa"), "signed", 3),
    trendChart("Offense success rate", pair(cf, "offense_sr"), "pct"),
    trendChart("Defense success rate allowed", pair(cf, "defense_sr"), "pct"),
    trendChart("PFF offense grade", pair(pf, "pff_offense"), "num", 1),
    trendChart("PFF defense grade", pair(pf, "pff_defense"), "num", 1),
  ].join("");
  return card("Trends", `<p class="legend"><span class="key sa"></span>${esc(A.school)} <span class="key sb"></span>${esc(B.school)}</p><div class="trends">${charts}</div>`, {
    footer: `Game by game inside the window. CFBD from ${esc(tr.table)}${tr.ngt ? " (no garbage time)" : ""}; PFF grades weighted by snaps. Hover a point for the opponent.`,
  });
}

// ---------- provenance + export ----------
function sourcesSection(d) {
  const m = d.meta;
  const items = [
    ["As-of cutoff", m.mode === "full" ? "none: full season, postgame" : `${stampTime(m.cutoff)} ET (first kickoff of the selected week); stat windows use games before it`],
    ["Odds snapshot", m.snapshot.file ? `${m.snapshot.file} · pulled ${stampTime(m.snapshot.pulled_at)} ET` : "none found"],
    ["Verdicts", "pregame_windowed: aggregated over prior games · pregame_direct: fixed before the season · lookahead_only: season-final, shown as last season's (or in postgame panels) · postgame: result"],
    ["Warehouse", "cfb.duckdb opened read-only for this request and closed before responding"],
    ["Request", `${m.elapsed_ms} ms`],
  ];
  return card("Sources and cutoffs", `<dl class="kv">${items.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`,
    { footer: "Hover any stat label for its table.column and verdict." });
}

function statRows(d, picks) {
  const s = d.sections, A = d.meta.a.school, B = d.meta.b.school, out = [];
  const add = (section, block, r, label) => out.push([section, block, label || r.label, r.a && r.a.value, r.a && r.a.rank,
    r.b && r.b.value, r.b && r.b.rank, r.verdict, r.source]);
  s.profile.rows.forEach((r) => add("profile", `${A} vs ${B}`, r));
  s.ratings.rows.forEach((r) => add("ratings", `${A} vs ${B}`, r));
  for (const [name, sec] of [["units", s.units], ["pff", s.pff]]) {
    (sec.blocks || []).forEach((bl) => bl.groups.forEach((g) => g.rows.forEach((c) => {
      const opt = c.options.find((o) => o.key === picks[c.concept]) || c.options[0];
      add(name, `${bl.off === d.meta.a.team_id ? A : B} offense vs ${bl.def === d.meta.a.team_id ? A : B} defense`, opt, `${g.group}: ${opt.label}`);
    })));
  }
  s.special_teams.rows.forEach((r) => add("special_teams", `${A} vs ${B}`, r));
  return out;
}

function download(name, type, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function exportCsv(d, picks) {
  const q = (v) => (v === null || v === undefined ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replaceAll('"', '""')}"` : String(v));
  const head = ["section", "block", "stat", "a_value", "a_rank", "b_value", "b_rank", "verdict", "source"];
  return [head, ...statRows(d, picks)].map((r) => r.map(q).join(",")).join("\n");
}

function playerTable(title, cols, list) {
  if (!list || !list.length) return `<div class="plist"><h3>${esc(title)}</h3>${nodata("none in the window")}</div>`;
  return `<div class="plist"><h3>${esc(title)}</h3><table><thead><tr>${cols.map((c) => `<th${c.r ? ' class="r"' : ""}>${esc(c.h)}</th>`).join("")}</tr></thead>
    <tbody>${list.map((p) => `<tr>${cols.map((c) => `<td${c.r ? ' class="r"' : ""}>${c.f(p)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function playersSection(pl, A, B) {
  const col = (t) => {
    const x = pl[t.team_id], pf = x.pff, cf = x.cfbd;
    const pffCols = (role) => [
      { h: "Player", f: (p) => `${esc(p.player || "#" + p.player_id)} <span class="dim">${esc(p.position || "")}</span>` },
      { h: "Grade", r: 1, f: (p) => num(p.grade, "num", 1) },
      { h: pf[role].volume.replaceAll("_", " "), r: 1, f: (p) => num(p.volume, "int") },
      { h: pf[role].extra, r: 1, f: (p) => num(p.extra, role === "Defenders" ? "int" : "num", role === "QB" ? 3 : 2) },
      { h: "n", r: 1, f: (p) => p.games }];
    const cfCols = (key) => [
      { h: "Player", f: (p) => `${esc(p.player)} <span class="dim">${esc(p.position || "")}</span>` },
      { h: key === "ppa_rush" ? "Rush PPA" : "Pass PPA", r: 1, f: (p) => num(p[key], "signed", 3) },
      { h: "All PPA", r: 1, f: (p) => num(p.ppa, "signed", 3) },
      { h: "n", r: 1, f: (p) => p.games }];
    const pffHtml = pf ? ["QB", "Rushers", "Receivers", "Defenders"].map((r) => playerTable(`PFF · ${r}`, pffCols(r), pf[r].players)).join("")
      : nodata("PFF grades start in 2019");
    const cfTag = cf.ngt ? "" : cf.ngt_lag ? ` <span class="tag">all plays, ngt lags ${cf.ngt_lag} wk</span>` : "";
    const cfHtml = playerTable("CFBD · QB", cfCols("ppa_pass"), cf.QB) + playerTable("CFBD · Rushers", cfCols("ppa_rush"), cf.Rushers)
      + playerTable("CFBD · Receivers", cfCols("ppa_pass"), cf.Receivers);
    return `<div><div class="team-h">${esc(t.school)}${cfTag}</div>${pffHtml}${cfHtml}</div>`;
  };
  return card("Key players", `<div class="grid2">${col(A)}${col(B)}</div>`, {
    footer: "PFF and CFBD player ids have no crosswalk, so the two lists stay separate. PFF: QB by dropbacks, rushers by carries, receivers by routes, defenders by grade among players with 40%+ of the top snap count. CFBD: most games, then PPA; PPA is a game mean (the feed has no play counts).",
  });
}

function tape(rows) {
  if (!rows || !rows.length) return nodata("no rows");
  return `<div class="tape">${rows.map((r) => tapeRow(r)).join("")}</div>`;
}

// A concept row: every candidate stat arrives ranked; the dropdown only picks which to show.
function conceptRow(c, picks) {
  const i = Math.max(0, c.options.findIndex((o) => o.key === picks[c.concept]));
  const opt = c.options[i];
  const label = c.options.length > 1
    ? `<select class="pick" data-concept="${esc(c.concept)}" aria-label="${esc(c.label)} stat">${c.options.map((o, j) =>
        `<option value="${esc(o.key)}"${j === i ? " selected" : ""}>${esc(o.label)}</option>`).join("")}</select>`
    : esc(opt.label);
  return tapeRow(opt, label);
}

function spark(history, flip) {
  const pts = history.filter((h) => h.spread_home !== null && h.spread_home !== undefined);
  if (pts.length < 2) return "";
  const vals = pts.map((h) => (flip ? -h.spread_home : h.spread_home));
  const lo = Math.min(...vals), hi = Math.max(...vals), w = 120, h = 24;
  const xy = vals.map((v, i) => `${(i / (vals.length - 1)) * w},${hi === lo ? h / 2 : h - ((v - lo) / (hi - lo)) * h}`);
  return `<svg class="spark" width="${w}" height="${h}" role="img" aria-label="spread moved ${line(vals[0])} to ${line(vals.at(-1))}">
    <polyline points="${xy.join(" ")}" stroke="var(--color-accent)"/></svg>`;
}

function gameSection(g, A, B, full) {
  if (!g) return card("Game", nodata(full ? "these teams do not meet this season"
    : "no meeting on or after this week; earlier meetings are in head-to-head"));
  const aHome = g.home_team_id === A.team_id;
  const aSpread = (home) => home === null || home === undefined ? null : aHome ? home : -home;
  const bookRow = (name, bk) => {
    const n = bk && bk.now;
    if (!n) return `<tr><td>${esc(name)}</td><td colspan="6">${nodata("no line")}</td></tr>`;
    const sa = aSpread(n.spread.home);
    const pr = n.prices || {};
    const sp = (school) => (pr.spread && pr.spread[school] ? " (" + price(pr.spread[school][1]) + ")" : "");
    const ml = (school, isHome) => pr.ml && pr.ml[school] !== undefined ? price(pr.ml[school])
      : n.ml && n.ml[isHome ? "home" : "away"] != null ? price(n.ml[isHome ? "home" : "away"]) : "—";
    const tot = pr.total && pr.total.over ? ` (o${price(pr.total.over[1])} u${price((pr.total.under || [])[1])})` : "";
    const asOf = n.as_of ? `${n.source} ${stampTime(n.as_of)}` : "closing line";
    return `<tr><td>${esc(name)}</td><td class="r">${line(sa)}${sp(A.school)}</td><td class="r">${line(neg(sa))}${sp(B.school)}</td>
      <td class="r">${n.total ?? "—"}${tot}</td><td class="r">${ml(A.school, aHome)} / ${ml(B.school, !aHome)}</td>
      <td>${spark(bk.history, !aHome)}</td><td class="r"><span class="stamp">${esc(asOf)}</span></td></tr>`;
  };
  const closeRow = (r) => `<tr><td>${esc(r.book)}</td><td class="r">${line(aSpread(r.spread_open))} → ${line(aSpread(r.spread_close))}</td>
    <td class="r">${r.total_open ?? "—"} → ${r.total_close ?? "—"}</td>
    <td class="r">${price(aHome ? r.moneyline_home : r.moneyline_away) || "—"} / ${price(aHome ? r.moneyline_away : r.moneyline_home) || "—"}</td></tr>`;
  const w = g.weather;
  const weather = w ? `${w.game_indoors ? "Indoors" : `${num(w.temperature, "int")}°F · wind ${num(w.wind_speed, "int")} mph${w.weather_condition ? " · " + w.weather_condition : ""}`}` : nodata("not posted until near kickoff");
  const wp = g.win_prob ? `${A.school} ${(100 * (aHome ? g.win_prob.home_win_probability : 1 - g.win_prob.home_win_probability)).toFixed(1)}%` : nodata("CFBD has not posted one");
  const score = full && g.home_points !== null ? `<dt>Final</dt><dd>${esc(g.away_team)} ${g.away_points}, ${esc(g.home_team)} ${g.home_points}</dd>` : "";
  const body = `<dl class="kv">
      <dt>Kickoff</dt><dd>${g.tbd ? "TBD" : esc(when(g.start_date, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) + " ET")}</dd>
      <dt>Venue</dt><dd>${esc([g.venue_name, g.venue_city, g.venue_state].filter(Boolean).join(", ")) || "—"}${g.neutral ? ' <span class="tag">Neutral</span>' : ""}${g.conference_game ? ' <span class="tag">Conference</span>' : ""}${g.venue_dome ? ' <span class="tag">Dome</span>' : ""}</dd>
      <dt>Weather</dt><dd>${weather}</dd><dt>CFBD win prob.</dt><dd>${wp}</dd>${score}
    </dl>
    <h2 style="margin-top:16px">Your books</h2>
    <table class="books"><thead><tr><th>Book</th><th class="r">${esc(A.school)}</th><th class="r">${esc(B.school)}</th>
      <th class="r">Total</th><th class="r">ML ${esc(A.school)} / ${esc(B.school)}</th><th>Spread move</th><th class="r">As of</th></tr></thead>
      <tbody>${bookRow("DraftKings", g.main_books.draftkings)}${bookRow("FanDuel", g.main_books.fanduel)}</tbody></table>
    <h2 style="margin-top:16px">Sharp reference and consensus</h2>
    <table class="books"><thead><tr><th>Book</th><th class="r">${esc(A.school)} open → close</th><th class="r">Total open → close</th><th class="r">ML ${esc(A.school)} / ${esc(B.school)}</th></tr></thead>
      <tbody>${g.sharp.length ? g.sharp.map(closeRow).join("") : `<tr><td colspan="4">${nodata("no Pinnacle or Circa line")}</td></tr>`}
      <tr><td>Consensus median</td><td class="r">${line(aSpread(g.median_spread_open))} → ${line(aSpread(g.median_spread_close))} <span class="dim">(n=${g.n_books_spread_close ?? 0})</span></td>
      <td class="r">${g.median_total_open ?? "—"} → ${g.median_total_close ?? "—"} <span class="dim">(n=${g.n_books_total_close ?? 0})</span></td><td></td></tr></tbody></table>
    <details><summary>All other books (${g.other_books.length})</summary>
      <table class="books"><thead><tr><th>Book</th><th class="r">${esc(A.school)} open → close</th><th class="r">Total open → close</th><th class="r">ML</th></tr></thead>
      <tbody>${g.other_books.map(closeRow).join("")}</tbody></table></details>`;
  return card("Game", body, { footer: "Lines as posted; no edge or fair-price math. Current DK/FD from the newest Odds API snapshot, movement from core.fact_game_odds; open/close from core.fact_game_line; consensus from core.v_game_book_median (closing lines are not decision-time)." });
}

function profileCol(t, pr, week, full) {
  const rec = pr.record;
  const polls = pr.polls.length ? pr.polls.map((x) => `${x.poll.replace(" Poll", "")} #${x.rank}`).join(" · ") : "unranked";
  const pollWeek = pr.polls.length ? Math.max(...pr.polls.map((x) => x.week)) : null;
  const c = pr.coach, m = pr.massey, po = pr.portal;
  return `<div><div class="team-h">${esc(t.school)} <span class="sub">${esc(t.conference || "")}</span></div><dl class="kv">
    <dt>Record</dt><dd>${rec.w}-${rec.l} <span class="dim">(${rec.conf_w}-${rec.conf_l} conf)</span></dd>
    <dt>Polls</dt><dd>${esc(polls)}${pollWeek !== null && !full && pollWeek < week ? ` <span class="stamp stale">poll wk ${pollWeek}</span>` : ""}</dd>
    <dt>Massey</dt><dd>${m ? `#${m.cmp_rank} <span class="dim">composite of ${m.n_systems} · ${esc(m.date)}</span>` : nodata("no edition before kickoff")}</dd>
    <dt>Coach</dt><dd>${c ? `${esc(c.first_name)} ${esc(c.last_name)} <span class="dim">season ${c.season_n}</span>` : nodata("none listed")}</dd>
    <dt>Portal</dt><dd>${po.incoming} in / ${po.outgoing} out${po.incoming_stars ? ` <span class="dim">avg ${po.incoming_stars.toFixed(1)}★ in</span>` : ""}</dd>
  </dl></div>`;
}

function ratingsSection(r, A, B, full) {
  const massey = r.massey.length ? `<details><summary>Massey systems as of ${esc(r.massey_date)} (${r.massey.length})</summary>
    <table><thead><tr><th>System</th><th class="r">${esc(A.school)}</th><th class="r">${esc(B.school)}</th></tr></thead><tbody>
    ${r.massey.map((x) => `<tr><td>${esc(x.system)}</td><td class="r">${x.a ?? "—"}</td><td class="r">${x.b ?? "—"}</td></tr>`).join("")}
    </tbody></table></details>` : nodata("no Massey edition before kickoff");
  const stamp = full ? { text: `${r.season} final` } : { text: `PRIOR SEASON ${r.season} final` };
  let html = card("Ratings", tape(r.rows) + massey, {
    stamps: [stamp],
    footer: full ? "Season-final snapshots (postgame)." : "Every rating system here is a season-final snapshot, so only last season's is knowable before kickoff. Massey ranks are dated editions, so this season's are shown as of the week.",
  });
  if (r.postgame) html += card(`Ratings, ${r.season + 1} to date`, tape(r.postgame),
    { cls: "postgame", note: `<span class="postgame-note">Postgame · not knowable before kickoff</span>` });
  return html;
}

function unitsSection(u, A, B, full, week, picks) {
  const names = { [A.team_id]: A.school, [B.team_id]: B.school };
  const stamps = Object.values(u.sources).map((s) => {
    const ga = s.games[A.team_id], gb = s.games[B.team_id], ea = s.expected[A.team_id], eb = s.expected[B.team_id];
    const thru = s.through_week ? `through wk ${s.through_week}` : "no data";
    return { text: `${s.label} · ${thru} · games ${A.school} ${ga}/${ea}, ${B.school} ${gb}/${eb}`,
      stale: s.stale || (u.rollup !== "last3" && (ga < ea || gb < eb)) };
  });
  const tags = Object.values(u.sources).map((s) => s.ngt ? "" : s.ngt_lag
    ? `<span class="tag" title="The no-garbage-time feed lags its all-plays table">${esc(s.label)}: all plays, ngt lags ${s.ngt_lag} wk</span>`
    : u.ngt ? `<span class="tag" title="CFBD publishes no garbage-time-filtered version">${esc(s.label)}: all plays</span>` : "").join(" ");
  return card("Unit matchups", `<p class="sub">${tags}</p>${pairBlocks(u.blocks, names, picks)}`, {
    stamps,
    footer: `${full ? "Whole season, postseason included." : `Games before week ${week}.`} Roll-up: ${esc(u.rollup === "pooled" ? "play-weighted (pooled)" : u.rollup === "mean" ? "game mean" : "last 3 games, pooled")}${u.fcs ? ", FCS games excluded" : ""}. Rank is among FBS teams with a game in the window; the dot marks the unit whose rank is better. Explosiveness is pooled by all plays, an approximation (CFBD averages it over successful plays). PPA-feed rows have no play counts, so they are game means.`,
  });
}

const cache = { key: null, data: null };

async function matchup(p) {
  const full = p.mode === "full";
  const [season_type, wk] = (p.week || "").includes(":") ? p.week.split(":") : ["regular", p.week];
  const query = { a: p.a, b: p.b, season: p.season, week: wk, season_type, game_id: p.game_id,
    mode: p.mode, postgame: p.postgame, rollup: p.rollup, fcs: p.fcs, ngt: p.ngt };
  const key = JSON.stringify(query);
  if (cache.key !== key) {
    app.innerHTML = `<p class="sub">Loading matchup…</p>`;
    cache.data = await api("/api/matchup", query);
    cache.key = key;
  }
  const d = cache.data;
  const picks = Object.fromEntries(Object.entries(p).filter(([k]) => k.startsWith("pick_")).map(([k, v]) => [k.slice(5), v]));
  const m = d.meta, s = d.sections, A = m.a, B = m.b;
  setSnap(m.snapshot);
  const cw = full ? "full" : m.season_type === "regular" ? String(m.week) : `${m.season_type}:${m.week}`;
  const chips = (pr) => [
    `${pr.record.w}-${pr.record.l}`,
    ...pr.polls.map((x) => `${x.poll.replace(" Poll", "").replace("AP Top 25", "AP")} #${x.rank}`),
    pr.massey ? `Massey #${pr.massey.cmp_rank}` : null,
  ].filter(Boolean).map((c) => `<span class="chip">${esc(c)}</span>`).join("");

  const weeks = m.weeks;
  let html = full ? `<div class="banner">Full season · postgame. Every number includes games played after any betting decision.</div>` : "";
  html += `<div class="vs"><div class="a"><div class="team">${esc(A.school)}</div><div class="sub">${esc(A.conference || A.classification || "")}</div>
      <div class="chips">${chips(s.profile.a)}</div></div>
    <div class="mid">${m.season}<br>${full ? "Full season" : "As of week " + m.week}<br><span class="dim">${m.elapsed_ms} ms</span></div>
    <div class="b"><div class="team">${esc(B.school)}</div><div class="sub">${esc(B.conference || B.classification || "")}</div>
      <div class="chips">${chips(s.profile.b)}</div></div></div>
    <div class="controls">
      <label>Season<select id="m-season">${seasonOptions(m.season, Math.max(m.season, new Date().getFullYear()))}</select></label>
      <label>As of<select id="m-week">${weekOptions(weeks, cw, { full: true })}</select></label>
      <label>Roll-up<select id="m-rollup">${[["pooled", "Pooled (play-weighted)"], ["mean", "Game mean"], ["last3", "Last 3 games"]]
        .map(([v, l]) => `<option value="${v}"${(p.rollup || "pooled") === v ? " selected" : ""}>${l}</option>`).join("")}</select></label>
      <label class="check"><input type="checkbox" id="m-fcs"${p.fcs === "0" ? "" : " checked"}> Exclude FCS games</label>
      <label class="check"><input type="checkbox" id="m-ngt"${p.ngt === "0" ? "" : " checked"}> Exclude garbage time</label>
      ${full ? "" : `<label class="check"><input type="checkbox" id="m-post"${p.postgame === "1" ? " checked" : ""}> Show postgame panels</label>`}
      <button class="ghost" id="m-swap">Swap teams</button>
      <button class="ghost" id="m-csv">Export CSV</button>
      <button class="ghost" id="m-json">Export JSON</button>
    </div>`;
  html += gameSection(s.game, A, B, full);
  html += card("Team profile", `<div class="grid2">${profileCol(A, s.profile.a, m.week, full)}${profileCol(B, s.profile.b, m.week, full)}</div>
    <h2 style="margin:16px 0 4px">Roster inputs · fixed before the season</h2>${tape(s.profile.rows)}`, {
    stamps: [{ text: s.profile.a.massey ? `Massey ${s.profile.a.massey.date}` : "" }],
    footer: "Record and polls as of the week (the poll labelled week N is released before week N's games). Talent, recruiting and returning production are fixed before the season; the small grey line under each value is last season's.",
  });
  html += ratingsSection(s.ratings, A, B, full);
  html += unitsSection(s.units, A, B, full, m.week, picks);
  html += pffSection(s.pff, A, B, picks);
  html += specialTeamsSection(s.special_teams, A, B, full);
  html += playersSection(s.players, A, B);
  html += bettingSection(s.betting, A, B);
  html += scheduleSection(s.schedule, A, B);
  html += h2hSection(s.h2h, A, B);
  html += trendsSection(s.trends, A, B);
  html += sourcesSection(d);
  app.innerHTML = html;

  const base = { ...p, season: m.season };
  document.getElementById("m-season").onchange = (e) => go({ ...base, season: e.target.value, week: "", game_id: "" });
  document.getElementById("m-week").onchange = (e) => go({ ...base, week: e.target.value === "full" ? "" : e.target.value,
    mode: e.target.value === "full" ? "full" : "" });
  const post = document.getElementById("m-post");
  if (post) post.onchange = (e) => go({ ...base, postgame: e.target.checked ? "1" : "" });
  document.getElementById("m-rollup").onchange = (e) => go({ ...base, rollup: e.target.value === "pooled" ? "" : e.target.value });
  document.getElementById("m-fcs").onchange = (e) => go({ ...base, fcs: e.target.checked ? "" : "0" });
  document.getElementById("m-ngt").onchange = (e) => go({ ...base, ngt: e.target.checked ? "" : "0" });
  document.getElementById("m-swap").onclick = () => go({ ...base, a: p.b, b: p.a });
  const stem = `matchup-${A.school}-${B.school}-${m.season}-${full ? "full" : "wk" + m.week}`.replace(/[^\w-]+/g, "_");
  document.getElementById("m-csv").onclick = () => download(stem + ".csv", "text/csv", exportCsv(d, picks));
  document.getElementById("m-json").onclick = () => download(stem + ".json", "application/json", JSON.stringify(d, null, 2));
  const y = window.scrollY;
  app.querySelectorAll("select.pick").forEach((sel) => {
    sel.onchange = () => { go({ ...base, ["pick_" + sel.dataset.concept]: sel.value }, true); window.scrollTo(0, y); };
  });
}

render();
