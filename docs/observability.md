# Observabilité

Cairn embarque une pile d'observabilité à quatre piliers (**métriques, logs,
dashboards et alertes**) branchée sur le même `docker compose` que le plan de
données. Grafana, Loki et Promtail sont isolés derrière un profil `obs` pour
garder la pile de base légère. Prometheus, en revanche, fait partie de la pile
de base : la page Pipeline de Streamlit y lit la latence de l'API, il doit
donc être actif pour que le dashboard reste entièrement à jour.

```
┌─────────────────┐  scrape  ┌─────────────────┐ requête ┌─────────────────┐
│ FastAPI (api)   │◀─────────│ Prometheus :9090│◀────────│                 │
│  /metrics       │          └─────────────────┘         │                 │
│  prometheus-    │                                       │  Grafana :3200  │
│  fastapi-instr  │  docker  ┌─────────────────┐ requête │  - datasources  │
└─────────────────┘  logs    │ Promtail        │         │    provisionnées│
        │                    │   ↓             │         │  - dashboards   │
        │                    │ Loki :3100      │◀────────│    provisionnés │
        ▼                    └─────────────────┘         │                 │
   stdout/stderr  ◀───────────────  tail  ──────────────▶│                 │
                                                         └─────────────────┘
                                                                 ▲
                                                                 │ SQL
                                                          ┌──────┴──────┐
                                                          │ Postgres    │
                                                          │  marts +    │
                                                          │  analytics  │
                                                          └─────────────┘
```

## Ce que vous obtenez

| Pilier     | Outil                                       | Source                                                    |
|------------|---------------------------------------------|-----------------------------------------------------------|
| Métriques  | Prometheus 2.55                             | FastAPI `/metrics` (latence des requêtes, débit, erreurs) |
| Logs       | Loki 3.3 + Promtail                         | stdout/stderr de tous les conteneurs Docker, étiquetés par conteneur |
| Dashboards | Grafana 11                                  | Auto-provisionnés : SLO de l'API, Pipeline et qualité des données |
| Alertes    | Alerting Grafana                            | Définies dans les dashboards via le provisioning JSON     |

## Lancement

```bash
make observability
# - prometheus :9090 (déjà actif avec la pile de base)
# - grafana    :3200  (admin / admin; accès viewer anonyme également activé)
# - loki       :3100
```

Arrêt avec `make obs-down`. Les volumes (`prometheus_data`, `loki_data`,
`grafana_data`) persistent entre les redémarrages; supprimez-les avec
`docker compose --profile obs down -v` pour repartir de zéro.

## Dashboards provisionnés

Les deux dashboards vivent dans `observability/grafana/dashboards/` et sont
montés en lecture seule dans Grafana. Leur édition via l'interface est
désactivée : modifiez le JSON, redémarrez le conteneur, la nouvelle version
est prise en compte.

### Cairn - Churn API: SLO & Latency

Quatre panneaux stat (req/s, latence p95, taux de 5xx, budget SLO sur
30 jours) pour une cible SLO de 99,5 % sur 30 jours, deux séries temporelles
(percentiles de latence, débit par route) et un panneau de logs Loki filtré
sur `container=cairn_api`.

La requête PromQL derrière la latence p95 :

```promql
histogram_quantile(
  0.95,
  sum by (le) (
    rate(http_request_duration_seconds_bucket{service="churn-api"}[5m])
  )
)
```

### Cairn - Pipeline & Data Quality

Lit directement la source de données Postgres de Cairn. Tuiles stat pour la
taille du dernier lot de prédictions, le nombre de comptes en niveau critical,
le dernier instantané de MRR et le taux de churn logo, plus une tendance MRR
sur 12 mois, un graphique en barres des mouvements de MRR sur 6 mois, le
camembert de santé des comptes et un panneau Loki qui suit les conteneurs
pipeline / prefect / dbt.

## Instrumentation FastAPI

Branchée dans `api/main.py` via `prometheus-fastapi-instrumentator` :

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator(
    excluded_handlers=["/metrics", "/health"],
    should_group_status_codes=True,
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
```

Les buckets d'histogramme par défaut sont calibrés pour des services internes
répondant sous la seconde (5 ms à 2,5 s). Surchargez-les via
`PROMETHEUS_BUCKETS` si vous commencez à servir des prédictions avec démarrage
à froid à travers un WAN.
