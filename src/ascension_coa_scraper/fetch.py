"""HTTP access to ascension.gg, with an optional on-disk cache.

Everything this scraper needs is a plain GET: the builder page, the sprite sheet CSS,
and the sprite sheet itself. No browser automation, no authentication.

The cache exists so repeated runs during development do not re-download the ~12 MB
builder page and ~6 MB sprite sheet. It is keyed by URL and never expires on its own;
delete the directory (or pass ``--no-cache``) to force a refresh.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urljoin

import httpx

from . import __version__

BASE_URL = "https://ascension.gg"
BUILDER_PATH = "/en/v2/coa-builder/{realm}"
DEFAULT_REALM = "voljin"

# Identify the client honestly so the operators can see who is calling and why.
USER_AGENT = (
    f"ascension-coa-scraper/{__version__} "
    "(+https://github.com/v1cferr/ascension-coa-scraper)"
)


class FetchError(RuntimeError):
    """Raised when a resource cannot be retrieved."""


class Fetcher:
    """Small HTTP client wrapper with retries and an optional on-disk cache."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        cache_dir: Path | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_dir = cache_dir
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            transport=httpx.HTTPTransport(retries=2),
        )

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def resolve(self, path_or_url: str) -> str:
        """Turn a site-relative path into an absolute URL; pass absolute URLs through."""
        if path_or_url.startswith(("http://", "https://")):
            return path_or_url
        return urljoin(f"{self.base_url}/", path_or_url.lstrip("/"))

    def get_bytes(self, path_or_url: str) -> bytes:
        url = self.resolve(path_or_url)
        cached = self._cache_path(url)

        if cached is not None and cached.exists():
            return cached.read_bytes()

        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FetchError(f"failed to fetch {url}: {exc}") from exc

        payload = response.content
        if cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(payload)
        return payload

    def get_text(self, path_or_url: str) -> str:
        return self.get_bytes(path_or_url).decode("utf-8", "replace")

    def builder_page(self, realm: str = DEFAULT_REALM) -> str:
        """Fetch the server-rendered CoA builder page for a realm slug."""
        return self.get_text(BUILDER_PATH.format(realm=realm))

    def builder_url(self, realm: str = DEFAULT_REALM) -> str:
        return self.resolve(BUILDER_PATH.format(realm=realm))

    def _cache_path(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        suffix = Path(httpx.URL(url).path).suffix or ".bin"
        return self.cache_dir / f"{digest}{suffix}"
