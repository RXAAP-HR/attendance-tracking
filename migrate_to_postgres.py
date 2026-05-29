"""
SQLite → PostgreSQL migration script.

Usage:
    pip install psycopg2-binary
    python migrate_to_postgres.py --sqlite employeeroster.db --postgres "postgresql://user:pass@host/dbname"

Get your Postgres URL from Render:
    Dashboard → attendance-db → Info tab → "External Database URL"
"""

import argparse
import sqlite3
import sys

def migrate(sqlite_path: str, postgres_url: str):
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    print(f"Connecting to SQLite: {sqlite_path}")
    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row

    print(f"Connecting to PostgreSQL...")
    dst = psycopg2.connect(postgres_url)
    dst.autocommit = False
    cur = dst.cursor()

    # ── employees ────────────────────────────────────────────────────────────
    print("Migrating employees...")
    rows = src.execute("SELECT * FROM employees").fetchall()
    cur.execute("DELETE FROM points_history")   # FK order — clear children first
    cur.execute("DELETE FROM pto_uploads")
    cur.execute("DELETE FROM employees")

    for r in rows:
        cur.execute("""
            INSERT INTO employees (
                employee_id, last_name, first_name, start_date,
                point_total, last_point_date, rolloff_date,
                perfect_attendance, point_warning_date, is_active,
                "Location", manager, employment_type
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            r["employee_id"], r["last_name"], r["first_name"], r["start_date"],
            r["point_total"], r["last_point_date"], r["rolloff_date"],
            r["perfect_attendance"], r["point_warning_date"], r["is_active"],
            r["Location"], r["manager"],
            r["employment_type"] if r["employment_type"] else "Full-Time",
        ))
    print(f"  → {len(rows)} employees inserted")

    # ── points_history ────────────────────────────────────────────────────────
    print("Migrating points_history...")
    rows = src.execute("SELECT * FROM points_history ORDER BY id").fetchall()
    for r in rows:
        cur.execute("""
            INSERT INTO points_history (id, employee_id, point_date, points, reason, note, flag_code)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (r["id"], r["employee_id"], r["point_date"], r["points"],
              r["reason"], r["note"], r["flag_code"]))
    # Sync the sequence so future inserts don't collide with migrated IDs
    cur.execute("SELECT setval('points_history_id_seq', (SELECT MAX(id) FROM points_history))")
    print(f"  → {len(rows)} point history rows inserted")

    # ── pto_uploads ───────────────────────────────────────────────────────────
    print("Migrating pto_uploads...")
    rows = src.execute("SELECT * FROM pto_uploads ORDER BY id").fetchall()
    for r in rows:
        cur.execute("""
            INSERT INTO pto_uploads (id, employee_id, last_name, first_name,
                building, pto_type, start_date, end_date, hours, request_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (r["id"], r["employee_id"], r["last_name"], r["first_name"],
              r["building"], r["pto_type"], r["start_date"], r["end_date"],
              r["hours"], r["request_date"]))
    if rows:
        cur.execute("SELECT setval('pto_uploads_id_seq', (SELECT MAX(id) FROM pto_uploads))")
    print(f"  → {len(rows)} PTO rows inserted")

    dst.commit()
    src.close()
    dst.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite attendance DB to PostgreSQL")
    parser.add_argument("--sqlite", default="employeeroster.db", help="Path to SQLite file")
    parser.add_argument("--postgres", required=True, help="PostgreSQL connection string")
    args = parser.parse_args()
    migrate(args.sqlite, args.postgres)
