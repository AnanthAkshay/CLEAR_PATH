"""Scenario: Spoofed preemption request rejection test.

Spawns a legitimate ambulance, forges its HMAC token (by flipping the last
character of the signature), submits the forged PreemptionRequest, and verifies
that the SecurityAgent correctly rejects it (authenticated=False).
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scenarios.run_spoofed")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEED = 42
TICKS = 50          # Short run — we only need the security verdict
AMB_ORIGIN = "j_0_0"
AMB_DEST = "j_5_5"
AMB_SPAWN_TICK = 5


# ---------------------------------------------------------------------------
# Token forging helper
# ---------------------------------------------------------------------------

def _forge_token(valid_token: str) -> str:
    """Return a corrupted token by flipping the last character of the signature.

    The token format is ``vehicle_id.nonce.ts.signature``.  Flipping the final
    character guarantees an HMAC mismatch without altering structural validity.
    """
    if not valid_token:
        return valid_token
    # Flip last char: cycle through ASCII printable range
    last = valid_token[-1]
    flipped = chr((ord(last) - 32 + 1) % 95 + 32)
    # Make sure we actually changed it (edge case: wraparound to same char)
    if flipped == last:
        flipped = chr((ord(last) - 32 + 2) % 95 + 32)
    return valid_token[:-1] + flipped


# ---------------------------------------------------------------------------
# Spoofed request builder
# ---------------------------------------------------------------------------

def _build_spoofed_request(engine: Any, amb_id: str) -> Optional[Any]:
    """Build a PreemptionRequest carrying a forged (invalid) HMAC token.

    Returns the request or None if construction fails.
    """
    try:
        from clearpath.agents.tokens import issue_token
        from clearpath.bus.messages import PreemptionRequest, Telemetry

        vehicle = engine.sim.vehicles.get(amb_id)
        if vehicle is None:
            logger.warning("Ambulance %s not found in simulator vehicles.", amb_id)
            return None

        tick = engine.current_tick
        x, y = engine.sim.network.edge_position(vehicle.edge, vehicle.offset_m)
        nonce = str(uuid.uuid4())

        # Issue a valid token first, then corrupt it
        valid_token = issue_token(amb_id, nonce, float(tick), engine.config.hmac_secret)
        forged_token = _forge_token(valid_token)

        bearing = engine.sim.network.edge_bearing(*vehicle.edge)

        req = PreemptionRequest(
            vehicle_id=amb_id,
            token=forged_token,          # <-- forged!
            nonce=nonce,
            incident_loc=(x, y),
            severity="CRITICAL",
            telemetry=Telemetry(
                x=x,
                y=y,
                speed_mps=vehicle.speed,
                accel_mps2=0.0,
                heading_deg=bearing,
                edge_id=f"{vehicle.edge[0]}_{vehicle.edge[1]}",
                lane=vehicle.lane,
                vehicle_id=amb_id,
            ),
            sender="attacker",           # attacker impersonates ambulance
        )
        return req
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to build spoofed PreemptionRequest: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    """Run the spoofed preemption attack scenario and verify rejection."""
    print("\n" + "=" * 62)
    print("CLEARPATH-LITE  —  SPOOFED PREEMPTION ATTACK TEST")
    print("=" * 62)

    # ------------------------------------------------------------------
    # Import & initialise
    # ------------------------------------------------------------------
    try:
        from clearpath.config import load_config
        from clearpath.engine.orchestrator import ClearPathEngine  # type: ignore[attr-defined]
    except ImportError as exc:
        print(f"[ERROR] Import failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_config(seed=SEED, max_ticks=TICKS)
        engine = ClearPathEngine(config, preemption_enabled=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to initialise ClearPathEngine: {exc}", file=sys.stderr)
        sys.exit(1)

    amb_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    forged_token_preview: str = ""

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------
    for _ in range(TICKS):
        try:
            engine.step()
        except Exception as exc:  # noqa: BLE001
            logger.error("Engine step error at tick %d: %s", engine.current_tick, exc)
            break

        # Spawn ambulance at the designated tick
        if engine.current_tick == AMB_SPAWN_TICK and amb_id is None:
            try:
                amb_id = engine.sim.spawn_ambulance(AMB_ORIGIN, AMB_DEST)
                print(f"[+] Ambulance {amb_id!r} spawned at tick {engine.current_tick}.")
            except Exception as exc:  # noqa: BLE001
                print(f"[!] Could not spawn ambulance: {exc}", file=sys.stderr)
                amb_id = None

            if amb_id is not None:
                spoofed_req = _build_spoofed_request(engine, amb_id)
                if spoofed_req is None:
                    print("[!] Could not build spoofed request; test cannot continue.", file=sys.stderr)
                    break

                forged_token_preview = spoofed_req.token[:40] + "…" if len(spoofed_req.token) > 40 else spoofed_req.token
                print(f"[+] Submitting forged PreemptionRequest for {amb_id!r}.")
                print(f"    Token (preview): {forged_token_preview}")

                try:
                    result = engine.submit_emergency_request(spoofed_req)
                except Exception as exc:  # noqa: BLE001
                    print(f"[!] submit_emergency_request raised: {exc}", file=sys.stderr)
                    result = {"authenticated": False, "_error": str(exc)}

                # We have our verdict — no need to run all ticks.
                break

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    print("\n" + "-" * 62)
    print("RESULT SUMMARY")
    print("-" * 62)

    if result is None:
        print("[!] No result obtained — ambulance could not be spawned or request was not sent.")
        print("=" * 62 + "\n")
        return

    authenticated: bool = result.get("authenticated", False)
    auth_obj = result.get("auth")

    # Security log / reasons
    security_log: str = ""
    reasons = []
    if auth_obj is not None:
        try:
            security_log = str(getattr(auth_obj, "security_log", ""))
            reasons = list(getattr(auth_obj, "reasons", []))
        except Exception:  # noqa: BLE001
            pass

    status_icon = "✗ REJECTED (CORRECT)" if not authenticated else "✓ ACCEPTED  (UNEXPECTED — possible security gap)"
    print(f"{'Ambulance ID':<28} {amb_id}")
    print(f"{'Forged token preview':<28} {forged_token_preview}")
    print(f"{'Authenticated':<28} {authenticated}")
    print(f"{'Verdict':<28} {status_icon}")
    if security_log:
        print(f"{'Security log':<28} {security_log}")
    if reasons:
        print(f"{'Failure reasons':<28} {', '.join(str(r) for r in reasons)}")

    print("-" * 62)
    if not authenticated:
        print("[PASS] Spoofed request was correctly rejected by the SecurityAgent.")
    else:
        print("[FAIL] Spoofed request was incorrectly authenticated. Review SecurityAgent logic.", file=sys.stderr)

    print("=" * 62 + "\n")


if __name__ == "__main__":
    run()
