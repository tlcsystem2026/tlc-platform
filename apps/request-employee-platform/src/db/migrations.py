from sqlalchemy import inspect, text
from src.db.session import get_engine

FOREIGN_KEY_FREE_TABLES = (
    "sales_records",
    "request_compare_runs",
    "review_tasks",
)


def _split_sqlite_table_definitions(create_sql: str) -> tuple[str, list[str], str]:
    start = create_sql.find("(")
    end = create_sql.rfind(")")
    if start < 0 or end <= start:
        raise ValueError("Unsupported SQLite CREATE TABLE statement")
    prefix = create_sql[: start + 1]
    body = create_sql[start + 1 : end]
    suffix = create_sql[end:]
    definitions: list[str] = []
    current: list[str] = []
    depth = 0
    quote = ""
    for char in body:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            continue
        if char in ('"', "'", "`"):
            quote = char
            current.append(char)
        elif char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            definitions.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        definitions.append("".join(current).strip())
    return prefix, definitions, suffix


def sqlite_create_table_without_foreign_keys(create_sql: str) -> str:
    prefix, definitions, suffix = _split_sqlite_table_definitions(create_sql)
    kept = [item for item in definitions if "FOREIGN KEY" not in item.upper()]
    if len(kept) == len(definitions):
        return create_sql
    return prefix + "\n  " + ",\n  ".join(kept) + "\n" + suffix


def remove_foreign_key_constraints(engine=None) -> list[str]:
    engine = engine or get_engine()
    if engine.dialect.name != "sqlite":
        foreign_keys = []
        inspector = inspect(engine)
        for table in inspector.get_table_names():
            foreign_keys.extend(inspector.get_foreign_keys(table))
        if foreign_keys:
            raise RuntimeError(
                "Foreign-key removal currently supports SQLite only; "
                "non-SQLite constraints were not changed"
            )
        return []

    raw = engine.raw_connection()
    migrated: list[str] = []
    cursor = raw.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("PRAGMA legacy_alter_table=ON")
        tables = [str(row[0]) for row in cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()]
        for table in tables:
            foreign_keys = cursor.execute(
                f'PRAGMA foreign_key_list("{table}")'
            ).fetchall()
            if not foreign_keys:
                continue
            create_row = cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not create_row or not create_row[0]:
                raise RuntimeError(f"CREATE TABLE SQL not found: {table}")
            original_sql = str(create_row[0])
            replacement_sql = sqlite_create_table_without_foreign_keys(original_sql)
            if replacement_sql == original_sql:
                raise RuntimeError(f"Foreign key definition was not removable: {table}")

            columns = [str(row[1]) for row in cursor.execute(
                f'PRAGMA table_info("{table}")'
            ).fetchall()]
            column_list = ",".join('"' + value.replace('"', '""') + '"' for value in columns)
            before_count = int(cursor.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0])
            indexes = [str(row[0]) for row in cursor.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
                (table,),
            ).fetchall()]
            triggers = [str(row[0]) for row in cursor.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='trigger' AND tbl_name=? AND sql IS NOT NULL",
                (table,),
            ).fetchall()]

            backup = "__tlc_fk_backup_" + table
            cursor.execute(f'DROP TABLE IF EXISTS "{backup}"')
            cursor.execute(f'ALTER TABLE "{table}" RENAME TO "{backup}"')
            cursor.execute(replacement_sql)
            cursor.execute(
                f'INSERT INTO "{table}" ({column_list}) '
                f'SELECT {column_list} FROM "{backup}"'
            )
            after_count = int(cursor.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0])
            if before_count != after_count:
                raise RuntimeError(
                    f"Row-count mismatch for {table}: {before_count} != {after_count}"
                )
            cursor.execute(f'DROP TABLE "{backup}"')
            for index_sql in indexes:
                cursor.execute(index_sql)
            for trigger_sql in triggers:
                cursor.execute(trigger_sql)
            if cursor.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
                raise RuntimeError(f"Foreign key remains after migration: {table}")
            migrated.append(table)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        try:
            cursor.execute("PRAGMA legacy_alter_table=OFF")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
            raw.close()
    return migrated

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
    applied.extend(f"removed_foreign_key:{table}" for table in remove_foreign_key_constraints(engine))
    return applied
