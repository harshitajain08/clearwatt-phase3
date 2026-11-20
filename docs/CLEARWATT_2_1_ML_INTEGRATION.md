# ClearWatt 2.1 — ML integration update

This development update is based on the ClearWatt 2.0 working ZIP supplied for the implementation. It is a separate development build and is not deployed.

## Implemented

- Historical bill chart now stores the period-end date and displays daily-normalised consumption (kWh/day) instead of comparing total units from unequal billing periods.
- Usage-change screening and Modified Z-score checks are evaluated independently; one finding no longer suppresses the other.
- Bill-period algorithm analysis is included in the audit response:
  - Isolation Forest (minimum 12 observations)
  - K-Means with three groups (minimum six observations and three distinct feature profiles)
  - Mean-shift change-point analysis (minimum six ordered observations)
- Smart-meter CSV upload returns daily consumption and per-meter algorithm outputs:
  - Isolation Forest (minimum 12 daily observations)
  - K-Means (three daily-use groups; minimum six days and three distinct values)
  - Mean-shift change-point analysis (minimum six days)
- New `GET /api/ml/benchmark` endpoint evaluates Isolation Forest and a 3-sigma daily-units baseline on a deterministic, labelled, synthetic held-out dataset.
- Utility workspace UI displays synthetic benchmark metrics, a confusion matrix, baseline comparison, and smart-meter CSV analysis outputs.
- Tests added for algorithm sufficiency states, bill-period algorithm execution, reproducible synthetic evaluation, benchmark endpoint, and meter CSV ML integration.

## Synthetic benchmark design

- Random seed: 42.
- 600 generated normal samples and 120 generated anomaly samples are created.
- Isolation Forest is fitted on 420 normal training samples only.
- Test partition: 180 held-out normal samples and 90 held-out anomaly samples (270 total).
- Features: daily consumption and daily bill amount.
- Metrics: accuracy, precision, recall, specificity, F1 and false-positive rate, with confusion matrix.

**Important:** The generated benchmark is a software/model demonstration and reproducibility check. It is not field validation, UPPCL validation, a forecast of real-world accuracy, or proof of billing errors. Real-world evaluation requires representative, reviewed and labelled meter/bill data with a documented split and evaluation protocol.

## Local development

Backend:

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
npm install
npm run dev
```

Use the backend `.env.example` as a template for `backend/.env`. Keep API keys in the backend environment only. Never commit `.env`.


## Validation

Backend test suite: **21 passed** in the implementation environment. The frontend production build could not be verified because dependency installation timed out; run `npm install` and `npm run build` locally before using this build as a presentation or deployment candidate.


## Not production-ready

This build still lacks authentication, user/meter data isolation, authorization, deployment hardening, real tariff validation, and a real labelled field dataset. The existing bill-history mechanism is development-only and must not be used with real multi-user data. Do not deploy it publicly or use it for consumer complaint decisions until these protections are implemented and reviewed.
