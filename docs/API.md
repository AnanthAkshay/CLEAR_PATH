# ClearPath-lite REST API Specification

The ClearPath-lite FastAPI service ([clearpath/api/server.py](file:///a:/CLEARPATH/clearpath/api/server.py)) provides HTTP endpoints for external orchestrators, hardware test harnesses, and automated benchmarks to control the simulation, query live state, and submit preemption requests.

## Table of Contents
- [1. Service Overview & Concurrency Model](#1-service-overview--concurrency-model)
- [2. Endpoints Catalog](#2-endpoints-catalog)
  - [2.1 GET /health](#21-get-health)
  - [2.2 GET /state](#22-get-state)
  - [2.3 GET /metrics](#23-get-metrics)
  - [2.4 GET /messages](#24-get-messages)
  - [2.5 POST /step](#25-post-step)
  - [2.6 POST /reset](#26-post-reset)
  - [2.7 POST /emergency](#27-post-emergency)
- [3. Error Handling & Validation Failures](#3-error-handling--validation-failures)
- [4. Cross-Document References](#4-cross-document-references)

---

## 1. Service Overview & Concurrency Model

### 1.1 Launching the API
The REST API runs on Uvicorn:
```bash
python -m uvicorn clearpath.api.server:app --host 127.0.0.1 --port 8000
```
Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

### 1.2 Concurrency Guarantees (`asyncio.Lock`)
Because the underlying simulation engine maintains discrete sequential state, concurrent HTTP requests could cause state corruption if executed simultaneously.

All state-mutating handlers (`/step`, `/reset`, and `/emergency`) are strictly guarded by an asynchronous lock:
```python
# clearpath/api/server.py:84-90, 239
_engine_lock: Optional[asyncio.Lock] = None

def get_engine_lock() -> asyncio.Lock:
    global _engine_lock
    if _engine_lock is None:
        _engine_lock = asyncio.Lock()
    return _engine_lock

# Inside mutating endpoints:
async with get_engine_lock():
    engine.step()
```
This guarantees thread-safe serialization: multiple concurrent clients sending requests will execute sequentially without race conditions. Verified in `tests/test_api.py::test_concurrent_step_calls_consistency`.

---

## 2. Endpoints Catalog

### 2.1 GET /health
Returns service liveness status and current simulation tick.

- **Method:** `GET`
- **Path:** `/health`
- **Response Schema:**
  ```json
  {
    "status": "string",
    "service": "string",
    "tick": "integer"
  }
  ```
- **Executed `curl` Command:**
  ```bash
  curl.exe -s http://127.0.0.1:8000/health
  ```
- **Live Output:**
  ```json
  {"status":"ok","service":"clearpath-lite","tick":0}
  ```

---

### 2.2 GET /state
Returns a full JSON snapshot of the current simulation world state.

- **Method:** `GET`
- **Path:** `/state`
- **Response Schema:**
  ```json
  {
    "tick": "integer",
    "preemption_enabled": "boolean",
    "vehicles": [
      {
        "id": "string",
        "kind": "string",
        "edge": ["string", "string"],
        "offset_m": "float",
        "speed_mps": "float",
        "lane": "integer",
        "x": "float",
        "y": "float",
        "heading_deg": "float",
        "is_stopped": "boolean",
        "wait_time_s": "float"
      }
    ],
    "signals": {"<junction_id>": "string"},
    "queues": {"<edge_id>": "integer"},
    "densities": {"<edge_id>": "float"},
    "active_ambulances": ["string"],
    "vms_board": {"<junction_id>": "string"}
  }
  ```
- **Executed `curl` Command:**
  ```bash
  curl.exe -s http://127.0.0.1:8000/state
  ```

---

### 2.3 GET /metrics
Returns aggregated performance, throughput, and security gateway counters.

- **Method:** `GET`
- **Path:** `/metrics`
- **Response Schema:**
  ```json
  {
    "ticks_elapsed": "integer",
    "ambulance_travel_time_s": "float | null",
    "ambulance_stops": "integer",
    "ambulance_stopped_time_s": "float",
    "ambulance_improvement_pct": "float | null",
    "cross_delay_avg_s": "float",
    "cross_delay_p95_s": "float",
    "network_throughput": "float",
    "network_avg_speed_mps": "float",
    "network_max_queue": "integer",
    "security_total_requests": "integer",
    "security_blocked": "integer",
    "security_attack_block_rate": "float",
    "security_false_positive_rate": "float",
    "negotiation_messages_sent": "integer"
  }
  ```
- **Executed `curl` Command:**
  ```bash
  curl.exe -s http://127.0.0.1:8000/metrics
  ```
- **Live Output:**
  ```json
  {"ticks_elapsed":5,"ambulance_travel_time_s":null,"ambulance_stops":0,"ambulance_stopped_time_s":0,"ambulance_improvement_pct":null,"cross_delay_avg_s":0.0,"cross_delay_p95_s":0.0,"network_throughput":0.0,"network_avg_speed_mps":12.761,"network_max_queue":0,"security_total_requests":0,"security_blocked":0,"security_attack_block_rate":0.0,"security_false_positive_rate":0.0,"negotiation_messages_sent":0}
  ```

---

### 2.4 GET /messages
Returns recent messages passing across the internal simulation message bus.

- **Method:** `GET`
- **Path:** `/messages`
- **Query Parameters:**
  - `limit` (int, default `50`, min `1`, max `1000`): Maximum messages to return.
- **Response Schema:** Array of message dictionaries with base fields (`id`, `ts`, `sender`, `recipient`, `type`) and type-specific payloads.
- **Executed `curl` Command:**
  ```bash
  curl.exe -s "http://127.0.0.1:8000/messages?limit=2"
  ```
- **Live Output:**
  ```json
  []
  ```

---

### 2.5 POST /step
Advances the simulation by $n$ discrete ticks and returns the updated world snapshot.

- **Method:** `POST`
- **Path:** `/step`
- **Query Parameters:**
  - `n` (int, default `1`, min `1`, max `1000`): Number of ticks to step forward.
- **Executed `curl` Command:**
  ```bash
  curl.exe -s -X POST "http://127.0.0.1:8000/step?n=5"
  ```
- **Live Output (Excerpt):**
  ```json
  {
    "tick": 5,
    "preemption_enabled": true,
    "vehicles": [
      {"id":"car_1","kind":"car","edge":["j_0_5","j_0_4"],"offset_m":78.78,"speed_mps":16.59,"lane":0,"x":921.22,"y":0.0,"heading_deg":270.0,"is_stopped":false,"wait_time_s":0.0}
    ],
    "signals": {"j_0_0":"NS_GREEN","j_0_1":"NS_GREEN","j_0_2":"NS_YELLOW","j_0_3":"EW_GREEN"},
    "metrics_summary": {"ticks_elapsed": 5, "network_avg_speed_mps": 12.761}
  }
  ```

---

### 2.6 POST /reset
Resets simulation state, vehicle inventories, and metrics back to tick 0.

- **Method:** `POST`
- **Path:** `/reset`
- **Query Parameters:**
  - `seed` (int, optional): New random seed for subsequent execution.
- **Executed `curl` Command:**
  ```bash
  curl.exe -s -X POST "http://127.0.0.1:8000/reset?seed=123"
  ```
- **Live Output:**
  ```json
  {"status":"reset","seed":123,"tick":0}
  ```

---

### 2.7 POST /emergency
Submits an emergency preemption request with cryptographic credentials and telemetry.

- **Method:** `POST`
- **Path:** `/emergency`
- **Request Body Schema (`EmergencyRequestBody`):**
  ```json
  {
    "vehicle_id": "string",
    "token": "string",
    "nonce": "string",
    "incident_loc": ["float", "float"],
    "severity": "string",
    "telemetry": {
      "x": "float",
      "y": "float",
      "speed_mps": "float",
      "accel_mps2": "float",
      "heading_deg": "float",
      "edge_id": "string",
      "lane": "integer",
      "vehicle_id": "string"
    }
  }
  ```
- **Response Schema:**
  ```json
  {
    "authenticated": "boolean",
    "auth": {
      "id": "string",
      "ts": "float",
      "sender": "string",
      "recipient": "string",
      "type": "string",
      "vehicle_id": "string",
      "is_authenticated": "boolean",
      "reasons": ["string"],
      "security_log": "string",
      "risk_score": "float"
    },
    "dispatch": {
      "vehicle_id": "string",
      "origin": "string",
      "hospital_id": "string",
      "path": ["string"],
      "eta_by_junction": {"<junction_id>": "float"},
      "total_eta_s": "float",
      "ranked": ["object"]
    }
  }
  ```
- **Executed `curl` Command (Valid Request):**
  ```bash
  curl.exe -s -X POST "http://127.0.0.1:8000/emergency" \
    -H "Content-Type: application/json" \
    -d '{
      "vehicle_id": "AMB_1",
      "token": "AMB_1.nonce-1.0.0.4Z13W95oI1dCg_K0wQ9L5v6P8eF",
      "nonce": "nonce-1",
      "incident_loc": [0.0, 0.0],
      "severity": "CRITICAL",
      "telemetry": {
        "x": 0.0, "y": 0.0, "speed_mps": 10.0, "accel_mps2": 0.0,
        "heading_deg": 90.0, "edge_id": "j_0_0_j_0_1", "lane": 0, "vehicle_id": "AMB_1"
      }
    }'
  ```
- **Live Output (Authenticated):**
  ```json
  {
    "authenticated": true,
    "auth": {
      "id": "f4c976ce-a710-4941-9407-0dac2be74484",
      "vehicle_id": "AMB_1",
      "is_authenticated": true,
      "reasons": [],
      "security_log": "vehicle=AMB_1 allowed=True risk=0.00 accepted",
      "risk_score": 0.0
    },
    "dispatch": {
      "vehicle_id": "AMB_1",
      "origin": "j_0_0",
      "hospital_id": "HOSP_RIVERSIDE",
      "path": ["j_0_0", "j_0_1", "j_0_2", "j_1_2", "j_2_2"],
      "eta_by_junction": {
        "j_0_0": 0.0, "j_0_1": 10.0, "j_0_2": 20.0, "j_1_2": 33.86, "j_2_2": 47.72
      },
      "total_eta_s": 47.72,
      "reason": "ok"
    }
  }
  ```

---

## 3. Error Handling & Validation Failures

### 3.1 Security Gateway Rejection (HTTP 200 with `authenticated: false`)
When a request fails cryptographic or kinematic validation, HTTP 200 is returned with diagnostic reason codes so callers can inspect the security verdict without treating it as an HTTP transport error:
```json
{
  "authenticated": false,
  "auth": {
    "vehicle_id": "AMB_1",
    "is_authenticated": false,
    "reasons": ["TOKEN"],
    "security_log": "vehicle=AMB_1 allowed=False risk=0.00 token bad_format reasons=TOKEN",
    "risk_score": 0.0
  },
  "dispatch": null
}
```

### 3.2 Schema Validation Error (HTTP 422 Unprocessable Content)
If mandatory fields are missing from the request JSON:
- **Executed `curl` Command:**
  ```bash
  curl.exe -s -i -X POST "http://127.0.0.1:8000/emergency" \
    -H "Content-Type: application/json" -d "{}"
  ```
- **Live Output:**
  ```http
  HTTP/1.1 422 Unprocessable Content
  content-type: application/json

  {
    "detail": [
      {"type":"missing","loc":["body","vehicle_id"],"msg":"Field required"},
      {"type":"missing","loc":["body","token"],"msg":"Field required"},
      {"type":"missing","loc":["body","nonce"],"msg":"Field required"}
    ]
  }
  ```

---

## 4. Cross-Document References
- For message dataclass formats, see [MESSAGE_PROTOCOL.md](MESSAGE_PROTOCOL.md).
- For security validation rules and HMAC generation, see [SECURITY.md](SECURITY.md).
- For Streamlit UI alternatives to the REST API, see [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md).

