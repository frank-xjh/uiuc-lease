from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx


@dataclass(frozen=True)
class Floorplan:
    name: str
    price: str
    beds: str
    baths: str
    sq_ft: str


@dataclass(frozen=True)
class Provider:
    key: str
    display_name: str
    aliases: tuple[str, ...]
    url: str
    fetcher: Callable[[httpx.AsyncClient, str], Awaitable[list[Floorplan]]]
