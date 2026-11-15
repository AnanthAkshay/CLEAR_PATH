"""Message bus and typed messaging protocols for ClearPath-lite."""

from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import (
    AuthResult,
    EtaNotice,
    GreenWavePrepare,
    GuidanceAdvisory,
    Message,
    PassedNotice,
    PreemptionRequest,
    RecoveryDone,
    RecoveryStarted,
    ReserveAck,
    ReserveCorridor,
    ReserveNack,
    RevokePreemption,
    RoutePlan,
    Telemetry,
)

__all__ = [
    "MessageBus",
    "Message",
    "Telemetry",
    "PreemptionRequest",
    "AuthResult",
    "RoutePlan",
    "EtaNotice",
    "ReserveCorridor",
    "ReserveAck",
    "ReserveNack",
    "GreenWavePrepare",
    "PassedNotice",
    "RecoveryStarted",
    "RecoveryDone",
    "RevokePreemption",
    "GuidanceAdvisory",
]

