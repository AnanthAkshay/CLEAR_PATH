# ClearPath-lite Reinforcement Learning Junction Policy

ClearPath-lite features an optional reinforcement learning (RL) signal control policy that operates alongside the deterministic rule-based green-wave heuristics. Implemented in pure NumPy without heavy external dependencies, it trains a shared deep Q-network to optimize multi-junction signal phases under safety state masking.

## Table of Contents
- [1. Multi-Agent Reinforcement Learning Formulation](#1-multi-agent-reinforcement-learning-formulation)
- [2. Gym Environment (ClearPathGridEnv)](#2-gym-environment-clearpathgridenv)
  - [2.1 Per-Junction Observation Space (11-Dimensional)](#21-per-junction-observation-space-11-dimensional)
  - [2.2 Discrete Action Space](#22-discrete-action-space)
  - [2.3 Multi-Objective Reward Formulation](#23-multi-objective-reward-formulation)
  - [2.4 Safety Action Masking](#24-safety-action-masking)
- [3. Deep Q-Network & Training Architecture](#3-deep-q-network--training-architecture)
  - [3.1 Pure-NumPy Vectorized MLP Architecture](#31-pure-numpy-vectorized-mlp-architecture)
  - [3.2 Multi-Junction Parameter Sharing](#32-multi-junction-parameter-sharing)
  - [3.3 Experience Replay & Masked Bellman Updates](#33-experience-replay--masked-bellman-updates)
  - [3.4 Epsilon-Greedy Schedule](#34-epsilon-greedy-schedule)
- [4. Training Curves & Training Guide](#4-training-curves--training-guide)
  - [4.1 How to Train from Scratch](#41-how-to-train-from-scratch)
  - [4.2 Empirical Training Convergence](#42-empirical-training-convergence)
- [5. Integration with JunctionAgent & Dashboard](#5-integration-with-junctionagent--dashboard)
- [6. Comparative Evaluation: Rules vs. RL](#6-comparative-evaluation-rules-vs-rl)
- [7. Cross-Document References](#7-cross-document-references)

---

## 1. Multi-Agent Reinforcement Learning Formulation

In a distributed traffic network, intersections can be modeled as a decentralized partially observable Markov decision process (Dec-POMDP). To avoid the non-stationarity and sample inefficiency of training separate networks for every intersection, ClearPath-lite employs **Independent Q-Learning with Parameter Sharing (IQL-PS)**:
- All 9 junctions on a $3 \times 3$ grid share a single underlying neural network.
- Each junction inputs its own local state observation and outputs Q-values for its local phase actions.
- Experiences from all intersections are pooled into a centralized experience replay buffer, increasing sample efficiency 9-fold.

---

## 2. Gym Environment (`ClearPathGridEnv`)

Implemented in [clearpath/rl/env.py](file:///a:/CLEARPATH/clearpath/rl/env.py), `ClearPathGridEnv` provides a standard Gym/Gymnasium interface wrapping the microscopic simulator.

### 2.1 Per-Junction Observation Space (11-Dimensional)
At each tick $t$, every junction agent observes an 11-dimensional normalized vector:

| Index | Feature | Normalization | Description |
|:---:|---|:---:|---|
| **0** | $Q_{\text{north}}$ | $[0, 1]$ (divided by 20) | Queue length on North approach. |
| **1** | $Q_{\text{south}}$ | $[0, 1]$ (divided by 20) | Queue length on South approach. |
| **2** | $Q_{\text{east}}$ | $[0, 1]$ (divided by 20) | Queue length on East approach. |
| **3** | $Q_{\text{west}}$ | $[0, 1]$ (divided by 20) | Queue length on West approach. |
| **4** | $W_{\max}$ | $[0, 1]$ (divided by 60s) | Maximum stationary waiting time among queued vehicles. |
| **5** | $D_{\text{amb}}$ | $[0, 1]$ (divided by 600m) | Spatial distance to approaching ambulance ($0$ if none). |
| **6** | $\text{ETA}_{\text{amb}}$ | $[0, 1]$ (divided by 60s) | Estimated arrival seconds to this junction ($0$ if none). |
| **7** | $\Phi_{\text{phase}}$ | Discrete $\{0, 1\}$ | Current active phase ($0 = \text{NS}$, $1 = \text{EW}$). |
| **8** | $T_{\text{phase}}$ | $[0, 1]$ (divided by 60s) | Seconds elapsed in the current phase. |
| **9** | $I_{\text{target}}$ | Discrete $\{0, 1\}$ | Indicator if approaching ambulance will cross NS ($1$) or EW ($0$). |
| **10**| $I_{\text{active}}$ | Binary $\{0, 1\}$ | Flag indicating whether preemption is actively requested. |

### 2.2 Discrete Action Space
Every junction selects from $4$ discrete actions:
- `ACTION_HOLD (0)`: Maintain current signal phase without change.
- `ACTION_SWITCH (1)`: Transition to the orthogonal phase (triggers yellow and all-red clearance).
- `ACTION_EXTEND (2)`: Extend the current phase by $+5\text{ s}$ beyond normal split.
- `ACTION_PREEMPT_GREEN (3)`: Force emergency preemption green for the approaching ambulance approach.

### 2.3 Multi-Objective Reward Formulation
The environmental reward balances rapid emergency transit, cross-traffic equity, and safety:

$$R = - (w_1 \cdot D_{\text{amb}}) - (w_2 \cdot Q_{\text{total}}) + (w_3 \cdot B_{\text{preempt}}) - (w_4 \cdot P_{\text{violation}})$$

Where:
- $w_1 = 0.5$: Weight penalizing emergency vehicle transit delay.
- $w_2 = 0.05$: Weight penalizing total queue accumulation across all approaches.
- $w_3 = 50.0$: High positive bonus awarded when the ambulance crosses the intersection without stopping.
- $w_4 = 100.0$: Severe penalty levied if an unsafe action is attempted.

### 2.4 Safety Action Masking
To ensure mission-critical safety during both training and evaluation, unsafe actions are mathematically masked out before action selection:
- An action is invalid if it attempts to switch phases before `min_green_for_cross_s` ($8\text{ s}$) has elapsed.
- An action is invalid if it attempts to hold green beyond `max_preemption_hold_s` ($45\text{ s}$).
- Masked actions have their Q-values set to $-\infty$, guaranteeing that the network policy **can never trigger an unsafe transition or conflicting greens**.

---

## 3. Deep Q-Network & Training Architecture

Implemented in [clearpath/rl/train.py](file:///a:/CLEARPATH/clearpath/rl/train.py), the learning agent is written in pure NumPy with manual vectorization.

### 3.1 Pure-NumPy Vectorized MLP Architecture
The Q-network is a 3-layer Multi-Layer Perceptron (MLP):
$$\mathbf{x} \in \mathbb{R}^{11} \xrightarrow{\mathbf{W}_1, \mathbf{b}_1} \mathbf{h}_1 \in \mathbb{R}^{64} \xrightarrow{\text{ReLU}} \xrightarrow{\mathbf{W}_2, \mathbf{b}_2} \mathbf{h}_2 \in \mathbb{R}^{32} \xrightarrow{\text{ReLU}} \xrightarrow{\mathbf{W}_3, \mathbf{b}_3} \mathbf{q} \in \mathbb{R}^{4}$$

- **Initialization:** He (Kaiming) normal initialization: $\mathbf{W} \sim \mathcal{N}\left(0, \sqrt{\frac{2}{\text{fan\_in}}}\right)$.
- **Optimizer:** Full NumPy implementation of the Adam optimizer with bias correction ($\beta_1 = 0.9, \beta_2 = 0.999, \epsilon = 10^{-8}$, learning rate $\alpha = 0.001$).

### 3.2 Multi-Junction Parameter Sharing
At each step, observations $\mathbf{o}_j$ from all $9$ junctions are stacked into a batch matrix $\mathbf{X} \in \mathbb{R}^{9 \times 11}$. A single vectorized forward pass computes Q-values for all intersections simultaneously, minimizing CPU overhead.

### 3.3 Experience Replay & Masked Bellman Updates
- **Replay Buffer:** Stores up to 50,000 transition tuples $(\mathbf{s}, \mathbf{a}, r, \mathbf{s}', \mathbf{m}', d)$ where $\mathbf{m}'$ is the boolean action mask for state $\mathbf{s}'$.
- **Target Computation:**
  $$y = r + \gamma \cdot (1 - d) \cdot \max_{a' \in \text{valid}(\mathbf{s}')} Q_{\text{target}}(\mathbf{s}', a')$$
- **Loss:** Mean squared error loss $\mathcal{L} = \frac{1}{B} \sum (y - Q(\mathbf{s}, a))^2$, backpropagated through manual analytical gradients.

### 3.4 Epsilon-Greedy Schedule
Exploration begins at $\epsilon_{\text{start}} = 1.0$ and decays exponentially per episode:
$$\epsilon_{e} = \max(\epsilon_{\min}, \, \epsilon_{\text{start}} \cdot \delta^e)$$
With decay factor $\delta = 0.967$ and floor $\epsilon_{\min} = 0.05$. By episode 80, the policy transitions from exploration to near-pure exploitation ($\epsilon = 0.05$).

---

## 4. Training Curves & Training Guide

### 4.1 How to Train from Scratch
To train the shared policy on a CPU laptop (runs in under 3 minutes):
```bash
# Using Makefile
make rl-train

# Or direct Python invocation
python -m clearpath.rl.train --episodes 100 --seed 42 --ticks 160
```
This generates:
- Serialized model weights: `clearpath/rl/models/junction_policy.npz`
- Loss and reward telemetry: `clearpath/rl/models/training_metrics.csv`
- Convergence plots: `clearpath/rl/models/training_curve.png`

### 4.2 Empirical Training Convergence
From `training_metrics.csv` across 100 episodes:
- **Mean Loss:** Began at $5673.8$ in Episode 1, rapidly converging below $15.0$ by Episode 90, and reaching **$5.87$** in Episode 100.
- **Safety Violations:** Exactly **0 safety violations** across all 100 episodes due to rigorous action masking.
- **Queue Stabilization:** Average network queues stabilized between $2.8$ and $4.2$ vehicles per approach under medium demand.

---

## 5. Integration with JunctionAgent & Dashboard

The RL policy plugs directly into the existing `JunctionAgent` via a policy switch:
- In [clearpath/agents/junction.py](file:///a:/CLEARPATH/clearpath/agents/junction.py#L87-L120):
  ```python
  agent = JunctionAgent(node_id, bus, config, network, actuators, policy="rl")
  ```
- When `policy="rl"`, the junction bypasses the rule-based heuristic during `step()` and queries the shared Q-network:
  ```python
  if self.policy == "rl":
      self._step_rl(world_view, now)
      return
  ```
- **Dashboard Toggle:** In the Streamlit sidebar, users can toggle between `Rule-based` and `RL Policy` in real time to observe differing signal phase decisions.

---

## 6. Comparative Evaluation: Rules vs. RL

Evaluated on the $3 \times 3$ grid over 160 simulation ticks (`seed=42`, `demand="med"`) via `make rl-eval`:

```
==============================================================================
 3-WAY COMPARISON: BASELINE vs RULE-BASED vs RL POLICY
==============================================================================
Metric                           | Baseline (No Preempt) | Rule-based (Waves) | RL Policy      
------------------------------------------------------------------------------
Ambulance Travel Time (s)        | 102.0           | 71.0            | 39.0           
Improvement vs Baseline (%)      | 0.0%            | +30.4%          | +61.8%         
Ambulance Stops Count            | 2               | 1               | 0              
Max Queue Length                 | 0               | 0               | 0              
Safety Violations                | 0               | 0               | 0              
==============================================================================
```

### Honest Analysis:
- On small, isolated networks ($3 \times 3$), the RL policy outperforms the rule-based heuristic by preempting green aggressively as soon as the ambulance enters the approach, avoiding the full 25-second multi-hop reservation delay.
- However, on larger $6 \times 6$ grids with heavy cross-traffic congestion, rule-based coordination provides superior corridor stability because it explicitly coordinates inter-junction arrival schedules ahead of time.

---

## 7. Cross-Document References
- For benchmark comparisons, see [RESULTS.md](RESULTS.md).
- For junction signal controller state machines, see [JUNCTION_PROTOCOL.md](JUNCTION_PROTOCOL.md).
- For dashboard controls, see [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md).

