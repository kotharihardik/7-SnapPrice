# 7 -  SnapPrice - Real-time AVM for Snaphomz Hackathon

## What it does

* Pulls comparable sales via RealEstateAPI (PropertyComps -> PropertySearch fallback -> fixture demo)
* Runs a Ridge Regression AVM when sufficient comparable sales exist
* Falls back to a hedonic adjustment model when comps are limited
* Returns a price estimate, confidence band, and plain-English explanation
* FastAPI backend + lightweight HTML/CSS/JavaScript frontend

---

## Project Structure

```text
7_2/
├── backend/
│   ├── avm_model.py
│   ├── main.py
│   ├── services/
│   │   └── comps_repository.py
│   └── data/
│       ├── training_comps.csv
│       └── demo_fixture.json
│
├── index.html
├── app.js
├── styles.css
│
├── .env
├── requirements.txt
└── README.md
```

---

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create `.env`

```env
REALESTATE_API_KEY=your-secret-key
PORT=8000
```

---

## Run Backend

Start FastAPI:

```bash
python3 -m uvicorn backend.main:app --reload --port 8000
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
```

API Documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Run Frontend

This project uses a lightweight HTML/CSS/JavaScript frontend.

### Option 1 (Recommended)

Start a local web server:

```bash
python3 -m http.server 5500
```

Open:

```text
http://localhost:5500
```

### Option 2 (VS Code)

1. Install "Live Server" extension
2. Right-click `index.html`
3. Click "Open with Live Server"

The browser will open automatically.

---

## Test API

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/value \
-H "Content-Type: application/json" \
-d '{
  "address":"4821 Shoal Creek Blvd, Austin TX",
  "sqft":1920,
  "beds":3,
  "baths":2
}'
```

---

## API Endpoints

| Method | Endpoint     | Description        |
| ------ | ------------ | ------------------ |
| GET    | /health      | Health check       |
| GET    | /api/markets | Supported markets  |
| POST   | /api/value   | Property valuation |

---

## AVM Logic

### Input Features

* Property Address
* Square Footage
* Bedrooms
* Bathrooms
* Comparable Sales
* Market Trends

### Models

| Comps Found | Method                  |
| ----------- | ----------------------- |
| ≥ 4         | Ridge Regression        |
| 1–3         | Hedonic Adjustment      |
| 0           | Market Average Fallback |

### Output

* Estimated Value
* Low Estimate
* High Estimate
* Confidence Score
* Comparable Sales Used
* Feature Contributions
* Plain-English Explanation

---

## Data Sources

### Live Mode

* RealEstateAPI Property Data
* Comparable Sales
* Property Search

### Demo Mode

* `demo_fixture.json`
* Used automatically if API data is unavailable

---

## Verify Live API Usage

When a valuation request is processed:

```text
SOURCE: LIVE API
```

appears in terminal if RealEstateAPI data is used.

If API is unavailable:

```text
SOURCE: FIXTURE
```

appears instead.

---

## Technology Stack

### Backend

* Python
* FastAPI
* Scikit-Learn
* Pandas
* NumPy
* HTTPX

### Frontend

* HTML
* CSS
* JavaScript

### Data

* RealEstateAPI
* Demo Fixture Dataset

---

## Demo Flow

```text
User Property
      ↓
RealEstateAPI
      ↓
Comparable Sales
      ↓
Feature Engineering
      ↓
AVM Model
      ↓
Price Estimate
      ↓
Explanation Layer
      ↓
SnapPrice UI
```
# 7-SnapPrice
