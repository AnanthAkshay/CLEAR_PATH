# ClearPath-lite Dispatcher Routing & Triage Algorithm

The `DispatcherAgent` algorithm balances real-time urban traffic dynamics, physical road topologies, and hospital emergency room capacity to select the optimal destination and compute a preemption corridor timeline.

## Table of Contents
- [1. Multi-Criteria Hospital Triage Scoring](#1-multi-criteria-hospital-triage-scoring)
  - [1.1 Mathematical Formulation](#11-mathematical-formulation)
  - [1.2 Reference Normalization Principle](#12-reference-normalization-principle)
- [2. Density-Aware Edge Cost Model](#2-density-aware-edge-cost-model)
  - [2.1 Velocity Degradation Function](#21-velocity-degradation-function)
  - [2.2 Queue Delay & Headway Formulation](#22-queue-delay--headway-formulation)
- [3. A* Pathfinding Heuristic](#3-a-pathfinding-heuristic)
- [4. Degraded Mode & Specialty Fallback](#4-degraded-mode--specialty-fallback)
- [5. Preemption Corridor ETA Timeline Generation](#5-preemption-corridor-eta-timeline-generation)
- [6. Dynamic Replanning Triggers](#6-dynamic-replanning-triggers)
- [7. Worked Numeric Example from Simulation](#7-worked-numeric-example-from-simulation)
- [8. Cross-Document References](#8-cross-document-references)

---

## 1. Multi-Criteria Hospital Triage Scoring

### 1.1 Mathematical Formulation
Selecting an emergency medical destination based purely on geographic distance can be fatal if the nearest hospital has zero ICU beds or a 2-hour emergency room triage backlog. ClearPath scores each candidate hospital $h$ using a composite cost function:

$$\text{Score}(h) = \alpha \cdot \left(\frac{t_{\text{travel}}(h)}{t_{\text{ref\_travel}}}\right) + (1 - \alpha) \cdot \left(\frac{t_{\text{wait}}(h)}{t_{\text{ref\_wait}}}\right)$$

Where:
- $t_{\text{travel}}(h)$: Predicted road network travel duration from the incident node to hospital node $h$ in seconds, derived from the density-aware cost model.
- $t_{\text{wait}}(h)$: Real-time estimated emergency department waiting time in seconds ($\text{avg\_wait\_time\_min} \times 60.0$).
- $t_{\text{ref\_travel}}$: Reference travel normalization constant ($120.0\text{ s}$ by default in `SimConfig.reference_travel_s`).
- $t_{\text{ref\_wait}}$: Reference waiting normalization constant ($1800.0\text{ s}$, or 30 minutes, in `SimConfig.reference_wait_s`).
- $\alpha$: Weighting parameter ($0.7$ by default in `SimConfig.alpha`), prioritizing rapid physical transit while maintaining significant sensitivity to ER wait times.

Scores are cost-like (lower is better). The candidate with the minimal composite score is selected as the destination.

### 1.2 Reference Normalization Principle
Unlike min-max normalization schemes where candidates are scaled relative to the current candidate set's $\min$ and $\max$, ClearPath normalizes against fixed external reference values ($t_{\text{ref\_travel}}$ and $t_{\text{ref\_wait}}$). This guarantees **Independence of Irrelevant Alternatives (IIA)**:
- A hospital's score depends solely on its own travel time and wait time.
- Adding or removing an unrelated hospital candidate does not alter the relative score or ranking order of other candidates.
- Scores remain directly comparable across different simulation runs and geographic areas.

---

## 2. Density-Aware Edge Cost Model

Every directed edge $e=(u, v)$ in the NetworkX road graph is assigned a dynamic traversal cost $t_{\text{edge}}$ representing expected transit time in seconds:

$$t_{\text{edge}} = \frac{L}{v_{\text{eff}}} + t_{\text{queue}}$$

### 2.1 Velocity Degradation Function
The effective velocity $v_{\text{eff}}$ degrades linearly as vehicular density increases toward the jam density $k_{\text{jam}}$:

$$v_{\text{eff}} = \max\left(v_{\min}, \, v_{\text{limit}} \cdot (1 - \rho)\right)$$

Where:
- $L$: Physical length of the road segment in meters (`length_m = 200.0m`).
- $v_{\text{limit}}$: Posted speed limit ($16.7\text{ m/s}$ on arterials, $11.1\text{ m/s}$ on residential roads).
- $v_{\min}$: Minimum speed floor ($2.0\text{ m/s}$ in `SimConfig.min_speed_mps`) to prevent division by zero in gridlock.
- $\rho$: Dimensionless density factor bounded in $[0.0, 1.0]$:
  $$\rho = \min\left(1.0, \, \max\left(0.0, \, \frac{k_{\text{live}}}{k_{\text{jam}}}\right)\right)$$
- $k_{\text{live}}$: Live density reported by `WorldView` in vehicles per kilometer.
- $k_{\text{jam}}$: Physical jam density capacity of the road:
  $$k_{\text{jam}} = \frac{\text{lanes} \cdot 1000.0}{L_{\text{veh}} + d_{\text{gap}}}$$
  With standard vehicle length $L_{\text{veh}} = 7.5\text{ m}$ and average bumper gap $d_{\text{gap}} = 5.0\text{ m}$, spacing is $12.5\text{ m}$, yielding $k_{\text{jam}} = 80.0\text{ veh/km/lane}$.

### 2.2 Queue Delay & Headway Formulation
If vehicles are queued at the downstream intersection stop bar, an additive queue clearance penalty is incurred:

$$t_{\text{queue}} = Q_{\text{len}} \cdot h_{\text{headway}}$$

Where:
- $Q_{\text{len}}$: Number of stationary vehicles queued on the approach.
- $h_{\text{headway}}$: Average time headway needed for one queued vehicle to advance:
  $$h_{\text{headway}} = \frac{L_{\text{veh}} + d_{\text{gap}}}{v_{\text{eff}}}$$

---

## 3. A* Pathfinding Heuristic

Paths between the emergency incident origin and candidate hospital nodes are computed using A* search (`nx.astar_path`) weighted by the live edge costs $t_{\text{edge}}$.

To guarantee optimal and admissible pathfinding, the heuristic function $h(u, v)$ estimates the lower-bound remaining travel time between junction nodes $u$ and $v$:

$$h(u, v) = \frac{\sqrt{(x_v - x_u)^2 + (y_v - y_u)^2}}{v_{\text{amb\_max}}}$$

Where:
- The numerator is the straight-line Euclidean distance between intersection coordinates $(x, y)$.
- $v_{\text{amb\_max}}$ is the physical top speed of an emergency vehicle ($25.0\text{ m/s}$).

**Admissibility Proof:** Because no vehicle in the simulation can exceed $v_{\text{amb\_max}}$, and the shortest possible physical distance between two points in 2D Euclidean space is the straight-line distance, $h(u, v) \le t_{\text{actual}}(u, v)$ for all nodes $u, v$. The heuristic never overestimates the true travel time, guaranteeing that A* finds the strictly optimal path.

---

## 4. Degraded Mode & Specialty Fallback

When a preemption request is received for a specialized incident (e.g., `incident_type = "cardiac"` or `"trauma"`), candidate hospitals are evaluated against two strict filters:
1. **Specialty Match:** The hospital's `specialties` list must contain the requested incident type.
2. **Bed Availability:** The specific departmental bed count `available_beds_by_unit[incident_type]` must be $> 0$.

### Degraded Fallback Logic
If zero hospitals satisfy both constraints (e.g., all cardiac beds are full across the city):
1. `degraded` flag is set to `True`.
2. Specialty filters are relaxed.
3. Candidate bed counts are recalculated as the sum of **all available beds across all units**:
   $$\text{Beds}_{\text{relaxed}} = \sum \text{available\_beds\_by\_unit.values}()$$
4. All hospitals with $\text{Beds}_{\text{relaxed}} > 0$ are ranked using the standard scoring formula.
5. The dispatcher routes to the best overall facility, preventing the ambulance from being stranded without a destination.

---

## 5. Preemption Corridor ETA Timeline Generation

Once the optimal path $[u_0, u_1, \dots, u_k]$ is selected, the dispatcher generates an estimated arrival timeline at each intersection.

Because the corridor will be preempted (signals cleared to green ahead of the vehicle), progression does not suffer red-light delays or normal traffic drag. Expected velocity along preemption edges is modeled as:

$$v_{\text{corridor}} = \min\left(0.8 \cdot v_{\text{amb\_max}}, \, 1.3 \cdot v_{\text{limit}}\right)$$

For arterial roads ($v_{\text{limit}} = 16.7\text{ m/s}$), $v_{\text{corridor}} = \min(20.0, 21.71) = 20.0\text{ m/s}$.  
For residential roads ($v_{\text{limit}} = 11.1\text{ m/s}$), $v_{\text{corridor}} = \min(20.0, 14.43) = 14.43\text{ m/s}$.

The schedule is computed cumulatively:
- $\text{ETA}(u_0) = 0.0\text{ s}$
- $\text{ETA}(u_i) = \text{ETA}(u_{i-1}) + \frac{L_{(u_{i-1}, u_i)}}{v_{\text{corridor}}}$

These values are populated into the `RoutePlan.eta_by_junction` dictionary and dispatched in individual `EtaNotice` messages.

---

## 6. Dynamic Replanning Triggers

The dispatcher maintains active corridor monitoring throughout transit:

1. **Congestion Reroute (`reroute_if_congested`):**
   Every 5 simulation ticks (`_REROUTE_EVERY_TICKS = 5`), the dispatcher re-evaluates the active corridor's remaining cost against live world traffic. If traffic jams or accidents inflate the remaining travel cost by more than $25\%$ ($\text{Cost}_{\text{live}} > 1.25 \cdot \text{Cost}_{\text{initial}}$), an automated re-route is triggered from the ambulance's current position.
2. **Junction Rejection Rollback (`replan`):**
   If a downstream junction rejects reservation via `ReserveNack` (due to an undrainable cross queue), the dispatcher executes `replan(vehicle_id, blocked_nodes={rejected_node})`, finding the next best path that bypasses the congested intersection.
3. **Revocation Drop:**
   If a `RevokePreemption` message is received, the session is removed from `_auth`, and no further route updates are published.

---

## 7. Worked Numeric Example from Simulation

The following data is extracted directly from an actual simulation run of ClearPath-lite (`seed=42`, incident origin at node `j_0_0`, incident type `cardiac`):

### Candidate Hospital Triage Ranking:

| Hospital ID | Facility Name | Node | Beds | $t_{\text{travel}}$ | $t_{\text{wait}}$ | Travel Ratio ($\frac{t}{120}$) | Wait Ratio ($\frac{t}{1800}$) | Composite Score | Rank |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `HOSP_RIVERSIDE` | Riverside Urgent Care | `j_2_2` | 6 | **59.99 s** | **720.0 s** (12 min) | $0.4999$ | $0.4000$ | **0.4699** | **1 (Selected)** |
| `HOSP_WEST` | Westside Community Clinic | `j_5_0` | 8 | 59.88 s | 1500.0 s (25 min) | $0.4990$ | $0.8333$ | 0.5993 | 2 |
| `HOSP_CENTRAL` | Central Memorial Hospital | `j_0_5` | 14 | 59.88 s | 2700.0 s (45 min) | $0.4990$ | $1.5000$ | 0.7993 | 3 |
| `HOSP_NORTH` | North General Hospital | `j_5_5` | 2 | 131.84 s | 1200.0 s (20 min) | $1.0987$ | $0.6667$ | 0.9691 | 4 |

### Score Calculation Breakdown for `HOSP_RIVERSIDE`:
$$\text{Score} = 0.7 \cdot \left(\frac{59.99}{120.0}\right) + 0.3 \cdot \left(\frac{720.0}{1800.0}\right) = 0.7 \cdot 0.4999 + 0.3 \cdot 0.4000 = 0.3499 + 0.1200 = \mathbf{0.4699}$$

Notice that `HOSP_WEST` and `HOSP_CENTRAL` were physically closer in road travel time ($59.88\text{ s}$ vs. $59.99\text{ s}$), but their long ER waiting backlogs ($25\text{ min}$ and $45\text{ min}$) gave them inferior overall scores ($0.5993$ and $0.7993$). The algorithm correctly selected Riverside Urgent Care.

### Scheduled Corridor Timeline:
- Selected Path: `['j_0_0', 'j_0_1', 'j_0_2', 'j_1_2', 'j_2_2']`
- Preemption Corridor Speed: Arterial $20.0\text{ m/s}$, Residential $14.43\text{ m/s}$
- **`j_0_0`**: $t = 0.00\text{ s}$
- **`j_0_1`**: $t = 10.00\text{ s}$
- **`j_0_2`**: $t = 20.00\text{ s}$
- **`j_1_2`**: $t = 33.86\text{ s}$
- **`j_2_2`**: $t = 47.72\text{ s}$
- Total Scheduled ETA: **$47.72\text{ s}$**

---

## 8. Cross-Document References
- For message schemas and bus propagation, see [MESSAGE_PROTOCOL.md](MESSAGE_PROTOCOL.md).
- For junction preemption response to `EtaNotice`, see [JUNCTION_PROTOCOL.md](JUNCTION_PROTOCOL.md).
- For complete empirical scenario benchmarks, see [RESULTS.md](RESULTS.md).

