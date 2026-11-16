# ClearPath-lite Troubleshooting & Operational FAQ

This guide resolves common installation issues, runtime warnings, networking collisions, and script execution nuances across supported platforms.

## Table of Contents
- [1. Installation & Environment Issues](#1-installation--environment-issues)
  - [1.1 ModuleNotFoundError: No module named 'matplotlib'](#11-modulenotfounderror-no-module-named-matplotlib)
  - [1.2 Windows PowerShell Execution Policy Restrictions](#12-windows-powershell-execution-policy-restrictions)
  - [1.3 Python Version Compatibility](#13-python-version-compatibility)
- [2. Runtime Warnings & Diagnostics](#2-runtime-warnings--diagnostics)
  - [2.1 Insecure Development Default HMAC Secret Warning](#21-insecure-development-default-hmac-secret-warning)
  - [2.2 Streamlit Deprecation: use_container_width](#22-streamlit-deprecation-use_container_width)
  - [2.3 StarletteDeprecationWarning regarding httpx](#23-starlettedeprecationwarning-regarding-httpx)
- [3. Networking & Port Collisions](#3-networking--port-collisions)
  - [3.1 Port 8501 Already in Use (Streamlit)](#31-port-8501-already-in-use-streamlit)
  - [3.2 Port 8000 Already in Use (FastAPI)](#32-port-8000-already-in-use-fastapi)
- [4. Frequently Asked Questions (FAQ)](#4-frequently-asked-questions-faq)
- [5. Cross-Document References](#5-cross-document-references)

---

## 1. Installation & Environment Issues

### 1.1 `ModuleNotFoundError: No module named 'matplotlib'`
- **Symptom:** Running RL training (`make rl-train`) or scenario plotting fails with `ModuleNotFoundError: No module named 'matplotlib'`.
- **Cause:** Matplotlib is required for generating RL convergence curves and training diagnostic plots. Older environments may have installed dependencies prior to its inclusion in `requirements.txt`.
- **Resolution:**
  ```bash
  pip install "matplotlib>=3.7.0"
  # Or refresh full requirements:
  pip install -r requirements.txt
  ```

---

### 1.2 Windows PowerShell Execution Policy Restrictions
- **Symptom:** Activating the virtual environment in PowerShell (`.\venv\Scripts\Activate.ps1`) fails with:
  ```
  File ...\Activate.ps1 cannot be loaded because running scripts is disabled on this system.
  ```
- **Cause:** Windows PowerShell restricts unsigned script execution by default (`Restricted` policy).
- **Resolution:** Set the execution policy for the current process:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\venv\Scripts\Activate.ps1
  ```

---

### 1.3 Python Version Compatibility
- **Symptom:** Syntax errors or import errors during installation on Python 3.9 or earlier.
- **Cause:** ClearPath-lite uses modern Python features including union operator syntax (`X | Y`), `from __future__ import annotations`, and dataclass keyword arguments introduced in Python 3.10+.
- **Resolution:** Upgrade to Python 3.10, 3.11, 3.12, 3.13, or 3.14. Verify your active version:
  ```bash
  python --version
  ```

---

## 2. Runtime Warnings & Diagnostics

### 2.1 Insecure Development Default HMAC Secret Warning
- **Symptom:** Starting scenarios or the API prints:
  ```
  UserWarning: SECURITY WARNING: Using insecure development default HMAC secret! 
  Set CLEARPATH_SECRET environment variable in production.
  ```
- **Explanation:** This is an intentional security safeguard. If `CLEARPATH_SECRET` is unset, the system uses the default fallback key `clearpath-dev-secret-key-12345`.
- **Resolution:**
  - In development and local testing, this warning can be safely ignored.
  - To eliminate the warning, export an environment variable:
    ```bash
    # Linux / macOS
    export CLEARPATH_SECRET="my-secure-production-key"

    # Windows PowerShell
    $env:CLEARPATH_SECRET="my-secure-production-key"
    ```
  - Note: Automated tests run under `tests/conftest.py` which sets a test secret automatically, keeping `pytest` clean.

---

### 2.2 Streamlit Deprecation: `use_container_width`
- **Symptom:** Streamlit logs warning:
  ```
  The use_container_width parameter has been deprecated and will be removed in a future release. 
  Please use width="stretch" or width="auto" instead.
  ```
- **Explanation:** Streamlit 1.35+ deprecated `use_container_width=True` in favor of `width="stretch"`.
- **Resolution:** All calls in [clearpath/dashboard/app.py](file:///a:/CLEARPATH/clearpath/dashboard/app.py) have been updated to use `width="stretch"`. If you see this warning, ensure your repository working tree is up to date.

---

### 2.3 `StarletteDeprecationWarning` regarding `httpx`
- **Symptom:** Running `pytest` shows:
  ```
  StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.
  ```
- **Explanation:** This warning originates from FastAPI's internal `TestClient` bridge in the current Starlette release and does not affect simulation execution or test validity. It can be safely ignored.

---

## 3. Networking & Port Collisions

### 3.1 Port 8501 Already in Use (Streamlit)
- **Symptom:** Launching the dashboard fails or spawns on an unexpected port (`http://localhost:8502`).
- **Cause:** Another instance of Streamlit is already running on port 8501.
- **Resolution:**
  - Find and terminate the process holding port 8501:
    ```powershell
    # Windows
    Get-NetTCPConnection -LocalPort 8501 | Select-Object OwningProcess
    Stop-Process -Id <PID>
    ```
    ```bash
    # Linux / macOS
    lsof -i :8501
    kill -9 <PID>
    ```
  - Or specify an alternative port:
    ```bash
    python -m streamlit run clearpath/dashboard/app.py --server.port 8505
    ```

---

### 3.2 Port 8000 Already in Use (FastAPI)
- **Symptom:** Launching `uvicorn` fails with `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`.
- **Resolution:**
  - Launch Uvicorn on an alternate port:
    ```bash
    python -m uvicorn clearpath.api.server:app --port 8001
    ```

---

## 4. Frequently Asked Questions (FAQ)

### Q: Why does the scenario summary report `0.0 s` for cross-traffic delay?
**A:** In [clearpath/engine/metrics.py](file:///a:/CLEARPATH/clearpath/engine/metrics.py), `on_preemption_start()` is called at tick 10 to snapshot vehicle wait times, but `on_preemption_end()` was not invoked in the scenario runner upon ambulance arrival. Consequently, the delay sample list remains empty and returns `0.0 s`. When instrumented manually at ambulance arrival ($t=46$), active civilian vehicles experienced an average delay delta of **$10.52\text{ s}$** (p95: $21.00\text{ s}$). See [METRICS.md](METRICS.md#31-cross-traffic-delay-average--p95) for a complete explanation.

### Q: Can ClearPath create conflicting green signals if multiple ambulances approach at once?
**A:** No. Traffic signals are physically guarded by the `SignalController` state machine in [clearpath/sim/signals.py](file:///a:/CLEARPATH/clearpath/sim/signals.py). Any transition between orthogonal phases strictly enforces mandatory yellow ($3\text{ s}$) and all-red ($1\text{ s}$) clearance intervals. Additionally, the `JunctionAgent` applies deterministic triage priority (`CRITICAL > HIGH > MEDIUM > LOW`) to grant priority to one vehicle while rejecting the other with a `ReserveNack`.

### Q: Does ClearPath require GPU hardware to train the RL policy?
**A:** No. The deep Q-network in [clearpath/rl/train.py](file:///a:/CLEARPATH/clearpath/rl/train.py) is implemented in vectorized pure NumPy. Training 100 episodes on a $3 \times 3$ grid completes in under **3 minutes on a standard CPU laptop**.

### Q: Why does ClearPath use HMAC tokens instead of JWT?
**A:** Custom HMAC-SHA256 tokens eliminate external library dependencies, eliminate JWT header malleability and algorithm-confusion vulnerabilities (such as the `alg: none` exploit), and minimize wireless V2I transmission byte overhead. See [SECURITY.md](SECURITY.md#33-architectural-rationale-why-jwt-is-not-used).

---

## 5. Cross-Document References
- For installation and environment setup, see [SETUP.md](SETUP.md).
- For test suite execution, see [TESTING.md](TESTING.md).
- For dashboard guidance, see [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md).

