from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
import joblib

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "data" / "demo_fixture.json"
OUT = ROOT / "model.joblib"


def load_rows():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = []
    for market, payload in data.items():
        for comp in payload.get("comps", []):
            sqft = comp.get("sqft")
            beds = comp.get("beds")
            baths = comp.get("baths")
            days = comp.get("sold_days_ago")
            price = comp.get("sale_price")
            if None in (sqft, beds, baths, days, price):
                continue
            rows.append((sqft, beds, baths, days, price))
    return rows


def main():
    rows = load_rows()
    if not rows:
        print("No training rows found in demo_fixture.json")
        return

    arr = np.array(rows, dtype=float)
    X = arr[:, :4]
    y = arr[:, 4]

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    model = Ridge(alpha=1.0)
    model.fit(Xs, y)

    joblib.dump({"model": model, "scaler": scaler}, OUT)
    print(f"Saved model to {OUT}")


if __name__ == "__main__":
    main()
