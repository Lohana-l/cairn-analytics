"""Page Churn Risk : comptes à risque classés par tier, avec les drivers SHAP de chaque score."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import plotly.graph_objects as go

import streamlit as st
from data.loader import feature_label, load_accounts_data, shap_drivers_for_account
from ui.components import (
    COLORS,
    RISK_COLORS,
    inject_base_css,
    page_header,
    risk_badge,
)

inject_base_css()

data     = load_accounts_data()
accounts = data["accounts"].copy()

# Annonce du fallback synthétique en haut de page (cohérent avec Pipeline).
if data.get("demo_sources"):
    st.warning(
        "Données simulées pour : " + ", ".join(data["demo_sources"])
        + ". Le warehouse est injoignable, les comptes ci-dessous ne sont pas réels.",
        icon=":material/cloud_off:",
    )

page_header("Churn Risk",
            "Comptes regroupés par tier de risque, avec le score de churn prédit par le modèle XGBoost et les drivers SHAP calculés pour chaque compte au moment de la prédiction.")

# Actions recommandées (sans emojis, prefixées d'un verbe d'action)
ACTIONS = {
    "critical": [
        "Appel d'urgence Account Manager sous 24h",
        "Proposer un audit usage gratuit",
        "Escalader au Customer Success Manager",
    ],
    "high": [
        "Planifier un QBR ce mois",
        "Envoyer un rapport d'usage personnalisé",
        "Identifier les champions internes",
    ],
    "medium": [
        "Séquence email re-engagement",
        "Proposer une formation produit",
        "Surveiller les prochains 30 jours",
    ],
    "low": [
        "Maintenir le contact (compte sain)",
        "Identifier les opportunités d'expansion",
    ],
}

tone_map = {"critical": "alert", "high": "warn", "medium": "", "low": "ok"}

# Libellés FR + icône SVG par tier (cohérent avec le style des autres sections)
TIER_LABELS = {
    "critical": "Comptes critiques",
    "high":     "Risque élevé",
    "medium":   "Risque modéré",
    "low":      "Comptes sains",
}
TIER_ICONS = {
    # icône inline (heroicons-style), couleur appliquée via currentColor
    "critical": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    "high":     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
    "medium":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>',
    "low":      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
}

for tier in ["critical", "high", "medium", "low"]:
    sub         = accounts[accounts["risk_tier"] == tier].copy()
    if sub.empty:
        continue
    sub_display = sub[["company_name", "mrr", "churn_risk_score", "top_driver"]].copy()
    sub_display["churn_risk_score"] = (sub_display["churn_risk_score"] * 100).round(1)
    tc = RISK_COLORS[tier]

    with st.container(border=True):
        # Header section : icône carré coloré par tier + titre + sous-titre
        # (classe cairn-section-head pour être détecté comme section par le CSS)
        st.markdown(
            f'<div class="cairn-section-head" '
            f'style="display:flex;align-items:flex-start;gap:14px;'
            f'margin:0 0 18px 0;padding:0 0 14px 0;'
            f'border-bottom:1px solid {COLORS["border_soft"]};">'
            f'  <div style="flex-shrink:0;width:42px;height:42px;border-radius:10px;'
            f'background:{tc}1A;color:{tc};display:flex;align-items:center;'
            f'justify-content:center;">'
            f'    <span style="width:22px;height:22px;display:block;">{TIER_ICONS[tier]}</span>'
            f'  </div>'
            f'  <div style="flex:1;min-width:0;">'
            f'    <h3 style="font-size:19px;font-weight:800;color:{tc};'
            f'margin:0 0 4px 0;line-height:1.25;letter-spacing:-0.01em;">'
            f'{TIER_LABELS[tier]}</h3>'
            f'    <p style="font-size:13.5px;color:{COLORS["text2"]};margin:0;'
            f'line-height:1.55;">'
            f'<b style="color:{COLORS["text"]};font-weight:700;">{len(sub)}</b> compte(s), '
            f'<b style="color:{COLORS["text"]};font-weight:700;">{sub["mrr"].sum():,.0f} €</b> de MRR cumulé</p>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # On allège : pas de carte redondante avec le header
        event = st.dataframe(
            sub_display.rename(columns={
                "company_name":     "Compte",
                "mrr":              "MRR",
                "churn_risk_score": "Score (%)",
                "top_driver":       "Raison principale",
            }),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"df_{tier}",
            column_config={
                "Compte":            st.column_config.TextColumn(),
                "MRR":               st.column_config.NumberColumn(format="%.0f €"),
                "Score (%)":         st.column_config.NumberColumn(format="%.1f %%"),
                "Raison principale": st.column_config.TextColumn(width="large"),
            },
            height=min(360, 42 + 35 * len(sub)),
        )

        # ── Drill-down inline ────────────────────────────────────────────────
        selected_rows = event.selection.get("rows", []) if event and event.selection else []
        if selected_rows:
            row = sub.iloc[selected_rows[0]]
            st.markdown("---")
            h1, h2, h3, h4 = st.columns([3, 1, 1, 1])
            with h1:
                st.markdown(
                    f"<div style='font-size:18px;font-weight:700;color:{COLORS['text']}'>"
                    f"{row['company_name']}</div>"
                    f"<div style='font-size:13px;color:{COLORS['text2']};margin-top:2px'>"
                    f"Plan {row['plan'].capitalize()} ({row['mrr']:,.0f} €/mois)</div>",
                    unsafe_allow_html=True,
                )
            with h2:
                st.metric("Score churn", f"{row['churn_risk_score']:.1%}")
            with h3:
                st.metric("Santé", f"{row['health_score']}/100")
            with h4:
                st.markdown(f"<div style='margin-top:8px'>{risk_badge(tier)}</div>",
                            unsafe_allow_html=True)

            col_shap, col_actions = st.columns([1.2, 1], gap="large")
            with col_shap:
                st.markdown("**Drivers SHAP : pourquoi ce score ?**")
                # Vrais SHAP stockés avec la prédiction du compte ; gabarit par
                # tier uniquement si le compte n'a pas été scoré.
                # Convention : shap > 0 pousse le risque vers le haut (rouge).
                drivers, shap_live = shap_drivers_for_account(row)
                features = [d[0] for d in drivers]
                values   = [d[1] for d in drivers]
                fig = go.Figure(go.Bar(
                    x=values,
                    y=[feature_label(f) for f in features],
                    orientation="h",
                    marker_color=[COLORS["danger"] if v > 0 else COLORS["ok"]
                                  for v in values],
                    text=[f"{v:+.2f}" for v in values],
                    textposition="outside",
                    cliponaxis=False,        # labels jamais coupés au bord du plot
                ))
                # plage x symétrique avec 35% de marge : les labels "outside"
                # des barres extrêmes restent entièrement lisibles
                _xmax = max(abs(v) for v in values) if values else 1.0
                fig.update_xaxes(range=[-_xmax * 1.35, _xmax * 1.35])
                fig.update_layout(
                    height=230, margin=dict(t=8, l=10, r=50, b=8),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=True, gridcolor=COLORS["border_soft"],
                               zeroline=True, zerolinecolor=COLORS["border"]),
                    yaxis=dict(showgrid=False), showlegend=False,
                    font=dict(family="Inter, system-ui, sans-serif",
                              color=COLORS["text"]),
                )
                st.plotly_chart(fig, use_container_width=True)
                if not shap_live:
                    st.caption("Valeurs indicatives par tier : ce compte n'a pas encore de prédiction scorée en base.")

            with col_actions:
                st.markdown("**Actions recommandées**")
                for action in ACTIONS.get(tier, []):
                    st.markdown(
                        f'<div style="display:flex;align-items:flex-start;gap:8px;'
                        f'padding:6px 0;color:{COLORS["text"]};font-size:13px;">'
                        f'<span style="color:{tc};font-weight:700;">›</span>'
                        f'<span>{action}</span></div>',
                        unsafe_allow_html=True,
                    )
                if row["invoices_overdue"] > 0:
                    st.warning(
                        f"{int(row['invoices_overdue'])} facture(s) en retard : "
                        "contacter le service financier.",
                        icon=":material/receipt_long:",
                    )
