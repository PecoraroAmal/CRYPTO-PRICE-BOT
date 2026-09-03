import time

import requests

import db
from config import COINGECKO_API_KEY, COINGECKO_BASE_URL, PRICE_CACHE_SECONDS

_cache: dict = {"timestamp": 0.0, "ids": frozenset(), "prices": {}}
_session = requests.Session()


def fetch_prices(ids: list[str]) -> dict:
    """Chiamata batch autenticata (API key), usata dal job periodico.
    Consuma quota mensile: incrementa il contatore in SQLite."""
    response = _session.get(
        f"{COINGECKO_BASE_URL}/simple/price",
        params={
            "ids": ",".join(ids),
            "vs_currencies": "usd,eur",
            "x_cg_demo_api_key": COINGECKO_API_KEY,
        },
        timeout=10,
    )
    response.raise_for_status()
    db.increment_api_usage()
    prices = response.json()
    _cache["timestamp"] = time.time()
    _cache["ids"] = frozenset(ids)
    _cache["prices"] = prices
    return prices


def fetch_prices_public(ids: list[str]) -> dict:
    """Chiamata batch anonima (nessuna API key), usata per le richieste
    on-demand dell'utente (/prezzo, creazione alert). Non consuma la quota
    mensile della API key: rate limit più basso ma indipendente."""
    response = _session.get(
        f"{COINGECKO_BASE_URL}/simple/price",
        params={
            "ids": ",".join(ids),
            "vs_currencies": "usd,eur",
        },
        timeout=10,
    )
    response.raise_for_status()
    prices = response.json()
    _cache["timestamp"] = time.time()
    _cache["ids"] = frozenset(ids)
    _cache["prices"] = prices
    return prices


def get_prices_cached(ids: list[str]) -> dict:
    """Usato dai comandi on-demand: riusa l'ultimo fetch se entro
    PRICE_CACHE_SECONDS e copriva lo stesso set di ids, altrimenti fa una
    chiamata pubblica fresca (senza consumare la quota della API key)."""
    now = time.time()
    if (
        now - _cache["timestamp"] < PRICE_CACHE_SECONDS
        and frozenset(ids) <= _cache["ids"]
    ):
        return _cache["prices"]
    return fetch_prices_public(ids)
