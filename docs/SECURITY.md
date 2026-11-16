# ClearPath-lite Cyber-Physical Security Architecture

ClearPath-lite incorporates a zero-trust cyber-physical firewall designed to protect municipal traffic infrastructure from unauthorized signal overrides, cryptographic tampering, and kinematic spoofing.

## Table of Contents
- [1. Threat Model & Security Boundaries](#1-threat-model--security-boundaries)
  - [1.1 Protected Assets](#11-protected-assets)
  - [1.2 Adversary Capabilities](#12-adversary-capabilities)
  - [1.3 Trust Boundaries](#13-trust-boundaries)
- [2. Attack Defense Matrix](#2-attack-defense-matrix)
- [3. Cryptographic Token Design](#3-cryptographic-token-design)
  - [3.1 Token Format](#31-token-format)
  - [3.2 HMAC-SHA256 Verification & Constant-Time Comparison](#32-hmac-sha256-verification--constant-time-comparison)
  - [3.3 Architectural Rationale: Why JWT is Not Used](#33-architectural-rationale-why-jwt-is-not-used)
- [4. Secret Management & Operational Environment](#4-secret-management--operational-environment)
- [5. Kinematic Telemetry Validation](#5-kinematic-telemetry-validation)
- [6. Known Security Limitations](#6-known-security-limitations)
- [7. Cross-Document References](#7-cross-document-references)

---

## 1. Threat Model & Security Boundaries

### 1.1 Protected Assets
1. **Traffic Signal State Machines:** Prevention of unauthorized phase manipulation, arbitrary green holds, and forced signal cycle desynchronization.
2. **Intersection Clearance Safety:** Absolute prevention of conflicting orthogonal greens that could lead to physical vehicular collisions.
3. **Emergency Corridor Bandwidth:** Prevention of Denial-of-Service (DoS) attacks that starve genuine ambulances of preemption priority.
4. **Computational Verification Quota:** Protection of the gateway CPU from verification resource exhaustion attacks.

### 1.2 Adversary Capabilities
We consider an active network and physical adversary capable of:
- **Eavesdropping:** Sniffing cleartext V2I messages broadcast over the radio medium.
- **Message Injection & Replay:** Fabricating arbitrary preemption requests or retransmitting recorded packets.
- **Telemetry Falsification:** Reporting fabricated GPS coordinates, speeds, and acceleration profiles via Software-Defined Radios (SDR).
- **Compromised Vehicle IDs:** Impersonating legitimate municipal fleet identifiers.

### 1.3 Trust Boundaries
- **Untrusted Zone:** All vehicular telemetry, radio frequency transmissions, and incoming HTTP preemption requests from external clients.
- **Perimeter Firewall:** The `SecurityAgent` in [clearpath/agents/security.py](file:///a:/CLEARPATH/clearpath/agents/security.py), which enforces cryptographic and kinematic gates before admitting requests.
- **Trusted Zone:** The internal event engine, `DispatcherAgent`, and `JunctionAgents`. Only pre-authenticated requests can trigger pathfinding or signal override actions.

---

## 2. Attack Defense Matrix

The following table details every attack vector evaluated in the ClearPath security audit suite, the corresponding defense mechanism, the diagnostic reason code emitted, and the unit test proving enforcement:

| Attack Vector | Adversary Action | Defense Mechanism | Reason Code | Proving Test |
|---|---|---|:---:|---|
| **Forged Signature** | Altered cryptographic signature or tampered payload. | HMAC-SHA256 signature verification fails constant-time check. | `TOKEN` | `test_security.py::test_tampered_signature_blocked`<br>`test_tokens.py::test_tampered_signature_fails` |
| **Expired Token** | Transmitting an authentic token older than TTL ($>60\text{ s}$). | Token age exceeds `token_ttl_s` configuration limit. | `TOKEN` | `test_security.py::test_expired_token_blocked` |
| **Future Drift** | Token timestamp drifted ahead of system clock ($>5\text{ s}$). | Timestamp violates `clock_skew_s` threshold. | `TOKEN` | `test_security.py::test_counters_and_audit_trail` |
| **Nonce Replay** | Replaying a previously observed valid token. | Single-use nonce match in `_nonces` replay cache. | `TOKEN` | `test_security.py::test_replayed_nonce_blocked` |
| **Kinematic Overspeed** | Valid token, but vehicle reports speed $>180\text{ km/h}$ ($50\text{ m/s}$). | Speed exceeds road posted limit $\times 1.5$ and ambulance ceiling ($25\text{ m/s}$). | `SPEED_LIMIT` | `test_security.py::test_speeding_on_residential_blocked` |
| **GPS Teleportation** | Vehicle jumps $800\text{ m}$ across grid in $1.0\text{ s}$. | Distance leap exceeds $(v_{\max} \cdot \Delta t) + \text{position\_tolerance\_m}$. | `CONTINUITY` | `test_security.py::test_teleport_blocked` |
| **Off-Road Location** | Coordinates do not project onto claimed road edge. | Geometric distance to segment $> \text{position\_tolerance\_m}$ ($30\text{ m}$). | `POSITION_ON_ROAD` | `test_security.py::test_off_road_position_blocked` |
| **Heading Mismatch** | Vehicle vector opposes road bearing ($>35^\circ$). | Heading deviation increments soft risk score; blocks if $\text{risk} > 0.6$. | `HEADING_MATCH` | `test_security.py::test_acceleration_flags_without_risk_and_heading_blocks` |
| **Excess Acceleration** | Vehicle reports acceleration $> 4.0\text{ m/s}^2$. | Telemetry acceleration magnitude flagged for audit analysis. | `ACCELERATION` | `test_security.py::test_acceleration_flags_without_risk_and_heading_blocks` |
| **Unauthorized Vehicle** | Legitimate token created using unauthorized fleet ID. | Vehicle ID not present in `authorized_vehicle_ids` set. | `UNAUTHORIZED_VEHICLE` | `test_security.py::test_unknown_vehicle_blocked` |
| **Request Flooding** | Flooding $>6$ requests/min from a single vehicle. | Sliding-window per-vehicle rate limiter triggers. | `RATE_LIMIT` | `test_security.py::test_rate_limit_flood_blocked` |
| **HMAC CPU Exhaustion** | Flooding invalid tokens to exhaust gateway verification CPU. | Pre-check circuit breaker throttles saturated claimed IDs before HMAC. | `RATE_LIMIT` | `test_security.py::test_forged_token_flood_is_throttled_without_consuming_quota` |
| **Mid-Route Violation** | Vehicle drives dangerously after initial corridor grant. | `validate_stream()` detects anomaly and broadcasts `RevokePreemption`. | `REVOKE` | `test_security.py::test_mid_route_revocation_published` |
| **Memory Exhaustion** | Flooding millions of nonces to bloat replay cache RAM. | Bounded replay cache enforces FIFO eviction at `max_replay_cache_size`. | Bounded Cache | `test_security.py::test_replay_cache_capacity_is_bounded` |

---

## 3. Cryptographic Token Design

### 3.1 Token Format
ClearPath preemption credentials utilize a compact, URL-safe dot-delimited string format implemented in [clearpath/agents/tokens.py](file:///a:/CLEARPATH/clearpath/agents/tokens.py):

$$\text{Token} = \langle\text{vehicle\_id}\rangle.\langle\text{nonce}\rangle.\langle\text{timestamp}\rangle.\langle\text{signature}\rangle$$

- **`vehicle_id`:** Unique alphanumeric emergency fleet identifier (e.g., `"AMB_1"`).
- **`nonce`:** Cryptographic single-use nonce (UUID4 or high-entropy string).
- **`timestamp`:** UTC simulation seconds formatted as a floating-point string (e.g., `"124.0"`).
- **`signature`:** Unpadded Base64URL-encoded HMAC-SHA256 digest computed over the canonical payload:
  $$\text{Payload} = \text{vehicle\_id} \,\|\, "|" \,\|\, \text{nonce} \,\|\, "|" \,\|\, \text{timestamp}$$

### 3.2 HMAC-SHA256 Verification & Constant-Time Comparison
Signature verification in `verify_token()` strictly enforces constant-time equality checks using Python's `hmac.compare_digest()`:

```python
# clearpath/agents/tokens.py:72-80
payload = f"{vehicle_id}|{nonce}|{ts_text}"
digest = hmac.new(
    secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
).digest()
expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

if not hmac.compare_digest(expected.encode("ascii"), provided):
    return False, "BAD_SIGNATURE", {}
```

This prevents side-channel timing attacks where an adversary iteratively guesses signature bytes by measuring server microsecond response latencies.

### 3.3 Architectural Rationale: Why JWT is Not Used
JSON Web Tokens (JWT) were intentionally excluded in favor of custom HMAC tokens for four engineering reasons:
1. **Zero External Dependencies:** Eliminates reliance on heavy third-party packages (`pyjwt`), maintaining a lean dependency footprint.
2. **Algorithm Confusion Elimination:** Standard JWT libraries parse the `alg` header from the untrusted token payload, introducing attack vectors such as the notorious `alg: none` exploit or RSA/HMAC public key confusion. ClearPath pins the cryptographic primitive strictly to HMAC-SHA256 in code.
3. **Payload Overhead Reduction:** V2I wireless telemetry packets require minimal transmission byte overhead. ClearPath tokens pack necessary authorization fields into $<100$ bytes without JSON object serialization bloat.
4. **Header Malleability Prevention:** Fixed-field dot syntax prevents header tampering and parser exploitation.

---

## 4. Secret Management & Operational Environment

ClearPath uses a shared symmetric secret key to authenticate fleet requests:
- **Production Environment:** The shared secret must be configured via the `CLEARPATH_SECRET` environment variable:
  ```bash
  # Linux / macOS
  export CLEARPATH_SECRET="your-high-entropy-production-key-here"

  # Windows (PowerShell)
  $env:CLEARPATH_SECRET="your-high-entropy-production-key-here"
  ```
- **Development Safeguards:** If `CLEARPATH_SECRET` is unset, the system defaults to `clearpath-dev-secret-key-12345`. To prevent accidental deployment in production, [clearpath/config.py](file:///a:/CLEARPATH/clearpath/config.py#L113-L122) emits a prominent warning on startup:
  ```
  UserWarning: SECURITY WARNING: Using insecure development default HMAC secret! 
  Set CLEARPATH_SECRET environment variable in production.
  ```
- **Test Suite Isolation:** In [tests/conftest.py](file:///a:/CLEARPATH/tests/conftest.py), `CLEARPATH_SECRET` is programmatically set to a dedicated test secret, suppressing spurious warnings during test runs while keeping production checks active.

---

## 5. Kinematic Telemetry Validation

A preemption system cannot rely on cryptography alone; an attacker who steals an authorized key must not be allowed to freeze city intersections from a bedroom. The `SecurityAgent` validates kinematic claims against physical road reality:

1. **Projection onto Road Geometry:**
   Coordinates $(x, y)$ are projected onto vector $\vec{AB}$ of the reported road segment:
   $$t = \frac{(\vec{P} - \vec{A}) \cdot (\vec{B} - \vec{A})}{\|\vec{B} - \vec{A}\|^2}, \quad 0 \le t \le 1$$
   The perpendicular distance $\|\vec{P} - \vec{P}_{\text{proj}}\|$ must not exceed `position_tolerance_m` ($30.0\text{ m}$).
2. **Velocity Limits:**
   Reported speed cannot exceed the structural ceiling of the vehicle ($25.0\text{ m/s}$) or $1.5\times$ the posted road speed limit.
3. **Spatio-Temporal Continuity:**
   The spatial displacement between successive telemetry frames must satisfy:
   $$\|\vec{P}_t - \vec{P}_{t-\Delta t}\| \le (v_{\text{amb\_max}} \cdot \Delta t) + \text{position\_tolerance\_m}$$
   Any displacement exceeding this physical reach is flagged as `CONTINUITY` and immediately blocked.

---

## 6. Known Security Limitations

While robust against spoofing and tampering, ClearPath-lite has documented architectural limitations:
- **In-Process Communication:** The simulated `MessageBus` resides in the same Python process memory space. In physical deployment, an encrypted network transport (e.g., mTLS, WireGuard, or IEEE 802.11bd V2X) must be introduced.
- **Symmetric Key Sharing:** All emergency fleet vehicles and the gateway currently share a symmetric key. A compromised vehicle key requires re-keying the gateway. Future versions will support asymmetric signatures (ECDSA / Ed25519) with per-vehicle certificates.
- **No Dynamic Key Rotation:** Automatic key rolling over time-bound epochs is not yet implemented.
- **GPS Multipath Slack:** The $30\text{ m}$ position tolerance accounts for urban GPS drift but allows minor spatial deviation.

---

## 7. Cross-Document References
- For message formats and sequence diagrams, see [MESSAGE_PROTOCOL.md](MESSAGE_PROTOCOL.md).
- For empirical attack block rates and audit outputs, see [RESULTS.md](RESULTS.md).
- For test suite verification scripts, see [TESTING.md](TESTING.md).

