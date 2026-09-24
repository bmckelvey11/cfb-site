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
  const pv = prior && prior.value !== null && prior.value !== undefined
    ? `<span class="prior">'${String(prior.season).slice(2)} ${num(prior.value, fmt, dp)}${prior.rank ? " · #" + prior.rank : ""}</span>` : "";
  const val = s.value === null || s.value === undefined
    ? `<span class="val">${nodata("none")}${pv}</span>`
    : `<span class="val${win ? " win" : ""}">${num(s.value, fmt, dp)}${pv}</span>`;
  return `<div class="side ${align}">${align === "a" ? rank + val : val + rank}</div>`;
}

function tape(rows) {
  if (!rows || !rows.length) return nodata("no rows");
  return `<div class="tape">${rows.map((r) => {
    const pa = r.prior ? { ...r.prior.a, season: r.prior.season } : null;
    const pb = r.prior ? { ...r.prior.b, season: r.prior.season } : null;
    const tip = `${r.source} · ${r.verdict}${r.season ? " · " + r.season : ""}`;
    return side(r.a, r.edge === "a", pa, r.fmt, r.dp, "a")
      + `<div class="label" title="${esc(tip)}">${esc(r.label)}</div>`
      + side(r.b, r.edge === "b", pb, r.fmt, r.dp, "b");
  }).join("")}</div>`;
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
  if (!g) return card("Game", nodata("these teams do not meet this season"));
  const aHome = g.home_team_id === A.team_id;
  const aSpread = (home) => home === null || home === undefined ? null : aHome ? home : -home;
  const bookRow = (name, bk) => {
    const n = bk && bk.now;
    if (!n) return `<tr><td>${esc(name)}</td><td colspan="6">${nodata("no line")}</td></tr>`;
    const sa = aSpread(n.spread.home);
    const pr = n.prices || {};
    const sp = (school) => (pr.spread && pr.spread[school] ? " (" + price(pr.spread[school][1]) + ")" : "");
    const ml = (school) => (pr.ml && pr.ml[school] !== undefined ? price(pr.ml[school]) : "—");
    const tot = pr.total && pr.total.over ? ` (o${price(pr.total.over[1])} u${price((pr.total.under || [])[1])})` : "";
    return `<tr><td>${esc(name)}</td><td class="r">${line(sa)}${sp(A.school)}</td><td class="r">${line(neg(sa))}${sp(B.school)}</td>
      <td class="r">${n.total ?? "—"}${tot}</td><td class="r">${ml(A.school)} / ${ml(B.school)}</td>
      <td>${spark(bk.history, !aHome)}</td><td class="r"><span class="stamp">${esc(n.source)} ${esc(stampTime(n.as_of))}</span></td></tr>`;
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

async function matchup(p) {
  app.innerHTML = `<p class="sub">Loading matchup…</p>`;
  const full = p.mode === "full";
  const [season_type, wk] = (p.week || "").includes(":") ? p.week.split(":") : ["regular", p.week];
  const d = await api("/api/matchup", { a: p.a, b: p.b, season: p.season, week: wk, season_type,
    game_id: p.game_id, mode: p.mode, postgame: p.postgame });
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
      ${full ? "" : `<label class="check"><input type="checkbox" id="m-post"${p.postgame === "1" ? " checked" : ""}> Show postgame panels</label>`}
      <button class="ghost" id="m-swap">Swap teams</button>
    </div>`;
  html += gameSection(s.game, A, B, full);
  html += card("Team profile", `<div class="grid2">${profileCol(A, s.profile.a, m.week, full)}${profileCol(B, s.profile.b, m.week, full)}</div>
    <h2 style="margin:16px 0 4px">Roster inputs · fixed before the season</h2>${tape(s.profile.rows)}`, {
    stamps: [{ text: s.profile.a.massey ? `Massey ${s.profile.a.massey.date}` : "" }],
    footer: "Record and polls as of the week (the poll labelled week N is released before week N's games). Talent, recruiting and returning production are fixed before the season; the small grey line under each value is last season's.",
  });
  html += ratingsSection(s.ratings, A, B, full);
  app.innerHTML = html;

  const base = { a: p.a, b: p.b, season: m.season, week: p.week, mode: p.mode, postgame: p.postgame, game_id: p.game_id };
  document.getElementById("m-season").onchange = (e) => go({ ...base, season: e.target.value, week: "", game_id: "" });
  document.getElementById("m-week").onchange = (e) => go({ ...base, week: e.target.value === "full" ? "" : e.target.value,
    mode: e.target.value === "full" ? "full" : "" });
  const post = document.getElementById("m-post");
  if (post) post.onchange = (e) => go({ ...base, postgame: e.target.checked ? "1" : "" });
  document.getElementById("m-swap").onclick = () => go({ ...base, a: p.b, b: p.a });
}

render();
