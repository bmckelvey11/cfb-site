import threading

import pytest

playwright = pytest.importorskip("playwright.sync_api")


@pytest.mark.slow
def test_editor_modal_golden_path():
    import os

    from werkzeug.serving import make_server

    from cfb_system_maker.web import create_app

    if not os.path.exists("data/processed/games.csv"):
        pytest.skip("requires a built data/ directory (run `sample` or the fetch/build pipeline first)")

    app = create_app("data")
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
            page.click("#filter-modal-close")  # header close (X); discards draft, same as #filter-modal-cancel
            page.goto("http://127.0.0.1:5599/")
            browser.close()
        assert errors == []
    finally:
        server.shutdown()
