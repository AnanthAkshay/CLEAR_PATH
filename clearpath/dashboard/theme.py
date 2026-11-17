"""ClearPath Dashboard Design System and Theme Tokens.

Strict editorial design system:
- Sharp hairline borders (1px)
- Zero drop shadows, zero gradients, zero glassmorphism
- Archivo (headings), Public Sans (body), IBM Plex Mono (numerals/code)
- Light/Dark mode tokens with WCAG AA compliance
- Responsive breakpoints and print stylesheet
"""

from __future__ import annotations
from typing import Dict, Any

TOKENS: Dict[str, Dict[str, str]] = {
    "light": {
        "bg": "#F1EEE6",
        "surface": "#F8F6F0",
        "surface_card": "#FFFFFF",
        "ink": "#141815",
        "muted": "#4F5953",
        "rule": "#D6D1C3",
        "accent": "#C8401B",
        "accent_hover": "#A53314",
        "accent_subtle": "#FBEAE5",
        # Signal data colours paired with text labels G / Y / R
        "signal_green": "#2F9E55",
        "signal_yellow": "#C99A1B",
        "signal_red": "#D6453A",
        # Road Network
        "road_color": "#D6D1C3",
        "road_bg": "rgba(248, 246, 240, 0.9)",
        "corridor_active": "#C8401B",
    },
    "dark": {
        "bg": "#0F1311",
        "surface": "#161B18",
        "surface_card": "#1C231F",
        "ink": "#E9E6DD",
        "muted": "#8FA497",
        "rule": "#28312C",
        "accent": "#FF6B3D",
        "accent_hover": "#FF855E",
        "accent_subtle": "#2B1B15",
        # Signal data colours paired with text labels G / Y / R
        "signal_green": "#2F9E55",
        "signal_yellow": "#C99A1B",
        "signal_red": "#D6453A",
        # Road Network
        "road_color": "#28312C",
        "road_bg": "rgba(22, 27, 24, 0.9)",
        "corridor_active": "#FF6B3D",
    },
}


def get_theme_css(dark_mode: bool = False) -> str:
    """Generate complete, self-contained CSS adhering strictly to editorial design guidelines."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500;600;700&family=Public+Sans:wght@400;500;600;700&display=swap');

    :root {{
        --cp-bg: {t['bg']};
        --cp-surface: {t['surface']};
        --cp-surface-card: {t['surface_card']};
        --cp-ink: {t['ink']};
        --cp-muted: {t['muted']};
        --cp-rule: {t['rule']};
        --cp-accent: {t['accent']};
        --cp-accent-hover: {t['accent_hover']};
        --cp-accent-subtle: {t['accent_subtle']};
        --cp-signal-green: {t['signal_green']};
        --cp-signal-yellow: {t['signal_yellow']};
        --cp-signal-red: {t['signal_red']};
        --cp-corridor: {t['corridor_active']};
        --cp-radius: 4px;
        --cp-font-heading: 'Archivo', -apple-system, BlinkMacSystemFont, sans-serif;
        --cp-font-body: 'Public Sans', system-ui, -apple-system, sans-serif;
        --cp-font-mono: 'IBM Plex Mono', 'SFMono-Regular', Consolas, monospace;
    }}

    /* Base Reset and Zero Shadows / Gradients */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{
        background-color: var(--cp-bg) !important;
        background-image: none !important;
        color: var(--cp-ink) !important;
        font-family: var(--cp-font-body) !important;
        box-sizing: border-box !important;
        box-shadow: none !important;
        overflow-x: hidden !important;
    }}

    *, *:before, *:after {{
        box-sizing: border-box !important;
        box-shadow: none !important;
        text-shadow: none !important;
    }}

    /* Typography */
    h1, h2, h3, h4, h5, h6 {{
        font-family: var(--cp-font-heading) !important;
        color: var(--cp-ink) !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        line-height: 1.2 !important;
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }}

    p, span, li, label, div {{
        font-family: var(--cp-font-body);
        color: var(--cp-ink);
    }}

    code, pre, .cp-mono {{
        font-family: var(--cp-font-mono) !important;
    }}

    /* Clean Streamlit Header & Footer removal */
    [data-testid="stHeader"], footer, #MainMenu {{
        visibility: hidden !important;
        display: none !important;
    }}

    /* Container constraints */
    .block-container {{
        max-width: 1360px !important;
        padding-top: 1.5rem !important;
        padding-bottom: 5rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
    }}

    /* Editorial Hairline Bordered Cards */
    .cp-card {{
        background: var(--cp-surface);
        border: 1px solid var(--cp-rule);
        border-radius: var(--cp-radius);
        padding: 20px 24px;
        margin-bottom: 20px;
        box-sizing: border-box;
    }}

    /* Streamlit Border Wrapper Overrides */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: var(--cp-surface) !important;
        border: 1px solid var(--cp-rule) !important;
        border-radius: var(--cp-radius) !important;
        box-shadow: none !important;
        padding: 20px 24px !important;
        margin-bottom: 20px !important;
    }}

    /* Sidebar Styling */
    [data-testid="stSidebar"] {{
        background-color: var(--cp-surface) !important;
        border-right: 1px solid var(--cp-rule) !important;
    }}
    [data-testid="stSidebarNav"] {{
        border-bottom: 1px solid var(--cp-rule) !important;
        padding-bottom: 12px !important;
        margin-bottom: 16px !important;
    }}
    [data-testid="stSidebarNav"] span {{
        font-family: var(--cp-font-heading) !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }}

    /* Sticky Top Header */
    .cp-sticky-header {{
        position: sticky;
        top: 0;
        z-index: 9999;
        background: var(--cp-bg);
        border-bottom: 1px solid var(--cp-rule);
        padding: 10px 0;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
    }}

    .cp-brand-wrap {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    .cp-brand-name {{
        font-family: var(--cp-font-heading);
        font-weight: 800;
        font-size: 1.3rem;
        letter-spacing: -0.03em;
        color: var(--cp-ink);
        text-decoration: none;
    }}
    .cp-brand-badge {{
        font-family: var(--cp-font-mono);
        font-size: 0.72rem;
        border: 1px solid var(--cp-rule);
        padding: 2px 8px;
        border-radius: var(--cp-radius);
        color: var(--cp-muted);
        text-transform: uppercase;
    }}

    /* Skip Link Accessibility */
    .cp-skip-link {{
        position: absolute;
        top: -100px;
        left: 12px;
        background: var(--cp-accent);
        color: #FFFFFF !important;
        padding: 8px 14px;
        z-index: 100000;
        font-weight: 700;
        text-decoration: none;
        border-radius: var(--cp-radius);
    }}
    .cp-skip-link:focus {{
        top: 12px;
    }}

    /* Scroll progress bar */
    .cp-scroll-progress {{
        position: fixed;
        top: 0;
        left: 0;
        height: 3px;
        background: var(--cp-accent);
        z-index: 100001;
        width: 100%;
        transform-origin: 0 50%;
    }}
    @supports (animation-timeline: scroll()) {{
        .cp-scroll-progress {{
            animation: cp-scroll-grow auto linear;
            animation-timeline: scroll();
        }}
        @keyframes cp-scroll-grow {{
            from {{ transform: scaleX(0); }}
            to {{ transform: scaleX(1); }}
        }}
    }}

    /* Big Numeral Metric Display */
    .cp-metric-box {{
        background: var(--cp-surface);
        border: 1px solid var(--cp-rule);
        border-radius: var(--cp-radius);
        padding: 16px 20px;
        margin-bottom: 12px;
        box-sizing: border-box;
    }}
    .cp-metric-label {{
        font-family: var(--cp-font-heading);
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--cp-muted);
        margin-bottom: 6px;
    }}
    .cp-metric-value {{
        font-family: var(--cp-font-mono);
        font-size: clamp(1.8rem, 3.5vw, 2.6rem);
        font-weight: 700;
        color: var(--cp-ink);
        line-height: 1.1;
    }}
    .cp-metric-sub {{
        font-size: 0.78rem;
        color: var(--cp-muted);
        margin-top: 6px;
    }}

    /* Editorial Agent Rows */
    .cp-agent-row {{
        display: grid;
        grid-template-columns: 48px 1fr auto;
        gap: 16px;
        align-items: center;
        padding: 14px 18px;
        border-bottom: 1px solid var(--cp-rule);
    }}
    .cp-agent-num {{
        font-family: var(--cp-font-mono);
        font-weight: 700;
        font-size: 1.1rem;
        color: var(--cp-accent);
    }}
    .cp-agent-name {{
        font-family: var(--cp-font-heading);
        font-weight: 700;
        font-size: 0.95rem;
    }}
    .cp-agent-desc {{
        font-size: 0.82rem;
        color: var(--cp-muted);
        margin-top: 2px;
    }}

    /* Vertical Timeline */
    .cp-timeline {{
        position: relative;
        padding-left: 28px;
        margin: 20px 0;
        border-left: 2px solid var(--cp-rule);
    }}
    .cp-timeline-step {{
        position: relative;
        margin-bottom: 24px;
    }}
    .cp-timeline-step:last-child {{
        margin-bottom: 0;
    }}
    .cp-timeline-marker {{
        position: absolute;
        left: -35px;
        top: 2px;
        width: 12px;
        height: 12px;
        background: var(--cp-bg);
        border: 2px solid var(--cp-accent);
        border-radius: 50%;
    }}
    .cp-timeline-title {{
        font-family: var(--cp-font-heading);
        font-weight: 700;
        font-size: 0.95rem;
        color: var(--cp-ink);
    }}
    .cp-timeline-body {{
        font-size: 0.82rem;
        color: var(--cp-muted);
        margin-top: 4px;
        line-height: 1.45;
    }}

    /* Cookie & Preferences Banner */
    .cp-cookie-banner {{
        background: var(--cp-surface);
        border: 1px solid var(--cp-rule);
        border-radius: var(--cp-radius);
        padding: 14px 20px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        flex-wrap: wrap;
    }}
    .cp-cookie-text {{
        font-size: 0.82rem;
        color: var(--cp-muted);
        flex: 1;
        min-width: 260px;
    }}

    /* Buttons: strict hover and focus-visible, NO scaling, NO transform */
    button, [role="button"], .stButton > button {{
        min-height: 44px !important;
        border-radius: var(--cp-radius) !important;
        font-family: var(--cp-font-heading) !important;
        font-weight: 600 !important;
        border: 1px solid var(--cp-rule) !important;
        background: var(--cp-surface) !important;
        color: var(--cp-ink) !important;
        transition: color 0.15s ease, border-color 0.15s ease !important;
        transform: none !important;
    }}
    button:hover, [role="button"]:hover, .stButton > button:hover {{
        border-color: var(--cp-accent) !important;
        color: var(--cp-accent) !important;
        text-decoration: underline !important;
        transform: none !important;
    }}
    button:focus-visible, [role="button"]:focus-visible, .stButton > button:focus-visible {{
        outline: 2px solid var(--cp-accent) !important;
        outline-offset: 2px !important;
        transform: none !important;
    }}

    /* Primary Button */
    .stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
        background: var(--cp-accent) !important;
        color: #FFFFFF !important;
        border-color: var(--cp-accent) !important;
    }}
    .stButton > button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {{
        background: var(--cp-accent-hover) !important;
        color: #FFFFFF !important;
        text-decoration: underline !important;
    }}

    /* Interactive Links */
    a {{
        color: var(--cp-accent) !important;
        text-decoration: none !important;
        transition: color 0.15s ease, text-decoration 0.15s ease !important;
    }}
    a:hover {{
        text-decoration: underline !important;
        color: var(--cp-accent-hover) !important;
    }}
    a:focus-visible {{
        outline: 2px solid var(--cp-accent) !important;
        outline-offset: 2px !important;
    }}

    /* Tab navigation override */
    [data-testid="stTabs"] [data-baseweb="tab-list"], [data-testid="stTabs"] [role="tablist"] {{
        background: transparent !important;
        border-bottom: 1px solid var(--cp-rule) !important;
        gap: 4px !important;
    }}
    [data-testid="stTabs"] [data-baseweb="tab"], [data-testid="stTabs"] [role="tab"] {{
        font-family: var(--cp-font-heading) !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        color: var(--cp-muted) !important;
        background: transparent !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        border-radius: 0 !important;
        padding: 8px 16px !important;
        transition: color 0.15s ease, border-color 0.15s ease !important;
    }}
    [data-testid="stTabs"] [aria-selected="true"] {{
        color: var(--cp-ink) !important;
        border-bottom: 2px solid var(--cp-accent) !important;
        font-weight: 700 !important;
    }}

    /* Data Tables Hairline Styling */
    table, .cp-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
        margin: 12px 0;
    }}
    table th, .cp-table th {{
        text-align: left;
        padding: 8px 12px;
        border-bottom: 1px solid var(--cp-rule);
        font-family: var(--cp-font-heading);
        font-weight: 700;
        color: var(--cp-muted);
        text-transform: uppercase;
        font-size: 0.72rem;
    }}
    table td, .cp-table td {{
        padding: 8px 12px;
        border-bottom: 1px solid var(--cp-rule);
        color: var(--cp-ink);
    }}

    /* Skeleton Loading Placeholder */
    .cp-skeleton {{
        background: var(--cp-surface);
        border: 1px solid var(--cp-rule);
        border-radius: var(--cp-radius);
        animation: cp-pulse 1.8s infinite ease-in-out;
    }}
    @keyframes cp-pulse {{
        0% {{ opacity: 0.6; }}
        50% {{ opacity: 1.0; }}
        100% {{ opacity: 0.6; }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        *, .cp-skeleton, button, a {{
            animation: none !important;
            transition: none !important;
        }}
    }}

    /* Floating Contact Button */
    .cp-floating-contact {{
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9998;
        background: var(--cp-surface);
        border: 1px solid var(--cp-rule);
        border-radius: var(--cp-radius);
        padding: 10px 16px;
        font-family: var(--cp-font-heading);
        font-size: 0.82rem;
        font-weight: 700;
        color: var(--cp-ink) !important;
        text-decoration: none !important;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }}
    .cp-floating-contact:hover {{
        border-color: var(--cp-accent);
        color: var(--cp-accent) !important;
        text-decoration: underline !important;
    }}

    /* Footer */
    .cp-footer {{
        border-top: 1px solid var(--cp-rule);
        padding-top: 24px;
        margin-top: 48px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
        font-size: 0.78rem;
        color: var(--cp-muted);
    }}

    /* Print Stylesheet */
    @media print {{
        [data-testid="stSidebar"],
        .cp-sticky-header,
        .cp-cookie-banner,
        .cp-floating-contact,
        .stButton,
        [data-testid="stTabs"] [role="tablist"] {{
            display: none !important;
        }}
        html, body, [data-testid="stAppViewContainer"] {{
            background: #FFFFFF !important;
            color: #000000 !important;
        }}
        .block-container {{
            max-width: 100% !important;
            padding: 0 !important;
        }}
        .cp-card, [data-testid="stVerticalBlockBorderWrapper"] {{
            border: 1px solid #CCCCCC !important;
            break-inside: avoid;
        }}
    }}

    /* Responsive Grid Controls */
    @media (max-width: 639px) {{
        .block-container {{
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-bottom: 80px !important;
        }}
        [data-testid="stHorizontalBlock"] {{
            flex-direction: column !important;
        }}
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
            width: 100% !important;
            min-width: 100% !important;
        }}
    }}
    </style>
    """
