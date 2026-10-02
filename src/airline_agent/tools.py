from langchain_core.tools import tool

from airline_agent.database import (
    FLIGHTS,
    HOLDS,
    BOOKINGS,
)

# ==========================
# TOOLS 1
# ==========================
@tool
def search_flights(
    origin: str,
    destination: str,
    date: str,
) -> dict:
    """
    Search for available flights based on origin, destination, and date.

    Args:
        origin (str): The departure city.
        destination (str): The arrival city.
        date (str): The date of the flight in YYYY-MM-DD format.

    Returns:
        dict: A dictionary containing the search results with flight details.
    """
    results = [
        flight
        for flight in FLIGHTS
        if (
            flight["origin"] == origin.upper()
            and flight["destination"] == destination.upper()
            and flight["date"] == date
            and flight["available_seats"] > 0
        )
    ]

    return {
        "status": "ok",
        "count": len(results),
        "flights": results,
    }

# ==========================
# TOOLS 2
# ==========================
@tool
def get_flight_detail(flight_id: str) -> dict:
    """
    Get the details of a specific flight by its flight ID.
    """
    
    for flight in FLIGHTS:
        if flight["flight_id"] == flight_id.upper():
            return {
                "status": "ok",
                "flight": flight,
            }

    return {
        "status": "error",
        "message": f"Flight with ID {flight_id} not found.",
        "flight_id": flight_id,
    }

# ==========================
# TOOLS 3
# ==========================
@tool 
def hold_flight(flight_id: str, passenger_name: str) -> dict:
    """
    Hold one seat for a specific flight for a passenger.
    """
    for flight in FLIGHTS:
        if flight["flight_id"] == flight_id.upper():
            if flight["available_seats"] > 0:
                # Create a hold entry
                HOLDS[passenger_name] = {
                    "hold_id": f"HOLD-{len(HOLDS) + 1:03d}",
                    "flight_id": flight_id.upper(),
                    "passenger_name": passenger_name,
                    "status": "held",
                }
                # Decrease available seats
                flight["available_seats"] -= 1
                return {
                    "status": "ok",
                    "message": f"Flight {flight_id} held for passenger {passenger_name}.",
                    "hold": HOLDS[passenger_name],
                    "remaining_seats": flight["available_seats"],
                }
            else:
                return {
                    "status": "error",
                    "message": f"No available seats for flight {flight_id}.",
                    "flight_id": flight_id,
                }

    return {
        "status": "error",
        "message": f"Flight with ID {flight_id} not found.",
        "flight_id": flight_id,
    }


# ==========================
# TOOLS 4
# ==========================
@tool 
def confirm_booking(hold_id: str) -> dict:
    """
    Confirm a flight booking from an existing hold.
    """
    # Check if the hold exists
    hold = HOLDS.get(hold_id.upper())

    if hold is None:
        return {
            "status": "error",
            "error": "Hold not found.",
            "hold_id": hold_id,
        }

    # Check if the hold is still valid (not expired)
    if hold["status"] != "held":
        return {
            "status": "error",
            "error": "Hold is no longer valid.",
            "hold_id": hold_id,
        }

    # Create a booking entry
    booking_id = f"BOOK-{len(BOOKINGS) + 1:03d}"

    booking = {
        "booking_id": booking_id,
        "hold_id": hold["hold_id"],
        "flight_id": hold["flight_id"],
        "passenger_name": hold["passenger_name"],
        "status": "confirmed",
    }

    # Save the booking
    BOOKINGS[booking_id] = booking

    # Update the hold status to confirmed
    hold["status"] = "confirmed"

    return {
        "status": "ok",
        "message": f"Booking confirmed for hold {hold_id}.",
        "booking": booking,
    }

# ==========================
# TOOLS 5
# ==========================
@tool 
def cancel_hold(hold_id: str) -> dict:
    """
    Cancel an active flight hold and release the seat back to available seats.
    """
    # Check if the hold exists
    hold = HOLDS.get(hold_id.upper())

    if hold is None:
        return {
            "status": "error",
            "error": "Hold not found.",
            "hold_id": hold_id,
        }

    # Check if the hold is still valid (not expired)
    if hold["status"] != "held":
        return {
            "status": "error",
            "error": "Hold is no longer valid.",
            "hold_id": hold_id,
        }

    # Update the hold status to canceled
    hold["status"] = "canceled"

    # Increase available seats for the flight
    for flight in FLIGHTS:
        if flight["flight_id"] == hold["flight_id"]:
            flight["available_seats"] += 1
            break

    if flight is None:
        return {
            "status": "error",
            "error": "Flight not found for the hold.",
            "hold_id": hold_id,
            "flight_id": hold["flight_id"],
        }
    
    return {
        "status": "ok",
        "message": f"Hold {hold_id} has been canceled.",
        "hold": hold,
        "remaining_seats": flight["available_seats"],
    }
