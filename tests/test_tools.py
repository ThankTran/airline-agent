from airline_agent.database import BOOKINGS, HOLDS, get_flight_by_id
from airline_agent.tools import search_flights, hold_flight, confirm_booking, cancel_hold


def test_search_returns_only_available_matching_flights():
    result = search_flights.invoke({"origin": "SGN", "destination": "HAN", "date": "2026-10-15"})
    assert result["status"] == "ok"
    assert result["count"] == 2
    assert {f["flight_id"] for f in result["flights"]} == {"VN002", "VN007"}


def test_hold_reduces_one_seat():
    before = get_flight_by_id("VN002")["available_seats"]
    result = hold_flight.invoke({"flight_id": "VN002", "passenger_name": "Nguyen Van A"})
    assert result["status"] == "ok"
    assert get_flight_by_id("VN002")["available_seats"] == before - 1
    assert result["hold"]["hold_id"] in HOLDS


def test_confirm_creates_verified_booking_record():
    hold = hold_flight.invoke({"flight_id": "VN002", "passenger_name": "Nguyen Van A"})
    result = confirm_booking.invoke({"hold_id": hold["hold"]["hold_id"]})
    assert result["status"] == "ok"
    booking_id = result["booking"]["booking_id"]
    assert BOOKINGS[booking_id]["status"] == "confirmed"
    assert BOOKINGS[booking_id]["flight_id"] == "VN002"


def test_cancel_hold_releases_seat():
    before = get_flight_by_id("VN002")["available_seats"]
    hold = hold_flight.invoke({"flight_id": "VN002", "passenger_name": "Nguyen Van A"})
    hold_id = hold["hold"]["hold_id"]
    result = cancel_hold.invoke({"hold_id": hold_id})
    assert result["status"] == "ok"
    assert HOLDS[hold_id]["status"] == "cancelled"
    assert get_flight_by_id("VN002")["available_seats"] == before


def test_sold_out_flight_cannot_be_held():
    result = hold_flight.invoke({"flight_id": "VN008", "passenger_name": "Nguyen Van A"})
    assert result["status"] == "error"
    assert result["error_code"] == "NO_AVAILABLE_SEATS"
    assert result["retryable"] is True
