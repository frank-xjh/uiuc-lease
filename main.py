import html
import re
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"
)
CACHE_TTL_SECONDS = 900


@dataclass(frozen=True)
class FloorplanPrice:
    plan_name: str
    layout_text: str
    starting_price: str


@dataclass(frozen=True)
class Provider:
    key: str
    display_name: str
    aliases: tuple[str, ...]
    url: str
    fetcher: Callable[[httpx.AsyncClient, str], Awaitable[list[FloorplanPrice]]]


def _clean_text(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_provider_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _extract_layout_text(details_text: str) -> str:
    match = re.search(
        r"(?P<beds>\d+)\s*Bed\s*\|\s*(?P<baths>\d+(?:\.\d+)?)\s*Bath",
        details_text,
        re.IGNORECASE,
    )
    if not match:
        return details_text
    return f"{match.group('beds')} BED {match.group('baths')} BATH"


def _parse_cottages_floorplans(page_html: str) -> list[FloorplanPrice]:
    pattern = re.compile(
        r'<h2 class="floorplan__name">(?P<name>.*?)</h2>.*?'
        r'<div class="floorplan__details">(?P<details>.*?)</div>.*?'
        r'<span class="floorplan__price--label">Installments Starting At:</span>.*?'
        r'<span class="floorplan__price--value">\s*(?P<price>\$[\d,]+(?:\.\d{2})?)\s*</span>',
        re.DOTALL,
    )
    floorplans: list[FloorplanPrice] = []
    seen: set[tuple[str, str, str]] = set()

    for match in pattern.finditer(page_html):
        full_name = _clean_text(match.group("name"))
        layout_text = _extract_layout_text(_clean_text(match.group("details")))
        price = _clean_text(match.group("price"))
        item = (full_name, layout_text, price)
        if item in seen:
            continue
        seen.add(item)
        floorplans.append(
            FloorplanPrice(
                plan_name=full_name,
                layout_text=layout_text,
                starting_price=price,
            )
        )

    floorplans.sort(
        key=lambda item: (item.layout_text, item.plan_name, item.starting_price)
    )
    return floorplans


def _parse_response_text(response: httpx.Response) -> str:
    charset = response.charset_encoding or "utf-8"
    return response.content.decode(charset, errors="ignore")


async def _fetch_cottages_floorplans(
    client: httpx.AsyncClient, url: str
) -> list[FloorplanPrice]:
    response = await client.get(url)
    response.raise_for_status()
    page_html = _parse_response_text(response)
    floorplans = _parse_cottages_floorplans(page_html)
    if not floorplans:
        raise ValueError("No floor plans were parsed from the provider page.")
    return floorplans


@register(
    "lease_price", "frank", "Show UIUC lease prices for supported landlords.", "1.0.0"
)
class LeasePricePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._providers = self._build_provider_registry()
        self._cache: dict[str, tuple[float, list[FloorplanPrice]]] = {}

    async def initialize(self):
        """Initialize the plugin state."""

    @staticmethod
    def _build_provider_registry() -> dict[str, Provider]:
        providers = [
            Provider(
                key="cottages",
                display_name="The Cottages",
                aliases=("cottages", "thecottages", "the cottages"),
                url="https://thecottagesillinois.com/floorplans/",
                fetcher=_fetch_cottages_floorplans,
            )
        ]
        return {provider.key: provider for provider in providers}

    def _list_supported_providers(self) -> str:
        lines = ["Supported providers:"]
        for provider in sorted(
            self._providers.values(), key=lambda item: item.display_name.lower()
        ):
            aliases = ", ".join(provider.aliases)
            lines.append(f"- {provider.display_name} ({aliases})")
        lines.append("Usage: /price <provider>")
        return "\n".join(lines)

    def _resolve_provider(self, query: str) -> Provider | None:
        normalized_query = _normalize_provider_name(query)
        for provider in self._providers.values():
            names = (provider.key, provider.display_name, *provider.aliases)
            if any(
                _normalize_provider_name(name) == normalized_query for name in names
            ):
                return provider
        return None

    def _parse_provider_query(self, message_text: str) -> str:
        stripped = message_text.strip()
        match = re.match(r"^/?price(?:\s+(?P<provider>.+))?$", stripped, re.IGNORECASE)
        if not match:
            return ""
        return (match.group("provider") or "").strip()

    def _get_cached_prices(self, provider: Provider) -> list[FloorplanPrice] | None:
        cached = self._cache.get(provider.key)
        if not cached:
            return None
        cached_at, prices = cached
        if time.time() - cached_at > CACHE_TTL_SECONDS:
            self._cache.pop(provider.key, None)
            return None
        return prices

    async def _fetch_provider_prices(self, provider: Provider) -> list[FloorplanPrice]:
        cached = self._get_cached_prices(provider)
        if cached is not None:
            return cached

        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            prices = await provider.fetcher(client, provider.url)
        self._cache[provider.key] = (time.time(), prices)
        return prices

    def _format_prices(self, provider: Provider, prices: list[FloorplanPrice]) -> str:
        lines = [f"{provider.display_name}:", ""]
        for item in prices:
            lines.append(item.plan_name)
            lines.append(f"{item.layout_text} {item.starting_price}")
            lines.append("")
        if lines[-1] == "":
            lines.pop()
        return "\n".join(lines)

    @filter.command("price")
    async def price(self, event: AstrMessageEvent):
        """Show supported UIUC lease providers or fetch prices for one provider."""
        provider_query = self._parse_provider_query(event.message_str)
        if not provider_query:
            yield event.plain_result(self._list_supported_providers())
            return

        provider = self._resolve_provider(provider_query)
        if provider is None:
            yield event.plain_result(
                f"Unknown provider: {provider_query}\n{self._list_supported_providers()}"
            )
            return

        try:
            prices = await self._fetch_provider_prices(provider)
        except httpx.HTTPStatusError as exc:
            yield event.plain_result(
                f"Failed to fetch {provider.display_name}: HTTP {exc.response.status_code}."
            )
            return
        except httpx.HTTPError as exc:
            yield event.plain_result(f"Failed to fetch {provider.display_name}: {exc}.")
            return
        except Exception as exc:
            yield event.plain_result(
                f"Failed to parse prices for {provider.display_name}: {exc}"
            )
            return

        yield event.plain_result(self._format_prices(provider, prices))

    async def terminate(self):
        """Clean up plugin state when unloading."""
