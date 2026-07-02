# Contexte marché : pourquoi Cairn Analytics ?

## 1. Le problème métier du SaaS

Les entreprises SaaS vivent ou meurent selon **l'efficacité de leur revenu
récurrent**. Trois métriques dominent chaque présentation au conseil
d'administration :

| Métrique               | Définition                                                         | Pourquoi c'est important                          |
|------------------------|--------------------------------------------------------------------|---------------------------------------------------|
| **MRR / ARR**          | Revenu récurrent mensuel / annuel                                  | Santé du chiffre d'affaires ; se compose avec la rétention |
| **Rétention nette du revenu (NRR)** | `(starting MRR + expansion - contraction - churn) / starting MRR` | Le meilleur prédicteur individuel de la valeur long terme d'un SaaS |
| **Rétention brute du revenu (GRR)** | `(starting MRR - contraction - churn) / starting MRR`            | Plancher de rétention, insensible au bruit de l'expansion |

Une entreprise à **130 % de NRR** double son chiffre d'affaires environ tous
les 2,6 ans sans aucun nouveau client net. Une entreprise à **85 % de NRR**
doit remplacer 15 % de son portefeuille chaque année juste pour rester au
même niveau, avant même de financer le CAC. L'écart entre un « excellent »
SaaS et un SaaS « moyen » est presque entièrement un écart de rétention.

## 2. La lacune analytique

La plupart des équipes SaaS en phase de démarrage instrumentent bien le
funnel (inscription, essai, payant), mais laissent la surface post-vente
sous-instrumentée :

- **La facturation** vit dans Stripe ou Chargebee, cloisonnée à l'écart de la
  télémétrie produit.
- **Les événements produit** atterrissent dans Segment / Amplitude mais
  atteignent rarement le warehouse sous une forme modélisée et testable.
- **Les tickets de support** restent dans Zendesk, inaccessibles à la finance
  et au CS dans une même requête.
- **Le churn est constaté après coup.** Les dirigeants le voient avec 30 à
  90 jours de retard, le plus souvent comme une surprise trimestrielle.

Résultat : les équipes croissance ne peuvent pas répondre à la question
« quels comptes sont à risque **en ce moment même**, et pourquoi ? » sans
extraire trois CSV et deviner.

## 3. Ce que fait Cairn

Cairn est une plateforme de prédiction du churn et d'observabilité data pour
le SaaS B2B : une implémentation de référence de bout en bout, aux partis
pris assumés, qui comble cette lacune sur un unique warehouse Postgres :

1. **Warehouse unifié** : comptes, abonnements, factures, événements produit
   et tickets dans un même schéma en étoile (`marts.*`).
2. **Vue canonique de santé des comptes** (`mart_account_health`) joignant
   cycle de vie, facturation, engagement et support en une ligne par compte.
3. **Décomposition des mouvements de MRR** (`fct_mrr_movements`) : chaque
   delta est classé en nouveau / expansion / contraction / churn, si bien que
   le NRR est calculé, et non estimé.
4. **Modèle de churn à indicateurs avancés** : une probabilité à horizon
   90 jours avec des facteurs SHAP par compte (« baisse des connexions sur
   30 jours », « hausse des tickets ouverts », « rétrogradation de plan le
   mois dernier »).
5. **Servi** via FastAPI pour le scoring en temps réel et Streamlit pour
   l'exploration par les analystes, **orchestré** par Prefect, **suivi** par
   MLflow, **surveillé** par Great Expectations (qualité des entrées) et
   Evidently (drift + performance).

## 4. À qui s'adresse la plateforme

Cairn est une **plateforme B2B SaaS généraliste** : les comptes, offres et
événements sont agnostiques du secteur (SaaS horizontal : productivité,
outils de développement, collaboration, plateformes ops). Le même pipeline
fonctionne aussi bien pour une startup en amorçage à 2 M$ d'ARR que pour une
scale-up à 50 M$ d'ARR.

Ce n'est explicitement **pas** une plateforme d'analytics pour la santé,
l'attribution marketing ou les applications grand public. Ces verticales ont
leurs propres formes de données et leurs propres contraintes réglementaires ;
Cairn garde un périmètre resserré pour bien faire une seule chose.

## 5. Limites de périmètre

| Dans le périmètre                                 | Hors périmètre                                     |
|---------------------------------------------------|----------------------------------------------------|
| Cycle de vie des abonnements (essai, payant, churn) | Scoring de leads, attribution marketing          |
| Comptabilité MRR/ARR/NRR/GRR                      | Analytics du pipeline commercial / CRM             |
| Engagement produit (DAU/MAU, usage des fonctionnalités) | Cohortes comportementales par utilisateur pour les boucles de croissance |
| Volume de support comme signal de churn           | Triage Zendesk complet / gestion des SLA           |
| Probabilité de churn + explication des facteurs   | Prévision de revenu, LTV/CAC, optimisation tarifaire |
| Traitement des données personnelles au niveau d'exigence RGPD pour les clients européens | Catalogues de contrôles SOC 2 / ISO 27001 |

La stack de référence est volontairement compacte, pour qu'une équipe puisse
la lire de bout en bout en une journée et la forker pour un déploiement en
production en une semaine.
