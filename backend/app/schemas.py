from pydantic import BaseModel, Field, model_validator
from datetime import date
from typing import Optional

class ManualAuditIn(BaseModel):
    period_start: date
    period_end: date
    units: float = Field(ge=0)
    amount: float = Field(ge=0)
    meter_reading_previous: Optional[float] = Field(default=None, ge=0)
    meter_reading_current: Optional[float] = Field(default=None, ge=0)
    consumer_category: str = "domestic"
    consumer_ref: Optional[str] = None
    meter_ref: Optional[str] = None
    discom: Optional[str] = None
    supply_area: Optional[str] = None
    connected_load_kw: Optional[float] = Field(default=None, gt=0)
    history: list[dict] = []
    @model_validator(mode="after")
    def check_dates(self):
        if self.period_end < self.period_start: raise ValueError("Billing period end must be on or after its start date.")
        if self.meter_reading_previous is not None and self.meter_reading_current is not None and self.meter_reading_current < self.meter_reading_previous:
            raise ValueError("Current meter reading cannot be lower than the previous reading unless a meter rollover or replacement is documented.")
        return self

class ConfirmDraftIn(ManualAuditIn): draft_id: int
class ExplainIn(BaseModel): audit_id: int; question: str = "Explain the main findings in simple language."
class EvaluationIn(BaseModel): y_true: list[int]; y_pred: list[int]
