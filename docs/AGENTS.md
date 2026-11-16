# ClearPath-lite Autonomous Agents

This document provides a comprehensive engineering specification for the four core intelligent agents comprising the ClearPath-lite multi-agent system: DispatcherAgent, SecurityAgent, JunctionAgent, and GuidanceAgent.

## Table of Contents
- [1. DispatcherAgent](#1-dispatcheragent)
  - [1.1 Purpose & Role](#11-purpose--role)
  - [1.2 Inputs & Outputs](#12-inputs--outputs)
  - [1.3 Internal State](#13-internal-state)
  - [1.4 Step-by-Step Algorithm](#14-step-by-step-algorithm)
  - [1.5 Configuration Parameters](#15-configuration-parameters)
  - [1.6 Failure Modes & Edge Cases](#16-failure-modes--edge-cases)
  - [1.7 Implementation References](#17-implementation-references)
- [2. SecurityAgent](#2-securityagent)
  - [2.1 Purpose & Role](#21-purpose--role)
  - [2.2 Inputs & Outputs](#22-inputs--outputs)
  - [2.3 Internal State](#23-internal-state)
  - [2.4 Step-by-Step Algorithm](#24-step-by-step-algorithm)
  - [2.5 Configuration Parameters](#25-configuration-parameters)
  - [2.6 Failure Modes & Edge Cases](#26-failure-modes--edge-cases)
  - [2.7 Implementation References](#27-implementation-references)
- [3. JunctionAgent](#3-junctionagent)
  - [3.1 Purpose & Role](#31-purpose--role)
  - [3.2 Inputs & Outputs](#32-inputs--outputs)
  - [3.3 Internal State](#33-internal-state)
  - [3.4 Step-by-Step Algorithm](#34-step-by-step-algorithm)
  - [3.5 Configuration Parameters](#35-configuration-parameters)
  - [3.6 Failure Modes & Edge Cases](#36-failure-modes--edge-cases)
  - [3.7 Implementation References](#37-implementation-references)
- [4. GuidanceAgent](#4-guidanceagent)
  - [4.1 Purpose & Role](#41-purpose--role)
  - [4.2 Inputs & Outputs](#42-inputs--outputs)
  - [4.3 Internal State](#43-internal-state)
  - [4.4 Step-by-Step Algorithm](#44-step-by-step-algorithm)
  - [4.5 Configuration Parameters](#45-configuration-parameters)
  - [4.6 Failure Modes & Edge Cases](#46-failure-modes--edge-cases)
  - [4.7 Implementation References](#47-implementation-references)

---

## 1. DispatcherAgent

### 1.1 Purpose & Role
The `DispatcherAgent` is the centralized strategic planning agent responsible for hospital selection, density-aware shortest-path routing, and timeline ETA scheduling for authenticated emergency preemption corridors.

### 1.2 Inputs & Outputs
- **Inputs:**
  - `PreemptionRequest` message and corresponding `AuthResult` from the `SecurityAgent`.
  - Live `WorldView` perception state containing network traffic densities (`veh/km`) and intersection approach queue lengths.
  - Hospital database containing geographic locations, specialty departments, available unit bed counts, and estimated emergency room waiting times.
- **Outputs:**
  - `RoutePlan` broadcast message containing designated vehicle ID, destination hospital, ordered sequence of junction nodes, and total estimated transit time.
  - Unicast `EtaNotice` messages dispatched to every downstream junction along the corridor timeline.

### 1.3 Internal State
- `_auth: Dict[str, AuthResult]`: Mapping of active authenticated emergency vehicle sessions.
- `_plans: Dict[str, Dict[str, Any]]`: Active routing plans keyed by vehicle ID, storing paths, scheduled ETAs, and initial edge cost estimates.
- `_cached_weights_tick: Optional[int]`: Simulation tick for cached edge weights to avoid recomputing identical road costs multiple times in the same tick.
- `_static_edge_params`: Precomputed static geometric edge properties (length, speed limit, vehicle spacing, and jam density).

### 1.4 Step-by-Step Algorithm
1. **Authentication Check:** When `dispatch()` is invoked, verify that `vehicle_id in self._auth`. If unauthenticated, refuse dispatch immediately.
2. **Dynamic Edge Costing:** For every directed edge $e=(u, v)$, compute live travel time:
   $$t_{\text{edge}} = \frac{L}{\max(v_{\min}, v_{\text{limit}} \cdot (1 - \text{density}))} + (\text{queue\_len} \cdot \text{headway})$$
3. **Candidate Hospital Evaluation:** Filter hospitals by medical specialty and positive bed capacity for the incident type. If zero hospitals qualify, enter **degraded fallback mode** (relax specialty constraints and sum all available beds across all departments).
4. **Multi-Criteria Scoring:** Compute cost score for each qualifying hospital:
   $$\text{Score} = \alpha \cdot \frac{t_{\text{travel}}}{t_{\text{ref\_travel}}} + (1 - \alpha) \cdot \frac{t_{\text{wait}}}{t_{\text{ref\_wait}}}$$
5. **A* Pathfinding:** Solve optimal path to the lowest-scoring hospital using A* with Euclidean distance over maximum ambulance speed as an admissible lower-bound heuristic.
6. **Preemption Corridor Scheduling:** Project arrival timestamp at each junction assuming preemption-enabled corridor speed $\min(0.8 \cdot v_{\text{amb\_max}}, 1.3 \cdot v_{\text{limit}})$.
7. **Broadcast & Replanning:** Publish `RoutePlan` and individual `EtaNotice` messages. During periodic ticks (every 5 ticks), evaluate `reroute_if_congested()`. If traffic congestion inflates active corridor travel cost by $>25\%$, re-route from the ambulance's live position.

### 1.5 Configuration Parameters
- `alpha = 0.7`: Tradeoff weight balancing transit time vs. ER wait time.
- `reference_travel_s = 120.0`: Reference transit baseline (seconds).
- `reference_wait_s = 1800.0`: Reference hospital wait baseline (30 minutes).
- `min_speed_mps = 2.0`: Floor on effective vehicle progression velocity.
- `avg_gap_m = 5.0`: Assumed bumper gap added to vehicle length when estimating headway.

### 1.6 Failure Modes & Edge Cases
- **No Qualified Hospital:** Triggers degraded mode to route to the nearest facility with any open bed.
- **Node Rejection:** When downstream junctions reject via `ReserveNack`, `replan()` is called with `blocked_nodes` to pathfind around the congested node.
- **Revocation:** If a `RevokePreemption` arrives, the active session is deleted from `_auth`, halting preemption broadcasts.

### 1.7 Implementation References
- **File:** [clearpath/agents/dispatcher.py](file:///a:/CLEARPATH/clearpath/agents/dispatcher.py)
- **Key Functions:** `dispatch()`, `replan()`, `reroute_if_congested()`, `_rank()`, `_score()`, `_edge_cost()`, `_schedule()`.

---

## 2. SecurityAgent

### 2.1 Purpose & Role
The `SecurityAgent` acts as the cyber-physical perimeter firewall. It authenticates cryptographic HMAC-SHA256 preemption tokens, protects against replay and spoofing attacks, and validates vehicle kinematic telemetry against urban road physics.

### 2.2 Inputs & Outputs
- **Inputs:** `PreemptionRequest` messages containing vehicle ID, HMAC token string, single-use nonce, and continuous `Telemetry` snapshots (coordinates, speed, acceleration, heading, edge ID).
- **Outputs:** `AuthResult` message containing `is_authenticated` boolean, granular failure reason codes, risk score, and structured audit log string. Publishes `RevokePreemption` if an active vehicle later violates kinematic invariants.

### 2.3 Internal State
- `_nonces: Dict[str, float]`: Sliding-window cache storing used nonces with ingestion timestamps.
- `_last: Dict[str, Tuple[float, float, Optional[Tuple[str, str]], float]]`: Previous verified coordinate, edge, and timestamp per vehicle for continuity checks.
- `_requests: Dict[str, List[float]]`: Request arrival timestamps per vehicle for rate limiting.
- `_failures: List[float]`: Agent-wide failure budget tracking failed verification attempts.
- `_claimed_failures: Dict[str, List[float]]`: Failure history per claimed vehicle ID to throttle repeated invalid probes.
- `audit_trail: List[Dict[str, Any]]`: Full chronological history of evaluated requests.

### 2.4 Step-by-Step Algorithm
1. **Pre-Check Throttling:** Check if the claimed vehicle ID has saturated failure buckets (`_claimed_failures >= rate_limit`). If so, reject immediately with `RATE_LIMIT` to protect HMAC verification CPU quota.
2. **Cryptographic Verification:** Parse token format (`vehicle_id.nonce.ts.signature`). Compute HMAC-SHA256 over `vehicle_id|nonce|ts` and execute constant-time comparison via `hmac.compare_digest()`. If signature differs, reject with `TOKEN`.
3. **Timestamp & Skew Check:** Verify token age: $(t_{\text{now}} - t_{\text{ts}}) \le \text{token\_ttl\_s}$ (60s) and $(t_{\text{ts}} - t_{\text{now}}) \le \text{clock\_skew\_s}$ (5s). If expired, reject with `TOKEN`.
4. **Fleet Authorization:** Check if vehicle ID is in `authorized_vehicle_ids`. If restricted and not listed, reject with `UNAUTHORIZED_VEHICLE`.
5. **Replay Protection:** Verify that `nonce` has not been observed in `_nonces`. If duplicate, reject with `TOKEN`. Record nonce upon approval.
6. **Kinematic Telemetry Checks:**
   - **Speed Limit:** Ensure $v \le \max(v_{\text{amb\_max}}, 1.5 \cdot v_{\text{limit}})$. Reject with `SPEED_LIMIT` if exceeded.
   - **Acceleration Limit:** Ensure $|a| \le a_{\text{max\_accel}}$ ($4.0\text{ m/s}^2$). Flag with `ACCELERATION`.
   - **Road Geometry Matching:** Ensure $(x, y)$ projects onto road segment within `position_tolerance_m` ($30.0\text{ m}$). Reject with `POSITION_ON_ROAD`.
   - **Heading Vector Match:** Ensure $|\theta_{\text{vehicle}} - \theta_{\text{road}}| \le \text{heading\_tolerance\_deg}$ ($35.0^\circ$). Adds $1.0$ to risk score if violated.
   - **Spatio-Temporal Continuity:** Ensure distance moved from last known position satisfies:
     $$\Delta d \le (v_{\text{amb\_max}} \cdot \Delta t) + \text{position\_tolerance\_m}$$
     Reject with `CONTINUITY` if violated (blocks GPS teleports).
7. **Verdict Issuance:** Approve only if zero hard reason codes are present and soft `risk_score <= 0.6`.

### 2.5 Configuration Parameters
- `token_ttl_s = 60`: Cryptographic token validity window (seconds).
- `clock_skew_s = 5.0`: Maximum acceptable forward timestamp drift (seconds).
- `heading_tolerance_deg = 35.0`: Heading deviation tolerance.
- `position_tolerance_m = 30.0`: GPS road projection margin.
- `rate_limit_per_vehicle_per_min = 6`: Permitted requests per vehicle per minute.
- `max_replay_cache_size = 10000`: Hard bound on nonce cache size to prevent memory exhaustion attacks.

### 2.6 Failure Modes & Edge Cases
- **Secret Misconfiguration:** Emits a prominent system `UserWarning` if default development HMAC key is in use.
- **Mid-Route Telemetry Drift:** If continuous stream telemetry deviates mid-corridor, `validate_stream()` publishes a broadcast `RevokePreemption` to tear down preemption green waves immediately.

### 2.7 Implementation References
- **File:** [clearpath/agents/security.py](file:///a:/CLEARPATH/clearpath/agents/security.py), [clearpath/agents/tokens.py](file:///a:/CLEARPATH/clearpath/agents/tokens.py)
- **Key Functions:** `authenticate()`, `validate_stream()`, `_check_token()`, `_telemetry_reasons()`, `_continuity_ok()`, `_position_ok()`.

---

## 3. JunctionAgent

### 3.1 Purpose & Role
The `JunctionAgent` is a distributed, autonomous agent deployed at each physical intersection. It manages phase preemption, evaluates queue drainage feasibility, coordinates green-wave handoffs with neighbors, and executes equitable recovery cycles to eliminate cross-street gridlock.

### 3.2 Inputs & Outputs
- **Inputs:** `RoutePlan`, `EtaNotice`, `ReserveCorridor`, `ReserveAck`, `ReserveNack`, `GreenWavePrepare`, `PassedNotice`, and `RevokePreemption` bus messages.
- **Outputs:** `ReserveAck`, `ReserveNack`, `GreenWavePrepare`, `RecoveryStarted`, and `RecoveryDone` bus messages. Actuator commands: `set_signal_override()` and `clear_signal_override()`.

### 3.3 Internal State
- `state: JunctionState`: Lifecycle phase (`NORMAL`, `PRE_CLEAR`, `HOLD_GREEN`, `RECOVERY`, `REJECTED`).
- `_reservation: Optional[Dict[str, Any]]`: Active vehicle reservation data (ETA, approach edge, target phase, severity).
- `_hold_started: Optional[float]`: Timestamp when preemption override was engaged.
- `_recovery_until: Optional[float]`: Timestamp when compensating green phase terminates.
- `_starved_phase: Optional[str]`: The orthogonal phase that was suppressed during preemption.

### 3.4 Step-by-Step Algorithm
1. **Reservation & Concurrency:** On receipt of an `EtaNotice`, check for overlapping reservations within `window_s` ($25\text{ s}$). If another emergency vehicle competes, higher severity level wins (`CRITICAL > HIGH > MEDIUM > LOW`), broken by earlier ETA. Loser is rejected with `ReserveNack`.
2. **Feasibility Inspection:** At $t = \text{ETA} - \text{window\_s}$, evaluate cross-street queue length $Q_{\text{cross}}$:
   - If $Q_{\text{cross}} \le \text{queue\_flush\_threshold}$ (12 veh): Normal preemption. Switch phase at $\text{ETA} - 5.0\text{ s}$.
   - If $Q_{\text{cross}} > 12\text{ veh}$: Transition to `PRE_CLEAR` immediately, clearing cross traffic until clearance intervals require green switch.
   - If $Q_{\text{cross}}$ cannot drain in time: Emit `ReserveNack` with earliest feasible clearance timestamp and enter `REJECTED`.
3. **Signal Override Engagement:** Request target green phase via `actuators.set_signal_override()`. Physical controller enforces yellow (3.0s) and all-red (1.0s) clearance.
4. **Green Wave Coordination:** While holding green, re-estimate arrival based on live vehicle velocity and dispatch `GreenWavePrepare` downstream to prime the next junction.
5. **Ambulance Passage:** When `PassedNotice` is received (vehicle cleared stop bar), hold green for an additional $3.0\text{ s}$ buffer, then release.
6. **Equitable Recovery:** Shift override to `_starved_phase`. Hold green for:
   $$t_{\text{recovery}} = \text{recovery\_s} + \min(\text{delay\_suffered}, \text{recovery\_s})$$
   Release override and return to `NORMAL` cycle.
7. **Fail-Safe Timeout:** If bus silence exceeds `bus_silence_timeout_ticks` (15s) while holding green, abort preemption lock and force recovery.

### 3.5 Configuration Parameters
- `window_s = 25`: Lookahead preemption planning horizon (seconds).
- `min_green_for_cross_s = 8`: Guaranteed minimum cross-traffic green before preemption override.
- `queue_flush_threshold = 12`: Queue count triggering proactive `PRE_CLEAR` flushing.
- `recovery_s = 20`: Base recovery green duration (seconds).
- `max_preemption_hold_s = 45`: Hard limit capping consecutive preemption green time.
- `bus_silence_timeout_ticks = 15`: Fail-safe bus silence threshold (seconds).

### 3.6 Failure Modes & Edge Cases
- **Overlong Preemption Lock:** Enforces hard cap at 45.0s, dropping override into recovery even if ambulance has not arrived.
- **Downstream Rejection:** If downstream junction Nacks, rollback notice propagates upstream to cancel tentative reservations.

### 3.7 Implementation References
- **File:** [clearpath/agents/junction.py](file:///a:/CLEARPATH/clearpath/agents/junction.py)
- **Key Functions:** `on_message()`, `step()`, `_plan_if_due()`, `_switch_if_allowed()`, `_advance_hold()`, `_enter_recovery()`, `_step_recovery()`.

---

## 4. GuidanceAgent

### 4.1 Purpose & Role
The `GuidanceAgent` monitors vehicle trajectories ahead of the emergency vehicle and synthesizes tactical lane-level driving advisories (e.g., "Clear lane 1", "Pull over to left shoulder") to clear the travel corridor proactively.

### 4.2 Inputs & Outputs
- **Inputs:** Active ambulance location and downstream route sequence from `WorldView`.
- **Outputs:** `GuidanceAdvisory` bus messages directed to civilian vehicle IDs; dynamic Variable Message Sign (VMS) display updates; actuator calls to `apply_yield()`.

### 4.3 Internal State
- `_advisories: Deque[AdvisoryRecord]`: Rolling buffer storing the last 50 generated advisories for dashboard display.
- `_dedup: Dict[_AdvisoryKey, float]`: Deduplication cache tracking emission timestamps per vehicle and instruction template.
- `_vms_boards: Dict[str, str]`: Active directional text displayed on physical intersection signage.

### 4.4 Step-by-Step Algorithm
1. **Lookahead Scanning:** Inspect all vehicles in a $150\text{ m}$ forward window along the ambulance's current and immediate downstream edge.
2. **Vehicle Classification:**
   - Same lane, same edge, distance $\le 80\text{ m}$: *"Clear lane N"* (move to shoulder).
   - Single-lane road ahead: *"Pull over to left shoulder and stop"* (or right shoulder if `drive_left=False`).
   - Approaching cross-street traffic: *"Stop. Do not enter intersection"*.
   - Different lane, distance $80\text{--}150\text{ m}$: *"Slow down, emergency vehicle approaching"*.
3. **Severity Assignment:** Distance $< 50\text{ m} \to \text{CRITICAL}$; $50\text{--}100\text{ m} \to \text{WARN}$; $> 100\text{ m} \to \text{INFO}$.
4. **Deduplication:** Suppress duplicate identical advisories for the same vehicle within `_DEDUP_WINDOW_S` ($5.0\text{ s}$).
5. **Actuator Execution:** Call `actuator.apply_yield(vehicle_id, duration_s=15.0)` to slow the vehicle and simulate driver compliance in simulator physics.
6. **VMS Broadcast:** Update approaching junction signage (e.g., *"EMERGENCY VEHICLE APPROACHING FROM SOUTH - YIELD"*).

### 4.5 Configuration Parameters
- `_LOOKAHEAD_M = 150.0`: Forward detection range.
- `_CLOSE_M = 80.0`: Critical proximity threshold.
- `_DEDUP_WINDOW_S = 5.0`: Advisory deduplication suppression period.
- `_ADVISORY_FEED_SIZE = 50`: Rolling history capacity.

### 4.6 Failure Modes & Edge Cases
- **Vehicles Behind Ambulance:** Automatically ignored to prevent issuing unnecessary braking instructions.
- **Drive-Side Sensitivity:** Respects `drive_left` flag (default True for India/UK conventions) to direct pull-overs to the correct shoulder.

### 4.7 Implementation References
- **File:** [clearpath/agents/guidance.py](file:///a:/CLEARPATH/clearpath/agents/guidance.py)
- **Key Functions:** `step()`, `_inspect_edge()`, `_generate_advisories()`, `_bearing_to_compass()`.

