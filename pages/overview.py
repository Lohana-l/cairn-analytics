"""Page Overview - vue de synthèse : revenu, mouvement net, santé des comptes et risque de churn."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import plotly.graph_objects as go

import streamlit as st
from data.loader import load_accounts_data, load_revenue_data
from ui.components import COLORS, inject_base_css, kpi_card, section_header, tip

inject_base_css()


def _recommended_action(driver: str) -> str:
    d = driver.lower()
    if any(k in d for k in ("stickiness", "événement", "event", "dau", "activité", "utilisateurs")):
        return "Campagne de réactivation produit"
    elif any(k in d for k in ("facture", "invoice", "overdue", "retard", "paiement")):
        return "Relance facturation urgente"
    elif any(k in d for k in ("contraction", "plan", "siège", "mrr")):
        return "Proposer une offre de rétention"
    elif any(k in d for k in ("csat", "ticket", "support", "satisfaction")):
        return "Escalade support prioritaire"
    else:
        return "Revue de compte recommandée"


rev         = load_revenue_data()
acc         = load_accounts_data()
kpis        = rev["kpis"]
accounts    = acc["accounts"]
mrr_monthly = rev["mrr_monthly"]

# Même philosophie que la page Pipeline : si une source est tombée en fallback
# synthétique, on le dit en haut de page, jamais en petit dans la sidebar.
_demo = sorted(set(rev.get("demo_sources", []) + acc.get("demo_sources", [])))
if _demo:
    st.warning(
        "Données simulées pour : " + ", ".join(_demo)
        + ". Le warehouse est injoignable, les chiffres ci-dessous ne sont pas réels.",
        icon=":material/cloud_off:",
    )

# Comptes à risque = tiers "high" + "critical". On unifie la définition
# pour TOUTE la page (KPI3, KPI4, bloc "Synthèse du risque") : c'est ce
# qu'un CSM contacte en priorité, pas seulement le tier critical isolé.
high_risk     = accounts[accounts["risk_tier"].isin(["high", "critical"])]
n_at_risk     = len(high_risk)
mrr_at_risk   = high_risk["mrr"].sum()
n_total       = len(accounts)
pct_at_risk   = (n_at_risk / n_total) if n_total else 0.0

pct_mrr_at_risk = (mrr_at_risk / kpis["gross_mrr"]) if kpis["gross_mrr"] else 0.0


def fmt_eur_compact(v: float, signed: bool = False) -> str:
    """Montant arrondi pour la page de synthèse : 37,0 M€ / 620 k€ / 850 €.

    L'accueil donne un ordre de grandeur ; les montants exacts vivent sur les
    pages de détail (Revenue, Churn Risk).
    """
    sign = "+" if (signed and v >= 0) else ("-" if v < 0 else "")
    a = abs(v)
    if a >= 1_000_000:
        txt = f"{a / 1_000_000:.1f}".replace(".", ",") + " M€"
    elif a >= 10_000:
        txt = f"{a / 1_000:.0f} k€"
    else:
        txt = f"{a:,.0f} €"
    return f"{sign}{txt}"

# ── Section 1 : KPI cards
with st.container(border=True):
    section_header("Vue d'ensemble du mois",
                   "Synthèse des revenus, du risque client et des alertes en cours",
                   icon="dashboard")

    mom_pct = kpis["gross_mrr_mom"]
    mom_str = f"<b>{'+' if mom_pct >= 0 else '-'} {abs(mom_pct):.1%}</b> vs mois préc."
    net     = kpis["net_new_mrr"]

    tip_mrr   = tip("MRR : somme des revenus d'abonnements actifs sur le mois en cours.")
    tip_net   = tip("Net MRR Movement : nouveaux plus expansions, moins contractions, moins churns.")
    tip_risk  = tip("Somme des MRR des comptes classés à risque élevé ou critique par le modèle (top 15 % du portefeuille). Détail compte par compte sur la page Churn Risk.")
    tip_churn = tip("Espérance de perte de MRR : somme des MRR pondérés par la probabilité de churn prédite par le modèle pour chaque compte actif.")

    # Perte attendue = Σ (probabilité de churn × MRR) sur le portefeuille actif.
    # Plus informatif qu'un simple taux : pondère le risque par la valeur en jeu.
    expected_loss = float((accounts["churn_risk_score"] * accounts["mrr"]).sum())
    pct_expected  = (expected_loss / kpis["gross_mrr"]) if kpis["gross_mrr"] else 0.0

    _c_danger = COLORS["danger"]
    _c_warn   = COLORS["warn"]

    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        st.markdown(kpi_card(
            f"Revenu mensuel récurrent {tip_mrr}",
            fmt_eur_compact(kpis["gross_mrr"]),
            delta=mom_str, delta_good=(mom_pct >= 0),
            tone="ok" if mom_pct >= 0 else "warn",
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_card(
            f"Variation nette du revenu {tip_net}",
            fmt_eur_compact(net, signed=True),
            delta="Nouveaux + Expansions - Contractions - Churns",
            delta_good=(net >= 0),
            tone="ok" if net >= 0 else "alert",
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_card(
            f"MRR menacé {tip_risk}",
            fmt_eur_compact(mrr_at_risk),
            delta=f"<b>{pct_mrr_at_risk:.1%}</b> du MRR<br><span style='color:{_c_danger};font-weight:700'>{n_at_risk}</span> comptes à risque",
            delta_good=False,
            tone="alert" if n_at_risk > 0 else "ok",
        ), unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_card(
            f"Perte attendue (churn) {tip_churn}",
            f"{pct_expected:.1%}",
            delta=f"<b>{fmt_eur_compact(expected_loss)}</b> de MRR<br><span style='color:{_c_warn};font-weight:700'>{n_total}</span> comptes actifs",
            delta_good=False,
            tone="warn" if pct_expected > 0.05 else "",
        ), unsafe_allow_html=True)

# ── Section 2 : Bloc MRR menacé + CTA (gros bloc dédié) ──────────────────────
n_inv    = acc["with_invoices"]
mrr_high = mrr_at_risk      # alias pour lisibilité de la section ci-dessous

with st.container(border=True):
    section_header("MRR menacé : action requise",
                   "Comptes à risque élevé ou critique nécessitant une intervention",
                   icon="warning")

    st.markdown(
        f"""
        <div class="cairn-alert">
          <div class="title">Synthèse du risque</div>
          <div class="body">
              <b>{len(high_risk)}</b> comptes à risque élevé ou critique représentent
              <b>{fmt_eur_compact(mrr_high)}</b> de MRR
              ({pct_mrr_at_risk:.1%} du portefeuille).
              {f"<b>{n_inv}</b> ont des factures en retard." if n_inv > 0 else ""}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Voir les comptes à risque", type="primary",
                 icon=":material/arrow_forward:"):
        st.switch_page("pages/churn_risk.py")

# ── Section 3 : Waterfall + Actions ──────────────────────────────────────────
with st.container(border=True):
    section_header("Variation du revenu (mois en cours)",
                   "Décomposition du mouvement de revenu et liste des actions prioritaires sur les comptes à risque.",
                   icon="trending_up")

    col_chart, col_actions = st.columns([1.4, 1], gap="large")

    with col_chart:
        last = mrr_monthly.iloc[-1]
        fig = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "relative", "total"],
            x=["Base", "Nouveau", "Expansion", "Contraction", "Churn", "Total"],
            y=[last["mrr_start"], last["mrr_new"], last["mrr_expansion"],
               -last["mrr_contraction"], -last["mrr_churn"], last["mrr_end"]],
            connector=dict(line=dict(color=COLORS["border"], width=1)),
            # Convention chromatique unifiée :
            #   croissance (nouveau / expansion) = primaire (bleu)
            #   perte (contraction / churn)      = rouge danger
            #   base / total                     = neutre gris
            increasing=dict(marker=dict(color=COLORS["primary"])),
            decreasing=dict(marker=dict(color=COLORS["danger"])),
            totals=dict(marker=dict(color=COLORS["text2"])),
            text=[f"{v:,.0f} €" for v in [
                last["mrr_start"], last["mrr_new"], last["mrr_expansion"],
                -last["mrr_contraction"], -last["mrr_churn"], last["mrr_end"],
            ]],
            textposition="outside",
        ))
        fig.update_traces(cliponaxis=False)
        fig.update_layout(
            # marges TRÈS généreuses + autorange padding pour que les labels valeur
            # (en haut) ne soient JAMAIS coupés, même sur petite hauteur
            height=420, margin=dict(t=90, l=10, r=10, b=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor=COLORS["border_soft"],
                       zeroline=False, automargin=True,
                       rangemode="tozero"),
            xaxis=dict(showgrid=False, automargin=True),
            showlegend=False,
            font=dict(family="Inter, system-ui, sans-serif", color=COLORS["text"]),
            uniformtext=dict(minsize=10, mode="hide"),
        )
        # padding 18% en haut pour les labels "outside"
        y_max = max(last["mrr_start"], last["mrr_end"]) * 1.18
        fig.update_yaxes(range=[0, y_max])
        st.plotly_chart(fig, use_container_width=True)

    with col_actions:
        st.markdown(
            '<p class="cairn-section-title">Action requise</p>'
            '<p class="cairn-section-subtitle" style="margin-bottom:12px;">'
            '5 comptes les plus à risque</p>',
            unsafe_allow_html=True,
        )
        top5 = accounts.head(5)[["company_name", "mrr", "risk_tier",
                                  "churn_risk_score", "top_driver"]]
        tier_color = {
            "critical": COLORS["danger"],
            "high":     COLORS["warn"],
            "medium":   COLORS["secondary"],
            "low":      COLORS["ok"],
        }
        for _, row in top5.iterrows():
            tc = tier_color.get(row["risk_tier"], COLORS["muted"])
            st.markdown(
                f"""<div style="border:1px solid {COLORS['border']};border-radius:8px;
                            padding:10px 14px;margin-bottom:8px;
                            border-left:3px solid {tc};background:#FFFFFF;">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-weight:600;font-size:13px;color:{COLORS['text']};">
                        {row['company_name']}</span>
                    <span style="font-size:12px;color:{COLORS['text2']};">
                        {row['mrr']:,.0f} €/mo</span>
                  </div>
                  <div style="font-size:11px;color:{COLORS['text2']};margin-top:3px;">
                      Score {row['churn_risk_score']:.0%} ({row['top_driver']})
                  </div>
                  <div style="font-size:11px;color:{COLORS['primary_dark']};
                              margin-top:4px;font-weight:600;">
                      Action : {_recommended_action(row['top_driver'])}
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )
