# ClearPath-lite Metrics & Telemetry Glossary

This document details the mathematical definitions, source code references, temporal windows, and vehicle cohorts used to calculate all performance, safety, and security metrics in ClearPath-lite.

## Table of Contents
- [1. Operational Performance Metrics](#1-operational-performance-metrics)
  - [1.1 Ambulance Travel Time](#11-ambulance-travel-time)
  - [1.2 Ambulance Stops](#12-ambulance-stops)
  - [1.3 Ambulance Stopped Time](#13-ambulance-stopped-time)
  - [1.4 Ambulance Improvement Percentage](#14-ambulance-improvement-percentage)
- [2. Traffic Flow & Queue Metrics](#2-traffic-flow--queue-metrics)
  - [2.1 Network Throughput](#21-network-throughput)
  - [2.2 Average Network Speed](#22-average-network-speed)
  - [2.3 Network Maximum & Mean Queue Length](#23-network-maximum--mean-queue-length)
  - [2.4 Network Throughput Recovery Ratio](#24-network-throughput-recovery-ratio)
- [3. Equity & Preemption Impact Metrics](#3-equity--preemption-impact-metrics)
  - [3.1 Cross-Traffic Delay (Average & P95)](#31-cross-traffic-delay-average--p95)
  - [3.2 Recovery Duration](#32-recovery-duration)
- [4. Cyber-Physical Security Gateway Metrics](#4-cyber-physical-security-gateway-metrics)
  - [4.1 Attack Block Rate](#41-attack-block-rate)
  - [4.2 False-Positive Rate](#42-false-positive-rate)
  - [4.3 Signal Overrides from Attacks](#43-signal-overrides-from-attacks)
- [5. Distributed Coordination Metrics](#5-distributed-coordination-metrics)
  - [5.1 Negotiation Messages Exchanged](#51-negotiation-messages-exchanged)
  - [5.2 Negotiation Nack Count & Latency](#52-negotiation-nack-count--latency)
- [6. Summary Reference Table](#6-summary-reference-table)
- [7. Cross-Document References](#7-cross-document-references)

---

## 1. Operational Performance Metrics

### 1.1 Ambulance Travel Time
- **Definition:** Total elapsed time in simulation seconds from the initial emergency request submission until the emergency vehicle arrives at the designated hospital terminus.
- **Formula:**
  $$T_{\text{travel}} = t_{\text{arrival}} - t_{\text{dispatch}}$$
- **Code Reference:** [clearpath/engine/metrics.py](file:///a:/CLEARPATH/clearpath/engine/metrics.py#L295-L298)
  ```python
  @property
  def ambulance_travel_time(self) -> Optional[float]:
      return self._amb_travel_time
  ```
- **Unit:** Seconds ($\text{s}$).

### 1.2 Ambulance Stops
- **Definition:** Total count of full stops experienced by the emergency vehicle during transit. A vehicle is considered stopped when its speed drops below $0.1\text{ m/s}$.
- **Formula:** Incremented by 1 when $v < 0.1\text{ m/s}$ following an active motion state ($v \ge 0.1\text{ m/s}$).
- **Code Reference:** [clearpath/engine/metrics.py](file:///a:/CLEARPATH/clearpath/engine/metrics.py#L300-L304)
- **Unit:** Integer stop count.

### 1.3 Ambulance Stopped Time
- **Definition:** Cumulative duration in seconds that the emergency vehicle spent stationary ($v < 0.1\text{ m/s}$) while traversing the preemption corridor.
- **Formula:**
  $$T_{\text{stopped}} = \sum_{t=t_{\text{dispatch}}}^{t_{\text{arrival}}} \mathbb{I}(v(t) < 0.1) \cdot \Delta t$$
- **Code Reference:** [clearpath/engine/metrics.py](file:///a:/CLEARPATH/clearpath/engine/metrics.py#L306-L310)
- **Unit:** Seconds ($\text{s}$).

### 1.4 Ambulance Improvement Percentage
- **Definition:** Relative percentage reduction in ambulance travel time achieved by ClearPath preemption compared to the fixed-time baseline with identical random seed and traffic demand:
- **Formula:**
  $$\Delta_{\text{imp}} = \frac{T_{\text{baseline}} - T_{\text{clearpath}}}{T_{\text{baseline}}} \times 100\%$$
- **Code Reference:** [clearpath/engine/metrics.py](file:///a:/CLEARPATH/clearpath/engine/metrics.py#L312-L318)
- **Unit:** Percentage ($\%$).

---

## 2. Traffic Flow & Queue Metrics

### 2.1 Network Throughput
- **Definition:** The rate of vehicles completing their journey and exiting the network per simulation tick.
- **Formula:**
  $$\Phi_{\text{net}} = \frac{N_{\text{completed}}}{T_{\text{ticks}}}$$
- **Code Reference:** [clearpath/engine/metrics.py](file:///a:/CLEARPATH/clearpath/engine/metrics.py#L334-L337)
- **Unit:** Vehicles per tick ($\text{veh/tick}$). Multiply by 3600 for vehicles per hour ($\text{veh/h}$).

### 2.2 Average Network Speed
- **Definition:** Mean instantaneous speed of all active civilian vehicles currently operating on the network at tick $t$.
- **Formula:**
  $$\bar{v}(t) = \frac{1}{|V(t)|} \sum_{i \in V(t)} v_i(t)$$
- **Code Reference:** [clearpath/engine/metrics.py](file:///a:/CLEARPATH/clearpath/engine/metrics.py#L339-L342)
- **Unit:** Meters per second ($\text{m/s}$). Multiply by 3.6 for $\text{km/h}$.

### 2.3 Network Maximum & Mean Queue Length
- **Definition:**
  - **Mean Queue:** Average number of queued (stationary) vehicles across all directed intersection approaches in the network.
  - **Max Queue:** The single longest queue observed across any approach during the run.
- **Formula:**
  $$Q_{\max} = \max_{e \in E, \, t} Q_e(t), \quad \bar{Q} = \frac{1}{|E|} \sum_{e \in E} Q_e(t)$$
- **Code Reference:** [clearpath/engine/metrics.py](file:///a:/CLEARPATH/clearpath/engine/metrics.py#L344-L352)
- **Unit:** Vehicles ($\text{veh}$).

### 2.4 Network Throughput Recovery Ratio
- **Definition:** Ratio of network throughput measured during the 60-second window following junction recovery ($t \in [t_{\text{rec}}, t_{\text{rec}} + 60\text{s}]$) versus the throughput of the un-preempted baseline scenario over the same temporal window.
- **Formula:**
  $$\text{Ratio}_{\text{rec}} = \frac{\Phi_{\text{clearpath}}[t_{\text{rec}} : t_{\text{rec}}+60]}{\Phi_{\text{baseline}}[t_{\text{rec}} : t_{\text{rec}}+60]} \times 100\%$$
- **Code Reference:** [clearpath/scenarios/run_emergency.py](file:///a:/CLEARPATH/clearpath/scenarios/run_emergency.py#L182-L215)
- **Unit:** Percentage ($\%$). Benchmarked at **$97.7\%$** (surpassing the $90\%$ recovery threshold).

---

## 3. Equity & Preemption Impact Metrics

### 3.1 Cross-Traffic Delay (Average & P95)

#### Mathematical Definition
Cross-traffic delay measures the additional waiting time imposed on civilian vehicles due to signals being locked green for the emergency corridor:
$$\Delta W_i = W_i(t_{\text{end}}) - W_i(t_{\text{start}})$$
Where $W_i(t)$ is vehicle $i$'s cumulative stationary waiting time.
- **Average Delay:** $\bar{D}_{\text{cross}} = \frac{1}{|S|} \sum_{i \in S} \Delta W_i$
- **P95 Delay:** The 95th percentile value of all positive delay deltas in $S$.

#### Vehicle Cohort & Temporal Window
- **Vehicles Tracked:** In [clearpath/engine/metrics.py](file:///a:/CLEARPATH/clearpath/engine/metrics.py#L185-L215), `on_preemption_start()` snapshots **all active civilian vehicles across the entire network** (`v.kind != "ambulance"`), plus any newly spawned vehicles entering during preemption. It does not isolate only vehicles queued on perpendicular cross-streets.
- **Intended Window:** From request dispatch ($t = 10\text{ s}$) until corridor preemption terminates.

#### Transparent Analysis of the `0.0 s` Benchmark Value
In the standard benchmark summary report (`results/summary.md`), `Cross-Traffic Delay` reports `0.0 s`:
1. **Root Cause:** In the simulation engine, `metrics.on_preemption_start()` is called at $t=10$ when the emergency request is accepted. However, `metrics.on_preemption_end()` was **never invoked anywhere in the codebase** upon arrival or recovery.
2. Because `on_preemption_end()` was not executed, `self._cross_delay_samples` remains empty (`[]`).
3. In `metrics.py`, `_safe_mean([])` defaults to `0.0`.
4. **Actual Measured Delay:** When instrumented to evaluate active civilian vehicles at ambulance arrival ($t=46$), the **31 active vehicles** in the network experienced:
   - **Average Delay Delta:** **$10.52\text{ s}$**
   - **95th Percentile Delay (P95):** **$21.00\text{ s}$**
   - **Peak Per-Junction Cross Wait:** Up to **$28.0\text{ s}$** at corridor junction `j_2_2`.

### 3.2 Recovery Duration
- **Definition:** The duration in seconds that an intersection holds a compensating green phase for the starved orthogonal cross-street after preemption terminates:
  $$t_{\text{recovery}} = \text{recovery\_s} + \min(\text{delay\_suffered}, \, \text{recovery\_s})$$
- **Code Reference:** [clearpath/agents/junction.py](file:///a:/CLEARPATH/clearpath/agents/junction.py#L484-L488)
- **Unit:** Seconds ($\text{s}$). Defaults to $20.0\text{ s}$ base, averaging **$31.0\text{ s}$** during corridor runs.

---

## 4. Cyber-Physical Security Gateway Metrics

### 4.1 Attack Block Rate
- **Definition:** The proportion of malicious or invalid preemption requests successfully intercepted and blocked by the `SecurityAgent`.
- **Formula:**
  $$\text{Block Rate} = \frac{N_{\text{blocked\_attacks}}}{N_{\text{total\_attacks}}} \times 100\%$$
- **Code Reference:** [clearpath/agents/security.py](file:///a:/CLEARPATH/clearpath/agents/security.py#L340-L355), [clearpath/scenarios/run_spoofed.py](file:///a:/CLEARPATH/clearpath/scenarios/run_spoofed.py#L120-L135)
- **Unit:** Percentage ($\%$). Benchmarked at **$100.0\%$** ($6/6$ attacks blocked).

### 4.2 False-Positive Rate
- **Definition:** The proportion of genuine, authorized emergency preemption requests incorrectly blocked by the security gateway.
- **Formula:**
  $$\text{FPR} = \frac{N_{\text{blocked\_legitimate}}}{N_{\text{total\_legitimate}}} \times 100\%$$
- **Code Reference:** [clearpath/scenarios/run_spoofed.py](file:///a:/CLEARPATH/clearpath/scenarios/run_spoofed.py#L136-L140)
- **Unit:** Percentage ($\%$). Benchmarked at **$0.0\%$** ($0/1$ legitimate requests blocked).

### 4.3 Signal Overrides from Attacks
- **Definition:** Count of unauthorized traffic signal phase changes or preemption holds caused by spoofed requests.
- **Formula:** Strictly must equal **0**. Verified in `test_engine.py::test_spoofed_request_no_signal_override`.

---

## 5. Distributed Coordination Metrics

### 5.1 Negotiation Messages Exchanged
- **Definition:** Total count of coordination messages (`ReserveCorridor`, `ReserveAck`, `ReserveNack`, `GreenWavePrepare`, `PassedNotice`) routed through the `MessageBus` during the corridor run.
- **Code Reference:** [clearpath/engine/metrics.py](file:///a:/CLEARPATH/clearpath/engine/metrics.py#L370-L375)
- **Benchmarked Count:** 74 messages exchanged during the ClearPath emergency run.

### 5.2 Negotiation Nack Count & Latency
- **Definition:**
  - **Nack Count:** Total reservation refusals emitted due to undrainable cross queues or concurrency conflicts.
  - **Average Latency:** Mean simulated transit delay experienced by bus messages.
- **Unit:** Integer count / seconds.

---

## 6. Summary Reference Table

| Metric Key | Display Name | Unit | Target / Direction | ClearPath Result |
|---|---|:---:|:---:|:---:|
| `ambulance_travel_time_s` | Ambulance Travel Time | s | Minimise | **$35.0\text{ s}$** (vs $111.0\text{ s}$) |
| `ambulance_stops` | Ambulance Stops | count | Zero | **0** (vs 7) |
| `ambulance_stopped_time_s` | Stopped Time | s | Zero | **$0.0\text{ s}$** (vs $48.0\text{ s}$) |
| `ambulance_improvement_pct` | Travel Improvement | % | Maximise | **$+68.5\%$** |
| `cross_delay_avg_s` | Cross-Traffic Delay (avg) | s | Minimise | **$0.0\text{ s}$** ($10.52\text{ s}$ actual) |
| `cross_delay_p95_s` | Cross-Traffic Delay (p95) | s | Minimise | **$0.0\text{ s}$** ($21.00\text{ s}$ actual) |
| `network_throughput` | Network Throughput | veh/t | Maintain | **$0.9\text{ veh/t}$** |
| `throughput_rec_ratio` | Throughput Recovery Ratio | % | $\ge 90\%$ | **$97.7\%$** |
| `security_attack_block_rate`| Attack Block Rate | % | $100\%$ | **$100.0\%$** ($6/6$) |
| `security_false_positive_rate` | False Positive Rate | % | $0\%$ | **$0.0\%$** ($0/1$) |
| `security_attack_overrides`| Attack Signal Overrides | count | Zero | **0** |
| `recovery_duration_avg_s` | Recovery Phase Duration | s | Balanced | **$31.0\text{ s}$** |
| `messages_exchanged` | Bus Messages Exchanged | count | Bounded | **74** |

---

## 7. Cross-Document References
- For experimental numbers from scenario runs, see [RESULTS.md](RESULTS.md).
- For security audit reason codes, see [SECURITY.md](SECURITY.md).
- For the underlying traffic equations and IDM parameters, see [SIMULATION.md](SIMULATION.md).

