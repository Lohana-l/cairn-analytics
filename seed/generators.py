"""Générateurs Faker par entité.

Chaque fonction renvoie un DataFrame pandas indexé par la PK de la table raw.
Les générateurs sont déterministes pour un ``SeedConfig.seed`` donné.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_DNS, uuid5

import numpy as np
import pandas as pd
from faker import Faker

from ingestion.config import reporting_date
from seed.config import SeedConfig


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _faker(cfg: SeedConfig) -> Faker:
    """Faker seedé : produit toujours le même flux pour une même config."""
    f = Faker(["en_US", "fr_FR", "de_DE"])
    Faker.seed(cfg.seed)
    return f


def _stable_id(prefix: str, *parts: str) -> str:
    """UUID5 déterministe : mêmes entrées, même id, re-seeding idempotent."""
    return f"{prefix}_{uuid5(NAMESPACE_DNS, '|'.join(parts)).hex[:12]}"


def _now(cfg: SeedConfig) -> datetime:
    # "now" figé pour que les tests soient reproductibles d'un jour à l'autre.
    # Source unique : ingestion.config.reporting_date (alignée sur la var dbt).
    d = reporting_date()
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


# ----------------------------------------------------------------------
# accounts
# ----------------------------------------------------------------------
def gen_accounts(cfg: SeedConfig) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.seed)
    fake = _faker(cfg)
    now = _now(cfg)

    industries = ["FinTech", "E-commerce", "Media", "EdTech", "Logistics",
                  "Manufacturing", "PropTech", "HR Tech"]
    countries  = ["US", "FR", "DE", "UK", "ES", "IT", "CA", "NL"]

    rows: list[dict] = []
    for i in range(cfg.n_accounts):
        signup_offset_days = int(rng.uniform(1, cfg.horizon_days_back))
        signup_ts          = now - timedelta(days=signup_offset_days)
        account_id         = _stable_id("acc", str(i))

        plan = rng.choice(
            ["starter", "pro", "enterprise"],
            p=[cfg.plan_mix_starter, cfg.plan_mix_pro, cfg.plan_mix_enterprise],
        )
        seats = {
            "starter":    int(rng.integers(1, 10)),
            "pro":        int(rng.integers(5, 50)),
            "enterprise": int(rng.integers(25, 500)),
        }[plan]

        acq = rng.choice(
            ["paid", "organic", "referral", "outbound"],
            p=[cfg.paid_acquisition_share, cfg.organic_acquisition_share,
               cfg.referral_acquisition_share, cfg.outbound_acquisition_share],
        )

        # churn plus probable sur starter + acquisition paid
        base_p = cfg.churn_rate
        if plan == "starter":
            base_p *= 1.5
        if plan == "enterprise":
            base_p *= 0.4
        if acq == "paid":
            base_p *= 1.3
        churned = rng.random() < min(base_p, 0.4)

        churned_ts = None
        if churned:
            # le churn se produit entre 30 jours après signup et maintenant
            min_churn = signup_ts + timedelta(days=30)
            if min_churn < now:
                span_days  = max((now - min_churn).days, 1)
                churned_ts = min_churn + timedelta(days=int(rng.integers(0, span_days)))

        rows.append({
            "account_id":     account_id,
            "company_name":   fake.company(),
            "industry":       industries[int(rng.integers(0, len(industries)))],
            "country":        countries[int(rng.integers(0, len(countries)))],
            "plan":           plan,
            "seats":          seats,
            "signup_ts":      signup_ts,
            "churned_ts":     churned_ts,
            "acquisition_ch": acq,
        })

    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# subscriptions : une ligne active par compte + changements de plan historiques
# ----------------------------------------------------------------------
_PLAN_PRICE = {"starter": 49, "pro": 149, "enterprise": 499}


def gen_subscriptions(accounts: pd.DataFrame, cfg: SeedConfig) -> pd.DataFrame:
    """Abonnement d'ouverture + changements de plan (upsell / downgrade).

    Les changements sont tirés UNIFORMÉMENT sur toute la vie du compte (pas
    seulement les 12 premiers mois) : chaque mois calendaire, dernier compris,
    reçoit ainsi des expansions ET des contractions - le waterfall MRR du mois
    courant n'est jamais à zéro sur ces composantes.

    Signal précurseur : une partie des comptes churnés downgradent avant de
    partir (contraction observable par le modèle dans la fenêtre pré-churn).
    """
    rng = np.random.default_rng(cfg.seed + 1)
    now = _now(cfg)
    rows: list[dict] = []

    for _, acc in accounts.iterrows():
        valid_from  = acc.signup_ts
        plan, seats = acc.plan, acc.seats
        # ATTENTION : pandas convertit None en NaT dans une colonne datetime,
        # donc `churned_ts is None` est TOUJOURS faux ici. C'était le bug qui
        # supprimait tous les upsells (waterfall avec expansion = 0 €).
        is_churned  = pd.notna(acc.churned_ts)
        end_of_life = acc.churned_ts if is_churned else now
        life_days   = max((end_of_life - valid_from).days, 1)

        # ── tirage des changements de plan sur la vie du compte ─────────────
        changes: list[tuple[int, str]] = []          # (jour, "up"|"down")
        if not is_churned:
            # comptes actifs : 25% upsell, 12% downgrade, possibles partout
            if life_days > 120 and rng.random() < 0.25:
                changes.append((int(rng.integers(90, life_days)), "up"))
            if life_days > 150 and rng.random() < 0.12:
                changes.append((int(rng.integers(120, life_days)), "down"))
        else:
            # 20% des churners réduisent la voilure avant de partir
            if life_days > 75 and rng.random() < 0.20:
                changes.append((int(rng.integers(45, life_days - 15)), "down"))

        # ordre chronologique + espacement minimal de 30 jours entre 2 changements
        changes.sort()
        spaced: list[tuple[int, str]] = []
        for day, kind in changes:
            if not spaced or day - spaced[-1][0] >= 30:
                spaced.append((day, kind))

        # ── chaînage des abonnements successifs ──────────────────────────────
        cursor = valid_from
        for day, kind in spaced:
            change_ts = valid_from + timedelta(days=day)
            rows.append({
                "subscription_id": _stable_id("sub", acc.account_id, cursor.isoformat()),
                "account_id":      acc.account_id,
                "plan":            plan,
                "seats":           seats,
                "mrr":             round(seats * _PLAN_PRICE[plan], 2),
                "valid_from":      cursor,
                "valid_to":        change_ts,
            })
            if kind == "up":
                # upsell : sièges +30-80%, montée de gamme
                seats = int(seats * rng.uniform(1.3, 1.8))
                plan  = "pro" if plan == "starter" else "enterprise"
            else:
                # downgrade : sièges -20-50%, plan conservé (contraction pure)
                seats = max(int(seats * rng.uniform(0.5, 0.8)), 1)
            cursor = change_ts

        # dernier abonnement : ouvert jusqu'au churn (ou toujours actif)
        rows.append({
            "subscription_id": _stable_id("sub", acc.account_id, cursor.isoformat()),
            "account_id":      acc.account_id,
            "plan":            plan,
            "seats":           seats,
            "mrr":             round(seats * _PLAN_PRICE[plan], 2),
            "valid_from":      cursor,
            "valid_to":        acc.churned_ts if is_churned else None,
        })

    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# invoices : facturation mensuelle dérivée de l'abonnement actif
# ----------------------------------------------------------------------
def gen_invoices(subs: pd.DataFrame, cfg: SeedConfig) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.seed + 2)
    now = _now(cfg)
    rows: list[dict] = []

    for _, s in subs.iterrows():
        cursor = s.valid_from
        end    = s.valid_to if pd.notna(s.valid_to) else now
        idx    = 0
        while cursor < end:
            issued_ts = cursor
            # 95% payé à temps, 3% en retard, 2% échoué
            roll      = rng.random()
            if   roll < 0.95:
                status, paid_ts = "paid",    issued_ts + timedelta(days=int(rng.integers(0, 7)))
            elif roll < 0.98:
                status, paid_ts = "overdue", issued_ts + timedelta(days=int(rng.integers(30, 60)))
            else:
                status, paid_ts = "failed",  None

            rows.append({
                "invoice_id": _stable_id("inv", s.subscription_id, str(idx)),
                "account_id": s.account_id,
                "amount":     s.mrr,
                "issued_ts":  issued_ts,
                "paid_ts":    paid_ts,
                "status":     status,
            })
            cursor += timedelta(days=30)
            idx    += 1

    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# events : usage produit (login, feature_use, export, invite)
# ----------------------------------------------------------------------
_EVENT_TYPES = ["login", "feature_use", "export", "invite_user", "dashboard_view"]


def gen_events(accounts: pd.DataFrame, cfg: SeedConfig) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.seed + 3)
    now = _now(cfg)
    rows: list[dict] = []

    for _, acc in accounts.iterrows():
        start = acc.signup_ts
        end   = acc.churned_ts if pd.notna(acc.churned_ts) else now
        days  = max((end - start).days, 1)

        # les comptes qui churned ralentissent : décroissance exponentielle vers la date de churn
        n_events = int(rng.poisson(cfg.events_per_account * (days / 365)))
        if n_events == 0:
            continue

        if pd.notna(acc.churned_ts):
            # Décroissance de l'engagement avant le churn : on tire un pool de
            # jours candidats, puis on échantillonne avec un poids qui chute à
            # l'approche de la date de churn. Résultat : les événements se
            # raréfient sur les dernières semaines, le signal précurseur que
            # le modèle est censé apprendre existe vraiment dans les données.
            n_pool    = n_events * 4
            day_pool  = rng.integers(0, days, size=n_pool)
            t_before  = days - day_pool          # jours restant avant le churn
            weights   = 1.0 - np.exp(-t_before / cfg.engagement_decay_half_life_days)
            weights  += 1e-9                     # évite une somme nulle
            idx       = rng.choice(
                n_pool, size=n_events, replace=False,
                p=weights / weights.sum(),
            )
            ts_pool = start + pd.to_timedelta(day_pool[idx], unit="D")
            ts_pool = ts_pool + pd.to_timedelta(
                rng.integers(0, 24 * 3600, size=n_events), unit="s"
            )
        else:
            ts_pool = start + pd.to_timedelta(
                rng.integers(0, days * 24 * 3600, size=n_events), unit="s"
            )

        # utilisateurs par compte : ceil(seats / 3), chacun reçoit ~une part uniforme
        n_users  = max(acc.seats // 3, 1)
        user_ids = [_stable_id("usr", acc.account_id, str(u)) for u in range(n_users)]

        for j, ts in enumerate(ts_pool):
            rows.append({
                "event_id":   _stable_id("evt", acc.account_id, str(j)),
                "account_id": acc.account_id,
                "user_id":    user_ids[int(rng.integers(0, n_users))],
                "event_type": _EVENT_TYPES[int(rng.integers(0, len(_EVENT_TYPES)))],
                "event_ts":   ts,
                "properties": None,
            })

    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# tickets : volume Poisson, client mécontent occasionnel
# ----------------------------------------------------------------------
def gen_tickets(accounts: pd.DataFrame, cfg: SeedConfig) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.seed + 4)
    now = _now(cfg)
    rows: list[dict] = []
    cats = ["billing", "bug", "feature_request", "onboarding", "integration"]

    for _, acc in accounts.iterrows():
        n = int(rng.poisson(cfg.tickets_lambda))
        if pd.notna(acc.churned_ts):
            n = int(n * 1.8)  # les churners se plaignent plus (signal précurseur réaliste)
        start = acc.signup_ts
        end   = acc.churned_ts if pd.notna(acc.churned_ts) else now
        if end <= start:
            continue
        for k in range(n):
            opened_ts = start + timedelta(
                seconds=int(rng.integers(0, max((end - start).total_seconds(), 1)))
            )
            closed_ts = opened_ts + timedelta(hours=int(rng.integers(1, 240)))
            rows.append({
                "ticket_id":  _stable_id("tkt", acc.account_id, str(k)),
                "account_id": acc.account_id,
                "category":   cats[int(rng.integers(0, len(cats)))],
                "opened_ts":  opened_ts,
                "closed_ts":  closed_ts if closed_ts < now else None,
                "priority":   rng.choice(["low", "medium", "high", "urgent"],
                                         p=[0.5, 0.3, 0.15, 0.05]),
                "csat":       int(rng.integers(1, 6)) if rng.random() < 0.6 else None,
            })

    df = pd.DataFrame(rows)
    df["csat"] = df["csat"].astype(pd.Int64Dtype())
    return df
