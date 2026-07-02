"""Page Monitoring : résultats qualité, état du drift et métriques de performance du modèle."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

import streamlit as st
from data.loader import load_monitoring_data
from ui.components import COLORS, inject_base_css, kpi_card, page_header, section_header

# ── Thème Plotly ─────────────────────────────────────────────────────────────
pio.templates["cairn"] = go.layout.Template(layout=dict(
    paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
    font=dict(family="Inter, system-ui, sans-serif", color=COLORS["text"], size=13),
    colorway=[COLORS["primary"], COLORS["secondary"], COLORS["ok"],
              COLORS["warn"], COLORS["danger"]],
    xaxis=dict(showgrid=False, zeroline=False,
               linecolor=COLORS["border"], tickcolor=COLORS["border"]),
    yaxis=dict(gridcolor=COLORS["border_soft"], zerolinecolor=COLORS["border"]),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=COLORS["border"]),
    hoverlabel=dict(bgcolor=COLORS["card"], bordercolor=COLORS["primary"],
                    font=dict(color=COLORS["text"], family="Inter")),
    margin=dict(t=32, l=8, r=8, b=8),
))
pio.templates.default = "cairn"

# ── CSS local (le CSS commun vient de inject_base_css) ──────────────────────
inject_base_css()


def _style_status_row(row):
    status = row.get("Statut") or row.get("status")
    if status == "Fail":
        return [f"background-color:{COLORS['danger_soft']};color:{COLORS['text']};"] * len(row)
    if status == "Warn":
        return [f"background-color:{COLORS['warn_soft']};color:{COLORS['text']};"] * len(row)
    return [""] * len(row)


# ── Filtres sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("##### Filtres Monitoring")
    drift_threshold = st.slider(
        "Seuil PSI", min_value=0.05, max_value=0.40, value=0.20, step=0.01,
        help="PSI ≥ seuil : feature considérée en drift. Standard : 0.10 warning, 0.20 action.",
    )
    st.markdown("---")
    rerun = st.button("Relancer les tests", use_container_width=True,
                      type="secondary", icon=":material/refresh:")
    with st.expander("Paramètres avancés", icon=":material/tune:"):
        st.checkbox("Inclure les tests Warn", value=True, key="include_warn")
        st.checkbox("Bloquer pipeline si échec critique", value=True, key="block_on_fail")

if rerun:
    load_monitoring_data.clear()
    st.toast("Tests relancés", icon=":material/check_circle:")

data = load_monitoring_data()

# ── Titre de la page (page_header = titre léger, hors bloc) ─────────────────
page_header("Monitoring DataOps",
            "Suivi de la qualité des données, de la dérive et de la performance du modèle en production.")

# ── Ligne KPIs ───────────────────────────────────────────────────────────────
qc = data.quality_checks
n_fail = int((qc["status"] == "Fail").sum())
n_warn = int((qc["status"] == "Warn").sum())
n_pass = int((qc["status"] == "Pass").sum())
quality_score = round(100 * n_pass / max(len(qc), 1), 1)
drifted = int((data.drift_per_feature["latest_psi"] >= drift_threshold).sum())
total_f = len(data.drift_per_feature)
churn_pred = float(data.predictions["churn_risk_score"].mean()) * 100
churn_real = float(data.predictions["actual_churn"].mean()) * 100
fresh_min  = data.pipeline_health["freshness_minutes"]
rows_24h   = data.pipeline_health["rows_ingested_24h"]
m = data.model_metrics

# Composant kpi_card commun (ui/components) : même HTML et même ordre visuel
# que toutes les autres pages, plus de variante locale à maintenir.
cards = [
    kpi_card("Anomalies détectées", str(n_fail), f"sur {len(qc)} tests",
             delta_good=not n_fail, tone="alert" if n_fail else "ok"),
    kpi_card("Score Data Quality", f"{quality_score:.1f}%",
             f"{n_pass} réussis, {n_warn} avertissements",
             delta_good=quality_score >= 95,
             tone="alert" if quality_score < 90 else ("warn" if quality_score < 97 else "ok")),
    kpi_card("Taux churn prédit", f"{churn_pred:.1f}%",
             f"vs réel {churn_real:.1f}%", delta_good=None),
    kpi_card("Features en drift", f"{drifted}/{total_f}",
             f"seuil PSI ≥ {drift_threshold:.2f}",
             delta_good=not drifted, tone="alert" if drifted else "ok"),
    kpi_card("PR-AUC modèle", f"{m['pr_auc']:.3f}", "challenger XGBoost",
             delta_good=True, tone="ok"),
    kpi_card("F1-score", f"{m['f1']:.3f}",
             f"precision {m['precision']:.2f}, recall {m['recall']:.2f}",
             delta_good=None),
    kpi_card("Fraîcheur pipeline", f"{fresh_min} min", "depuis le dernier run",
             delta_good=None,
             tone="alert" if fresh_min > 360 else ("warn" if fresh_min > 180 else "ok")),
    kpi_card("Lignes ingérées 24h", f"{rows_24h:,}".replace(",", " "),
             "mise à jour quotidienne", delta_good=None),
]

with st.container(border=True):
    section_header("Indicateurs clés",
                   "État global du pipeline, score de qualité des données, performance du modèle et fraîcheur du dernier chargement.",
                   icon="speed")

    row1, row2 = cards[:4], cards[4:]
    cols = st.columns(4, gap="medium")
    for col, card in zip(cols, row1, strict=False):
        with col:
            st.markdown(card, unsafe_allow_html=True)
    st.markdown('<div style="height:0.75rem"></div>', unsafe_allow_html=True)
    cols = st.columns(4, gap="medium")
    for col, card in zip(cols, row2, strict=False):
        with col:
            st.markdown(card, unsafe_allow_html=True)

# ── Onglets ──────────────────────────────────────────────────────────────────
tab_drift, tab_quality, tab_model = st.tabs([
    ":material/show_chart: Data Drift",
    ":material/verified: Qualité & Anomalies",
    ":material/trending_up: Prédictions vs Réalité",
])

# ── Onglet 1 : Data Drift ────────────────────────────────────────────────────
with tab_drift:
  with st.container(border=True):
    section_header("Data Drift",
                   "Population Stability Index par feature au dernier run Evidently : écart entre la fenêtre de référence et la fenêtre courante.",
                   icon="trending_up")
    # Evidently produit un snapshot par run, pas d'historique : on trace donc
    # le PSI COURANT par feature (bar chart), pas une fausse série temporelle.
    dpf    = data.drift_per_feature.copy()
    as_of  = data.drift["day"].iloc[0] if not data.drift.empty else None

    col_chart, col_side = st.columns([2.2, 1], gap="medium")

    with col_chart:
        suffix = f" (snapshot du {pd.Timestamp(as_of):%d/%m/%Y})" if as_of is not None else ""
        st.markdown(f'<div class="cairn-section-title">PSI courant par feature{suffix}</div>',
                    unsafe_allow_html=True)
        dpf_sorted = dpf.sort_values("latest_psi")     # plus forte dérive en haut
        bar_colors = [
            COLORS["danger"] if v >= drift_threshold
            else (COLORS["warn"] if v >= drift_threshold * 0.6 else COLORS["ok"])
            for v in dpf_sorted["latest_psi"]
        ]
        fig = go.Figure(go.Bar(
            x=dpf_sorted["latest_psi"],
            y=dpf_sorted["feature"],
            orientation="h",
            marker_color=bar_colors,
            text=[f"{v:.3f}" for v in dpf_sorted["latest_psi"]],
            textposition="outside",
        ))
        fig.add_vline(x=drift_threshold, line_dash="dash",
                      line_color=COLORS["danger"], line_width=1.5,
                      annotation_text=f"Seuil critique ({drift_threshold:.2f})",
                      annotation_position="top",
                      annotation_font=dict(color=COLORS["danger"], size=11))
        fig.update_layout(
            height=max(380, 36 * len(dpf_sorted) + 60),
            xaxis_title="PSI", yaxis_title=None, showlegend=False,
            xaxis=dict(range=[0, max(float(dpf_sorted["latest_psi"].max()) * 1.25,
                                     drift_threshold * 1.5)]),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Un snapshot par run de pipeline (pas d'historique conservé) : "
                   "la tendance se lit en comparant les runs successifs.")

    with col_side:
        st.markdown('<div class="cairn-section-title">PSI par feature</div>', unsafe_allow_html=True)
        ranked = data.drift_per_feature.copy()
        ranked["status"] = ranked["latest_psi"].apply(
            lambda v: "Drift" if v >= drift_threshold
            else ("Watch" if v >= drift_threshold * 0.6 else "OK")
        )
        ranked["latest_psi"] = ranked["latest_psi"].round(3)
        ranked["mean_psi"]   = ranked["mean_psi"].round(3)
        ranked["max_psi"]    = ranked["max_psi"].round(3)
        st.dataframe(
            ranked[["feature", "latest_psi", "mean_psi", "max_psi", "status"]],
            hide_index=True, use_container_width=True,
            column_config={
                "feature":    "Feature",
                "latest_psi": st.column_config.NumberColumn("PSI courant", format="%.3f"),
                "mean_psi":   st.column_config.NumberColumn("PSI moyen",   format="%.3f"),
                "max_psi":    st.column_config.NumberColumn("PSI max",     format="%.3f"),
                "status":     "Statut",
            },
        )

    with st.expander("Méthode de détection (PSI / Evidently)", icon=":material/info:"):
        st.markdown("""
        Le **Population Stability Index (PSI)** mesure l'écart entre la distribution
        d'une feature en production et celle du jeu d'entraînement de référence.

        - PSI < 0.10 : stable
        - 0.10 ≤ PSI < 0.20 : dérive significative, à surveiller
        - PSI ≥ 0.20 : dérive critique, action requise
        """)



# ── Onglet 2 : Qualité ───────────────────────────────────────────────────────
with tab_quality:
  with st.container(border=True):
    section_header("Qualité & Anomalies",
                   "Résultats des tests Great Expectations exécutés à chaque chargement, avec détail des anomalies détectées.",
                   icon="verified")

    qc2 = data.quality_checks.copy()
    if not st.session_state.get("include_warn", True):
        qc2 = qc2[qc2["status"] != "Warn"]

    nf2 = int((qc2["status"] == "Fail").sum())
    nw2 = int((qc2["status"] == "Warn").sum())
    np2 = int((qc2["status"] == "Pass").sum())
    nr2 = int(qc2["n_failed"].sum())

    c1, c2, c3, c4 = st.columns(4, gap="small")
    c1.markdown(kpi_card("Tests exécutés", str(len(qc2))), unsafe_allow_html=True)
    c2.markdown(kpi_card("Pass", str(np2), tone="ok"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Warn", str(nw2), tone="warn" if nw2 else ""), unsafe_allow_html=True)
    c4.markdown(kpi_card("Fail", str(nf2), delta=f"{nr2} lignes affectées",
                         delta_good=not nf2,
                         tone="alert" if nf2 else ""), unsafe_allow_html=True)

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    fcat, fstatus = st.columns([1, 1])
    cat_filter    = fcat.multiselect("Catégories", sorted(qc2["category"].unique()),
                                     default=sorted(qc2["category"].unique()))
    status_filter = fstatus.multiselect("Statuts", ["Pass", "Warn", "Fail"],
                                        default=["Pass", "Warn", "Fail"])
    view = qc2[qc2["category"].isin(cat_filter) & qc2["status"].isin(status_filter)].rename(
        columns={"test_name": "Test Name", "category": "Catégorie",
                 "status": "Statut", "n_failed": "Lignes en échec", "message": "Message"}
    )
    styled = view.style.apply(_style_status_row, axis=1)
    st.dataframe(styled, hide_index=True, use_container_width=True,
                 column_config={
                     "Lignes en échec": st.column_config.NumberColumn(format="%d"),
                     "Message":         st.column_config.TextColumn(width="large"),
                 })

    fails = qc2[qc2["status"] == "Fail"]
    if not fails.empty:
        st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
        for _, r in fails.iterrows():
            st.markdown(
                f'<div style="border-left:3px solid {COLORS["danger"]};padding:10px 16px;'
                f'border-radius:0 8px 8px 0;background:{COLORS["danger_soft"]};'
                f'margin-bottom:8px;">'
                f'<div style="font-weight:600;color:{COLORS["danger"]}">{r["test_name"]}</div>'
                f'<div style="font-size:12px;color:{COLORS["text2"]};margin-top:2px">'
                f'{r["category"]}</div>'
                f'<div style="font-size:13px;color:{COLORS["text"]};margin-top:6px">'
                f'{r["message"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ── Onglet 3 : Prédictions ───────────────────────────────────────────────────
with tab_model:
  with st.container(border=True):
    section_header("Prédictions vs Réalité",
                   "Comparaison des prédictions du modèle avec les valeurs réelles, distribution des scores et matrice de confusion.",
                   icon="model_training")

    m2    = data.model_metrics
    preds = data.predictions

    c1, c2, c3, c4 = st.columns(4, gap="small")
    c1.markdown(kpi_card("PR-AUC",   f"{m2['pr_auc']:.3f}", "métrique champion",
                         delta_good=True, tone="ok"), unsafe_allow_html=True)
    c2.markdown(kpi_card("ROC-AUC",  f"{m2['roc_auc']:.3f}", "sur set hold-out",
                         delta_good=None), unsafe_allow_html=True)
    c3.markdown(kpi_card("Precision", f"{m2['precision']:.3f}",
                         f"TP={m2['tp']}, FP={m2['fp']}", delta_good=None),
                unsafe_allow_html=True)
    c4.markdown(kpi_card("Recall",    f"{m2['recall']:.3f}",
                         f"FN={m2['fn']}, TN={m2['tn']}", delta_good=None),
                unsafe_allow_html=True)

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    col_l, col_r = st.columns(2, gap="medium")

    with col_l:
        st.markdown('<div class="cairn-section-title">Distribution du score de churn</div>',
                    unsafe_allow_html=True)
        from ui.components import RISK_COLORS
        fig_hist = px.histogram(
            preds, x="churn_risk_score", color="churn_risk_tier", nbins=40,
            category_orders={"churn_risk_tier": ["low", "medium", "high", "critical"]},
            color_discrete_map=RISK_COLORS,
        )
        fig_hist.update_layout(height=340, xaxis_title="Score de churn",
                               yaxis_title="Comptes", legend_title="Tier")
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_r:
        st.markdown('<div class="cairn-section-title">Matrice de confusion (seuil 0.50)</div>',
                    unsafe_allow_html=True)
        cm = pd.DataFrame(
            [[m2["tn"], m2["fp"]], [m2["fn"], m2["tp"]]],
            index=["Réel: non-churn", "Réel: churn"],
            columns=["Prédit: non-churn", "Prédit: churn"],
        )
        fig_cm = px.imshow(cm, text_auto=True, aspect="auto",
                           color_continuous_scale=[(0, COLORS["primary_50"]),
                                                   (0.5, COLORS["primary"]),
                                                   (1, COLORS["primary_dark"])])
        fig_cm.update_layout(height=340)
        st.plotly_chart(fig_cm, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
_footer_right = ("Mode démo (données simulées)"
                 if "synthetic" in data.pipeline_health["data_source"]
                 else data.pipeline_health["data_source"])
st.markdown(
    f'<div style="margin-top:24px;padding-top:14px;border-top:1px solid {COLORS["border"]};'
    f'font-size:11px;color:{COLORS["muted"]};text-align:right;">'
    f'{_footer_right}</div>',
    unsafe_allow_html=True,
)
