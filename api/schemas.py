"""Schémas Pydantic requête/réponse pour l'API churn."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RiskTier = Literal["low", "medium", "high", "critical"]


class AccountFeatures(BaseModel):
    """Payload pour /predict/churn. Miroir du jeu de features ML."""
    account_id:             str          = Field(..., examples=["acc_abc123"])
    mrr:                    float        = 0.0
    tenure_months:          float        = 0.0
    days_since_signup:      float        = 0.0
    current_seats:          int          = 0
    events_30d:             int          = 0
    dau_30d_distinct:       int          = 0
    active_days_30d:        int          = 0
    stickiness_30d:         float        = 0.0
    invoices_paid_count:    int          = 0
    invoices_overdue_count: int          = 0
    invoices_failed_count:  int          = 0
    tickets_90d:            int          = 0
    urgent_tickets_90d:     int          = 0
    current_plan:           Literal["starter", "pro", "enterprise"] = "starter"
    acquisition_channel:    Literal["paid", "organic", "referral", "outbound"] = "organic"
    industry:               str          = "Other"


class Driver(BaseModel):
    feature:   str
    value:     float | int | str | None
    shap:      float
    direction: Literal["↑ risk", "↓ risk"]


class PredictionResponse(BaseModel):
    account_id:       str
    churn_risk_score: float    = Field(..., ge=0, le=100)
    churn_risk_tier:  RiskTier
    model_name:       str
    model_version:    str
    top_drivers:      list[Driver] = []


class BatchPredictRequest(BaseModel):
    accounts: list[AccountFeatures]


class BatchPredictResponse(BaseModel):
    predictions: list[PredictionResponse]
    count:       int


class HealthResponse(BaseModel):
    status:             Literal["ok", "degraded"]
    model_loaded:       bool
    db_reachable:       bool
    model_name:         str | None = None
    model_version:      str | None = None


class ModelInfoResponse(BaseModel):
    model_name:       str
    model_version:    str
    trained_at:       str
    feature_names:    list[str]
    base_rate:        float
    n_features:       int
