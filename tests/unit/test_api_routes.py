"""Tests unitaires routes FastAPI : modèle et DB patchés, pas d'I/O réel."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def fake_bundle():
    b = MagicMock()
    b.model_name     = "logreg"        # SHAP non calculé pour logreg
    b.model_version  = "1.0.0"
    b.base_rate      = 0.08
    b.trained_at     = "2026-06-01"
    b.feature_names  = [
        "mrr", "tenure_months", "days_since_signup", "current_seats",
        "events_30d", "dau_30d_distinct", "active_days_30d", "stickiness_30d",
        "invoices_paid_count", "invoices_overdue_count", "invoices_failed_count",
        "tickets_90d", "urgent_tickets_90d",
    ]
    model        = MagicMock()
    model.predict_proba.return_value = np.array([[0.2, 0.8]])
    b.model      = model
    return b


@pytest.fixture
def client(fake_bundle):
    # patch avant l'import de app pour éviter l'erreur de chargement eager
    with patch("api.main.load_model", return_value=fake_bundle), \
         patch("api.main.pg_conn") as pg:
        pg.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value \
            .fetchone.return_value = (1,)
        from api.main import app
        yield TestClient(app)


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["db_reachable"] is True


def test_model_info(client):
    r = client.get("/model/info")
    assert r.status_code == 200
    body = r.json()
    assert body["model_name"]  == "logreg"
    assert body["n_features"]  == 13
    assert body["base_rate"]   == pytest.approx(0.08)


def test_predict_churn_single(client, fake_bundle):
    fake_bundle.model.predict_proba.return_value = np.array([[0.1, 0.9]])
    payload = {"account_id": "acc_demo", "mrr": 499, "tenure_months": 3.0,
               "stickiness_30d": 0.1}
    r = client.post("/predict/churn", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["churn_risk_score"] == 90.0
    assert body["churn_risk_tier"]  == "critical"
    assert body["model_name"]       == "logreg"


def test_batch_predict_rejects_empty(client):
    r = client.post("/batch/predict", json={"accounts": []})
    assert r.status_code == 400


def test_batch_predict_rejects_too_large(client, fake_bundle):
    # 413 déclenché avant predict_proba (vérification purement endpoint)
    big = [{"account_id": f"acc_{i}"} for i in range(5_001)]
    r = client.post("/batch/predict", json={"accounts": big})
    assert r.status_code == 413


def test_batch_predict_happy_path(client, fake_bundle):
    fake_bundle.model.predict_proba.return_value = np.array([[0.5, 0.5], [0.7, 0.3]])
    payload = {"accounts": [
        {"account_id": "acc_1"},
        {"account_id": "acc_2", "current_plan": "pro"},
    ]}
    r = client.post("/batch/predict", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert body["predictions"][0]["account_id"] == "acc_1"
    assert body["predictions"][1]["churn_risk_score"] == 30.0
