from langchain_core.tools import tool

from airline_agent.database import FLIGHTS, HOLDS, BOOKINGS, get_flight_by_id


def _error(error_code: str, message: str, retryable: bool = False, **extra) -> dict:
    return {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "retryable": retryable,
        **extra,
    }


@tool
def search_flights(origin: str, destination: str, date: str) -> dict:
    """Search available flights by route and date."""
    origin = origin.upper()
    destination = destination.upper()

    results = [
        dict(flight)
        for flight in FLIGHTS
        if flight["origin"] == origin
        and flight["destination"] == destination
        and flight["date"] == date
        and flight.get("status") == "available"
        and flight["available_seats"] > 0
    ]

    return {
        "status": "ok",
        "count": len(results),
        "flights": results,
    }


@tool
def get_flight_detail(flight_id: str) -> dict:
    """Get one flight by ID."""
    flight = get_flight_by_id(flight_id)
    if not flight:
        return _error(
            "FLIGHT_NOT_FOUND",
            f"Flight {flight_id} does not exist.",
            retryable=False,
            flight_id=flight_id,
        )

    return {"status": "ok", "flight": dict(flight)}


@tool
def hold_flight(flight_id: str, passenger_name: str) -> dict:
    """Hold one seat for a passenger."""
    flight = get_flight_by_id(flight_id)
    if not flight:
        return _error(
            "FLIGHT_NOT_FOUND",
            f"Flight {flight_id} does not exist.",
            retryable=False,
            flight_id=flight_id,
        )

    if flight.get("status") == "cancelled":
        return _error(
            "FLIGHT_CANCELLED",
            f"Flight {flight_id} has been cancelled.",
            retryable=True,
            flight_id=flight_id,
        )

    if flight.get("status") == "sold_out" or flight["available_seats"] <= 0:
        return _error(
            "NO_AVAILABLE_SEATS",
            f"No available seats for flight {flight_id}.",
            retryable=True,
            flight_id=flight_id,
        )

    hold_id = f"HOLD-{len(HOLDS) + 1:03d}"
    hold = {
        "hold_id": hold_id,
        "flight_id": flight["flight_id"],
        "passenger_name": passenger_name.strip(),
        "status": "active",
    }
    HOLDS[hold_id] = hold
    flight["available_seats"] -= 1
    if flight["available_seats"] == 0:
        flight["status"] = "sold_out"

    return {
        "status": "ok",
        "message": f"Flight {flight_id} held for {passenger_name}.",
        "hold": dict(hold),
        "remaining_seats": flight["available_seats"],
    }


@tool
def confirm_booking(hold_id: str) -> dict:
    """Confirm a booking from an active hold."""
    hold_id = hold_id.upper()
    hold = HOLDS.get(hold_id)
    if hold is None:
        return _error("HOLD_NOT_FOUND", "Hold not found.", False, hold_id=hold_id)

    if hold["status"] == "expired":
        return _error("HOLD_EXPIRED", "Hold has expired.", True, hold_id=hold_id)

    if hold["status"] != "active":
        return _error(
            "HOLD_NOT_ACTIVE",
            f"Hold is not active (status={hold['status']}).",
            False,
            hold_id=hold_id,
        )

    booking_id = f"BOOK-{len(BOOKINGS) + 1:03d}"
    booking = {
        "booking_id": booking_id,
        "hold_id": hold["hold_id"],
        "flight_id": hold["flight_id"],
        "passenger_name": hold["passenger_name"],
        "status": "confirmed",
    }
    BOOKINGS[booking_id] = booking
    hold["status"] = "confirmed"

    return {
        "status": "ok",
        "message": f"Booking confirmed for hold {hold_id}.",
        "booking": dict(booking),
    }


@tool
def cancel_hold(hold_id: str) -> dict:
    """Cancel an active hold and release its seat."""
    hold_id = hold_id.upper()
    hold = HOLDS.get(hold_id)
    if hold is None:
        return _error("HOLD_NOT_FOUND", "Hold not found.", False, hold_id=hold_id)

    if hold["status"] != "active":
        return _error(
            "HOLD_NOT_ACTIVE",
            f"Hold is not active (status={hold['status']}).",
            False,
            hold_id=hold_id,
        )

    hold["status"] = "cancelled"
    flight = get_flight_by_id(hold["flight_id"])
    if not flight:
        return _error(
            "FLIGHT_NOT_FOUND",
            "Flight for the hold no longer exists.",
            False,
            hold_id=hold_id,
        )

    flight["available_seats"] += 1
    if flight.get("status") == "sold_out":
        flight["status"] = "available"

    return {
        "status": "ok",
        "message": f"Hold {hold_id} cancelled.",
        "hold": dict(hold),
        "remaining_seats": flight["available_seats"],
    }
