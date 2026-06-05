"""Async rate limiter to prevent IP blocking during scraping."""

import asyncio
import random
from config import REQUEST_DELAY_MIN, REQUEST_DELAY_MAX


class RateLimiter:
    """Controls request frequency with randomized async delays."""

    async def sleep_random(self) -> None:
        """Wait a random time between general requests."""
        await asyncio.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

    async def sleep_between_profiles(self) -> None:
        """Wait slightly longer between individual profile page visits."""
        await asyncio.sleep(random.uniform(3.0, 7.0))

    async def sleep_between_pages(self) -> None:
        """Wait between pagination transitions."""
        await asyncio.sleep(random.uniform(2.0, 4.0))

    async def sleep_on_error(self) -> None:
        """Wait longer after encountering an error."""
        await asyncio.sleep(random.uniform(10.0, 20.0))

    async def sleep_on_block(self) -> None:
        """Wait a full minute when the site temporarily blocks the IP."""
        await asyncio.sleep(60.0)

    async def sleep_extended_block(self) -> None:
        """Wait 5 minutes after 3 consecutive blocks."""
        await asyncio.sleep(300.0)
