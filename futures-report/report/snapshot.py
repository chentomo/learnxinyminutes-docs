"""用 Playwright（無頭 Chromium）把 HTML 報表截成 PNG。"""
from __future__ import annotations

import os
from pathlib import Path


def html_to_png(html_path: Path, png_path: Path, width: int = 1408) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # CHROMIUM_PATH 可指定現有的 Chromium，免執行 playwright install
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=2)
        page.goto(html_path.resolve().as_uri())
        page.wait_for_function("window.__reportReady === true", timeout=15_000)
        page.screenshot(path=str(png_path), full_page=True)
        browser.close()
