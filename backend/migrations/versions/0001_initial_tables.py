"""Create initial ClearWatt audit and upload-draft tables.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision="0001_initial"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("audits",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("status",sa.String(length=32),nullable=False),sa.Column("source_filename",sa.String(length=255),nullable=True),sa.Column("payload_json",sa.Text(),nullable=False),sa.Column("result_json",sa.Text(),nullable=False))
    op.create_table("upload_drafts",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("source_filename",sa.String(length=255),nullable=False),sa.Column("file_path",sa.Text(),nullable=False),sa.Column("extracted_json",sa.Text(),nullable=False),sa.Column("status",sa.String(length=32),nullable=False))

def downgrade():
    # Explicit downgrade only; do not run against production data without a reviewed backup/rollback plan.
    op.drop_table("upload_drafts")
    op.drop_table("audits")
