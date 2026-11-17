# ClearPath-lite Dashboard Operator's Guide

The ClearPath-lite interactive dashboard ([clearpath/dashboard/app.py](file:///a:/CLEARPATH/clearpath/dashboard/app.py)) provides a real-time web interface built with Streamlit and Plotly for visualizing microscopic vehicle dynamics, signal states, security gateway decisions, and hospital triage routing.

## Table of Contents
- [1. Launching the Dashboard](#1-launching-the-dashboard)
- [2. Visual Layout & Panes](#2-visual-layout--panes)
  - [2.1 Sidebar Controls](#21-sidebar-controls)
  - [2.2 2D Interactive Road Network Map](#22-2d-interactive-road-network-map)
  - [2.3 Reading Traffic Signal Indicators](#23-reading-traffic-signal-indicators)
  - [2.4 Security Status Banner & Verdict Block](#24-security-status-banner--verdict-block)
  - [2.5 Real-Time KPI Cards](#25-real-time-kpi-cards)
- [3. Tabbed Diagnostic Inspectors](#3-tabbed-diagnostic-inspectors)
  - [3.1 Event Bus Feed](#31-event-bus-feed)
  - [3.2 Junction States](#32-junction-states)
  - [3.3 Security Audit Log](#33-security-audit-log)
  - [3.4 Hospital Database & Triage](#34-hospital-database--triage)
  - [3.5 Route ETA Corridor Schedule](#35-route-eta-corridor-schedule)
  - [3.6 Guidance & Tactical Advisories](#36-guidance--tactical-advisories)
- [4. Step-by-Step Scenario Reproduction](#4-step-by-step-scenario-reproduction)
  - [4.1 Scenario 1: Normal Traffic Baseline](#41-scenario-1-normal-traffic-baseline)
  - [4.2 Scenario 2: Valid Emergency Preemption](#42-scenario-2-valid-emergency-preemption)
  - [4.3 Scenario 3: Cyber-Physical Attack Injection](#43-scenario-3-cyber-physical-attack-injection)
- [5. Cross-Document References](#5-cross-document-references)

---

## 1. Launching the Dashboard

Launch the Streamlit app from the repository root:
```bash
# Recommended multi-page entry point
streamlit run streamlit_app.py

# Or backwards-compatible CLI
python -m streamlit run clearpath/dashboard/app.py
```
By default, the server listens at `http://localhost:8501`.

![Dashboard Overview](images/overview_grid.png)

---

## 2. Visual Layout & Panes

### 2.1 Sidebar Controls
The left sidebar configures the simulation environment:
- **Scenario Selector:** Choose between:
  - `"Normal traffic"`: Autonomous signal cycling with civilian vehicles only.
  - `"Valid emergency"`: Spawns an authenticated ambulance at `j_0_0` requesting a preemption corridor.
  - `"Spoofed request"`: Injects an adversarial attack into the security gateway.
- **Incident Type:** Select medical category (`cardiac`, `trauma`, `general`) to test hospital specialty matching.
- **Traffic Demand:** Select Poisson arrival rate (`low`, `med`, `high`).
- **Preemption Toggle:** Enable or disable ClearPath preemption (`ON` = multi-agent green wave, `OFF` = fixed-time baseline).
- **Junction Policy Switch:** Switch between `Rule-based` heuristics and `Reinforcement Learning (RL)` policy.
- **Simulation Controls:**
  - `▶ Start` / `⏸ Pause`: Run or pause continuous simulation animation loop.
  - `Step (1 tick)`: Manually step forward by exactly 1 tick.
  - `↺ Reset`: Re-initialize simulation state, clear vehicle inventories, and reset metrics.

### 2.2 2D Interactive Road Network Map
Rendered with Plotly, the main canvas displays 10 synchronized visual layers:
- **Road Segments:** Slate-colored road lines showing arterials (2 lanes) and residential streets (1 lane).
- **Junction Nodes:** Gray intersection hubs labeled with node identifiers (`j_0_0` to `j_5_5`).
- **Hospital Markers:** Distinct cyan diamond markers displaying hospital names, bed counts, and current ER wait times.
- **Civilian Vehicles:** Circular markers colored by speed (blue = free-flow, gray = queued/stopped).
- **Emergency Ambulance:** High-visibility gold star marker (`#ffc107`, size 16) displaying ID and live speed.
- **Active Preemption Corridor:** A thick orange polyline overlay (`#f0883e`, width 6) connecting scheduled corridor nodes.
- **Preemption Rings:** Pulsing halo rings around junctions with active preemption locks.

![Emergency Corridor Map](images/emergency_corridor.png)

### 2.3 Reading Traffic Signal Indicators
At each intersection approach, small circular indicators display live signal phases:
- <span style="color:#3fb950;font-weight:bold;">● Green (`#3fb950`)</span>: Right-of-way granted. Vehicles accelerate toward desired speed.
- <span style="color:#d29922;font-weight:bold;">● Yellow (`#d29922`)</span>: Transition phase ($3.0\text{ s}$). Approaching vehicles stop if safe.
- <span style="color:#f85149;font-weight:bold;">● Red (`#f85149`)</span>: Stop line locked ($1.0\text{ s}$ all-red clearance, or cross-phase green). Vehicles must stop.

### 2.4 Security Status Banner & Verdict Block
When an emergency or spoofed request is evaluated, a high-contrast banner appears at the top of the dashboard:
- **Allowed:**
  ```html
  <div class="verdict-block" style="background:#1f3d24; border-left:4px solid #3fb950;">
    ✅ ALLOWED | Vehicle: AMB_1 | Destination: Riverside Urgent Care
  </div>
  ```
- **Blocked:**
  ```html
  <div class="verdict-block" style="background:#3d1f1f; border-left:4px solid #f85149;">
    🚫 BLOCKED | Attack: Bad Signature<br>
    <small>Risk: 0.00 | Reasons: TOKEN</small>
  </div>
  ```

![Security Alert Banner](images/security_blocked_banner.png)

### 2.5 Real-Time KPI Cards
A 5-column metric row summarizes live operational performance:

![KPI Metrics Row](images/kpi_metrics_row.png)

1. **Ambulance Transit:** Total elapsed travel time to destination (seconds), with green delta vs. baseline.
2. **Cross-Traffic Delay:** Network-wide civilian vehicle delay incurred during preemption (seconds).
3. **Attack Block Rate:** Cumulative percentage of spoofed requests blocked by the security gateway ($100.0\%$).
4. **False-Positive Rate:** Percentage of legitimate requests improperly rejected ($0.0\%$).
5. **Ambulance Stops:** Total number of full stops ($v < 0.1\text{ m/s}$) suffered by the ambulance ($0$ under ClearPath).

---

## 3. Tabbed Diagnostic Inspectors

The right-hand column features 6 tabbed panels for deep system inspection:

### 3.1 Event Bus Feed
Displays a rolling table of the last 30 bus events with message ID, timestamp, sender, recipient, and message type discriminator (`PreemptionRequest`, `RoutePlan`, `ReserveCorridor`, `PassedNotice`, etc.).

### 3.2 Junction States
A 36-row live table detailing every intersection's state machine status (`NORMAL`, `PRE_CLEAR`, `HOLD_GREEN`, `RECOVERY`), active override reason, and current phase.

### 3.3 Security Audit Log
Chronological security audit trail recording every request evaluated, authentication verdict (`ALLOW` / `BLOCK`), risk score, and failure reason codes (`TOKEN`, `SPEED_LIMIT`, `CONTINUITY`, `UNAUTHORIZED_VEHICLE`).

### 3.4 Hospital Database & Triage
Displays regional medical facilities, specialty units (Cardiac, Trauma, General), live bed counts, and calculated multi-criteria scores for the active incident.

![Hospital Triage Tab](images/hospital_triage_tab.png)

### 3.5 Route ETA Corridor Schedule
Shows the selected path nodes, expected per-junction arrival times, and planned speed limits along the corridor.

### 3.6 Guidance & Tactical Advisories
Displays the rolling feed of tactical advisories issued to drivers within the 150m forward lookahead zone, including advisory text ("Clear lane 0", "Slow down"), severity tags (`CRITICAL`, `WARN`, `INFO`), and live VMS board text.

![Guidance Feed Tab](images/guidance_feed_tab.png)

---

## 4. Step-by-Step Scenario Reproduction

### 4.1 Scenario 1: Normal Traffic Baseline
1. In the sidebar, select **Scenario: "Normal traffic"**.
2. Select **Demand: "med"**.
3. Click `▶ Start` to advance the simulation.
4. **Observe:** Signals cycle autonomously between North-South and East-West every 30 seconds. Preempted signal count remains `0`.

### 4.2 Scenario 2: Valid Emergency Preemption
1. In the sidebar, select **Scenario: "Valid emergency"**.
2. Set **Incident Type: "cardiac"** and **Preemption: "ON"**.
3. Click `🚨 Request Preemption`.
4. **Observe:**
   - Security banner indicates `✅ ALLOWED`.
   - Dispatcher selects `Riverside Urgent Care` (`j_2_2`) based on bed availability.
   - Orange route polyline illuminates across `j_0_0 -> j_1_0 -> j_2_0 -> j_2_1 -> j_2_2`.
   - Signals along the route transition to green 5 seconds before the ambulance arrives.
   - Ambulance reaches hospital in **35.0 seconds with 0 stops** (compared to 111.0s and 7 stops with preemption OFF).
   - Signals enter `RECOVERY`, clearing cross-traffic queues.

### 4.3 Scenario 3: Cyber-Physical Attack Injection
1. In the sidebar, select **Scenario: "Spoofed request"**.
2. Choose an attack vector from the dropdown (e.g., `180 km/h Overspeed` or `Bad Signature`).
3. Click `🚨 Inject Attack`.
4. **Observe:**
   - Security banner turns red displaying `🚫 BLOCKED`.
   - Reason codes display `SPEED_LIMIT,CONTINUITY` or `TOKEN`.
   - The map route overlay remains empty.
   - Traffic signals continue normal cycling without interruption (`0 signal overrides`).

---

## 5. Cross-Document References
- For scripted talking points and presenter instructions, see [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
- For REST API alternatives to the UI, see [API.md](API.md).
- For metric formulas and calculation definitions, see [METRICS.md](METRICS.md).

