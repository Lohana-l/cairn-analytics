"""Helpers de connexion Postgres : fine couche au-dessus de psycopg2 / SQLAlchemy.

Les deux coexistent car :
  - psycopg2 est l'outil adapté pour les COPY / UPSERT idempotents
  - SQLAlchemy est ce que Streamlit, ML et FastAPI utilisent en lecture
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from ingestion.config import settings


@contextmanager
def pg_conn() -> Iterator[psycopg2.extensions.connection]:
    """Connexion psycopg2 brute (autocommit OFF), les appelants gèrent leurs transactions."""
    s    = settings()
    conn = psycopg2.connect(
        host=s.pg_host, port=s.pg_port, user=s.pg_user,
        password=s.pg_password, dbname=s.pg_db,
    )
    try:
        yield conn
    finally:
        conn.close()


def engine() -> Engine:
    """Engine SQLAlchemy avec pool, utilisé sur les chemins lecture seule."""
    return create_engine(settings().pg_dsn, pool_pre_ping=True, pool_size=5)
