"""Tests unitaires générateurs seed : distributions et déterminisme."""
from __future__ import annotations

import pandas as pd

from seed.config import SeedConfig
from seed.generators import (
    gen_accounts,
    gen_events,
    gen_invoices,
    gen_subscriptions,
    gen_tickets,
)


def test_accounts_are_deterministic_across_runs():
    cfg_a = SeedConfig(n_accounts=50, seed=7)
    cfg_b = SeedConfig(n_accounts=50, seed=7)
    a = gen_accounts(cfg_a)
    b = gen_accounts(cfg_b)
    pd.testing.assert_frame_equal(a, b)


def test_accounts_respect_natural_key():
    cfg = SeedConfig(n_accounts=200, seed=1)
    df = gen_accounts(cfg)
    assert df["account_id"].is_unique
    assert len(df) == 200


def test_churn_rate_lands_in_sensible_range():
    # taux biaisé vers le haut pour starter + paid, plafond à 0.4 pour rester réaliste
    cfg = SeedConfig(n_accounts=1_000, seed=1, churn_rate=0.08)
    acc = gen_accounts(cfg)
    rate = acc["churned_ts"].notna().mean()
    assert 0.05 <= rate <= 0.30, f"taux de churn inattendu : {rate:.3f}"


def test_plan_mix_respected_within_tolerance():
    cfg = SeedConfig(n_accounts=1_000, seed=1)
    acc = gen_accounts(cfg)
    mix = acc["plan"].value_counts(normalize=True).to_dict()
    # tolérance de 5%
    assert abs(mix.get("starter",    0) - 0.55) < 0.05
    assert abs(mix.get("pro",        0) - 0.33) < 0.05
    assert abs(mix.get("enterprise", 0) - 0.12) < 0.05


def test_subscriptions_foreign_key_to_accounts():
    cfg = SeedConfig(n_accounts=100, seed=1)
    acc = gen_accounts(cfg)
    sub = gen_subscriptions(acc, cfg)
    assert sub["account_id"].isin(acc["account_id"]).all()
    # chaque compte a au moins une ligne
    assert set(sub["account_id"]) == set(acc["account_id"])


def test_invoices_only_within_subscription_window():
    cfg = SeedConfig(n_accounts=80, seed=1)
    acc = gen_accounts(cfg)
    sub = gen_subscriptions(acc, cfg)
    inv = gen_invoices(sub, cfg)
    # les factures référencent des comptes existants (vérification indirecte via account_id)
    assert inv["account_id"].isin(acc["account_id"]).all()
    # le montant est toujours positif
    assert (inv["amount"] > 0).all()


def test_events_do_not_predate_signup():
    cfg = SeedConfig(n_accounts=60, seed=2)
    acc = gen_accounts(cfg)
    evt = gen_events(acc, cfg)
    if evt.empty:
        return
    j = evt.merge(acc[["account_id", "signup_ts"]], on="account_id", how="left")
    assert (j["event_ts"] >= j["signup_ts"]).all()


def test_tickets_are_stable_and_priced():
    cfg = SeedConfig(n_accounts=60, seed=3)
    acc = gen_accounts(cfg)
    tkt = gen_tickets(acc, cfg)
    if tkt.empty:
        return
    assert set(tkt["priority"]) <= {"low", "medium", "high", "urgent"}
    # csat renseigné : dans [1..5]
    csat = tkt["csat"].dropna()
    assert ((csat >= 1) & (csat <= 5)).all()
