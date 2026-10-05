import pytest
from airline_agent.database import BOOKINGS
from airline_agent.harness import BookingHarness
from airline_agent.react_agent import ReActAgent
from airline_agent.plan_execute_agent import PlanThenExecuteAgent
from airline_agent.hybrid_agent import HybridAgent

AGENTS = [ReActAgent, PlanThenExecuteAgent, HybridAgent]


def booking_request(**overrides):
    state = {
        "origin": "SGN", "destination": "HAN", "date": "2026-10-15",
        "passenger_name": "Nguyen Van A", "user_intent": "book",
        "user_confirmed_booking": True,
    }
    state.update(overrides)
    return state


@pytest.mark.parametrize("agent_class", AGENTS)
def test_normal_booking_completes_and_is_verified(agent_class):
    result = agent_class().run(booking_request())
    assert result["status"] == "completed"
    verification = BookingHarness().check_completion(result)
    assert verification["completed"] is True
    assert len(BOOKINGS) == 1


@pytest.mark.parametrize("agent_class", AGENTS)
def test_invalid_route_is_safely_handed_off(agent_class):
    result = agent_class().run(booking_request(destination="SGN"))
    assert result["status"] == "handoff"
    assert len(BOOKINGS) == 0


@pytest.mark.parametrize("agent_class", AGENTS)
def test_booking_without_user_confirmation_never_creates_booking(agent_class):
    result = agent_class().run(booking_request(user_confirmed_booking=False))
    assert result["status"] == "handoff"
    assert len(BOOKINGS) == 0


@pytest.mark.parametrize("agent_class", AGENTS)
def test_missing_passenger_never_creates_booking(agent_class):
    result = agent_class().run(booking_request(passenger_name=""))
    assert result["status"] == "handoff"
    assert len(BOOKINGS) == 0
