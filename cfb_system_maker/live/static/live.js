// Live odds board. Polls /api/live every 30 s; the server caches Polymarket for 20 s.
// Each card remembers its last prices so a move since the previous poll gets an up/down mark.
(() => {
  const POLL_MS = 30000;
  const last = new Map();               // `${slug}:${field}` -> previous midpoint
  const $ = (id) => document.getElementById(id);
  const pct = (p) => (p == null ? "–" : `${Math.round(p * 100)}%`);
  const signed = (n) => (n > 0 ? `+${n}` : `${n}`);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let data = null;

  function move(key, mid) {
    const prev = last.get(key);
    last.set(key, mid);
    if (prev == null || mid == null || Math.abs(mid - prev) < 0.005) return "";
    return mid > prev ? `<span class="up" title="up from ${pct(prev)}">▲</span>`
                      : `<span class="down" title="down from ${pct(prev)}">▼</span>`;
  }

  function line(g, field, label, describe) {
    const q = g[field];
    if (!q) return `<div class="line"><span class="k">${label}</span><span class="v">–</span></div>`;
    return `<div class="line"><span class="k">${label}</span>
      <span class="v">${esc(describe(q))} <b>${pct(q.mid)}</b>${move(`${g.slug}:${field}`, q.mid)}</span>
      <span class="book">${q.bid.toFixed(2)} / ${q.ask.toFixed(2)} · $${q.liquidity.toLocaleString()}</span></div>`;
  }

  function card(g) {
    const live = g.state === "live" || g.state === "starting";
    const time = (iso) => new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    const status = g.state === "live" ? `${esc(g.period || "")} ${esc(g.clock || "")}`.trim()
      : g.state === "starting" ? "Kicking off" : time(g.kickoff);
    const asof = g.updated_at ? `<span class="asof">as of ${new Date(g.updated_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" })}</span>` : "";
    const ml = g.moneyline;
    const row = (team, sc, chance, side) => `<div class="team"><span class="name">${esc(team)}</span>
      ${live ? `<span class="score">${sc ?? ""}</span>` : ""}
      <span class="win${ml && ml.wide ? " wide" : ""}"${ml && ml.wide ? ' title="Wide book: bid and ask more than 10 cents apart"' : ""}>${ml ? pct(chance) : "–"}${ml ? move(`${g.slug}:ml-${side}`, chance) : ""}</span></div>`;
    return `<article class="card${live ? " is-live" : ""}">
      <header><span class="status">${live ? '<i class="dot" aria-hidden="true"></i>' : ""}${status}</span>
        ${asof}<a href="${esc(g.url)}" target="_blank" rel="noopener">Polymarket ↗</a></header>
      <div class="teams"><div class="team head"><span></span>${live ? "<span>Score</span>" : ""}<span>Win</span></div>
        ${row(g.away, g.away_score, ml && ml.away, "away")}${row(g.home, g.home_score, ml && ml.home, "home")}</div>
      ${line(g, "spread", "Spread", (q) => `${q.first} ${signed(q.line)}`)}
      ${line(g, "total", "Total", (q) => `Over ${q.line}`)}
    </article>`;
  }

  function render() {
    if (!data) return;
    const term = $("q").value.trim().toLowerCase();
    $("fbs-wrap").hidden = !data.fbs_available;
    const fbsOnly = data.fbs_available && $("fbs").checked;   // at least one FBS team
    const keep = (g) => (!term || `${g.away} ${g.home}`.toLowerCase().includes(term))
      && (!fbsOnly || g.away_fbs || g.home_fbs);
    for (const [id, empty] of [["live", "No games in progress."], ["upcoming", "Nothing kicks off in the next 3 hours."]]) {
      const games = data[id].filter(keep);
      $(id).innerHTML = games.length ? games.map(card).join("") : `<p class="empty">${empty}</p>`;
    }
  }

  async function poll() {
    try {
      const res = await fetch("/api/live");
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || res.statusText);
      data = body;
      render();
      $("snap").textContent = `Updated ${new Date(body.pulled_at).toLocaleTimeString()}`;
      $("snap").classList.remove("stale");
    } catch (err) {
      $("snap").textContent = `${err.message} Showing the last prices.`;
      $("snap").classList.add("stale");
    }
  }

  try { $("fbs").checked = localStorage.getItem("live-fbs") !== "0"; } catch (e) { /* storage blocked */ }
  $("fbs").addEventListener("change", () => {
    try { localStorage.setItem("live-fbs", $("fbs").checked ? "1" : "0"); } catch (e) { /* storage blocked */ }
    last.clear(); render();
  });
  $("q").addEventListener("input", () => { last.clear(); render(); });
  poll();
  setInterval(poll, POLL_MS);
})();
