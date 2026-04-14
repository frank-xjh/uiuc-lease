import re
import time

import httpx
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .cottages import COTTAGES_PROVIDER
from .models import Floorplan, Provider


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"
)
CACHE_TTL_SECONDS = 900


def _normalize_provider_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _format_price_display(price: str) -> str:
    return price.removeprefix("$") + "🔪"


@register(
    "lease_price", "frank", "Show UIUC lease prices for supported landlords.", "1.0.0"
)
class LeasePricePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._providers = self._build_provider_registry()
        self._cache: dict[str, tuple[float, list[Floorplan]]] = {}

    async def initialize(self):
        """Initialize the plugin state."""

    @staticmethod
    def _build_provider_registry() -> dict[str, Provider]:
        providers = [COTTAGES_PROVIDER]
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

    def _get_cached_prices(self, provider: Provider) -> list[Floorplan] | None:
        cached = self._cache.get(provider.key)
        if not cached:
            return None
        cached_at, prices = cached
        if time.time() - cached_at > CACHE_TTL_SECONDS:
            self._cache.pop(provider.key, None)
            return None
        return prices

    async def _fetch_provider_prices(self, provider: Provider) -> list[Floorplan]:
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

    def _format_prices(self, provider: Provider, prices: list[Floorplan]) -> str:
        lines = [f"{provider.display_name}:", ""]
        for item in prices:
            lines.append(item.name)
            lines.append("")
            lines.append(
                f"{item.beds} BED {item.baths} BATH {_format_price_display(item.price)} {item.sq_ft} SQ FT"
            )
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
