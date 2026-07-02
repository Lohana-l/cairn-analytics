"""Point d'entrée CLI : python -m ingestion.main --raw-dir data/raw"""
from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from ingestion.loaders import load_csv

# ordre respectant les FK
_ORDER = ["accounts", "subscriptions", "invoices", "events", "tickets"]


def run(raw_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in _ORDER:
        path = raw_dir / f"{name}.csv"
        if not path.exists():
            logger.warning("  {} introuvable, ignoré", path)
            continue
        counts[name] = load_csv(path, name)
    logger.success("Ingestion terminée : {}", counts)
    return counts


def main() -> None:
    p = argparse.ArgumentParser(description="Cairn CSV vers Postgres loader")
    p.add_argument("--raw-dir", default="data/raw", type=Path)
    args = p.parse_args()
    run(args.raw_dir)


if __name__ == "__main__":
    main()
