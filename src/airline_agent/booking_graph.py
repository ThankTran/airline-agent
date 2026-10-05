from langgraph.graph import StateGraph, START, END

from airline_agent.state import BookingState
from airline_agent.harness import BookingHarness, LoopDetector
from airline_agent.tools import (
    search_flights,
    hold_flight,
    confirm_booking,
)


harness = BookingHarness()


def validate_request(state: BookingState) -> BookingState:
    result = harness.validate_flight_request(
        state.get("origin", ""),
        state.get("destination", ""),
        state.get("date", ""),
    )

    if not result["valid"]:
        return {
            **state,
            "status": "invalid_request",
            "error": "; ".join(result["errors"]),
        }

    return {
        **state,
        "status": "request_valid",
    }


def search_node(state: BookingState) -> BookingState:
    detector = LoopDetector()

    args = {
        "origin": state["origin"],
        "destination": state["destination"],
        "date": state["date"],
    }

    before = harness.before_tool(
        action="search_flights",
        args=args,
        state=state,
        loop_detector=detector,
    )

    if before["stop"]:
        return {
            **state,
            "status": "handoff",
            "error": before["reason"],
        }

    result = search_flights.invoke(args)

    if result["status"] != "ok" or result["count"] == 0:
        return {
            **state,
            "status": "no_flight",
            "error": "No available flight",
        }

    first_flight = result["flights"][0]

    return {
        **state,
        "flight_id": first_flight["flight_id"],
        "status": "flight_found",
    }


def hold_node(state: BookingState) -> BookingState:
    detector = LoopDetector()

    args = {
        "flight_id": state["flight_id"],
        "passenger_name": state["passenger_name"],
    }

    before = harness.before_tool(
        action="hold_flight",
        args=args,
        state=state,
        loop_detector=detector,
    )

    if before["stop"]:
        return {
            **state,
            "status": "handoff",
            "error": before["reason"],
        }

    result = hold_flight.invoke(args)

    if result["status"] != "ok":
        return {
            **state,
            "status": "hold_failed",
            "error": result["error"],
        }

    return {
        **state,
        "hold_id": result["hold"]["hold_id"],
        "status": "flight_held",
    }


def confirm_node(state: BookingState) -> BookingState:
    detector = LoopDetector()

    args = {
        "hold_id": state["hold_id"],
    }

    before = harness.before_tool(
        action="confirm_booking",
        args=args,
        state=state,
        loop_detector=detector,
    )

    if before["stop"]:
        return {
            **state,
            "status": "handoff",
            "error": before["reason"],
        }

    result = confirm_booking.invoke(args)

    if result["status"] != "ok":
        return {
            **state,
            "status": "confirmation_failed",
            "error": result["error"],
        }

    return {
        **state,
        "booking_id": result["booking"]["booking_id"],
        "status": "confirmed",
    }


def check_completion(state: BookingState) -> BookingState:
    result = harness.check_completion(state)

    if result["completed"]:
        return {
            **state,
            "status": "completed",
        }

    return {
        **state,
        "status": "incomplete",
        "error": ", ".join(result["missing"]),
    }


def route_after_validation(state: BookingState):
    if state.get("status") == "request_valid":
        return "search"

    return "end"


def route_after_search(state: BookingState):
    if state.get("status") == "flight_found":
        return "hold"

    return "end"


def route_after_hold(state: BookingState):
    if state.get("status") == "flight_held":
        return "confirm"

    return "end"


def route_after_confirm(state: BookingState):
    return "completion"


def build_booking_graph():
    graph = StateGraph(BookingState)

    graph.add_node("validate", validate_request)
    graph.add_node("search", search_node)
    graph.add_node("hold", hold_node)
    graph.add_node("confirm", confirm_node)
    graph.add_node("completion", check_completion)

    graph.add_edge(START, "validate")

    graph.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "search": "search",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "search",
        route_after_search,
        {
            "hold": "hold",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "hold",
        route_after_hold,
        {
            "confirm": "confirm",
            "end": END,
        },
    )

    graph.add_edge("confirm", "completion")
    graph.add_edge("completion", END)

    return graph.compile()