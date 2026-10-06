from airline_agent.harness import BookingHarness, LoopDetector
from airline_agent.tools import search_flights, get_flight_detail, hold_flight, confirm_booking, cancel_hold


class PlanThenExecuteAgent:
    """Lập plan một lần rồi thực thi; tool failure không tự re-plan."""

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
        detector = LoopDetector()

        validation = self.harness.validate_flight_request(
            state.get("origin", ""), state.get("destination", ""), state.get("date", "")
        )
        if not validation["valid"]:
            return self._handoff(state, "; ".join(validation["errors"]), "Please provide valid booking information.")
        state["status"] = "request_valid"

        plan = self._create_plan(state)
        for action, args_builder in plan:
            args = args_builder(state)
            state["attempted_actions"].append({"action": action, "args": dict(args)})
            before = self.harness.before_tool(action, args, state, detector)
            if before["stop"]:
                return self._handoff(state, before["reason"], "The fixed plan cannot safely continue.")

            if self.fault_injector:
                event = self.fault_injector.before_tool(action, args, state)
                if event:
                    state.setdefault("fault_events", []).append(event)

            result = self.tool_map[action].invoke(args)
            state["observations"].append({"action": action, "result": result})
            state = self._update_state(state, action, result)

            if action == "search_flights" and not result.get("flights", []):
                return self._handoff(
                    state,
                    "NO_MATCHING_FLIGHT",
                    "No matching flight was found. Please choose another route or date",
                )
            after = self.harness.after_tool(
                action,
                args,
                result,
                state,
                detector,
            )

            if after["handoff"]:
                return {
                    **state,
                    "status": "handoff",
                    "handoff": after["handoff"],
                    "error": after["handoff"]["stop_reason"],
                }

            if after["completed"]:
                return {
                    **state,
                    "status": "completed",
                }

            if result.get("status") != "ok":
                return self._handoff(
                    state,
                    result.get("error_code", "TOOL_FAILURE"),
                    "The precomputed plan failed and this pattern does not re-plan automatically.",
                )
            
        if state.get("user_intent") == "search" and state.get("flight_id"):
            return {**state, "status": "search_completed"}

        completion = self.harness.check_completion(state)
        if completion["completed"]:
            return {**state, "status": "completed"}
        return self._handoff(state, completion["reason"], "The fixed plan ended before verified completion.")

    def _create_plan(self, state):
        plan = [
            ("search_flights", lambda s: {"origin": s["origin"], "destination": s["destination"], "date": s["date"]}),
        ]
        if state.get("user_intent") != "search":
            plan.extend([
                ("hold_flight", lambda s: {"flight_id": s["flight_id"], "passenger_name": s["passenger_name"]}),
                ("confirm_booking", lambda s: {"hold_id": s["hold_id"]}),
            ])
        return plan

    def _update_state(self, state, action, result):
        new_state = dict(state)
        if result.get("status") != "ok":
            new_state["status"] = f"{action}_failed"
            new_state["error"] = result.get("message", "Tool failed.")
            return new_state
        if action == "search_flights":
            flights = result.get("flights", [])
            if not flights:
                new_state["status"] = "no_flight"
                new_state["error"] = "No available flight."
            else:
                new_state["flight_id"] = flights[0]["flight_id"]
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


def run_plan_execute_demo():
    state = {
        "origin": "SGN", "destination": "HAN", "date": "2026-10-15",
        "passenger_name": "Nguyen Van A", "user_intent": "book",
        "user_confirmed_booking": True,
    }
    print("=== PLAN-THEN-EXECUTE AGENT ===")
    print(PlanThenExecuteAgent().run(state))


if __name__ == "__main__":
    run_plan_execute_demo()
