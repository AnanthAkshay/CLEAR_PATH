"""ClearPath Dashboard Design System and Theme Tokens.

Provides modern soft mint UI styling, responsive breakpoints, dark mode support,
and shared design tokens for HTML components and Plotly charts.
"""

from __future__ import annotations
from typing import Dict, Any

# Design Tokens (Hex colors and CSS values)
TOKENS = {
    # Light Mode Tokens (Soft mint nutrition-app aesthetic)
    "light": {
        "bg": "#DDEBE1",
        "bg_gradient": "linear-gradient(180deg, #DDEBE1 0%, #E8F2EA 100%)",
        "surface": "#FFFFFF",
        "surface_muted": "#F4F8F5",
        "hero": "#CDE8BB",
        "hero_soft": "#E7EFD6",
        "hero_border": "#B5DC9C",
        "ink": "#14181F",
        "ink_muted": "#5B6770",
        "ink_light": "#8E9DA6",
        "nav": "#15171A",
        "nav_ink": "#FFFFFF",
        "accent": "#2E7D1F",
        "accent_light": "#45B334",
        "accent_bg": "#E3F4DF",
        "border": "rgba(20, 24, 31, 0.07)",
        "card_shadow": "0 8px 30px rgba(20, 40, 30, 0.06)",
        "card_shadow_hover": "0 12px 36px rgba(20, 40, 30, 0.10)",
        # Semantics
        "signal_green": "#3FB950",
        "signal_yellow": "#D29922",
        "signal_red": "#F85149",
        "ambulance": "#F28C28",
        "route_blue": "#388BFD",
        "info_blue": "#4DB6D6",
        # Pastel Chips
        "chip_green_bg": "#DDEFD9",
        "chip_green_ink": "#1E6B15",
        "chip_pink_bg": "#FBD9E3",
        "chip_pink_ink": "#A81D43",
        "chip_blue_bg": "#D9ECF8",
        "chip_blue_ink": "#155D8A",
        "chip_amber_bg": "#FBEBC8",
        "chip_amber_ink": "#87560B",
        # Road Grid Plotly
        "road_color": "#D0D9D3",
        "road_grid_bg": "rgba(255, 255, 255, 0.6)",
        "node_border": "#FFFFFF",
    },
    # Dark Mode Tokens
    "dark": {
        "bg": "#0D1411",
        "bg_gradient": "linear-gradient(180deg, #0D1411 0%, #131E18 100%)",
        "surface": "#16221B",
        "surface_muted": "#1B2A22",
        "hero": "#1B3B24",
        "hero_soft": "#14281B",
        "hero_border": "#2B5E39",
        "ink": "#EAF2EC",
        "ink_muted": "#8EA395",
        "ink_light": "#5D7365",
        "nav": "#090E0C",
        "nav_ink": "#FFFFFF",
        "accent": "#45B334",
        "accent_light": "#61C950",
        "accent_bg": "#142A1A",
        "border": "rgba(255, 255, 255, 0.08)",
        "card_shadow": "0 8px 30px rgba(0, 0, 0, 0.35)",
        "card_shadow_hover": "0 12px 36px rgba(0, 0, 0, 0.45)",
        # Semantics
        "signal_green": "#3FB950",
        "signal_yellow": "#D29922",
        "signal_red": "#F85149",
        "ambulance": "#F28C28",
        "route_blue": "#58A6FF",
        "info_blue": "#56D4F7",
        # Pastel Chips
        "chip_green_bg": "#163820",
        "chip_green_ink": "#68DB7B",
        "chip_pink_bg": "#3B1420",
        "chip_pink_ink": "#FF7B9C",
        "chip_blue_bg": "#122A3B",
        "chip_blue_ink": "#79C0FF",
        "chip_amber_bg": "#382910",
        "chip_amber_ink": "#E3B341",
        # Road Grid Plotly
        "road_color": "#273D30",
        "road_grid_bg": "rgba(22, 34, 27, 0.8)",
        "node_border": "#16221B",
    },
}


def get_theme_css(dark_mode: bool = False) -> str:
    """Generate complete responsive CSS injected into the Streamlit app."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    :root {{
        --cp-bg: {t['bg']};
        --cp-bg-gradient: {t['bg_gradient']};
        --cp-surface: {t['surface']};
        --cp-surface-muted: {t['surface_muted']};
        --cp-hero: {t['hero']};
        --cp-hero-soft: {t['hero_soft']};
        --cp-hero-border: {t['hero_border']};
        --cp-ink: {t['ink']};
        --cp-ink-muted: {t['ink_muted']};
        --cp-ink-light: {t['ink_light']};
        --cp-nav: {t['nav']};
        --cp-nav-ink: {t['nav_ink']};
        --cp-accent: {t['accent']};
        --cp-accent-light: {t['accent_light']};
        --cp-accent-bg: {t['accent_bg']};
        --cp-border: {t['border']};
        --cp-card-shadow: {t['card_shadow']};
        --cp-radius-card: 26px;
        --cp-radius-chip: 999px;
        --cp-radius-sm: 14px;
        --cp-signal-green: {t['signal_green']};
        --cp-signal-yellow: {t['signal_yellow']};
        --cp-signal-red: {t['signal_red']};
        --cp-ambulance: {t['ambulance']};
        --cp-info-blue: {t['info_blue']};
        --cp-chip-green-bg: {t['chip_green_bg']};
        --cp-chip-green-ink: {t['chip_green_ink']};
        --cp-chip-pink-bg: {t['chip_pink_bg']};
        --cp-chip-pink-ink: {t['chip_pink_ink']};
        --cp-chip-blue-bg: {t['chip_blue_bg']};
        --cp-chip-blue-ink: {t['chip_blue_ink']};
        --cp-chip-amber-bg: {t['chip_amber_bg']};
        --cp-chip-amber-ink: {t['chip_amber_ink']};
    }}

    /* Global Typography & Background */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background: var(--cp-bg-gradient) !important;
        background-color: var(--cp-bg) !important;
        color: var(--cp-ink) !important;
        box-sizing: border-box !important;
        overflow-x: hidden !important;
    }}

    *, *:before, *:after {{
        box-sizing: border-box !important;
    }}

    [data-testid="stHeader"] {{
        background: transparent !important;
    }}

    #MainMenu, footer {{
        visibility: hidden !important;
        display: none !important;
    }}

    /* Sidebar Styling */
    [data-testid="stSidebar"] {{
        background-color: var(--cp-surface) !important;
        border-right: 1px solid var(--cp-border) !important;
    }}
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {{
        color: var(--cp-ink) !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }}

    /* Container padding and responsive bounds */
    .block-container {{
        max-width: 1400px !important;
        padding-top: 1.5rem !important;
        padding-bottom: 5rem !important; /* Safe padding for bottom navigation */
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
    }}

    /* Card Container and Streamlit container wrappers */
    .cp-card, [data-testid="stVerticalBlockBorderWrapper"] {{
        background: var(--cp-surface) !important;
        border: 1px solid var(--cp-border) !important;
        border-radius: var(--cp-radius-card) !important;
        box-shadow: var(--cp-card-shadow) !important;
        padding: 20px 24px !important;
        margin-bottom: 20px !important;
        box-sizing: border-box !important;
    }}

    /* Header Bar */
    .cp-header-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 20px;
    }}
    .cp-brand {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    .cp-logo-icon {{
        width: 38px;
        height: 38px;
        background: var(--cp-accent);
        color: #FFFFFF;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 1.25rem;
    }}
    .cp-title {{
        font-size: clamp(1.5rem, 2.8vw, 2.2rem);
        font-weight: 800;
        color: var(--cp-ink);
        line-height: 1.15;
        letter-spacing: -0.02em;
        margin: 0;
    }}
    .cp-badge-pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: var(--cp-radius-chip);
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.01em;
    }}

    /* Hero Section */
    .cp-hero-container {{
        display: grid;
        grid-template-columns: 1.2fr 1fr;
        gap: 20px;
        margin-bottom: 20px;
    }}
    .cp-hero-savings {{
        background: var(--cp-surface);
        border-radius: var(--cp-radius-card);
        padding: 28px;
        box-shadow: var(--cp-card-shadow);
        border: 1px solid var(--cp-border);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}
    .cp-hero-label {{
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--cp-ink-muted);
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .cp-hero-number-wrap {{
        display: flex;
        align-items: baseline;
        gap: 14px;
        margin: 12px 0;
        flex-wrap: wrap;
    }}
    .cp-hero-number {{
        font-size: clamp(3.2rem, 6vw, 5.5rem);
        font-weight: 800;
        color: var(--cp-ink);
        line-height: 0.95;
        letter-spacing: -0.04em;
    }}
    .cp-hero-unit {{
        font-size: clamp(1.4rem, 2.5vw, 2.2rem);
        font-weight: 700;
        color: var(--cp-ink-muted);
    }}
    .cp-hero-chip {{
        display: inline-flex;
        align-items: center;
        padding: 6px 16px;
        border-radius: var(--cp-radius-chip);
        background: var(--cp-chip-green-bg);
        color: var(--cp-chip-green-ink);
        font-weight: 700;
        font-size: 0.95rem;
    }}

    /* Dual Progress Bar */
    .cp-dual-bar {{
        margin-top: 14px;
    }}
    .cp-dual-bar-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 0.78rem;
        color: var(--cp-ink-muted);
        margin-bottom: 4px;
    }}
    .cp-progress-track {{
        width: 100%;
        height: 8px;
        background: var(--cp-surface-muted);
        border-radius: 999px;
        overflow: hidden;
        margin-bottom: 8px;
        position: relative;
    }}
    .cp-progress-fill {{
        height: 100%;
        border-radius: 999px;
        transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }}

    /* Pale-Green Emergency Hero Card */
    .cp-active-emergency-card {{
        background: var(--cp-hero);
        border: 1px solid var(--cp-hero-border);
        border-radius: var(--cp-radius-card);
        padding: 26px;
        box-shadow: var(--cp-card-shadow);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}
    .cp-emg-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }}
    .cp-emg-title {{
        font-size: 1.15rem;
        font-weight: 800;
        color: #17371A;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .cp-emg-grid {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin: 12px 0;
    }}
    .cp-emg-item {{
        background: rgba(255, 255, 255, 0.55);
        border-radius: 16px;
        padding: 10px 14px;
    }}
    .cp-emg-item-lbl {{
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        color: #2F5733;
        margin-bottom: 2px;
    }}
    .cp-emg-item-val {{
        font-size: 1.05rem;
        font-weight: 800;
        color: #112814;
    }}

    /* KPI Row */
    .cp-kpi-grid {{
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 14px;
        margin-bottom: 22px;
    }}
    .cp-kpi-card {{
        background: var(--cp-surface);
        border: 1px solid var(--cp-border);
        border-radius: 20px;
        padding: 16px 18px;
        box-shadow: var(--cp-card-shadow);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}
    .cp-kpi-top {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 8px;
    }}
    .cp-kpi-label {{
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--cp-ink-muted);
    }}
    .cp-kpi-val {{
        font-size: 1.65rem;
        font-weight: 800;
        color: var(--cp-ink);
        line-height: 1.1;
        margin: 4px 0;
    }}
    .cp-kpi-bar {{
        width: 100%;
        height: 4px;
        background: var(--cp-surface-muted);
        border-radius: 999px;
        overflow: hidden;
        margin-top: 10px;
    }}
    .cp-kpi-bar-fill {{
        height: 100%;
        border-radius: 999px;
    }}

    /* Legend Row */
    .cp-legend-bar {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        margin-bottom: 14px;
    }}
    .cp-legend-chip {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 12px;
        border-radius: var(--cp-radius-chip);
        font-size: 0.78rem;
        font-weight: 700;
    }}
    .cp-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }}

    /* Security Status Banner */
    .cp-sec-banner {{
        border-radius: 18px;
        padding: 16px 20px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
    }}
    .cp-sec-banner-allow {{
        background: var(--cp-chip-green-bg);
        border: 1px solid var(--cp-chip-green-ink);
        color: var(--cp-chip-green-ink);
    }}
    .cp-sec-banner-block {{
        background: var(--cp-chip-pink-bg);
        border: 1px solid var(--cp-chip-pink-ink);
        color: var(--cp-chip-pink-ink);
    }}

    /* VMS Board Panel */
    .cp-vms-panel {{
        background: var(--cp-nav);
        color: #56D4F7;
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
        padding: 16px 20px;
        border-radius: 18px;
        box-shadow: inset 0 2px 8px rgba(0,0,0,0.4);
        margin-top: 14px;
    }}
    .cp-vms-header {{
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8E9DA6;
        margin-bottom: 8px;
    }}

    /* Guidance Item */
    .cp-advisory-item {{
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 12px 14px;
        border-radius: 16px;
        background: var(--cp-surface-muted);
        border: 1px solid var(--cp-border);
        margin-bottom: 8px;
        font-size: 0.85rem;
    }}

    /* Clean Audit & Tables */
    .cp-clean-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
    }}
    .cp-clean-table th {{
        text-align: left;
        padding: 10px 12px;
        border-bottom: 2px solid var(--cp-border);
        color: var(--cp-ink-muted);
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.72rem;
        letter-spacing: 0.04em;
    }}
    .cp-clean-table td {{
        padding: 10px 12px;
        border-bottom: 1px solid var(--cp-border);
        color: var(--cp-ink);
    }}

    /* Mobile Quick Controls Bar */
    .cp-mobile-controls {{
        display: none;
        background: var(--cp-surface);
        border: 1px solid var(--cp-border);
        border-radius: var(--cp-radius-card);
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: var(--cp-card-shadow);
    }}

    /* Touch target guarantee */
    button, [role="button"], .stButton > button {{
        min-height: 44px !important;
        border-radius: 14px !important;
        font-weight: 700 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        transition: all 0.2s ease !important;
    }}

    /* Pill Navigation Styling on Streamlit Tabs */
    [data-testid="stTabs"] [data-baseweb="tab-list"], [data-testid="stTabs"] [role="tablist"], .stTabs [data-baseweb="tab-list"] {{
        background-color: var(--cp-nav) !important;
        padding: 6px !important;
        border-radius: 999px !important;
        gap: 4px !important;
        border: none !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15) !important;
        justify-content: center !important;
    }}
    [data-testid="stTabs"] [data-baseweb="tab"], [data-testid="stTabs"] [role="tab"], .stTabs [data-baseweb="tab"] {{
        border-radius: 999px !important;
        color: #A0AEC0 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 8px 18px !important;
        border: none !important;
        background-color: transparent !important;
        transition: all 0.2s ease !important;
    }}
    [data-testid="stTabs"] [aria-selected="true"], .stTabs [aria-selected="true"] {{
        background-color: #FFFFFF !important;
        color: #15171A !important;
        font-weight: 800 !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.12) !important;
    }}
    [data-testid="stTabs"] [data-baseweb="tab-border"], [data-testid="stTabs"] [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{
        display: none !important;
    }}

    /* ── Responsive Breakpoints ────────────────────────────────────────────── */

    /* Tablet (640px to 1099px) */
    @media (max-width: 1099px) and (min-width: 640px) {{
        .cp-kpi-grid {{
            grid-template-columns: repeat(3, 1fr) !important;
        }}
        [data-testid="stHorizontalBlock"] {{
            flex-direction: column !important;
        }}
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
            width: 100% !important;
            min-width: 100% !important;
        }}
    }}

    /* Mobile (< 640px) */
    @media (max-width: 639px) {{
        [data-testid="stHorizontalBlock"] {{
            flex-direction: column !important;
        }}
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
            width: 100% !important;
            min-width: 100% !important;
        }}
        .block-container {{
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-bottom: 90px !important; /* ensure nothing hidden behind bottom bar */
        }}
        .cp-mobile-controls {{
            display: block !important;
        }}
        .cp-hero-container {{
            grid-template-columns: 1fr !important;
            gap: 14px;
        }}
        .cp-hero-savings {{
            padding: 20px !important;
        }}
        .cp-hero-number {{
            font-size: 3.2rem !important;
        }}
        .cp-kpi-grid {{
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 10px !important;
        }}
        .cp-kpi-card {{
            padding: 12px 14px !important;
        }}
        .cp-kpi-val {{
            font-size: 1.35rem !important;
        }}
        /* Fixed bottom navigation on mobile */
        [data-testid="stTabs"] [data-baseweb="tab-list"], [data-testid="stTabs"] [role="tablist"], .stTabs [data-baseweb="tab-list"] {{
            position: fixed !important;
            bottom: calc(12px + env(safe-area-inset-bottom, 0px)) !important;
            left: 12px !important;
            right: 12px !important;
            z-index: 999999 !important;
            margin: 0 auto !important;
            width: auto !important;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3) !important;
        }}
        [data-testid="stTabs"] [data-baseweb="tab"], [data-testid="stTabs"] [role="tab"], .stTabs [data-baseweb="tab"] {{
            padding: 6px 12px !important;
            font-size: 0.78rem !important;
        }}
    }}

    /* Reduced Motion Accessibility */
    @media (prefers-reduced-motion: reduce) {{
        * {{
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }}
    }}
    </style>
    """
