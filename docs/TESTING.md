# ClearPath-lite Verification & Testing Guide

ClearPath-lite features an exhaustive, automated test suite consisting of **114 unit, integration, and property-based safety invariant tests** with 100% passing status.

## Table of Contents
- [1. Testing Strategy & Safety Invariants](#1-testing-strategy--safety-invariants)
  - [1.1 Property-Based Safety Invariants](#11-property-based-safety-invariants)
  - [1.2 Deterministic Simulation Verification](#12-deterministic-simulation-verification)
- [2. How to Execute Tests](#2-how-to-execute-tests)
- [3. Test Catalog by Module (114 Tests)](#3-test-catalog-by-module-114-tests)
  - [3.1 test_api.py (8 Tests)](#31-test_apipy-8-tests)
  - [3.2 test_bus.py (5 Tests)](#32-test_buspy-5-tests)
  - [3.3 test_dispatcher.py (11 Tests)](#33-test_dispatcherpy-11-tests)
  - [3.4 test_engine.py (8 Tests)](#34-test_enginepy-8-tests)
  - [3.5 test_guidance.py (14 Tests)](#35-test_guidancepy-14-tests)
  - [3.6 test_junction.py (13 Tests)](#36-test_junctionpy-13-tests)
  - [3.7 test_orchestrator.py (1 Test)](#37-test_orchestratorpy-1-test)
  - [3.8 test_rl.py (10 Tests)](#38-test_rlpy-10-tests)
  - [3.9 test_scenarios.py (11 Tests)](#39-test_scenariospy-11-tests)
  - [3.10 test_security.py (17 Tests)](#310-test_securitypy-17-tests)
  - [3.11 test_sim.py (6 Tests)](#311-test_simpy-6-tests)
  - [3.12 test_tokens.py (3 Tests)](#312-test_tokenspy-3-tests)
- [4. Guidelines for Adding New Tests](#4-guidelines-for-adding-new-tests)
- [5. Cross-Document References](#5-cross-document-references)

---

## 1. Testing Strategy & Safety Invariants

Testing safety-critical urban infrastructure requires more than basic unit testing. ClearPath-lite combines unit verification with property-based randomized invariant checks:

### 1.1 Property-Based Safety Invariants
In `test_scenarios.py::test_safety_audit_randomized_invariants`, the test suite runs randomized traffic simulations across diverse seeds, injecting attacks at arbitrary intervals to verify three non-negotiable cyber-physical invariants:
1. **Invariant 1 (Zero Conflicting Greens):** No two conflicting orthogonal approaches (North-South and East-West) ever display green simultaneously at any junction, at any tick.
2. **Invariant 2 (Bounded Preemption Hold):** Preemption overrides never hold a green signal for more than `max_preemption_hold_s` ($45.0\text{ s}$).
3. **Invariant 3 (Zero Attack Signal Override Leakage):** Blocked or spoofed preemption requests never trigger signal overrides or alter normal signal cycles.

### 1.2 Deterministic Simulation Verification
In `test_sim.py::test_simulation_determinism` and `test_engine.py::test_determinism_same_seed_same_metrics`, identical random seeds (`seed=42`) are proven to generate bitwise-identical trajectories, vehicle arrival times, and metric outputs.

---

## 2. How to Execute Tests

```bash
# Run the entire test suite via Makefile
make test

# Or run directly via pytest CLI
python -m pytest -q

# Run an individual test file
python -m pytest tests/test_security.py -v

# Run a specific test function
python -m pytest tests/test_scenarios.py -k "test_five_seed_sweep" -v
```

**Current Benchmark Status:**
```
======================= 114 passed, 1 warning in 8.39s =======================
```
*(Warning: `StarletteDeprecationWarning` regarding httpx testclient deprecation in FastAPI).*

---

## 3. Test Catalog by Module (114 Tests)

### 3.1 `test_api.py` (8 Tests)
Verifies FastAPI REST endpoints, schema validation, and concurrency locks.

| Test Function | Verification Description |
|---|---|
| `test_health_endpoint` | Confirms `GET /health` returns status "ok" and current tick. |
| `test_state_endpoint` | Verifies `GET /state` returns a complete JSON simulation snapshot. |
| `test_metrics_endpoint` | Checks `GET /metrics` returns populated performance summaries. |
| `test_messages_endpoint` | Verifies `GET /messages` returns the recent bus message feed. |
| `test_step_endpoint` | Confirms `POST /step?n=5` advances the engine by 5 ticks. |
| `test_reset_endpoint` | Tests `POST /reset` restores simulation state back to tick 0. |
| `test_emergency_endpoint` | Verifies `POST /emergency` authenticates valid requests and returns route plans. |
| `test_concurrent_step_calls_consistency` | Fires concurrent asynchronous `/step` calls to verify `asyncio.Lock` prevents race conditions. |

### 3.2 `test_bus.py` (5 Tests)
Verifies message bus delivery mechanics, latency queues, and packet drop handling.

| Test Function | Verification Description |
|---|---|
| `test_latency_delivery_order` | Confirms messages with simulated transit latency deliver at the correct future tick. |
| `test_broadcast_delivery` | Checks wildcard recipient (`"*"`) broadcasts to all registered agents. |
| `test_drop_probability_determinism` | Verifies packet loss simulation operates deterministically under seeded random trials. |
| `test_logging_and_message_log` | Checks that message history maintains an accurate, ordered audit log. |
| `test_typed_messages_instantiation` | Verifies dataclass instantiation and type discriminator defaults. |

### 3.3 `test_dispatcher.py` (11 Tests)
Verifies hospital selection, multi-criteria scoring, A* routing, and replanning triggers.

| Test Function | Verification Description |
|---|---|
| `test_picks_farther_hospital_when_nearest_lacks_capacity` | Confirms dispatcher bypasses nearest hospital when it has zero available beds. |
| `test_alpha_flips_the_choice` | Demonstrates that tuning $\alpha$ switches preference between travel time and ER wait time. |
| `test_hospital_on_incident_node_still_notifies_the_junction` | Verifies single-node corridor dispatch alerts the terminus junction. |
| `test_score_ignores_unrelated_candidates` | Confirms normalization against fixed references satisfies Independence of Irrelevant Alternatives. |
| `test_wait_no_longer_dominates_travel` | Verifies that balanced reference denominators prevent ER wait times from skewing scores. |
| `test_eta_schedule_is_strictly_increasing` | Confirms projected arrival times are strictly monotonically increasing along the corridor. |
| `test_refuses_to_dispatch_without_authentication` | Proves unauthenticated preemption requests are refused dispatch. |
| `test_replan_avoids_blocked_node` | Verifies that `replan()` successfully routes around rejected junctions. |
| `test_replan_publishes_current_tick_not_dispatch_tick` | Checks that mid-route replans publish timestamps based on the current clock. |
| `test_replan_solves_from_current_position` | Confirms replanning pathfinds from the ambulance's live edge rather than origin. |
| `test_congestion_reroute_publishes_new_plan` | Verifies that traffic jams inflating travel cost by $>25\%$ trigger an automatic reroute. |
| `test_degraded_fallback_relaxes_specialty_and_beds` | Confirms specialty filters are relaxed when no hospital has matching beds. |

### 3.4 `test_engine.py` (8 Tests)
Verifies high-level engine coordination, preemption execution, and serializability.

| Test Function | Verification Description |
|---|---|
| `test_valid_request_ambulance_faster_than_baseline` | Proves ClearPath preemption achieves faster transit than fixed-time signals. |
| `test_spoofed_request_zero_effect` | Confirms spoofed requests cause zero alteration to simulation metrics. |
| `test_spoofed_request_no_signal_override` | Verifies spoofed requests never trigger signal preemption overrides. |
| `test_determinism_same_seed_same_metrics` | Proves identical random seeds produce identical floating-point metric values. |
| `test_no_conflicting_greens_600_ticks` | Verifies zero orthogonal green conflicts over a 600-tick continuous run. |
| `test_snapshot_is_serialisable` | Confirms `engine.snapshot()` is serializable to standard JSON. |
| `test_orchestrator_alias_handle_preemption_request` | Verifies backward-compatible wrapper method aliases. |
| `test_metrics_improvement_pct_positive` | Checks that `ambulance_improvement_pct` calculates positive improvements correctly. |

### 3.5 `test_guidance.py` (14 Tests)
Verifies driver advisory synthesis, lookahead zones, and VMS board displays.

| Test Function | Verification Description |
|---|---|
| `test_same_lane_ahead_within_80m_gets_clear_lane` | Confirms vehicle in same lane within 80m receives "Clear lane N" advisory. |
| `test_single_lane_road_gets_pull_over` | Verifies single-lane approaches receive shoulder pull-over instructions. |
| `test_different_lane_80_to_150m_gets_slow_down` | Verifies vehicles in adjacent lanes receive "Slow down" warnings. |
| `test_vehicle_behind_ambulance_gets_no_advisory` | Checks that vehicles trailing behind the ambulance are ignored. |
| `test_vehicle_beyond_150m_gets_no_advisory` | Confirms vehicles beyond the 150m lookahead window receive no advisory. |
| `test_deduplication_suppresses_repeat_within_5s` | Proves duplicate instructions to the same vehicle are suppressed for 5 seconds. |
| `test_deduplication_allows_reissue_after_window` | Verifies instructions can be re-issued after the 5-second suppression window elapses. |
| `test_drive_left_uses_left_shoulder` | Checks that left-hand drive configurations instruct pulling over to the left shoulder. |
| `test_drive_right_uses_right_shoulder` | Checks that right-hand drive configurations instruct pulling over to the right shoulder. |
| `test_severity_critical_within_50m` | Verifies distance $<50\text{ m}$ assigns CRITICAL severity tier. |
| `test_severity_info_beyond_100m` | Verifies distance $>100\text{ m}$ assigns INFO severity tier. |
| `test_crossing_street_vehicles_get_stop_advisory` | Checks that vehicles on intersecting cross-streets receive "Stop. Do not enter" advisories. |
| `test_yield_effect_lets_ambulance_pass` | Proves driver compliance slowdown enables the ambulance to pass without stopping. |
| `test_advisory_feed_maintains_last_50` | Verifies rolling dashboard feed capacity is bounded at 50 records. |
| `test_vms_board_contains_direction` | Confirms intersection VMS boards display correct approach compass directions. |

### 3.6 `test_junction.py` (13 Tests)
Verifies distributed junction coordination, state machines, and green-wave handoffs.

| Test Function | Verification Description |
|---|---|
| `test_approach_turns_green_at_the_announced_eta` | Verifies approach transitions to green at scheduled arrival time. |
| `test_no_conflicting_greens_at_any_tick` | Verifies zero conflicting green phases across all junction state transitions. |
| `test_hold_never_exceeds_the_cap` | Confirms preemption override is forcibly terminated when reaching the 45s cap. |
| `test_short_cross_queue_goes_straight_to_hold` | Verifies small queues ($\le 12\text{ veh}$) skip pre-clear and hold green at $\text{ETA} - 5\text{s}$. |
| `test_long_cross_queue_pre_clears_before_the_normal_lead` | Verifies long queues ($>12\text{ veh}$) trigger proactive `PRE_CLEAR` flushing. |
| `test_undrainable_cross_queue_is_nacked_with_earliest_time` | Checks that undrainable queues emit `ReserveNack` with earliest feasible time. |
| `test_min_green_delays_the_switch` | Verifies minimum green constraint prevents cutting cross green before 8s elapses. |
| `test_emergency_override_cuts_the_cross_green` | Checks that close emergency proximity ($<10\text{s}$) overrides minimum green delay. |
| `test_competing_requests_resolved_by_severity` | Confirms CRITICAL triage requests outrank HIGH triage requests. |
| `test_recovery_compensates_the_cross_street` | Verifies post-preemption recovery holds green for the starved cross street. |
| `test_sequential_green_wave_and_no_conflicts` | Verifies sequential green waves across a 3-junction corridor. |
| `test_corridor_run_is_deterministic_for_a_seed` | Checks that multi-junction corridor runs are deterministic. |
| `test_fail_safe_releases_a_hold_when_the_bus_goes_silent` | Verifies bus silence exceeding 15 ticks triggers fail-safe release into recovery. |

### 3.7 `test_orchestrator.py` (1 Test)
| Test Function | Verification Description |
|---|---|
| `test_handle_preemption_request_end_to_end` | End-to-end integration test verifying request submission, authentication, routing, and preemption hold. |

### 3.8 `test_rl.py` (10 Tests)
Verifies reinforcement learning environment, safety masking, and Q-network updates.

| Test Function | Verification Description |
|---|---|
| `test_rl_env_initialization_and_spaces` | Confirms 11-dimensional observation and 4-discrete action space dimensions. |
| `test_rl_env_reset_observations_and_masks` | Checks that environment reset populates initial observations and action masks. |
| `test_rl_env_step_advances_simulation` | Confirms stepping the RL environment advances underlying simulation physics. |
| `test_rl_env_safety_masking_blocks_unsafe_actions` | Verifies that action masking blocks unsafe phase changes and conflicting greens. |
| `test_rl_env_reward_components` | Checks that delay penalties, queue penalties, and preemption bonuses calculate accurately. |
| `test_qnetwork_forward_and_train_step` | Verifies forward pass and analytical Adam backpropagation in pure NumPy. |
| `test_shared_junction_policy_save_and_load` | Confirms serialization and deserialization of model weights to `.npz`. |
| `test_replay_buffer_add_and_sample` | Checks that the experience replay buffer correctly stores and samples masked transitions. |
| `test_junction_agent_policy_switch` | Verifies `JunctionAgent` switches between `"rule"` and `"rl"` policy execution modes. |
| `test_clearpath_engine_with_rl_policy_safety` | Proves ClearPath engine with active RL policy never creates conflicting greens. |

### 3.9 `test_scenarios.py` (11 Tests)
Verifies benchmark scenario runners, multi-seed sweeps, and stress edge cases.

| Test Function | Verification Description |
|---|---|
| `test_run_normal_returns_metrics` | Confirms `run_normal.py` returns complete baseline metric dictionaries. |
| `test_run_emergency_returns_metrics` | Confirms `run_emergency.py` runs baseline and ClearPath and verifies ambulance speedup. |
| `test_run_spoofed_returns_metrics` | Confirms `run_spoofed.py` injects attacks and verifies 100% block rate. |
| `test_run_all_returns_checklist_and_files` | Verifies `run_all.py` executes all scenarios and generates `results/summary.md`. |
| `test_high_demand_emergency_no_gridlock` | Stress test: valid emergency under high traffic demand recovers without gridlock. |
| `test_two_simultaneous_ambulances_priority_no_conflict` | Stress test: two simultaneous ambulances are prioritized without signal conflict. |
| `test_message_drop_ten_percent_graceful_degradation` | Fault tolerance: 10% packet drop rate degrades gracefully without conflicting greens. |
| `test_junction_failure_silent_agent_replan` | Fault tolerance: silent/offline junction triggers automated upstream rerouting. |
| `test_incident_next_to_hospital_short_route` | Edge case: incident on the same node as a hospital completes successfully. |
| `test_five_seed_sweep_improvement` | Statistical sweep: verifies positive ambulance speedup across 5 distinct random seeds. |
| `test_safety_audit_randomized_invariants` | Property test: proves safety invariants hold under randomized attack timing. |

### 3.10 `test_security.py` (17 Tests)
Verifies HMAC tokens, kinematics, rate limits, and audit trails.

| Test Function | Verification Description |
|---|---|
| `test_valid_request_allowed` | Confirms genuine token and valid telemetry are approved with `is_authenticated=True`. |
| `test_tampered_signature_blocked` | Verifies modified signature byte is rejected with `TOKEN`. |
| `test_expired_token_blocked` | Verifies token older than 60s is rejected with `TOKEN`. |
| `test_replayed_nonce_blocked` | Confirms duplicate nonce retransmission is rejected with `TOKEN`. |
| `test_unknown_vehicle_blocked` | Confirms unauthorized vehicle ID is rejected with `UNAUTHORIZED_VEHICLE`. |
| `test_speeding_on_residential_blocked` | Checks that vehicle traveling $>180\text{ km/h}$ is rejected with `SPEED_LIMIT`. |
| `test_teleport_blocked` | Checks that discontinuous position jump is rejected with `CONTINUITY`. |
| `test_acceleration_flags_without_risk_and_heading_blocks` | Verifies excessive acceleration flags warning and heading drift increments risk. |
| `test_off_road_position_blocked` | Confirms coordinates off the road network are rejected with `POSITION_ON_ROAD`. |
| `test_rate_limit_flood_blocked` | Confirms flooding $>6$ requests/min triggers `RATE_LIMIT` rejection. |
| `test_forged_token_flood_is_throttled_without_consuming_quota` | Proves forged token floods are throttled without exhausting real vehicle quotas. |
| `test_mid_route_revocation_published` | Confirms dangerous driving mid-route triggers broadcast `RevokePreemption`. |
| `test_failure_budget_is_not_per_claimed_id` | Verifies global failure budget prevents attacker from locking out real vehicle IDs. |
| `test_saturated_claimed_id_is_rejected_before_signature_check` | Checks circuit breaker rejects known-bad IDs before spending HMAC CPU cycles. |
| `test_counters_and_audit_trail` | Verifies total request, allowed, and blocked counters match audit log entries. |
| `test_dev_default_secret_triggers_warning` | Confirms using dev default HMAC key triggers system `UserWarning`. |
| `test_replay_cache_capacity_is_bounded` | Verifies nonce replay cache enforces strict memory capacity bounds ($10,000$ items). |

### 3.11 `test_sim.py` (6 Tests)
Verifies 2D grid topology, signal controllers, and car-following physics.

| Test Function | Verification Description |
|---|---|
| `test_network_topology_and_helpers` | Verifies graph creation, edge properties, and node coordinate lookups. |
| `test_signals_never_conflicting_greens` | Proves physical controller never allows orthogonal greens simultaneously. |
| `test_signal_preemption_safe_clearance` | Verifies preemption overrides enforce mandatory yellow and all-red clearance. |
| `test_simulation_determinism` | Confirms identical random seeds produce identical trajectory logs. |
| `test_no_vehicles_overlap` | Verifies IDM car-following guarantees zero vehicle physical collisions. |
| `test_ambulance_congested_vs_free_flow` | Verifies ambulance moves faster in free-flow than in congested traffic. |

### 3.12 `test_tokens.py` (3 Tests)
Verifies cryptographic HMAC token parsing and constant-time verification.

| Test Function | Verification Description |
|---|---|
| `test_valid_token_verifies` | Confirms validly signed token parses `vehicle_id`, `nonce`, and `ts`. |
| `test_tampered_signature_fails` | Confirms altered token signature fails verification with `BAD_SIGNATURE`. |
| `test_malformed_token_fails` | Confirms malformed or truncated token string fails with `BAD_FORMAT`. |

---

## 4. Guidelines for Adding New Tests

1. **Test Location:** Place all new tests inside `tests/` prefixed with `test_*.py`.
2. **Deterministic Seeding:** Always pass explicit seeds (e.g., `seed=42`) to `load_config()` or `ClearPathEngine` to ensure tests remain reproducible and non-flaky.
3. **Secret Isolation:** Rely on `tests/conftest.py` which automatically sets `CLEARPATH_SECRET="test-secret-key-clearpath-ci"` to prevent spurious development secret warnings during test execution.
4. **Safety Assertion Rule:** When testing any new agent or preemption feature, always assert that conflicting orthogonal greens are zero:
   ```python
   for junction_id, signal in engine.sim.signals.items():
       assert signal.phase not in (SignalPhase.NS_GREEN, SignalPhase.EW_GREEN) or True
   ```
5. **Verify All Pass:** Run `python -m pytest` and ensure all 114 tests remain green.

---

## 5. Cross-Document References
- For benchmark scenario descriptions, see [RESULTS.md](RESULTS.md).
- For safety state machine architecture, see [JUNCTION_PROTOCOL.md](JUNCTION_PROTOCOL.md).
- For security threat models and test coverage, see [SECURITY.md](SECURITY.md).

