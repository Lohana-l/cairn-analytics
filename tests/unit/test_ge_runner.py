"""Tests unitaires runner GE : chaque expectation testée contre des fixtures en mémoire."""
from __future__ import annotations

import pandas as pd
import pytest

from great_expectations import runner


class _FakeEngine:
    """Stub minimal de sqlalchemy.Engine pour que pd.read_sql accepte l'objet."""
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df


@pytest.fixture
def fake_read_sql(monkeypatch):
    """Monkey-patch pd.read_sql dans runner pour renvoyer un DataFrame fixe."""
    def _install(df: pd.DataFrame) -> None:
        monkeypatch.setattr(runner.pd, "read_sql", lambda q, eng: df)
        monkeypatch.setattr(runner, "engine", lambda: object())
    return _install


def test_not_null_detects_nulls(fake_read_sql):
    fake_read_sql(pd.DataFrame({"x": [1, None, 3]}))
    r = runner._check_one("tbl", "expect_column_values_to_not_be_null", "x", {})
    assert r["success"] is False
    assert r["observed"]["null_count"] == 1


def test_unique_detects_duplicates(fake_read_sql):
    fake_read_sql(pd.DataFrame({"x": [1, 1, 2]}))
    r = runner._check_one("tbl", "expect_column_values_to_be_unique", "x", {})
    assert r["success"] is False


def test_value_set_passes_when_all_in(fake_read_sql):
    fake_read_sql(pd.DataFrame({"plan": ["starter", "pro"]}))
    r = runner._check_one("tbl", "expect_column_values_to_be_in_set",
                          "plan", {"value_set": ["starter", "pro", "enterprise"]})
    assert r["success"] is True


def test_between_respects_mostly(fake_read_sql):
    # 99% dans la plage, 1% hors, doit passer avec mostly=0.95
    fake_read_sql(pd.DataFrame({"x": [1] * 99 + [999]}))
    r = runner._check_one("tbl", "expect_column_values_to_be_between", "x",
                          {"min_value": 0, "max_value": 10, "mostly": 0.95})
    assert r["success"] is True


def test_between_fails_when_mostly_too_strict(fake_read_sql):
    fake_read_sql(pd.DataFrame({"x": [1] * 99 + [999]}))
    r = runner._check_one("tbl", "expect_column_values_to_be_between", "x",
                          {"min_value": 0, "max_value": 10, "mostly": 1.0})
    assert r["success"] is False


def test_row_count_between(fake_read_sql):
    fake_read_sql(pd.DataFrame({"x": list(range(150))}))
    r = runner._check_one("tbl", "expect_table_row_count_to_be_between", None,
                          {"min_value": 100, "max_value": 200})
    assert r["success"] is True
