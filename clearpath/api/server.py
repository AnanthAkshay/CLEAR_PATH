"""FastAPI application providing REST endpoints for simulation control and telemetry.

Wraps the ClearPath simulation engine (Orchestrator) with a thin HTTP API so that
external clients and test suites can drive the simulation, submit emergency
preemption requests, and query live state without coupling to Python internals.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from clearpath.bus.messages import PreemptionRequest, Telemetry
from clearpath.config import SimConfig, load_config
from clearpath.engine.orchestrator import ClearPathEngine

logger = logging.getLogger("clearpath.api.server")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _msg_to_dict(msg: Any) -> Dict[str, Any]:
    """Serialise a Message (or any dataclass) to a plain dict.

    Always includes the canonical base fields; extra type-specific fields are
    included via ``dataclasses.asdict`` when available.
    """
    if msg is None:
        return {}
    if dataclasses.is_dataclass(msg):
        raw = dataclasses.asdict(msg)
    else:
        raw = vars(msg) if hasattr(msg, "__dict__") else {}
    # Guarantee the base fields are present.
    return {
        "id": raw.get("id", ""),
        "ts": raw.get("ts", 0.0),
        "sender": raw.get("sender", ""),
        "recipient": raw.get("recipient", ""),
        "type": raw.get("type", type(msg).__name__),
        **{k: v for k, v in raw.items() if k not in {"id", "ts", "sender", "recipient", "type"}},
    }


def _dispatch_to_dict(dispatch: Any) -> Optional[Dict[str, Any]]:
    """Convert a dispatcher result to a JSON-serialisable dict."""
    if dispatch is None:
        return None
    if isinstance(dispatch, dict):
        # Recursively serialise any nested dataclasses.
        out: Dict[str, Any] = {}
        for k, v in dispatch.items():
            if dataclasses.is_dataclass(v):
                out[k] = dataclasses.asdict(v)
            elif isinstance(v, list):
                out[k] = [
                    dataclasses.asdict(i) if dataclasses.is_dataclass(i) else i
                    for i in v
                ]
            else:
                out[k] = v
        return out
    if dataclasses.is_dataclass(dispatch):
        return dataclasses.asdict(dispatch)
    return {}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_engine: Optional[ClearPathEngine] = None


def get_engine() -> ClearPathEngine:
    """FastAPI dependency that returns (or lazily creates) the global engine."""
    global _engine
    if _engine is None:
        logger.info("Creating default ClearPathEngine singleton.")
        _engine = ClearPathEngine(load_config(), preemption_enabled=True)
    return _engine


def create_engine(
    config: Optional[SimConfig] = None,
    preemption_enabled: bool = True,
) -> ClearPathEngine:
    """Replace the module-level singleton with a custom engine.

    Intended for use in tests or external orchestration so callers can inject
    a pre-configured engine before the first request arrives.

    Args:
        config: Optional simulation configuration; defaults are used if None.
        preemption_enabled: Whether the engine should process preemption requests.

    Returns:
        The newly created :class:`ClearPathEngine` instance (also set globally).
    """
    global _engine
    _engine = ClearPathEngine(config, preemption_enabled=preemption_enabled)
    return _engine


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class TelemetryBody(BaseModel):
    """Kinematic snapshot of the requesting emergency vehicle."""

    x: float = 0.0
    y: float = 0.0
    speed_mps: float = 0.0
    accel_mps2: float = 0.0
    heading_deg: float = 0.0
    edge_id: str = "j_0_0_j_0_1"
    lane: int = 0
    vehicle_id: str = "AMB_1"


class EmergencyRequestBody(BaseModel):
    """Payload for POST /emergency."""

    vehicle_id: str = Field(..., examples=["AMB_1"])
    token: str = Field(..., examples=["<hmac-token>"])
    nonce: str = Field(..., examples=["AMB_1-0"])
    incident_loc: List[float] = Field(default=[0.0, 0.0], min_length=2, max_length=2)
    severity: str = Field(default="HIGH", examples=["HIGH"])
    telemetry: TelemetryBody = Field(default_factory=TelemetryBody)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ClearPath-lite API",
    description="Emergency ambulance preemption & urban traffic management system",
    version="0.2.0",
)


# ------------------------------------------------------------------
# GET /health
# ------------------------------------------------------------------


@app.get("/health", summary="Service health check")
def health_check(engine: ClearPathEngine = Depends(get_engine)) -> Dict[str, Any]:
    """Return service liveness status and current simulation tick."""
    return {
        "status": "ok",
        "service": "clearpath-lite",
        "tick": engine.current_tick,
    }


# ------------------------------------------------------------------
# GET /state
# ------------------------------------------------------------------


@app.get("/state", summary="Full simulation state snapshot")
def get_state(engine: ClearPathEngine = Depends(get_engine)) -> Dict[str, Any]:
    """Return a full JSON snapshot of the current simulation world state."""
    try:
        return engine.snapshot()
    except Exception as exc:
        logger.exception("Failed to build state snapshot")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------
# GET /metrics
# ------------------------------------------------------------------


@app.get("/metrics", summary="Aggregated simulation metrics")
def get_metrics(engine: ClearPathEngine = Depends(get_engine)) -> Dict[str, Any]:
    """Return aggregated performance and throughput metrics."""
    try:
        return engine.metrics.summary()
    except Exception as exc:
        logger.exception("Failed to build metrics summary")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------
# GET /messages
# ------------------------------------------------------------------


@app.get("/messages", summary="Recent bus messages")
def get_messages(
    limit: int = Query(default=50, ge=1, le=1000, description="Maximum messages to return"),
    engine: ClearPathEngine = Depends(get_engine),
) -> List[Dict[str, Any]]:
    """Return the last *limit* messages from the simulation message bus."""
    try:
        log = engine.bus.message_log
        recent = log[-limit:] if len(log) > limit else log
        return [_msg_to_dict(m) for m in recent]
    except Exception as exc:
        logger.exception("Failed to retrieve message log")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------
# POST /step
# ------------------------------------------------------------------


@app.post("/step", summary="Advance simulation ticks")
def step_simulation(
    n: int = Query(default=1, ge=1, le=1000, description="Number of ticks to advance"),
    engine: ClearPathEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """Advance the simulation by *n* ticks and return the new world state."""
    try:
        for _ in range(n):
            engine.step()
        return engine.snapshot()
    except Exception as exc:
        logger.exception("Failed to advance simulation")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------
# POST /reset
# ------------------------------------------------------------------


@app.post("/reset", summary="Reset the simulation engine")
def reset_simulation(
    seed: Optional[int] = Query(default=None, description="Optional RNG seed override"),
    engine: ClearPathEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """Reset the simulation to its initial state, optionally with a new seed."""
    try:
        engine.reset(seed=seed)
        return {"status": "reset", "seed": seed, "tick": engine.current_tick}
    except Exception as exc:
        logger.exception("Failed to reset simulation")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------
# POST /emergency
# ------------------------------------------------------------------


@app.post("/emergency", summary="Submit an emergency preemption request")
def submit_emergency(
    body: EmergencyRequestBody,
    engine: ClearPathEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """Authenticate an emergency vehicle and compute a corridor route plan.

    Returns the security auth verdict and, when authenticated, the full
    dispatcher result including path nodes and per-junction ETAs.
    """
    try:
        telemetry = Telemetry(
            x=body.telemetry.x,
            y=body.telemetry.y,
            speed_mps=body.telemetry.speed_mps,
            accel_mps2=body.telemetry.accel_mps2,
            heading_deg=body.telemetry.heading_deg,
            edge_id=body.telemetry.edge_id,
            lane=body.telemetry.lane,
            vehicle_id=body.telemetry.vehicle_id,
            sender=body.vehicle_id,
            recipient="security",
        )
        request = PreemptionRequest(
            vehicle_id=body.vehicle_id,
            token=body.token,
            nonce=body.nonce,
            incident_loc=(body.incident_loc[0], body.incident_loc[1]),
            severity=body.severity,
            telemetry=telemetry,
            sender=body.vehicle_id,
            recipient="security",
        )
        result = engine.submit_emergency_request(request)
        auth = result.get("auth")
        dispatch = result.get("dispatch")
        return {
            "authenticated": result["authenticated"],
            "auth": _msg_to_dict(auth) if auth is not None else None,
            "dispatch": _dispatch_to_dict(dispatch) if dispatch is not None else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to process emergency request for %s", body.vehicle_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
