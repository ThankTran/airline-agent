from langgraph.graph import StateGraph, START, END

from airline_agent.state import BookingState
from airline_agent.harness import BookingHarness, LoopDetector
from airline_agent.tools import search_flights, hold_flight, confirm_booking

harness = BookingHarness()


def _runtime(state):
    state = dict(state)
    state.setdefault("attempted_actions", [])
    state.setdefault("observations", [])
    return state


def validate_request(state: BookingState) -> BookingState:
    state = _runtime(state)
    result = harness.validate_flight_request(state.get("origin", ""), state.get("destination", ""), state.get("date", ""))
    if not result["valid"]:
        return {**state, "status": "invalid_request", "error": "; ".join(result["errors"])}
    return {**state, "status": "request_valid"}


def _run_tool(state, action, args, tool):
    # Baseline là DAG không quay lại node, nhưng vẫn dùng cùng harness contract.
    detector = LoopDetector()
    state = _runtime(state)
    state["attempted_actions"].append({"action": action, "args": dict(args)})
    before = harness.before_tool(action, args, state, detector)
    if before["stop"]:
        return {**state, "status": "handoff", "error": before["reason"]}

    result = tool.invoke(args)
    state["observations"].append({"action": action, "result": result})
    return state, result, detector


def search_node(state: BookingState) -> BookingState:
    args = {"origin": state["origin"], "destination": state["destination"], "date": state["date"]}
    executed = _run_tool(state, "search_flights", args, search_flights)
    if isinstance(executed, dict):
        return executed
    state, result, detector = executed
    if result.get("status") != "ok" or not result.get("flights"):
        state.update(status="no_flight", error=result.get("message", "No available flight."))
    else:
        state.update(flight_id=result["flights"][0]["flight_id"], status="flight_found")
    after = harness.after_tool("search_flights", args, result, state, detector)
    if after["handoff"]:
        state.update(status="handoff", error=after["handoff"]["stop_reason"], handoff=after["handoff"])
    return state


def hold_node(state: BookingState) -> BookingState:
    args = {"flight_id": state["flight_id"], "passenger_name": state["passenger_name"]}
    executed = _run_tool(state, "hold_flight", args, hold_flight)
    if isinstance(executed, dict):
        return executed
    state, result, detector = executed
    if result.get("status") != "ok":
        state.update(status="hold_failed", error=result.get("message", "Hold failed."))
    else:
        state.update(hold_id=result["hold"]["hold_id"], status="flight_held")
    after = harness.after_tool("hold_flight", args, result, state, detector)
    if after["handoff"]:
        state.update(status="handoff", error=after["handoff"]["stop_reason"], handoff=after["handoff"])
    return state


def confirm_node(state: BookingState) -> BookingState:
    args = {"hold_id": state["hold_id"]}
    executed = _run_tool(state, "confirm_booking", args, confirm_booking)
    if isinstance(executed, dict):
        return executed
    state, result, detector = executed
    if result.get("status") != "ok":
        state.update(status="confirmation_failed", error=result.get("message", "Confirmation failed."))
    else:
        state.update(booking_id=result["booking"]["booking_id"], status="confirmed")
    after = harness.after_tool("confirm_booking", args, result, state, detector)
    if after["handoff"]:
        state.update(status="handoff", error=after["handoff"]["stop_reason"], handoff=after["handoff"])
    elif after["completed"]:
        state["status"] = "completed"
    return state


def check_completion(state: BookingState) -> BookingState:
    result = harness.check_completion(state)
    if result["completed"]:
        return {**state, "status": "completed"}
    return {**state, "status": "incomplete", "error": result["reason"]}


def route_after_validation(state):
    return "search" if state.get("status") == "request_valid" else "end"


def route_after_search(state):
    return "hold" if state.get("status") == "flight_found" else "end"


def route_after_hold(state):
    return "confirm" if state.get("status") == "flight_held" else "end"


def route_after_confirm(state):
    return "completion" if state.get("status") in {"confirmed", "completed"} else "end"


def build_booking_graph():
    graph = StateGraph(BookingState)
    graph.add_node("validate", validate_request)
    graph.add_node("search", search_node)
    graph.add_node("hold", hold_node)
    graph.add_node("confirm", confirm_node)
    graph.add_node("completion", check_completion)
    graph.add_edge(START, "validate")
    graph.add_conditional_edges("validate", route_after_validation, {"search": "search", "end": END})
    graph.add_conditional_edges("search", route_after_search, {"hold": "hold", "end": END})
    graph.add_conditional_edges("hold", route_after_hold, {"confirm": "confirm", "end": END})
    graph.add_conditional_edges("confirm", route_after_confirm, {"completion": "completion", "end": END})
    graph.add_edge("completion", END)
    return graph.compile()
