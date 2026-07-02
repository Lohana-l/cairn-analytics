"""Point d'entrée CLI : python -m seed.main --output-dir data/raw

Écrit 5 fichiers CSV, un par table raw.*. Idempotent (même seed, mêmes octets).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from seed.config import SeedConfig
from seed.generators import (
    gen_accounts,
    gen_events,
    gen_invoices,
    gen_subscriptions,
    gen_tickets,
)


def run(output_dir: Path, cfg: SeedConfig | None = None) -> None:
    cfg = cfg or SeedConfig()
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Génération de {} comptes (seed={})…", cfg.n_accounts, cfg.seed)
    accounts = gen_accounts(cfg)

    logger.info("Génération des abonnements…")
    subs = gen_subscriptions(accounts, cfg)

    logger.info("Génération des factures…")
    invoices = gen_invoices(subs, cfg)

    logger.info("Génération des événements…")
    events = gen_events(accounts, cfg)

    logger.info("Génération des tickets…")
    tickets = gen_tickets(accounts, cfg)

    for name, df in [
        ("accounts",      accounts),
        ("subscriptions", subs),
        ("invoices",      invoices),
        ("events",        events),
        ("tickets",       tickets),
    ]:
        path = output_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        logger.info("  écrit {:>7,} lignes vers {}", len(df), path)


def main() -> None:
    p = argparse.ArgumentParser(description="Générateur de données synthétiques Cairn")
    p.add_argument("--output-dir", default="data/raw", type=Path)
    p.add_argument("--accounts", type=int, default=None,
                   help="Surcharge SeedConfig.n_accounts")
    p.add_argument("--seed",     type=int, default=None,
                   help="Surcharge SeedConfig.seed (pour isolation de reproductibilité)")
    args = p.parse_args()

    cfg = SeedConfig(
        **{k: v for k, v in {
            "n_accounts": args.accounts,
            "seed":       args.seed,
        }.items() if v is not None}
    )
    run(args.output_dir, cfg)


if __name__ == "__main__":
    main()
