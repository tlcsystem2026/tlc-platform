from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.services.request_pending_review_service import ensure_pending_review_table

def test_pending_review_schema_contains_business_review_columns(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'schema.sqlite3').as_posix()}")
    db = sessionmaker(bind=engine)()
    try:
        ensure_pending_review_table(db)
        columns = {row._mapping["name"] for row in db.execute(text("PRAGMA table_info(request_pending_review)")).all()}
        required = {"reviewed_by","review_note","reviewed_at","sales_ledger_id","posted_at"}
        assert required.issubset(columns)
    finally:
        db.close()
        engine.dispose()
