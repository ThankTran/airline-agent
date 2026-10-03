from collections import deque

from airline_agent.database import (
    FLIGHTS,
    HOLDS,
    BOOKINGS,
)

class LoopDetector:
    """
    Phát hiện vòng lặp trong các hành động của agent
    Sử dụng một deque để lưu trữ các hành động gần đây và kiểm tra xem có hành động nào lặp lại hay không.
    
    3 tín hiệu:
    1. Cùng tool + cùng arguments được gọi lặp lại
    2. Các tool khác nhau nhưng trả về cùng observation
    3. Trạng thái nghiệp vụ không tiến triển
    """
    def __init__(
        self,
        window=6,
        repeat_k=2,
        same_obs_k=4,
        stall_n=5,
    ):
        self.recent = deque(maxlen=window)
        self.observations = deque(maxlen=window)

        self.repeat_k = repeat_k
        self.same_obs_k = same_obs_k
        self.stall_n = stall_n
        self.last_state = None
        self.stall_count = 0

    def check(
        self,
        tool: str,
        args: dict,
        observation=None,
        progress=None,
    ):
        """
        Trả về cảnh báo nếu phát hiện vòng lặp
        Trả về None nếu không phát hiện vòng lặp
        """

        # ==========================
        # 1. Kiểm tra trùng action
        # ==========================
        fingerprint = (
            tool,
            repr(sorted(args.items())),
        )

        count = self.recent.count(fingerprint) + 1

        if count >= self.repeat_k:
            return {
                f"LOOP: '{tool}' được gọi {count} lần"
                f" với cùng arguments {args}",
            }
        self.recent.append(fingerprint)

        # ==========================
        # 2. Kiểm tra trùng observation
        # ==========================

        if observation is not None:
            observation_fp = repr(observation)

            count_obs = self.observations.count(observation_fp) + 1

            if count_obs >= self.same_obs_k:
                return (
                    f"LOOP: Nhận được cùng observation {count_obs} lần: "
                    f"trả về cùng kết quả {observation}"
                )
            self.observations.append(observation_fp)

        # ==========================
        # 3. Kiểm tra trạng thái nghiệp vụ không tiến triển
        # ==========================
        if progress is not None:

            if progress == self.last_state:
                self.stall_count += 1
            else:
                self.stall_count = 0

            self.last_state = progress

            if self.stall_count >= self.stall_n:
                return (
                    f"LOOP: Trạng thái nghiệp vụ không tiến triển "
                    f"trong {self.stall_count} lần liên tiếp: {progress}"
                )
        return None

class BookingHarness:
    """
    Harness kiểm soát agent đặt vé máy bay

    Harness chịu trách nhiệm:
    1. Kiểm tra ràng buộc dữ liệu
    2. Kiểm tra điều kiện hoàn thành
    3. Kiểm tra quyền thực hiện hành động
    4. Bàn giao khi agent không thể hoàn thành an toàn
    """

    # =========================================================
    # 1. DATA CONSTRAINTS
    # =========================================================
    def validate_flight_request(
        self,
        origin: str,
        destination: str,
        date: str,
    ) -> dict:
        """
        Kiểm tra dữ liệu đầu vào của yêu cầu tìm chuyến bay
        """
        errors = []

        if not origin:
            errors.append("Origin is required.")

        if not destination:
            errors.append("Destination is required.")

        if not date:
            errors.append("Date is required.")

        if origin and len(origin) != 3:
            errors.append("Origin must be a 3-letter airport code.")

        if destination and len(destination) != 3:
            errors.append("Destination must be a 3-letter airport code.")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    # =========================================================
    # 2. COMPLETION CRITERIA
    # =========================================================
    def check_completion(self, state: dict) -> bool:
        """
        Kiểm tra xem agent đã hoàn thành nhiệm vụ đặt vé hay chưa
        """
        required_fields = [
            "origin",
            "destination",
            "date",
            "flight_id",
            "passenger_name",
            "hold_id",
            "booking_id",
        ]

        missing = [
            field
            for field in required_fields
            if not state.get(field)
        ]

        booking_id = state.get("booking_id")

        if booking_id and booking_id in BOOKINGS:
            booking_confirmed = (
                BOOKINGS[booking_id]["status"] == "confirmed"
            )
        else:
            booking_confirmed = False

        return {
            "completed": (
                len(missing) == 0 
                and booking_confirmed
            ),
            "missing": missing,
            "booking_confirmed": booking_confirmed,
        }

# ========================================================
# 3. AUTHORIZATION CHECKS
# ========================================================
def check_authorization(
    self,
    action: str,
    state: dict,
) -> dict:
    """
    Kiểm tra xem agent có quyền thực hiện hành động hay không
    """

    # Only read actions are allowed for now
    read_only_actions = {
        "search_flights",
        "get_flight_detail",
    }

    # Action can change state, so we need to check if the agent is authorized
    state_changing_actions = {
        "hold_flight",
        "confirm_booking",
        "cancel_hold",
    }

    if action in read_only_actions:
        return {
            "allowed": True,
            "reason": "Read-only action is allowed.",
        }

    if action in state_changing_actions:
        if not state.get("passenger_name"):
            return {
                "allowed": False,
                "reason": "Passenger name is required for state-changing actions.",
            }
        
        return {
            "allowed": False,
            "reason": "Required passenger information exists",
        }

    return {
        "allowed": False,
        "reason": "Unknown action",
    }

# ========================================================
# 4. HANDOFF MECHANISM
# ========================================================
def handoff(
    self, 
    reason: str,
    attempted_action: list,
    state: dict,
    question: str,
) -> dict:
    """
    Bàn giao cho con người khi agent không thể hoàn thành nhiệm vụ an toàn
    """
    return {
        "stop_reason": reason,
        "attempted_action": attempted_action,
        "state": state,
        "question_for_human": question,
    }