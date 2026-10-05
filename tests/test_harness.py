from airline_agent.database import BOOKINGS
from airline_agent.harness import BookingHarness, LoopDetector
from airline_agent.tools import hold_flight, confirm_booking


def base_state(**overrides):
    state = {
        "origin": "SGN", "destination": "HAN", "date": "2026-10-15",
        "passenger_name": "Nguyen Van A", "user_intent": "book",
        "user_confirmed_booking": True, "flight_id": "VN002",
        "attempted_actions": [], "observations": [],
    }
    state.update(overrides)
    return state


def test_request_validation_rejects_same_airport():
    result = BookingHarness().validate_flight_request("SGN", "SGN", "2026-10-15")
    assert result["valid"] is False


def test_confirm_requires_explicit_user_authorization():
    result = BookingHarness().check_authorization("confirm_booking", base_state(user_confirmed_booking=False))
    assert result["allowed"] is False
    assert "confirmation" in result["reason"].lower()


def test_hold_requires_passenger_name():
    result = BookingHarness().check_authorization("hold_flight", base_state(passenger_name=""))
    assert result["allowed"] is False


def test_completion_verifies_real_database_booking():
    state = base_state()
    hold = hold_flight.invoke({"flight_id": "VN002", "passenger_name": state["passenger_name"]})
    state["hold_id"] = hold["hold"]["hold_id"]
    booking = confirm_booking.invoke({"hold_id": state["hold_id"]})
    state["booking_id"] = booking["booking"]["booking_id"]
    result = BookingHarness().check_completion(state)
    assert result["completed"] is True
    assert result["reason"] == "verified_booking"
    assert state["booking_id"] in BOOKINGS


def test_completion_rejects_fake_booking_id():
    state = base_state(hold_id="HOLD-999", booking_id="BOOK-999")
    result = BookingHarness().check_completion(state)
    assert result["completed"] is False
    assert result["reason"] == "booking_not_found"


def test_loop_detector_blocks_duplicate_side_effect_action():
    detector = LoopDetector(repeat_k=2)
    args = {"flight_id": "VN002", "passenger_name": "Nguyen Van A"}
    assert detector.check("hold_flight", args) is None
    reason = detector.check("hold_flight", args)
    assert reason is not None
    assert reason.startswith("LOOP_DUPLICATE_ACTION")


def test_read_only_duplicate_action_is_not_blocked_immediately():
    detector = LoopDetector(repeat_k=2)
    args = {"origin": "SGN", "destination": "HAN", "date": "2026-10-15"}
    assert detector.check("search_flights", args) is None
    assert detector.check("search_flights", args) is None
