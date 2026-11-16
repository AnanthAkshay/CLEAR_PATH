# ClearPath-lite Pitch Deck & Presentation Guide

A structured 6-slide presentation outline designed for technical hackathon judges, municipal traffic authorities, and engineering evaluators.

## Table of Contents
- [Slide 1: The Urban Emergency Dilemma](#slide-1-the-urban-emergency-dilemma)
- [Slide 2: The ClearPath-lite Solution](#slide-2-the-clearpath-lite-solution)
- [Slide 3: Multi-Agent System Architecture](#slide-3-multi-agent-system-architecture)
- [Slide 4: Zero-Trust Cyber-Physical Security](#slide-4-zero-trust-cyber-physical-security)
- [Slide 5: Empirical Benchmark Results](#slide-5-empirical-benchmark-results)
- [Slide 6: Scalability & Future Roadmap](#slide-6-scalability--future-roadmap)
- [Cross-Document References](#cross-document-references)

---

### Slide 1: The Urban Emergency Dilemma

```
+--------------------------------------------------------------------------+
|  THE URBAN EMERGENCY DILEMMA                                             |
|                                                                          |
|  * 1-Minute Delay = 7-10% Drop in Cardiac Survival Rates                 |
|                                                                          |
|  Current Emergency Vehicle Preemption (EVP) Suffers Three Fatal Flaws:   |
|  1. Optical/Strobe Sensors Detect Late (<80m): Ambulances still brake    |
|  2. Cross-Street Gridlock: Indefinite green holds paralyze intersecting  |
|     arterials for miles, taking hours to dissolve                        |
|  3. Zero Authentication: Unencrypted radio triggers can be trivially   |
|     spoofed using $30 Software-Defined Radios (SDR)                      |
+--------------------------------------------------------------------------+
```

#### Speaker Notes:
> *"Good morning, judges. In medical emergencies, minutes mean lives—every 60-second delay in cardiac transit reduces patient survival by 7 to 10 percent. Yet across global cities, emergency preemption is broken. Optical strobes and siren sensors only see ambulances when they are already at the intersection, forcing emergency vehicles to brake and wait. When preemption does activate, signals hold arbitrarily, stranding cross-traffic for miles. And worst of all, these systems lack authentication—modern SDRs can trivially clone preemption triggers and freeze city signals. We built ClearPath to solve all three."*

---

### Slide 2: The ClearPath-lite Solution

```
+--------------------------------------------------------------------------+
|  THE CLEARPATH-LITE SOLUTION                                             |
|                                                                          |
|  An Intelligent, Cryptographically Secure, Multi-Agent Traffic Platform  |
|                                                                          |
|  [+] Lookahead Green Waves: Opens synchronized green corridors 25s ahead |
|  [+] Equitable Recovery: Proportional post-preemption green splits      |
|      restore 97.7% baseline throughput within 80 seconds                 |
|  [+] Zero-Trust Defense: Constant-time HMAC-SHA256 tokens + kinematic    |
|      validation block 100% of spoofed attacks with zero overrides        |
|  [+] Multi-Criteria Triage: Real-time routing balances road travel       |
|      times against live hospital bed capacity and ER wait backlogs       |
+--------------------------------------------------------------------------+
```

#### Speaker Notes:
> *"ClearPath-lite is an open-source, multi-agent AI system for intelligent emergency preemption and urban traffic recovery. Instead of reacting at the stop line, ClearPath plans 25 seconds ahead, opening continuous green waves while providing tactical lane-clearing advisories to drivers. Crucially, ClearPath treats the city as an interconnected ecosystem: as soon as the ambulance passes, intersections execute controlled recovery phases, restoring 97.7% of normal throughput within 80 seconds. It is fast for the ambulance, fair for the city, and bulletproof against attacks."*

---

### Slide 3: Multi-Agent System Architecture

```
+--------------------------------------------------------------------------+
|  DECOUPLED MULTI-AGENT ARCHITECTURE                                      |
|                                                                          |
|            [ Emergency Vehicle (HMAC Token + Telemetry) ]                |
|                                 |                                        |
|                                 v                                        |
|      +----------------------------------------------------+              |
|      |               SECURITY GATEWAY AGENT               |              |
|      |    (Constant-Time HMAC, Nonces, Kinematic Gating)  |              |
|      +----------------------------------------------------+              |
|                                 |                                        |
|                                 v (Authenticated Session)                |
|      +----------------------------------------------------+              |
|      |                 DISPATCHER AGENT                   |              |
|      |   (Hospital Triage Ranking + Density-Aware A*)     |              |
|      +----------------------------------------------------+              |
|                       /                  \                               |
|                      v                    v                              |
|   +-----------------------+     +-----------------------+                |
|   |   JUNCTION AGENTS     |     |    GUIDANCE AGENT     |                |
|   | Distributed Handshake |     | Dynamic VMS Boards &  |                |
|   | & Starvation Recovery |     | Lane Yield Advisories |                |
|   +-----------------------+     +-----------------------+                |
|              |                             |                             |
|              +--------------+--------------+                             |
|                             | (Actuation)                                |
|                             v                                            |
|   [ Physical Signal Clearance (Yellow + All-Red) & Microscopic Simulator] |
+--------------------------------------------------------------------------+
```

#### Speaker Notes:
> *"ClearPath is built on four specialized autonomous agents communicating through an asynchronous message bus. The SecurityAgent authenticates cryptographic tokens and kinematic plausibility before allowing requests into the network. The DispatcherAgent evaluates live road densities and regional hospital bed capacities to choose the optimal hospital and compute arrival timelines. Distributed JunctionAgents negotiate sequential corridor locks and execute recovery cycles. And our GuidanceAgent scans 150m ahead to synthesize tactical driver advisories. Notice that agents never touch hardware lamps directly—actuators physically enforce mandatory yellow and all-red clearance intervals."*

---

### Slide 4: Zero-Trust Cyber-Physical Security

```
+--------------------------------------------------------------------------+
|  ZERO-TRUST CYBER-PHYSICAL SECURITY                                      |
|                                                                          |
|  Attack Vector                  Defense Mechanism          Result        |
|  ----------------------------------------------------------------------  |
|  Forged Signature Byte          Constant-Time HMAC-SHA256  BLOCKED       |
|  Expired Replay Token (>60s)    Sliding-Window TTL         BLOCKED       |
|  Nonce Retransmission           Single-Use Nonce Cache     BLOCKED       |
|  180 km/h Telemetry Overspeed   Physical Velocity Bounds   BLOCKED       |
|  Discontinuous GPS Teleport     Spatio-Temporal Continuity BLOCKED       |
|  Unauthorized Fleet ID          Fleet Authorization Check  BLOCKED       |
|                                                                          |
|  [BENCHMARK] 6/6 Attacks Blocked (100%) | 0 Signal Overrides Leaked      |
+--------------------------------------------------------------------------+
```

#### Speaker Notes:
> *"Because traffic preemption can override municipal infrastructure, security cannot be an afterthought. We evaluated six distinct cyber-physical attack vectors in sequence: signature tampering, expired tokens, nonce replays, 180 km/h overspeeding, GPS teleports, and unauthorized fleet IDs. Our gateway achieved a 100% attack block rate and a 0.0% false-positive rate, with zero signal override leakage to the traffic network. Stolen keys cannot fake physics, and replay attacks cannot bypass our nonces."*

---

### Slide 5: Empirical Benchmark Results

```
+--------------------------------------------------------------------------+
|  EMPIRICAL BENCHMARK RESULTS (Seed=42, Demand=Med)                      |
|                                                                          |
|  Metric                     Baseline       ClearPath      Delta          |
|  ----------------------------------------------------------------------  |
|  Ambulance Travel Time      111.0 s        35.0 s         -68.5% FASTER  |
|  Ambulance Stops            7 stops        0 stops        -100% UNBROKEN |
|  Ambulance Stopped Time     48.0 s         0.0 s          -48.0 s        |
|  Cross-Traffic Recovery     —              97.7% Ratio    NO GRIDLOCK    |
|  5-Seed Sweep Mean Speedup  —              58.51%         +/- 10.45%     |
|  Safety Invariant Proof     114 Tests      114 Passed     ZERO CONFLICTS |
+--------------------------------------------------------------------------+
```

#### Speaker Notes:
> *"Let's examine the empirical benchmark numbers. In an emergency run across our 36-junction grid, ClearPath slashed ambulance travel time from 111.0 seconds down to 35.0 seconds—a 68.5% time reduction. Ambulance stops dropped from 7 stops to exactly zero stops. Stopped time dropped from 48 seconds to zero. Within 80 seconds, cross-traffic throughput recovered to 97.7% of the normal baseline. Across a 5-seed parametric sweep, travel time improvements averaged 58.5%. And across all 114 automated tests, zero conflicting greens were ever created."*

---

### Slide 6: Scalability & Future Roadmap

```
+--------------------------------------------------------------------------+
|  DEPLOYMENT READINESS & FUTURE ROADMAP                                   |
|                                                                          |
|  High-Speed Simulation Engine:                                           |
|  * 900 ticks execute in <11 seconds on a CPU laptop                      |
|  * Pure NumPy Reinforcement Learning trains in <3 minutes                |
|                                                                          |
|  Near-Term Engineering Roadmap:                                          |
|  1. MQTT / gRPC Edge Bridge for physical roadside cabinet deployment     |
|  2. Eclipse SUMO / TraCI co-simulation adapter for real-world maps       |
|  3. Multi-Agent MAPPO for continuous green split optimization            |
|  4. C-V2X (SAE J2735) integration for connected vehicle fleets          |
|                                                                          |
|  All code, scenarios, and tests are 100% open-source and runnable locally|
+--------------------------------------------------------------------------+
```

#### Speaker Notes:
> *"ClearPath is high-performance and deployment-ready. Our simulation engine runs 900 ticks in under 11 seconds, and our pure-NumPy RL policy trains in under 3 minutes on a CPU. Our prioritized roadmap bridges ClearPath to physical controller cabinets via MQTT, integrates SUMO co-simulation for complex city imports, and advances our RL policy to multi-agent MAPPO. ClearPath proves that cities do not have to choose between saving lives and maintaining traffic flow. Thank you! All code, scenarios, and tests are available to run right now with `make demo`."*

---

## Cross-Document References
- For detailed tabular figures, see [RESULTS.md](RESULTS.md).
- For step-by-step 3-minute demo speaking script, see [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
- For technical deep dive on architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

