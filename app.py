"""Point d'entrée Streamlit : branding, navigation multipage et footer du dashboard Cairn."""
from __future__ import annotations

import os

import streamlit as st

# ── Constantes de marque ──────────────────────────────────────────────────────
HERE         = os.path.dirname(__file__)
LOGO_FULL    = os.path.join(HERE, "ui", "logo.svg")
LOGO_ICON    = os.path.join(HERE, "ui", "logo_icon.svg")

PRIMARY      = "#7C3AED"   # violet-600
PRIMARY_DARK = "#5B21B6"   # violet-800
PRIMARY_SOFT = "#EDE9FE"   # violet-100
PRIMARY_50   = "#F5F3FF"   # violet-50
SECONDARY    = "#0EA5E9"   # sky-500
SECONDARY_DK = "#0369A1"   # sky-700
DANGER       = "#DC2626"
WARN         = "#EA580C"
OK           = "#16A34A"
MUTED        = "#94A3B8"
TEXT         = "#0F172A"
TEXT2        = "#475569"
BORDER       = "#E5E7EB"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cairn, Churn Intelligence",
    page_icon=LOGO_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Cairn, Churn Intelligence"},
)

# ── Logo natif Streamlit (persistant) ─────────────────────────────────────────
st.logo(LOGO_FULL, icon_image=LOGO_ICON, size="large")

# ── Statut pipeline calculé EN AMONT pour le 1er rendu ────────────────────────
data_source_label = "-"   # libellé pour les marts du dashboard (live vs fallback)
try:
    from data.loader import (
        fmt_dt,
        get_last_run_info,
        load_accounts_data,
        load_pipeline_data,
        load_revenue_data,
    )
    last_run, nb_fail = get_last_run_info()

    # ── Détection du mode des marts dashboard (revenue + accounts) ────────────
    # Si l'un des deux est en fallback synthétique, on l'indique en footer
    try:
        rev_demo = bool(load_revenue_data().get("demo_sources"))
        acc_demo = bool(load_accounts_data().get("demo_sources"))
        if not rev_demo and not acc_demo:
            data_source_label = "marts dbt (live)"
        elif rev_demo and acc_demo:
            data_source_label = "données démo (Postgres injoignable)"
        else:
            data_source_label = "données partiellement live"
    except Exception:
        data_source_label = "marts indisponibles"

    try:
        pdata = load_pipeline_data()
        ing  = pdata.ingestion_kpis
        runs = pdata.flow_runs

        recent_failed = (runs.head(5)["status"].isin(["Failed", "Crashed"]).any()
                         if not runs.empty else False)
        stale         = isinstance(ing, dict) and ing.get("freshness_min", 0) > 360
        warn_level    = isinstance(ing, dict) and ing.get("freshness_min", 0) > 180
        errs          = ing.get("errors_24h", 0) if isinstance(ing, dict) else 0

        if not runs.empty:
            last_run = fmt_dt(runs["started_at"].iloc[0], "%H:%M", default=last_run)

        if recent_failed or errs > 0:
            dot_color, status_label = DANGER, "incident détecté"
        elif stale:
            dot_color, status_label = WARN, "fraîcheur dégradée"
        elif warn_level:
            dot_color, status_label = SECONDARY, "à surveiller"
        else:
            dot_color, status_label = OK, "système opérationnel"
        tooltip = (f"Dernier run à {last_run} ({status_label}), "
                   f"{nb_fail} test(s) en échec, {errs} erreur(s) ingestion 24h. "
                   f"Source dashboard : {data_source_label}")
    except Exception:
        dot_color, status_label = OK, "OK"
        tooltip = f"Dernier run à {last_run}. Source dashboard : {data_source_label}"
except Exception:
    last_run, dot_color, status_label = "-", MUTED, "indisponible"
    tooltip = "Pipeline injoignable"

# ── CSS global injecté UNE SEULE FOIS ─────────────────────────────────────────
st.html(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
/* ============================================================
   POLICE UNIFIÉE : Inter (Streamlit + Plotly)
   Les icônes de section sont des SVG inline, pas de webfont.
   ============================================================ */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stSidebar"],
.stApp, .main, .block-container,
.kpi, .kpi *, .cairn-section-head *,
.cairn-alert, .cairn-alert *,
.js-plotly-plot, .js-plotly-plot *,
.modebar, .modebar *,
text, tspan {{
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
}}

/* ============================================================
   ANTI-FLASH + FOND CLAIR
   ============================================================ */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {{
    background-color: #FAFAFA !important;
    color: {TEXT} !important;
}}
[data-testid="stHeader"] {{
    background: transparent !important;
    height: 3rem !important;
}}
[data-testid="stMainBlockContainer"] {{
    padding-top: 3.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1400px;
    min-height: 100vh;
}}

/* ============================================================
   SIDEBAR (flex column natif pour ancrer le footer)
   ============================================================ */
[data-testid="stSidebar"] {{
    background-color: #FFFFFF !important;
    border-right: 1px solid {BORDER} !important;
}}
section[data-testid="stSidebar"] > div {{
    display: flex !important;
    flex-direction: column !important;
    height: 100vh !important;
    padding-bottom: 0 !important;
}}

/* Logo */
[data-testid="stSidebarHeader"] {{
    padding: 18px 16px 14px 16px !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-bottom: 1px solid {BORDER} !important;
    flex-shrink: 0 !important;
}}
[data-testid="stSidebarHeader"] img,
[data-testid="stLogo"] {{
    max-width: 100% !important;
    height: auto !important;
    max-height: 44px !important;
}}

/* Nav */
[data-testid="stSidebarNav"] {{
    padding-top: 12px !important;
    padding-bottom: 8px !important;
    flex-shrink: 0 !important;
}}
[data-testid="stSidebarUserContent"] {{
    margin-top: auto !important;
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
}}
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stSidebarUserContent"] > div,
[data-testid="stSidebarUserContent"] [data-testid="stMarkdownContainer"] {{
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}}

/* Items de nav : plus aérés, typo plus marquée */
[data-testid="stSidebarNavLink"] {{
    font-size: 14px !important;
    font-weight: 500 !important;
    color: {TEXT} !important;
    border-radius: 10px !important;
    margin: 3px 12px !important;
    padding: 10px 14px !important;
    transition: all 120ms ease;
    border-left: 3px solid transparent !important;
    gap: 12px !important;
}}
[data-testid="stSidebarNavLink"]:hover {{
    background-color: {PRIMARY_50} !important;
    color: {PRIMARY_DARK} !important;
    transform: translateX(2px);
}}
[data-testid="stSidebarNavLink"][aria-current="page"] {{
    background-color: {PRIMARY_SOFT} !important;
    color: {PRIMARY_DARK} !important;
    font-weight: 700 !important;
    border-left: 3px solid {PRIMARY} !important;
}}

/* Icônes nav TOUJOURS en couleur principale */
[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"],
[data-testid="stSidebarNavLink"] [class*="material-symbols"],
[data-testid="stSidebarNavLink"] [class*="material-icons"],
[data-testid="stSidebarNavLink"] svg {{
    color: {PRIMARY} !important;
    fill: {PRIMARY} !important;
}}
[data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stIconMaterial"],
[data-testid="stSidebarNavLink"][aria-current="page"] svg {{
    color: {PRIMARY_DARK} !important;
    fill: {PRIMARY_DARK} !important;
}}

/* Pastille pipeline (dernier item) */
[data-testid="stSidebarNav"] li:last-child a {{
    position: relative;
    --pipeline-dot: {dot_color};
}}
[data-testid="stSidebarNav"] li:last-child a::after {{
    content: "";
    position: absolute;
    right: 14px;
    top: 50%;
    transform: translateY(-50%);
    width: 9px; height: 9px; border-radius: 50%;
    background: var(--pipeline-dot, {MUTED});
    box-shadow: 0 0 0 2px #FFFFFF;
}}

/* ============================================================
   FOOTER SIDEBAR : minimal, sans cadre ni trait
   ============================================================ */
.cairn-footer {{
    border: none;
    border-top: none;
    padding: 14px 22px 18px 22px;
    background: transparent;
    font-size: 11.5px;
    color: {TEXT2};
    line-height: 1.55;
}}
.cairn-footer .dot {{
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 8px;
    vertical-align: middle;
}}
.cairn-footer .status {{ color: {TEXT2}; font-weight: 600; }}
.cairn-footer .meta {{
    color: {MUTED};
    font-size: 10.5px;
    margin-top: 3px;
    padding-left: 16px;
}}
</style>""")

# ── Navigation multipage ──────────────────────────────────────────────────────
pg = st.navigation([
    st.Page("pages/overview.py",   title="Overview",         icon=":material/home:",     default=True),
    st.Page("pages/revenue.py",    title="Revenue",          icon=":material/payments:"),
    st.Page("pages/accounts.py",   title="Accounts Health",  icon=":material/favorite:"),
    st.Page("pages/churn_risk.py", title="Churn Risk",       icon=":material/warning:"),
    st.Page("pages/monitoring.py", title="Monitoring",       icon=":material/sensors:"),
    st.Page("pages/pipeline.py",   title="État du pipeline", icon=":material/hub:"),
])

# ── Footer sidebar (rendu naturellement en bas via flex auto) ─────────────────
with st.sidebar:
    st.markdown(
        f"""
        <div class="cairn-footer" title="{tooltip}">
            <span class="dot" style="background:{dot_color};"></span>
            <span class="status">Pipeline : {status_label}</span>
            <div class="meta">Dernier run à {last_run}</div>
            <div class="meta">Source dashboard : {data_source_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Contenu de la page ────────────────────────────────────────────────────────
pg.run()
