# Changelog

All notable changes to the ClearPath-lite platform are documented in this file.
The project adheres to Semantic Versioning (`MAJOR.MINOR.PATCH`).

## [v0.3.0] - 2026-11-16
### Added
- Comprehensive documentation suite in `docs/` covering architecture, agent specifications, message protocol, security threat modeling, algorithm derivations, simulation physics, API reference, testing catalog, setup instructions, and ADRs.
- Reinforcement learning junction control module (`clearpath/rl/`) with action safety masking, parameter sharing across intersections, and 3-way evaluation (Baseline vs Rules vs RL).
- Dedicated `UNAUTHORIZED_VEHICLE` security rejection code in `SecurityAgent` for unauthorized fleet identifiers.
- Concurrency protection via `asyncio.Lock` across mutating FastAPI endpoints (`/step`, `/reset`, `/emergency`).
- Test suite expansion to 114 tests with 100% passing status.

### Changed
- Dashboard layout updated for Streamlit compatibility (`width="stretch"`).
- Metrics reporting separated in spoofed benchmark: independent reporting for attack block rate (100.0%) and false-positive rate (0.0%).
- Dependencies refined in `requirements.txt`: included `matplotlib>=3.7.0`, removed unused packages.

## [v0.2.0] - 2026-11-15
### Added
- Standard benchmark scenario runners: `run_normal.py`, `run_emergency.py`, `run_spoofed.py`, and consolidated runner `run_all.py`.
- Interactive Streamlit dashboard (`clearpath/dashboard/app.py`) featuring 2D Plotly road network canvas, live signal markers, route overlays, and diagnostic inspectors.
- FastAPI REST service (`clearpath/api/server.py`) for headless simulation stepping and preemption submission.
- Tactical `GuidanceAgent` synthesizing lane-clearing advisories within a 150m forward lookahead zone and driving VMS boards.

## [v0.1.0] - 2026-11-14
### Added
- Core microscopic simulation engine: 2D road network model, IDM-lite car-following kinematics, and fixed-time signal controllers with clearance intervals.
- Asynchronous `MessageBus` with simulated wireless latency and probabilistic packet drops.
- Cryptographic `SecurityAgent` gating HMAC-SHA256 tokens and validating kinematic telemetry (speed, acceleration, heading, continuity).
- `DispatcherAgent` implementing multi-criteria hospital triage scoring and density-aware A* routing.
- Distributed `JunctionAgent` state machine coordinating green-wave preemption and post-preemption recovery phases.

