from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
class Base(DeclarativeBase): pass

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()


def migrate_schema():
    """Additive migration for older local SQLite/PostgreSQL audit tables."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "audits" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("audits")}
    additions = {"bill_id":"INTEGER", "consumer_ref":"VARCHAR(120)", "meter_ref":"VARCHAR(120)", "discom":"VARCHAR(120)", "period_start":"VARCHAR(10)", "period_end":"VARCHAR(10)", "units":"FLOAT", "amount":"FLOAT"}
    with engine.begin() as conn:
        for column, sql_type in additions.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE audits ADD COLUMN {column} {sql_type}"))
