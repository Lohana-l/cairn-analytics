"""Intégration : `dbt build` contre le Postgres Testcontainers.

Plus lent que les autres tests d'intégration, marqué séparément pour pouvoir splitter en CI.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from ingestion.loaders import load_csv
from seed.config import SeedConfig
from seed.main import run as seed_run

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
@pytest.mark.slow
def test_dbt_build_succeeds(pg_container, pg_conn_clean, tmp_path):
    # 1. seed + ingestion d'un petit dataset de test
    seed_run(tmp_path, SeedConfig(n_accounts=80, seed=11))
    for k in ("accounts", "subscriptions", "invoices", "events", "tickets"):
        load_csv(tmp_path / f"{k}.csv", k)

    # 2. dbt pointe sur le conteneur de test via les vars d'env
    env = os.environ.copy()
    env.update({
        "DBT_POSTGRES_HOST":   env["POSTGRES_HOST"],
        "DBT_POSTGRES_PORT":   str(env["POSTGRES_PORT"]),
        "DBT_POSTGRES_USER":   "cairn",
        "DBT_POSTGRES_PASS":   "password",
        "DBT_POSTGRES_DBNAME": "cairn",
        "DBT_POSTGRES_SCHEMA": "marts",
        "DBT_PROFILES_DIR":    str(ROOT / "dbt"),
    })

    # 3. pipeline dbt complet : deps, run, test
    subprocess.run(["dbt", "deps"],  check=True, cwd=ROOT / "dbt", env=env)
    subprocess.run(["dbt", "run"],   check=True, cwd=ROOT / "dbt", env=env)
    subprocess.run(["dbt", "test"],  check=True, cwd=ROOT / "dbt", env=env)
