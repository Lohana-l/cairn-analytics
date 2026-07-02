"""Paramètres configurables du générateur.

Ici plutôt que dans le CLI : les tests unitaires peuvent ainsi importer
et vérifier les distributions exactes qu'on échantillonne.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedConfig:
    # volumes : tient en RAM sur un laptop, assez grand pour rester représentatif
    n_accounts:         int = 2_000
    events_per_account: int = 120       # moyenne : distribution Poisson-ish
    invoices_months:    int = 18        # une facture par mois sur 18 mois max

    # fenêtre temporelle (ancrée au "now" de la machine au moment du seed)
    horizon_days_back:  int = 540       # ~18 mois d'historique

    # mix comportemental : 8% de churn (standard B2B SaaS sain).
    # On laisse les "tiers" ML s'attribuer par quantile (top 5% critical, 6-15% high,
    # 16-30% medium) plutôt que par seuils absolus, pour rester robuste à la calibration
    # du modèle quel que soit le taux de base de churn réel des données.
    churn_rate:                 float = 0.08
    paid_acquisition_share:     float = 0.35
    organic_acquisition_share:  float = 0.40
    referral_acquisition_share: float = 0.15
    outbound_acquisition_share: float = 0.10

    # mix de plans, pondéré par ARPU
    plan_mix_starter:    float = 0.55   # 49 $ / siège
    plan_mix_pro:        float = 0.33   # 149 $ / siège
    plan_mix_enterprise: float = 0.12   # 499 $ / siège

    # forme de l'engagement : décroissance exponentielle vers le churn
    engagement_decay_half_life_days: int = 90

    # support : biaisé, la plupart des comptes ont 0-3 tickets, queue jusqu'à ~30
    tickets_lambda:      float = 2.0

    # déterminisme
    seed: int = 42
