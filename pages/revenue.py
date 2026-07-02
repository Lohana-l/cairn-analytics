"""Page Revenue : tendance et waterfall du MRR, rétention nette, décomposition des mouvements."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import plotly.graph_objects as go

import streamlit as st
from data.loader import load_revenue_data
from ui.components import COLORS, inject_base_css, kpi_card, section_header, tip

inject_base_css()

rev     = load_revenue_data()
kpis    = rev["kpis"]
monthly = rev["mrr_monthly"]
moves   = rev["mrr_movements"]

# Cohérence avec la page Pipeline : tout fallback synthétique est annoncé
# en haut de page, pas seulement dans le footer de la sidebar.
if rev.get("demo_sources"):
    st.warning(
        "Données simulées pour : " + ", ".join(rev["demo_sources"])
        + ". Le warehouse est injoignable, les chiffres ci-dessous ne sont pas réels.",
        icon=":material/cloud_off:",
    )

# ── Section 1 : KPIs ──────────────────────────────────────────────────────────
with st.container(border=True):
    section_header("Revenus",
                   "Analyse du revenu mensuel récurrent (12 derniers mois)",
                   icon="payments")

    qr  = kpis["quick_ratio"]
    nrr = kpis["nrr"]

    tip_mrr   = tip("MRR : somme des revenus d'abonnements actifs sur le mois en cours.")
    tip_qr    = tip("(Nouveaux + Expansions) ÷ (Churns + Contractions). > 1 = croissance saine.")
    tip_nrr   = tip("Net Revenue Retention : % du MRR conservé et développé sur les comptes existants. > 100 % = expansion supérieure au churn.")
    mom_sign  = "+" if kpis["gross_mrr_mom"] >= 0 else "-"
    mom_delta = f"{mom_sign} {abs(kpis['gross_mrr_mom']):.1%} vs mois préc."

    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        st.markdown(kpi_card(
            f"Revenu brut mensuel {tip_mrr}",
            f"{kpis['gross_mrr']:,.0f} €",
            delta=mom_delta,
            delta_good=(kpis["gross_mrr_mom"] >= 0), tone="ok",
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_card(
            "Revenu net nouveau", f"{kpis['net_new_mrr']:+,.0f} €",
            delta="Nouveaux + Expansions - Contractions - Churns",
            delta_good=(kpis["net_new_mrr"] >= 0),
            tone="ok" if kpis["net_new_mrr"] >= 0 else "alert",
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_card(
            f"Quick Ratio {tip_qr}",
            f"{qr:.2f}",
            delta="(Nouveaux + Expansions) ÷ (Churns + Contractions)",
            delta_good=(qr >= 1), tone="ok" if qr >= 1 else "warn",
        ), unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_card(
            f"Rétention nette {tip_nrr}",
            f"{nrr:.0%}",
            delta="% du revenu conservé et développé sur les comptes existants",
            delta_good=(nrr >= 1), tone="ok" if nrr >= 1 else "warn",
        ), unsafe_allow_html=True)

# ── Section 2 : MRR Waterfall (convention chromatique unifiée) ────────────────
with st.container(border=True):
    section_header("Cascade du revenu mensuel",
                   "Décomposition du revenu mensuel en nouveaux abonnements, expansions, contractions et churns.",
                   icon="waterfall_chart")

    last = monthly.iloc[-1]
    fig_wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "relative", "total"],
        x=["Base", "Nouveau", "Expansion", "Contraction", "Churn", "MRR Final"],
        y=[last["mrr_start"], last["mrr_new"], last["mrr_expansion"],
           -last["mrr_contraction"], -last["mrr_churn"], last["mrr_end"]],
        connector=dict(line=dict(color=COLORS["border"], width=1)),
        # Convention unifiée avec overview.py
        increasing=dict(marker=dict(color=COLORS["primary"])),
        decreasing=dict(marker=dict(color=COLORS["danger"])),
        totals=dict(marker=dict(color=COLORS["text2"])),
        text=[f"{v:,.0f} €" for v in [
            last["mrr_start"], last["mrr_new"], last["mrr_expansion"],
            -last["mrr_contraction"], -last["mrr_churn"], last["mrr_end"],
        ]],
        textposition="outside",
    ))
    fig_wf.update_traces(cliponaxis=False)
    fig_wf.update_layout(
        # marges hautes généreuses pour éviter la coupe des labels valeur
        height=440, margin=dict(t=90, l=10, r=10, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(showgrid=True, gridcolor=COLORS["border_soft"],
                   zeroline=False, ticksuffix=" €", automargin=True,
                   rangemode="tozero"),
        xaxis=dict(showgrid=False, automargin=True), showlegend=False,
        font=dict(family="Inter, system-ui, sans-serif", color=COLORS["text"]),
    )
    # padding 18% en haut pour les labels "outside"
    y_max_wf = max(last["mrr_start"], last["mrr_end"]) * 1.18
    fig_wf.update_yaxes(range=[0, y_max_wf])
    st.plotly_chart(fig_wf, use_container_width=True)

# ── Section 3 : MRR Courbe ────────────────────────────────────────────────────
with st.container(border=True):
    section_header("Évolution MRR",
                   "Tendance du revenu mensuel récurrent sur les 12 derniers mois.",
                   icon="show_chart")

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=monthly["month"], y=monthly["mrr_end"],
        mode="lines+markers", name="MRR",
        line=dict(color=COLORS["primary"], width=2.5),
        fill="tozeroy", fillcolor="rgba(124,58,237,0.10)",
        marker=dict(size=6, color=COLORS["primary"]),
    ))
    fig_line.update_layout(
        height=280, margin=dict(t=16, l=0, r=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(showgrid=True, gridcolor=COLORS["border_soft"],
                   zeroline=False, ticksuffix=" €"),
        xaxis=dict(showgrid=False), showlegend=False,
        font=dict(family="Inter, system-ui, sans-serif", color=COLORS["text"]),
    )
    st.plotly_chart(fig_line, use_container_width=True)

# ── Section 4 : Mouvements du mois ───────────────────────────────────────────
with st.container(border=True):
    section_header("Mouvements du mois",
                   "Les 10 mouvements de revenu les plus importants observés sur le mois en cours.",
                   icon="swap_vert")

    last_month = moves[moves["month"] == monthly.iloc[-1]["month"]].copy()
    last_month["delta_mrr_abs"] = last_month["delta_mrr"].abs()
    last_month = last_month.sort_values("delta_mrr_abs", ascending=False).head(10)
    type_label = {"new": "Nouveau", "expansion": "Expansion",
                  "contraction": "Contraction", "churn": "Churn"}
    # Convention sémantique alignée :
    #   croissance = teal/ok, perte = danger/warn
    type_color = {
        "new":         COLORS["primary"],
        "expansion":   COLORS["ok"],
        "contraction": COLORS["warn"],
        "churn":       COLORS["danger"],
    }
    rows_html = []
    for _, r in last_month.iterrows():
        t = r["type"]
        c = type_color.get(t, COLORS["muted"])
        badge = (f'<span style="background:{c}22;color:{c};padding:2px 10px;'
                 f'border-radius:999px;font-size:11px;font-weight:700;'
                 f'letter-spacing:0.03em;">{type_label.get(t, t)}</span>')
        dc = COLORS["ok"] if r["delta_mrr"] > 0 else COLORS["danger"]
        rows_html.append(
            f'<tr><td style="padding:9px 12px;border-bottom:1px solid {COLORS["border_soft"]}">'
            f'{r["company"]}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid {COLORS["border_soft"]}">{badge}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid {COLORS["border_soft"]};text-align:right">'
            f'<span style="color:{dc};font-weight:600">{r["delta_mrr"]:+,.0f} €</span></td></tr>'
        )
    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
        f'<thead><tr style="border-bottom:1px solid {COLORS["border"]}">'
        f'<th style="text-align:left;padding:9px 12px;color:{COLORS["text2"]};'
        f'font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:0.05em;">Compte</th>'
        f'<th style="text-align:left;padding:9px 12px;color:{COLORS["text2"]};'
        f'font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:0.05em;">Type</th>'
        f'<th style="text-align:right;padding:9px 12px;color:{COLORS["text2"]};'
        f'font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:0.05em;">Δ MRR</th>'
        f'</tr></thead><tbody>' + "".join(rows_html) + '</tbody></table>',
        unsafe_allow_html=True,
    )
