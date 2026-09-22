import json
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import Settings


@dataclass(slots=True)
class WebsiteHit:
    title: str
    url: str
    text: str


class PageTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


class OfficialWebsiteSearch:
    """Bounded same-origin search for the configured official WordPress site."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def _same_origin(self, url: str) -> bool:
        if not self.settings.official_website_url:
            return False
        expected = urlparse(str(self.settings.official_website_url))
        candidate = urlparse(url)
        return (
            candidate.scheme in {"http", "https"}
            and candidate.scheme == expected.scheme
            and candidate.hostname == expected.hostname
            and candidate.port == expected.port
            and not candidate.username
            and not candidate.password
        )

    async def _read(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> tuple[bytes, str] | None:
        current = url
        current_params = params
        for _ in range(4):
            if not self._same_origin(current):
                return None
            async with client.stream("GET", current, params=current_params, follow_redirects=False) as response:
                current_params = None
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        return None
                    current = urljoin(str(response.url), location)
                    continue
                if response.status_code != 200:
                    return None
                declared = response.headers.get("content-length")
                if declared and int(declared) > self.settings.website_search_max_bytes:
                    return None
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self.settings.website_search_max_bytes:
                        return None
                return bytes(body), str(response.url)
        return None

    async def search(self, query: str, limit: int = 3) -> list[WebsiteHit]:
        if not self.settings.official_website_url or not query.strip():
            return []
        base = str(self.settings.official_website_url).rstrip("/") + "/"
        search_url = urljoin(base, "wp-json/wp/v2/search")
        timeout = httpx.Timeout(self.settings.website_search_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
                response = await self._read(
                    client,
                    search_url,
                    params={"search": query[:200], "per_page": min(max(limit, 1), 5)},
                )
                if not response:
                    return []
                payload = json.loads(response[0])
                if not isinstance(payload, list):
                    return []
                hits: list[WebsiteHit] = []
                for item in payload[:limit]:
                    if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                        continue
                    page = await self._read(client, item["url"])
                    if not page:
                        continue
                    extractor = PageTextExtractor()
                    extractor.feed(page[0].decode("utf-8", errors="ignore"))
                    text = extractor.text()
                    if not text:
                        continue
                    title = item.get("title") if isinstance(item.get("title"), str) else "Official CIET website"
                    hits.append(WebsiteHit(title=unescape(title), url=page[1], text=text))
                return hits
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeError, ValueError):
            return []
