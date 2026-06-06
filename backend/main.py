from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.services.comps_repository import CompsRepository
from backend.avm_model import AVMEngine, ValuationResult

app = FastAPI(title="SnapPrice AVM", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_repo   = CompsRepository()
_engine = AVMEngine()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ValuationRequest(BaseModel):
    address: str = Field(..., min_length=5, example="123 Main St, Austin TX")
    sqft:    int   = Field(1800, ge=300,  le=20000)
    beds:    float = Field(3.0,  ge=0,    le=15)
    baths:   float = Field(2.0,  ge=0,    le=15)


class ValuationResponse(BaseModel):
    estimated_value: int
    low_estimate:    int
    high_estimate:   int
    confidence:      float
    price_per_sqft:  float
    adjustments:     dict[str, int]
    explanation:     str
    comps_used:      int
    market_trend:    str
    source:          str
    mode:            str
    market_label:    str
    comps_detail:    list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "SnapPrice AVM"}


@app.post("/api/value", response_model=ValuationResponse)
def get_valuation(req: ValuationRequest) -> ValuationResponse:
    """
    Main AVM endpoint.
    Accepts a property address + features, returns estimated value + explanation.
    """
    try:
        package = _repo.fetch(req.address)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Comps fetch failed: {exc}") from exc

    subject = {"sqft": req.sqft, "beds": req.beds, "baths": req.baths}

    result: ValuationResult = _engine.value(subject, package.comps, package.market)

    comps_detail = [
        {
            "address":       c.address,
            "sale_price":    c.sale_price,
            "sqft":          c.sqft,
            "beds":          c.beds,
            "baths":         c.baths,
            "sold_days_ago": c.sold_days_ago,
        }
        for c in package.comps
    ]

    return ValuationResponse(
        **result.__dict__,
        market_label=package.market.label,
        comps_detail=comps_detail,
    )


@app.get("/api/markets")
def list_markets() -> dict:
    from backend.avm_model import MARKETS
    return {
        k: {
            "label":      v.label,
            "base_price": v.base_price,
            "trend":      v.trend,
        }
        for k, v in MARKETS.items()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )