"""Composants partagés du dashboard : palette, cartes KPI, en-têtes de section.

Design system Cairn v6
----------------------
2 couleurs de marque, choisies pour parler à l'app (Churn Intelligence) :
  - Primaire   : violet   #7C3AED  (signal lumineux, intelligence, "cairn")
  - Secondaire : ciel     #0EA5E9  (signal data, accent froid complémentaire)

Hiérarchie visuelle :
  - Section = card blanche (border, padding généreux, pas d'ombre lourde)
  - En-tête : icône colorée dans un carré arrondi + titre GROS en primaire + desc
  - KPI : compactes, valeurs en texte sombre (jamais criardes), statut via accent

Palette sémantique (réservée strictement aux états) :
  critical #DC2626, high #EA580C, ok #16A34A
"""
from __future__ import annotations

import streamlit as st

# ── TOKENS ────────────────────────────────────────────────────────────────────
COLORS = {
    # - Couleur principale (violet, identité visuelle "Cairn") -
    "primary":      "#7C3AED",   # violet-600
    "primary_dark": "#5B21B6",   # violet-800 (titres, hover)
    "primary_soft": "#EDE9FE",   # violet-100 (backgrounds, icon squares)
    "primary_50":   "#F5F3FF",   # violet-50 (zones légères)

    # ─ Couleur secondaire (ciel : signal data, accent complémentaire) ─
    "secondary":      "#0EA5E9", # sky-500
    "secondary_dark": "#0369A1", # sky-700
    "secondary_soft": "#E0F2FE", # sky-100
    "secondary_50":   "#F0F9FF", # sky-50

    # ─ États ─
    "danger":       "#DC2626",
    "danger_soft":  "#FEE2E2",
    "warn":         "#EA580C",
    "warn_soft":    "#FFEDD5",
    "ok":           "#16A34A",
    "ok_soft":      "#DCFCE7",

    # ─ Surfaces / textes ─
    "bg":           "#FAFAFA",
    "card":         "#FFFFFF",
    "card_alt":     "#F5F3FF",
    "border":       "#E5E7EB",
    "border_soft":  "#F3F4F6",
    "text":         "#0F172A",
    "text2":        "#475569",
    "muted":        "#94A3B8",
}

RISK_COLORS = {
    "low":      "#16A34A",
    "medium":   "#7C3AED",
    "high":     "#EA580C",
    "critical": "#DC2626",
}


# ── CSS GLOBAL (composants contenu) ───────────────────────────────────────────
def inject_base_css() -> None:
    st.html(f"""<style>
    /* === BASE TYPO ============================================== */
    html, body {{
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }}

    /* === SECTION CARD : chaque st.container(border=True) = CARD AUTONOME
       Card blanche qui FLOTTE sur le fond gris.
       ============================================================
       LOGIQUE de détection :
         - On RESET tous les stVerticalBlockBorderWrapper à invisible
         - On stylise UNIQUEMENT ceux dont le 1er enfant est un markdown
           (= section_header), caractéristique des VRAIES sections.
         - Le wrapper extérieur a un autre wrapper en 1er enfant
           (pas un markdown), donc reste invisible. */

    /* RESET : tous les wrappers invisibles par défaut */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
        border-radius: 0 !important;
    }}

    /* CARD : SEULEMENT les wrappers dont le 1er enfant est un markdown
       qui contient un .cairn-section-head (= un vrai section_header).
       Comme ça :
         - les colonnes (st.columns) avec markdown autre ne deviennent PAS des cards
         - les wrappers extérieurs (1er enfant = autre wrapper) ne matchent pas */
    [data-testid="stVerticalBlockBorderWrapper"]:has(
        > div
        > [data-testid="stVerticalBlock"]
        > [data-testid="stElementContainer"]:first-child
        [data-testid="stMarkdown"] .cairn-section-head
    ) {{
        border: 1px solid {COLORS["border"]} !important;
        background: #FFFFFF !important;
        border-radius: 16px !important;
        box-shadow:
            0 1px 2px rgba(15,23,42,0.04),
            0 4px 14px rgba(15,23,42,0.06) !important;
        padding: 30px 32px !important;
        margin: 0 0 36px 0 !important;
    }}

    /* Force le gap au niveau du parent vertical block (flex) au cas où
       le margin-bottom des cards serait absorbé par Streamlit */
    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {{
        gap: 36px !important;
    }}

    /* Sécurité supplémentaire : chaque enfant direct du block principal
       doit avoir un espacement vertical clair */
    [data-testid="stMainBlockContainer"]
        > [data-testid="stVerticalBlock"]
        > [data-testid="stElementContainer"] {{
        margin-bottom: 0 !important;
    }}

    /* === SLIDERS / INPUTS ====================================== */
    [data-testid="stSlider"] [role="slider"] {{
        background-color: {COLORS["primary"]} !important;
        border-color: {COLORS["primary"]} !important;
        box-shadow: 0 0 0 3px rgba(124,58,237,0.18) !important;
    }}
    [data-testid="stSlider"] > div > div > div > div {{
        background: {COLORS["primary"]} !important;
    }}
    [data-testid="stSlider"] {{ padding: 0 6px; }}
    [data-testid="stSlider"] [data-baseweb="slider"] {{ margin: 0 8px; }}
    [data-testid="stSlider"] [data-testid="stTickBar"] > div,
    [data-testid="stSlider"] [data-baseweb="slider"] + div {{
        font-size: 11px !important;
        color: {COLORS["text2"]} !important;
        white-space: nowrap !important;
    }}

    /* === BOUTONS =============================================== */
    [data-testid="stBaseButton-primary"],
    .stButton > button[kind="primary"] {{
        background-color: {COLORS["primary"]} !important;
        border: 1px solid {COLORS["primary"]} !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 2px rgba(124,58,237,0.20) !important;
        transition: all 120ms ease;
    }}
    [data-testid="stBaseButton-primary"]:hover,
    .stButton > button[kind="primary"]:hover {{
        background-color: {COLORS["primary_dark"]} !important;
        border-color: {COLORS["primary_dark"]} !important;
        box-shadow: 0 2px 6px rgba(124,58,237,0.30) !important;
    }}
    [data-testid="stBaseButton-secondary"] {{
        border: 1px solid {COLORS["border"]} !important;
        color: {COLORS["text"]} !important;
        background: #FFFFFF !important;
        border-radius: 8px !important;
    }}
    [data-testid="stBaseButton-secondary"]:hover {{
        border-color: {COLORS["primary"]} !important;
        color: {COLORS["primary_dark"]} !important;
        background: {COLORS["primary_50"]} !important;
    }}

    /* === TABS ================================================== */
    [data-testid="stTabs"] button[aria-selected="true"] {{
        color: {COLORS["primary_dark"]} !important;
        border-bottom-color: {COLORS["primary"]} !important;
        font-weight: 700 !important;
    }}
    [data-testid="stTabs"] button[aria-selected="true"] p,
    [data-testid="stTabs"] button[aria-selected="true"] span {{
        font-weight: 700 !important;
        color: {COLORS["primary_dark"]} !important;
    }}

    /* === DATAFRAMES ============================================ */
    [data-testid="stDataFrame"] {{
        border: 1px solid {COLORS["border"]} !important;
        border-radius: 10px !important;
        overflow: hidden;
    }}

    /* === SECTION HEADER ========================================
       [icône carré violet] | TITRE (gros, primaire)
                              description (text2)
       ============================================================ */
    .cairn-section-head {{
        display: flex;
        align-items: flex-start;
        gap: 14px;
        margin: 0 0 18px 0;
        padding: 0 0 14px 0;
        border-bottom: 1px solid {COLORS["border_soft"]};
    }}
    .cairn-section-head .icon-box {{
        flex-shrink: 0;
        width: 42px; height: 42px;
        border-radius: 10px;
        background: {COLORS["primary_soft"]};
        color: {COLORS["primary_dark"]};
        display: flex;
        align-items: center; justify-content: center;
    }}
    .cairn-section-head .icon-box svg {{
        width: 22px; height: 22px;
        display: block;
    }}
    .cairn-section-head .text {{ flex: 1; min-width: 0; }}
    .cairn-section-head .title {{
        font-size: 19px;
        font-weight: 800;
        color: {COLORS["primary_dark"]};
        margin: 0 0 4px 0;
        line-height: 1.25;
        letter-spacing: -0.01em;
    }}
    .cairn-section-head .subtitle {{
        font-size: 13.5px;
        color: {COLORS["text2"]};
        margin: 0;
        line-height: 1.55;
        font-weight: 400;
    }}

    /* compatibilité avec anciens libellés CSS */
    .section-title, .cairn-section-title {{
        font-size: 14px;
        font-weight: 700;
        text-transform: none;
        letter-spacing: 0;
        color: {COLORS["primary_dark"]};
        margin: 0 0 8px 0;
    }}
    .section-sub, .cairn-section-subtitle {{
        font-size: 12.5px;
        color: {COLORS["text2"]};
        margin: 0;
    }}
    </style>""")

    st.html(f"""<style>
    /* === KPI : pas de card, juste un indicateur coloré à gauche
       + label + chiffre + delta. Posé directement dans la section. */
    .kpi {{
        border: none;
        border-left: 3px solid {COLORS["border"]};
        background: transparent;
        border-radius: 0;
        padding: 6px 0 6px 16px;
        height: 100%;
        min-height: 100px;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        gap: 6px;
        transition: border-color 120ms ease;
    }}
    .kpi:hover {{
        border-left-color: {COLORS["primary"]};
        box-shadow: none;
    }}
    .kpi .label {{
        font-size: 13px;
        font-weight: 700;
        color: {COLORS["text"]};
        text-transform: none;
        letter-spacing: 0;
        line-height: 1.35;
        display: flex; align-items: center; gap: 6px;
        margin: 0 0 4px 0;
    }}
    /* Sous-titre : juste sous le titre, en light, descriptif */
    .kpi .delta {{
        font-size: 11.5px;
        font-weight: 400;        /* LIGHT, pas bold */
        color: {COLORS["text2"]};
        line-height: 1.45;
        margin: 0 0 10px 0;       /* respiration avant le chiffre */
    }}
    /* Chiffre : plus modéré qu'avant, sobre, jamais en couleur */
    .kpi .value {{
        font-size: 22px;
        font-weight: 700;
        color: {COLORS["text"]};
        font-feature-settings: "tnum";
        line-height: 1.15;
        letter-spacing: -0.02em;
        margin: 0;
    }}

    /* Statut via accent gauche + petit point coloré */
    .kpi.alert    {{ border-left-color: {COLORS["danger"]}; }}
    .kpi.alert    .label::before {{ content: "●"; color: {COLORS["danger"]}; font-size: 10px; }}
    .kpi.warn     {{ border-left-color: {COLORS["warn"]}; }}
    .kpi.warn     .label::before {{ content: "●"; color: {COLORS["warn"]}; font-size: 10px; }}
    .kpi.ok       {{ border-left-color: {COLORS["ok"]}; }}
    .kpi.ok       .label::before {{ content: "●"; color: {COLORS["ok"]}; font-size: 10px; }}
    .kpi.primary  {{ border-left-color: {COLORS["primary"]}; }}
    .kpi.primary  .label::before {{ content: "●"; color: {COLORS["primary"]}; font-size: 10px; }}

    /* Sous-titre garde sa couleur sémantique mais reste en LIGHT (400) */
    .delta-up   {{ color: {COLORS["ok"]};     font-weight: 400; }}
    .delta-down {{ color: {COLORS["danger"]}; font-weight: 400; }}
    .delta-neutral {{ color: {COLORS["text2"]}; font-weight: 400; }}

    /* === TOOLTIP "?" =========================================== */
    .tip {{
        display: inline-block;
        width: 14px; height: 14px; border-radius: 50%;
        background: {COLORS["primary_soft"]};
        color: {COLORS["primary_dark"]};
        font-size: 9px; font-weight: 700;
        text-align: center; line-height: 14px;
        cursor: help; margin-left: 4px;
        vertical-align: middle;
    }}

    /* === ALERTE (MRR menacé) : sobre =========================== */
    .cairn-alert {{
        background: {COLORS["primary_50"]};
        border-left: 3px solid {COLORS["primary"]};
        border-radius: 10px;
        padding: 16px 20px;
        margin: 8px 0 16px 0;
    }}
    .cairn-alert .title {{
        font-weight: 700; color: {COLORS["primary_dark"]};
        font-size: 13px;
        margin-bottom: 6px;
        text-transform: none; letter-spacing: 0;
    }}
    .cairn-alert .body {{ color: {COLORS["text"]}; font-size: 13.5px; line-height: 1.55; }}

    /* === PILL ACCENT SKY ======================================= */
    .pill-accent {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 11px; font-weight: 700;
        background: {COLORS["secondary_soft"]};
        color: {COLORS["secondary_dark"]};
        text-transform: uppercase; letter-spacing: 0.05em;
    }}
    </style>""")


# ── ICÔNES SVG INLINE (Lucide-style, currentColor) ────────────────────────────
# Pas de webfont, donc pas de FOUC, rendu instantané sur les 6 pages.
_ICON_SVG = {
    "dashboard": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>',
    "trending_up": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>',
    "payments": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>',
    "waterfall_chart": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="20" x2="3" y2="10"/><line x1="9" y1="20" x2="9" y2="4"/><line x1="15" y1="20" x2="15" y2="8"/><line x1="21" y1="20" x2="21" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg>',
    "show_chart": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 7"/></svg>',
    "swap_vert": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="7 17 7 3 11 7"/><polyline points="3 7 7 3"/><polyline points="17 7 17 21 13 17"/><polyline points="21 17 17 21"/></svg>',
    "favorite": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
    "format_list_bulleted": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/></svg>',
    "monitoring": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
    "speed": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="9"/><polyline points="12 9 12 13 15 15"/><path d="M9 2h6"/></svg>',
    "verified": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 3 4-1 1 4 3 3-3 3 1 4-4 1-3 3-3-3-4 1-1-4-3-3 3-3-1-4 4 1z"/><polyline points="9 12 11 14 15 10"/></svg>',
    "model_training": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z"/><circle cx="19" cy="19" r="2"/><circle cx="5" cy="19" r="2"/><path d="M7 19h10"/></svg>',
    "schedule": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    "database": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v6c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 11v6c0 1.66 4 3 9 3s9-1.34 9-3v-6"/></svg>',
    "bolt": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    "psychology": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5a4 4 0 0 1 4 4v2h2a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2h-1v2a2 2 0 0 1-2 2H8"/><path d="M9 5a4 4 0 0 0-3.7 5.5"/><path d="M5.5 14a3 3 0 0 0 0 5"/><circle cx="10" cy="9" r="1"/></svg>',
    "warning": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    "hub": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2"/><circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><line x1="6.5" y1="6.5" x2="10.5" y2="10.5"/><line x1="17.5" y1="6.5" x2="13.5" y2="10.5"/><line x1="6.5" y1="17.5" x2="10.5" y2="13.5"/><line x1="17.5" y1="17.5" x2="13.5" y2="13.5"/></svg>',
    "sensors": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2"/><path d="M7.76 7.76A6 6 0 0 0 6 12c0 1.66.67 3.16 1.76 4.24"/><path d="M16.24 16.24A6 6 0 0 0 18 12a6 6 0 0 0-1.76-4.24"/><path d="M4.93 4.93A10 10 0 0 0 2 12c0 2.76 1.12 5.26 2.93 7.07"/><path d="M19.07 19.07A10 10 0 0 0 22 12c0-2.76-1.12-5.26-2.93-7.07"/></svg>',
    "insights": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4"/><path d="m4.93 4.93 2.83 2.83"/><path d="M2 12h4"/><path d="m4.93 19.07 2.83-2.83"/><path d="M12 22v-4"/><path d="m16.24 16.24 2.83 2.83"/><path d="M22 12h-4"/><path d="m16.24 7.76 2.83-2.83"/><circle cx="12" cy="12" r="3"/></svg>',
}


def _icon_svg(name: str, size: int = 22) -> str:
    svg = _ICON_SVG.get(name, _ICON_SVG["insights"])
    return svg.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)

# ── COMPONENTS ────────────────────────────────────────────────────────────────
def kpi_card(label: str, value: str, delta: str = "",
             delta_good: bool | None = True, tone: str = "") -> str:
    """Ordre visuel : titre (label) puis sous-titre (delta) en light puis valeur (chiffre).
    Le sous-titre vit directement sous le titre, jamais sous le chiffre.

    delta_good : True = vert, False = rouge, None = neutre (sous-titre
    purement informatif, sans lecture bon/mauvais).
    """
    if not delta or delta_good is None:
        delta_cls = "delta-neutral"
    else:
        delta_cls = "delta-up" if delta_good else "delta-down"
    cls = f"kpi {tone}".strip()
    delta_html = f'<div class="delta {delta_cls}">{delta}</div>' if delta else ""
    return (
        f'<div class="{cls}">'
        f'<div class="label">{label}</div>'
        f'{delta_html}'
        f'<div class="value">{value}</div>'
        f'</div>'
    )


def risk_badge(tier: str) -> str:
    color = RISK_COLORS.get(tier, COLORS["muted"])
    return (
        f'<span style="background:{color}22;color:{color};padding:3px 12px;'
        f'border-radius:999px;font-size:11px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.05em;">{tier}</span>'
    )


def section_header(title: str, subtitle: str = "", icon: str = "insights") -> None:
    """En-tête de section : icône SVG en carré violet + titre gros + desc.

    Args:
        title:    Titre principal (gros, primaire).
        subtitle: Description courte.
        icon:     Nom d'icône dans _ICON_SVG (dashboard, trending_up, payments,
                  waterfall_chart, show_chart, swap_vert, favorite,
                  format_list_bulleted, monitoring, speed, verified,
                  model_training, schedule, database, bolt, psychology,
                  warning, hub, sensors, insights).
    """
    svg = _icon_svg(icon, 22)
    sub = (f'<p class="subtitle">{subtitle}</p>' if subtitle else "")
    st.markdown(
        f'<div class="cairn-section-head">'
        f'  <div class="icon-box">{svg}</div>'
        f'  <div class="text">'
        f'    <h3 class="title">{title}</h3>{sub}'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "") -> None:
    """Titre de page standalone (petit, hors bloc, en haut de page)."""
    sub = (f'<p style="font-size:13.5px;color:{COLORS["text2"]};'
           f'margin:4px 0 24px;line-height:1.5;">'
           f'{subtitle}</p>' if subtitle else
           '<div style="height:24px;"></div>')
    st.markdown(
        f'<p style="font-size:22px;font-weight:800;color:{COLORS["text"]};'
        f'margin:0 0 2px;letter-spacing:-0.02em;">{title}</p>{sub}',
        unsafe_allow_html=True,
    )


def tip(text: str) -> str:
    return f'<span class="tip" title="{text}">?</span>'
