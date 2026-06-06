from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from backend.avm_model import CompsItem, MARKETS, MarketProfile


@dataclass(frozen=True)
class CompsPackage:
    market: MarketProfile
    comps: list[CompsItem]
    trend: str
    source: str
    mode: str


class CompsRepository:
    def __init__(self) -> None:
        self._fixture_path = (
            Path(__file__).resolve().parent.parent / "data" / "demo_fixture.json"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_market(self, address: str) -> MarketProfile:
        normalized = address.lower()
        for key, profile in MARKETS.items():
            if key in normalized:
                return profile
        return MarketProfile(
            "Default Metro", 560_000, 520_000, 610_000, 0.76,
            "+1.2% over 3 months", "ATTOM fixture data"
        )

    def fetch(self, address: str) -> CompsPackage:
        market = self.detect_market(address)
        live = self._fetch_live(address, market)
        if live is not None:
            return live
        return self._load_fixture(market)

    # ------------------------------------------------------------------
    # Live path – RealEstateAPI PropertyComps endpoint
    # ------------------------------------------------------------------

    def _fetch_live(self, address: str, market: MarketProfile) -> CompsPackage | None:
        api_key = os.getenv("REALESTATE_API_KEY", "").strip()
        if not api_key:
            return None

        base_url = os.getenv(
            "REALESTATE_API_BASE_URL", "https://api.realestateapi.com"
        ).rstrip("/")

        # --- Try Property Comps first (preferred) ---
        package = self._call_comps_endpoint(address, market, api_key, base_url)
        if package is not None:
            return package

        # --- Fallback: PropertySearch (returns estimated values) ---
        return self._call_search_endpoint(address, market, api_key, base_url)

    def _call_comps_endpoint(
        self,
        address: str,
        market: MarketProfile,
        api_key: str,
        base_url: str,
    ) -> CompsPackage | None:
        try:
            response = httpx.post(
                f"{base_url}/v2/PropertyComps",
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={"address": address, "radius": 1.0, "limit": 6},
                timeout=12.0,
            )
            response.raise_for_status()
            payload = response.json()

            # API may return {"result": [...]} or {"data": [...]} or a bare list
            items = (
                payload.get("result")
                or payload.get("data")
                or (payload if isinstance(payload, list) else [])
            )

            comps = [self._parse_comp(item, market) for item in items[:6]]
            comps = [c for c in comps if c is not None]

            if not comps:
                return None

            return CompsPackage(
                market=market,
                comps=comps,
                trend=market.trend,
                source="RealEstateAPI-Comps",
                mode="live-comps",
            )

        except Exception as exc:
            print(f"[CompsRepository] PropertyComps error: {exc}")
            return None

    def _call_search_endpoint(
        self,
        address: str,
        market: MarketProfile,
        api_key: str,
        base_url: str,
    ) -> CompsPackage | None:
        try:
            response = httpx.get(
                f"{base_url}/v2/PropertySearch",
                headers={
                    "x-api-key": api_key,
                    "Accept": "application/json",
                },
                params={"address": address},
                timeout=12.0,
            )
            response.raise_for_status()
            payload = response.json()

            items = (
                payload.get("result")
                or payload.get("data")
                or (payload if isinstance(payload, list) else [])
            )

            comps = [self._parse_search_item(item, market) for item in items[:6]]
            comps = [c for c in comps if c is not None]

            if not comps:
                return None

            return CompsPackage(
                market=market,
                comps=comps,
                trend=market.trend,
                source="RealEstateAPI-Search",
                mode="live-search",
            )

        except Exception as exc:
            print(f"[CompsRepository] PropertySearch error: {exc}")
            return None

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _parse_comp(self, item: dict, market: MarketProfile) -> CompsItem | None:
        try:
            sale_price = int(
                item.get("lastSalePrice")
                or item.get("salePrice")
                or item.get("estimatedValue")
                or market.base_price
            )
            if sale_price <= 0:
                return None

            sold_days_ago = self._days_ago(
                item.get("lastSaleDate") or item.get("saleDate")
            )

            return CompsItem(
                address=item.get("address") or item.get("formattedAddress") or "Unknown",
                sale_price=sale_price,
                sqft=int(item.get("squareFootage") or item.get("livingSquareFeet") or 0),
                beds=float(item.get("bedrooms") or item.get("bedroomsTotal") or 0),
                baths=float(item.get("bathrooms") or item.get("bathroomsTotal") or 0),
                sold_days_ago=sold_days_ago,
            )
        except Exception:
            return None

    def _parse_search_item(self, item: dict, market: MarketProfile) -> CompsItem | None:
        try:
            price = int(
                item.get("estimatedValue")
                or item.get("lastSalePrice")
                or market.base_price
            )
            if price <= 0:
                return None

            return CompsItem(
                address=item.get("address") or "Unknown",
                sale_price=price,
                sqft=int(item.get("squareFootage") or 0),
                beds=float(item.get("bedrooms") or 0),
                baths=float(item.get("bathrooms") or 0),
                sold_days_ago=self._days_ago(item.get("lastSaleDate")),
            )
        except Exception:
            return None

    @staticmethod
    def _days_ago(date_str: str | None) -> int:
        if not date_str:
            return 45   # sensible default
        try:
            sale_date = date.fromisoformat(str(date_str)[:10])
            return max(0, (date.today() - sale_date).days)
        except (ValueError, TypeError):
            return 45

    # ------------------------------------------------------------------
    # Fixture fallback
    # ------------------------------------------------------------------

    def _load_fixture(self, market: MarketProfile) -> CompsPackage:
        payload = json.loads(self._fixture_path.read_text(encoding="utf-8"))
        market_payload = payload.get(market.label) or next(iter(payload.values()))
        comps = [CompsItem(**item) for item in market_payload["comps"]]
        trend  = market_payload.get("trend",  market.trend)
        source = market_payload.get("source", market.source)
        return CompsPackage(
            market=market, comps=comps, trend=trend, source=source, mode="fixture"
        )