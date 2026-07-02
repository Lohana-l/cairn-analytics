# Modélisation ML : prédiction du churn

## 1. Cadrage du problème

**Tâche.** Classification binaire : le compte *a* va-t-il churner dans les 90
prochains jours, à la date de reporting *t* ?

**Classe positive.** `subscription.status IN ('churned','cancelled')` AND
`subscription.ended_at BETWEEN t AND t + 90 days`.

**Unité d'observation.** Une ligne par `(account_id, t)`. À l'entraînement,
*t* avance mois par mois sur les 18 derniers mois pour générer ~36 k
observations étiquetées.

**Pourquoi 90 jours ?** Assez court pour que le CS puisse agir sur la liste ;
assez long pour que le taux de positifs (~8 %) reste modélisable. Un horizon
de 30 jours donnait un taux de positifs inférieur à 3 %, trop proche du seuil
opérationnel pour battre un score à base de règles. Un horizon de 180 jours
brouillait la question "pourquoi maintenant ?" à laquelle le CS doit
répondre.

## 2. Features

Toutes les features proviennent de `mart_account_health`. La liste des
features est figée dans `ml/features.py::FEATURE_COLUMNS` :

### 2.1 Numériques (13)

| Feature                    | Sémantique                                    | Fait source                |
|----------------------------|-----------------------------------------------|----------------------------|
| `tenure_months`            | Mois écoulés depuis l'inscription             | `dim_account`              |
| `days_since_signup`        | Jours bruts                                   | `dim_account`              |
| `current_mrr`              | MRR à la date *t*                             | `fct_mrr_monthly`          |
| `mrr_trend_90d`            | Pente du MRR sur les 90 derniers jours        | `fct_mrr_movements`        |
| `expansion_count_180d`     | Événements d'upgrade sur les 180 derniers jours | `fct_mrr_movements`      |
| `contraction_count_180d`   | Événements de downgrade sur les 180 derniers jours | `fct_mrr_movements`   |
| `active_days_30d`          | Jours distincts avec ≥1 événement             | `fct_engagement_daily`     |
| `active_days_90d`          | Idem, sur 90 jours                            | `fct_engagement_daily`     |
| `stickiness_30_90`         | `active_days_30d / active_days_90d`           | `fct_engagement_daily`     |
| `seats_active`             | Sièges avec ≥1 événement sur les 30 derniers jours | `fct_engagement_daily` |
| `tickets_open`             | Tickets de support actuellement ouverts       | `fct_tickets_monthly`      |
| `avg_csat_90d`             | CSAT moyen des tickets résolus, 90 derniers jours | `fct_tickets_monthly`  |
| `failed_invoice_count_90d` | Nombre de factures en échec, 90 derniers jours | `int_billing_history`     |

### 2.2 Catégorielles (3) : encodées en one-hot

| Feature                | Domaine                                               |
|------------------------|-------------------------------------------------------|
| `current_plan`         | `starter`, `pro`, `enterprise`                        |
| `acquisition_channel`  | `organic`, `paid_search`, `referral`, `outbound`, `partner` |
| `industry`             | 8 segments SaaS horizontaux (issus de `dim_industry`) |

### 2.3 Garde-fou contre le leakage (fuite de données cible)

Toutes les features sont évaluées **à la date** *t* : aucun événement
postérieur à *t* n'est visible. Cette règle est appliquée dans
`build_features()` en filtrant chaque table intermédiaire sur
`<= reporting_date`. La fenêtre de labellisation (*t*, *t*+90j) n'est
interrogée que pour construire `y`, jamais pour construire `X`.

Le test dbt singulier `assert_no_future_events` empêche toute ligne dont
l'horodatage dépasse `var('reporting_date')` d'entrer dans
`fct_engagement_daily` : une seconde ligne de défense.

## 3. Stratégie de découpage

Temporel, stratifié :

```python
train_test_split_by_date(
    X, y, reporting_date,
    validation_months=3,   # les mois (t-3, t-2, t-1) deviennent la validation
    test_months=3,         # les mois (t-6, t-5, t-4) deviennent le test
)
```

Un k-fold aléatoire fuirait, car le même compte apparaît à plusieurs dates de
reporting. Le découpage se fait **par compte × période**, et au sein de
chaque partition on stratifie sur le taux de positifs afin que l'équilibre
des classes reste stable.

## 4. Modèles

### 4.1 Régression logistique (baseline)

* `StandardScaler` sur les numériques, passage direct pour les variables
  indicatrices.
* `LogisticRegression(class_weight="balanced", max_iter=1000, C=1.0)`.
* Raison de son maintien en production : des coefficients inspectables, des
  probabilités bien calibrées, et un plancher que tout challenger doit
  battre. C'est aussi le modèle que la CI exécute sur un tout petit
  échantillon pour vérifier le chemin d'entraînement complet (les
  compilations XGBoost sont lentes).

### 4.2 XGBoost (challenger)

```python
XGBClassifier(
    n_estimators=500,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=11,       # ≈ ratio négatifs/positifs à 8 % de positifs
    eval_metric="aucpr",
    early_stopping_rounds=25,
    tree_method="hist",
)
```

Choisi parce que, sur des données tabulaires de churn SaaS, les GBDT avec un
`scale_pos_weight` bien réglé dominent tout ce qui n'exige pas un jeu de
données plus grand que ce que nous pouvons générer.

### 4.3 Barrière champion / challenger

`ml.train` :

1. Entraîne les deux modèles, calcule `metrics.full_report` sur la tranche de
   test.
2. Trie par `pr_auc` (décroissant).
3. Sauvegarde le gagnant sous `ml/models/churn_<name>.pkl` avec un
   dictionnaire de métadonnées (noms des features, version du modèle dérivée
   de la date d'entraînement, taux de base, horodatage d'entraînement).
4. Journalise les deux runs dans MLflow ; le modèle XGBoost est enregistré
   sous `xgboost_churn_model` et promu automatiquement au stage `Production`
   (les versions précédentes sont archivées).
5. Le serving lit délibérément le pickle local, pas le registre : le registre
   est la piste d'audit, le pickle est l'artefact de déploiement (aucune
   dépendance réseau sur le chemin d'inférence).

Résultat sur le seed de référence : PR-AUC ~0.58 pour la régression
logistique, PR-AUC ~0.71 pour XGBoost.

## 5. Métriques

`ml/metrics.py::full_report` retourne un dictionnaire contenant :

| Métrique       | Pourquoi                                                            |
|----------------|---------------------------------------------------------------------|
| `roc_auc`      | Qualité de l'ordonnancement des scores ; indépendante du seuil.      |
| **`pr_auc`**   | **Métrique principale.** Robuste au déséquilibre des classes (8 % de positifs). |
| `brier`        | Qualité de la calibration ; critique parce que les déclencheurs CS reposent sur des bandes de score. |
| `ks`           | Statistique KS entre les distributions de scores ; complète le ROC-AUC. |
| `precision@50` | Sur les 50 comptes les mieux scorés, combien churnent réellement ? C'est la liste d'appels quotidienne du CS. |
| `precision@100`| Idem, pour la liste hebdomadaire.                                    |

`roc_auc` et `pr_auc` sont livrés avec des **intervalles de confiance
bootstrap à 95 %** (`*_ci_low` / `*_ci_high`, 1 000 rééchantillonnages) :
avec une tranche de test d'environ 80 comptes et environ 8 churners, une
estimation ponctuelle seule surestimerait la certitude.

Un modèle moins bon sur le Brier mais meilleur sur la PR-AUC n'est **pas**
promu automatiquement : les seuils de tiering supposent une bonne
calibration.

## 6. Explications SHAP

`ml/shap_explain.py` :

* `explain_xgboost()` : `shap.TreeExplainer` (rapide, exact).
* `top_drivers_per_row()` : pour chaque compte, sélectionne les 3 features à
  la plus forte valeur SHAP absolue, annotées avec la direction :
  * `"↑ risk"` : la feature augmente la probabilité de churn (SHAP positif).
  * `"↓ risk"` : la feature la diminue (SHAP négatif).
* `global_importance()` : moyenne des valeurs SHAP absolues sur le jeu
  d'entraînement, utilisée dans la page Monitoring.

Les drivers sont sérialisés en JSONB dans
`analytics.churn_predictions.top_drivers` au moment de la prédiction, si bien
que la table de risque de churn dans Streamlit et la réponse FastAPI lisent
la même explication canonique, ligne par ligne. Pas de recalcul, pas de
divergence entre les interfaces.

## 7. Exploitation du modèle

### 7.1 Tiering

Un module partagé unique, `ml/tiering.py`, porte les deux granularités de
tiering :

* **Batch (`ml.predict`, la source de vérité du dashboard)** : classement par
  rang dans le portefeuille complet (top 5 % critical, 6 à 15 % high, 16 à
  30 % medium). C'est la convention des CSM : faire remonter les "N comptes à
  appeler en priorité", indépendamment de la calibration absolue du modèle.
* **Appels API unitaires** : seuils de probabilité absolus, parce qu'une
  prédiction isolée n'a pas de portefeuille face auquel être classée :

| Plage de score | Tier       | Action CS typique           |
|----------------|------------|-----------------------------|
| ≥ 0.75         | critical   | Appel de la direction sous 24 h |
| 0.50 - 0.75    | high       | Appel du CSM sous 72 h      |
| 0.25 - 0.50    | medium     | Email de bilan de santé + relance |
| < 0.25         | low        | Aucune action               |

Les deux approches peuvent diverger sur un compte donné (calibration contre
rang) ; quand la cohérence stricte compte, consommez
`analytics.churn_predictions` (le batch).

### 7.2 Cadence de réentraînement

* **Hebdomadaire** : `make ml-train` via Prefect le dimanche à 02:00 UTC.
* **Ad hoc** : sur alerte de drift des données émise par Evidently (une
  feature avec `drift_score > 0.3`).

### 7.3 Limites connues

* **Jeu de test petit et synthétique** : environ 80 comptes, environ 8
  churners. Les métriques affichées (ROC-AUC ~0.97) mesurent la justesse du
  pipeline sur des données générées, pas un pouvoir prédictif réel ; le seed
  injecte le signal de churn par construction, ce qui rend les classes plus
  séparables que ne le seraient des données de production. C'est pourquoi
  `full_report` inclut des intervalles de confiance bootstrap : ils sont
  larges, et c'est la lecture honnête.
* **Comptes en démarrage à froid** : moins de 30 jours d'historique. Le
  modèle les signale ; l'interface les pondère à la baisse avec un badge
  "confiance faible".
* **Événements génératifs** : des migrations ad hoc ("nous avons fusionné
  tous les comptes UK") peuvent ressembler à un churn massif. GE dispose d'un
  garde-fou `row_count_between` sur `raw.accounts` pour attraper les cas les
  plus évidents avant que dbt ne reconstruise.
* **Non-stationnarité** : des changements tarifaires peuvent déplacer les
  moyennes des features de plus de 2σ du jour au lendemain. La fenêtre de
  référence d'Evidently (`tenure_months >= 6`) est choisie pour que la
  référence corresponde toujours aux "comptes matures", les moins sensibles
  aux expérimentations tarifaires menées sur les nouvelles inscriptions.
