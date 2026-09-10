from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from urllib.parse import urlparse

import aiohttp

LOG = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchPolicy:
    concurrency: int = 20
    per_host: int = 4
    attempts: int = 5
    timeout_seconds: int = 30
    base_backoff_seconds: float = 1.0


class AsyncHttpClient:
    """Bounded, polite client with retryable 429/5xx handling and jitter."""

    def __init__(self, policy: FetchPolicy = FetchPolicy()) -> None:
        self.policy = policy
        self._semaphore = asyncio.Semaphore(policy.concurrency)
        self._host_semaphores: dict[str, asyncio.Semaphore] = {}
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "AsyncHttpClient":
        timeout = aiohttp.ClientTimeout(total=self.policy.timeout_seconds)
        self._session = aiohttp.ClientSession(timeout=timeout, headers={
            "User-Agent": "FrontierAtlasResearchBot/0.1 (+https://github.com/your-org/frontier-atlas)"
        })
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._session:
            await self._session.close()

    def _host_limiter(self, url: str) -> asyncio.Semaphore:
        host = urlparse(url).netloc.lower()
        return self._host_semaphores.setdefault(host, asyncio.Semaphore(self.policy.per_host))

    async def get_text(self, url: str, *, accept: str = "text/html,application/xml;q=0.9,*/*;q=0.8") -> str:
        if not self._session:
            raise RuntimeError("Use AsyncHttpClient as an async context manager")
        for attempt in range(self.policy.attempts):
            try:
                async with self._semaphore, self._host_limiter(url):
                    async with self._session.get(url, headers={"Accept": accept}, allow_redirects=True) as response:
                        if response.status == 413:
                            raise FetchError(f"413 from {url}; request input must be chunked before sending")
                        if response.status == 429 or response.status >= 500:
                            retry_after = response.headers.get("Retry-After")
                            delay = float(retry_after) if retry_after and retry_after.isdigit() else self._delay(attempt)
                            LOG.warning("Retryable HTTP %s from %s; sleeping %.1fs", response.status, url, delay)
                            await asyncio.sleep(delay)
                            continue
                        if response.status >= 400:
                            raise FetchError(f"HTTP {response.status} from {url}")
                        return await response.text()
            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                if attempt == self.policy.attempts - 1:
                    raise FetchError(f"Request failed for {url}: {error}") from error
                delay = self._delay(attempt)
                LOG.warning("Request error for %s: %s; retrying in %.1fs", url, error, delay)
                await asyncio.sleep(delay)
        raise FetchError(f"Retries exhausted for {url}")

    def _delay(self, attempt: int) -> float:
        return min(60.0, self.policy.base_backoff_seconds * (2 ** attempt)) + random.uniform(0, 0.75)
