"""FastAPI application providing REST endpoints for simulation control and telemetry."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="ClearPath-lite API",
    description="Emergency ambulance preemption & urban traffic management system",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok", "service": "clearpath-lite"}

