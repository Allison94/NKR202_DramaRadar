"""Apply db/schema.sql to PostgreSQL (dev helper).

Usage:
    uv run python -m db.apply_schema
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from db.database import engine


def apply_schema() -> None:
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8-sig").strip()

    raw = engine.raw_connection()
    try:
        with raw.cursor() as cursor:
            cursor.execute(sql)
        raw.commit()
    finally:
        raw.close()


if __name__ == "__main__":
    apply_schema()
    print("schema applied")
