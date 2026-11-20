"""Persist bill-period records separately from audit snapshots.

Revision ID: 0002_bill_records
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
revision = "0002_bill_records"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumer_ref", sa.String(120), nullable=True),
        sa.Column("meter_ref", sa.String(120), nullable=True),
        sa.Column("discom", sa.String(120), nullable=True),
        sa.Column("period_start", sa.String(10), nullable=False),
        sa.Column("period_end", sa.String(10), nullable=False),
        sa.Column("units", sa.Float(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    for column, kind in [
        ("bill_id", sa.Integer()), ("consumer_ref", sa.String(120)),
        ("meter_ref", sa.String(120)), ("discom", sa.String(120)),
        ("period_start", sa.String(10)), ("period_end", sa.String(10)),
        ("units", sa.Float()), ("amount", sa.Float()),
    ]:
        op.add_column("audits", sa.Column(column, kind, nullable=True))
    op.create_index("ix_bills_consumer_ref", "bills", ["consumer_ref"])
    op.create_index("ix_bills_meter_ref", "bills", ["meter_ref"])
    op.create_index("ix_bills_discom", "bills", ["discom"])
    op.create_index("ix_bills_period_start", "bills", ["period_start"])
    op.create_index("ix_bills_period_end", "bills", ["period_end"])
    op.create_index("ix_audits_bill_id", "audits", ["bill_id"])
    op.create_index("ix_audits_meter_ref", "audits", ["meter_ref"])
    op.create_index("ix_audits_consumer_ref", "audits", ["consumer_ref"])
    op.create_index("ix_audits_discom", "audits", ["discom"])
    op.create_index("ix_audits_period_start", "audits", ["period_start"])
    op.create_index("ix_audits_period_end", "audits", ["period_end"])

def downgrade():
    for idx in ["ix_audits_period_end", "ix_audits_period_start", "ix_audits_discom", "ix_audits_consumer_ref", "ix_audits_meter_ref", "ix_audits_bill_id"]:
        op.drop_index(idx, table_name="audits")
    for idx in ["ix_bills_period_end", "ix_bills_period_start", "ix_bills_discom", "ix_bills_meter_ref", "ix_bills_consumer_ref"]:
        op.drop_index(idx, table_name="bills")
    op.drop_table("bills")
    for column in ["amount", "units", "period_end", "period_start", "discom", "meter_ref", "consumer_ref", "bill_id"]:
        op.drop_column("audits", column)
