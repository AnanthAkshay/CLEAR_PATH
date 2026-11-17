# ClearPath-lite Documentation Index

ClearPath-lite is an open-source, multi-agent AI system designed for intelligent emergency vehicle preemption, cryptographic security verification, and equitable urban traffic recovery. This index outlines the full documentation suite, providing quick reference summaries and guided reading paths tailored to developers, academic evaluators, and demo presenters.

## Table of Contents
- [Documentation Catalog](#documentation-catalog)
- [Suggested Reading Orders](#suggested-reading-orders)
  - [1. For New Developers](#1-for-new-developers)
  - [2. For Reviewers, Auditors, and Hackathon Judges](#2-for-reviewers-auditors-and-hackathon-judges)
  - [3. For Presenters Running the Live Demo](#3-for-presenters-running-the-live-demo)
- [Core Verification Metrics](#core-verification-metrics)

---

## Documentation Catalog

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | High-level system design, multi-agent component architecture, per-tick execution loop sequence diagram, and engineering design principles. |
| [AGENTS.md](AGENTS.md) | In-depth specifications of the four core agents (Dispatcher, Security, Junction, Guidance): algorithms, state machines, inputs, outputs, and failure modes. |
| [MESSAGE_PROTOCOL.md](MESSAGE_PROTOCOL.md) | Complete specification of typed dataclass messages, asynchronous bus delivery semantics, latency/drop models, and corridor reservation handshake sequences. |
| [SECURITY.md](SECURITY.md) | Threat model, HMAC-SHA256 token verification, kinematic telemetry validation, attack defense matrix, secret management, and security test invariants. |
| [DISPATCHER_ALGORITHM.md](DISPATCHER_ALGORITHM.md) | Hospital multi-criteria triage scoring, density-aware edge cost function, A* routing heuristic, degraded fallback, and dynamic congestion replanning. |
| [JUNCTION_PROTOCOL.md](JUNCTION_PROTOCOL.md) | Distributed junction state machine, pre-clearing, green-wave holds, starvation-preventing recovery cycles, fail-safe timeouts, and conflict safety proofs. |
| [SIMULATION.md](SIMULATION.md) | Synthetic 2D urban grid physics, IDM-lite car-following mechanics, Poisson traffic demand generation, clearance intervals, and physical limitations. |
| [API.md](API.md) | FastAPI REST service specification, endpoint schemas, concurrency guarantees (`asyncio.Lock`), and verified `curl` execution examples. |
| [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md) | Interactive Streamlit interface guide, map visualization layers, signal indicator interpretation, security verdict inspection, and scenario reproduction. |
| [DEPLOY_STREAMLIT.md](DEPLOY_STREAMLIT.md) | Complete deployment guide for launching the multi-page Streamlit application to Streamlit Community Cloud or Docker containers. |
| [UI_QA_REPORT.md](UI_QA_REPORT.md) | Quality assurance and compliance report verifying all 20 UI features, editorial design tokens, and zero-overflow responsive testing. |
| [METRICS.md](METRICS.md) | Mathematical formulas, telemetry collection rules, vehicle coverage boundaries, and implementation code references for all system metrics. |
| [RESULTS.md](RESULTS.md) | Verified empirical benchmarks: normal traffic baselines, emergency preemption comparison, 6-attack spoofed audit, 5-seed sweeps, and 3-way RL evaluation. |
| [RL_POLICY.md](RL_POLICY.md) | Reinforcement learning environment (`ClearPathGridEnv`), action masking, shared multi-agent Q-network architecture, and policy evaluation versus rule heuristics. |
| [TESTING.md](TESTING.md) | Complete test suite catalog (114 tests), determinism testing, property-based safety invariant proofs, mock scenarios, and execution commands. |
| [SETUP.md](SETUP.md) | Installation guide across Windows (PowerShell), Linux, and macOS, environment variables (`CLEARPATH_SECRET`), Makefile commands, and run targets. |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common environment issues, runtime warnings, port collisions, PowerShell script execution nuances, and an operational FAQ. |
| [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) | Architectural Decision Records (ADRs) explaining key choices: custom simulator vs. SUMO, in-process bus, HMAC vs. JWT, and distributed negotiation. |
| [LIMITATIONS_AND_FUTURE_WORK.md](LIMITATIONS_AND_FUTURE_WORK.md) | Transparent analysis of physical and network model limitations, alongside a structured development roadmap (SUMO/TraCI, MQTT, MARL). |
| [GLOSSARY.md](GLOSSARY.md) | Comprehensive definitions of domain terminology across traffic engineering, distributed systems, cyber-physical security, and reinforcement learning. |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | Exact 3-minute scripted presentation walkthrough covering setup, talking points, screen interactions, and key benchmark figures. |
| [PITCH.md](PITCH.md) | Structured 6-slide presentation deck outline complete with slide narrative, technical arguments, speaker notes, and presentation tips. |
| [PROJECT_REPORT.md](PROJECT_REPORT.md) | Comprehensive academic/engineering technical report covering abstract, problem formulation, methodology, empirical results, and conclusions. |

---

## Suggested Reading Orders

### 1. For New Developers
To understand the codebase structure and begin contributing new features or test scenarios:
1. [SETUP.md](SETUP.md) — Set up Python, dependencies, and verify green test status.
2. [ARCHITECTURE.md](ARCHITECTURE.md) — Understand how the simulation engine, message bus, and agents interact.
3. [AGENTS.md](AGENTS.md) — Study the role and responsibilities of each autonomous agent.
4. [MESSAGE_PROTOCOL.md](MESSAGE_PROTOCOL.md) — Learn how agents exchange messages across the bus.
5. [SIMULATION.md](SIMULATION.md) — Understand the underlying traffic physics and car-following equations.
6. [TESTING.md](TESTING.md) — Review existing test invariants before authoring code changes.

### 2. For Reviewers, Auditors, and Hackathon Judges
To evaluate system correctness, safety guarantees, cryptographic rigor, and experimental performance:
1. [PROJECT_REPORT.md](PROJECT_REPORT.md) — High-level technical overview and project motivations.
2. [SECURITY.md](SECURITY.md) — Inspection of HMAC authentication, replay prevention, and kinematic checks.
3. [JUNCTION_PROTOCOL.md](JUNCTION_PROTOCOL.md) — Verification of orthogonal conflict prevention and starvation mitigation.
4. [RESULTS.md](RESULTS.md) — Review empirical data from the 114 tests, 5-seed sweeps, and attack rejection benchmarks.
5. [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) — Rationale behind architectural trade-offs.
6. [LIMITATIONS_AND_FUTURE_WORK.md](LIMITATIONS_AND_FUTURE_WORK.md) — Honest appraisal of real-world deployment challenges.

### 3. For Presenters Running the Live Demo
To prepare a live interactive showcase in under 3 minutes:
1. [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — Rehearse the 3-minute narrative, click sequence, and metric highlights.
2. [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md) — Learn the visual layout, controls, and scenario triggers of the Streamlit app.
3. [PITCH.md](PITCH.md) — Familiarize yourself with the slide deck structure and speaker notes.
4. [RESULTS.md](RESULTS.md) — Memorize the core benchmark figures to answer judge questions accurately.

---

## Core Verification Metrics
All figures in these documents are derived directly from the automated benchmark suite:
- **Test Suite Status:** `119 / 119 passed` (100% green).
- **Emergency Travel Time:** Dropped from **111.0 s** (Baseline) to **35.0 s** (ClearPath) — **-68.5% transit time reduction**.
- **Ambulance Stops:** Reduced from **7 stops** to **0 stops** (unbroken green wave).
- **Network Recovery:** Cross-traffic throughput returns to **97.7%** of baseline throughput within recovery window + 60s.
- **Cyber-Physical Defense:** **100% attack block rate** (6/6 blocked), **0.0% false positive rate** (1/1 legitimate allowed), and **0 signal overrides leaked**.

