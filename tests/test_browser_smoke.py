import threading

import pytest

playwright = pytest.importorskip("playwright.sync_api")


@pytest.mark.slow
def test_editor_modal_golden_path():
    import os

    from werkzeug.serving import make_server

    from cfb_system_maker.web import create_app

    from cfb_paths import DATA_ROOT

    if not (DATA_ROOT / "processed" / "games.csv").exists():
        pytest.skip("requires a built data root (run `sample` or the fetch/build pipeline first)")

    app = create_app(DATA_ROOT)
    server = make_server("127.0.0.1", 5599, app)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(e))
            page.goto("http://127.0.0.1:5599/system")
            page.click("button.filter-launcher")  # opens the first filter's modal (Season)
            page.wait_for_selector("dialog#filter-modal[open]")
            # Wait for the async draft-metrics fetch to actually populate the modal
            # (per-value Record/ROI/Money table), not just for the <dialog> to open --
            # opening is synchronous and would let this test pass without exercising
            # the JS that fetches and renders the table. (Note: page.wait_for_function
            # can't be used here -- the app's own CSP (default-src 'self', no
            # unsafe-eval) blocks Playwright's eval-based polling.)
            page.wait_for_selector("#filter-modal-controls table.filter-modal__table")
            page.click("#filter-modal-close")  # header close (X); discards draft, same as #filter-modal-cancel
            page.goto("http://127.0.0.1:5599/")
            browser.close()
        assert errors == []
    finally:
        server.shutdown()
