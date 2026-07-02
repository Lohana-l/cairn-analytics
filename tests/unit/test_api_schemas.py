"""Tests unitaires api.schemas : validation Pydantic cas nominaux et cas d'erreur."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas import (
    AccountFeatures,
    BatchPredictRequest,
    PredictionResponse,
)


def test_account_features_accepts_defaults():
    f = AccountFeatures(account_id="acc_x")
    assert f.current_plan == "starter"
    assert f.acquisition_channel == "organic"


def test_account_features_rejects_invalid_plan():
    with pytest.raises(ValidationError):
        AccountFeatures(account_id="acc_x", current_plan="ultra-premium")


def test_account_features_rejects_invalid_channel():
    with pytest.raises(ValidationError):
        AccountFeatures(account_id="acc_x", acquisition_channel="instagram")


def test_batch_predict_request_allows_empty_then_api_validates():
    # le schéma Pydantic accepte une liste vide ; c'est l'endpoint qui renvoie 400
    req = BatchPredictRequest(accounts=[])
    assert len(req.accounts) == 0


def test_batch_predict_request_accepts_single_account():
    req = BatchPredictRequest(accounts=[AccountFeatures(account_id="acc_1")])
    assert len(req.accounts) == 1
    assert req.accounts[0].account_id == "acc_1"


def test_prediction_response_score_bounds():
    ok = PredictionResponse(
        account_id="acc_x",
        churn_risk_score=50.0,
        churn_risk_tier="medium",
        model_name="xgb",
        model_version="1.0.0",
    )
    assert ok.churn_risk_tier == "medium"
    with pytest.raises(ValidationError):
        PredictionResponse(
            account_id="acc_x",
            churn_risk_score=150.0,        # hors plage [0, 100]
            churn_risk_tier="high",
            model_name="xgb",
            model_version="1.0.0",
        )
