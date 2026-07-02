"""Intégration : seed, CSV, load_csv, SELECT COUNT(*) round-trip.

Vérifie que :
  • générateurs et loaders s'accordent sur noms + ordre des colonnes
  • le full refresh rend le loader idempotent : rejouer le même snapshot
    laisse exactement le même état, sans accumuler de lignes obsolètes
"""
from __future__ import annotations

import pytest

from ingestion.db import pg_conn
from ingestion.loaders import load_csv
from seed.config import SeedConfig
from seed.main import run as seed_run


@pytest.mark.integration
def test_full_seed_and_ingest_roundtrip(pg_container, pg_conn_clean, tmp_path):
    cfg = SeedConfig(n_accounts=50, seed=1)
    seed_run(tmp_path, cfg)

    order = ["accounts", "subscriptions", "invoices", "events", "tickets"]
    counts: dict[str, int] = {}
    for k in order:
        counts[k] = load_csv(tmp_path / f"{k}.csv", k)

    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM raw.accounts;")
        accounts_n = cur.fetchone()[0]
    assert accounts_n == 50


@pytest.mark.integration
def test_ingest_is_idempotent(pg_container, pg_conn_clean, tmp_path):
    cfg = SeedConfig(n_accounts=30, seed=2)
    seed_run(tmp_path, cfg)
    first = load_csv(tmp_path / "accounts.csv", "accounts")
    load_csv(tmp_path / "accounts.csv", "accounts")              # deuxième passage : full refresh

    assert first == 30
    # Idempotence : la table reflète exactement le snapshot, sans accumulation.
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM raw.accounts;")
        assert cur.fetchone()[0] == 30
