"""Versioned tariff configuration interface. Rates stay disabled until verified against the signed UPERC order."""
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json

DATA = Path(__file__).resolve().parents[1] / "data" / "tariffs" / "uppcl_fy2026_27.json"
@dataclass
class TariffCheck:
    status: str
    message: str
    source: str | None = None

def load_uppcl_schedule() -> dict:
    if not DATA.exists(): return {"status":"not_configured","jurisdiction":"UPPCL","financial_year":"2026-27"}
    return json.loads(DATA.read_text())

def check_eligibility(period_end: str, category: str, area: str | None = None) -> TariffCheck:
    schedule=load_uppcl_schedule()
    if schedule.get("status") != "verified":
        return TariffCheck("not_verified", "UPPCL FY 2026-27 tariff data has not yet passed line-by-line verification. No tariff correctness conclusion has been made.", schedule.get("official_source"))
    # Slab engine is enabled only after tariff schedule data and effective dates are verified.
    return TariffCheck("configured_pending_engine", "Tariff schedule loaded; category mapping and billing-period application require review.", schedule.get("official_source"))
