
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_batch_service import ensure_batch_tables


def _table_exists(db: Session, table_name: str) -> bool:
    row = db.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name=:table_name"
        ),
        {"table_name": table_name},
    ).first()
    return row is not None


def _table_columns(db: Session, table_name: str) -> set[str]:
    if not _table_exists(db, table_name):
        return set()
    rows = db.execute(text(f"PRAGMA table_info({table_name})")).all()
    return {str(row[1]) for row in rows}


def _first_column(columns: set[str], *candidates: str) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return ""


def _column_or_literal(
    columns: set[str],
    alias: str,
    candidates: tuple[str, ...],
    literal: str = "''",
) -> str:
    column = _first_column(columns, *candidates)
    return f"{alias}.{column}" if column else literal


def _rows(
    db: Session,
    sql: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [
        dict(row._mapping)
        for row in db.execute(text(sql), params or {}).all()
    ]


def operational_exception_dashboard(
    db: Session,
    *,
    business_month: str = "",
    limit: int = 500,
) -> dict[str, Any]:
    ensure_batch_tables(db)

    limit = min(max(int(limit), 1), 2000)
    month_clause = ""
    month_params: dict[str, Any] = {"limit": limit}

    if business_month:
        month_clause = "AND b.business_month=:business_month"
        month_params["business_month"] = business_month

    exceptions: list[dict[str, Any]] = []

    if _table_exists(db, "tlc_import_job"):
        rows = _rows(
            db,
            f"""
            SELECT
              j.id AS reference_id,
              j.batch_id,
              b.business_month,
              b.batch_no,
              b.title AS batch_title,
              'IMPORT_JOB_ERROR' AS category,
              'HIGH' AS severity,
              j.status,
              j.import_type AS subcategory,
              j.source_name AS title,
              j.message AS detail,
              j.updated_at AS occurred_at
            FROM tlc_import_job j
            LEFT JOIN tlc_batch b ON b.id=j.batch_id
            WHERE j.status='ERROR'
            {month_clause}
            ORDER BY j.updated_at DESC
            LIMIT :limit
            """,
            month_params,
        )
        exceptions.extend(rows)

    if _table_exists(db, "tlc_import_job_error"):
        rows = _rows(
            db,
            f"""
            SELECT
              e.id AS reference_id,
              e.batch_id,
              b.business_month,
              b.batch_no,
              b.title AS batch_title,
              'IMPORT_RECORD_ERROR' AS category,
              'HIGH' AS severity,
              e.status,
              e.error_code AS subcategory,
              COALESCE(NULLIF(e.record_reference,''), e.field_name) AS title,
              e.message AS detail,
              e.updated_at AS occurred_at
            FROM tlc_import_job_error e
            LEFT JOIN tlc_batch b ON b.id=e.batch_id
            WHERE e.status='OPEN'
            {month_clause}
            ORDER BY e.updated_at DESC
            LIMIT :limit
            """,
            month_params,
        )
        exceptions.extend(rows)

    if _table_exists(db, "tlc_batch_compare_error"):
        columns = _table_columns(db, "tlc_batch_compare_error")
        field_expr = _column_or_literal(
            columns,
            "e",
            ("field_name", "field", "difference_field", "error_field"),
            "'compare'",
        )
        message_expr = _column_or_literal(
            columns,
            "e",
            ("message", "error_message", "detail", "description"),
            "''",
        )
        severity_expr = _column_or_literal(
            columns,
            "e",
            ("severity", "error_level", "level"),
            "'ERROR'",
        )
        status_expr = _column_or_literal(
            columns,
            "e",
            ("status", "error_status"),
            "'OPEN'",
        )
        updated_expr = _column_or_literal(
            columns,
            "e",
            ("updated_at", "created_at", "detected_at"),
            "''",
        )
        batch_id_expr = _column_or_literal(
            columns,
            "e",
            ("batch_id",),
            "''",
        )
        id_expr = _column_or_literal(
            columns,
            "e",
            ("id", "error_id"),
            "''",
        )
        status_filter = ""
        if "status" in columns:
            status_filter = "WHERE e.status='OPEN'"
        elif "error_status" in columns:
            status_filter = "WHERE e.error_status='OPEN'"
        else:
            status_filter = "WHERE 1=1"

        rows = _rows(
            db,
            f"""
            SELECT
              {id_expr} AS reference_id,
              {batch_id_expr} AS batch_id,
              b.business_month,
              b.batch_no,
              b.title AS batch_title,
              'COMPARE_ERROR' AS category,
              CASE
                WHEN UPPER(COALESCE({severity_expr},'')) IN ('ERROR','HIGH','CRITICAL')
                THEN 'HIGH'
                ELSE 'MEDIUM'
              END AS severity,
              {status_expr} AS status,
              {field_expr} AS subcategory,
              {field_expr} AS title,
              {message_expr} AS detail,
              {updated_expr} AS occurred_at
            FROM tlc_batch_compare_error e
            LEFT JOIN tlc_batch b ON b.id={batch_id_expr}
            {status_filter}
            {month_clause}
            ORDER BY {updated_expr} DESC
            LIMIT :limit
            """,
            month_params,
        )
        exceptions.extend(rows)

    if _table_exists(db, "tlc_monthly_close_carry_forward"):
        carry_params = {"limit": limit}
        carry_month_clause = ""
        if business_month:
            carry_month_clause = (
                "AND (source_month=:business_month "
                "OR target_month=:business_month)"
            )
            carry_params["business_month"] = business_month

        rows = _rows(
            db,
            f"""
            SELECT
              id AS reference_id,
              source_batch_id AS batch_id,
              source_month AS business_month,
              '' AS batch_no,
              '' AS batch_title,
              'CARRY_FORWARD_OPEN' AS category,
              'MEDIUM' AS severity,
              status,
              category AS subcategory,
              title,
              reason AS detail,
              updated_at AS occurred_at
            FROM tlc_monthly_close_carry_forward
            WHERE status IN ('OPEN','CONFIRMED')
            {carry_month_clause}
            ORDER BY updated_at DESC
            LIMIT :limit
            """,
            carry_params,
        )
        exceptions.extend(rows)

    if _table_exists(db, "tlc_monthly_close_authorization"):
        auth_params = {"limit": limit}
        auth_month_clause = ""
        if business_month:
            auth_month_clause = "AND business_month=:business_month"
            auth_params["business_month"] = business_month

        rows = _rows(
            db,
            f"""
            SELECT
              id AS reference_id,
              '' AS batch_id,
              business_month,
              '' AS batch_no,
              '' AS batch_title,
              'AUTHORIZATION_PENDING' AS category,
              'MEDIUM' AS severity,
              decision AS status,
              action AS subcategory,
              action || ' authorization pending' AS title,
              request_reason AS detail,
              requested_at AS occurred_at
            FROM tlc_monthly_close_authorization
            WHERE decision='PENDING'
            {auth_month_clause}
            ORDER BY requested_at DESC
            LIMIT :limit
            """,
            auth_params,
        )
        exceptions.extend(rows)

    batch_params = {"limit": limit}
    batch_month_clause = ""
    if business_month:
        batch_month_clause = "AND business_month=:business_month"
        batch_params["business_month"] = business_month

    rows = _rows(
        db,
        f"""
        SELECT
          id AS reference_id,
          id AS batch_id,
          business_month,
          batch_no,
          title AS batch_title,
          'BATCH_NOT_FINISHED' AS category,
          'LOW' AS severity,
          status,
          status AS subcategory,
          COALESCE(NULLIF(batch_no,''), title) AS title,
          'Batch has not reached FINISHED' AS detail,
          updated_at AS occurred_at
        FROM tlc_batch
        WHERE status<>'FINISHED'
        {batch_month_clause}
        ORDER BY updated_at DESC
        LIMIT :limit
        """,
        batch_params,
    )
    exceptions.extend(rows)

    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    exceptions.sort(
        key=lambda item: (
            severity_order.get(item.get("severity", "LOW"), 9),
            str(item.get("occurred_at", "")),
        )
    )
    exceptions = exceptions[:limit]

    by_category: dict[str, int] = {}
    by_severity: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for item in exceptions:
        category = item.get("category", "UNKNOWN")
        severity = item.get("severity", "LOW")
        by_category[category] = by_category.get(category, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1

    return {
        "business_month": business_month,
        "exception_count": len(exceptions),
        "high_count": by_severity.get("HIGH", 0),
        "medium_count": by_severity.get("MEDIUM", 0),
        "low_count": by_severity.get("LOW", 0),
        "by_category": by_category,
        "exceptions": exceptions,
    }
