# ClearPath-lite Architectural Decision Records (ADRs)

This document records the fundamental design and architectural decisions made during the construction of ClearPath-lite, formatted as Architectural Decision Records (ADR) detailing context, chosen options, alternatives considered, and engineering consequences.

## Table of Contents
- [ADR-001: Custom Lightweight Python Simulator vs. SUMO](#adr-001-custom-lightweight-python-simulator-vs-sumo)
- [ADR-002: In-Process Asynchronous MessageBus vs. Network Broker](#adr-002-in-process-asynchronous-messagebus-vs-network-broker)
- [ADR-003: Compact HMAC-SHA256 Tokens vs. JSON Web Tokens (JWT)](#adr-003-compact-hmac-sha256-tokens-vs-json-web-tokens-jwt)
- [ADR-004: Distributed Sequential Negotiation vs. Centralized Controller](#adr-004-distributed-sequential-negotiation-vs-centralized-controller)
- [ADR-005: Density-Aware A* Cost Model with Fixed Normalization](#adr-005-density-aware-a-cost-model-with-fixed-normalization)
- [ADR-006: Global Deterministic Seeding via Pure NumPy Generators](#adr-006-global-deterministic-seeding-via-pure-numpy-generators)
- [ADR-007: Reinforcement Learning with Action Safety Masking](#adr-007-reinforcement-learning-with-action-safety-masking)
- [Cross-Document References](#cross-document-references)

---

### ADR-001: Custom Lightweight Python Simulator vs. SUMO

#### Context
Evaluating multi-agent preemption algorithms and cyber-physical security vectors requires rapid iteration across hundreds of simulation ticks and thousands of automated tests. Eclipse SUMO is the industry standard for microscopic traffic simulation, but requires heavyweight C++ binaries, TraCI socket communication overhead, and complex XML road network definitions.

#### Decision
Build an internal, microscopic 2D traffic simulator in pure Python using NetworkX and an Intelligent Driver Model (IDM-lite).

#### Alternatives Considered
- **Eclipse SUMO / TraCI:** Full physical fidelity, but adds multi-gigabyte external dependencies, slow socket step latency (~10x slower execution), and severe setup friction across diverse operating systems.
- **Aimsun / VISSIM:** Proprietary, closed-source, and incompatible with open-source hackathon benchmarks.

#### Consequences
- **Positive:** Blazing execution speed (900 ticks execute in $<11\text{ s}$ on a CPU); zero external C++ dependencies; 100% reproducible execution in pure Python; instant test suite runs (114 tests pass in $<9\text{ s}$).
- **Negative:** Omits complex continuous 3D vehicle dynamics, vehicle yaw angles, lateral overtaking friction, and multi-modal traffic (pedestrians/bicycles).

---

### ADR-002: In-Process Asynchronous MessageBus vs. Network Broker

#### Context
Autonomous agents must communicate without directly accessing internal simulator pointers. However, deploying an external message broker (RabbitMQ, Kafka, or Mosquitto MQTT) introduces heavy infrastructure dependencies and networking flakiness to the local evaluation pipeline.

#### Decision
Implement a zero-dependency in-process `MessageBus` dataclass abstraction ([clearpath/bus/message_bus.py](file:///a:/CLEARPATH/clearpath/bus/message_bus.py)) that enforces asynchronous delivery, simulated wireless latency, and probabilistic packet drops in memory.

#### Alternatives Considered
- **MQTT / Mosquitto Broker:** Highly realistic V2X representation, but requires running a background daemon process, opening network ports, and managing socket lifecycles in unit tests.
- **Direct Python Method Calls:** Removes communication overhead entirely, but tightly couples agents to simulator internals, violating multi-agent boundaries.

#### Consequences
- **Positive:** Zero external services required; deterministic testing of packet drops ($10\%$ drop rate test) and network latency without network flakes.
- **Negative:** In-process messaging does not provide network isolation or TLS encryption out-of-the-box. (See roadmap for MQTT adapter in [LIMITATIONS_AND_FUTURE_WORK.md](LIMITATIONS_AND_FUTURE_WORK.md)).

---

### ADR-003: Compact HMAC-SHA256 Tokens vs. JSON Web Tokens (JWT)

#### Context
Emergency vehicle preemption requests must be cryptographically authenticated to prevent spoofing. JSON Web Tokens (JWT) are ubiquitous in web applications, while HMAC-SHA256 provides raw symmetric authentication.

#### Decision
Use custom compact HMAC-SHA256 tokens (`vehicle_id.nonce.ts.signature`) with constant-time verification (`hmac.compare_digest`) and remove `pyjwt` from dependencies.

#### Alternatives Considered
- **JSON Web Tokens (JWT):** Supported by many libraries, but introduces third-party dependency vulnerabilities, algorithm-confusion risks (e.g., `alg: none` exploit), and JSON payload byte overhead over V2I radio.
- **Unauthenticated Siren Chirps / Optical Strobes:** Legacy industry approach, highly vulnerable to SDR radio replay attacks.

#### Consequences
- **Positive:** Minimal byte footprint ($<100$ bytes); zero third-party dependencies; eliminated JWT parser vulnerabilities; constant-time comparison prevents timing attacks.
- **Negative:** Requires pre-shared symmetric keys rather than asymmetric public-key certificate validation.

---

### ADR-004: Distributed Sequential Negotiation vs. Centralized Controller

#### Context
Coordinating green waves across a corridor can be achieved either by a centralized municipal traffic management center (TMC) that commands all signals or by distributed edge negotiation among neighboring intersection controllers.

#### Decision
Implement distributed sequential negotiation: the `DispatcherAgent` issues scheduled ETAs, but individual `JunctionAgents` autonomously evaluate local feasibility, negotiate sequential locks via `ReserveCorridor`/`ReserveAck`, and execute local recovery.

#### Alternatives Considered
- **Centralized Signal Overrides:** The central dispatcher directly overrides all signals along the corridor simultaneously. While simpler, it ignores local cross-street queues, creates severe cross-street gridlock, and introduces a single point of failure.

#### Consequences
- **Positive:** Resilient to partial network partition; local intersections reject reservations if cross-queues are undrainable; prevents city-wide gridlock through autonomous recovery cycles.
- **Negative:** Requires multi-hop message exchanges (74 messages per corridor run) and timeout handling for dropped messages.

---

### ADR-005: Density-Aware A* Cost Model with Fixed Normalization

#### Context
Dispatching ambulances to hospitals requires balancing travel time through congested streets against emergency room waiting times. If normalization scales dynamically relative to current candidate minima and maxima, hospital rankings can flip unexpectedly when unrelated hospitals open or close.

#### Decision
Implement a density-aware edge cost model solved via A* with an admissible Euclidean heuristic, and score hospitals against fixed external reference constants ($t_{\text{ref\_travel}} = 120\text{s}$, $t_{\text{ref\_wait}} = 1800\text{s}$).

#### Alternatives Considered
- **Static Free-Flow Shortest Path:** Fast Dijkstra search on speed limits, but routes ambulances directly into massive traffic jams.
- **Dynamic Min-Max Candidate Scaling:** Normalizes candidates relative to $[\min, \max]$ of the current pool. Violates the Independence of Irrelevant Alternatives (IIA) axiom.

#### Consequences
- **Positive:** Route dynamically circumvents congested avenues; hospital scores depend strictly on their own merits; ranking is robust and deterministic.
- **Negative:** Reference denominators must be calibrated to the geographic scale of the city.

---

### ADR-006: Global Deterministic Seeding via Pure NumPy Generators

#### Context
Simulation and reinforcement learning experiments often suffer from stochastic flakiness, making security and safety regressions difficult to reproduce and debug.

#### Decision
Eliminate global `random` state and enforce deterministic seeding using explicit `np.random.default_rng(config.seed)` instances passed down through simulator and agent classes.

#### Alternatives Considered
- **Global Python `random.seed()`:** Prone to leakage and order-of-import pollution across concurrent threads and test runners.

#### Consequences
- **Positive:** 100% bitwise reproducibility across runs; regression tests reproduce identical failures every time; eliminates flaky test runs.
- **Negative:** Requires passing RNG instances or configurations explicitly during class initialization.

---

### ADR-007: Reinforcement Learning with Action Safety Masking

#### Context
Applying deep reinforcement learning (RL) to traffic signal control allows policies to discover non-linear phase timing. However, unconstrained exploration can lead the policy to choose conflicting greens or starve pedestrian crossings.

#### Decision
Implement independent Q-learning with multi-junction parameter sharing in pure NumPy, and wrap action selection with a strict **Safety Action Masking** layer enforced by the physical state machine.

#### Alternatives Considered
- **Unconstrained RL Exploration:** Relies on reward penalties to discourage collisions. Inevitably causes catastrophic crashes during initial exploration.
- **Full Centralized MAPPO:** High training complexity, requiring PyTorch/GPU hardware and excessive training time.

#### Consequences
- **Positive:** Mathematical guarantee of zero conflicting greens during training and inference; lightweight vectorized training on CPU in $<3$ minutes.
- **Negative:** The policy's action space is constrained by the hardcoded clearance safety intervals.

---

## Cross-Document References
- For system architecture diagrams, see [ARCHITECTURE.md](ARCHITECTURE.md).
- For security and HMAC design, see [SECURITY.md](SECURITY.md).
- For RL action masking formulas, see [RL_POLICY.md](RL_POLICY.md).

