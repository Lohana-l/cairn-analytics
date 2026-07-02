# Stratégie de qualité des données

Cairn applique **trois couches de contrôles**, une par étage de la cascade.
Chaque couche a son propre responsable, son propre mode de défaillance et sa
propre façon de signaler l'échec. Rien n'est vérifié deux fois, rien ne passe
entre les mailles.

```
 raw          :  Great Expectations (contrat d'entrée)          :  bloque le pipeline
 staging+marts:  tests dbt (contrat de transformation)          :  bloque le dbt run
 predictions  :  Evidently + métriques modèle (contrat runtime) :  alerte, sans blocage
```

## 1. Couche 1 : Great Expectations à la frontière

**Objectif :** intercepter les problèmes dès la porte d'entrée, avant qu'un
seul modèle dbt ne soit construit.

**Périmètre :** les 5 tables raw.

**Implémentation :** `great_expectations/suites.py` définit les suites sous
forme de tuples déclaratifs ; `great_expectations/runner.py` est un exécuteur
de 120 lignes qui implémente 6 types d'expectations (`row_count_between`,
`value_in_set`, `not_null`, `between`, `mostly_between`, `pair_ge`)
directement contre Postgres.

Les arborescences GE complètes conviennent très bien aux déploiements
d'entreprise ; pour une plateforme de référence, la version en 200 lignes de
code obtient le même résultat sans committer 40 fichiers YAML.

### 1.1 Suites

```
RAW_ACCOUNTS
  row_count_between     : 100 .. 200_000
  value_in_set          : plan          ∈ {starter, pro, enterprise}
  value_in_set          : acquisition_ch ∈ {organic, paid_search, referral, outbound, partner}
  mostly_between (0.99) : seats          ∈ [1, 100_000]

RAW_SUBSCRIPTIONS
  not_null              : account_id, plan, valid_from
  pair_ge               : valid_to >= valid_from (where valid_to IS NOT NULL)
  value_in_set          : status        ∈ {active, trial, churned, cancelled, paused}

RAW_INVOICES
  not_null              : invoice_id, account_id, amount, issued_at
  between               : amount         ∈ [0, 1_000_000]
  value_in_set          : status         ∈ {paid, open, past_due, void, uncollectible}

RAW_EVENTS
  value_in_set          : event_type     ∈ {login, feature_use, export, invite, ...}
  not_null              : account_id, event_ts

RAW_TICKETS
  between               : csat           ∈ [1, 5]
  value_in_set          : priority       ∈ {low, normal, high, urgent}
```

### 1.2 Sortie

`data/ge_reports/ge_summary.json` :

```json
{
  "total": 23, "passed": 23, "failed": 0,
  "results": [ { "suite": "RAW_ACCOUNTS", "check": "row_count_between", "passed": true, "observed": 2000, "expected": "[100, 200000]" }, … ]
}
```

Consommé par :

* La tâche Prefect `ge_checks` : un code de sortie non nul bloque `daily_refresh`.
* La page Monitoring de Streamlit : le bandeau des 4 KPI affiche `23/23`.

### 1.3 Pourquoi GE avant dbt

Un `dbt test` sur une vue de staging détectera bien les mêmes violations,
mais seulement après que les données sources ont déjà été chargées dans
Postgres et converties. GE voit les données au format CSV telles qu'elles
arrivent, c'est-à-dire au moment précis où il faut arrêter un mauvais export
Stripe, une dérive de schéma après une mise à jour Segment ou une erreur de
saisie sur un CSV manuel.

## 2. Couche 2 : tests dbt sur les transformations

**Objectif :** garantir que la couche de transformation produit ce que le
code aval attend.

**Périmètre :** chaque vue de staging, chaque modèle intermédiaire, chaque
mart.

**Implémentation :** un mélange de tests génériques dans `schema.yml` et de
tests singuliers dans `dbt/tests/`.

### 2.1 Tests génériques (dans `schema.yml`)

Chaque vue de staging est livrée avec :

* `not_null` + `unique` sur les clés naturelles.
* `accepted_values` sur les colonnes de type chaîne énumérées (reflète le
  `value_in_set` de GE, mais attrape les conversions accidentelles côté
  staging).
* `relationships` sur toutes les clés étrangères : `stg_subscriptions.account_id`
  référence `stg_accounts.account_id`, etc.
* `dbt_utils.expression_is_true` pour les invariants au niveau ligne, par
  exemple :
  ```yaml
  - dbt_utils.expression_is_true:
      expression: "mrr >= 0"
  ```

### 2.2 Tests singuliers (dans `dbt/tests/`)

Quatre tests encodent les invariants les plus importants pour la logique
métier de Cairn :

* **`assert_mrr_movements_reconcile.sql`** : la somme de `fct_mrr_movements`
  sur un mois doit être égale au delta dans `fct_mrr_monthly`. C'est
  l'identité comptable qui rend le NRR crédible.
* **`assert_no_future_events.sql`** : aucune ligne de `fct_engagement_daily`
  ne porte une date postérieure à `var('reporting_date')`. Prévient toute
  fuite accidentelle de données cible (leakage) via les labels.
* **`assert_subscription_history_non_overlapping.sql`** : pour un compte
  donné, les intervalles de `int_subscription_history` sont disjoints.
  Indispensable pour que le MRR à date donnée soit bien défini.
* **`assert_churned_accounts_have_no_active_subs.sql`** : si
  `dim_account.status = 'churned'`, aucune ligne de `int_subscription_history`
  n'a `valid_to IS NULL`. Attrape la classe de bugs "compte marqué churné,
  abonnement encore ouvert".

### 2.3 Quand les tests dbt échouent

`dbt test` sort avec un code non nul, donc `make dbt-build` échoue, et le pipeline de bootstrap signale l'échec (les tests dbt y sont non bloquants par conception : le run est marqué en échec, pas interrompu).
Le job CI `lint-and-unit` exécute `dbt parse` (pas `dbt run`) ; `dbt test`
lui-même est exercé par le job `integration` contre un vrai Postgres via
testcontainers.

## 3. Couche 3 : Evidently + métriques modèle à l'exécution

**Objectif :** détecter le moment où le *monde* a changé sous un modèle
entraîné sur les données du trimestre précédent.

**Périmètre :** features et prédictions, toutes les 2 heures.

**Implémentation :** `monitoring/evidently_jobs.py` construit une fenêtre de
référence (comptes avec `tenure_months >= 6`) et une fenêtre courante (tous
les comptes scorés aujourd'hui) et produit :

| Rapport       | Question à laquelle il répond                               |
|---------------|-------------------------------------------------------------|
| Drift des données | La distribution d'une feature a-t-elle dévié par rapport à la référence ? |
| Drift de la cible | Le taux de churn observé a-t-il lui-même dévié ?         |
| Performance de classification | Sur les comptes désormais labellisables (90 jours après le scoring), quels sont les ROC-AUC, PR-AUC et Brier ? |

### 3.1 Sortie

* `data/evidently_reports/data_drift.html` : rapport HTML interactif complet.
* `data/evidently_reports/summary.json` : synthèse exploitable par machine,
  consommée par la page Monitoring de Streamlit (déplacements des moyennes
  des features, taux de churn de référence et courant).

Si les dépendances Evidently ne sont pas installées (par exemple en CI), le
job se dégrade proprement vers la synthèse JSON seule ; le pipeline ne casse
pas.

### 3.2 Seuils d'alerte

| Signal                               | Seuil            | Action                         |
|--------------------------------------|------------------|--------------------------------|
| Déplacement de la moyenne d'une feature > 3σ | strict    | Bloque predict, réveille l'astreinte |
| Une feature avec `drift_score > 0.3` | souple           | Alerte, continue de prédire, réentraînement au cycle suivant |
| Le taux de churn courant dévie de plus de 2 points | souple | Alerte, investiguer avant de promouvoir un nouveau modèle |
| La PR-AUC sur les prédictions vieilles de 90 jours chute de plus de 5 points face au champion | strict | Bloque la promotion du prochain challenger |

Les seuils *stricts* sont appliqués dans le flow Prefect : la tâche lève une
exception, les tâches aval ne s'exécutent pas, `analytics.churn_predictions`
conserve les derniers bons scores. Mieux vaut des scores périmés que des
scores faux.

## 4. Tests de bout en bout

`tests/` est découpé en deux :

* **Unitaires (`tests/unit/`)** : Python pur, sans base de données. Couvrent
  le déterminisme du seed, le contrat d'ingestion, le constructeur de
  features, les métriques, les routes de l'API (avec modèle mocké), le runner
  GE (avec `pd.read_sql` monkey-patché), l'ordonnancement des tâches du flow
  Prefect.
* **Intégration (`tests/integration/`)** : démarrent un vrai Postgres via
  `testcontainers`, appliquent `sql/init.sql`, chargent un petit jeu de
  données et exécutent ingestion + GE + dbt (lent) de bout en bout. Inclut le
  test d'idempotence aller-retour (premier run = 30 lignes, second run = 0).

Jobs CI :

| Job                | Déclencheur    | Exécute                             |
|--------------------|----------------|-------------------------------------|
| `lint-and-unit`    | chaque push    | ruff + pytest tests/unit            |
| `integration`      | chaque push    | pytest tests/integration (hors slow) |
| `sql-lint`         | chaque push    | sqlfluff lint (échec non bloquant)  |
| `slow`             | workflow_dispatch | tests marqués `slow` (dbt build, entraînement complet) |

## 5. Qui est responsable de quoi

| Couche            | Responsable dans une vraie équipe |
|-------------------|-------------------------------|
| Suites GE         | Data engineer (responsable du contrat CSV) |
| Tests dbt         | Analytics engineer (responsable des marts) |
| Rapports Evidently | ML engineer (responsable du runtime du modèle) |
| Runbooks          | Rotation d'astreinte (répond aux alertes strictes) |

Garder ces responsabilités distinctes est un choix de conception délibéré :
une astreinte et une métrique par couche, donc chaque défaillance est routée
vers la personne qui peut réellement la corriger.
