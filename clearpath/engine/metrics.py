"""Metrics collection and performance tracking for ClearPath-lite.

Collects per-tick telemetry, computes derived statistics, and exposes a
``summary()`` dict suitable for the dashboard and test assertions.

Metric categories
-----------------
Ambulance
    travel_time_s, stops, stopped_time_s, improvement_pct (vs baseline)

Cross-traffic delay
    per-vehicle extra wait accumulated while a preemption corridor is active,
    reported as average and p95 vs a baseline snapshot.

Network-wide
    throughput (completed vehicles / elapsed ticks), average speed, max queue,
    gridlock indicator (fraction of edges with queue > threshold).

Security
    total_requests, blocked, block_rate, false_accept / false_reject counts
    (the scenario runner injects ground truth), reason_histogram.

Negotiation
    messages_sent, nack_count, avg_latency_s.

Recovery
    per_junction recovery duration samples.

Time series
    raw per-tick arrays for speed, queue, throughput — consumed by charts.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _percentile(data: List[float], p: float) -> float:
    """Return the p-th percentile of a non-empty list (linear interpolation)."""
    if not data:
        return 0.0
    s = sorted(data)
    idx = (len(s) - 1) * p / 100.0
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def _safe_mean(data: List[float]) -> float:
    return sum(data) / len(data) if data else 0.0


# ---------------------------------------------------------------------------
# Per-vehicle wait snapshot used for cross-traffic delay
# ---------------------------------------------------------------------------

@dataclass
class _WaitSnapshot:
    vehicle_id: str
    wait_at_start: float   # wait_time_s when recording started
    tick_start: int


# ---------------------------------------------------------------------------
# Main collector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """Accumulates and derives all simulation performance metrics.

    Parameters
    ----------
    config : SimConfig
        Simulation configuration; used for the gridlock threshold.
    baseline : MetricsCollector | None
        A previously-completed baseline run.  When set, improvement percentages
        and cross-traffic delta comparisons become available.
    """

    def __init__(self, config: Any, baseline: "MetricsCollector | None" = None) -> None:
        self.config = config
        self.baseline = baseline

        # ── ambulance ─────────────────────────────────────────────────────────
        self._amb_start_tick: Dict[str, int] = {}
        self._amb_end_tick: Dict[str, int] = {}
        self._amb_stops: Dict[str, int] = {}
        self._amb_stopped_time: Dict[str, float] = {}
        self._amb_was_stopped: Dict[str, bool] = {}

        # ── cross-traffic delay ───────────────────────────────────────────────
        # During a preemption window we record extra wait accumulated by civs
        self._preemption_active: bool = False
        self._preemption_start_tick: Optional[int] = None
        self._wait_snapshots: Dict[str, _WaitSnapshot] = {}
        self._cross_delay_samples: List[float] = []

        # ── network ───────────────────────────────────────────────────────────
        self._completed_vehicles: List[int] = []   # cumulative, per tick
        self._avg_speed_series: List[float] = []
        self._max_queue_series: List[int] = []
        self._gridlock_series: List[bool] = []

        # ── security ─────────────────────────────────────────────────────────
        self.security_total_requests: int = 0
        self.security_blocked: int = 0
        self.security_total_attacks: int = 0
        self.security_blocked_attacks: int = 0
        self.security_total_legitimate: int = 0
        self.security_allowed_legitimate: int = 0
        self.security_false_accept: int = 0
        self.security_false_reject: int = 0
        self.security_reason_histogram: Counter = Counter()

        # ── negotiation ───────────────────────────────────────────────────────
        self.negotiation_messages_sent: int = 0
        self.negotiation_nack_count: int = 0
        self._negotiation_latencies: List[float] = []   # seconds

        # ── recovery ─────────────────────────────────────────────────────────
        self.recovery_times: Dict[str, List[float]] = defaultdict(list)

        # ── tick counter ──────────────────────────────────────────────────────
        self.ticks_elapsed: int = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Per-tick recorder (called by the orchestrator after each sim step)
    # ─────────────────────────────────────────────────────────────────────────

    def record(self, t: int, world_view: Any, sim: Any) -> None:
        """Record one tick of raw data from the simulator world view."""
        self.ticks_elapsed = t
        vehicles = getattr(world_view, "vehicles", []) or []
        queues   = getattr(world_view, "queues",   {}) or {}

        # ── ambulance tracking ────────────────────────────────────────────────
        for v in vehicles:
            if getattr(v, "kind", "") != "ambulance":
                continue
            vid = v.id
            if vid not in self._amb_start_tick:
                self._amb_start_tick[vid] = t
                self._amb_stops[vid] = 0
                self._amb_stopped_time[vid] = 0.0
                self._amb_was_stopped[vid] = False

            stopped = getattr(v, "is_stopped", False)
            if stopped:
                self._amb_stopped_time[vid] = self._amb_stopped_time.get(vid, 0.0) + 1.0
                if not self._amb_was_stopped.get(vid, False):
                    self._amb_stops[vid] = self._amb_stops.get(vid, 0) + 1
            self._amb_was_stopped[vid] = stopped

        # Detect ambulances that have just finished (present in start, absent now)
        active_ids = {v.id for v in vehicles if getattr(v, "kind", "") == "ambulance"}
        for vid in list(self._amb_start_tick):
            if vid not in active_ids and vid not in self._amb_end_tick:
                self._amb_end_tick[vid] = t

        # ── network stats ─────────────────────────────────────────────────────
        civil = [v for v in vehicles if getattr(v, "kind", "") != "ambulance"]
        speeds = [float(v.speed_mps) for v in civil]
        avg_speed = _safe_mean(speeds)
        self._avg_speed_series.append(avg_speed)

        completed = int(getattr(sim, "completed_vehicles", 0))
        self._completed_vehicles.append(completed)

        max_q = int(max(queues.values())) if queues else 0
        self._max_queue_series.append(max_q)

        # Gridlock: more than 30% of edges have queue > threshold
        graph = getattr(getattr(sim, "network", None), "graph", None)
        if graph is not None:
            total_edges = graph.number_of_edges()
            overloaded = sum(
                1 for q in queues.values()
                if q > self.config.queue_flush_threshold
            )
            self._gridlock_series.append(
                total_edges > 0 and overloaded / total_edges > 0.30
            )
        else:
            self._gridlock_series.append(False)

        # ── cross-traffic delay ───────────────────────────────────────────────
        if self._preemption_active:
            for v in civil:
                vid = v.id
                if vid not in self._wait_snapshots:
                    self._wait_snapshots[vid] = _WaitSnapshot(
                        vehicle_id=vid,
                        wait_at_start=float(getattr(v, "wait_time_s", 0.0)),
                        tick_start=t,
                    )

    # ─────────────────────────────────────────────────────────────────────────
    # Event hooks called by the orchestrator
    # ─────────────────────────────────────────────────────────────────────────

    def on_preemption_start(self, t: int, world_view: Any) -> None:
        """Mark start of an active preemption corridor."""
        if not self._preemption_active:
            self._preemption_active = True
            self._preemption_start_tick = t
            # Snapshot current wait times so we can compute deltas
            for v in getattr(world_view, "vehicles", []) or []:
                if getattr(v, "kind", "") == "ambulance":
                    continue
                self._wait_snapshots[v.id] = _WaitSnapshot(
                    vehicle_id=v.id,
                    wait_at_start=float(getattr(v, "wait_time_s", 0.0)),
                    tick_start=t,
                )

    def on_preemption_end(self, t: int, world_view: Any) -> None:
        """Mark end of preemption; finalise delay samples."""
        if not self._preemption_active:
            return
        self._preemption_active = False
        vehicles = {v.id: v for v in (getattr(world_view, "vehicles", []) or [])}
        for vid, snap in self._wait_snapshots.items():
            v = vehicles.get(vid)
            if v is None:
                continue
            delta = float(getattr(v, "wait_time_s", 0.0)) - snap.wait_at_start
            if delta > 0:
                self._cross_delay_samples.append(delta)
        self._wait_snapshots.clear()

    def on_security_result(
        self,
        allowed: bool,
        reasons: List[str],
        ground_truth_valid: Optional[bool] = None,
    ) -> None:
        """Record one security verdict, optionally comparing to ground truth."""
        self.security_total_requests += 1
        if not allowed:
            self.security_blocked += 1
        for r in reasons:
            self.security_reason_histogram[r] += 1

        if ground_truth_valid is not None:
            if not ground_truth_valid:
                self.security_total_attacks += 1
                if not allowed:
                    self.security_blocked_attacks += 1
                else:
                    self.security_false_accept += 1
            else:
                self.security_total_legitimate += 1
                if not allowed:
                    self.security_false_reject += 1
                else:
                    self.security_allowed_legitimate += 1

    def on_negotiation_message(self, msg_type: str) -> None:
        """Record one bus message relevant to junction negotiation."""
        self.negotiation_messages_sent += 1
        if msg_type in ("ReserveNack",):
            self.negotiation_nack_count += 1

    def on_negotiation_latency(self, latency_s: float) -> None:
        """Record one reservation round-trip latency."""
        self._negotiation_latencies.append(latency_s)

    def on_recovery(self, junction_id: str, duration_s: float) -> None:
        """Record one junction recovery duration."""
        self.recovery_times[junction_id].append(duration_s)

    # ─────────────────────────────────────────────────────────────────────────
    # Derived properties
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def ambulance_travel_time_s(self) -> Optional[float]:
        """Travel time (s) of the first ambulance that completed its run."""
        for vid, end_t in self._amb_end_tick.items():
            start_t = self._amb_start_tick.get(vid)
            if start_t is not None:
                return float(end_t - start_t)
        return None

    @property
    def ambulance_stops(self) -> int:
        return sum(self._amb_stops.values())

    @property
    def ambulance_stopped_time_s(self) -> float:
        return sum(self._amb_stopped_time.values())

    @property
    def improvement_pct(self) -> Optional[float]:
        """Percent reduction in ambulance travel time vs the baseline run."""
        if self.baseline is None:
            return None
        base = self.baseline.ambulance_travel_time_s
        mine = self.ambulance_travel_time_s
        if base is None or mine is None or base <= 0:
            return None
        return round(100.0 * (base - mine) / base, 2)

    @property
    def network_throughput(self) -> float:
        """Completed vehicles per elapsed tick."""
        if not self._completed_vehicles or self.ticks_elapsed == 0:
            return 0.0
        return round(self._completed_vehicles[-1] / self.ticks_elapsed, 4)

    @property
    def network_avg_speed(self) -> float:
        return round(_safe_mean(self._avg_speed_series), 3)

    @property
    def network_max_queue(self) -> int:
        return int(max(self._max_queue_series)) if self._max_queue_series else 0

    @property
    def network_gridlock_ticks(self) -> int:
        return sum(1 for g in self._gridlock_series if g)

    @property
    def cross_delay_avg(self) -> float:
        return round(_safe_mean(self._cross_delay_samples), 3)

    @property
    def cross_delay_p95(self) -> float:
        return round(_percentile(self._cross_delay_samples, 95), 3)

    @property
    def security_block_rate(self) -> float:
        if self.security_total_requests == 0:
            return 0.0
        return round(self.security_blocked / self.security_total_requests, 4)

    @property
    def security_attack_block_rate(self) -> float:
        if self.security_total_attacks == 0:
            return self.security_block_rate
        return round(self.security_blocked_attacks / self.security_total_attacks, 4)

    @property
    def security_false_positive_rate(self) -> float:
        if self.security_total_legitimate == 0:
            return 0.0
        return round(self.security_false_reject / self.security_total_legitimate, 4)

    @property
    def negotiation_avg_latency_s(self) -> float:
        return round(_safe_mean(self._negotiation_latencies), 3)

    # ─────────────────────────────────────────────────────────────────────────
    # Public summary
    # ─────────────────────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Return a JSON-serialisable summary of all collected metrics."""
        return {
            # timing
            "ticks_elapsed": self.ticks_elapsed,
            # ambulance
            "ambulance_travel_time_s": self.ambulance_travel_time_s,
            "ambulance_stops": self.ambulance_stops,
            "ambulance_stopped_time_s": self.ambulance_stopped_time_s,
            "ambulance_improvement_pct": self.improvement_pct,
            # cross-traffic
            "cross_delay_avg_s": self.cross_delay_avg,
            "cross_delay_p95_s": self.cross_delay_p95,
            # network
            "network_throughput": self.network_throughput,
            "network_avg_speed_mps": self.network_avg_speed,
            "network_max_queue": self.network_max_queue,
            "network_gridlock_ticks": self.network_gridlock_ticks,
            # security
            "security_total_requests": self.security_total_requests,
            "security_blocked": self.security_blocked,
            "security_block_rate": self.security_block_rate,
            "security_total_attacks": self.security_total_attacks,
            "security_blocked_attacks": self.security_blocked_attacks,
            "security_attack_block_rate": self.security_attack_block_rate,
            "security_total_legitimate": self.security_total_legitimate,
            "security_false_positive_rate": self.security_false_positive_rate,
            "security_false_accept": self.security_false_accept,
            "security_false_reject": self.security_false_reject,
            "security_reason_histogram": dict(self.security_reason_histogram),
            # negotiation
            "negotiation_messages_sent": self.negotiation_messages_sent,
            "negotiation_nack_count": self.negotiation_nack_count,
            "negotiation_avg_latency_s": self.negotiation_avg_latency_s,
            # recovery
            "recovery_times": {
                jid: list(times)
                for jid, times in self.recovery_times.items()
            },
            # time series
            "ts_avg_speed": list(self._avg_speed_series),
            "ts_max_queue": list(self._max_queue_series),
            "ts_completed": list(self._completed_vehicles),
        }

    # Alias for legacy callers
    @property
    def ticks(self) -> int:
        return self.ticks_elapsed
