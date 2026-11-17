# Streamlit Community Cloud Deployment Guide

Deployment manual and operational runbook for launching the ClearPath-lite multi-page traffic preemption dashboard on Streamlit Community Cloud or any standard containerized hosting platform.

## Table of Contents

- [Overview](#overview)
- [Architecture & Runtime Requirements](#architecture--runtime-requirements)
- [Prerequisites](#prerequisites)
- [Step-by-Step Deployment on Streamlit Cloud](#step-by-step-deployment-on-streamlit-cloud)
  - [Step 1: Repository Preparation](#step-1-repository-preparation)
  - [Step 2: Connect Streamlit Community Cloud](#step-2-connect-streamlit-community-cloud)
  - [Step 3: Configure App Settings](#step-3-configure-app-settings)
  - [Step 4: Configure Secrets (`secrets.toml`)](#step-4-configure-secrets-secretstoml)
  - [Step 5: Deploy & Monitor Logs](#step-5-deploy--monitor-logs)
- [Configuration Reference](#configuration-reference)
  - [`.streamlit/config.toml`](#streamlitconfigtoml)
  - [`requirements.txt`](#requirementstxt)
- [Post-Deployment Verification Checklist](#post-deployment-verification-checklist)
- [Local Running and Container Testing](#local-running-and-container-testing)
- [Resource Consumption & Performance Limits](#resource-consumption--performance-limits)
- [Troubleshooting](#troubleshooting)

---

## Overview

ClearPath-lite is architected as a self-contained, single-deployment Streamlit multi-page application. It requires no external database, node runtime, third-party trackers, or cloud storage buckets. The application serves interactive simulation visualizations, benchmark reports, security audit matrices, documentation manuals, and simulated dispatch controls from a single Python entry point (`streamlit_app.py`).

Streamlit Community Cloud provides free hosting for public GitHub repositories with 1 GB resource limits, making it the primary target deployment environment.

---

## Architecture & Runtime Requirements

- **Python Version**: Python 3.10, 3.11, 3.12, 3.13, or 3.14.
- **Entry Point**: `streamlit_app.py` in the workspace root.
- **Framework**: Streamlit `>= 1.30.0` (utilizes modern native routing via `st.navigation` and `st.Page`, and non-blocking sub-second rendering via `st.fragment`).
- **Dependencies**: Pure Python (`numpy`, `pydantic`, `fastapi`, `uvicorn`, `httpx`, `pytest`, `plotly`, `streamlit`).
- **Storage**: In-memory ephemeral session state (`st.session_state`) for simulator state, cookies preferences, theme selection, and inquiry reference log.
- **Static Assets**: Enabled via `.streamlit/config.toml` (`enableStaticServing = true`) mapped to `static/`.

---

## Prerequisites

Before launching the deployment:

1. A GitHub account with read/write access to the ClearPath repository.
2. Verified local test suite: ensure `python -m pytest` passes all 119 tests.
3. Clean git tree on the target branch (typically `main`).
4. An active [Streamlit Community Cloud](https://share.streamlit.io/) account connected to your GitHub profile.

---

## Step-by-Step Deployment on Streamlit Cloud

### Step 1: Repository Preparation

Confirm that the root directory contains the following configuration files:

```text
CLEARPATH/
├── .streamlit/
│   └── config.toml          # Server, theme, and static serving settings
├── static/                  # Static file directory for fonts and assets
├── clearpath/               # Core simulation and dashboard modules
│   └── dashboard/
│       ├── charts.py        # Accessible Plotly figure builders
│       ├── components.py    # Editorial HTML/Streamlit reusable widgets
│       ├── theme.py         # Design tokens, CSS injection, typography
│       └── pages/           # 10 dedicated subpages
├── results/
│   └── summary.json         # Real benchmark data for display
├── requirements.txt         # Pinned Python package dependencies
└── streamlit_app.py         # Multi-page router and shell layout
```

Push all commits to GitHub:

```powershell
git push origin main
```

### Step 2: Connect Streamlit Community Cloud

1. Navigate to [share.streamlit.io](https://share.streamlit.io/) in your browser.
2. Sign in using your GitHub account.
3. Click the **"New app"** button located in the upper-right corner of the workspace.

### Step 3: Configure App Settings

In the Streamlit app setup modal, provide the following parameters:

- **Repository**: `<your-github-username>/clearpath` (select from repository dropdown)
- **Branch**: `main`
- **Main file path**: `streamlit_app.py`
- **App URL** (Optional): Choose a custom subdomain (e.g., `clearpath-emergency.streamlit.app`).

### Step 4: Configure Secrets (`secrets.toml`)

ClearPath utilizes HMAC-SHA256 signature verification for emergency vehicle preemption requests. To protect the cryptographic signing key in production without hardcoding secrets:

1. Click **"Advanced settings..."** before deploying, or go to **App Settings > Secrets** in an existing app.
2. Paste the following configuration into the secrets editor:

```toml
# Streamlit Secrets for ClearPath Production Deployment
CLEARPATH_SECRET = "production-cryptographic-signing-key-clearpath-2026"
```

> [!NOTE]
> If `CLEARPATH_SECRET` is not set in secrets, the application automatically falls back to the environment variable `os.getenv("CLEARPATH_SECRET")`, or defaults to the internal test fixture key `test-secret-key-12345`. Explicitly defining this secret ensures secure token verification.

### Step 5: Deploy & Monitor Logs

1. Click **"Deploy!"**.
2. Streamlit Cloud will spin up a Debian container, install system libraries, execute `pip install -r requirements.txt`, and start the app process.
3. Expand the **"Manage app"** bottom drawer to observe live deployment logs.
4. Once completed, your browser will automatically redirect to the live multi-page dashboard.

---

## Configuration Reference

### `.streamlit/config.toml`

The production `.streamlit/config.toml` file enforces deterministic editorial styling, disables telemetry, and enables static asset caching:

```toml
[browser]
gatherUsageStats = false

[server]
headless = true
enableStaticServing = true
port = 8501

[theme]
primaryColor = "#C8401B"
backgroundColor = "#F1EEE6"
secondaryBackgroundColor = "#F8F6F0"
textColor = "#141815"
font = "sans serif"
```

### `requirements.txt`

The dependencies required for cloud deployment are:

```text
numpy>=1.24.0
pydantic>=2.0.0
fastapi>=0.100.0
uvicorn>=0.22.0
httpx>=0.24.0
pytest>=7.0.0
plotly>=5.0.0
streamlit>=1.30.0
```

---

## Post-Deployment Verification Checklist

Verify each of the following points after the deployment finishes:

| Verification Item | Action | Expected Result | Pass/Fail |
| :--- | :--- | :--- | :--- |
| **Public Routing** | Navigate to `https://<your-app>.streamlit.app/` | `Home` page loads with hero numeral, value statement, and timeline | [ ] |
| **Multi-Page Nav** | Click `Console`, `Security`, `Results`, `Docs`, `FAQ` | Clean subpage rendering without full-page white flash | [ ] |
| **Dark Mode** | Click the theme toggle icon in the top header | All tokens invert: bg `#0F1311`, surface `#161B18`, text `#E9E6DD` | [ ] |
| **Mobile Layout** | Inspect viewport at 390px (iPhone 14) | No horizontal scrolling (`scrollWidth == innerWidth`), stacked controls | [ ] |
| **Cookie Banner** | Click "Accept" on preferences banner | Banner clears; `st.session_state.cookie_consent` sets to `accepted` | [ ] |
| **Operator Sign-in**| Click "Operator Sign-in" button | Modal dialog opens with password field and eye visibility toggle | [ ] |
| **Simulation Loop** | On `/console`, click "Step" or "Play" | Grid animates at ~0.35s intervals inside fragment; controls stay responsive | [ ] |
| **Emergency Trigger**| Click "Dispatch Emergency" | Confirmation modal prompts; corridor turns gold with signal green corridor | [ ] |
| **Attack Prevention**| Trigger "Spoofed Replay Attack" | Security gateway rejects request with `FORGED_SIGNATURE` code | [ ] |
| **Contact Form** | Submit on `/contact` with valid inputs | Form renders green success box with generated `REF-2026-XXXX` ID | [ ] |
| **UTM Consent** | Navigate with `?utm_source=test` | Query params captured only if cookie banner accepted | [ ] |
| **Print Stylesheet**| Press `Ctrl + P` on `/results` | Navigation sidebar, header, and floating buttons are hidden in print preview | [ ] |

---

## Local Running and Container Testing

To replicate the production environment locally:

```powershell
# 1. Create and activate Python virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set test secret
$env:CLEARPATH_SECRET = "production-cryptographic-signing-key-clearpath-2026"

# 4. Launch Streamlit
streamlit run streamlit_app.py --server.headless=true --server.port=8501
```

Access the local server at `http://localhost:8501`.

---

## Resource Consumption & Performance Limits

Measurements taken under simulated load on a 1 CPU / 1 GB standard container:

- **Cold Start Time**: ~6.8 seconds (install + import + network graph build).
- **Idle Memory Footprint**: ~165 MB RSS.
- **Active Simulation Footprint**: ~210 MB RSS (well below the 1,024 MB Streamlit Cloud limit).
- **Fragment Tick Frequency**: 0.35 seconds per frame when unpaused.
- **Network Bandwidth**: ~25 KB per simulation tick (diff-only Plotly figures).

---

## Troubleshooting

### Issue 1: `ModuleNotFoundError: No module named 'clearpath'`

- **Cause**: Streamlit working directory not recognizing the root package.
- **Resolution**: `streamlit_app.py` includes programmatic path resolution at line 12:
  ```python
  repo_root = Path(__file__).resolve().parent
  if str(repo_root) not in sys.path:
      sys.path.insert(0, str(repo_root))
  ```
  Ensure deployment specifies `streamlit_app.py` as the main entry path rather than `clearpath/dashboard/pages/console.py`.

### Issue 2: Static Folder Warning

- **Cause**: `.streamlit/config.toml` specifies `enableStaticServing = true` but the folder does not exist.
- **Resolution**: Ensure the empty `static/` folder is committed to git. (Added via `.gitkeep`).

### Issue 3: Streamlit Community Cloud Session Eviction

- **Cause**: Inactivity timeout (apps sleep after 7 days of inactivity on the free tier).
- **Resolution**: Clicking "Wake up" revives the container in under 15 seconds. In-memory simulations reset cleanly to step 0.

