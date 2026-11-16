# ClearPath-lite: 3-Minute Live Demo Script

**Target Audience:** Technical evaluators, municipal traffic engineers, and security reviewers.  
**Total Duration:** 3 minutes (180 seconds).

---

## Preparation Checklist
1. Ensure dependencies are installed: `make install`
2. Run test suite to verify green status: `make test`
3. Launch Streamlit dashboard in a browser window:
   ```bash
   make dashboard
   ```
   *(Opens at `http://localhost:8501`)*
4. Have a split terminal open to demonstrate CLI benchmarks:
   ```bash
   make demo
   ```

---

## Act 1: The Problem & System Architecture (0:00 – 0:35)

### What to Click / Display
- Point to the **ClearPath Architecture Diagram** on screen or the live dashboard overview.

### What to Say
> *"Welcome! Today we are demonstrating **ClearPath-lite**, an open-source, multi-agent platform for intelligent emergency vehicle preemption and fair urban traffic recovery.*  
>  
> *Traditional emergency siren preemption suffers from three critical flaws:*  
> *1. **Local optic sensors fail:** They only see the ambulance when it is already at the intersection.*  
> *2. **Severe cross-traffic gridlock:** Signals hold arbitrarily and strand cross-streets for miles.*  
> *3. **Zero authentication:** Modern software-defined radios can easily spoof optical emitters or radio triggers.*  
>  
> *ClearPath solves this by decoupling the world simulator from four autonomous agents through an asynchronous MessageBus: a **DispatcherAgent** for multi-criteria hospital triage and routing, a **SecurityAgent** gating cryptographic HMAC tokens and kinematics, distributed **JunctionAgents** coordinating green waves, and a **GuidanceAgent** synthesizing driver lane advisories."*

---

## Act 2: Emergency Preemption & Recovery in Action (0:35 – 1:35)

### What to Click / Display
- In the Streamlit dashboard sidebar, select **Scenario: "Valid emergency"** (Incident Type: `cardiac`, Demand: `med`).
- Click **"Run Simulation"** (or in terminal: `python -m clearpath.scenarios.run_emergency`).
- Scroll to the **Side-by-Side Comparison KPI Table**.

### What to Point At & Say
> *"Notice the simulation running a severe cardiac incident originating at the far corner of our grid (`j_0_0`).*  
>  
> *Look at these top three metrics:*  
> - **Ambulance Travel Time:** *Dropped from **111.0 seconds** in the baseline down to **35.0 seconds** with ClearPath—a **68.5% time reduction**.*  
> - **Ambulance Stops:** *Dropped from **7 stops to exactly 0 stops**.*  
> - **Ambulance Stopped Time:** *Dropped from **48 seconds to 0 seconds**.*  
>  
> *Now watch the map. The JunctionAgents negotiated a synchronized green corridor 25 seconds ahead of arrival using `ReserveCorridor` and `GreenWavePrepare` messages. Civilian drivers received dynamic VMS advisories instructing them to yield.*  
>  
> *Most importantly, point to **Throughput @ Recovery+60s**: Within 80 seconds after arrival, cross-traffic throughput recovered to **97.7% of the normal baseline**. ClearPath clears the ambulance without paralyzing the city."*

---

## Act 3: Cyber-Physical Threat Rejection (1:35 – 2:25)

### What to Click / Display
- In the dashboard, switch to **Scenario: "Spoofed request"** or in terminal run:
  ```bash
  python -m clearpath.scenarios.run_spoofed
  ```
- Point to the **Security Gateway Audit Table**.

### What to Point At & Say
> *"Next, let's look at cyber-physical security. If a system can override city traffic lights, it will be targeted by bad actors.*  
>  
> *Here we inject **six adversarial attack vectors in sequence**, interleaved with one legitimate ambulance:*  
> 1. **Forged HMAC Signature:** *Signature byte tampered → `BLOCKED (TOKEN)` via constant-time verification.*  
> 2. **Expired Token:** *Replay of a 2-minute-old token → `BLOCKED (TOKEN)` due to TTL expiration.*  
> 3. **Legitimate Ambulance Request:** *Valid HMAC, valid kinematic telemetry → `ALLOWED`.*  
> 4. **Nonce Replay Attack:** *Attacker eavesdrops and retransmits the valid token → `BLOCKED (TOKEN)` because the nonce is already consumed in our replay cache.*  
> 5. **Kinematic Overspeed:** *Valid cryptographic token, but telemetry reports 180 km/h on an urban road → `BLOCKED (SPEED_LIMIT)`.*  
> 6. **Discontinuous GPS Teleport:** *Vehicle jumps 800m across the city in 1 second → `BLOCKED (CONTINUITY)`.*  
> 7. **Unauthorized Fleet ID:** *Valid cryptographic key used by an unauthorized vehicle ID → `BLOCKED (UNAUTHORIZED_VEHICLE)`.*  
>  
> *Notice the key result: **6 out of 6 attacks blocked (100%)**, 1 legitimate request allowed, and **0 signal overrides leaked to the network**."*

---

## Act 4: Verification, Scalability & Roadmap (2:25 – 3:00)

### What to Click / Display
- Run `make test` or `make demo` in terminal.
- Show the **Consolidated PASS/FAIL Checklist**.

### What to Say
> *"To ensure mission-critical safety, our test suite has **114 passing tests** verifying property-based safety invariants:*  
> - *Invariant 1: **Zero conflicting orthogonal greens** are ever active across any junction at any tick.*  
> - *Invariant 2: Preemption hold duration **never exceeds the 45-second safety limit**.*  
> - *Invariant 3: Blocked requests **never alter any traffic signal**.*  
>  
> *Our optimized simulation engine executes 900 discrete ticks with high demand in **under 11 seconds**, enabling rapid scenario exploration and reinforcement learning.*  
>  
> *Looking ahead, our roadmap includes SUMO/TraCI co-simulation, MARL MAPPO junction policies, and MQTT secure edge telemetry.*  
>  
> *Thank you! All code, scenarios, and tests are 100% runnable locally with `make demo`."*

