from airline_agent.database import (
    FLIGHTS,
    HOLDS,
    BOOKINGS,
)

def test_flight_database_exists():
    assert len(FLIGHTS) > 0, "Flight database should not be empty"

def test_flight_has_required_fields():
    required_fields = {
        "flight_id",
        "airline",
        "origin",
        "destination",
        "date",
        "departure",
        "arrival",
        "price",
        "currency",
        "available_seats",
        "baggage",
        "cabin",
    }
    for flight in FLIGHTS:
        assert required_fields.issubset(flight.keys()), f"Flight {flight['flight_id']} is missing required fields"

def test_booking_database_is_empty():
    assert len(BOOKINGS) == 0, "Booking database should be empty initially"
    assert isinstance(BOOKINGS, dict), "Booking database should be a dictionary"
    assert isinstance(HOLDS, dict), "Holds database should be a dictionary"