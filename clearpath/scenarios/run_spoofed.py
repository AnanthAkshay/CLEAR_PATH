"""Scenario 3: Spoofed preemption request injection and rejection test.

Injects 6 distinct cyber-physical attack vectors in sequence:
  (a) Forged HMAC signature
  (b) Expired token (stale timestamp)
  (c) Replay of a previously valid request (duplicate nonce)
  (d) Valid token but excessive telemetry speed (180 km/h on urban arterial)
  (e) Valid token but discontinuous GPS position teleport
  (f) Valid cryptographic token for an unauthorized vehicle ID (outside fleet)

Interleaved with one legitimate preemption request.
Verifies:
  - 6/6 attacks are blocked
  - 1/1 legitimate request is authenticated and allowed
  - Zero signal overrides are triggered by any of the attacks
  - Prints audit trail table and security block rate
"""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from clearpath.agents.tokens import issue_token
from clearpath.bus.messages import PreemptionRequest, Telemetry
from clearpath.config import load_config
from clearpath.engine.orchestrator import ClearPathEngine

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("scenarios.run_spoofed")


def _count_overrides(engine: ClearPathEngine) -> int:
    """Count how many traffic signal controllers currently have an active preemption override."""
    return sum(1 for ctrl in engine.sim.signals.values() if ctrl.is_preempted)


def run(seed: int = 42, demand: str = "med", ticks: int = 50) -> Dict[str, Any]:
    """Execute the multi-vector spoofed preemption scenario and return security audit metrics.

    Parameters
    ----------
    seed : int
        RNG seed for simulation determinism.
    demand : str
        Traffic demand level ('low', 'med', 'high').
    ticks : int
        Simulation ticks to run (default 50).

    Returns
    -------
    dict
        Security metrics including attack block rate, audit records, and signal isolation check.
    """
    logger.info("Starting Scenario 3: Spoofed Attack Injection (seed=%d, demand=%s)", seed, demand)

    # Configure authorized fleet with specific vehicle IDs
    fleet = frozenset({"AMB_1", "AMB_2"})
    config = load_config(seed=seed, max_ticks=ticks, authorized_vehicle_ids=fleet)
    engine = ClearPathEngine(config, preemption_enabled=True, demand_level=demand)

    # Warm up simulation for a few ticks
    for _ in range(5):
        engine.step()

    now_t = float(engine.current_tick)
    secret = config.hmac_secret
    audit_records: List[Dict[str, Any]] = []

    # Helper to test an injection
    def test_request(
        name: str,
        category: str,
        req: PreemptionRequest,
        is_attack: bool,
        expected_allowed: bool,
        expected_reason_substr: Optional[str] = None,
    ) -> bool:
        overrides_before = _count_overrides(engine)
        res = engine.submit_emergency_request(
            req,
            incident_type="cardiac",
            ground_truth_valid=(not is_attack),
        )
        overrides_after = _count_overrides(engine)

        auth_ok = res.get("authenticated", False)
        auth_obj = res.get("auth")
        reasons = list(getattr(auth_obj, "reasons", [])) if auth_obj else []
        risk = float(getattr(auth_obj, "risk_score", 0.0)) if auth_obj else 0.0

        # Check signal override isolation: attacks must NOT increase signal overrides
        new_overrides = max(0, overrides_after - overrides_before)
        overrides_caused = new_overrides if is_attack else 0

        passed = (auth_ok == expected_allowed)
        if is_attack and overrides_caused > 0:
            passed = False
        if expected_reason_substr and not any(expected_reason_substr in r for r in reasons):
            passed = False

        audit_records.append({
            "name": name,
            "category": category,
            "is_attack": is_attack,
            "vehicle_id": req.vehicle_id,
            "nonce": req.nonce,
            "authenticated": auth_ok,
            "reasons": reasons,
            "risk_score": risk,
            "overrides_caused": overrides_caused,
            "expected_allowed": expected_allowed,
            "passed": passed,
        })
        return passed

    # -------------------------------------------------------------------------
    # 1. Attack (a): Forged HMAC Signature
    # -------------------------------------------------------------------------
    t_forged = issue_token("AMB_1", "nonce_forged", now_t, secret) + "_TAMPERED"
    req_a = PreemptionRequest(
        vehicle_id="AMB_1",
        token=t_forged,
        nonce="nonce_forged",
        incident_loc=(0.0, 0.0),
        severity="CRITICAL",
        telemetry=Telemetry(
            x=0.0, y=0.0, speed_mps=10.0, accel_mps2=0.0, heading_deg=90.0,
            edge_id="j_0_0_j_0_1", lane=0, vehicle_id="AMB_1",
        ),
        sender="attacker",
    )
    test_request(
        "(a) Forged HMAC", "Cryptographic", req_a,
        is_attack=True, expected_allowed=False, expected_reason_substr="TOKEN",
    )

    # -------------------------------------------------------------------------
    # 2. Attack (b): Expired Token (Stale Timestamp)
    # -------------------------------------------------------------------------
    t_expired = issue_token("AMB_1", "nonce_expired", now_t - 120.0, secret)
    req_b = PreemptionRequest(
        vehicle_id="AMB_1",
        token=t_expired,
        nonce="nonce_expired",
        incident_loc=(0.0, 0.0),
        severity="CRITICAL",
        telemetry=Telemetry(
            x=0.0, y=0.0, speed_mps=10.0, accel_mps2=0.0, heading_deg=90.0,
            edge_id="j_0_0_j_0_1", lane=0, vehicle_id="AMB_1",
        ),
        sender="attacker",
    )
    test_request(
        "(b) Expired Token", "Cryptographic", req_b,
        is_attack=True, expected_allowed=False, expected_reason_substr="TOKEN",
    )

    # -------------------------------------------------------------------------
    # 3. Interleaved Legitimate Request
    # -------------------------------------------------------------------------
    t_legit = issue_token("AMB_1", "nonce_legit_42", now_t, secret)
    req_legit = PreemptionRequest(
        vehicle_id="AMB_1",
        token=t_legit,
        nonce="nonce_legit_42",
        incident_loc=(0.0, 0.0),
        severity="CRITICAL",
        telemetry=Telemetry(
            x=0.0, y=0.0, speed_mps=10.0, accel_mps2=0.0, heading_deg=90.0,
            edge_id="j_0_0_j_0_1", lane=0, vehicle_id="AMB_1",
        ),
        sender="ambulance",
    )
    test_request(
        "[+] Legitimate Request", "Legitimate", req_legit,
        is_attack=False, expected_allowed=True,
    )

    # -------------------------------------------------------------------------
    # 4. Attack (c): Replay of Previously Valid Request
    # -------------------------------------------------------------------------
    test_request(
        "(c) Replay Attack", "Cryptographic", req_legit,
        is_attack=True, expected_allowed=False, expected_reason_substr="TOKEN",
    )

    # -------------------------------------------------------------------------
    # 5. Attack (d): Valid Token but 180 km/h Telemetry (50.0 m/s on arterial)
    # -------------------------------------------------------------------------
    t_overspeed = issue_token("AMB_1", "nonce_overspeed", now_t, secret)
    req_d = PreemptionRequest(
        vehicle_id="AMB_1",
        token=t_overspeed,
        nonce="nonce_overspeed",
        incident_loc=(0.0, 0.0),
        severity="CRITICAL",
        telemetry=Telemetry(
            x=50.0, y=0.0, speed_mps=50.0, accel_mps2=0.0, heading_deg=90.0,
            edge_id="j_0_0_j_0_1", lane=0, vehicle_id="AMB_1",
        ),
        sender="attacker",
    )
    test_request(
        "(d) 180 km/h Overspeed", "Kinematic", req_d,
        is_attack=True, expected_allowed=False, expected_reason_substr="SPEED_LIMIT",
    )

    # -------------------------------------------------------------------------
    # 6. Attack (e): Valid Token but Discontinuous Position Teleport
    # -------------------------------------------------------------------------
    t_teleport = issue_token("AMB_1", "nonce_teleport", now_t, secret)
    req_e = PreemptionRequest(
        vehicle_id="AMB_1",
        token=t_teleport,
        nonce="nonce_teleport",
        incident_loc=(800.0, 800.0),
        severity="CRITICAL",
        telemetry=Telemetry(
            x=800.0, y=800.0, speed_mps=10.0, accel_mps2=0.0, heading_deg=90.0,
            edge_id="j_4_4_j_4_5", lane=0, vehicle_id="AMB_1",
        ),
        sender="attacker",
    )
    test_request(
        "(e) Position Teleport", "Kinematic", req_e,
        is_attack=True, expected_allowed=False, expected_reason_substr="CONTINUITY",
    )

    # -------------------------------------------------------------------------
    # 7. Attack (f): Valid Token for Unauthorized Vehicle ID
    # -------------------------------------------------------------------------
    t_unauth = issue_token("AMB_999", "nonce_unauth", now_t, secret)
    req_f = PreemptionRequest(
        vehicle_id="AMB_999",
        token=t_unauth,
        nonce="nonce_unauth",
        incident_loc=(0.0, 0.0),
        severity="CRITICAL",
        telemetry=Telemetry(
            x=0.0, y=0.0, speed_mps=10.0, accel_mps2=0.0, heading_deg=90.0,
            edge_id="j_0_0_j_0_1", lane=0, vehicle_id="AMB_999",
        ),
        sender="attacker",
    )
    test_request(
        "(f) Unauthorized Vehicle", "Authorization", req_f,
        is_attack=True, expected_allowed=False, expected_reason_substr="UNAUTHORIZED_VEHICLE",
    )

    # -------------------------------------------------------------------------
    # Summarize & Verify
    # -------------------------------------------------------------------------
    total_attacks = sum(1 for r in audit_records if r["is_attack"])
    attacks_blocked = sum(1 for r in audit_records if r["is_attack"] and not r["authenticated"])
    legit_total = sum(1 for r in audit_records if not r["is_attack"])
    legit_allowed = sum(1 for r in audit_records if not r["is_attack"] and r["authenticated"])
    legit_blocked = legit_total - legit_allowed
    total_overrides_from_attacks = sum(r["overrides_caused"] for r in audit_records if r["is_attack"])

    all_passed = all(r["passed"] for r in audit_records)
    attack_block_rate = attacks_blocked / max(1, total_attacks)
    false_positive_rate = legit_blocked / max(1, legit_total)

    # Print formatted audit table
    sep = "=" * 80
    div = "-" * 80
    print("\n" + sep)
    print("CLEARPATH-LITE SECURITY GATEWAY AUDIT REPORT (6 ATTACKS + 1 LEGITIMATE)")
    print(sep)
    print(f"{'Attack / Request Description':<30} {'Type':<15} {'Allowed':<10} {'Reasons':<14} {'Result':<8}")
    print(div)
    for r in audit_records:
        allowed_str = "YES" if r["authenticated"] else "BLOCKED"
        reasons_str = ",".join(r["reasons"]) if r["reasons"] else "none"
        result_str = "[PASS]" if r["passed"] else "[FAIL]"
        print(f"{r['name']:<30} {r['category']:<15} {allowed_str:<10} {reasons_str:<14} {result_str:<8}")
    print(sep)
    print(f"Attack Block Rate        : {attacks_blocked}/{total_attacks} ({attack_block_rate * 100.0:.1f}%)")
    print(f"False-Positive Rate      : {legit_blocked}/{legit_total} ({false_positive_rate * 100.0:.1f}%)")
    print(f"Legitimate Allowed       : {legit_allowed}/{legit_total} ({(legit_allowed/legit_total) * 100.0:.1f}%)")
    print(f"Signal Overrides From Attacks: {total_overrides_from_attacks} (zero signal corruption)")
    print(sep)

    print(f"[ASSERT {'PASS' if attacks_blocked == total_attacks else 'FAIL'}] Verified 6/6 attacks blocked.")
    print(f"[ASSERT {'PASS' if legit_allowed == legit_total else 'FAIL'}] Verified 1/1 legitimate request allowed.")
    print(f"[ASSERT {'PASS' if total_overrides_from_attacks == 0 else 'FAIL'}] Verified 0 signal overrides from attacks.\n")

    assert attacks_blocked == 6, f"Expected 6 attacks blocked, got {attacks_blocked}"
    assert legit_allowed == 1, f"Expected 1 legitimate allowed, got {legit_allowed}"
    assert total_overrides_from_attacks == 0, f"Expected 0 overrides from attacks, got {total_overrides_from_attacks}"

    return {
        "status": "PASS" if all_passed else "FAIL",
        "scenario": "run_spoofed",
        "seed": seed,
        "demand": demand,
        "ticks": ticks,
        "total_requests": len(audit_records),
        "attacks_total": total_attacks,
        "attacks_blocked": attacks_blocked,
        "legitimate_total": legit_total,
        "legitimate_allowed": legit_allowed,
        "legitimate_blocked": legit_blocked,
        "attack_block_rate": round(attack_block_rate, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "signal_overrides_from_attacks": total_overrides_from_attacks,
        "audit_table": audit_records,
    }


def main() -> None:
    """Run spoofed preemption multi-vector attack test."""
    run(seed=42, demand="med", ticks=50)


if __name__ == "__main__":
    main()
