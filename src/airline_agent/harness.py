from collections import deque
from datetime import datetime
from typing import Any

from airline_agent.database import BOOKINGS, FLIGHTS, HOLDS, get_flight_by_id


class LoopDetector:
    """Phát hiện duplicate action/observation và trạng thái không tiến triển."""

    NON_REPEATABLE_ACTIONS = {"hold_flight", "confirm_booking", "cancel_hold"}

    def __init__(self, window=6, repeat_k=2, same_obs_k=4, stall_n=5):
        self.recent = deque(maxlen=window)
        self.observations = deque(maxlen=window)
        self.repeat_k = repeat_k
        self.same_obs_k = same_obs_k
        self.stall_n = stall_n
        self.last_progress = None
        self.stall_count = 0

    @staticmethod
    def _freeze(value: Any):
        if isinstance(value, dict):
            return tuple(sorted((k, LoopDetector._freeze(v)) for k, v in value.items()))
        if isinstance(value, list):
            return tuple(LoopDetector._freeze(v) for v in value)
        return value

    def check(self, tool: str, args: dict, observation=None, progress=None, check_action=True):
        if check_action:
            fingerprint = (tool, self._freeze(args))
            count = self.recent.count(fingerprint) + 1
            # Side-effect actions bị chặn sớm; read-only actions được phép lặp nếu còn progress.
            if tool in self.NON_REPEATABLE_ACTIONS and count >= self.repeat_k:
                return f"LOOP_DUPLICATE_ACTION: {tool} repeated {count} times with same args."
            self.recent.append(fingerprint)

        if observation is not None:
            observation_fp = self._freeze(observation)
            count_obs = self.observations.count(observation_fp) + 1
            if count_obs >= self.same_obs_k:
                return f"LOOP_DUPLICATE_OBSERVATION: same observation repeated {count_obs} times."
            self.observations.append(observation_fp)

        if progress is not None:
            progress_fp = self._freeze(progress)
            if progress_fp == self.last_progress:
                self.stall_count += 1
            else:
                self.stall_count = 0
            self.last_progress = progress_fp
            if self.stall_count >= self.stall_n:
                return f"LOOP_NO_PROGRESS: business state stalled for {self.stall_count} checks."

        return None


class BookingHarness:
    READ_ONLY_ACTIONS = {"search_flights", "get_flight_detail"}
    WRITE_ACTIONS = {"hold_flight", "cancel_hold"}
    COMMIT_ACTIONS = {"confirm_booking"}

    def validate_flight_request(self, origin: str, destination: str, date: str) -> dict:
        errors = []
        origin = (origin or "").strip().upper()
        destination = (destination or "").strip().upper()
        date = (date or "").strip()

        if not origin:
            errors.append("Origin is required.")
        elif len(origin) != 3 or not origin.isalpha():
            errors.append("Origin must be a 3-letter airport code.")

        if not destination:
            errors.append("Destination is required.")
        elif len(destination) != 3 or not destination.isalpha():
            errors.append("Destination must be a 3-letter airport code.")

        if origin and destination and origin == destination:
            errors.append("Origin and destination must be different.")

        if not date:
            errors.append("Date is required.")
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                errors.append("Date must use YYYY-MM-DD format.")

        return {"valid": not errors, "errors": errors}

    def validate_selected_flight(self, state: dict) -> dict:
        flight_id = state.get("flight_id")
        if not flight_id:
            return {"valid": False, "reason": "No flight has been selected."}

        flight = get_flight_by_id(flight_id)
        if not flight:
            return {"valid": False, "reason": "Selected flight does not exist."}

        expected = (state.get("origin"), state.get("destination"), state.get("date"))
        actual = (flight["origin"], flight["destination"], flight["date"])
        if actual != expected:
            return {"valid": False, "reason": "Selected flight does not match requested route/date."}

        if flight.get("status") != "available" or flight.get("available_seats", 0) <= 0:
            return {"valid": False, "reason": "Selected flight is not currently available."}

        return {"valid": True, "reason": "Selected flight is valid."}

    def validate_hold_for_confirmation(self, state: dict) -> dict:
        hold_id = state.get("hold_id")
        hold = HOLDS.get(hold_id) if hold_id else None
        if not hold:
            return {"valid": False, "reason": "Hold does not exist."}
        if hold.get("status") != "active":
            return {"valid": False, "reason": f"Hold is not active (status={hold.get('status')})."}
        if hold.get("passenger_name") != state.get("passenger_name"):
            return {"valid": False, "reason": "Hold belongs to a different passenger."}
        if hold.get("flight_id") != state.get("flight_id"):
            return {"valid": False, "reason": "Hold belongs to a different flight."}
        return {"valid": True, "reason": "Hold is valid."}

    def check_authorization(self, action: str, state: dict) -> dict:
        if action in self.READ_ONLY_ACTIONS:
            return {"allowed": True, "reason": "Read-only action is allowed."}

        if action in self.WRITE_ACTIONS:
            if not (state.get("passenger_name") or "").strip():
                return {"allowed": False, "reason": "Passenger name is required for state-changing actions."}
            return {"allowed": True, "reason": "Write action authorized."}

        if action in self.COMMIT_ACTIONS:
            if not (state.get("passenger_name") or "").strip():
                return {"allowed": False, "reason": "Passenger name is required before booking."}
            if not state.get("user_confirmed_booking", False):
                return {"allowed": False, "reason": "Explicit user confirmation is required before confirming booking."}
            return {"allowed": True, "reason": "Commit action explicitly authorized."}

        return {"allowed": False, "reason": f"Unknown action: {action}."}

    def check_completion(self, state: dict) -> dict:
        required = ["origin", "destination", "date", "flight_id", "passenger_name", "hold_id", "booking_id"]
        missing = [field for field in required if not state.get(field)]
        if missing:
            return {"completed": False, "reason": "missing_fields", "missing": missing}

        booking = BOOKINGS.get(state["booking_id"])
        if not booking:
            return {"completed": False, "reason": "booking_not_found", "missing": []}
        if booking.get("status") != "confirmed":
            return {"completed": False, "reason": "booking_not_confirmed", "missing": []}
        if booking.get("flight_id") != state.get("flight_id"):
            return {"completed": False, "reason": "wrong_flight", "missing": []}
        if booking.get("passenger_name") != state.get("passenger_name"):
            return {"completed": False, "reason": "wrong_passenger", "missing": []}

        flight = get_flight_by_id(booking["flight_id"])
        if not flight:
            return {"completed": False, "reason": "flight_not_found", "missing": []}
        if (flight["origin"], flight["destination"], flight["date"]) != (
            state["origin"], state["destination"], state["date"]
        ):
            return {"completed": False, "reason": "booking_does_not_match_request", "missing": []}

        return {
            "completed": True,
            "reason": "verified_booking",
            "missing": [],
            "booking_id": state["booking_id"],
        }

    def handoff(self, reason: str, attempted_action: list, state: dict, question: str) -> dict:
        return {
            "stop_reason": reason,
            "attempted_actions": list(attempted_action),
            "state_snapshot": dict(state),
            "question_for_human": question,
        }

    @staticmethod
    def progress_snapshot(state: dict):
        return {
            "status": state.get("status"),
            "flight_id": state.get("flight_id"),
            "hold_id": state.get("hold_id"),
            "booking_id": state.get("booking_id"),
        }

    def before_tool(self, action: str, args: dict, state: dict, loop_detector: LoopDetector) -> dict:
        auth = self.check_authorization(action, state)
        if not auth["allowed"]:
            return {"allowed": False, "stop": True, "reason": auth["reason"]}

        if action == "hold_flight":
            check = self.validate_selected_flight(state)
            if not check["valid"]:
                return {"allowed": False, "stop": True, "reason": check["reason"]}

        if action == "confirm_booking":
            check = self.validate_hold_for_confirmation(state)
            if not check["valid"]:
                return {"allowed": False, "stop": True, "reason": check["reason"]}

        loop_reason = loop_detector.check(tool=action, args=args)
        if loop_reason:
            return {"allowed": False, "stop": True, "reason": loop_reason}

        return {"allowed": True, "stop": False, "reason": ""}

    def after_tool(self, action: str, args: dict, result: dict, state: dict, loop_detector: LoopDetector) -> dict:
        loop_reason = loop_detector.check(
            tool=action,
            args=args,
            observation=result,
            progress=self.progress_snapshot(state),
            check_action=False,
        )
        if loop_reason:
            return {
                "continue": False,
                "completed": False,
                "handoff": self.handoff(
                    loop_reason,
                    state.get("attempted_actions", []),
                    state,
                    "Please review the repeated actions/observations and decide the next safe step.",
                ),
            }

        completion = self.check_completion(state)
        if completion["completed"]:
            return {"continue": False, "completed": True, "handoff": None, "completion": completion}

        return {"continue": True, "completed": False, "handoff": None, "completion": completion}
