import html
import re

import httpx

from .models import Floorplan, Provider


def _clean_text(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_response_text(response: httpx.Response) -> str:
    charset = response.charset_encoding or "utf-8"
    return response.content.decode(charset, errors="ignore")


def _trim_cottages_name(full_name: str) -> str:
    return re.sub(r"^\d+x\d+(?:\.\d+)?\s*-\s*", "", full_name).strip()


def _parse_layout(details_text: str) -> tuple[str, str, str]:
    match = re.search(
        r"(?P<beds>\d+)\s*Bed\s*\|\s*(?P<baths>\d+(?:\.\d+)?)\s*Bath\s*\|\s*(?P<sq_ft>\d+)?\s*Sq\s*Ft",
        details_text,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("Could not parse floorplan details.")
    return (
        match.group("beds"),
        match.group("baths"),
        match.group("sq_ft") or "N/A",
    )


def parse_cottages_floorplans(page_html: str) -> list[Floorplan]:
    pattern = re.compile(
        r'<h2 class="floorplan__name">(?P<name>.*?)</h2>.*?'
        r'<div class="floorplan__details">(?P<details>.*?)</div>.*?'
        r'<span class="floorplan__price--label">Installments Starting At:</span>.*?'
        r'<span class="floorplan__price--value">\s*(?P<price>\$[\d,]+(?:\.\d{2})?)\s*</span>',
        re.DOTALL,
    )
    floorplans: list[Floorplan] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    for match in pattern.finditer(page_html):
        name = _trim_cottages_name(_clean_text(match.group("name")))
        price = _clean_text(match.group("price"))
        beds, baths, sq_ft = _parse_layout(_clean_text(match.group("details")))
        item = (name, price, beds, baths, sq_ft)
        if item in seen:
            continue
        seen.add(item)
        floorplans.append(
            Floorplan(
                name=name,
                price=price,
                beds=beds,
                baths=baths,
                sq_ft=sq_ft,
            )
        )

    floorplans.sort(
        key=lambda item: (int(item.beds), float(item.baths), item.name, item.price)
    )
    return floorplans


async def fetch_cottages_floorplans(
    client: httpx.AsyncClient, url: str
) -> list[Floorplan]:
    response = await client.get(url)
    response.raise_for_status()
    floorplans = parse_cottages_floorplans(_parse_response_text(response))
    if not floorplans:
        raise ValueError("No floor plans were parsed from the provider page.")
    return floorplans


COTTAGES_PROVIDER = Provider(
    key="cottages",
    display_name="The Cottages",
    aliases=("cottages", "thecottages", "the cottages"),
    url="https://thecottagesillinois.com/floorplans/",
    fetcher=fetch_cottages_floorplans,
)
