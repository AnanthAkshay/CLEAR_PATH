"""ClearPath Command Center Design System and Modern Theme Engine.

Implements a high-precision, production-grade cyber-physical operations theme:
- Deep obsidian and titanium command center palette (Dark) & crisp slate snow (Light)
- Plus Jakarta Sans / Inter typographic hierarchy with JetBrains Mono telemetry
- High-visibility safety indicators (Signal Emerald, Emergency Coral, Amber Warning)
- Clean card architecture with subtle borders, glowing active states, and zero clutter
- Accessible WCAG AA compliant contrast ratios (>= 4.5:1 text, >= 3:1 graphical)
- Hardware-accelerated transitions and responsive mobile/tablet breakpoints
"""

from __future__ import annotations
from typing import Dict, Any

TOKENS: Dict[str, Dict[str, str]] = {
    "dark": {
        "bg": "#080C14",
        "surface": "#0E1524",
        "surface_card": "#131C30",
        "surface_hover": "#1A2640",
        "surface_elevated": "#1E2C4A",
        "ink": "#F8FAFC",
        "ink_secondary": "#94A3B8",
        "muted": "#64748B",
        "rule": "rgba(255, 255, 255, 0.08)",
        "rule_subtle": "rgba(255, 255, 255, 0.04)",
        "rule_active": "rgba(56, 189, 248, 0.4)",
        "accent": "#0284C7",
        "accent_hover": "#38BDF8",
        "accent_subtle": "rgba(56, 189, 248, 0.12)",
        "accent_glow": "rgba(56, 189, 248, 0.25)",
        "emergency": "#EF4444",
        "emergency_glow": "rgba(239, 68, 68, 0.25)",
        "emergency_subtle": "rgba(239, 68, 68, 0.12)",
        "signal_green": "#10B981",
        "signal_green_glow": "rgba(16, 185, 129, 0.25)",
        "signal_yellow": "#F59E0B",
        "signal_yellow_glow": "rgba(245, 158, 11, 0.25)",
        "signal_red": "#EF4444",
        "road_color": "#1E293B",
        "road_arterial": "#334155",
        "road_bg": "#080C14",
        "corridor_active": "#10B981",
        "hospital_blue": "#38BDF8",
    },
    "light": {
        "bg": "#F8FAFC",
        "surface": "#FFFFFF",
        "surface_card": "#FFFFFF",
        "surface_hover": "#F1F5F9",
        "surface_elevated": "#E2E8F0",
        "ink": "#0F172A",
        "ink_secondary": "#475569",
        "muted": "#64748B",
        "rule": "#E2E8F0",
        "rule_subtle": "#F1F5F9",
        "rule_active": "rgba(2, 132, 199, 0.4)",
        "accent": "#0284C7",
        "accent_hover": "#0369A1",
        "accent_subtle": "rgba(2, 132, 199, 0.08)",
        "accent_glow": "rgba(2, 132, 199, 0.15)",
        "emergency": "#DC2626",
        "emergency_glow": "rgba(220, 38, 38, 0.2)",
        "emergency_subtle": "rgba(220, 38, 38, 0.08)",
        "signal_green": "#059669",
        "signal_green_glow": "rgba(5, 150, 105, 0.2)",
        "signal_yellow": "#D97706",
        "signal_yellow_glow": "rgba(217, 119, 6, 0.2)",
        "signal_red": "#DC2626",
        "road_color": "#CBD5E1",
        "road_arterial": "#94A3B8",
        "road_bg": "#F1F5F9",
        "corridor_active": "#059669",
        "hospital_blue": "#0284C7",
    },
}


def get_theme_css(dark_mode: bool = True) -> str:
    """Generate high-performance CSS for the ClearPath modern command center UI."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

    :root {{
        --cp-bg: {t['bg']};
        --cp-surface: {t['surface']};
        --cp-surface-card: {t['surface_card']};
        --cp-surface-hover: {t['surface_hover']};
        --cp-surface-elevated: {t['surface_elevated']};
        --cp-ink: {t['ink']};
        --cp-ink-secondary: {t['ink_secondary']};
        --cp-muted: {t['muted']};
        --cp-rule: {t['rule']};
        --cp-rule-subtle: {t['rule_subtle']};
        --cp-rule-active: {t['rule_active']};
        --cp-accent: {t['accent']};
        --cp-accent-hover: {t['accent_hover']};
        --cp-accent-subtle: {t['accent_subtle']};
        --cp-accent-glow: {t['accent_glow']};
        --cp-emergency: {t['emergency']};
        --cp-emergency-glow: {t['emergency_glow']};
        --cp-emergency-subtle: {t['emergency_subtle']};
        --cp-signal-green: {t['signal_green']};
        --cp-signal-green-glow: {t['signal_green_glow']};
        --cp-signal-yellow: {t['signal_yellow']};
        --cp-signal-yellow-glow: {t['signal_yellow_glow']};
        --cp-signal-red: {t['signal_red']};
        --cp-corridor: {t['corridor_active']};
        --cp-hospital: {t['hospital_blue']};
        --cp-radius: 8px;
        --cp-radius-lg: 12px;
        --cp-radius-sm: 6px;
        --cp-font-heading: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
        --cp-font-body: 'Inter', system-ui, -apple-system, sans-serif;
        --cp-font-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
        --cp-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.35);
        --cp-shadow-sm: 0 2px 8px -1px rgba(0, 0, 0, 0.2);
    }}

    /* Base Reset & Core Canvas */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{
        background-color: var(--cp-bg) !important;
        background-image: radial-gradient(circle at 50% 0%, rgba(56, 189, 248, 0.03) 0%, transparent 60%) !important;
        color: var(--cp-ink) !important;
        font-family: var(--cp-font-body) !important;
        box-sizing: border-box !important;
        overflow-x: hidden !important;
        letter-spacing: -0.01em;
    }}

    /* Typography Hierarchy */
    h1, h2, h3, h4, h5, h6 {{
        font-family: var(--cp-font-heading) !important;
        color: var(--cp-ink) !important;
        font-weight: 700 !important;
        letter-spacing: -0.025em !important;
        line-height: 1.25 !important;
        margin-top: 0.6rem !important;
        margin-bottom: 0.4rem !important;
    }}

    h1 {{ font-size: clamp(1.8rem, 3.2vw, 2.5rem) !important; font-weight: 800 !important; }}
    h2 {{ font-size: clamp(1.4rem, 2.4vw, 1.85rem) !important; }}
    h3 {{ font-size: clamp(1.15rem, 1.8vw, 1.4rem) !important; }}

    p, span, li, label, div {{
        font-family: var(--cp-font-body);
        color: var(--cp-ink);
        line-height: 1.5;
    }}

    code, pre, .cp-mono {{
        font-family: var(--cp-font-mono) !important;
    }}

    /* Hide Default Chrome */
    [data-testid="stHeader"], footer, #MainMenu {{
        visibility: hidden !important;
        display: none !important;
    }}

    /* Main Container Constraints */
    .block-container {{
        max-width: 1440px !important;
        padding-top: 1rem !important;
        padding-bottom: 4rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
    }}

    /* Sleek Elevated Cards */
    .cp-card {{
        background: var(--cp-surface);
        border: 1px solid var(--cp-rule);
        border-radius: var(--cp-radius);
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: var(--cp-shadow-sm);
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    .cp-card:hover {{
        border-color: var(--cp-rule-active);
    }}

    /* Streamlit Bordered Container Overrides */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: var(--cp-surface) !important;
        border: 1px solid var(--cp-rule) !important;
        border-radius: var(--cp-radius) !important;
        box-shadow: var(--cp-shadow-sm) !important;
        padding: 18px 22px !important;
        margin-bottom: 16px !important;
        transition: border-color 0.2s ease;
    }}
    [data-testid="stVerticalBlockBorderWrapper"]:hover {{
        border-color: var(--cp-rule-active) !important;
    }}

    /* Modern Sidebar Navigation */
    [data-testid="stSidebar"], [data-testid="stSidebarContent"], [data-testid="stSidebarUserContent"] {{
        background-color: var(--cp-surface) !important;
        color: var(--cp-ink) !important;
        border-right: 1px solid var(--cp-rule) !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span {{
        color: var(--cp-ink) !important;
    }}
    [data-testid="stSidebarNav"] {{
        border-bottom: 1px solid var(--cp-rule) !important;
        padding-bottom: 14px !important;
        margin-bottom: 16px !important;
    }}
    [data-testid="stSidebarNav"] span {{
        font-family: var(--cp-font-heading) !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        color: var(--cp-ink-secondary) !important;
    }}
    [data-testid="stSidebarNav"] [aria-current="page"] span {{
        color: var(--cp-accent-hover) !important;
        font-weight: 700 !important;
    }}

    /* Precision Sticky Command Header */
    .cp-sticky-header {{
        position: sticky;
        top: 0;
        z-index: 9999;
        background: var(--cp-bg);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-bottom: 1px solid var(--cp-rule);
        padding: 12px 0;
        margin-bottom: 20px;
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
    .cp-brand-icon {{
        width: 32px;
        height: 32px;
        border-radius: var(--cp-radius-sm);
        background: linear-gradient(135deg, #0284C7, #0369A1);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #FFFFFF;
        font-family: var(--cp-font-heading);
        font-weight: 800;
        font-size: 0.9rem;
        box-shadow: 0 0 12px var(--cp-accent-glow);
    }}
    .cp-brand-name {{
        font-family: var(--cp-font-heading);
        font-weight: 800;
        font-size: 1.28rem;
        letter-spacing: -0.03em;
        color: var(--cp-ink);
        text-decoration: none;
    }}
    .cp-brand-badge {{
        font-family: var(--cp-font-mono);
        font-size: 0.72rem;
        font-weight: 600;
        border: 1px solid var(--cp-rule);
        padding: 3px 8px;
        border-radius: var(--cp-radius-sm);
        color: var(--cp-ink-secondary);
        background: var(--cp-surface-card);
    }}
    .cp-status-pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-family: var(--cp-font-mono);
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--cp-signal-green);
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.25);
        padding: 3px 10px;
        border-radius: 9999px;
    }}
    .cp-status-dot {{
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--cp-signal-green);
        box-shadow: 0 0 8px var(--cp-signal-green);
        animation: cp-pulse-dot 2s infinite ease-in-out;
    }}
    @keyframes cp-pulse-dot {{
        0%, 100% {{ opacity: 1; transform: scale(1); }}
        50% {{ opacity: 0.4; transform: scale(0.85); }}
    }}

    /* Skip Link Accessibility */
    .cp-skip-link {{
        position: absolute;
        top: -100px;
        left: 16px;
        background: var(--cp-accent);
        color: #FFFFFF !important;
        padding: 8px 16px;
        z-index: 100000;
        font-weight: 700;
        text-decoration: none;
        border-radius: var(--cp-radius);
    }}
    .cp-skip-link:focus {{
        top: 12px;
    }}

    /* Scroll Progress Bar */
    .cp-scroll-progress {{
        position: fixed;
        top: 0;
        left: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--cp-accent), var(--cp-signal-green));
        z-index: 100001;
        width: 100%;
        transform-origin: 0 50%;
    }}

    /* High-Impact Stat / KPI Cards */
    .cp-metric-box {{
        background: var(--cp-surface);
        border: 1px solid var(--cp-rule);
        border-radius: var(--cp-radius);
        padding: 16px 20px;
        margin-bottom: 12px;
        box-sizing: border-box;
        box-shadow: var(--cp-shadow-sm);
        transition: transform 0.15s ease, border-color 0.15s ease;
    }}
    .cp-metric-box:hover {{
        border-color: var(--cp-rule-active);
        transform: translateY(-2px);
    }}
    .cp-metric-label {{
        font-family: var(--cp-font-heading);
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--cp-muted);
        margin-bottom: 6px;
    }}
    .cp-metric-value {{
        font-family: var(--cp-font-mono);
        font-size: clamp(1.8rem, 3.2vw, 2.4rem);
        font-weight: 700;
        color: var(--cp-ink);
        line-height: 1.1;
    }}
    .cp-metric-sub {{
        font-size: 0.8rem;
        font-weight: 600;
        margin-top: 6px;
        display: flex;
        align-items: center;
        gap: 4px;
    }}

    /* Buttons: Tactile Modern Command Style */
    button, [role="button"], .stButton > button {{
        min-height: 42px !important;
        border-radius: var(--cp-radius-sm) !important;
        font-family: var(--cp-font-heading) !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        border: 1px solid var(--cp-rule) !important;
        background: var(--cp-surface-card) !important;
        color: var(--cp-ink) !important;
        transition: all 0.15s ease !important;
        box-shadow: var(--cp-shadow-sm) !important;
    }}
    button:hover, [role="button"]:hover, .stButton > button:hover {{
        border-color: var(--cp-accent-hover) !important;
        background: var(--cp-surface-hover) !important;
        color: var(--cp-accent-hover) !important;
    }}
    button:focus-visible, [role="button"]:focus-visible, .stButton > button:focus-visible {{
        outline: 2px solid var(--cp-accent-hover) !important;
        outline-offset: 2px !important;
    }}

    /* Primary Accent Button */
    .stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
        background: linear-gradient(135deg, #0284C7, #0369A1) !important;
        color: #FFFFFF !important;
        border-color: #0284C7 !important;
        box-shadow: 0 0 14px var(--cp-accent-glow) !important;
    }}
    .stButton > button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {{
        background: linear-gradient(135deg, #0369A1, #075985) !important;
        color: #FFFFFF !important;
        border-color: #38BDF8 !important;
    }}

    /* Form Controls & Text Inputs */
    [data-baseweb="input"], [data-baseweb="select"] {{
        background-color: var(--cp-surface-card) !important;
        border-radius: var(--cp-radius-sm) !important;
        border: 1px solid var(--cp-rule) !important;
        color: var(--cp-ink) !important;
    }}
    [data-baseweb="input"]:focus-within, [data-baseweb="select"]:focus-within {{
        border-color: var(--cp-accent-hover) !important;
        box-shadow: 0 0 0 2px var(--cp-accent-glow) !important;
    }}
    div[data-baseweb="select"] > div {{
        background-color: var(--cp-surface-card) !important;
        color: var(--cp-ink) !important;
        border-color: var(--cp-rule) !important;
    }}
    div[data-baseweb="select"] svg {{
        fill: var(--cp-ink-secondary) !important;
    }}
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul[role="listbox"] {{
        background-color: var(--cp-surface-card) !important;
        border: 1px solid var(--cp-rule-active) !important;
        border-radius: var(--cp-radius-sm) !important;
        box-shadow: var(--cp-shadow) !important;
    }}
    li[role="option"] {{
        background-color: var(--cp-surface-card) !important;
        color: var(--cp-ink) !important;
        font-family: var(--cp-font-body) !important;
        font-size: 0.88rem !important;
        transition: background 0.1s ease !important;
    }}
    li[role="option"]:hover, li[role="option"][aria-selected="true"] {{
        background-color: var(--cp-surface-hover) !important;
        color: var(--cp-accent-hover) !important;
    }}
    input, textarea {{
        background-color: transparent !important;
        color: var(--cp-ink) !important;
        font-family: var(--cp-font-body) !important;
    }}

    /* Streamlit Tabs - Sleek Capsule Style */
    [data-testid="stTabs"] [data-baseweb="tab-list"], [data-testid="stTabs"] [role="tablist"] {{
        background: var(--cp-surface) !important;
        border-radius: var(--cp-radius-sm) !important;
        padding: 4px !important;
        border: 1px solid var(--cp-rule) !important;
        gap: 4px !important;
        margin-bottom: 16px !important;
    }}
    [data-testid="stTabs"] [data-baseweb="tab"], [data-testid="stTabs"] [role="tab"] {{
        font-family: var(--cp-font-heading) !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        color: var(--cp-ink-secondary) !important;
        background: transparent !important;
        border: none !important;
        border-radius: 4px !important;
        padding: 8px 18px !important;
        transition: all 0.15s ease !important;
    }}
    [data-testid="stTabs"] [aria-selected="true"] {{
        color: #FFFFFF !important;
        background: var(--cp-surface-card) !important;
        border: 1px solid var(--cp-rule-active) !important;
        font-weight: 700 !important;
    }}

    /* Modern Table / Log Styling */
    table, .cp-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 0.84rem;
        margin: 12px 0;
        border-radius: var(--cp-radius);
        overflow: hidden;
        border: 1px solid var(--cp-rule);
    }}
    table th, .cp-table th {{
        text-align: left;
        padding: 10px 14px;
        background: var(--cp-surface);
        border-bottom: 1px solid var(--cp-rule);
        font-family: var(--cp-font-heading);
        font-weight: 700;
        color: var(--cp-muted);
        text-transform: uppercase;
        font-size: 0.72rem;
        letter-spacing: 0.05em;
    }}
    table td, .cp-table td {{
        padding: 10px 14px;
        border-bottom: 1px solid var(--cp-rule-subtle);
        color: var(--cp-ink);
        background: var(--cp-surface-card);
    }}
    table tr:last-child td, .cp-table tr:last-child td {{
        border-bottom: none;
    }}

    /* Floating Toast Cookie Banner */
    .cp-cookie-banner {{
        position: fixed;
        bottom: 24px;
        left: 24px;
        max-width: 440px;
        background: var(--cp-surface);
        border: 1px solid var(--cp-rule-active);
        border-radius: var(--cp-radius);
        padding: 16px 20px;
        z-index: 99999;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(12px);
    }}
    .cp-cookie-text {{
        font-size: 0.84rem;
        color: var(--cp-ink-secondary);
        margin-bottom: 12px;
        line-height: 1.45;
    }}

    /* Floating Action Trigger */
    .cp-floating-contact {{
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 9998;
        background: var(--cp-surface-card);
        border: 1px solid var(--cp-rule);
        border-radius: 9999px;
        padding: 10px 18px;
        font-family: var(--cp-font-heading);
        font-size: 0.85rem;
        font-weight: 700;
        color: var(--cp-ink) !important;
        text-decoration: none !important;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        box-shadow: var(--cp-shadow);
        transition: all 0.2s ease;
    }}
    .cp-floating-contact:hover {{
        border-color: var(--cp-accent-hover);
        color: var(--cp-accent-hover) !important;
        transform: translateY(-2px);
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
        font-size: 0.82rem;
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
            border: 1px solid #CBD5E1 !important;
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
        .cp-cookie-banner {{
            left: 12px;
            right: 12px;
            bottom: 12px;
            max-width: calc(100% - 24px);
        }}
    }}
    </style>
    """
