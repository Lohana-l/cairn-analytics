"""Smoke test câblage flows Prefect : subprocess non exécuté, ordre des tâches vérifié."""
from __future__ import annotations

from unittest.mock import patch


def test_daily_refresh_graph_wires_every_task():
    """daily_refresh appelle les 7 tâches dans l'ordre attendu."""
    import flows.flows as f

    call_order: list[str] = []

    def _record(name):
        def _fn(*a, **kw):
            call_order.append(name)
        return _fn

    with patch.object(f, "seed_task",       side_effect=_record("seed")), \
         patch.object(f, "ingest_task",     side_effect=_record("ingest")), \
         patch.object(f, "dbt_build_task",  side_effect=_record("dbt")), \
         patch.object(f, "ge_checks_task",  side_effect=_record("ge")), \
         patch.object(f, "train_task",      side_effect=_record("train")), \
         patch.object(f, "predict_task",    side_effect=_record("predict")), \
         patch.object(f, "evidently_task",  side_effect=_record("evidently")):
        f.daily_refresh(accounts=10)

    assert call_order == ["seed", "ingest", "dbt", "ge",
                          "train", "predict", "evidently"]
