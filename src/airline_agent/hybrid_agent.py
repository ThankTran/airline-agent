from airline_agent.harness import BookingHarness, LoopDetector
from airline_agent.tools import search_flights, get_flight_detail, hold_flight, confirm_booking, cancel_hold


class HybridAgent:
    """Plan + observation-driven execution + explicit re-planning khi plan không còn hợp lệ."""

    MAX_REPLANS = 2

    def __init__(self):
        self.harness = BookingHarness()
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
            return self._handoff(state, "; ".join(validation["errors"]), "Please provide valid route/date information.")
        state["status"] = "request_valid"

        plan = self._create_plan(state)
        plan_index = 0

        while plan_index < len(plan):
            planned_action = plan[plan_index]
            action = self._decide_next_action(state, planned_action)
            if action is None:
                break

            args = self._build_args(action, state)
            state["attempted_actions"].append({"action": action, "args": dict(args)})
            before = self.harness.before_tool(action, args, state, detector)
            if before["stop"]:
                return self._handoff(state, before["reason"], "The current plan is unsafe and requires review.")

            result = self.tool_map[action].invoke(args)
            state["observations"].append({"action": action, "result": result})
            state = self._update_state(state, action, result)

            after = self.harness.after_tool(action, args, result, state, detector)
            if after["handoff"]:
                return {**state, "status": "handoff", "handoff": after["handoff"], "error": after["handoff"]["stop_reason"]}
            if after["completed"]:
                return {**state, "status": "completed"}

            if result.get("status") != "ok":
                if self._can_replan(action, result, state):
                    state = self._prepare_replan(state, action, result)
                    plan = self._replan(state, action, result)
                    plan_index = 0
                    continue
                return self._handoff(
                    state,
                    result.get("error_code", "TOOL_FAILURE"),
                    "Automatic recovery is unavailable; please choose the next action.",
                )

            if state.get("user_intent") == "search" and state.get("flight_id"):
                return {**state, "status": "search_completed"}

            plan_index += 1

        completion = self.harness.check_completion(state)
        if completion["completed"]:
            return {**state, "status": "completed"}
        return self._handoff(state, completion["reason"], "The hybrid plan ended before verified completion.")

    def _create_plan(self, state):
        if state.get("user_intent") == "search":
            return ["search_flights"]
        return ["search_flights", "hold_flight", "confirm_booking"]

    def _replan(self, state, failed_action, observation):
        # Sau lỗi flight availability, bỏ lựa chọn cũ và lập lại phần còn lại.
        if failed_action == "hold_flight" and observation.get("error_code") in {
            "NO_AVAILABLE_SEATS", "FLIGHT_CANCELLED"
        }:
            return ["search_flights", "hold_flight", "confirm_booking"]
        if failed_action == "confirm_booking" and observation.get("error_code") == "HOLD_EXPIRED":
            return ["hold_flight", "confirm_booking"]
        return []

    def _can_replan(self, action, result, state):
        return (
            result.get("retryable", False)
            and state.get("retry_count", 0) < self.MAX_REPLANS
            and bool(self._replan(state, action, result))
        )

    def _prepare_replan(self, state, action, result):
        new_state = dict(state)
        new_state["retry_count"] = new_state.get("retry_count", 0) + 1

        if action == "hold_flight":
            failed = result.get("flight_id") or new_state.get("flight_id")
            excluded = list(new_state.get("excluded_flight_ids", []))
            if failed and failed not in excluded:
                excluded.append(failed)
            new_state["excluded_flight_ids"] = excluded
            new_state.pop("flight_id", None)
            new_state.pop("hold_id", None)
            new_state["status"] = "replanning_after_flight_failure"

        elif action == "confirm_booking" and result.get("error_code") == "HOLD_EXPIRED":
            new_state.pop("hold_id", None)
            new_state["status"] = "replanning_after_expired_hold"

        return new_state

    def _decide_next_action(self, state, planned_action):
        # Plan định hướng; state quyết định bước thực tế cần thiết.
        if not state.get("flight_id"):
            return "search_flights"
        if state.get("user_intent") == "search":
            return None
        if not state.get("hold_id"):
            return "hold_flight"
        if not state.get("booking_id"):
            return "confirm_booking"
        return None

    def _build_args(self, action, state):
        if action == "search_flights":
            return {"origin": state["origin"], "destination": state["destination"], "date": state["date"]}
        if action == "hold_flight":
            return {"flight_id": state["flight_id"], "passenger_name": state["passenger_name"]}
        if action == "confirm_booking":
            return {"hold_id": state["hold_id"]}
        if action == "get_flight_detail":
            return {"flight_id": state["flight_id"]}
        if action == "cancel_hold":
            return {"hold_id": state["hold_id"]}
        return {}

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
            else:
                new_state["flight_id"] = candidates[0]["flight_id"]
                new_state["status"] = "flight_found"
        elif action == "hold_flight":
            new_state["hold_id"] = result["hold"]["hold_id"]
            new_state["status"] = "flight_held"
        elif action == "confirm_booking":
            new_state["booking_id"] = result["booking"]["booking_id"]
            new_state["status"] = "confirmed"
        return new_state

    def _handoff(self, state, reason, question):
        handoff = self.harness.handoff(reason, state.get("attempted_actions", []), state, question)
        return {**state, "status": "handoff", "error": reason, "handoff": handoff}


def run_hybrid_demo():
    state = {
        "origin": "SGN", "destination": "HAN", "date": "2026-10-15",
        "passenger_name": "Nguyen Van A", "user_intent": "book",
        "user_confirmed_booking": True,
    }
    print("=== HYBRID AGENT ===")
    print(HybridAgent().run(state))


if __name__ == "__main__":
    run_hybrid_demo()
