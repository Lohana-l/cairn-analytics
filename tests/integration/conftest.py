"""Fixture Testcontainers : lance Postgres, applique sql/init.sql, exporte les vars d'env.

Scope session : un seul conteneur Postgres par session pytest (acceptable sur laptop).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from testcontainers.postgres import PostgresContainer

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer(
        "postgres:16-alpine",
        username="cairn",
        password="password",
        dbname="cairn",
    ) as pg:
        os.environ["POSTGRES_HOST"]     = pg.get_container_host_ip()
        os.environ["POSTGRES_PORT"]     = pg.get_exposed_port(5432)
        os.environ["POSTGRES_USER"]     = "cairn"
        os.environ["POSTGRES_PASSWORD"] = "password"
        os.environ["POSTGRES_DB"]       = "cairn"

        # lru_cache vidé pour que ingestion.db lise les nouvelles vars d'env
        from ingestion.config import settings
        settings.cache_clear()

        # schéma initial appliqué une seule fois en début de session
        init_sql = (ROOT / "sql" / "init.sql").read_text()
        from ingestion.db import pg_conn
        with pg_conn() as conn, conn.cursor() as cur:
            cur.execute(init_sql)
            conn.commit()

        yield pg


@pytest.fixture
def pg_conn_clean(pg_container):
    """Tronque les tables raw + analytics entre les tests (isolation garantie)."""
    from ingestion.db import pg_conn
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            TRUNCATE
                raw.accounts, raw.subscriptions, raw.invoices,
                raw.events,   raw.tickets,
                analytics.churn_predictions, analytics.audit_log
            RESTART IDENTITY CASCADE;
        """)
        conn.commit()
    yield
