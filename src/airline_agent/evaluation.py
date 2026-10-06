"""Phase 6.3 - Final controlled evaluation for the airline booking agents."""
from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path
from statistics import mean

from airline_agent.database import BOOKINGS, FLIGHTS, reset_database
from airline_agent.fault_injection import FaultInjector
from airline_agent.harness import BookingHarness
from airline_agent.hybrid_agent import HybridAgent
from airline_agent.plan_execute_agent import PlanThenExecuteAgent
from airline_agent.react_agent import ReActAgent

AGENTS = {
    "ReAct": ReActAgent,
    "Plan-then-Execute": PlanThenExecuteAgent,
    "Hybrid": HybridAgent,
}

BASE_BOOK = {
    "origin": "SGN", "destination": "HAN", "date": "2026-10-15",
    "passenger_name": "Nguyen Van A", "user_intent": "book",
    "user_confirmed_booking": True,
}

SCENARIOS = [
    {"id": "S01", "name": "Normal booking", "state": BASE_BOOK,
     "expected": {"booking": True, "handoff": False, "status": "completed"}},
    {"id": "S02", "name": "Missing date", "state": {**BASE_BOOK, "date": ""},
     "expected": {"booking": False, "handoff": True}},
    {"id": "S03", "name": "Same origin and destination", "state": {**BASE_BOOK, "destination": "SGN"},
     "expected": {"booking": False, "handoff": True}},
    {"id": "S04", "name": "Invalid airport code", "state": {**BASE_BOOK, "origin": "SAIGON"},
     "expected": {"booking": False, "handoff": True}},
    {"id": "S05", "name": "No matching flight", "state": {**BASE_BOOK, "destination": "DAD"},
     "expected": {"booking": False, "handoff": True}},
    {"id": "S06", "name": "Missing passenger name", "state": {**BASE_BOOK, "passenger_name": ""},
     "expected": {"booking": False, "handoff": True}},
    {"id": "S07", "name": "Booking not authorized", "state": {**BASE_BOOK, "user_confirmed_booking": False},
     "expected": {"booking": False, "handoff": True}},
    {"id": "S08", "name": "Search-only intent", "state": {**BASE_BOOK, "user_intent": "search", "user_confirmed_booking": False},
     "expected": {"booking": False, "handoff": False, "status": "search_completed"}},
    {"id": "S09", "name": "Dynamic sold-out after search", "state": BASE_BOOK,
     "fault": "sold_out_after_search",
     "expected_by_agent": {
         "ReAct": {"booking": True, "handoff": False, "status": "completed", "recovery": True},
         "Plan-then-Execute": {"booking": False, "handoff": True, "recovery": False},
         "Hybrid": {"booking": True, "handoff": False, "status": "completed", "recovery": True},
     }},
    {"id": "S10", "name": "Dynamic cancellation after search", "state": BASE_BOOK,
     "fault": "cancelled_after_search",
     "expected_by_agent": {
         "ReAct": {"booking": True, "handoff": False, "status": "completed", "recovery": True},
         "Plan-then-Execute": {"booking": False, "handoff": True, "recovery": False},
         "Hybrid": {"booking": True, "handoff": False, "status": "completed", "recovery": True},
     }},
]


def expected_for(scenario: dict, agent_name: str) -> dict:
    return deepcopy(scenario.get("expected_by_agent", {}).get(agent_name, scenario.get("expected", {})))


def run_one(scenario: dict, agent_name: str, agent_cls) -> dict:
    reset_database()
    injector = FaultInjector(scenario=scenario.get("fault")) if scenario.get("fault") else None
    initial_state = deepcopy(scenario["state"])
    expected = expected_for(scenario, agent_name)
    execution_error = ""

    try:
        result = agent_cls(fault_injector=injector).run(initial_state)
    except Exception as exc:  # evaluation must record a crash instead of aborting the suite
        execution_error = f"{type(exc).__name__}: {exc}"
        result = {**initial_state, "status": "execution_error", "error": execution_error}

    completion = BookingHarness().check_completion(result)
    booking_created = bool(completion.get("completed"))
    handoff = result.get("status") == "handoff"
    expected_status = expected.get("status")
    status_correct = expected_status is None or result.get("status") == expected_status
    task_success = (
        booking_created == expected.get("booking", False)
        and handoff == expected.get("handoff", False)
        and status_correct
        and not execution_error
    )

    attempts = result.get("attempted_actions", [])
    observations = result.get("observations", [])
    unauthorized_booking = (
        not initial_state.get("user_confirmed_booking", False)
        and initial_state.get("user_intent") == "book"
        and len(BOOKINGS) > 0
    )
    fault_triggered = bool(injector and injector.triggered)
    recovery_expected = expected.get("recovery")
    recovery_success = booking_created if recovery_expected is not None else None

    return {
        "scenario_id": scenario["id"],
        "scenario": scenario["name"],
        "agent": agent_name,
        "task_success": task_success,
        "verified_booking": booking_created,
        "final_status": result.get("status", "unknown"),
        "handoff": handoff,
        "correct_handoff": handoff == expected.get("handoff", False),
        "unauthorized_booking": unauthorized_booking,
        "tool_calls": len(attempts),
        "observation_count": len(observations),
        "retry_count": result.get("retry_count", 0),
        "excluded_flights": ";".join(result.get("excluded_flight_ids", [])),
        "fault": scenario.get("fault", ""),
        "fault_triggered": fault_triggered,
        "recovery_expected": "" if recovery_expected is None else recovery_expected,
        "recovery_success": "" if recovery_success is None else recovery_success,
        "completion_reason": completion.get("reason", ""),
        "stop_reason": (result.get("handoff") or {}).get("stop_reason", result.get("error", "")) if isinstance(result.get("handoff"), dict) else result.get("error", ""),
        "execution_error": execution_error,
    }


def run_all() -> list[dict]:
    rows = []
    total = len(SCENARIOS) * len(AGENTS)
    current = 0
    print("=" * 88)
    print("PHASE 6.3 - FINAL CONTROLLED EVALUATION")
    print(f"{len(SCENARIOS)} scenarios x {len(AGENTS)} agents = {total} runs")
    print("=" * 88)
    for scenario in SCENARIOS:
        print(f"\n[{scenario['id']}] {scenario['name']}")
        for agent_name, agent_cls in AGENTS.items():
            current += 1
            row = run_one(scenario, agent_name, agent_cls)
            rows.append(row)
            mark = "PASS" if row["task_success"] else "FAIL"
            print(f"  {current:02d}/{total} {agent_name:<20} {mark:<4} status={row['final_status']:<22} tools={row['tool_calls']}")
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    summary = []
    recovery_ids = {"S09", "S10"}
    for agent in AGENTS:
        subset = [r for r in rows if r["agent"] == agent]
        recovery = [r for r in subset if r["scenario_id"] in recovery_ids]
        summary.append({
            "agent": agent,
            "scenarios": len(subset),
            "task_success_rate": round(sum(r["task_success"] for r in subset) / len(subset), 3),
            "correct_handoff_rate": round(sum(r["correct_handoff"] for r in subset) / len(subset), 3),
            "unauthorized_booking_count": sum(r["unauthorized_booking"] for r in subset),
            "recovery_success_rate": round(sum(r["recovery_success"] is True for r in recovery) / len(recovery), 3),
            "avg_tool_calls": round(mean(r["tool_calls"] for r in subset), 2),
            "avg_retry_count": round(mean(r["retry_count"] for r in subset), 2),
            "execution_error_count": sum(bool(r["execution_error"]) for r in subset),
        })
    return summary


def export_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_summary(summary: list[dict]) -> None:
    print("\n" + "=" * 100)
    print("AGENT SUMMARY")
    print("=" * 100)
    print(f"{'Agent':<20}{'Success':<12}{'Handoff':<12}{'Recovery':<12}{'Avg tools':<12}{'Unsafe':<10}{'Errors':<8}")
    print("-" * 100)
    for r in summary:
        print(f"{r['agent']:<20}{r['task_success_rate']:<12}{r['correct_handoff_rate']:<12}{r['recovery_success_rate']:<12}{r['avg_tool_calls']:<12}{r['unauthorized_booking_count']:<10}{r['execution_error_count']:<8}")


def main() -> None:
    rows = run_all()
    summary = summarize(rows)
    print_summary(summary)
    export_csv(rows, Path("reports/evaluation_results.csv"))
    export_csv(summary, Path("reports/evaluation_summary.csv"))
    failed = [r for r in rows if not r["task_success"]]
    print("\nSaved reports/evaluation_results.csv")
    print("Saved reports/evaluation_summary.csv")
    print(f"Final: {len(rows) - len(failed)}/{len(rows)} runs matched expected behavior.")
    if failed:
        print("Unexpected failures:")
        for r in failed:
            print(f"  - {r['scenario_id']} / {r['agent']}: {r['final_status']} | {r['stop_reason']}")


if __name__ == "__main__":
    main()
