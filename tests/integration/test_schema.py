"""Vérifications schéma : init.sql a bien créé les tables et index attendus."""
from __future__ import annotations

import pytest

EXPECTED_TABLES = {
    ("raw",       "accounts"),
    ("raw",       "subscriptions"),
    ("raw",       "invoices"),
    ("raw",       "events"),
    ("raw",       "tickets"),
    ("analytics", "churn_predictions"),
    ("analytics", "audit_log"),
}


@pytest.mark.integration
def test_schemas_exist(pg_container):
    from ingestion.db import pg_conn
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT nspname FROM pg_namespace WHERE nspname IN ('raw','staging','marts','analytics');")
        schemas = {r[0] for r in cur.fetchall()}
    assert {"raw", "staging", "marts", "analytics"}.issubset(schemas)


@pytest.mark.integration
def test_tables_exist(pg_container):
    from ingestion.db import pg_conn
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('raw', 'analytics');
        """)
        found = {(s, t) for s, t in cur.fetchall()}
    assert EXPECTED_TABLES.issubset(found)
