import sqlite3
from pathlib import Path


def get_set_config_by_id(set_id):
    normalized = str(set_id or "").strip().lower()
    if not normalized:
        raise KeyError("Unknown set id: empty")

    row = _fetch_set_row(normalized)

    if row is None:
        raise KeyError(f"Unknown set id: {set_id}")

    set_name = str(row["name"] or "").strip() or normalized.upper()

    return {
        "label": f"{normalized.upper()} - {set_name}",
        "name": set_name,
        "id": normalized,
        "api_set": str(row["api_set"] or normalized).strip().lower(),
    }


def _fetch_set_row(set_id):
    db_path = Path(__file__).resolve().parent / "database" / "ops_nexus.db"
    if not db_path.exists():
        return None

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    try:
        return connection.execute(
            """
            SELECT
                id,
                name,
                COALESCE(NULLIF(TRIM(api_set), ''), id) AS api_set
            FROM sets
            WHERE LOWER(id) = LOWER(?)
            LIMIT 1
            """,
            (set_id,),
        ).fetchone()
    finally:
        connection.close()
