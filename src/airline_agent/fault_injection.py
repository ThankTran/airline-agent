from __future__ import annotations

from dataclasses import dataclass, field

from airline_agent.database import get_flight_by_id


@dataclass
class FaultInjector:
    """Deterministic test-only fault injector.

    Faults are injected after the harness approves an action but immediately
    before the tool executes. This models an external business-state change
    between planning/observation and execution without changing agent logic.
    """

    scenario: str | None = None
    triggered: bool = False
    events: list[dict] = field(default_factory=list)

    def before_tool(self, action: str, args: dict, state: dict) -> dict | None:
        if self.triggered or not self.scenario:
            return None

        if self.scenario == "sold_out_after_search" and action == "hold_flight":
            flight_id = args.get("flight_id")
            flight = get_flight_by_id(flight_id)
            if flight:
                flight["available_seats"] = 0
                flight["status"] = "sold_out"
                return self._record("FLIGHT_SOLD_OUT", action, flight_id)

        if self.scenario == "cancelled_after_search" and action == "hold_flight":
            flight_id = args.get("flight_id")
            flight = get_flight_by_id(flight_id)
            if flight:
                flight["status"] = "cancelled"
                return self._record("FLIGHT_CANCELLED", action, flight_id)

        return None

    def _record(self, event: str, action: str, flight_id: str | None) -> dict:
        self.triggered = True
        payload = {
            "event": event,
            "before_action": action,
            "flight_id": flight_id,
        }
        self.events.append(payload)
        return payload
