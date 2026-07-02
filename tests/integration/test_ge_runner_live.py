"""Intégration : runner GE contre un Postgres réel pré-seedé."""
from __future__ import annotations

import json

import pytest

from great_expectations.runner import run as ge_run
from ingestion.loaders import load_csv
from seed.config import SeedConfig
from seed.main import run as seed_run


@pytest.mark.integration
def test_ge_runner_on_seeded_db(pg_container, pg_conn_clean, tmp_path, monkeypatch):
    seed_run(tmp_path, SeedConfig(n_accounts=150, seed=3))
    for k in ("accounts", "subscriptions", "invoices", "events", "tickets"):
        load_csv(tmp_path / f"{k}.csv", k)

    # rapports redirigés vers tmp_path pour ne pas polluer le repo
    monkeypatch.setattr("great_expectations.runner.OUT_DIR", tmp_path / "ge_reports")
    exit_code = ge_run()

    summary_path = tmp_path / "ge_reports" / "ge_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text())
    assert summary["total"] > 0
    assert summary["failed"] == 0, summary
    assert exit_code == 0
