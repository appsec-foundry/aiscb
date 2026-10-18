"""Existing admission boundary for untrusted transport events."""

from dataclasses import dataclass


REASONS = {
    "connection_reset": "Peer closed the connection",
    "timeout": "Timed out waiting for the transport",
}


@dataclass(frozen=True)
class AdmittedEvent:
    kind: str
    attempt: int
    maximum: int
    explanation: str


def admit_event(raw):
    if not isinstance(raw, dict):
        raise ValueError("Invalid transport event")
    kind, reason = raw.get("kind"), raw.get("reason")
    attempt, maximum = raw.get("attempt"), raw.get("maximum")
    if not isinstance(kind, str) or kind not in ("retry", "failed"):
        raise ValueError("Invalid event kind")
    if not isinstance(reason, str) or reason not in REASONS:
        raise ValueError("Invalid reason")
    if type(attempt) is not int or type(maximum) is not int:
        raise ValueError("Invalid attempt count")
    if not 1 <= attempt <= maximum <= 10:
        raise ValueError("Invalid attempt count")
    # Raw exceptions and other provider fields do not cross this boundary.
    return AdmittedEvent(kind, attempt, maximum, REASONS[reason])
