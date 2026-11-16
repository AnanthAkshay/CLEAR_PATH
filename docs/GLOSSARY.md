# ClearPath-lite Domain Terminology Glossary

This glossary defines standard terminology across traffic engineering, cyber-physical security, distributed multi-agent systems, and reinforcement learning as utilized within ClearPath-lite.

## Table of Contents
- [1. Traffic Engineering & Signal Control](#1-traffic-engineering--signal-control)
- [2. Emergency Preemption & Green Waves](#2-emergency-preemption--green-waves)
- [3. Cyber-Physical Security & Cryptography](#3-cyber-physical-security--cryptography)
- [4. Distributed Systems & Multi-Agent Architecture](#4-distributed-systems--multi-agent-architecture)
- [5. Microscopic Simulation & Kinematics](#5-microscopic-simulation--kinematics)
- [6. Reinforcement Learning](#6-reinforcement-learning)
- [7. Cross-Document References](#7-cross-document-references)

---

## 1. Traffic Engineering & Signal Control

### Actuator
The hardware interface or software driver responsible for commanding physical signal lamps or motor switches based on agent directives. In ClearPath, the `ActuatorInterface` mediates signal phase changes and driver compliance slowdowns.

### All-Red Interval
A clearance phase during which all approaches to an intersection display red simultaneously (default $1.0\text{ s}$ in ClearPath). This allows vehicles that lawfully entered the intersection on yellow to clear the conflict zone before cross-traffic receives green.

### Clearance Interval
The combined duration of yellow change and all-red clearance intervals ($\text{yellow\_s} + \text{all\_red\_s} = 4.0\text{ s}$). Enforced physically by signal controllers before switching between conflicting movements.

### Cycle Length
The total time in seconds required for a signal controller to complete one full sequence of all served phases (default $60.0\text{ s}$ in ClearPath).

### Fixed-Time Control
A traditional signal operation mode where phase timings, splits, and cycle durations are predetermined and static, cycling independently of live traffic fluctuations.

### Phase
The set of simultaneous green, yellow, and red indications allocated to specific compatible traffic movements at an intersection (e.g., `NS_GREEN`, `EW_GREEN`).

### Phase Split
The proportion of total cycle time allocated to a particular signal phase.

### Signal Offset
The time difference in seconds between the start of a designated phase at one intersection relative to a master system clock, staggered to establish coordinated progression waves.

### Spillback
A traffic phenomenon where a queue of stopped vehicles at a downstream intersection extends backward along the road segment, blocking the upstream intersection and paralyzing cross-traffic.

### Starvation
An unfair condition where one traffic approach is completely deprived of green time due to an extended override on a competing movement. ClearPath prevents starvation via post-preemption recovery phases and maximum hold limits.

---

## 2. Emergency Preemption & Green Waves

### Emergency Vehicle Preemption (EVP)
The operational strategy of interrupting normal signal cycles to grant immediate right-of-way to approaching emergency vehicles (ambulances, fire engines).

### Green Wave
A coordinated progression of green traffic signals timed along an emergency vehicle's path so that the vehicle encounters green lights continuously without stopping.

### Pre-Clear Phase (`PRE_CLEAR`)
A proactive signal phase executed by a `JunctionAgent` when an approaching preemption corridor faces a heavy cross-street queue. It flushes cross-street vehicles before the ambulance arrives, preventing intersection gridlock.

### Recovery Phase (`RECOVERY`)
A compensatory phase executed immediately after an emergency vehicle clears an intersection. It locks green for the starved cross-street for an extended duration ($20\text{--}40\text{ s}$) to dissipate queued traffic.

### Hold Cap (`max_preemption_hold_s`)
A hard limit (default $45.0\text{ s}$) enforcing the maximum consecutive duration that an intersection may hold green for an emergency preemption request, preventing indefinite overrides if an ambulance stalls.

---

## 3. Cyber-Physical Security & Cryptography

### Constant-Time Comparison
A comparison function (such as Python's `hmac.compare_digest()`) that executes in identical CPU clock cycles regardless of where byte mismatches occur, preventing side-channel timing attacks from deducing cryptographic secrets.

### HMAC-SHA256
Hash-based Message Authentication Code utilizing the SHA-256 cryptographic hash function. ClearPath uses HMAC-SHA256 to sign preemption credentials with a shared symmetric key.

### Kinematic Telemetry Validation
The verification of vehicular physical claims (speed, acceleration, heading, spatial displacement) against the physical limits of roads and vehicles, ensuring that stolen keys cannot be used to trigger remote signal overrides.

### Nonce
A cryptographic "Number used ONCE". A high-entropy unique string bound into preemption tokens to ensure that recorded legitimate credentials cannot be replayed by adversaries.

### Replay Attack
A cyber attack where an adversary records a valid wireless preemption transmission and retransmits it at a later time to trigger an unauthorized green light. Blocked in ClearPath via nonces and a 60-second TTL.

### Time-to-Live (TTL)
The maximum validity lifespan of an authentication token (default $60.0\text{ s}$). Tokens presented after their TTL has elapsed are rejected as expired.

---

## 4. Distributed Systems & Multi-Agent Architecture

### Asynchronous Message Bus
A decoupled communication layer where agents exchange typed messages without blocking or maintaining direct internal references to other agents.

### Independence of Irrelevant Alternatives (IIA)
An axiomatic decision-making principle: the relative ranking between two candidates (e.g., Hospital A and Hospital B) should depend solely on their individual scores and not on whether a third candidate (Hospital C) is present in the pool. ClearPath achieves IIA by normalizing against fixed reference denominators.

### Loose Coupling
An architectural property where subsystems communicate through well-defined protocol contracts (such as dataclass messages) rather than directly invoking internal methods or mutating shared state.

### Unicast vs. Broadcast
- **Unicast:** Delivering a message to a single specific agent recipient (e.g., `"j_0_1"`).
- **Broadcast:** Delivering a message to all active agents across the network (designated by recipient `"*"`).

---

## 5. Microscopic Simulation & Kinematics

### Free-Flow Speed
The desired velocity a driver maintains when unconstrained by other vehicles or traffic control signals (e.g., $16.7\text{ m/s}$ on arterials).

### Headway
- **Time Headway:** The elapsed time in seconds between consecutive vehicles passing a fixed point on the road (default $1.2\text{ s}$ in IDM).
- **Space Headway:** The distance in meters from the front bumper of a lead vehicle to the front bumper of the following vehicle.

### Intelligent Driver Model (IDM)
A continuous car-following model that calculates vehicle acceleration as a non-linear function of current speed, desired velocity, net distance to the leader, and approach velocity difference.

### Jam Density ($k_{\text{jam}}$)
The maximum theoretical density of stationary, bumper-to-bumper vehicles packed onto a road segment, calculated as $\frac{1000}{L_{\text{veh}} + d_{\text{gap}}} = 80\text{ veh/km/lane}$.

### Variable Message Sign (VMS)
Dynamic electronic roadside display signs that broadcast tactical alerts to drivers (e.g., *"EMERGENCY VEHICLE APPROACHING FROM SOUTH - YIELD"*).

---

## 6. Reinforcement Learning

### Action Masking
A mathematical safety mechanism that sets the Q-values of illegal or unsafe actions to $-\infty$, preventing an RL policy from ever choosing an invalid transition (such as violating minimum green splits).

### Deep Q-Network (DQN)
A model-free reinforcement learning algorithm that uses a neural network function approximator to estimate the expected cumulative future return (Q-value) of taking action $a$ in state $s$.

### Parameter Sharing
A multi-agent RL paradigm where multiple homogeneous agents (e.g., all 9 junction controllers) share the identical neural network weights, drastically accelerating sample efficiency while allowing each agent to act on its local observation vector.

---

## 7. Cross-Document References
- For system architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).
- For cryptographic token verification, see [SECURITY.md](SECURITY.md).
- For traffic physics and car-following equations, see [SIMULATION.md](SIMULATION.md).

