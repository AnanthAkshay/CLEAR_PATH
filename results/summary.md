# ClearPath-lite Benchmark Summary Report

Generated: 2026-11-18 23:00:40  
Seed: `42` | Demand: `med`

---

## 1. Executive Status Checklist

| Check | Item | Status | Details |
|---|---|:---:|---|
| CHK-01 | Normal traffic baseline (autonomous cycling, 0 preempted) | ✅ PASS | 600 ticks, throughput=1.273 veh/t, avg speed=6.15 m/s |
| CHK-02 | Emergency ambulance travel time improvement | ✅ PASS | ClearPath=36.0s vs Baseline=111.0s (-67.6%) |
| CHK-03 | Network throughput recovery within recovery_s + 60s | ✅ PASS | Recovered to 106.8% of baseline throughput |
| CHK-04 | Security gateway attack rejection (6/6 blocked, 1/1 allowed) | ✅ PASS | Blocked 6/6 attacks (100%), allowed 1/1 legitimate |
| CHK-05 | Attack signal override isolation (0 overrides from attacks) | ✅ PASS | Zero signal phase overrides caused by spoofed requests |

---

## 2. Normal Traffic Baseline (run_normal.py)

- **Ticks Simulated:** 600
- **Average Network Speed:** 6.15 m/s
- **Network Throughput:** 1.273 veh/tick
- **Completed Vehicles:** 764
- **Mean Approach Queue:** 2.55 vehicles
- **Max Approach Queue:** 13 vehicles
- **Preempted Signals:** 0 (zero agent interference)

---

## 3. Emergency Preemption vs. Baseline (run_emergency.py)

| Metric | Baseline (Preemption OFF) | ClearPath (Preemption ON) | Improvement / Delta |
|---|:---:|:---:|:---:|
| **Ambulance Travel Time** | 111.0 s | 36.0 s | **-75.0 s (67.6%)** |
| **Ambulance Stops** | 7 | 0 | -7 stops |
| **Cross-Traffic Delay (avg)** | 0.0 s | 0.0 s | 0.0 s |
| **Cross-Traffic Delay (p95)** | 0.0 s | 0.0 s | 0.0 s |
| **Max Queue Length** | 13 veh | 13 veh | 0 veh |
| **Recovery Duration (avg)** | — | 34.0 s | Standard recovery cycle |
| **Messages Exchanged** | 336 | 197 | Inter-junction coordination |
| **Throughput @ Recovery+60s** | 0.349 veh/t | 0.373 veh/t | 106.8% of baseline |

---

## 4. Cyber-Physical Security Gateway (run_spoofed.py)

- **Total Injections Evaluated:** 7
- **Attacks Injected:** 6 (Forged HMAC, Expired Token, Replay, 180 km/h Overspeed, Teleport, Unauthorized Fleet ID)
- **Attack Block Rate:** 100.0% (6/6 attacks blocked)
- **False-Positive Rate:** 0.0% (0/1 legitimate blocked)
- **Legitimate Allowed:** 1/1 (**100.0%**)
- **Signal Overrides from Attacks:** 0 (**Zero signal override leakage**)

### Security Audit Trail

| Request | Type | Verdict | Reasons | Status |
|---|---|:---:|---|:---:|
| (a) Forged HMAC | Cryptographic | `BLOCK` | `TOKEN` | PASS |
| (b) Expired Token | Cryptographic | `BLOCK` | `TOKEN` | PASS |
| [+] Legitimate Request | Legitimate | `ALLOW` | `none` | PASS |
| (c) Replay Attack | Cryptographic | `BLOCK` | `TOKEN` | PASS |
| (d) 180 km/h Overspeed | Kinematic | `BLOCK` | `SPEED_LIMIT, CONTINUITY` | PASS |
| (e) Position Teleport | Kinematic | `BLOCK` | `CONTINUITY` | PASS |
| (f) Unauthorized Vehicle | Authorization | `BLOCK` | `UNAUTHORIZED_VEHICLE` | PASS |
