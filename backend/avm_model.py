from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import numpy as np


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CompsItem:
    address: str
    sale_price: int
    sqft: int
    beds: float
    baths: float
    sold_days_ago: int


@dataclass(frozen=True)
class MarketProfile:
    label: str
    base_price: int
    low_price: int
    high_price: int
    price_per_sqft: float
    trend: str
    source: str


@dataclass
class ValuationResult:
    estimated_value: int
    low_estimate: int
    high_estimate: int
    confidence: float          # 0-1
    price_per_sqft: float
    adjustments: dict[str, int]   # factor -> dollar impact
    explanation: str
    comps_used: int
    market_trend: str
    source: str
    mode: str


# ---------------------------------------------------------------------------
# Market profiles
# ---------------------------------------------------------------------------

MARKETS: dict[str, MarketProfile] = {
    "austin": MarketProfile(
        "Austin TX", 575000, 490000, 680000, 0.82,
        "+3.1% over 3 months", "ATTOM / RealEstateAPI"
    ),
    "dallas": MarketProfile(
        "Dallas TX", 420000, 360000, 510000, 0.74,
        "+1.8% over 3 months", "ATTOM / RealEstateAPI"
    ),
    "phoenix": MarketProfile(
        "Phoenix AZ", 395000, 330000, 475000, 0.71,
        "+0.9% over 3 months", "ATTOM / RealEstateAPI"
    ),
    "miami": MarketProfile(
        "Miami FL", 620000, 520000, 760000, 0.89,
        "+4.2% over 3 months", "ATTOM / RealEstateAPI"
    ),
    "denver": MarketProfile(
        "Denver CO", 545000, 470000, 645000, 0.85,
        "+2.3% over 3 months", "ATTOM / RealEstateAPI"
    ),
    "seattle": MarketProfile(
        "Seattle WA", 780000, 650000, 940000, 1.02,
        "+1.5% over 3 months", "ATTOM / RealEstateAPI"
    ),
    "chicago": MarketProfile(
        "Chicago IL", 340000, 280000, 430000, 0.61,
        "-0.4% over 3 months", "ATTOM / RealEstateAPI"
    ),
    "nashville": MarketProfile(
        "Nashville TN", 480000, 400000, 580000, 0.77,
        "+2.8% over 3 months", "ATTOM / RealEstateAPI"
    ),
}


# ---------------------------------------------------------------------------
# AVM Engine
# ---------------------------------------------------------------------------

class AVMEngine:
    """
    Lightweight AVM that uses comparable sales to produce a hedonic price estimate.
    Falls back to scikit-learn LinearRegression when enough comps exist;
    otherwise uses weighted-median with manual feature adjustments.
    Uses SHAP-style additive decomposition for plain-English explanations.
    """

    # Adjustment coefficients (dollars per unit)
    BED_PREMIUM     =  8_000   # per extra bedroom vs median comp
    BATH_PREMIUM    = 12_000   # per extra bathroom vs median comp
    SQFT_PREMIUM    =    180   # per extra sq-ft vs median comp  (≈ avg $/sqft)
    RECENCY_BONUS   =     50   # per day fresher the sale is vs 90-day baseline
    RECENCY_CUTOFF  =     90   # days – sales older than this get a discount

    def value(
        self,
        subject: dict[str, Any],
        comps: list[CompsItem],
        market: MarketProfile,
    ) -> ValuationResult:
        """Main entry point."""
        if not comps:
            return self._fallback(subject, market)

        if len(comps) >= 4:
            return self._ml_valuation(subject, comps, market)
        return self._hedonic_valuation(subject, comps, market)

    # ------------------------------------------------------------------
    # ML path (≥4 comps)
    # ------------------------------------------------------------------
    def _ml_valuation(
        self,
        subject: dict,
        comps: list[CompsItem],
        market: MarketProfile,
    ) -> ValuationResult:
        try:
            from sklearn.linear_model import Ridge
            from sklearn.preprocessing import StandardScaler

            X = np.array([[c.sqft, c.beds, c.baths, c.sold_days_ago] for c in comps], dtype=float)
            y = np.array([c.sale_price for c in comps], dtype=float)

            scaler = StandardScaler()
            Xs = scaler.fit_transform(X)

            model = Ridge(alpha=1.0)
            model.fit(Xs, y)

            subj_vec = np.array([[
                subject.get("sqft", 1800),
                subject.get("beds", 3),
                subject.get("baths", 2),
                0,   # subject is current, 0 days ago
            ]], dtype=float)
            subj_scaled = scaler.transform(subj_vec)
            predicted = float(model.predict(subj_scaled)[0])

            # SHAP-style: perturb each feature to get contribution
            base_pred = float(model.predict(scaler.transform(
                np.array([[np.mean(X[:, 0]), np.mean(X[:, 1]),
                           np.mean(X[:, 2]), np.mean(X[:, 3])]])
            ))[0])

            adjustments = self._shap_adjustments(
                model, scaler, subj_vec[0], X, predicted, base_pred
            )

            median_comp_price = float(np.median(y))
            confidence = self._confidence(len(comps), predicted, y)

            low  = int(predicted * 0.94)
            high = int(predicted * 1.06)

            explanation = self._explain(
                subject, adjustments, predicted, median_comp_price,
                market, len(comps), mode="ml"
            )

            return ValuationResult(
                estimated_value=int(predicted),
                low_estimate=low,
                high_estimate=high,
                confidence=round(confidence, 2),
                price_per_sqft=round(predicted / max(subject.get("sqft", 1), 1), 2),
                adjustments=adjustments,
                explanation=explanation,
                comps_used=len(comps),
                market_trend=market.trend,
                source=market.source,
                mode="ml-ridge",
            )
        except ImportError:
            return self._hedonic_valuation(subject, comps, market)

    def _shap_adjustments(self, model, scaler, subj_raw, X_train, pred, base_pred):
        """Approximate SHAP via leave-one-out feature perturbation."""
        feature_names = ["sqft", "beds", "baths", "recency"]
        means = X_train.mean(axis=0)
        contributions = {}

        for i, name in enumerate(feature_names):
            perturbed = subj_raw.copy()
            perturbed[i] = means[i]
            p_scaled = scaler.transform(perturbed.reshape(1, -1))
            p_pred = float(model.predict(p_scaled)[0])
            contributions[name] = int(pred - p_pred)

        return contributions

    # ------------------------------------------------------------------
    # Hedonic path (<4 comps)
    # ------------------------------------------------------------------
    def _hedonic_valuation(
        self,
        subject: dict,
        comps: list[CompsItem],
        market: MarketProfile,
    ) -> ValuationResult:
        prices   = [c.sale_price for c in comps]
        sqfts    = [c.sqft       for c in comps]
        beds_l   = [c.beds       for c in comps]
        baths_l  = [c.baths      for c in comps]
        days_l   = [c.sold_days_ago for c in comps]

        med_price = float(np.median(prices))
        med_sqft  = float(np.median(sqfts))  if sqfts  else 1800
        med_beds  = float(np.median(beds_l)) if beds_l else 3
        med_baths = float(np.median(baths_l))if baths_l else 2
        med_days  = float(np.median(days_l)) if days_l else 45

        subj_sqft  = subject.get("sqft",  med_sqft)
        subj_beds  = subject.get("beds",  med_beds)
        subj_baths = subject.get("baths", med_baths)

        adj_sqft   = int((subj_sqft  - med_sqft)  * self.SQFT_PREMIUM)
        adj_beds   = int((subj_beds  - med_beds)  * self.BED_PREMIUM)
        adj_baths  = int((subj_baths - med_baths) * self.BATH_PREMIUM)
        adj_recency= int((self.RECENCY_CUTOFF - med_days) * self.RECENCY_BONUS)

        adjustments = {
            "sqft":    adj_sqft,
            "beds":    adj_beds,
            "baths":   adj_baths,
            "recency": adj_recency,
        }

        predicted = med_price + sum(adjustments.values())
        predicted = max(predicted, market.low_price * 0.7)

        confidence = self._confidence(len(comps), predicted, prices)
        spread = 0.07 if len(comps) < 3 else 0.055

        explanation = self._explain(
            subject, adjustments, predicted, med_price,
            market, len(comps), mode="hedonic"
        )

        return ValuationResult(
            estimated_value=int(predicted),
            low_estimate=int(predicted * (1 - spread)),
            high_estimate=int(predicted * (1 + spread)),
            confidence=round(confidence, 2),
            price_per_sqft=round(predicted / max(subj_sqft, 1), 2),
            adjustments=adjustments,
            explanation=explanation,
            comps_used=len(comps),
            market_trend=market.trend,
            source=market.source,
            mode="hedonic",
        )

    # ------------------------------------------------------------------
    # Fallback – no comps
    # ------------------------------------------------------------------
    def _fallback(self, subject: dict, market: MarketProfile) -> ValuationResult:
        sqft = subject.get("sqft", 1800)
        beds = subject.get("beds", 3)

        estimated = int(market.base_price
                        + (sqft - 1800) * market.price_per_sqft
                        + (beds - 3) * self.BED_PREMIUM)

        return ValuationResult(
            estimated_value=estimated,
            low_estimate=market.low_price,
            high_estimate=market.high_price,
            confidence=0.45,
            price_per_sqft=round(estimated / max(sqft, 1), 2),
            adjustments={},
            explanation=(
                f"Estimated using {market.label} market averages only. "
                "No comparable sales were available for this address. "
                f"Market trend: {market.trend}."
            ),
            comps_used=0,
            market_trend=market.trend,
            source=market.source,
            mode="market-average",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _confidence(self, n_comps: int, predicted: float, prices) -> float:
        base = min(0.55 + n_comps * 0.06, 0.92)
        if len(prices) > 1:
            cv = float(np.std(prices) / (np.mean(prices) + 1e-9))
            base -= min(cv * 0.3, 0.15)
        return round(max(0.40, min(base, 0.95)), 2)

    def _explain(
        self,
        subject: dict,
        adjustments: dict,
        predicted: float,
        median_comp: float,
        market: MarketProfile,
        n_comps: int,
        mode: str,
    ) -> str:
        parts = []
        adj = adjustments

        if n_comps:
            parts.append(
                f"Based on {n_comps} comparable {'sale' if n_comps == 1 else 'sales'} "
                f"near this property, the median comp price is ${median_comp:,.0f}."
            )
        else:
            parts.append(f"No recent comps found; using {market.label} market baseline of ${median_comp:,.0f}.")

        sqft_adj = adj.get("sqft", 0)
        if sqft_adj:
            direction = "adds" if sqft_adj > 0 else "reduces"
            parts.append(
                f"Your home's size {direction} approximately ${abs(sqft_adj):,} "
                f"vs. the median comparable."
            )

        beds_adj = adj.get("beds", 0)
        if beds_adj:
            direction = "adds" if beds_adj > 0 else "reduces"
            parts.append(
                f"Bedroom count {direction} approximately ${abs(beds_adj):,} "
                f"vs. the median comparable."
            )

        baths_adj = adj.get("baths", 0)
        if abs(baths_adj) > 1000:
            direction = "adds" if baths_adj > 0 else "reduces"
            parts.append(
                f"Bathroom count {direction} approximately ${abs(baths_adj):,} "
                f"vs. the median comparable."
            )

        rec_adj = adj.get("recency", 0)
        if abs(rec_adj) > 500:
            direction = "fresher" if rec_adj > 0 else "older"
            parts.append(
                f"Comp recency is {direction} than average, "
                f"{'adding' if rec_adj > 0 else 'reducing'} ~${abs(rec_adj):,}."
            )

        parts.append(
            f"Market trend for {market.label}: {market.trend}. "
            f"Final estimate: ${predicted:,.0f}."
        )

        return " ".join(parts)