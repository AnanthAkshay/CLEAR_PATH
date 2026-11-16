# ClearPath-lite Installation & Setup Guide

This guide provides end-to-end instructions for installing dependencies, configuring environment variables, running tests, executing scenarios, launching the dashboard, and training reinforcement learning policies across Windows, macOS, and Linux.

## Table of Contents
- [1. System Prerequisites](#1-system-prerequisites)
- [2. Installation Walkthrough](#2-installation-walkthrough)
  - [2.1 Windows (PowerShell)](#21-windows-powershell)
  - [2.2 Linux & macOS (Bash/Zsh)](#22-linux--macos-bashzsh)
- [3. Environment Variable Configuration (CLEARPATH_SECRET)](#3-environment-variable-configuration-clearpath_secret)
- [4. Makefile Targets Reference](#4-makefile-targets-reference)
- [5. How to Run System Components](#5-how-to-run-system-components)
  - [5.1 Running the Test Suite](#51-running-the-test-suite)
  - [5.2 Running the Benchmark Scenarios](#52-running-the-benchmark-scenarios)
  - [5.3 Launching the Interactive Streamlit Dashboard](#53-launching-the-interactive-streamlit-dashboard)
  - [5.4 Starting the FastAPI REST Service](#54-starting-the-fastapi-rest-service)
  - [5.5 Training & Evaluating the RL Policy](#55-training--evaluating-the-rl-policy)
- [6. Expected Outputs & Verification Checkpoints](#6-expected-outputs--verification-checkpoints)
- [7. Cross-Document References](#7-cross-document-references)

---

## 1. System Prerequisites

Before installing, ensure your environment meets the following specifications:
- **Python:** Python 3.10, 3.11, 3.12, 3.13, or 3.14. (Tested extensively on Python 3.14.7).
- **Git:** Git 2.30+ installed and available on system PATH.
- **Operating System:** Windows 10/11, Ubuntu 20.04+, Debian 11+, or macOS 12+ (Apple Silicon or Intel).
- **RAM & Disk:** Minimum 4 GB RAM; ~250 MB free disk space for virtualenv and dependencies.

---

## 2. Installation Walkthrough

### 2.1 Windows (PowerShell)
Open PowerShell in the repository root directory:

```powershell
# 1. Clone repository (if not already cloned)
git clone https://github.com/AnanthAkshay/CLEAR_PATH.git
cd CLEAR_PATH

# 2. Create Python virtual environment
python -m venv venv

# 3. Activate virtual environment
.\venv\Scripts\Activate.ps1

# If script execution is restricted on Windows, allow execution for current session:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 4. Upgrade pip and install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2.2 Linux & macOS (Bash/Zsh)
Open a terminal shell in the repository root directory:

```bash
# 1. Clone repository
git clone https://github.com/AnanthAkshay/CLEAR_PATH.git
cd CLEAR_PATH

# 2. Create Python virtual environment
python3 -m venv venv

# 3. Activate virtual environment
source venv/bin/activate

# 4. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Environment Variable Configuration (`CLEARPATH_SECRET`)

ClearPath uses an HMAC-SHA256 shared secret to authenticate emergency preemption tokens:

- **Development Default:** If `CLEARPATH_SECRET` is unset, the system uses an internal development fallback (`clearpath-dev-secret-key-12345`) and issues a loud warning.
- **Setting Production Secret:**
  ```powershell
  # Windows PowerShell
  $env:CLEARPATH_SECRET="your-high-entropy-production-key-here"
  ```
  ```bash
  # Linux & macOS
  export CLEARPATH_SECRET="your-high-entropy-production-key-here"
  ```
- **Automated Tests:** In `tests/conftest.py`, a dedicated test secret is automatically loaded, preventing warnings during `pytest` execution.

---

## 4. Makefile Targets Reference

A `Makefile` is provided for standard operations:

| Target | Underlying Command | Description |
|---|---|---|
| `make install` | `pip install -r requirements.txt` | Installs all production and test dependencies. |
| `make test` | `python -m pytest -q` | Executes full 114-test verification suite. |
| `make demo` | `python -m clearpath.scenarios.run_all` | Runs all 3 benchmark scenarios and prints final PASS checklist. |
| `make dashboard` | `streamlit run clearpath/dashboard/app.py` | Launches interactive browser UI at `http://localhost:8501`. |
| `make rl-train` | `python -m clearpath.rl.train --episodes 100 --seed 42` | Trains Q-network with parameter sharing across junctions. |
| `make rl-eval` | `python -m clearpath.rl.train --eval-only` | Runs honest 3-way evaluation: Baseline vs Rules vs RL. |

---

## 5. How to Run System Components

### 5.1 Running the Test Suite
```bash
# Run quiet test suite
make test
# Or verbose output
python -m pytest -v
```

### 5.2 Running the Benchmark Scenarios
Each scenario can be executed individually as a standalone module:

```bash
# 1. Normal traffic baseline (600 ticks, low/med/high demand)
python -m clearpath.scenarios.run_normal

# 2. Emergency preemption comparison (Baseline vs ClearPath)
python -m clearpath.scenarios.run_emergency

# 3. Cyber-physical spoofed attack injection (6 attacks + 1 legitimate)
python -m clearpath.scenarios.run_spoofed

# 4. Full consolidated benchmark checklist
python -m clearpath.scenarios.run_all
```

### 5.3 Launching the Interactive Streamlit Dashboard
```bash
make dashboard
# Or directly:
python -m streamlit run clearpath/dashboard/app.py
```
Open your browser to `http://localhost:8501`.

### 5.4 Starting the FastAPI REST Service
```bash
python -m uvicorn clearpath.api.server:app --host 127.0.0.1 --port 8000
```
Interactive OpenAPI Swagger docs will be accessible at `http://127.0.0.1:8000/docs`.

### 5.5 Training & Evaluating the RL Policy
```bash
# Train shared Q-network across 100 episodes
make rl-train

# Run 3-way comparison on 3x3 grid
make rl-eval
```

---

## 6. Expected Outputs & Verification Checkpoints

When running `make demo` or `python -m clearpath.scenarios.run_all`, the terminal output should conclude with the following checklist:

```
============================================================================
FINAL BENCHMARK VERIFICATION CHECKLIST
============================================================================
 [PASS] CHK-01: Normal traffic baseline (autonomous cycling, 0 preempted)
        -> 600 ticks, throughput=1.273 veh/t, avg speed=6.15 m/s
 [PASS] CHK-02: Emergency ambulance travel time improvement
        -> ClearPath=35.0s vs Baseline=111.0s (-68.5%)
 [PASS] CHK-03: Network throughput recovery within recovery_s + 60s
        -> Recovered to 97.7% of baseline throughput
 [PASS] CHK-04: Security gateway attack rejection (6/6 blocked, 1/1 allowed)
        -> Blocked 6/6 attacks (100%), allowed 1/1 legitimate
 [PASS] CHK-05: Attack signal override isolation (0 overrides from attacks)
        -> Zero signal phase overrides caused by spoofed requests
----------------------------------------------------------------------------
STATUS: ALL PASS
Reports written to:
  - results/summary.json
  - results/summary.md
============================================================================
```

And when running `make test`:
```
114 passed, 1 warning in 8.39s
```

---

## 7. Cross-Document References
- For common installation issues and troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
- For Streamlit UI instructions, see [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md).
- For complete test descriptions, see [TESTING.md](TESTING.md).

