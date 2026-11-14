"""Typed message definitions for agent and simulator communication.

All messages derive from a base Message class carrying an identifier, timestamp,
sender, recipient, and message type discriminator.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class Message:
    """Base class for all typed messages passed across the MessageBus.

    Attributes:
        id: Unique identifier for the message.
        ts: Simulation timestamp (seconds) when the message was dispatched.
        sender: Agent or entity ID originating the message.
        recipient: Agent ID, junction ID, or broadcast topic.
        type: Discriminator name for message handling.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: float = 0.0
    sender: str = ""
    recipient: str = ""
    type: str = field(default="")

    def __post_init__(self) -> None:
        """Set message type to class name if not explicitly provided."""
        if not self.type:
            self.type = self.__class__.__name__


@dataclass
class Telemetry(Message):
    """Kinematic observation and spatial location for a vehicle.

    Attributes:
        x: Cartesian X coordinate (meters).
        y: Cartesian Y coordinate (meters).
        speed_mps: Instantaneous velocity in meters per second.
        accel_mps2: Instantaneous acceleration in meters per second squared.
        heading_deg: Heading angle in degrees [0, 360).
        edge_id: Road segment identifier currently occupied.
        lane: Lane index on current edge (0-indexed).
        vehicle_id: Identifier of the reporting vehicle.
    """

    x: float = 0.0
    y: float = 0.0
    speed_mps: float = 0.0
    accel_mps2: float = 0.0
    heading_deg: float = 0.0
    edge_id: str = ""
    lane: int = 0
    vehicle_id: str = ""


@dataclass
class PreemptionRequest(Message):
    """Emergency vehicle request for traffic signal corridor preemption.

    Attributes:
        vehicle_id: Emergency vehicle identifier.
        token: Cryptographic HMAC or JWT verification token.
        telemetry: Vehicle telemetry captured at request generation.
        incident_loc: (x, y) coordinates of the emergency origin.
        severity: Triage level (e.g. CRITICAL, HIGH, MEDIUM).
        nonce: Cryptographic nonce for replay attack prevention.
    """

    vehicle_id: str = ""
    token: str = ""
    telemetry: Telemetry = field(default_factory=Telemetry)
    incident_loc: Tuple[float, float] = (0.0, 0.0)
    severity: str = "HIGH"
    nonce: str = ""


@dataclass
class AuthResult(Message):
    """Validation verdict emitted by SecurityAgent after verifying preemption request.

    Attributes:
        vehicle_id: Vehicle whose request was evaluated.
        is_authenticated: True if cryptographic and kinematic checks passed.
        reasons: List of explanatory flags or failure rationales.
        security_log: Structured log summary of verification details.
    """

    vehicle_id: str = ""
    is_authenticated: bool = False
    reasons: List[str] = field(default_factory=list)
    security_log: str = ""


@dataclass
class RoutePlan(Message):
    """Optimal path and scheduled intersection arrival timeline computed by Dispatcher.

    Attributes:
        vehicle_id: Designated emergency vehicle identifier.
        hospital_id: Selected destination medical facility.
        path_nodes: Ordered sequence of network junction identifiers.
        eta_by_junction: Mapping of junction node ID to estimated arrival time (s).
        total_eta_s: Total expected transit time to the destination hospital (s).
    """

    vehicle_id: str = ""
    hospital_id: str = ""
    path_nodes: List[str] = field(default_factory=list)
    eta_by_junction: Dict[str, float] = field(default_factory=dict)
    total_eta_s: float = 0.0


@dataclass
class EtaNotice(Message):
    """Corridor schedule notice sent to an individual junction.

    Attributes:
        junction_id: Target intersection identifier.
        vehicle_id: Approaching emergency vehicle identifier.
        eta_t: Estimated arrival timestamp in simulation seconds.
        approach_edge: Inbound edge on which the vehicle enters the intersection.
        exit_edge: Outbound edge onto which the vehicle departs.
    """

    junction_id: str = ""
    vehicle_id: str = ""
    eta_t: float = 0.0
    approach_edge: str = ""
    exit_edge: str = ""


@dataclass
class ReserveCorridor(Message):
    """Corridor reservation coordination request along a sequence of junctions.

    Attributes:
        vehicle_id: Emergency vehicle identifier requesting passage.
        corridor_nodes: Ordered list of junction nodes in the reservation path.
        eta_t: Target arrival time at the receiving junction.
        duration_s: Estimated green reservation window duration in seconds.
    """

    vehicle_id: str = ""
    corridor_nodes: List[str] = field(default_factory=list)
    eta_t: float = 0.0
    duration_s: float = 25.0


@dataclass
class ReserveAck(Message):
    """Confirmation that a junction has reserved an approach phase for an emergency vehicle.

    Attributes:
        junction_id: Confirming intersection node identifier.
        vehicle_id: Emergency vehicle granted reservation.
        reservation_id: Identifier generated for the active reservation lock.
    """

    junction_id: str = ""
    vehicle_id: str = ""
    reservation_id: str = ""


@dataclass
class ReserveNack(Message):
    """Rejection or conflict notice when a junction cannot accommodate preemption.

    Attributes:
        junction_id: Rejecting intersection node identifier.
        vehicle_id: Emergency vehicle identifier.
        reason: Explanation for rejection (e.g., minimum green violated, active conflict).
    """

    junction_id: str = ""
    vehicle_id: str = ""
    reason: str = ""


@dataclass
class GreenWavePrepare(Message):
    """Upstream-to-downstream handoff notification to initiate green-wave coordination.

    Attributes:
        from_junction_id: Upstream intersection clearing the vehicle.
        to_junction_id: Downstream intersection preparing the phase.
        vehicle_id: Emergency vehicle in transit.
        expected_arrival_t: Projected arrival timestamp at the downstream node.
    """

    from_junction_id: str = ""
    to_junction_id: str = ""
    vehicle_id: str = ""
    expected_arrival_t: float = 0.0


@dataclass
class PassedNotice(Message):
    """Notification confirming that an emergency vehicle has exited an intersection.

    Attributes:
        junction_id: Intersection node that vehicle cleared.
        vehicle_id: Emergency vehicle identifier.
        t: Timestamp when vehicle crossed the stop bar and exited.
    """

    junction_id: str = ""
    vehicle_id: str = ""
    t: float = 0.0


@dataclass
class RecoveryStarted(Message):
    """Notice indicating that an intersection has initiated its post-preemption recovery phase.

    Attributes:
        junction_id: Intersection entering recovery.
        recovery_duration_s: Expected duration of the compensatory recovery phase.
    """

    junction_id: str = ""
    recovery_duration_s: float = 0.0


@dataclass
class RecoveryDone(Message):
    """Notice indicating that signal recovery is complete and standard cycling has resumed.

    Attributes:
        junction_id: Intersection completing recovery.
    """

    junction_id: str = ""


@dataclass
class GuidanceAdvisory(Message):
    """Advisory instruction issued to civilian or emergency drivers.

    Attributes:
        target_vehicle_ids: List of vehicle IDs to which the guidance is directed.
        text: Driver instruction text (e.g., "Move left", "Clear lane 1").
        lane: Target or prohibited lane index.
        severity: Urgency of advisory (e.g. INFO, WARN, CRITICAL).
    """

    target_vehicle_ids: List[str] = field(default_factory=list)
    text: str = ""
    lane: int = 0
    severity: str = "INFO"

