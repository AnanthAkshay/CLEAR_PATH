"""SecurityAgent: HMAC token and kinematic telemetry gatekeeper for preemption."""

from __future__ import annotations

import math
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from clearpath.agents.base import Agent
from clearpath.agents.tokens import verify_token
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import (
    AuthResult, Message, PreemptionRequest, RevokePreemption,
)
from clearpath.config import SimConfig

_RISK_BLOCK = 0.6
_RATE_WINDOW_S = 60.0
_HARD = frozenset(
    {"TOKEN", "RATE_LIMIT", "SPEED_LIMIT", "POSITION_ON_ROAD", "CONTINUITY"}
)


class SecurityAgent(Agent):
    """Gatekeeper that authenticates preemption requests.

    Token, speed, continuity and position failures block outright. Implausible
    acceleration is only flagged in the reasons; heading drift is the sole
    contributor to the risk score, which blocks once it exceeds 0.6.
    """

    def __init__(
        self, agent_id: str, bus: MessageBus, config: SimConfig,
        graph: nx.DiGraph, clock: Any = time.monotonic,
    ) -> None:
        """Initialize the agent with config, road graph and an injectable clock."""
        super().__init__(agent_id, bus)
        self.config = config
        self.graph = graph
        self.clock = clock
        self._nonces: Dict[str, float] = {}
        self._last: Dict[str, Tuple[float, float, Optional[Tuple[str, str]], float]] = {}
        self._requests: Dict[str, List[float]] = {}
        # Agent-wide budget for failed verifications; never keyed on the claimed id.
        self._failures: List[float] = []
        # Per-claimed-id failure history, used only to short-circuit known-bad ids
        # before the HMAC. Ids that have authenticated once are exempt below.
        self._claimed_failures: Dict[str, List[float]] = {}
        self._verified_ids: Set[str] = set()

        self.total_requests = 0
        self.allowed = 0
        self.blocked = 0
        self.reason_counts: Counter[str] = Counter()
        self.audit_trail: List[Dict[str, Any]] = []

    def on_message(self, msg: Message) -> None:
        """Ignore stray messages; requests are checked via authenticate()."""
        return

    def step(self, world_view: Any, t: int) -> None:
        """No per-tick work yet."""
        return

    def authenticate(self, request: PreemptionRequest) -> AuthResult:
        """Validate one preemption request and return the resulting AuthResult."""
        now = self.clock()
        self.total_requests += 1

        reasons: List[str] = []
        risk = 0.0
        allowed = False
        detail = "accepted"

        if self._precheck_blocks(request.vehicle_id, now):
            reasons.append("RATE_LIMIT")
            detail = "claimed id failure bucket saturated"
            return self._result(request, False, reasons, risk, detail, now)

        parsed, token_error = self._check_token(request, now)
        if token_error is not None:
            if self._failures_limited(now):
                reasons.append("RATE_LIMIT")
                detail = "verification failure budget exhausted"
            else:
                self._record_claimed_failure(request.vehicle_id, now)
                reasons.append("TOKEN")
                detail = token_error
        elif self._rate_limited(str(parsed["vehicle_id"]), now):
            reasons.append("RATE_LIMIT")
            detail = "rate limited"
        else:
            vehicle_id = str(parsed["vehicle_id"])
            self._verified_ids.add(vehicle_id)
            telemetry = request.telemetry
            edge = self._edge(telemetry.edge_id)
            reasons, risk = self._telemetry_reasons(telemetry, edge, vehicle_id, now)
            allowed = not (set(reasons) & _HARD) and risk <= _RISK_BLOCK
            detail = "accepted" if allowed else "blocked"
            if allowed:
                self._nonces[str(parsed["nonce"])] = now
                self._last[vehicle_id] = (telemetry.x, telemetry.y, edge, now)
                self._prune_nonces(now)

        return self._result(request, allowed, reasons, risk, detail, now)

    def validate_stream(self, telemetry: Any) -> bool:
        """Re-check an authorized vehicle's telemetry, revoking it if invalid."""
        now = self.clock()
        vehicle_id = telemetry.vehicle_id
        edge = self._edge(telemetry.edge_id)
        reasons, risk = self._telemetry_reasons(telemetry, edge, vehicle_id, now)
        if not (set(reasons) & _HARD) and risk <= _RISK_BLOCK:
            self._last[vehicle_id] = (telemetry.x, telemetry.y, edge, now)
            return True

        self.bus.publish(
            RevokePreemption(
                vehicle_id=vehicle_id,
                reason=",".join(reasons) or "RISK",
                ts=now,
                sender=self.id,
                recipient="*",
            )
        )
        return False

    def _rate_limited(self, vehicle_id: str, now: float) -> bool:
        """Record a token-verified request and report whether it exceeded the quota.

        Callers must pass the vehicle id taken from the verified token. Requests
        that fail token verification never reach this method, so forged traffic
        cannot consume a legitimate vehicle's quota.
        """
        recent = [t for t in self._requests.get(vehicle_id, []) if now - t <= _RATE_WINDOW_S]
        limited = len(recent) >= self.config.rate_limit_per_vehicle_per_min
        if not limited:
            recent.append(now)
        self._requests[vehicle_id] = recent
        return limited

    def _telemetry_reasons(
        self, telemetry: Any, edge: Optional[Tuple[str, str]],
        vehicle_id: str, now: float,
    ) -> Tuple[List[str], float]:
        """Collect telemetry reason codes and the weighted soft risk score."""
        reasons: List[str] = []
        risk = 0.0

        if not self._speed_ok(telemetry, edge):
            reasons.append("SPEED_LIMIT")

        if abs(telemetry.accel_mps2) > self.config.ambulance_max_accel:
            reasons.append("ACCELERATION")

        if not self._position_ok(telemetry, edge):
            reasons.append("POSITION_ON_ROAD")

        if not self._heading_ok(telemetry, edge):
            reasons.append("HEADING_MATCH")
            risk += self.config.risk_weight_heading

        if not self._continuity_ok(telemetry, edge, vehicle_id, now):
            reasons.append("CONTINUITY")

        return reasons, risk

    def _check_token(
        self, request: PreemptionRequest, now: float
    ) -> Tuple[Dict[str, object], Optional[str]]:
        """Return parsed token fields, or an error string explaining the rejection."""
        ok, reason, parsed = verify_token(request.token, self.config.hmac_secret)
        if not ok:
            return {}, "token " + reason.lower()

        issued = float(parsed["ts"])
        if (now - issued) > self.config.token_ttl_s:
            return {}, "token expired"
        if (issued - now) > self.config.clock_skew_s:
            return {}, "token issued in the future"

        fleet = self.config.authorized_vehicle_ids
        if fleet and str(parsed["vehicle_id"]) not in fleet:
            return {}, "vehicle not in authorized fleet"

        if str(parsed["nonce"]) in self._nonces:
            return {}, "nonce already used"

        return parsed, None

    def _precheck_blocks(self, vehicle_id: str, now: float) -> bool:
        """Reject a known-bad claimed id before spending an HMAC verification.

        Eligible only when this id has never authenticated successfully, so a
        forger that saturates a *real* vehicle's bucket cannot lock it out: that
        vehicle is exempt for the rest of its life and is verified normally.
        """
        if vehicle_id in self._verified_ids:
            return False
        return self._claimed_id_saturated(vehicle_id, now)

    def _claimed_id_saturated(self, vehicle_id: str, now: float) -> bool:
        """True once this claimed id has failed often enough to be throttled."""
        recent = [
            t for t in self._claimed_failures.get(vehicle_id, [])
            if now - t <= _RATE_WINDOW_S
        ]
        return len(recent) >= self.config.rate_limit_per_vehicle_per_min

    def _record_claimed_failure(self, vehicle_id: str, now: float) -> None:
        """Count one failed verification against the claimed id."""
        recent = [
            t for t in self._claimed_failures.get(vehicle_id, [])
            if now - t <= _RATE_WINDOW_S
        ]
        recent.append(now)
        self._claimed_failures[vehicle_id] = recent

    def _failures_limited(self, now: float) -> bool:
        """Throttle requests that failed token verification, agent-wide.

        Deliberately not keyed on the claimed vehicle id: an attacker controls
        that field, so a per-id bucket would let them lock a real vehicle out.
        The budget is the per-vehicle allowance times the size of the authorised
        fleet, falling back to one vehicle's allowance when the registry is empty,
        so there is no second threshold to tune. Only failed verifications consult
        it, so it can never throttle traffic that authenticates, and excess
        attempts are turned from ``TOKEN`` into ``RATE_LIMIT`` -- the only thing
        this budget ever does.
        """
        limit = self.config.rate_limit_per_vehicle_per_min * max(
            1, len(self.config.authorized_vehicle_ids)
        )
        recent = [t for t in self._failures if now - t <= _RATE_WINDOW_S]
        limited = len(recent) >= limit
        if not limited:
            recent.append(now)
        self._failures = recent
        return limited

    def _prune_nonces(self, now: float) -> None:
        """Drop nonce records older than the token lifetime."""
        ttl = self.config.token_ttl_s
        self._nonces = {n: t for n, t in self._nonces.items() if now - t <= ttl}

    def _speed_ok(self, telemetry: Any, edge: Optional[Tuple[str, str]]) -> bool:
        """Speed must respect the fleet ceiling and the edge's own posted limit."""
        if telemetry.speed_mps > self.config.ambulance_max_mps:
            return False
        if edge is None:
            return True
        limit = float(self.graph[edge[0]][edge[1]]["speed_limit_mps"])
        return telemetry.speed_mps <= max(self.config.ambulance_max_mps, limit * 1.5)

    def _position_ok(self, telemetry: Any, edge: Optional[Tuple[str, str]]) -> bool:
        """Reported (x, y) must project onto the named edge within tolerance."""
        if edge is None:
            return False
        ax, ay = self._xy(edge[0])
        bx, by = self._xy(edge[1])
        dx, dy = bx - ax, by - ay
        span = dx * dx + dy * dy
        if span <= 0.0:
            return False
        t = ((telemetry.x - ax) * dx + (telemetry.y - ay) * dy) / span
        if not 0.0 <= t <= 1.0:
            return False
        px, py = ax + t * dx, ay + t * dy
        return math.hypot(telemetry.x - px, telemetry.y - py) <= self.config.position_tolerance_m

    def _heading_ok(self, telemetry: Any, edge: Optional[Tuple[str, str]]) -> bool:
        """Reported heading must be within tolerance of the edge bearing."""
        if edge is None:
            return True
        bearing = float(self.graph[edge[0]][edge[1]]["bearing_deg"])
        diff = abs((telemetry.heading_deg - bearing + 180.0) % 360.0 - 180.0)
        return diff <= self.config.heading_tolerance_deg

    def _continuity_ok(
        self, telemetry: Any, edge: Optional[Tuple[str, str]],
        vehicle_id: str, now: float,
    ) -> bool:
        """Reject implausible leaps since the last accepted position.

        The reachable distance is the vehicle's physical ceiling over the elapsed
        time (``ambulance_max_mps * elapsed``) plus ``position_tolerance_m`` of
        GPS slack, so no tolerance constants are hard-coded here.
        """
        last = self._last.get(vehicle_id)
        if last is None:
            return True

        lx, ly, last_edge, last_t = last
        if edge is not None and last_edge is not None and edge != last_edge:
            if not set(edge) & set(last_edge):
                return False

        elapsed = max(now - last_t, 0.0)
        moved = math.hypot(telemetry.x - lx, telemetry.y - ly)
        reach = (
            self.config.ambulance_max_mps * elapsed
            + self.config.position_tolerance_m
        )
        return moved <= reach

    def _edge(self, edge_id: str) -> Optional[Tuple[str, str]]:
        """Split an edge id such as ``j_0_0_j_0_1`` into its two graph nodes."""
        parts = edge_id.split("_")
        for i in range(1, len(parts)):
            u, v = "_".join(parts[:i]), "_".join(parts[i:])
            if self.graph.has_edge(u, v):
                return (u, v)
        return None

    def _xy(self, node: str) -> Tuple[float, float]:
        """Return the (x, y) coordinate of a graph node."""
        data = self.graph.nodes[node]
        return float(data["x"]), float(data["y"])

    def _result(
        self, request: PreemptionRequest, allowed: bool, reasons: List[str],
        risk: float, detail: str, now: float,
    ) -> AuthResult:
        """Build the AuthResult message with a single-line security log."""
        log = f"vehicle={request.vehicle_id} allowed={allowed} risk={risk:.2f} {detail}"
        if reasons:
            log += " reasons=" + ",".join(reasons)

        for reason in reasons:
            self.reason_counts[reason] += 1
        if allowed:
            self.allowed += 1
        else:
            self.blocked += 1
        self.audit_trail.append(
            {
                "ts": now,
                "vehicle_id": request.vehicle_id,
                "allowed": allowed,
                "reasons": list(reasons),
                "risk_score": round(risk, 2),
            }
        )

        result = AuthResult(
            vehicle_id=request.vehicle_id,
            is_authenticated=allowed,
            reasons=list(reasons),
            security_log=log,
            risk_score=round(risk, 2),
        )
        result.sender = self.id
        result.recipient = request.sender
        result.ts = now
        return result
