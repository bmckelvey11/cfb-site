# Ship Plan — Professional-Quality Web App

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the `cfb_system_maker` web app from "feature-complete local dev tool" to a shippable, professional-quality sports-betting analytics product: installable from a fresh clone, served by a production WSGI server, hardened (logging, error pages, throttling, security headers), visually finished (branding, favicon, disclaimer, empty states), and verified live against the 2026 season.

**Architecture:** No rewrite. The Flask + vanilla JS/CSS stack stays (project constraint). This plan adds the missing production layer around the existing app — packaging, serving, observability, hardening, polish — then hands off to the already-written feature roadmap (`docs/roadmap-v2-2026-08.md`) for v1.1→v1.5 product depth. Feature milestones are NOT re-planned here; each gets its own detailed plan at execution time.

**Tech Stack:** Python 3.11+, Flask, waitress (new — production WSGI, pure-Python, Windows-native), vanilla JS/CSS, pytest. No frontend framework, no build step (existing constraint, kept).

## Scope assumptions (stated, per CLAUDE.md §1)

1. **"Ship" = professional-grade product you run and could demo/hand to a peer** — installable anywhere, served properly, polished. It does **not** mean public multi-user SaaS hosting. Public hosting is a separate later decision (needs auth, hosting, terms); a decision gate is included as Phase 5 so nothing here blocks it.
2. **Analytics only, no wagering.** The app backtests and tracks; it never places or facilitates bets. A visible disclaimer saying exactly that is part of "professional quality" (Task 3.3).
3. **Feature scope for ship = v1.1 Season Readiness** (roadmap v2 §2). v1.2+ (CLV, results depth, weekly loop) are post-ship milestones, sequenced in Phase 6.

## Global Constraints

- Python + Flask + vanilla JS/CSS, no frontend framework, no build step (PROJECT.md constraint).
- `cfbd-python/` is a vendored dependency — never edited, never treated as our code.
- `GameRecord` field order is the CSV read/write contract; no ad hoc column adds.
- `SavedSystem` JSON changes must default gracefully for older files.
- No lookahead: new registry features are entering-game only or quarantined.
- Default bind stays `127.0.0.1` — never expose beyond localhost without Phase 5's auth gate.
- All new href/text rendering uses `urlencode`/Jinja auto-escape, never `|safe` (Phase-1 v1.0 decision).
- Full suite (`python -m pytest`) must pass before every merge; ~435 tests today.

## Current state (surveyed 2026-08-26)

- v1.0 Bet Labs parity shipped 2026-07-20 (5 phases, 21 plans). `.planning/STATE.md`: "Awaiting next milestone."
- Branch `fix/web-app-review-2026-08-26`: **27 commits ahead of master** (correctness, crash-resistance, modal robustness, caching, same-origin POST check, a11y, totals semantics). All 14 planned review tasks done except task 14 (web.py module split, explicitly deferred).
- Working tree dirty: 7 untracked analysis docs in `docs/`, modified `.solopreneur/observer-log.md`.
- **Fresh clone is broken**: `requirements.txt` line 1 is `-r cfbd-python/requirements.txt`, but `cfbd-python/` is in `.gitignore`.
- Serving: Flask dev server only (`cli.py:400-405`). No WSGI server, no Dockerfile, no pyproject, no process manager.
- No logging config anywhere. No error pages. No favicon (route returns 204). No export/download path.
- `POST /search-runs/<name>/narrate` calls the paid Anthropic API with zero throttling.
- `copy_example` (`web.py:487-500`) swallows all errors; identical redirect on success and failure.
- Zero inline `<script>`/`<style>` anywhere (verified) — a strict CSP is cheap.
- Season starts ~2026-08-29. Two v1.0 verifications are deferred to week 1 (`human_needed`).

## Phase map

| Phase | What | When | Detail level |
|---|---|---|---|
| 0 | Land what's ready (merge branch, commit docs, bookkeeping) | Today | Full steps below |
| 1 | Installable anywhere (vendored-dep fix, pinning, prod server) | This week | Full steps below |
| 2 | Production hardening (logging, error pages, throttle, headers, silent-failure fix) | This week | Full steps below |
| 3 | Professional finish (branding, disclaimer, favicon, empty states, browser smoke test) | This week / week 1 | Full steps below |
| 4 | v1.1 Season Readiness features + live verification | Before/at week 1 (~08-29) | Task level; details in roadmap v2 §2 |
| 5 | Decision gate: public hosting (auth, deploy target) | User decision | Gate only |
| 6 | Post-ship milestones v1.2–v1.5 | September onward | Pointer to roadmap v2 |

---

## Phase 0 — Land what's ready (today)

The single highest-leverage ship action: 27 finished, tested commits are not on master.

### Task 0.1: Commit the analysis docs and bookkeeping

**Files:**
- Add: `docs/bet-history-analysis.md`, `docs/clv-analysis.md`, `docs/seasonal-totals-backtest.md`, `docs/stat-angles-retest.md`, `docs/under-bets-analysis.md`, `docs/under-bets-summary.md`, `docs/under-team-stats-analysis.md`
- Modify: `.planning/STATE.md` (Quick Tasks table — add row for `20260826-register-player-success-rate-endpoints`)
- Modify: `.solopreneur/observer-log.md` (already modified; include as-is)

**Interfaces:** none — docs only.

- [ ] **Step 1: Add the quick-task row to STATE.md**

Append to the Quick Tasks Completed table in `.planning/STATE.md`:

```markdown
| 2026-08-26 | register-player-success-rate-endpoints | Registered player success-rate GraphQL/REST endpoints per .planning/quick/20260826-register-player-success-rate-endpoints/PLAN.md | complete |
```

(Adjust the "What" cell to match that PLAN.md's actual summary — read it first.)

- [ ] **Step 2: Commit**

```bash
git add docs/bet-history-analysis.md docs/clv-analysis.md docs/seasonal-totals-backtest.md docs/stat-angles-retest.md docs/under-bets-analysis.md docs/under-bets-summary.md docs/under-team-stats-analysis.md .planning/STATE.md .solopreneur/observer-log.md
git commit -m "docs: commit 2026-08 analysis arc (CLV/unders/stat-angles) + STATE bookkeeping"
```

### Task 0.2: Merge the review branch to master

**Files:** none created; git only.

- [ ] **Step 1: Full suite on the branch**

Run: `python -m pytest`
Expected: all pass (~435). Any failure blocks the merge — fix on the branch first.

- [ ] **Step 2: Merge and push**

```bash
git checkout master
git pull
git merge --no-ff fix/web-app-review-2026-08-26 -m "merge: web app review fixes 2026-08-26 (correctness, caching, modal robustness, totals semantics)"
python -m pytest
git push
```

Expected: clean merge (branch is ahead-only per survey; if master moved, resolve then rerun suite).

- [ ] **Step 3: Verify the app still boots**

Run: `python -m cfb_system_maker web --data-dir data --port 5000` and load `http://127.0.0.1:5000/` — dashboard renders, `/system` renders, one modal opens. Stop the server.

**Done when:** master contains the 27 commits, suite green on master, working tree clean.

---

## Phase 1 — Installable anywhere

A professional app installs from a fresh clone with documented steps. Today it cannot.

### Task 1.1: Fix the vendored-dependency break

`cfbd-python/` is loaded by path injection at runtime and referenced by `requirements.txt`, but gitignored — a fresh clone has neither the package nor its requirements file.

**Files:**
- Modify: `.gitignore` (remove the `cfbd-python/` ignore line)
- Add: the entire `cfbd-python/` tree to git
- Modify: `README.md` (setup section)

**Interfaces:**
- Produces: a repo where `git clone` + `pip install -r requirements.txt` succeeds with no manual steps.

**Decision (recommended: commit the vendored tree).** Alternatives considered: (a) git submodule — adds a clone-time step and pin-drift risk for a pydantic-v1-frozen upstream we never update casually; (b) setup script that clones a pinned SHA — one more moving part, network required at install. Committing the tree matches how it's already treated (vendored, never edited) and makes clones self-contained. It is a few MB of Python source. If the user objects to repo size, fall back to (b).

- [ ] **Step 1: Un-ignore and add**

```bash
# remove the cfbd-python ignore entry from .gitignore first (edit the file), then:
git add .gitignore cfbd-python
git status   # sanity: cfbd-python files staged, no venv/eggs/__pycache__ inside
```

`cfbd-python/` is a plain git clone, so it has a nested `.git/`. To vendor it as ordinary files: record its current SHA first (`git -C cfbd-python rev-parse HEAD` → note it in the commit message), then delete the nested metadata (`rm -rf cfbd-python/.git`), then `git add cfbd-python`. If `git status` shows `cfbd-python` as a single gitlink line instead of individual files, the nested `.git` still exists — remove it and run `git rm --cached cfbd-python` then `git add cfbd-python/` again. Confirm `.gitignore`'s global `__pycache__`/egg-info patterns still apply inside the tree.

- [ ] **Step 2: Fresh-clone verification**

```bash
git commit -m "build: vendor cfbd-python tree so fresh clones install"
cd "$TMPDIR" && git clone <repo-url> cfb-site-clone-test && cd cfb-site-clone-test
python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements.txt
python -m cfb_system_maker sample --data-dir data
python -m pytest -x -q
```

Expected: install succeeds, sample backtest runs, suite passes. Delete the test clone after.

### Task 1.2: Pin the dependency set

**Files:**
- Modify: `requirements.txt` (add floor/ceiling pins)
- Create: `requirements.lock` (full freeze)

**Interfaces:**
- Produces: reproducible installs; `requirements.lock` is the ship artifact, `requirements.txt` stays the human-edited source.

- [ ] **Step 1: Pin top-level requirements**

`requirements.txt` becomes:

```text
-r cfbd-python/requirements.txt
Flask>=3.0,<4
waitress>=3.0,<4
anthropic==0.111.0
pytest>=8,<9
```

- [ ] **Step 2: Generate the lock**

```bash
pip install -r requirements.txt
pip freeze --exclude-editable > requirements.lock
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt requirements.lock
git commit -m "build: pin Flask/waitress/pytest, add requirements.lock"
```

### Task 1.3: Production WSGI serving

Flask's dev server is single-threaded-ish, unhardened, and prints a warning saying not to ship it. `waitress` is the standard pure-Python production server that works natively on Windows (gunicorn does not).

**Files:**
- Modify: `cfb_system_maker/cli.py:400-405` (the `web` command handler) and the `web` argparse block (`cli.py:535-539`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `create_app(data_dir)` from `web.py` (unchanged).
- Produces: `python -m cfb_system_maker web` serves via waitress by default; `--debug` keeps the Flask dev server with the reloader.

- [ ] **Step 1: Write the failing test**

In `tests/test_cli.py` (follow the existing parser-level test pattern in that file):

```python
def test_web_command_defaults_to_production_server(monkeypatch):
    served = {}

    def fake_serve(app, host, port, threads):
        served.update(host=host, port=port, threads=threads)

    monkeypatch.setattr("waitress.serve", fake_serve)
    from cfb_system_maker import cli
    cli.main(["web", "--data-dir", "data", "--port", "5000"])
    assert served == {"host": "127.0.0.1", "port": 5000, "threads": 8}


def test_web_command_debug_uses_flask_dev_server(monkeypatch):
    ran = {}

    def fake_run(self, host, port, debug):
        ran.update(host=host, port=port, debug=debug)

    monkeypatch.setattr("flask.Flask.run", fake_run)
    from cfb_system_maker import cli
    cli.main(["web", "--data-dir", "data", "--port", "5000", "--debug"])
    assert ran["debug"] is True
```

(Adapt entry-point spelling to how `cli.py` actually exposes `main` — read the file first; existing CLI tests show the invocation convention.)

- [ ] **Step 2: Run to verify both fail**

Run: `python -m pytest tests/test_cli.py -k web_command -v`
Expected: FAIL (waitress not wired / serve never called).

- [ ] **Step 3: Implement**

In the `web` command handler in `cli.py`, replace the unconditional `app.run(...)`:

```python
app = create_app(args.data_dir)
if args.debug:
    app.run(host=args.host, port=args.port, debug=True)
else:
    from waitress import serve
    serve(app, host=args.host, port=args.port, threads=8)
```

Note on the existing in-process caches (`_FIGURE_CACHE`, `_DATA_CACHE`, `_FEATURE_OPTIONS_CACHE` at `web.py:1440-1442`, plus `_cached_backtest`'s store): waitress is one process with a thread pool, so the caches keep working. Dict get/set is GIL-atomic; worst case two threads race to compute the same entry and one wins — acceptable. Do NOT add locking speculatively.

- [ ] **Step 4: Run tests, then boot both modes manually**

Run: `python -m pytest tests/test_cli.py -v` → PASS.
Run `python -m cfb_system_maker web --data-dir data` → no Flask "development server" warning, dashboard loads. Then `--debug` → dev server + reloader as before.

- [ ] **Step 5: Update launchers and commit**

`launch.bat` and `.claude/launch.json` need no change (same command, now prod-served). Update the CLAUDE.md commands section's `web` line comment if it mentions Flask dev server.

```bash
git add cfb_system_maker/cli.py tests/test_cli.py requirements.txt
git commit -m "feat(cli): serve web via waitress by default, Flask dev server behind --debug"
```

### Task 1.4: Environment-variable config

**Files:**
- Modify: `cfb_system_maker/cli.py` (web argparse defaults)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `CFB_DATA_DIR`, `CFB_WEB_HOST`, `CFB_WEB_PORT` env vars as defaults; CLI flags still win.

- [ ] **Step 1: Failing test**

```python
def test_web_command_reads_env_defaults(monkeypatch):
    monkeypatch.setenv("CFB_DATA_DIR", "elsewhere")
    monkeypatch.setenv("CFB_WEB_PORT", "8123")
    captured = {}
    monkeypatch.setattr("waitress.serve", lambda app, host, port, threads: captured.update(port=port))
    created = {}
    from cfb_system_maker import cli, web
    real_create = web.create_app
    monkeypatch.setattr("cfb_system_maker.cli.create_app", lambda d: created.update(data_dir=d) or real_create("data"))
    cli.main(["web"])
    assert created["data_dir"] == "elsewhere"
    assert captured["port"] == 8123
```

- [ ] **Step 2: Implement**

In the `web` argparse block:

```python
web_parser.add_argument("--data-dir", default=os.environ.get("CFB_DATA_DIR", "data"))
web_parser.add_argument("--host", default=os.environ.get("CFB_WEB_HOST", "127.0.0.1"))
web_parser.add_argument("--port", type=int, default=int(os.environ.get("CFB_WEB_PORT", "5000")))
```

- [ ] **Step 3: Test → PASS → commit**

```bash
git add cfb_system_maker/cli.py tests/test_cli.py
git commit -m "feat(cli): CFB_DATA_DIR/CFB_WEB_HOST/CFB_WEB_PORT env defaults for web command"
```

**Done when (Phase 1):** a colleague on a clean machine can `git clone` → `pip install -r requirements.lock` → drop in `env.env` → `python -m cfb_system_maker web` and get the production-served dashboard.

---

## Phase 2 — Production hardening

### Task 2.1: Logging

Zero logging configuration exists. Ship minimum: level-configured stdlib logging plus one access-style line per request, so a hung page or 500 is diagnosable.

**Files:**
- Modify: `cfb_system_maker/cli.py` (basicConfig in the web handler)
- Modify: `cfb_system_maker/web.py` (`create_app` — after_request log line)
- Test: `tests/test_web.py`

**Interfaces:**
- Produces: `app.logger` usable by every later task (error pages, narrate throttle).

- [ ] **Step 1: Failing test**

```python
def test_requests_emit_one_access_log_line(client, caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="cfb_system_maker.web"):
        client.get("/")
    lines = [r for r in caplog.records if "GET /" in r.getMessage()]
    assert len(lines) == 1
    assert "200" in lines[0].getMessage()
```

(Use the existing `client` fixture pattern from `tests/test_web.py`.)

- [ ] **Step 2: Implement**

In `create_app`, next to the existing `before_request` (add `g` to the existing `from flask import ...` line if it is not already imported):

```python
import logging
import time as _time

logger = logging.getLogger(__name__)

@app.before_request
def _start_timer():
    g.request_start = _time.perf_counter()

@app.after_request
def _access_log(response):
    elapsed_ms = (_time.perf_counter() - g.request_start) * 1000
    logger.info("%s %s %s %.0fms", request.method, request.full_path.rstrip("?"), response.status_code, elapsed_ms)
    return response
```

In the CLI web handler, before serving:

```python
logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
```

- [ ] **Step 3: Test → PASS → commit**

```bash
git add cfb_system_maker/web.py cfb_system_maker/cli.py tests/test_web.py
git commit -m "feat(web): access logging with request timing"
```

### Task 2.2: Error pages (404 / 500)

Default Werkzeug error pages look like a stack dump, not a product.

**Files:**
- Create: `cfb_system_maker/templates/error.html`
- Modify: `cfb_system_maker/web.py` (`create_app` — two errorhandlers)
- Test: `tests/test_web.py`

- [ ] **Step 1: Failing tests**

```python
def test_404_renders_branded_error_page(client):
    resp = client.get("/definitely-not-a-route")
    assert resp.status_code == 404
    assert b"Page not found" in resp.data
    assert b"styles.css" in resp.data  # branded, not werkzeug default


def test_500_renders_branded_error_page(app_instance, client):
    @app_instance.route("/boom")
    def boom():
        raise RuntimeError("kaboom")
    app_instance.config["PROPAGATE_EXCEPTIONS"] = False
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert b"Something went wrong" in resp.data
    assert b"kaboom" not in resp.data  # no leak
```

(`app_instance` = however the existing fixtures expose the app object; match the file's convention.)

- [ ] **Step 2: Template**

`templates/error.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} — CFB System Maker</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
</head>
<body>
  <main class="error-page">
    <h1>{{ title }}</h1>
    <p>{{ message }}</p>
    <p><a href="{{ url_for('dashboard') }}">Back to My Systems</a></p>
  </main>
</body>
</html>
```

- [ ] **Step 3: Handlers in `create_app`**

```python
@app.errorhandler(404)
def _not_found(err):
    return render_template("error.html", title="Page not found",
                           message="That page does not exist."), 404

@app.errorhandler(500)
def _server_error(err):
    logger.exception("unhandled error on %s %s", request.method, request.path)
    return render_template("error.html", title="Something went wrong",
                           message="An internal error occurred. Details are in the server log."), 500
```

Plus ~10 lines of `.error-page` styling in `styles.css` consistent with the existing look.

- [ ] **Step 4: Tests → PASS → commit**

```bash
git add cfb_system_maker/templates/error.html cfb_system_maker/web.py cfb_system_maker/static/styles.css tests/test_web.py
git commit -m "feat(web): branded 404/500 error pages, exception logging"
```

### Task 2.3: Surface `copy_example` failures

Today failure and success redirect identically (`web.py:487-500`) — a silent-failure bug in a money-adjacent product.

**Files:**
- Modify: `cfb_system_maker/web.py` (`copy_example`)
- Modify: `cfb_system_maker/templates/dashboard.html` (error banner)
- Test: `tests/test_web.py`

- [ ] **Step 1: Failing test**

```python
def test_copy_example_failure_redirects_with_error_flag(client, monkeypatch):
    monkeypatch.setattr("cfb_system_maker.web.save_system",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    resp = client.post("/copy-example", data={"name": "neutral-unders"})
    assert resp.status_code == 302
    assert "copy_error=1" in resp.headers["Location"]
```

(Monkeypatch target = whatever function the except-block actually wraps — read `web.py:487-500` and patch the real callee.)

- [ ] **Step 2: Implement**

Replace the bare `pass` except-block:

```python
except (ValueError, OSError, json.JSONDecodeError):
    logger.exception("copy_example failed for %r", requested_name)
    return redirect(url_for("dashboard", tab="examples", copy_error="1"))
```

In `dashboard.html`, at the top of the Examples tab pane:

```html
{% if request.args.get('copy_error') %}
<p class="banner banner-error">Could not copy the example system. See the server log.</p>
{% endif %}
```

- [ ] **Step 3: Tests (new + existing 10 example-tab tests) → PASS → commit**

```bash
git add cfb_system_maker/web.py cfb_system_maker/templates/dashboard.html cfb_system_maker/static/styles.css tests/test_web.py
git commit -m "fix(web): surface copy-example failures instead of silent redirect"
```

### Task 2.4: Throttle the narrate endpoint

`POST /search-runs/<name>/narrate` triggers a paid Anthropic call, unthrottled. One in-process cooldown is enough for a single-user app.

**Files:**
- Modify: `cfb_system_maker/web.py` (narrate route)
- Test: `tests/test_web.py`

- [ ] **Step 1: Failing test**

```python
def test_narrate_is_rate_limited(client_with_search_run, monkeypatch):
    monkeypatch.setattr("cfb_system_maker.web.narrate_run", lambda *a, **k: "text")
    first = client_with_search_run.post("/search-runs/run1/narrate")
    assert first.status_code == 200
    second = client_with_search_run.post("/search-runs/run1/narrate")
    assert second.status_code == 429
    assert second.get_json()["error"] == "rate_limited"
```

(Reuse whatever fixture the existing 6 narrate tests use to have a persisted run on disk.)

- [ ] **Step 2: Implement**

Module level in `web.py`:

```python
_NARRATE_COOLDOWN_S = 30.0
_NARRATE_LAST: dict[str, float] = {"t": 0.0}
```

Top of the narrate route:

```python
now = time.monotonic()
if now - _NARRATE_LAST["t"] < _NARRATE_COOLDOWN_S:
    return jsonify({"error": "rate_limited"}), 429
_NARRATE_LAST["t"] = now
```

Add a `monkeypatch`-reset (`_NARRATE_LAST["t"] = 0.0`) to the existing narrate-test fixture so old tests keep passing.

- [ ] **Step 3: Tests → PASS → commit**

```bash
git add cfb_system_maker/web.py tests/test_web.py
git commit -m "feat(web): 30s cooldown on paid narrate endpoint"
```

### Task 2.5: Security headers

Zero inline scripts/styles exist (verified by survey + `test_dashboard_loads_no_javascript`), so a strict CSP costs nothing and certifies that property forever.

**Files:**
- Modify: `cfb_system_maker/web.py` (extend the after_request from Task 2.1)
- Test: `tests/test_web.py`

- [ ] **Step 1: Failing test**

```python
def test_security_headers_present_on_all_pages(client):
    for path in ("/", "/system", "/compare"):
        resp = client.get(path)
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["Referrer-Policy"] == "same-origin"
        assert resp.headers["Content-Security-Policy"] == "default-src 'self'"
        assert resp.headers["X-Frame-Options"] == "DENY"
```

- [ ] **Step 2: Implement** (inside the existing `_access_log` after_request or a sibling)

```python
response.headers.setdefault("X-Content-Type-Options", "nosniff")
response.headers.setdefault("Referrer-Policy", "same-origin")
response.headers.setdefault("Content-Security-Policy", "default-src 'self'")
response.headers.setdefault("X-Frame-Options", "DENY")
```

- [ ] **Step 3: Full suite** (CSP will break the page if any inline handler slipped in — the suite plus one manual browser pass over dashboard/system/modal/compare catches it) **→ commit**

```bash
git add cfb_system_maker/web.py tests/test_web.py
git commit -m "feat(web): security headers incl. strict same-origin CSP"
```

**Done when (Phase 2):** every request logged with timing; 404/500 are branded pages; copy failures visible; narrate throttled; headers asserted by tests.

---

## Phase 3 — Professional finish

### Task 3.1: Real favicon + page identity

`/favicon.ico` returns 204 — browser tabs show a blank. Professional apps have an identity.

**Files:**
- Create: `cfb_system_maker/static/favicon.svg` (simple football/chart glyph, hand-written SVG, <1 KB)
- Modify: all 5 templates' `<head>` (`index.html`, `dashboard.html`, `compare.html`, `search_run.html`, `error.html`)
- Modify: `cfb_system_maker/web.py` (delete the 204 favicon route — the static file replaces it)
- Test: `tests/test_web.py`

- [ ] **Step 1: Failing test**

```python
def test_pages_link_svg_favicon(client):
    for path in ("/", "/system"):
        assert b'rel="icon"' in client.get(path).data
```

- [ ] **Step 2: Implement**

`static/favicon.svg` (placeholder identity — replace art later without touching code):

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#1a3d2e"/>
  <path d="M6 22 L13 14 L18 18 L26 8" stroke="#e8c547" stroke-width="3" fill="none" stroke-linecap="round"/>
</svg>
```

Each template `<head>`:

```html
<link rel="icon" type="image/svg+xml" href="{{ url_for('static', filename='favicon.svg') }}">
```

Also normalize `<title>` per page: `My Systems — CFB System Maker`, `System Editor — CFB System Maker`, `Compare — CFB System Maker`, `Search Run — CFB System Maker`.

- [ ] **Step 3: Test → PASS → commit**

```bash
git add cfb_system_maker/static/favicon.svg cfb_system_maker/templates cfb_system_maker/web.py tests/test_web.py
git commit -m "feat(web): favicon and per-page titles"
```

### Task 3.2: Empty states

A professional first-run shows guidance, not a bare table. Survey found exactly one saved system and an empty `data/search_runs/` — first-run states are the real states.

**Files:**
- Modify: `cfb_system_maker/templates/dashboard.html` (My Systems tab: zero-systems state pointing at Examples tab + `/system`; Current Matches panel: explicit "No upcoming games loaded — run `python -m cfb_system_maker upcoming`" when `upcoming.csv` is absent, distinct from "no systems match")
- Test: `tests/test_web.py`

- [ ] **Step 1: Failing tests**

```python
def test_dashboard_zero_systems_shows_onboarding(client_empty_systems):
    body = client_empty_systems.get("/").data
    assert b"No saved systems yet" in body
    assert b"Example Systems" in body


def test_current_matches_distinguishes_missing_upcoming_file(client_no_upcoming):
    body = client_no_upcoming.get("/").data
    assert b"No upcoming games loaded" in body
```

(Fixtures: existing dashboard tests already build tmp data dirs — copy that pattern with the systems dir / upcoming.csv omitted. Check first whether some empty-state copy already exists; if so this task narrows to the missing-`upcoming.csv` distinction.)

- [ ] **Step 2: Implement in `dashboard.html` + `styles.css`, test → PASS → commit**

```bash
git add cfb_system_maker/templates/dashboard.html cfb_system_maker/static/styles.css tests/test_web.py
git commit -m "feat(web): first-run empty states for systems list and current matches"
```

### Task 3.3: Analytics-only disclaimer footer

**Files:**
- Create: `cfb_system_maker/templates/_footer.html`
- Modify: `index.html`, `dashboard.html`, `compare.html` (include before `</body>`)
- Test: `tests/test_web.py`

- [ ] **Step 1: Failing test**

```python
def test_disclaimer_footer_on_main_pages(client):
    for path in ("/", "/system", "/compare"):
        assert b"research tool" in client.get(path).data
```

- [ ] **Step 2: Implement**

`templates/_footer.html`:

```html
<footer class="site-footer">
  <p>CFB System Maker is a historical research tool. It does not accept, place, or facilitate
  wagers. Backtested results do not guarantee future performance. If you choose to bet,
  bet responsibly and only where legal.</p>
</footer>
```

Include in the three page templates: `{% include "_footer.html" %}`. Style muted/small in `styles.css`.

- [ ] **Step 3: Test → PASS → commit**

```bash
git add cfb_system_maker/templates cfb_system_maker/static/styles.css tests/test_web.py
git commit -m "feat(web): analytics-only responsible-use footer"
```

### Task 3.4: Browser smoke test (the modal coverage ceiling)

`filter_modal.js` is 1685 lines covered only by source-contract greps (debt register). One Playwright smoke pass over the golden path closes the biggest untested surface.

**Files:**
- Create: `tests/test_browser_smoke.py`
- Modify: `pytest.ini` (the smoke test carries `@pytest.mark.slow` so default runs skip it — `addopts = -m "not slow"` already does this)

**Interfaces:**
- Consumes: `create_app`, real `data/` build.
- Produces: `python -m pytest -m slow tests/test_browser_smoke.py` as the pre-release gate.

- [ ] **Step 1: Write the smoke test**

```python
import threading

import pytest

playwright = pytest.importorskip("playwright.sync_api")


@pytest.mark.slow
def test_editor_modal_golden_path(tmp_path):
    from werkzeug.serving import make_server
    from cfb_system_maker.web import create_app

    app = create_app("data")  # real built data; skip if missing
    server = make_server("127.0.0.1", 5599, app)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        with playwright.sync_playwright() as p:
            page = p.chromium.launch().new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(e))
            page.goto("http://127.0.0.1:5599/system")
            page.click("text=Spread")            # open a filter launcher
            page.wait_for_selector("dialog[open]")
            page.click("dialog >> text=Cancel")
            page.goto("http://127.0.0.1:5599/")
            assert errors == []
    finally:
        server.shutdown()
```

(Selectors above are indicative — read `index.html:503`'s dialog markup and the real launcher labels, then use the actual ones. The assertion that matters: dialog opens, closes, zero uncaught JS errors across editor + dashboard.)

- [ ] **Step 2: Run** `python -m pytest -m slow tests/test_browser_smoke.py -v` → PASS (requires `pip install playwright && playwright install chromium`, dev-only, documented in README, not in requirements.txt).

- [ ] **Step 3: Commit**

```bash
git add tests/test_browser_smoke.py README.md
git commit -m "test: playwright smoke pass over editor modal golden path (slow-marked)"
```

### Task 3.5: README ship rewrite

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite** with exactly these sections: What it is (2 sentences + screenshot of the dashboard), Quick start (clone → venv → `pip install -r requirements.lock` → `env.env` token setup → `sample` → `web`), Full data build (fetch/build/enrich/upcoming command sequence for 2013–2025), Weekly in-season refresh (the 3 commands), Configuration (env vars from Task 1.4, `env.env` format), Development (pytest, slow marker, playwright optional), Disclaimer (same text as footer).

- [ ] **Step 2: Fresh-eyes check**: every command in the README copy-pastes and runs on Windows PowerShell. Take the dashboard screenshot with real data loaded.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/img/dashboard.png
git commit -m "docs: ship-quality README (quick start, data build, config, disclaimer)"
```

### Task 3.6 (OPTIONAL, post-ship): Split `web.py`

1826 lines, 11 routes as closures in one `create_app` — deferred task 14 from the review plan. Not a ship blocker; schedule as its own plan when it next hurts. Target shape when done: `web/__init__.py` (`create_app`, caches), `web/parsing.py` (strict + lenient parsers), `web/charts.py` (`_range_chart`, `_cumulative_chart`, sparklines), `web/routes_dashboard.py`, `web/routes_editor.py`, `web/routes_api.py`. Pure mechanical moves, suite green after every move, no behavior change.

**Done when (Phase 3):** favicon + titles + footer on every page, empty states render, smoke test green, README passes the fresh-eyes check.

---

## Phase 4 — v1.1 Season Readiness (feature work, ~08-29 deadline)

These are product features already specified in `docs/roadmap-v2-2026-08.md` §2 — execute from there; this plan only fixes their order and gates. Run via `/gsd-new-milestone` with roadmap §2 as the requirements seed (the roadmap's own "next formal step").

| Order | Item (roadmap #) | Gate |
|---|---|---|
| 4.1 | Hide Duplicates toggle (1.4) — required correctness now that totals match either side | Before recommending any total-system plays |
| 4.2 | Close T-01-03: `describe()` fallback sentence so no active filter is invisible (1.5) | Before ship — trust bug |
| 4.3 | Bundled example: neutral-site + indoor unders (1.6) | Nice-to-have for ship |
| 4.4 | **Live week-1 verification** (1.3): run `upcoming` pipeline when week-1 lines post; verify Current Matches shows real unplayed games and a feature-filtered system matches via season-to-date stats; record both `human_needed` items closed in `.planning/STATE.md` | The actual "it works in production" moment — ~08-29 |

**Done when:** all four landed/verified; STATE.md deferred-items table cleared of the two verification rows.

---

## Phase 5 — Decision gate: public hosting

**Blocked on user decision — do not start without it.** Everything above ships a professional self-hosted app bound to `127.0.0.1`. Exposing it publicly requires, at minimum:

1. Authentication (single-user password gate — Flask session + `SECRET_KEY` + constant-time compare is enough; no user model needed).
2. A host (small VM or PaaS; waitress behind Caddy/nginx for TLS).
3. Real rate limiting on the JSON endpoints (`/api/backtest`, `/filter-detail` are CPU-heavy; the in-process cache helps but an abuser can vary params).
4. Legal review of the disclaimer for the jurisdictions it would be visible in.
5. Secrets handling: `env.env` replaced by real env vars on the host; Anthropic key optional (narrate degrades to 502 already).

If/when wanted: write `docs/superpowers/plans/<date>-public-hosting.md` covering these five. Until then, the default bind and the same-origin POST check are the security model, and that is fine for a local tool.

---

## Phase 6 — Post-ship milestones (pointer, not a plan)

Sequenced in `docs/roadmap-v2-2026-08.md` §8 — do not re-derive here:

- **v1.2 CLV & Bet Tracking (September, flagship)** — bet-log ingestion, CLV computation/surfaces, live record per system, paper tracking. The analysis arc's conclusion (the measured edge is CLV, not game selection) makes this the product's center of gravity.
- **v1.3 Finance-Grade Results Depth** — max drawdown, holdout chips by default, traffic-light tables, CSV export everywhere, surface `/search-runs/`. Interleaves with v1.2 (disjoint files).
- **v1.4 Weekly Loop** — match alerts, line shopping, teaser records.
- **v1.5 Differentiators** — opportunistic.

Each milestone gets its own detailed plan (per the writing-plans scope rule: one plan per subsystem, each producing working software).

---

## Sequencing & calendar

```
Today (08-26):        Phase 0 (land branch + docs)
08-26 → 08-28:        Phase 1 (installable) → Phase 2 (hardening) → Phase 3.1-3.3, 3.5
~08-29 (week 1):      Phase 4.4 live verification; Phase 3.4 smoke test against live data
Week of 09-01:        Phase 4.1-4.3 if not already landed; declare v1.1 shipped
September:            Phase 6 (v1.2 CLV flagship), Phase 3.6 split when convenient
Whenever decided:     Phase 5 (public hosting) — gated
```

## Ship checklist (the definition of "shipped")

- [ ] Master contains the review branch; suite green (~435+ tests).
- [ ] Fresh clone → install → run works, verified in a throwaway clone.
- [ ] Served by waitress; no dev-server warning; env-var config documented.
- [ ] Access logs, branded 404/500, copy-failure banner, narrate cooldown, security headers.
- [ ] Favicon, titles, disclaimer footer, empty states.
- [ ] README quick start passes fresh-eyes copy-paste test.
- [ ] Hide Duplicates + T-01-03 fixed (trust/correctness).
- [ ] Week-1 live verification of Current Matches recorded in STATE.md.
- [ ] Playwright smoke test green against real data.
