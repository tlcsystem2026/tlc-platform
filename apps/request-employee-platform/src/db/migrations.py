from sqlalchemy import inspect, text
from src.db.session import get_engine

EXPECTED_COLUMNS = {
    "legal_entities": {"created_at": "DATETIME"},
    "requests": {"created_at": "DATETIME"},
    "sales_records": {"created_at": "DATETIME"},
    "request_compare_runs": {"created_at": "DATETIME"},
    "review_tasks": {
        "assignee": "VARCHAR(200) DEFAULT ''",
        "resolution_note": "TEXT DEFAULT ''",
        "resolved_at": "DATETIME",
        "created_at": "DATETIME",
    },
}
def migrate_schema():
    engine=get_engine(); applied=[]
    for table, columns in EXPECTED_COLUMNS.items():
        names=set(inspect(engine).get_table_names())
        if table not in names: continue
        existing={c["name"] for c in inspect(engine).get_columns(table)}
        with engine.begin() as conn:
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}'))
                    applied.append(f"{table}.{name}")
    return applied
