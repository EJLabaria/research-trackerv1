"""
wake_app.py

Visits the Streamlit dashboard using a real headless browser (not just a
simple HTTP request) and clicks "Yes, get this app back up!" if the app
is asleep. A plain HTTP request doesn't work here -- Streamlit's sleeping
page returns a normal-looking 200 response, but the actual app never
starts unless a real browser loads the page and establishes a live
connection to it.

Run automatically on a schedule via GitHub Actions (see
.github/workflows/wake-streamlit.yml) -- no local machine or manual step
needed once it's set up.
"""

import os
import sys

from playwright.sync_api import sync_playwright

STREAMLIT_URL = os.environ.get("STREAMLIT_URL", "REPLACE_WITH_YOUR_STREAMLIT_URL")


def main():
    if "REPLACE_WITH_YOUR_STREAMLIT_URL" in STREAMLIT_URL:
        print("[error] STREAMLIT_URL not set -- add it as a GitHub Actions secret or environment variable")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        print(f"Visiting {STREAMLIT_URL} ...")
        page.goto(STREAMLIT_URL, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(5_000)  # give the page a moment to render fully

        wake_button = page.get_by_role("button", name="Yes, get this app back up!")

        if wake_button.count() > 0:
            print("App was asleep -- clicking wake-up button")
            wake_button.click()
            page.wait_for_timeout(60_000)  # give the app time to actually spin up
            print("Done -- app should be awake now")
        else:
            print("App was already awake -- nothing to do")

        browser.close()


if __name__ == "__main__":
    main()