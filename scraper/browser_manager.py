"""Playwright browser manager with anti-detection measures."""

import asyncio
import logging
import random
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)

_VIEWPORTS = [
    {"width": 1280, "height": 720},
    {"width": 1366, "height": 768},
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
]

_JS_HIDE_WEBDRIVER = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
"""

_CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-infobars",
    "--disable-extensions",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-webrtc",
    "--disable-rtc-smoothness-algorithm",
]

_MODAL_SELECTORS = [
    "button[aria-label='Close']",
    "button[aria-label='Fechar']",
    ".modal-close",
    "[data-testid='modal-close']",
    "[data-dismiss='modal']",
    "button.close",
    ".overlay-close",
    "[class*='CloseButton']",
    "[class*='close-button']",
]

_COOKIE_SELECTORS = [
    "button[id*='accept']",
    "button[class*='accept']",
    "button[class*='cookie']",
    "button[aria-label='Accept']",
    "[data-testid='cookie-accept']",
    "#onetrust-accept-btn-handler",
    ".cc-accept",
]


class BrowserInitError(Exception):
    """Raised when the browser cannot be initialised."""


class BrowserManager:
    """Manages a Playwright Chromium browser with anti-fingerprinting settings."""

    def __init__(self, headless: bool = True, debug: bool = False) -> None:
        self.headless = headless
        self.debug = debug
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self) -> None:
        """Start Playwright; auto-install chromium if missing."""
        try:
            await self._launch()
        except Exception as exc:
            logger.warning("Browser launch failed (%s). Trying to install playwright...", exc)
            _install_playwright()
            try:
                await self._launch()
            except Exception as exc2:
                raise BrowserInitError(
                    f"Browser could not start after installation attempt: {exc2}"
                ) from exc2

    async def _launch(self) -> None:
        from playwright.async_api import async_playwright

        try:
            from fake_useragent import UserAgent
            ua = UserAgent()
            user_agent: str = ua.random
        except Exception:
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )

        viewport = random.choice(_VIEWPORTS)

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=_CHROMIUM_ARGS,
        )
        self._context = await self._browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            ignore_https_errors=True,
            java_script_enabled=True,
        )
        await self._context.add_init_script(_JS_HIDE_WEBDRIVER)

        self._page = await self._context.new_page()

        from config import TIMEOUT
        self._page.set_default_timeout(TIMEOUT)

        logger.info(
            "Browser started — headless=%s, UA=%.60s…, viewport=%s",
            self.headless,
            user_agent,
            viewport,
        )

    async def accept_cookies(self) -> None:
        """Dismiss cookie consent banners if present."""
        for sel in _COOKIE_SELECTORS:
            try:
                btn = await self._page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    logger.debug("Accepted cookies via: %s", sel)
                    return
            except Exception:
                continue

    async def close_modals(self) -> None:
        """Close any popup / app-download modals blocking the page."""
        for sel in _MODAL_SELECTORS:
            try:
                btn = await self._page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.3)
                    logger.debug("Closed modal via: %s", sel)
                    return
            except Exception:
                continue

    @property
    def page(self):
        return self._page

    async def close(self) -> None:
        """Gracefully close browser and Playwright."""
        for obj, method in [
            (self._context, "close"),
            (self._browser, "close"),
            (self._playwright, "stop"),
        ]:
            if obj is not None:
                try:
                    await getattr(obj, method)()
                except Exception as exc:
                    logger.debug("Cleanup warning: %s", exc)

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await self.close()
        return False


def _install_playwright() -> None:
    """Run `playwright install chromium` via subprocess."""
    logger.info("Running: playwright install chromium")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("playwright install failed:\n%s", result.stderr)
    else:
        logger.info("Playwright chromium installed successfully.")
