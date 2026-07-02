"""Tests unitaires ml.metrics : cohérence de KS, precision@k, full_report."""
from __future__ import annotations

import numpy as np
import pytest

from ml.metrics import compare_reports, full_report, ks_statistic, precision_at_k


def test_perfect_ranking_ks_is_one():
    y      = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    scores = np.array([0.1, 0.2, 0.3, 0.4, 0.9, 0.95, 0.97, 0.99])
    assert ks_statistic(y, scores) == pytest.approx(1.0, abs=1e-6)


def test_random_ranking_ks_near_zero():
    rng = np.random.default_rng(0)
    y     = rng.integers(0, 2, size=5_000)
    score = rng.uniform(0, 1, size=5_000)
    ks    = ks_statistic(y, score)
    assert ks < 0.1      # ≤ 10% sur grand échantillon aléatoire


def test_precision_at_k_edge_cases():
    y     = np.array([1, 1, 0, 0, 0])
    score = np.array([0.9, 0.8, 0.7, 0.2, 0.1])
    assert precision_at_k(y, score, 2) == 1.0   # top-2 tous positifs
    assert precision_at_k(y, score, 5) == 0.4   # tous les 5 : 2 pos / 5
    assert precision_at_k(y, score, 0) == 0.0   # cas dégénéré


def test_full_report_contains_expected_keys():
    rng = np.random.default_rng(1)
    y   = rng.integers(0, 2, size=500)
    s   = rng.uniform(0, 1, size=500)
    r   = full_report(y, s)
    for k in ("roc_auc", "pr_auc", "brier", "ks",
              "precision_at_50", "precision_at_100", "base_rate", "n"):
        assert k in r


def test_compare_reports_returns_dataframe():
    rng = np.random.default_rng(2)
    y, s = rng.integers(0, 2, 100), rng.uniform(0, 1, 100)
    r1, r2 = full_report(y, s), full_report(y, 1 - s)
    df = compare_reports(("a", r1), ("b", r2))
    assert list(df.index) == ["a", "b"]
    assert "roc_auc" in df.columns
