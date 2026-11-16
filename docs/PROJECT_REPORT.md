# ClearPath-lite Technical Engineering Report

A multi-agent, cyber-physically secured architecture for intelligent emergency vehicle preemption, multi-criteria hospital triage, and equitable urban traffic recovery.

## Table of Contents
- [Abstract](#abstract)
- [1. Introduction](#1-introduction)
- [2. Problem Statement](#2-problem-statement)
- [3. Background & Related Work](#3-background--related-work)
  - [3.1 Traditional Emergency Preemption Systems](#31-traditional-emergency-preemption-systems)
  - [3.2 Multi-Agent Traffic Signal Control](#32-multi-agent-traffic-signal-control)
  - [3.3 Cyber-Physical Vulnerabilities in Connected Infrastructure](#33-cyber-physical-vulnerabilities-in-connected-infrastructure)
- [4. Methodology & Architectural Design](#4-methodology--architectural-design)
  - [4.1 Asynchronous Multi-Agent Framework](#41-asynchronous-multi-agent-framework)
  - [4.2 Cryptographic & Kinematic Gatekeeping](#42-cryptographic--kinematic-gatekeeping)
  - [4.3 Multi-Criteria Hospital Triage & Density-Aware Routing](#43-multi-criteria-hospital-triage--density-aware-routing)
  - [4.4 Distributed Green-Wave Negotiation & Controlled Recovery](#44-distributed-green-wave-negotiation--controlled-recovery)
  - [4.5 Tactical Vehicle Guidance & Driver Compliance](#45-tactical-vehicle-guidance--driver-compliance)
- [5. System Implementation](#5-system-implementation)
  - [5.1 Microscopic Physics Simulation (IDM-lite)](#51-microscopic-physics-simulation-idm-lite)
  - [5.2 Signal Actuation & Physical Clearance State Machine](#52-signal-actuation--physical-clearance-state-machine)
  - [5.3 Reinforcement Learning Policy Integration](#53-reinforcement-learning-policy-integration)
- [6. Experimental Evaluation & Results](#6-experimental-evaluation--results)
  - [6.1 Experimental Setup & Environmental Baselines](#61-experimental-setup--environmental-baselines)
  - [6.2 Emergency Preemption Travel Time & Queue Impact](#62-emergency-preemption-travel-time--queue-impact)
  - [6.3 Network Throughput Recovery Analysis](#63-network-throughput-recovery-analysis)
  - [6.4 Cyber-Physical Adversarial Stress Testing](#64-cyber-physical-adversarial-stress-testing)
  - [6.5 Reinforcement Learning Performance Comparison](#65-reinforcement-learning-performance-comparison)
- [7. Discussion & Limitations](#7-discussion--limitations)
- [8. Conclusion & Future Work](#8-conclusion--future-work)
- [9. Cross-Document References](#9-cross-document-references)

---

## Abstract
Urban emergency vehicle preemption systems face an inherent tension between rapid emergency transit, cross-street traffic gridlock, and cyber-physical security. Legacy optical and acoustic preemption mechanisms suffer from late line-of-sight detection, arbitrary signal locking that paralyzes perpendicular arterials, and an absence of cryptographic authentication. This report presents **ClearPath-lite**, an event-driven multi-agent AI system designed to resolve these challenges. ClearPath-lite decouples microscopic traffic physics from strategic decision-making through four specialized autonomous agents: a **SecurityAgent** gating cryptographic HMAC-SHA256 tokens and kinematic telemetry, a **DispatcherAgent** optimizing hospital selection and corridor schedules, distributed **JunctionAgents** negotiating green waves and controlled recovery phases, and a **GuidanceAgent** synthesizing tactical driver lane advisories. Evaluated across 36 intersections, ClearPath reduces ambulance travel time by **$68.5\%$** ($111.0\text{ s} \to 35.0\text{ s}$) with **zero stops**, restores cross-traffic throughput to **$97.7\%$** of baseline within 80 seconds, and intercepts **$100\%$** of injected spoofing attacks without signal disruption.

---

## 1. Introduction
Emergency medical response times are a critical determinant of patient mortality in acute trauma, cardiac arrest, and stroke incidents. In urban environments, traffic congestion and red-light delays account for a substantial portion of transit duration. Although emergency vehicle preemption (EVP) systems have existed for decades, municipal adoption has been hindered by cross-street gridlock, signal desynchronization, and the vulnerability of wireless signals to unauthorized exploitation.

ClearPath-lite addresses these limitations by introducing a decentralized, multi-agent cyber-physical platform that unifies hospital capacity triage, cryptographic authentication, distributed intersection negotiation, and driver guidance.

---

## 2. Problem Statement
The urban emergency transit problem encompasses three interlinked engineering challenges:
1. **The Transit Delay Problem:** Conventional traffic signals operate on fixed-time or localized vehicle-actuated cycles. Approaching ambulances frequently encounter red signals or long queues of civilian vehicles that cannot clear the intersection, causing repeated stops and severe transit delay.
2. **The Cross-Street Starvation Problem:** Uncoordinated preemption forces arbitrary green holds that starve intersecting roads. Stranded vehicles form queues that spill back into upstream junctions, creating gridlock that persists long after the emergency vehicle has cleared.
3. **The Cyber-Physical Security Problem:** Emerging connected vehicle (V2X) and wireless preemption systems transmit signal override requests over radio frequencies. Without rigorous cryptographic verification and kinematic plausibility checks, malicious actors can forge preemption credentials or replay intercepted packets to freeze city intersections.

---

## 3. Background & Related Work

### 3.1 Traditional Emergency Preemption Systems
First-generation EVP systems rely on optical strobes (e.g., infrared emitters pulsing at specific frequencies) or acoustic siren detectors mounted directly on signal mast arms. These systems suffer from line-of-sight obstruction, environmental attenuation (fog, heavy rain), and late detection ranges ($<100\text{ m}$). Second-generation GPS-based radio systems improve detection ranges but traditionally rely on centralized traffic management centers, creating single points of failure and substantial communication latency.

### 3.2 Multi-Agent Traffic Signal Control
Distributed multi-agent systems (MAS) have emerged as a scalable paradigm for urban traffic management. By treating each intersection as an autonomous agent that coordinates with adjacent neighbors, decentralized systems achieve high fault tolerance and computational scalability without requiring global network state centralized in a single server.

### 3.3 Cyber-Physical Vulnerabilities in Connected Infrastructure
With the proliferation of low-cost Software-Defined Radios (SDR), wireless vehicular protocols face severe security threats. Prior research has demonstrated that unauthenticated or weakly authenticated preemption mechanisms can be exploited to execute denial-of-service attacks, manipulate corridor signals, and disrupt emergency services.

---

## 4. Methodology & Architectural Design

### 4.1 Asynchronous Multi-Agent Framework
ClearPath-lite structures intelligence into four decoupled agent roles communicating across an asynchronous `MessageBus`:

```mermaid
flowchart TB
    AMB["Emergency Ambulance"] -->|PreemptionRequest| SEC["SecurityAgent"]
    SEC -->|AuthResult (Approved)| DISP["DispatcherAgent"]
    DISP -->|RoutePlan & EtaNotice| JUNCT["JunctionAgents"]
    DISP -->|RoutePlan| GUID["GuidanceAgent"]
    JUNCT <-->|ReserveCorridor / Ack / Nack| JUNCT
    JUNCT -->|set_signal_override| ACT["Hardware Actuator Interface"]
    GUID -->|GuidanceAdvisory / apply_yield| ACT
```

### 4.2 Cryptographic & Kinematic Gatekeeping
The `SecurityAgent` validates incoming preemption requests through a multi-tiered filter:
- **HMAC-SHA256 Authentication:** Verification of compact credentials (`vehicle_id.nonce.ts.signature`) using constant-time comparisons (`hmac.compare_digest`) to prevent timing side-channel attacks.
- **Single-Use Nonces & TTL:** Sliding-window nonce caching and a 60-second expiration window reject replay attacks.
- **Kinematic Plausibility:** Telemetry validation ensures vehicle velocity respects posted limits ($v \le 1.5 \cdot v_{\text{limit}}$), coordinates project onto physical road segments ($\le 30\text{ m}$), and displacement obeys spatio-temporal continuity bounds.

### 4.3 Multi-Criteria Hospital Triage & Density-Aware Routing
The `DispatcherAgent` selects medical destinations and plans preemption corridors:
- **Triage Cost Formulation:** Normalizes candidate travel times and ER wait times against fixed reference baselines:
  $$\text{Score} = \alpha \cdot \frac{t_{\text{travel}}}{t_{\text{ref\_travel}}} + (1 - \alpha) \cdot \frac{t_{\text{wait}}}{t_{\text{ref\_wait}}}$$
- **Density-Aware Edge Costing:** Traversal costs degrade as edge vehicle densities approach jam density ($k_{\text{jam}} = 80\text{ veh/km/lane}$), adding queuing delay penalties based on approach headways.
- **A* Pathfinding:** Solves optimal paths using an admissible Euclidean distance lower-bound heuristic.

### 4.4 Distributed Green-Wave Negotiation & Controlled Recovery
- **Sequential Corridor Locks:** Intersections coordinate green-wave reservations via `ReserveCorridor` and `ReserveAck` handshakes, locking approach greens 5 seconds prior to arrival.
- **Proactive Pre-Clearing:** Intersections facing large cross-street queues ($>12\text{ veh}$) enter `PRE_CLEAR` ahead of time to flush queued vehicles before the ambulance reaches the block.
- **Compensatory Recovery:** Once the vehicle clears the intersection (`PassedNotice`), the signal switches override to the starved orthogonal approach, holding green for:
  $$t_{\text{recovery}} = \text{recovery\_s} + \min(\text{delay\_suffered}, \, \text{recovery\_s})$$

### 4.5 Tactical Vehicle Guidance & Driver Compliance
The `GuidanceAgent` scans a 150m forward lookahead zone, categorizing civilian vehicles and publishing lane advisories (`GuidanceAdvisory`):
- Same lane within 80m: *"Clear lane N"* (move aside).
- Single-lane road: *"Pull over to left shoulder and stop"*.
- Approaching cross-streets: *"Stop. Do not enter intersection"*.
The actuator applies compliance slowdowns (`apply_yield`) to simulate driver cooperation in microscopic physics.

---

## 5. System Implementation

### 5.1 Microscopic Physics Simulation (IDM-lite)
Implemented in pure Python, the simulator models vehicular longitudinal dynamics via an Intelligent Driver Model (IDM-lite) enforcing minimum bumper gaps ($s_0 = 2.5\text{ m}$), desired time headways ($T = 1.2\text{ s}$), and bounded deceleration profiles ($-6.0\text{ m/s}^2 \le a \le a_{\max}$).

### 5.2 Signal Actuation & Physical Clearance State Machine
The `SignalController` enforces a 6-phase state machine with mandatory clearance intervals:
$$\text{NS\_GREEN} \to \text{NS\_YELLOW (3s)} \to \text{ALL\_RED (1s)} \to \text{EW\_GREEN} \dots$$
Hardware actuators guarantee that orthogonal conflicting greens can never illuminate simultaneously under any software state.

### 5.3 Reinforcement Learning Policy Integration
An optional shared deep Q-network (11-input, 64-hidden, 32-hidden, 4-output MLP) trained via vectorized NumPy parameter sharing operates alongside the rule-based heuristics. Action safety masking mathematically prevents the network from taking illegal phase switching actions during training and inference.

---

## 6. Experimental Evaluation & Results

### 6.1 Experimental Setup & Environmental Baselines
Experiments were conducted on a $6 \times 6$ orthogonal Manhattan grid spanning $1.0\text{ km}^2$ (36 intersections, 200m block spacing). Traffic arrival demand followed Poisson distributions across low ($\lambda=0.04$), medium ($\lambda=0.10$), and high ($\lambda=0.20$) intensities.

### 6.2 Emergency Preemption Travel Time & Queue Impact
In the primary emergency scenario (`seed=42`, `demand="med"`), an ambulance traveled from corner `j_0_0` to `Riverside Urgent Care` (`j_2_2`):

| Evaluation Metric | Baseline (Preemption OFF) | ClearPath (Preemption ON) | Performance Impact |
|---|:---:|:---:|:---:|
| **Ambulance Travel Time** | 111.0 s | **35.0 s** | **-68.5% (-76.0 s)** |
| **Ambulance Stops** | 7 | **0** | **-100% (Unbroken Wave)** |
| **Ambulance Stopped Time** | 48.0 s | **0.0 s** | **-100% (-48.0 s)** |
| **Network Maximum Queue** | 13 veh | 13 veh | Identical (0 veh delta) |
| **Recovery Phase Duration** | — | 31.0 s | Controlled queue release |

Parametric evaluation across 5 distinct random seeds (`101, 202, 303, 404, 505`) demonstrated a mean travel time improvement of **$58.51\% \pm 10.45\%$**, with positive speedups observed in $5/5$ seeds ($100\%$).

### 6.3 Network Throughput Recovery Analysis
Post-preemption network throughput evaluated over $[t_{\text{rec}}, t_{\text{rec}} + 60\text{s}]$ reached **$0.344\text{ veh/tick}$** under ClearPath compared to **$0.352\text{ veh/tick}$** in the un-preempted baseline. ClearPath restored **$97.7\%$** of baseline throughput within 80 seconds of ambulance arrival, proving the efficacy of the recovery phase in averting permanent gridlock.

### 6.4 Cyber-Physical Adversarial Stress Testing
The security gateway was subjected to 6 distinct adversarial injection attacks:

| Attack Vector | Category | Result | Diagnostic Reason |
|---|---|:---:|:---:|
| (a) Forged HMAC Signature | Cryptographic | `BLOCKED` | `TOKEN` |
| (b) Expired Token (>60s) | Cryptographic | `BLOCKED` | `TOKEN` |
| [+] Legitimate Ambulance | Legitimate | `ALLOWED` | `none` |
| (c) Nonce Replay Attack | Cryptographic | `BLOCKED` | `TOKEN` |
| (d) 180 km/h Overspeed | Kinematic | `BLOCKED` | `SPEED_LIMIT, CONTINUITY` |
| (e) GPS Teleport (800m leap) | Kinematic | `BLOCKED` | `CONTINUITY` |
| (f) Unauthorized Vehicle ID | Fleet Auth | `BLOCKED` | `UNAUTHORIZED_VEHICLE` |

The security gateway achieved an **Attack Block Rate of 100.0%** ($6/6$), a **False-Positive Rate of 0.0%** ($0/1$), and leaked **exactly 0 signal phase overrides** to the physical traffic network.

### 6.5 Reinforcement Learning Performance Comparison
On a $3 \times 3$ grid benchmark, the trained RL policy achieved an ambulance travel time of **$39.0\text{ s}$** (61.8% improvement vs. baseline) with zero stops, matching and slightly exceeding rule-based preemption ($71.0\text{ s}$, 30.4% improvement) while maintaining zero safety violations.

---

## 7. Discussion & Limitations
While ClearPath-lite establishes strong empirical benchmarks, several physical and architectural simplifications should be noted:
1. **1D Kinematic Coordinates:** Microscopic vehicle following models 1D longitudinal offsets along graph edges without continuous lateral steering dynamics.
2. **In-Process Communication:** The simulated `MessageBus` resides in memory, abstracting physical-layer RF fading and multipath interference.
3. **Symmetric Fleet Secret:** Current preemption tokens utilize a shared HMAC secret. A compromised physical vehicle requires rotating keys across the fleet.

---

## 8. Conclusion & Future Work
ClearPath-lite demonstrates that urban emergency preemption does not require compromising cross-street traffic flow or exposing physical infrastructure to wireless spoofing. By synthesizing cryptographic HMAC gatekeeping, density-aware hospital routing, distributed green-wave coordination, and equitable recovery phases, ClearPath achieves unbroken emergency progression while preserving network equilibrium.

Future work will focus on three key directions:
1. Bridging the message bus to physical hardware controllers via secure MQTT / gRPC protocols.
2. Developing a TraCI co-simulation adapter for high-fidelity Eclipse SUMO integration with real-world OpenStreetMap topologies.
3. Expanding reinforcement learning to continuous multi-agent MAPPO for joint multi-corridor preemption.

---

## 9. Cross-Document References
- For system component diagrams and sequence loops, see [ARCHITECTURE.md](ARCHITECTURE.md).
- For mathematical formulations of all metrics, see [METRICS.md](METRICS.md).
- For complete raw benchmark data tables, see [RESULTS.md](RESULTS.md).

