# Gouvernance et RGPD

Cairn modélise la plateforme de données d'un éditeur SaaS B2B européen : un
déploiement réel traiterait donc des **données personnelles de contacts de
comptes clients** et entrerait pleinement dans le champ d'application du RGPD.
Ce document fait deux choses, en les gardant strictement séparées :

1. **Tel que construit** : ce que l'implémentation de référence livre
   effectivement aujourd'hui (données synthétiques, contrôles au niveau du
   code présents dans ce dépôt).
2. **Surcouche production** : ce qu'un déploiement réel devrait ajouter, avec
   une conception concrète pour chaque point.

> Note de périmètre. Cairn fonctionne exclusivement sur des **données
> synthétiques** générées par `seed/` (Faker + numpy, déterministe). Aucune
> donnée de personne réelle n'entre jamais dans la plateforme. L'analyse RGPD
> ci-dessous est donc un exercice de conception sur le schéma, et non une
> déclaration de conformité ; elle est rédigée de façon à rendre l'écart entre
> les deux explicite plutôt qu'implicite.

## 1. Inventaire des données personnelles (schéma tel que construit)

Les colonnes ci-dessous sont celles qui existent dans `sql/init.sql`. Dans un
déploiement réel, elles porteraient des données personnelles selon la
catégorisation suivante :

| Table                  | Champs concernés                              | Catégorie (art. 4 RGPD)        |
|------------------------|-----------------------------------------------|--------------------------------|
| `raw.accounts`         | `company_name`, `country`                     | Identification (niveau organisation) |
| `raw.subscriptions`    | `account_id` (identifiant indirect)           | Identifiant indirect           |
| `raw.invoices`         | `account_id`, `amount`, `status`              | Financier, identifiant indirect |
| `raw.events`           | `account_id`, `user_id` (niveau utilisateur), `event_ts` | Comportemental, identifiant indirect |
| `raw.tickets`          | `account_id`, `category`, `csat`              | Interaction support            |
| `analytics.churn_predictions` | `account_id`, score, niveau, facteurs explicatifs | Résultat de profilage (proche de l'art. 22) |

Ce que le schéma tel que construit ne contient délibérément pas :

* Aucun nom ni email de contact de facturation. Le schéma de référence est
  uniquement au niveau du compte ; un schéma de production ajoutant des
  colonnes `billing_contact_*` étendrait l'inventaire et la logique
  d'effacement en conséquence (voir §3.3).
* Aucune donnée de catégorie particulière (santé, biométrie, opinions
  politiques, etc.). Le cadrage SaaS rend cela structurellement impossible
  pour les données de référence.
* Aucune donnée de carte bancaire. Stripe / le prestataire de facturation
  porte le périmètre PCI ; Cairn ne voit que les montants et statuts des
  factures.

Surcouche production pour `raw.events.user_id` : pseudonymiser à l'ingestion
avec un hachage SHA-256 salé afin que le warehouse ne détienne jamais
d'identifiant utilisateur brut. Le pipeline tel que construit ingère le
`user_id` synthétique tel quel, ce qui n'est acceptable que parce que la
donnée est synthétique.

## 2. Bases légales (analyse de conception)

| Activité de traitement                              | Base légale (art. 6)                        |
|-----------------------------------------------------|---------------------------------------------|
| Contact de facturation conservé pour la facturation | **Contrat** (6.1.b)                         |
| Historique des abonnements et factures              | **Contrat** (6.1.b) + **obligation légale** de conservation comptable (6.1.c) |
| Événements produit pour l'exploitation du service (correction de bugs, planification de capacité) | **Contrat** (6.1.b) |
| Événements produit utilisés pour le **profilage du churn** | **Intérêt légitime** (6.1.f) avec un droit d'opposition au titre de l'art. 21 |
| Tickets de support                                  | **Contrat** (6.1.b)                         |

La base du profilage est la seule qui ne va pas de soi. Elle repose sur une
**analyse d'intérêt légitime** documentée séparément : le client peut
raisonnablement s'attendre à ce qu'un éditeur SaaS cherche à le fidéliser ;
le profilage se fait au niveau du compte, sans ciblage publicitaire ; le
résultat est présenté à un CSM humain (aucune décision exclusivement
automatisée au sens de l'art. 22). Voir §3.4 pour la conception du mécanisme
d'opposition.

## 3. Droits des personnes concernées (surcouche production, avec conceptions concrètes)

Aucun des endpoints ou scripts de cette section n'existe aujourd'hui dans le
dépôt. Ils sont spécifiés ici afin que le coût de leur ajout soit visible et
borné. Le schéma tel que construit fait de chacun d'eux un changement modeste
et localisé.

### 3.1 Droit d'accès (art. 15)

Conception : un endpoint `GET /privacy/account/{account_id}` dans
`api/main.py` (authentifié, avec limitation de débit) retournant chaque champ
détenu sur un compte, ainsi que sa prédiction de churn la plus récente.
L'export sous-jacent tient en six requêtes :

```sql
SELECT * FROM raw.accounts            WHERE account_id = :id;
SELECT * FROM raw.subscriptions       WHERE account_id = :id;
SELECT * FROM raw.invoices            WHERE account_id = :id;
SELECT * FROM raw.events              WHERE account_id = :id;
SELECT * FROM raw.tickets             WHERE account_id = :id;
SELECT * FROM analytics.churn_predictions WHERE account_id = :id;
```

### 3.2 Droit de rectification (art. 16)

Les données de facturation sont mises à jour à la source (dans le système de
facturation) et réingérées au prochain `daily_refresh`. Pas d'API d'écriture
séparée : un seul système de référence, par conception. Ce point ne demande
aucun code nouveau ; c'est une propriété de l'architecture d'ingestion.

### 3.3 Droit à l'effacement (art. 17), « droit à l'oubli »

Conception : un modèle `sql/erase_account.sql` et une cible
`make erase ACCOUNT_ID=...` enchaînant les suppressions dans une seule
transaction, tables enfants d'abord (les clés étrangères sur `account_id`
imposent cet ordre) :

```sql
BEGIN;
  DELETE FROM analytics.churn_predictions WHERE account_id = :id;
  DELETE FROM raw.events                  WHERE account_id = :id;
  DELETE FROM raw.tickets                 WHERE account_id = :id;
  DELETE FROM raw.invoices                WHERE account_id = :id;
  DELETE FROM raw.subscriptions           WHERE account_id = :id;
  UPDATE raw.accounts
     SET company_name = '[redacted]'
   WHERE account_id = :id;
  INSERT INTO analytics.audit_log (actor, action, target)
         VALUES (current_user, 'erase', :id);
COMMIT;
```

Justification du choix de conserver une **ligne tombstone** dans
`raw.accounts` plutôt que de procéder à une suppression définitive :
l'art. 17.3.b du RGPD autorise la conservation du minimum de données
nécessaire au respect des obligations comptables (facturation). Le tombstone
permet à `fct_mrr_monthly` de préserver les totaux MRR historiques sans
détenir de donnée identifiante. Un schéma de production ajouterait une
colonne d'horodatage `erased_at` pour rendre les tombstones requêtables. La
table `analytics.audit_log` dans laquelle cette conception écrit existe
**bel et bien** dans `sql/init.sql`.

### 3.4 Droit d'opposition et art. 22 (décision individuelle automatisée)

Le score de churn de Cairn n'est **pas** une décision exclusivement
automatisée : aucun changement tarifaire, aucune action sur le compte ni
aucun email n'est déclenché par le seul score ; chaque action CS garde un
humain dans la boucle. Un déploiement en production implémenterait néanmoins
le mécanisme d'opposition :

* un booléen `profiling_opt_out` sur `raw.accounts` (FALSE par défaut),
* propagé à travers `mart_account_health` et filtré dans `ml.predict` avant
  le scoring,
* affiché dans Streamlit avec un badge « opt-out » et exclu de la liste de
  priorités.

### 3.5 Droit à la portabilité (art. 20)

Même endpoint qu'au §3.1, avec un paramètre de requête `?format=json`. La
sortie est un ensemble JSON lisible par machine, soit exactement ce que
demande l'art. 20.

## 4. Durées de conservation (cibles de conception)

| Jeu de données                 | Durée de conservation                               |
|--------------------------------|-----------------------------------------------------|
| `raw.accounts`                 | Durée du contrat + 10 ans (conservation comptable légale, FR : art. L123-22 du Code de commerce), puis effacement hors éléments comptables essentiels |
| `raw.subscriptions`, `raw.invoices` | 10 ans (comptabilité)                          |
| `raw.events`                   | **13 mois** glissants, aligné sur les recommandations de la CNIL en matière de mesure d'audience et d'usage |
| `raw.tickets`                  | 3 ans après la clôture du ticket                    |
| `analytics.churn_predictions`  | **90 jours** : l'horizon de prédiction              |
| `analytics.audit_log`          | 5 ans                                               |

L'application de ces durées n'est pas implémentée dans le dépôt (le jeu de
données synthétique est régénéré à chaque bootstrap, rien ne vieillit donc).
La conception production est un déploiement Prefect nocturne exécutant
`DELETE FROM raw.events WHERE event_ts < now() - interval '13 months'`, avec
un garde-fou qui interrompt l'opération si le nombre de lignes supprimées
devait dépasser 1 % de la table (prévention des suppressions massives en cas
de bug).

## 5. Contrôles de sécurité

| Contrôle                           | Statut                                                       |
|------------------------------------|--------------------------------------------------------------|
| SQL paramétré partout              | **Tel que construit.** `ingestion.loaders` et `ml.predict` utilisent le binding de paramètres psycopg2 ; aucune interpolation de valeurs dans les chaînes. |
| Épinglage des dépendances          | **Tel que construit.** Tous les `requirements*.txt` sont épinglés sur des versions exactes. |
| Surface d'image minimale           | **Tel que construit.** Images de base `python:3.11-slim`.    |
| Identifiants utilisateur pseudonymisés | **Surcouche.** SHA-256 salé du `user_id` à l'ingestion (voir §1). |
| Rôle base de données en lecture seule pour l'API et Streamlit | **Surcouche.** La démo locale utilise l'unique superutilisateur `cairn` ; la production ajoute un rôle limité au `SELECT` dans `sql/init.sql`. |
| Gestion des secrets                | **Surcouche.** La démo locale conserve les identifiants dans `docker-compose.yml` pour un démarrage en une commande ; la production les déplace vers des fichiers d'environnement ou un gestionnaire de secrets. |
| Surface de vulnérabilité           | **Surcouche.** `pip-audit` / Dependabot sur les PR.          |

## 6. Chaîne sous-traitants et sous-traitants ultérieurs

Dans un déploiement réel, le responsable de traitement (l'éditeur SaaS) et
les sous-traitants sont :

| Partie                    | Rôle                 | Données                               |
|---------------------------|----------------------|---------------------------------------|
| Éditeur SaaS              | Responsable de traitement | Toutes                           |
| Fournisseur cloud hébergeant Cairn | Sous-traitant | Toutes (chiffrées au repos et en transit) |
| Stripe (ou équivalent)    | Sous-traitant ultérieur | Factures + contact de facturation  |
| Segment / Amplitude       | Sous-traitant ultérieur (en amont) | Événements produit avant ingestion |
| Zendesk (ou équivalent)   | Sous-traitant ultérieur | Tickets + CSAT                     |

Les accords de traitement des données (DPA) avec chaque sous-traitant
relèvent de la responsabilité de l'organisation qui déploie. Cairn,
l'implémentation de référence, ne fournit elle-même aucun service SaaS qui
ferait d'elle un sous-traitant pour un tiers.

## 7. Contrôles organisationnels à ajouter pour un passage en production

1. **Registre des activités de traitement** (art. 30) : un tableur, pas du
   code.
2. **Analyse d'impact relative à la protection des données** (AIPD, art. 35) :
   parce que du profilage est en jeu, même si l'art. 22 ne s'applique pas.
3. **Désignation d'un DPO** si l'organisation atteint les seuils de
   l'art. 37.
4. **Politique de confidentialité** mise à jour pour nommer le profilage du
   churn comme finalité, au titre de l'intérêt légitime, avec le mécanisme
   d'opposition décrit au §3.4.
5. **Procédure de notification de violation** : 72 h pour notifier la CNIL
   conformément à l'art. 33.
6. **DPA fournisseurs** et, pour tout transfert hors EEE, clauses
   contractuelles types et analyse d'impact des transferts.

## 8. Synthèse

La posture RGPD de Cairn tient en une phrase : **ne conserver que le
nécessaire, le conserver aussi longtemps que la loi l'exige, expliquer au
client ce qui est fait de ses données et laisser un humain trancher.**
L'implémentation de référence livre le schéma et l'hygiène au niveau du
code ; les endpoints de droits des personnes concernées, l'application des
durées de conservation et les contrôles organisationnels sont spécifiés
ci-dessus comme surcouche production explicite, afin que personne ne confonde
une plateforme portfolio avec un livrable de conformité.
