from airline_agent.harness import BookingHarness


def test_validate_flight_request_valid():
    harness = BookingHarness()

    result = harness.validate_flight_request(
        origin="HN",
        destination="SGN",
        date="2026-10-15",
    )

    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_flight_request_invalid_airport():
    harness = BookingHarness()

    result = harness.validate_flight_request(
        origin="SG",
        destination="HN",
        date="2026-10-15",
    )

    assert result["valid"] is False
    assert "Origin must be a 3-letter airport code" in result["errors"]


def test_completion_not_completed():
    harness = BookingHarness()

    result = harness.check_completion({
        "origin": "SGN",
        "destination": "HN",
        "date": "2026-10-15",
        "passenger_name": "Nguyen Van A",
    })

    assert result["completed"] is False


def test_authorization_read_only():
    harness = BookingHarness()

    result = harness.check_authorization(
        "search_flights",
        {},
    )

    assert result["allowed"] is True


def test_authorization_requires_passenger():
    harness = BookingHarness()

    result = harness.check_authorization(
        "hold_flight",
        {},
    )

    assert result["allowed"] is False


def test_handoff():
    harness = BookingHarness()

    result = harness.handoff(
        reason="No available seats",
        attempted_actions=["search_flights", "hold_flight"],
        state={"flight_id": "VN001"},
        question="Có muốn chọn chuyến bay khác không?",
    )

    assert result["stop_reason"] == "No available seats"
    assert len(result["attempted_actions"]) == 2
    assert result["state"]["flight_id"] == "VN001"
    assert result["question_for_human"] != ""