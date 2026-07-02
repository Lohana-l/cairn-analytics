"""Tests unitaires ingestion.loaders : idempotence et mapping colonnes.

Postgres mocké pour la portabilité, le round-trip complet est dans
tests/integration/test_ingest_roundtrip.py.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ingestion import loaders


@contextmanager
def _fake_conn(rowcount: int = 0):
    conn = MagicMock()
    cur  = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    cur.rowcount = rowcount
    yield conn


def test_load_csv_unknown_key_raises(tmp_path: Path):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        loaders.load_csv(bad, "unknown_table")


def test_load_csv_empty_csv_returns_zero(tmp_path: Path, monkeypatch):
    p = tmp_path / "accounts.csv"
    p.write_text("account_id,company_name,industry,country,plan,seats,signup_ts,churned_ts,acquisition_ch\n")
    monkeypatch.setattr(loaders, "pg_conn", lambda: _fake_conn(0))
    assert loaders.load_csv(p, "accounts") == 0


def test_load_csv_happy_path_calls_copy_and_upsert(tmp_path: Path, monkeypatch):
    p = tmp_path / "accounts.csv"
    p.write_text(
        "account_id,company_name,industry,country,plan,seats,signup_ts,churned_ts,acquisition_ch\n"
        "acc_1,Corp,FinTech,US,starter,5,2025-01-01T00:00:00Z,,organic\n"
        "acc_2,Bar, E-commerce,FR,pro,25,2025-01-02T00:00:00Z,,paid\n"
    )

    captured: dict = {"copy_calls": 0, "exec_calls": 0}

    @contextmanager
    def _stub_conn():
        conn = MagicMock()
        cur  = MagicMock()

        def _copy_expert(sql, buf):
            captured["copy_calls"] += 1
            assert "COPY _stage" in sql

        def _execute(sql, *args, **kwargs):
            captured["exec_calls"] += 1
            if "INSERT INTO raw.accounts" in sql:
                captured["saw_upsert"] = True
                cur.rowcount = 2
            return None

        cur.copy_expert.side_effect = _copy_expert
        cur.execute.side_effect      = _execute
        cur.rowcount = 0
        conn.cursor.return_value.__enter__.return_value = cur
        conn.__enter__.return_value = conn
        conn.__exit__.return_value  = False
        yield conn

    monkeypatch.setattr(loaders, "pg_conn", _stub_conn)

    inserted = loaders.load_csv(p, "accounts")
    assert captured["copy_calls"] == 1
    assert captured["saw_upsert"] is True
    assert inserted == 2
