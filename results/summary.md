# ClearPath-lite Benchmark Summary Report

Generated: 2026-11-17 17:52:22  
Seed: `42` | Demand: `low`

---

## 1. Executive Status Checklist

| Check | Item | Status | Details |
|---|---|:---:|---|
| CHK-01 | Normal traffic baseline (autonomous cycling, 0 preempted) | ✅ PASS | 600 ticks, throughput=0.593 veh/t, avg speed=7.41 m/s |
| CHK-02 | Emergency ambulance travel time improvement | ✅ PASS | ClearPath=35.0s vs Baseline=105.0s (-66.7%) |
| CHK-03 | Network throughput recovery within recovery_s + 60s | ✅ PASS | Recovered to 107.1% of baseline throughput |
| CHK-04 | Security gateway attack rejection (6/6 blocked, 1/1 allowed) | ✅ PASS | Blocked 6/6 attacks (100%), allowed 1/1 legitimate |
| CHK-05 | Attack signal override isolation (0 overrides from attacks) | ✅ PASS | Zero signal phase overrides caused by spoofed requests |

---

## 2. Normal Traffic Baseline (run_normal.py)

- **Ticks Simulated:** 600
- **Average Network Speed:** 7.41 m/s
- **Network Throughput:** 0.593 veh/tick
- **Completed Vehicles:** 356
- **Mean Approach Queue:** 1.60 vehicles
- **Max Approach Queue:** 10 vehicles
- **Preempted Signals:** 0 (zero agent interference)

---

## 3. Emergency Preemption vs. Baseline (run_emergency.py)

| Metric | Baseline (Preemption OFF) | ClearPath (Preemption ON) | Improvement / Delta |
|---|:---:|:---:|:---:|
| **Ambulance Travel Time** | 105.0 s | 35.0 s | **-70.0 s (66.7%)** |
| **Ambulance Stops** | 3 | 0 | -3 stops |
| **Cross-Traffic Delay (avg)** | 0.0 s | 0.0 s | 0.0 s |
| **Cross-Traffic Delay (p95)** | 0.0 s | 0.0 s | 0.0 s |
| **Max Queue Length** | 10 veh | 10 veh | 0 veh |
| **Recovery Duration (avg)** | — | 31.0 s | Standard recovery cycle |
| **Messages Exchanged** | 150 | 74 | Inter-junction coordination |
| **Throughput @ Recovery+60s** | 0.112 veh/t | 0.120 veh/t | 107.1% of baseline |

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
