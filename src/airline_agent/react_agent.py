from airline_agent.harness import BookingHarness, LoopDetector
from airline_agent.tools import search_flights, get_flight_detail, hold_flight, confirm_booking, cancel_hold


class ReActAgent:
    """Deterministic ReAct-style agent: observation ở vòng trước ảnh hưởng action vòng sau."""

    MAX_STEPS = 12

    def __init__(self, fault_injector=None):
        self.harness = BookingHarness()
        self.fault_injector = fault_injector
        self.tool_map = {
            "search_flights": search_flights,
            "get_flight_detail": get_flight_detail,
            "hold_flight": hold_flight,
            "confirm_booking": confirm_booking,
            "cancel_hold": cancel_hold,
        }

    def run(self, state: dict) -> dict:
        state = dict(state)
        state.setdefault("attempted_actions", [])
        state.setdefault("observations", [])
        state.setdefault("excluded_flight_ids", [])
        state.setdefault("retry_count", 0)
        detector = LoopDetector()

        validation = self.harness.validate_flight_request(
            state.get("origin", ""), state.get("destination", ""), state.get("date", "")
        )
        if not validation["valid"]:
            return self._handoff(state, "; ".join(validation["errors"]), "Please provide a valid route and date.")
        state["status"] = "request_valid"

        last_observation = None
        for _ in range(self.MAX_STEPS):
            action, args = self._reason(state, last_observation)
            if action is None:
                completion = self.harness.check_completion(state)
                if completion["completed"]:
                    return {**state, "status": "completed"}
                # Search-only intent is legitimately complete after results are obtained.
                if state.get("user_intent") == "search" and state.get("flight_id"):
                    return {**state, "status": "search_completed"}
                return self._handoff(state, completion["reason"], "More information or user authorization is required.")

            state["attempted_actions"].append({"action": action, "args": dict(args)})
            before = self.harness.before_tool(action, args, state, detector)
            if before["stop"]:
                return self._handoff(state, before["reason"], "Please authorize or correct the requested action.")

            if self.fault_injector:
                event = self.fault_injector.before_tool(action, args, state)
                if event:
                    state.setdefault("fault_events", []).append(event)

            result = self.tool_map[action].invoke(args)
            state["observations"].append({"action": action, "result": result})
            state = self._update_state(state, action, result)

            after = self.harness.after_tool(action, args, result, state, detector)
            if after["handoff"]:
                return {**state, "status": "handoff", "handoff": after["handoff"], "error": after["handoff"]["stop_reason"]}
            if after["completed"]:
                return {**state, "status": "completed"}

            last_observation = result

        return self._handoff(state, "STEP_BUDGET_EXCEEDED", "The agent reached its maximum step budget.")

    def _reason(self, state: dict, observation: dict | None):
        # ReAct recovery: observation lỗi retryable làm thay đổi quyết định tiếp theo.
        if observation and observation.get("status") == "error":
            code = observation.get("error_code")
            if observation.get("retryable") and code in {"NO_AVAILABLE_SEATS", "FLIGHT_CANCELLED"}:
                failed = observation.get("flight_id") or state.get("flight_id")
                if failed and failed not in state["excluded_flight_ids"]:
                    state["excluded_flight_ids"].append(failed)
                state.pop("flight_id", None)
                state.pop("hold_id", None)
                state["retry_count"] += 1
                if state["retry_count"] <= 2:
                    return "search_flights", self._search_args(state)
                return None, {}
            return None, {}

        if not state.get("flight_id"):
            return "search_flights", self._search_args(state)

        if state.get("user_intent") == "search":
            return None, {}

        if not state.get("hold_id"):
            return "hold_flight", {
                "flight_id": state["flight_id"],
                "passenger_name": state["passenger_name"],
            }

        if not state.get("booking_id"):
            return "confirm_booking", {"hold_id": state["hold_id"]}

        return None, {}

    @staticmethod
    def _search_args(state):
        return {"origin": state["origin"], "destination": state["destination"], "date": state["date"]}

    def _update_state(self, state, action, result):
        new_state = dict(state)
        if result.get("status") != "ok":
            new_state["status"] = f"{action}_failed"
            new_state["error"] = result.get("message", "Tool failed.")
            return new_state

        if action == "search_flights":
            candidates = [
                f for f in result.get("flights", [])
                if f["flight_id"] not in new_state.get("excluded_flight_ids", [])
            ]
            if not candidates:
                new_state["status"] = "no_flight"
                new_state["error"] = "No non-excluded available flight."
                return new_state
            new_state["flight_id"] = candidates[0]["flight_id"]
            new_state["status"] = "flight_found"
        elif action == "hold_flight":
            new_state["hold_id"] = result["hold"]["hold_id"]
            new_state["status"] = "flight_held"
        elif action == "confirm_booking":
            new_state["booking_id"] = result["booking"]["booking_id"]
            new_state["status"] = "confirmed"
        elif action == "cancel_hold":
            new_state.pop("hold_id", None)
            new_state["status"] = "hold_cancelled"
        return new_state

    def _handoff(self, state, reason, question):
        handoff = self.harness.handoff(reason, state.get("attempted_actions", []), state, question)
        return {**state, "status": "handoff", "error": reason, "handoff": handoff}


def run_react_demo():
    state = {
        "origin": "SGN", "destination": "HAN", "date": "2026-10-15",
        "passenger_name": "Nguyen Van A", "user_intent": "book",
        "user_confirmed_booking": True,
    }
    print("=== REACT AGENT ===")
    print(ReActAgent().run(state))


if __name__ == "__main__":
    run_react_demo()
