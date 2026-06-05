"""Handles pagination on Doctoralia search results pages."""

import logging
from config import MAX_PAGES

logger = logging.getLogger(__name__)

_NEXT_SELECTORS = [
    "a[aria-label='next']",
    "a[rel='next']",
    "li.next > a",
    "a.next",
    "[data-testid='pagination-next']",
    "a[title='Próximo']",
    "a[title='Próxima página']",
    "nav[aria-label='pagination'] li:last-child a",
]

_BLOCKED_URL_PATTERNS = ["/login", "/captcha", "/bloqueado", "/blocked", "/verify"]
_BLOCKED_TITLE_PATTERNS = ["captcha", "access denied", "bot detected", "verificação"]


class PaginationHandler:
    """Detects and navigates paginated search results safely."""

    def __init__(self, page, max_pages: int = MAX_PAGES) -> None:
        self._page = page
        self._max_pages = max_pages
        self._current_page: int = 1
        self._block_count: int = 0

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def block_count(self) -> int:
        return self._block_count

    async def has_next_page(self) -> bool:
        """Return True if a usable 'next page' link exists."""
        if self._current_page >= self._max_pages:
            logger.info("Page limit reached (%d).", self._max_pages)
            return False

        for sel in _NEXT_SELECTORS:
            try:
                elem = await self._page.query_selector(sel)
                if not elem:
                    continue
                aria_disabled = await elem.get_attribute("aria-disabled")
                class_attr = (await elem.get_attribute("class")) or ""
                if aria_disabled == "true" or "disabled" in class_attr:
                    return False
                if await elem.is_visible():
                    return True
            except Exception:
                continue

        return False

    async def go_to_next_page(self) -> bool:
        """Click the next-page button and wait for new results to load."""
        for sel in _NEXT_SELECTORS:
            try:
                elem = await self._page.query_selector(sel)
                if not elem or not await elem.is_visible():
                    continue

                await elem.click()
                try:
                    await self._page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass

                self._current_page += 1
                logger.info("Navigated to page %d.", self._current_page)

                if await self._is_blocked():
                    logger.warning("Block/captcha detected after pagination.")
                    self._block_count += 1
                    return False

                return True
            except Exception as exc:
                logger.debug("Next-page click failed with '%s': %s", sel, exc)
                continue

        return False

    async def _is_blocked(self) -> bool:
        """Detect captcha or login-wall redirects."""
        url: str = self._page.url
        for pattern in _BLOCKED_URL_PATTERNS:
            if pattern in url:
                return True

        try:
            title: str = await self._page.title()
            for pattern in _BLOCKED_TITLE_PATTERNS:
                if pattern in title.lower():
                    return True
        except Exception:
            pass

        return False
