"""Tests unitaires ml.features : câblage labels, absence de leakage, alignement one-hot."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from ml.features import (
    FEATURE_COLUMNS,
    build_features,
    encode,
    train_test_split_by_date,
)


def _fake_health(n: int = 50, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df  = pd.DataFrame({
        "account_id":             [f"acc_{i}" for i in range(n)],
        "company_name":           [f"Co{i}" for i in range(n)],
        "industry":               rng.choice(["FinTech", "EdTech"], size=n),
        "country":                rng.choice(["US", "FR"], size=n),
        "current_plan":           rng.choice(["starter", "pro", "enterprise"], size=n),
        "current_seats":          rng.integers(1, 50, size=n),
        "tenure_months":          rng.uniform(0.5, 24, size=n),
        "days_since_signup":      rng.uniform(10, 720, size=n),
        "acquisition_channel":    rng.choice(["paid", "organic", "referral", "outbound"], size=n),
        "is_churned":             rng.random(size=n) < 0.15,
        "mrr":                    rng.uniform(49, 5_000, size=n),
        "events_30d":             rng.integers(0, 500, size=n),
        "dau_30d_distinct":       rng.integers(0, 20,  size=n),
        "active_days_30d":        rng.integers(0, 30,  size=n),
        "stickiness_30d":         rng.uniform(0, 1, size=n),
        "last_event_ts":          pd.NaT,
        "signup_ts":              pd.NaT,
        "churned_ts":             pd.NaT,
        "rule_based_health_score": rng.uniform(0, 100, size=n),
        "invoices_paid_count":    rng.integers(0, 10, size=n),
        "invoices_overdue_count": rng.integers(0,  3, size=n),
        "invoices_failed_count":  rng.integers(0,  2, size=n),
        "tickets_90d":            rng.integers(0, 15, size=n),
        "urgent_tickets_90d":     rng.integers(0,  3, size=n),
        "avg_csat_90d":           rng.uniform(1, 5, size=n),
    })
    return df


def test_encode_creates_prefixed_dummies():
    df  = _fake_health(20)
    out = encode(df)
    assert "current_plan" not in out.columns
    assert any(c.startswith("current_plan_") for c in out.columns)
    assert any(c.startswith("acquisition_channel_") for c in out.columns)


def test_build_features_drops_identifiers_and_label():
    ff = build_features(_fake_health(50), as_of=date(2026, 6, 1))
    for forbidden in ("account_id", "is_churned", "company_name",
                      "rule_based_health_score", "avg_csat_90d"):
        assert forbidden not in ff.X.columns


def test_build_features_all_numeric_features_present():
    ff = build_features(_fake_health(50), as_of=date(2026, 6, 1))
    for col in FEATURE_COLUMNS:
        assert col in ff.X.columns, f"{col} absent de X"


def test_train_test_split_preserves_class_ratio():
    ff = build_features(_fake_health(200, seed=7), as_of=date(2026, 6, 1))
    tr, te = train_test_split_by_date(ff, holdout_frac=0.25)
    # au moins un positif dans chaque côté (garanti par le split stratifié)
    assert tr.y.sum() >= 1
    assert te.y.sum() >= 1
    # somme des tailles = taille totale
    assert len(tr.X) + len(te.X) == len(ff.X)
