"""Page Accounts Health : distribution du score de santé et fiche détaillée par compte."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import plotly.graph_objects as go

import streamlit as st
from data.loader import feature_label, load_accounts_data, shap_drivers_for_account
from ui.components import (
    COLORS,
    inject_base_css,
    kpi_card,
    risk_badge,
    section_header,
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

# ── Section 1 : Filtres + KPIs ────────────────────────────────────────────────
with st.container(border=True):
    section_header("Santé des comptes",
                   "Vue agrégée du portefeuille avec filtres par tier de risque, plan et MRR pour isoler les comptes à surveiller.",
                   icon="favorite")

    f1, f2, f3 = st.columns([1, 1, 2], gap="medium")
    with f1:
        tier_filter = st.selectbox("Tier de risque", ["Tous", "critical", "high", "medium", "low"])
    with f2:
        plan_filter = st.selectbox("Plan", ["Tous", "enterprise", "business", "pro", "free"])
    with f3:
        # Arrondir la borne haute à la dizaine supérieure pour éviter le label tronqué
        raw_max  = int(accounts["mrr"].max()) + 1
        mrr_max  = int(((raw_max + 49) // 50) * 50)      # arrondi à 50 €
        mrr_range = st.slider(
            "MRR (€)", 0, mrr_max, (0, mrr_max),
            step=50, format="%d €",
        )

    df = accounts.copy()
    if tier_filter != "Tous":
        df = df[df["risk_tier"] == tier_filter]
    if plan_filter != "Tous":
        df = df[df["plan"] == plan_filter]
    df = df[(df["mrr"] >= mrr_range[0]) & (df["mrr"] <= mrr_range[1])]

    st.markdown('<div style="height:0.75rem"></div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        st.markdown(kpi_card("Comptes affichés", str(len(df))), unsafe_allow_html=True)
    with c2:
        n_crit = int((df["risk_tier"] == "critical").sum())
        st.markdown(kpi_card("Critiques", str(n_crit),
                             tone="alert" if n_crit else ""),
                    unsafe_allow_html=True)
    with c3:
        n_inv = int((df["invoices_overdue"] > 0).sum())
        st.markdown(kpi_card("Factures en retard", str(n_inv),
                             tone="warn" if n_inv else ""),
                    unsafe_allow_html=True)
    with c4:
        mrr_total = df["mrr"].sum()
        st.markdown(kpi_card("MRR filtré", f"{mrr_total:,.0f} €", tone="ok"),
                    unsafe_allow_html=True)

# ── Section 2 : Tableau des comptes ──────────────────────────────────────────
with st.container(border=True):
    section_header("Liste des comptes",
                   f'<b style="color:{COLORS["text"]};font-weight:700;">{len(df)}</b> comptes affichés selon les filtres ci-dessus. Cliquer une ligne pour ouvrir la fiche détaillée avec les drivers SHAP.',
                   icon="format_list_bulleted")

    # FIX bug score de risque : churn_risk_score est entre 0 et 1.
    # On le multiplie par 100 explicitement pour afficher 88 % et non 1 %.
    df_view = df[[
        "company_name", "plan", "mrr", "health_score",
        "risk_tier", "churn_risk_score", "tickets_open",
        "invoices_overdue", "last_activity_days",
    ]].copy()
    df_view["churn_risk_score"] = (df_view["churn_risk_score"] * 100).round(1)

    event = st.dataframe(
        df_view.rename(columns={
            "company_name":      "Compte",
            "plan":              "Plan",
            "mrr":               "MRR",
            "health_score":      "Santé",
            "risk_tier":         "Tier",
            "churn_risk_score":  "Score de risque",
            "tickets_open":      "Tickets",
            "invoices_overdue":  "Factures OD",
            "last_activity_days":"Inactivité (j)",
        }),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Compte":           st.column_config.TextColumn(),
            "Plan":             st.column_config.TextColumn(),
            "MRR":              st.column_config.NumberColumn(format="%.0f €"),
            # Barre de santé colorée par seuil via min/max corrects
            "Santé":            st.column_config.ProgressColumn(
                                    min_value=0, max_value=100, format="%d %%"),
            "Tier":             st.column_config.TextColumn(),
            # FIX : score déjà × 100, format en %
            "Score de risque":  st.column_config.NumberColumn(format="%.1f %%"),
            "Tickets":          st.column_config.NumberColumn(format="%d"),
            "Factures OD":      st.column_config.NumberColumn(format="%d"),
            "Inactivité (j)":   st.column_config.NumberColumn(format="%d j"),
        },
        height=520,
    )

# ── Dialog drill-down ─────────────────────────────────────────────────────────
selected = event.selection.get("rows", []) if event and event.selection else []
if selected:
    row  = df.iloc[selected[0]]
    tier = row["risk_tier"]

    @st.dialog(f"Fiche compte : {row['company_name']}", width="large")
    def show_account():
        h1, h2, h3 = st.columns([3, 1, 1])
        with h1:
            st.markdown(
                f"<div style='font-size:16px;font-weight:700;color:{COLORS['text']}'>"
                f"{row['company_name']}</div>"
                f"<div style='font-size:13px;color:{COLORS['text2']}'>"
                f"Plan {row['plan'].capitalize()} ({row['mrr']:,.0f} €/mois)</div>",
                unsafe_allow_html=True,
            )
        with h2:
            st.metric("Score de risque", f"{row['churn_risk_score']:.1%}")
        with h3:
            st.metric("Santé", f"{row['health_score']}/100")
        st.markdown(risk_badge(tier), unsafe_allow_html=True)
        st.markdown("---")

        # Vrais SHAP du modèle (analytics.churn_predictions.top_drivers) ;
        # gabarit par tier seulement si le compte n'a pas de prédiction.
        # Convention : shap > 0 pousse le risque vers le haut (rouge).
        drivers, shap_live = shap_drivers_for_account(row)
        features = [d[0] for d in drivers]
        values   = [d[1] for d in drivers]
        fig = go.Figure(go.Bar(
            x=values,
            y=[feature_label(f) for f in features],
            orientation="h",
            marker_color=[COLORS["danger"] if v > 0 else COLORS["ok"] for v in values],
            text=[f"{v:+.2f}" for v in values],
            textposition="outside",
            cliponaxis=False,            # labels jamais coupés au bord du plot
        ))
        _xmax = max(abs(v) for v in values) if values else 1.0
        fig.update_xaxes(range=[-_xmax * 1.35, _xmax * 1.35])
        fig.update_layout(
            height=210, margin=dict(t=8, l=10, r=50, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor=COLORS["border_soft"],
                       zeroline=True, zerolinecolor=COLORS["border"]),
            yaxis=dict(showgrid=False), showlegend=False,
            title=dict(text="Drivers SHAP" + ("" if shap_live else " (indicatif)"),
                       font=dict(size=13)),
        )
        st.plotly_chart(fig, use_container_width=True)
        if not shap_live:
            st.caption("Valeurs indicatives par tier : ce compte n'a pas encore de prédiction scorée en base.")

        if row["invoices_overdue"] > 0:
            st.warning(
                f"{int(row['invoices_overdue'])} facture(s) en retard.",
                icon=":material/receipt_long:",
            )

    show_account()
