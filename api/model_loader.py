"""Chargeur de modèle singleton : chargé une fois au démarrage de FastAPI.

Choix assumé : l'API sert le pickle local de ``CAIRN_MODEL_DIR`` et n'interroge
jamais le MLflow Registry au runtime. Le registry reste l'audit trail
(versions, stages, lignage) ; le serving n'a aucune dépendance réseau, donc
pas de mode dégradé si MLflow tombe. En production on chargerait
``models:/xgboost_churn_model/Production`` au démarrage, avec ce même pickle
en fallback.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from loguru import logger

from ingestion.config import settings


class ModelBundle:
    model:          Any
    feature_names:  list[str]
    model_name:     str
    model_version:  str
    base_rate:      float
    trained_at:     str

    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


_BUNDLE: ModelBundle | None = None


def load_model(model_dir: str | Path | None = None) -> ModelBundle:
    """Charge et met en cache. Sans effet si déjà chargé."""
    global _BUNDLE
    if _BUNDLE is not None:
        return _BUNDLE

    model_dir  = Path(model_dir or settings().model_dir)
    # XGB en priorité, fallback sur ce qui existe
    candidates = sorted(model_dir.glob("churn_*.pkl"))
    xgb_first  = [c for c in candidates if "xgb" in c.name]
    chosen     = (xgb_first + candidates)[0] if candidates else None
    if chosen is None:
        raise FileNotFoundError(f"Aucun modèle sérialisé dans {model_dir}")

    data = pickle.loads(chosen.read_bytes())
    _BUNDLE = ModelBundle(**data)
    logger.info("Modèle chargé : {} depuis {}", _BUNDLE.model_name, chosen)
    return _BUNDLE


def reset() -> None:
    """Tests uniquement : force le prochain appel à load_model() à relire depuis le disque."""
    global _BUNDLE
    _BUNDLE = None
