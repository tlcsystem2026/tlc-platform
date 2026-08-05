from sqlalchemy import create_engine, text

from src.db.migrations import (
    remove_foreign_key_constraints,
    sqlite_create_table_without_foreign_keys,
)


def test_create_sql_removes_only_foreign_key_clause():
    original = """CREATE TABLE child (
      id VARCHAR(64) PRIMARY KEY,
      parent_id VARCHAR(64) NOT NULL,
      value VARCHAR(100),
      CONSTRAINT uq_child UNIQUE (parent_id, value),
      FOREIGN KEY(parent_id) REFERENCES parent (id)
    )"""
    result = sqlite_create_table_without_foreign_keys(original)
    assert "FOREIGN KEY" not in result
    assert "CONSTRAINT uq_child UNIQUE" in result
    assert "parent_id VARCHAR(64) NOT NULL" in result


def test_sqlite_migration_preserves_rows_and_unique_constraint(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'foreign-key-removal.sqlite3'}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE legal_entities (id VARCHAR(50) PRIMARY KEY, name TEXT)"
        ))
        connection.execute(text("""CREATE TABLE sales_records (
          id VARCHAR(64) PRIMARY KEY,
          legal_entity_id VARCHAR(50) NOT NULL,
          request_no VARCHAR(100) NOT NULL,
          CONSTRAINT uq_sales_entity_request_no UNIQUE (legal_entity_id, request_no),
          FOREIGN KEY(legal_entity_id) REFERENCES legal_entities(id)
        )"""))
        connection.execute(text("INSERT INTO legal_entities VALUES ('TLC','TLC')"))
        connection.execute(text(
            "INSERT INTO sales_records VALUES ('S1','TLC','REQ-1')"
        ))
        connection.execute(text("""CREATE TABLE extra_child (
          id VARCHAR(64) PRIMARY KEY,
          entity_id VARCHAR(50),
          FOREIGN KEY(entity_id) REFERENCES legal_entities(id)
        )"""))

    assert remove_foreign_key_constraints(engine) == ["extra_child", "sales_records"]
    assert remove_foreign_key_constraints(engine) == []

    with engine.begin() as connection:
        assert connection.execute(text(
            "PRAGMA foreign_key_list(sales_records)"
        )).all() == []
        assert connection.execute(text(
            "PRAGMA foreign_key_list(extra_child)"
        )).all() == []
        assert connection.execute(text(
            "SELECT id,legal_entity_id,request_no FROM sales_records"
        )).one() == ("S1", "TLC", "REQ-1")
        try:
            connection.execute(text(
                "INSERT INTO sales_records VALUES ('S2','TLC','REQ-1')"
            ))
            raise AssertionError("unique constraint was lost")
        except Exception as exc:
            assert "UNIQUE constraint failed" in str(exc)


def test_models_no_longer_declare_foreign_keys():
    from src.db.models import RequestCompareRunORM, ReviewTaskORM, SalesRecordORM

    for model in (SalesRecordORM, RequestCompareRunORM, ReviewTaskORM):
        assert list(model.__table__.foreign_keys) == []
