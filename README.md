# ClearPath-lite

**ClearPath-lite** is a 100% software-only, open-source, locally runnable multi-agent system for emergency ambulance preemption and urban traffic management.

---

## Architecture Overview

ClearPath-lite decouples the traffic world simulator from decision-making agents via an in-process, latency-aware `MessageBus`:

```
+--------------------------------------------------------------+
|                     ClearPath-lite Engine                    |
+--------------------------------------------------------------+
  |                                                          |
  v                                                          v
+------------------+                              +--------------------+
|  Deterministic   |                              |  Typed MessageBus  |
|  Grid Simulator  | <--- Minimal Actuators ----- |  (1s Latency, Logs)|
+------------------+                              +--------------------+
         ^                                                   ^
         | World View                                        | Typed Messages
         +--------------------+     +------------------------+
                              |     |
                 +-------------------------------+
                 |       Autonomous Agents       |
                 | - DispatcherAgent (Routing)   |
                 | - SecurityAgent (HMAC/JWT)    |
                 | - JunctionAgent (Green Waves) |
                 | - GuidanceAgent (Advisories)  |
                 +-------------------------------+
```

### The 4 Agents
1. **DispatcherAgent**: Evaluates incident locations, road network congestion, and regional hospital availability (bed count, specialty triage) to select destination hospitals and calculate A*/Dijkstra paths with per-junction ETA schedules.
2. **SecurityAgent**: Authenticates preemption requests using HMAC/JWT tokens and verifies continuous vehicle kinematics (speed, acceleration, heading, road snapping) against road limits and network topology to block spoofing.
3. **JunctionAgent**: Distributed per intersection. Receives projected ETAs, assesses local queues, negotiates green-wave corridors via inter-junction messaging, executes preemption, and manages fair post-preemption recovery phases.
4. **GuidanceAgent**: Generates dynamic tactical advisories for civilian drivers (e.g., "Clear lane 1", "Move right") to proactively clear the emergency vehicle's path.

---

## Project Layout

```
clearpath/
  config.py            # Frozen SimConfig dataclass and configuration loader
  sim/                 # Deterministic 1-second tick simulator
    network.py         # NetworkX grid topology and edge definitions
    vehicles.py        # Vehicle states, kinematics, and types
    signals.py         # Traffic signal phase controllers
    simulator.py       # Core simulation world loop
    traffic_gen.py     # Deterministic vehicle generation
  bus/                 # Decoupled communication
    messages.py        # Strongly-typed message dataclasses
    message_bus.py     # In-process bus with latency, topics, and fault injection
  agents/              # Autonomous multi-agent implementations
    base.py            # Abstract base Agent class
    security.py        # HMAC/JWT and kinematic verification
    dispatcher.py      # Multi-criteria routing and ETA scheduling
    junction.py        # Distributed intersection and recovery agent
    guidance.py        # Driver advisory synthesizer
  engine/              # Orchestration and metrics
    orchestrator.py    # Main tick coordinator
    metrics.py         # Aggregated simulation performance metrics
  data/                # Static data
    hospitals.json     # Hospital capacities, wait times, and specialties
  api/                 # REST API endpoints (FastAPI)
    server.py          # API server definition
  dashboard/           # Visualization (Streamlit)
    app.py             # Live traffic and preemption dashboard
  scenarios/           # Benchmark scenarios
    run_normal.py      # Normal traffic baseline
    run_emergency.py   # Valid preemption corridor
    run_spoofed.py     # Spoofed request rejection
    run_all.py         # Sequential benchmark runner
tests/                 # Pytest test suite
  test_bus.py          # MessageBus latency, broadcast, determinism, and log tests
pytest.ini             # Pytest configuration
requirements.txt       # Project dependencies
```

---

## Quickstart

### Installation
```bash
pip install -r requirements.txt
```

### Running Tests
```bash
pytest -q
```

### Verifying Imports
```bash
python -c "import clearpath; print(clearpath.__all__)"
```

