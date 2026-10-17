"""Renders a page in a headless browser and returns its text and a screenshot."""
import re
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

import config

CAPTCHA_MARKERS = re.compile(
    r"captcha|are you a robot|verify you are human|unusual traffic|access denied|"
    r"checking your browser|attention required|just a moment",
    re.I,
)


@dataclass
class FetchResult:
    status_code: int
    final_url: str
    title: str
    text: str
    screenshot: bytes


class FetchFailed(Exception):
    """Page could not be loaded at all (timeout, DNS, connection refused)."""


def fetch_page(url: str, timeout_s: int = config.FETCH_TIMEOUT_S) -> FetchResult:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=config.USER_AGENT,
            )
            page = ctx.new_page()
            page.set_default_timeout(timeout_s * 1000)
            try:
                resp = page.goto(url, wait_until="domcontentloaded")
                try:  # give scripts a moment, but never wait forever
                    page.wait_for_load_state("networkidle", timeout=8000)
                except PlaywrightTimeout:
                    pass
                return FetchResult(
                    status_code=resp.status if resp else 0,
                    final_url=page.url,
                    title=page.title(),
                    text=page.inner_text("body"),
                    screenshot=page.screenshot(full_page=True),
                )
            except PlaywrightTimeout:
                raise FetchFailed(f"Timed out after {timeout_s}s")
            except PlaywrightError as e:
                raise FetchFailed(str(e).splitlines()[0][:200])
        finally:
            browser.close()


def classify(result: FetchResult) -> tuple[str, str]:
    """Decides if a fetched page is a real page or an outage/CAPTCHA.

    Returns (state, reason) where state is 'ok', 'error' or 'blocked'.
    An outage or CAPTCHA is NOT a content change.
    """
    code = result.status_code
    if code >= 500:
        return "error", f"Server error {code}"
    if code in (401, 403, 429):
        return "blocked", f"Blocked with HTTP {code}"
    if code >= 400:
        return "error", f"HTTP {code}"
    head = result.text[:1500]
    if CAPTCHA_MARKERS.search(head) and len(result.text) < 1500:
        return "blocked", "Looks like a CAPTCHA or bot check"
    return "ok", ""
