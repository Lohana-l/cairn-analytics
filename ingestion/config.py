"""Paramètres de configuration pilotés par les variables d'environnement, partagés par ingestion, ML et API."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache


def reporting_date() -> date:
    """Date de référence du jeu de données synthétique.

    Source unique pour tout le code Python (seed, ML, monitoring). Le seed
    génère l'historique en remontant depuis cette date, et les features ML
    sont coupées à cette même date. Doit rester alignée avec la var
    `reporting_date` de dbt/dbt_project.yml, qui joue le même rôle côté SQL.

    Surchargable par CAIRN_REPORTING_DATE pour rejouer le pipeline à une
    autre date sans toucher au code.
    """
    return date.fromisoformat(os.getenv("CAIRN_REPORTING_DATE", "2026-06-01"))


@dataclass(frozen=True)
class Settings:
    # Valeurs lues a l'INSTANCIATION (default_factory), pas a l'import du module.
    # Indispensable : du code qui definit les variables d'environnement APRES
    # l'import (ex. les tests testcontainers) doit etre pris en compte. Avec un
    # simple `= os.getenv(...)`, les defauts seraient figes au 1er import.
    pg_host:     str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    pg_port:     int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    pg_user:     str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "cairn"))
    pg_password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "password"))
    pg_db:       str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "cairn"))

    mlflow_tracking_uri: str = field(default_factory=lambda: os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
    mlflow_experiment:   str = field(default_factory=lambda: os.getenv("MLFLOW_EXPERIMENT", "cairn-churn"))

    model_dir: str = field(default_factory=lambda: os.getenv("CAIRN_MODEL_DIR", "ml/models"))

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
