import pytest

from airline_agent.database import reset_database
from airline_agent.fault_injection import FaultInjector
from airline_agent.react_agent import ReActAgent
from airline_agent.plan_execute_agent import PlanThenExecuteAgent
from airline_agent.hybrid_agent import HybridAgent


BASE_STATE = {
    "origin": "SGN",
    "destination": "HAN",
    "date": "2026-10-15",
    "passenger_name": "Nguyen Van A",
    "user_intent": "book",
    "user_confirmed_booking": True,
}


@pytest.fixture(autouse=True)
def clean_database():
    reset_database()
    yield
    reset_database()


def run_with_fault(agent_cls, scenario="sold_out_after_search"):
    injector = FaultInjector(scenario=scenario)
    result = agent_cls(fault_injector=injector).run(dict(BASE_STATE))
    return result, injector


def test_plan_then_execute_does_not_replan_after_dynamic_sold_out():
    result, injector = run_with_fault(PlanThenExecuteAgent)
    assert injector.triggered is True
    assert result["status"] == "handoff"
    assert not result.get("booking_id")


def test_react_recovers_after_dynamic_sold_out():
    result, injector = run_with_fault(ReActAgent)
    assert injector.triggered is True
    assert result["status"] == "completed"
    assert result.get("booking_id")
    assert result.get("retry_count", 0) >= 1
    assert "VN002" in result.get("excluded_flight_ids", [])
    assert result.get("flight_id") == "VN007"


def test_hybrid_replans_after_dynamic_sold_out():
    result, injector = run_with_fault(HybridAgent)
    assert injector.triggered is True
    assert result["status"] == "completed"
    assert result.get("booking_id")
    assert result.get("retry_count", 0) >= 1
    assert "VN002" in result.get("excluded_flight_ids", [])
    assert result.get("flight_id") == "VN007"


@pytest.mark.parametrize("agent_cls", [ReActAgent, HybridAgent])
def test_adaptive_agents_recover_from_dynamic_cancellation(agent_cls):
    result, injector = run_with_fault(agent_cls, "cancelled_after_search")
    assert injector.triggered is True
    assert result["status"] == "completed"
    assert result.get("flight_id") == "VN007"
