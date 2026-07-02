"""Application FastAPI : service de prédiction du churn Cairn.

Lancement (dans le conteneur) :
    uvicorn api.main:app --host 0.0.0.0 --port 8000

Endpoints
---------
GET  /health          : liveness + statut modèle + statut DB
GET  /model/info      : métadonnées du modèle chargé
POST /predict/churn   : prédiction unitaire (outillage CSM temps réel)
POST /batch/predict   : bulk (Streamlit / sync CRM)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator

from api.model_loader import load_model
from api.schemas import (
    AccountFeatures,
    BatchPredictRequest,
    BatchPredictResponse,
    HealthResponse,
    ModelInfoResponse,
    PredictionResponse,
)
from ingestion.db import pg_conn
from ml.tiering import tier_from_probability


# ----------------------------------------------------------------------
# Lifespan : chargement eager pour éviter le cold start sur la 1re requête
# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        load_model()
    except FileNotFoundError as exc:
        logger.warning("Modèle pas encore entraîné : {}", exc)
    yield


app = FastAPI(
    title="Cairn Churn API",
    version="1.0.0",
    description="Churn risk scoring for SaaS B2B accounts.",
    lifespan=lifespan,
)

# ----------------------------------------------------------------------
# Observabilité : métriques Prometheus sur /metrics (scrape toutes les 15s)
#   - http_request_duration_seconds  (histogram)
#   - http_requests_total            (counter)
#   - http_request_size_bytes        (summary)
# ----------------------------------------------------------------------
Instrumentator(
    excluded_handlers=["/metrics", "/health"],
    should_group_status_codes=True,
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _features_to_frame(features: list[AccountFeatures], feature_names: list[str]) -> pd.DataFrame:
    """Transforme une liste d'AccountFeatures en DataFrame aligné sur les colonnes attendues par le modèle.

    Les colonnes one-hot manquantes deviennent 0, les extras sont supprimées.
    """
    from ml.features import encode

    df  = pd.DataFrame([f.model_dump() for f in features])
    df  = encode(df)
    df  = df.reindex(columns=feature_names, fill_value=0)
    return df


def _top_drivers(bundle, X: pd.DataFrame) -> list[list[dict] | None]:
    """Drivers SHAP best-effort : None si le modèle n'est pas en arbres ou si shap est absent."""
    if bundle.model_name != "xgb":
        return [None] * len(X)
    try:
        from ml.shap_explain import explain_xgboost, top_drivers_per_row
        sv, _ = explain_xgboost(bundle.model, X)
        return top_drivers_per_row(sv, X, top_n=3)
    except Exception as exc:
        logger.warning("SHAP échoué : {}", exc)
        return [None] * len(X)


def _predict(features: list[AccountFeatures]) -> list[PredictionResponse]:
    bundle = load_model()
    X      = _features_to_frame(features, bundle.feature_names)
    probs  = bundle.model.predict_proba(X)[:, 1]
    drivers = _top_drivers(bundle, X)

    out: list[PredictionResponse] = []
    for i, f in enumerate(features):
        out.append(PredictionResponse(
            account_id=f.account_id,
            churn_risk_score=float(round(probs[i] * 100, 2)),
            # Seuils absolus partagés (ml.tiering) : une prédiction unitaire
            # n'a pas de contexte portefeuille pour un rang par quantile.
            churn_risk_tier=tier_from_probability(float(probs[i])),
            model_name=bundle.model_name,
            model_version=bundle.model_version,
            top_drivers=[d for d in (drivers[i] or [])],
        ))
    return out


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
def health():
    model_ok = True
    model_name = None
    model_version = None
    try:
        b = load_model()
        model_name    = b.model_name
        model_version = b.model_version
    except Exception:
        model_ok = False

    db_ok = True
    try:
        with pg_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if (model_ok and db_ok) else "degraded",
        model_loaded=model_ok,
        db_reachable=db_ok,
        model_name=model_name,
        model_version=model_version,
    )


@app.get("/model/info", response_model=ModelInfoResponse)
def model_info():
    try:
        b = load_model()
    except FileNotFoundError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return ModelInfoResponse(
        model_name=b.model_name,
        model_version=b.model_version,
        trained_at=b.trained_at,
        feature_names=b.feature_names,
        base_rate=b.base_rate,
        n_features=len(b.feature_names),
    )


@app.post("/predict/churn", response_model=PredictionResponse)
def predict_churn(features: AccountFeatures):
    try:
        return _predict([features])[0]
    except FileNotFoundError as exc:
        raise HTTPException(503, detail=f"Modèle non chargé : {exc}") from exc


@app.post("/batch/predict", response_model=BatchPredictResponse)
def batch_predict(req: BatchPredictRequest):
    if len(req.accounts) == 0:
        raise HTTPException(400, detail="accounts list is empty")
    if len(req.accounts) > 5_000:
        raise HTTPException(413, detail="batch limited to 5,000 accounts; chunk on client")
    preds = _predict(req.accounts)
    return BatchPredictResponse(predictions=preds, count=len(preds))
