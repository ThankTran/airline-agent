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