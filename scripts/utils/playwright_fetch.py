# playwright_fetch.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError  # type: ignore
except ModuleNotFoundError as e:  # pragma: no cover
    raise ImportError(
        "playwright is required for browser fallback. "
        "Install with: poetry add playwright && poetry run playwright install chromium"
    ) from e


@dataclass(slots=True)
class BrowserFetchResult:
    url: str
    status: Optional[int]
    html: Optional[str]


def fetch_html_with_playwright(
    url: str,
    *,
    timeout_ms: int = 25_000,
    wait_until: str = "domcontentloaded",  # "load" | "domcontentloaded" | "networkidle"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    locale: str = "en-AU",
    block_images: bool = True,
) -> BrowserFetchResult:
    url = (url or "").strip()
    if not url:
        return BrowserFetchResult(url="", status=None, html=None)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=user_agent,
            locale=locale,
            viewport={"width": 1365, "height": 900},
        )

        if block_images:
            context.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"image", "media", "font"}
                else route.continue_(),
            )

        page = context.new_page()

        try:
            resp = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            status = resp.status if resp else None
            html = page.content()
        except PWTimeoutError:
            status = None
            html = page.content()  # best-effort
        finally:
            context.close()
            browser.close()

    html_out = html if html and html.strip() else None
    return BrowserFetchResult(url=url, status=status, html=html_out)
