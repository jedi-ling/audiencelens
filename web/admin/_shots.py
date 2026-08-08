from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://127.0.0.1:4175/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    page.screenshot(path="screenshots/admin-gate.png")
    print("saved admin-gate")
    page.close()
    browser.close()
