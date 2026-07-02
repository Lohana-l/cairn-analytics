"""
État du pipeline : Cairn Analytics
Vue ops complète : orchestration (Prefect), ingestion, API SLO (FastAPI + Prometheus), MLflow

Architecture des données :
  - Sources réelles tentées en premier (Prefect API, Prometheus, MLflow, Postgres)
  - Fallback synthétique si les services sont down, badge "Mode démo"
  - PromQL issues de observability/grafana/dashboards/api_slo.json
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

import streamlit as st
from data.loader import DEMO_MODE, fmt_dt, load_pipeline_data
from ui.components import COLORS, inject_base_css, kpi_card, section_header

# ── Thème Plotly ──────────────────────────────────────────────────────────────
pio.templates["cairn"] = go.layout.Template(layout=dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
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

# ── CSS ───────────────────────────────────────────────────────────────────────
inject_base_css()
st.html("""<style>
/* Bandeau de statut global */
.pipeline-banner {
    padding: 11px 18px;
    border-radius: 10px;
    border: 1px solid;
    margin-bottom: 20px;
    font-size: 13px;
    font-weight: 500;
    color: #0F172A;
    display: flex;
    align-items: center;
    gap: 10px;
}
/* Indicateur rond statut */
.sdot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
/* Badge de run (Completed / Failed / Running) */
.run-badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
/* Ligne de run dans la timeline */
.run-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 0;
    border-bottom: 1px solid #F1F5F9;
    font-size: 13px;
    color: #0F172A;
}
.run-row:last-child { border-bottom: none; }
/* En-tête modèle MLflow */
.model-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 11px 15px;
    background: #F4FBFB;
    border-radius: 8px;
    border: 1px solid #E2E8F0;
    margin-bottom: 16px;
    flex-wrap: wrap;
}
/* Strip de statut par source (live / simulé) */
.src-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 22px;
}
.src-chip {
    display: inline-flex;
    align-items: center;
    padding: 5px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
}
/* Pastille "données simulées" en tête de section */
.demo-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    color: #B45309;
    background: rgba(234,88,12,0.10);
    border: 1px solid rgba(234,88,12,0.25);
    margin: 0 0 14px 0;
}
</style>""")

# ── Données ───────────────────────────────────────────────────────────────────
data = load_pipeline_data()
p    = data.prefect_kpis
ing  = data.ingestion_kpis
api  = data.api_kpis
ml   = data.model_info


# ── Helpers ───────────────────────────────────────────────────────────────────
def tip(text: str) -> str:
    """Tooltip ? inline sur la même ligne que le label."""
    return (
        f'<span class="tip" title="{text}">?</span>'
    )


def sdot(color: str) -> str:
    return f'<span class="sdot" style="background:{color};"></span>'


def run_badge(status: str) -> str:
    cfg = {
        "Completed": (COLORS["ok"],      "rgba(16,185,129,0.10)"),
        "Failed":    (COLORS["danger"],  "rgba(220,38,38,0.10)"),
        "Crashed":   (COLORS["danger"],  "rgba(220,38,38,0.10)"),
        "Running":   (COLORS["secondary"], "rgba(245,158,11,0.10)"),
        "Pending":   (COLORS["muted"],   "rgba(148,163,184,0.10)"),
    }
    color, bg = cfg.get(status, (COLORS["muted"], "rgba(148,163,184,0.10)"))
    return (
        f'<span class="run-badge" style="background:{bg};color:{color};">'
        f'{status}</span>'
    )


# ── Statut des sources : live d'abord, simulé signalé clairement ───────────────
# Clé interne (dans demo_sources) -> libellé affiché.
SOURCES = [
    ("Prefect",    "Orchestration (Prefect)"),
    ("Ingestion",  "Ingestion (Postgres)"),
    ("Prometheus", "API / SLO (Prometheus)"),
    ("MLflow",     "Modèle ML (MLflow)"),
]
_demo  = set(data.demo_sources)
n_live = sum(1 for k, _ in SOURCES if k not in _demo) if not DEMO_MODE else 0

last_run_ts  = data.flow_runs["started_at"].iloc[0] if not data.flow_runs.empty else None
last_run_str = fmt_dt(last_run_ts, "%H:%M", default="(en attente)")


def src_live(key: str) -> bool:
    """True si la source est réellement connectée (live)."""
    return (key not in _demo) and not DEMO_MODE


def demo_pill(key: str) -> None:
    """Affiche une pastille 'données simulées' si la source n'est pas live."""
    if not src_live(key):
        st.markdown(
            '<div class="demo-pill">Source non connectée (données simulées)</div>',
            unsafe_allow_html=True,
        )


# ── Bandeau de mode (factuel : live / partiel / démo) ──────────────────────────
if DEMO_MODE:
    b_bg, b_border, b_dot = COLORS["warn_soft"], COLORS["warn"], COLORS["warn"]
    b_text = (
        "Mode démonstration (DEMO_MODE=1) : toutes les données sont simulées. "
        "Lancez la stack docker et retirez DEMO_MODE pour passer en live."
    )
elif not _demo:
    b_bg, b_border, b_dot = COLORS["ok_soft"], COLORS["ok"], COLORS["ok"]
    b_text = (
        f"Données live : 4/4 sources connectées (Prefect, Postgres, Prometheus, MLflow). "
        f"Dernier run Prefect à {last_run_str}."
    )
else:
    b_bg, b_border, b_dot = COLORS["secondary_soft"], COLORS["secondary"], COLORS["secondary"]
    _live_lbls = ", ".join(lbl for k, lbl in SOURCES if k not in _demo) or "aucune"
    _demo_lbls = ", ".join(lbl for k, lbl in SOURCES if k in _demo)
    b_text = (
        f"Mode partiel : {n_live}/4 sources en live ({_live_lbls}). "
        f"Non connectées (données simulées) : {_demo_lbls}."
    )

st.markdown(
    f'<div class="pipeline-banner" style="background:{b_bg};border-color:{b_border};">'
    f'{sdot(b_dot)}&nbsp;{b_text}'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Strip par source ───────────────────────────────────────────────────────────
_chips = ""
for _k, _lbl in SOURCES:
    _is_live = src_live(_k)
    _c  = COLORS["ok"] if _is_live else COLORS["muted"]
    _bg = "rgba(16,163,74,0.10)" if _is_live else "rgba(148,163,184,0.14)"
    _tag = "live" if _is_live else "simulé"
    _chips += (
        f'<span class="src-chip" style="background:{_bg};color:{_c};">'
        f'{sdot(_c)}&nbsp;{_lbl} : {_tag}</span>'
    )
st.markdown(f'<div class="src-strip">{_chips}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 : ORCHESTRATION (Prefect)
# ══════════════════════════════════════════════════════════════════════════════
with st.container(border=True):
    section_header(
        "Orchestration (Prefect)",
        "Historique d'exécution des flows Prefect (daily_refresh, intraday_predict) avec leurs durées et statuts.",
        icon="schedule",
    )
    demo_pill("Prefect")

    sr_tone = "ok" if p["success_rate_7d"] >= 90 else ("warn" if p["success_rate_7d"] >= 75 else "alert")
    c1, c2, c3 = st.columns(3, gap="medium")
    c1.markdown(
        kpi_card(
            "Taux de succès 7j", f"{p['success_rate_7d']} %",
            delta="objectif ≥ 90 %",
            delta_good=p["success_rate_7d"] >= 90,
            tone=sr_tone,
        ),
        unsafe_allow_html=True,
    )
    c2.markdown(
        kpi_card("Durée moyenne", f"{p['avg_duration_min']} min", delta="par run"),
        unsafe_allow_html=True,
    )
    c3.markdown(
        kpi_card("Prochain run", p["next_run_at"], delta="daily_refresh (schedulé)"),
        unsafe_allow_html=True,
    )

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="cairn-section-title">Derniers runs</div>',
        unsafe_allow_html=True,
    )

    if data.flow_runs.empty:
        st.markdown(
            '<div style="color:#9BA5C0;font-size:13px;padding:8px 0;">'
            'Aucune exécution démarrée pour le moment.</div>',
            unsafe_allow_html=True,
        )
    rows_html = ""
    for _, row in data.flow_runs.head(10).iterrows():
        t   = fmt_dt(row["started_at"], "%d/%m à %H:%M", default="(planifié)")
        dv  = row["duration_min"]
        dur = f"{dv:.1f} min" if pd.notna(dv) else "(en cours)"
        nc  = COLORS["primary"] if row["flow_name"] == "daily_refresh" else COLORS["secondary_dark"]
        rows_html += (
            f'<div class="run-row">'
            f'<span style="width:145px;font-weight:600;color:{nc};font-size:12px;flex-shrink:0;">'
            f'{row["flow_name"]}</span>'
            f'{run_badge(row["status"])}'
            f'<span style="color:#4A5568;margin-left:6px;">{t}</span>'
            f'<span style="color:#9BA5C0;margin-left:auto;white-space:nowrap;">'
            f'{dur}</span>'
            f'</div>'
        )
    st.markdown(f'<div>{rows_html}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 : INGESTION (Postgres, COPY idempotent)
# ══════════════════════════════════════════════════════════════════════════════
with st.container(border=True):
    section_header(
        "Ingestion (base de données)",
        "Volume réel chargé dans le warehouse, fraîcheur du dernier rafraîchissement et intégrité des tables sources.",
        icon="database",
    )
    demo_pill("Ingestion")

    f_tone = "ok" if ing["freshness_min"] <= 180 else ("warn" if ing["freshness_min"] <= 360 else "alert")
    e_tone = "alert" if ing["errors_24h"] > 0 else "ok"

    c1, c2, c3, c4 = st.columns(4, gap="medium")
    c1.markdown(
        kpi_card(
            f'Lignes en base (raw) {tip("Total des lignes chargées dans le schéma raw Postgres via COPY puis full refresh (la couche raw reflète exactement le dernier snapshot du seed), réparties sur les 5 tables sources.")}',
            f'{ing["total_rows"]:,}'.replace(",", " "),
            delta="réparties sur 5 tables sources",
        ),
        unsafe_allow_html=True,
    )
    c2.markdown(
        kpi_card(
            "Dernière mise à jour",
            f'{ing["freshness_min"]} min',
            delta="depuis le dernier run du pipeline",
            delta_good=ing["freshness_min"] <= 180,
            tone=f_tone,
        ),
        unsafe_allow_html=True,
    )
    c3.markdown(
        kpi_card(
            "Tables sources actives",
            str(ing["active_tables"]),
            delta="accounts, events, invoices, subscriptions, tickets",
        ),
        unsafe_allow_html=True,
    )
    c4.markdown(
        kpi_card(
            "Erreurs d'ingestion (24h)",
            str(ing["errors_24h"]),
            delta="pipeline propre" if ing["errors_24h"] == 0 else f'{ing["errors_24h"]} erreur(s)',
            delta_good=ing["errors_24h"] == 0,
            tone=e_tone,
        ),
        unsafe_allow_html=True,
    )

    st.markdown('<div style="height:0.75rem"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="cairn-section-title">Lignes par table source</div>',
        unsafe_allow_html=True,
    )

    bt = data.ingestion_by_table.sort_values("rows", ascending=True)
    fig_bar = go.Figure(go.Bar(
        x=bt["rows"], y=bt["table_name"],
        orientation="h",
        marker=dict(color=COLORS["primary"]),
        text=[f'{int(v):,}'.replace(",", " ") for v in bt["rows"]],
        textposition="auto",
        hovertemplate="%{y} : %{x:,} lignes<extra></extra>",
    ))
    fig_bar.update_layout(
        height=190,
        margin=dict(t=4, l=0, r=4, b=0),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False),
        bargap=0.35,
    )
    st.plotly_chart(fig_bar, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 : API (FastAPI, Prometheus, SLO)
# ══════════════════════════════════════════════════════════════════════════════
with st.container(border=True):
    section_header(
        "API de prédiction (FastAPI)",
        "Latence des prédictions, disponibilité du service et budget d'erreurs SLO restant sur la fenêtre courante.",
        icon="bolt",
    )
    demo_pill("Prometheus")

    p50_tone = "ok"    if api["p50_ms"] < 100  else "warn"
    p95_tone = "ok"    if api["p95_ms"] < 200  else ("warn" if api["p95_ms"] < 300 else "alert")
    up_tone  = "ok"    if api["uptime_pct"] >= 99.5 else "alert"

    c1, c2, c3 = st.columns(3, gap="medium")
    c1.markdown(
        kpi_card(
            f'Latence p50 {tip("50e percentile de latence : la requête médiane. Objectif < 100 ms.")}',
            f'{api["p50_ms"]} ms',
            delta="objectif < 100 ms",
            delta_good=api["p50_ms"] < 100,
            tone=p50_tone,
        ),
        unsafe_allow_html=True,
    )
    c2.markdown(
        kpi_card(
            f'Latence p95 {tip("95e percentile : 95 % des requêtes sont sous ce seuil. Objectif SLO < 200 ms.")}',
            f'{api["p95_ms"]} ms',
            delta="objectif < 200 ms",
            delta_good=api["p95_ms"] < 200,
            tone=p95_tone,
        ),
        unsafe_allow_html=True,
    )
    c3.markdown(
        kpi_card(
            f'Uptime {tip("Disponibilité mesurée sur les 30 derniers jours. SLO cible : 99.5 %.")}',
            f'{api["uptime_pct"]:.2f} %',
            delta="objectif ≥ 99.5 %",
            delta_good=api["uptime_pct"] >= 99.5,
            tone=up_tone,
        ),
        unsafe_allow_html=True,
    )

    st.markdown('<div style="height:0.75rem"></div>', unsafe_allow_html=True)

    col_gauge, col_chart = st.columns([1, 2.2], gap="medium")

    with col_gauge:
        budget = api["error_budget_pct"]
        _tip_budget = tip(
            "Service Level Objective : engagement de performance. "
            "SLO cible : p95 < 200 ms sur 99.5 % des requetes. "
            "Le budget d'erreurs = marge toleree avant violation. "
            "Vert > 50 %, ambre 20-50 %, rouge < 20 %."
        )
        st.markdown(
            f'<div class="cairn-section-title">Budget d\'erreurs SLO restant{_tip_budget}</div>',
            unsafe_allow_html=True,
        )
        g_color = COLORS["ok"] if budget > 50 else (COLORS["warn"] if budget > 20 else COLORS["danger"])
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=budget,
            number={"suffix": "%", "font": {"size": 30, "color": g_color, "family": "Inter"}},
            gauge={
                "axis":      {"range": [0, 100], "showticklabels": False, "ticks": ""},
                "bar":       {"color": g_color, "thickness": 0.55},
                "bgcolor":   COLORS["border_soft"],
                "borderwidth": 0,
                "steps": [
                    {"range": [0,  20],  "color": "rgba(220,38,38,0.08)"},
                    {"range": [20, 50],  "color": "rgba(245,158,11,0.08)"},
                    {"range": [50, 100], "color": "rgba(16,185,129,0.08)"},
                ],
            },
        ))
        fig_gauge.update_layout(height=210, margin=dict(t=20, l=12, r=12, b=0))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_chart:
        st.markdown(
            '<div class="cairn-section-title">Latence p50 / p95 / p99 (24h)</div>',
            unsafe_allow_html=True,
        )
        lat = data.api_latency_series
        fig_lat = go.Figure()
        fig_lat.add_trace(go.Scatter(
            x=lat["ts"], y=lat["p50_ms"], name="p50",
            line=dict(color=COLORS["primary"], width=1.8),
            hovertemplate="%{y:.0f} ms<extra>p50</extra>",
        ))
        fig_lat.add_trace(go.Scatter(
            x=lat["ts"], y=lat["p95_ms"], name="p95",
            line=dict(color=COLORS["warn"], width=1.8),
            hovertemplate="%{y:.0f} ms<extra>p95</extra>",
        ))
        fig_lat.add_trace(go.Scatter(
            x=lat["ts"], y=lat["p99_ms"], name="p99",
            line=dict(color=COLORS["danger"], width=1.8),
            hovertemplate="%{y:.0f} ms<extra>p99</extra>",
        ))
        fig_lat.add_hline(
            y=200, line_dash="dash", line_color=COLORS["warn"], line_width=1,
            annotation_text="SLO p95 (200 ms)",
            annotation_font=dict(color=COLORS["warn"], size=11),
        )
        fig_lat.update_layout(
            height=210,
            xaxis_title=None, yaxis_title="ms",
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_lat, use_container_width=True)

    # Lien vers Grafana
    st.link_button(
        "Ouvrir le dashboard Grafana API SLO (p50/p95/p99, burn rate, Loki logs)",
        "http://localhost:3200/d/api-slo",
        icon=":material/open_in_new:",
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 : MODÈLE ML (MLflow, Freshness, Drift)
# ══════════════════════════════════════════════════════════════════════════════
with st.container(border=True):
    section_header(
        "Modèle ML (MLflow)",
        "Version actuellement déployée en production, fraîcheur d'entraînement et indicateurs de dérive du modèle.",
        icon="psychology",
    )
    demo_pill("MLflow")

    fresh_d   = ml["freshness_days"]
    f_tone_ml = "ok" if fresh_d < 7 else ("warn" if fresh_d < 30 else "alert")
    drift_n   = ml["drift_features_above_threshold"]
    d_tone    = "ok" if drift_n == 0 else ("warn" if drift_n == 1 else "alert")

    # PSI >0.20 sur ≥2 features ET modèle >14j, ré-entraînement recommandé
    retrain = drift_n >= 2 and fresh_d > 14

    # En-tête modèle
    _ta = ml["trained_at"]
    trained_str = fmt_dt(_ta, "%d/%m/%Y à %H:%M", default="date inconnue")
    stage_color = COLORS["ok"] if ml["stage"] == "Production" else COLORS["warn"]
    stage_bg    = "rgba(16,185,129,0.10)" if ml["stage"] == "Production" else "rgba(234,88,12,0.10)"
    st.markdown(
        f'<div class="model-header">'
        f'<span style="font-weight:700;font-size:14px;color:{COLORS["text"]};">{ml["name"]}</span>'
        f'<span style="color:{COLORS["muted"]};">v{ml["version"]}</span>'
        f'<span style="padding:2px 10px;border-radius:999px;font-size:11px;font-weight:700;'
        f'background:{stage_bg};color:{stage_color};">{ml["stage"]}</span>'
        f'<span style="color:{COLORS["muted"]};font-size:12px;margin-left:auto;">'
        f'Entraîné le {trained_str}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3, gap="medium")
    c1.markdown(
        kpi_card(
            f'Fraîcheur du modèle {tip("Nombre de jours depuis le dernier entraînement. Un modèle exposé à du data drift sans ré-entraînement peut dégrader ses prédictions silencieusement.")}',
            f'{fresh_d}j',
            delta="moins de 7j idéal, moins de 30j acceptable",
            delta_good=fresh_d < 7,
            tone=f_tone_ml,
        ),
        unsafe_allow_html=True,
    )
    c2.markdown(
        kpi_card(
            "Prédictions (24h)",
            f'{ml["predictions_24h"]:,}'.replace(",", " "),
            delta="scoring batch (Prefect + MLflow)",
        ),
        unsafe_allow_html=True,
    )
    c3.markdown(
        kpi_card(
            f'Features en drift {tip("Features avec PSI ≥ 0.20 (seuil critique Evidently). Si 2+ features ET modèle > 14j sans ré-entraînement, alerte déclenchée.")}',
            str(drift_n),
            delta="seuil PSI ≥ 0.20",
            delta_good=drift_n == 0,
            tone=d_tone,
        ),
        unsafe_allow_html=True,
    )

    st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)

    if retrain:
        st.warning(
            f"Ré-entraînement recommandé : {drift_n} features en drift PSI ≥ 0.20 "
            f"et modèle âgé de {fresh_d}j (seuil : 2+ features ET > 14j).",
            icon=":material/warning:",
        )
    else:
        st.success(
            f"Modèle stable : {drift_n} feature(s) en drift, fraîcheur {fresh_d}j, "
            f"seuil de déclenchement non atteint (2+ features et plus de 14j requis).",
            icon=":material/check_circle:",
        )


# ── Footer ────────────────────────────────────────────────────────────────────
if DEMO_MODE:
    footer_right = "Mode démonstration (DEMO_MODE=1) : toutes les sources simulées"
elif data.demo_sources:
    sources_str = ", ".join(data.demo_sources)
    footer_right = f"Sources live + simulées ({sources_str} non connectée(s))"
else:
    footer_right = "Données live (Prefect, Postgres, Prometheus, MLflow)"

st.markdown(
    f'<div style="margin-top:24px;padding-top:14px;border-top:1px solid {COLORS["border"]};'
    f'font-size:11px;color:{COLORS["muted"]};text-align:right;">'
    f'{footer_right}</div>',
    unsafe_allow_html=True,
)
