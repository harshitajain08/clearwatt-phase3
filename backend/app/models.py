from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String, Text, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class BillingRecord(Base):
    __tablename__ = "bills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    consumer_ref: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    meter_ref: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    discom: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    period_start: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    period_end: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    units: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

class AuditRecord(Base):
    __tablename__ = "audits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("bills.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False, index=True)
    consumer_ref: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    meter_ref: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    discom: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    period_start: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    period_end: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    units: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)

class UploadDraft(Base):
    __tablename__ = "upload_drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="needs_review", nullable=False)
