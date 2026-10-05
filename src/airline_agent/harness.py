from collections import deque

from airline_agent.database import (
    FLIGHTS,
    HOLDS,
    BOOKINGS,
)


class LoopDetector:
    """
    Phát hiện vòng lặp trong các hành động của agent.

    Sử dụng deque để lưu trữ các hành động gần đây
    và kiểm tra xem có hành động nào lặp lại hay không.

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
        Trả về cảnh báo nếu phát hiện vòng lặp.
        Trả về None nếu không phát hiện vòng lặp.
        """

        # ========================================================
        # 1. Kiểm tra trùng action
        # ========================================================

        fingerprint = (
            tool,
            repr(sorted(args.items())),
        )

        count = self.recent.count(fingerprint) + 1

        if count >= self.repeat_k:
            return (
                f"LOOP: '{tool}' được gọi {count} lần "
                f"với cùng arguments {args}"
            )

        self.recent.append(fingerprint)

        # ========================================================
        # 2. Kiểm tra trùng observation
        # ========================================================

        if observation is not None:
            observation_fp = repr(observation)

            count_obs = (
                self.observations.count(observation_fp) + 1
            )

            if count_obs >= self.same_obs_k:
                return (
                    f"LOOP: Nhận được cùng observation "
                    f"{count_obs} lần: "
                    f"trả về cùng kết quả {observation}"
                )

            self.observations.append(observation_fp)

        # ========================================================
        # 3. Kiểm tra trạng thái nghiệp vụ không tiến triển
        # ========================================================

        if progress is not None:
            if progress == self.last_state:
                self.stall_count += 1
            else:
                self.stall_count = 0

            self.last_state = progress

            if self.stall_count >= self.stall_n:
                return (
                    f"LOOP: Trạng thái nghiệp vụ không tiến triển "
                    f"trong {self.stall_count} lần liên tiếp: "
                    f"{progress}"
                )

        return None


class BookingHarness:
    """
    Harness kiểm soát agent đặt vé máy bay.

    Harness chịu trách nhiệm:
    1. Kiểm tra ràng buộc dữ liệu
    2. Kiểm tra điều kiện hoàn thành
    3. Kiểm tra quyền thực hiện hành động
    4. Bàn giao khi agent không thể hoàn thành an toàn
    """

    # ============================================================
    # 1. DATA CONSTRAINTS
    # ============================================================

    def validate_flight_request(
        self,
        origin: str,
        destination: str,
        date: str,
    ) -> dict:
        """
        Kiểm tra dữ liệu đầu vào của yêu cầu tìm chuyến bay.
        """

        errors = []

        if not origin:
            errors.append("Origin is required.")

        if not destination:
            errors.append("Destination is required.")

        if not date:
            errors.append("Date is required.")

        if origin and len(origin) != 3:
            errors.append(
                "Origin must be a 3-letter airport code."
            )

        if destination and len(destination) != 3:
            errors.append(
                "Destination must be a 3-letter airport code."
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    # ============================================================
    # 2. COMPLETION CRITERIA
    # ============================================================

    def check_completion(
        self,
        state: dict,
    ) -> dict:
        """
        Kiểm tra xem agent đã hoàn thành nhiệm vụ
        đặt vé hay chưa.
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

    # ============================================================
    # 3. AUTHORIZATION CHECKS
    # ============================================================

    def check_authorization(
        self,
        action: str,
        state: dict,
    ) -> dict:
        """
        Kiểm tra xem agent có quyền thực hiện hành động hay không.
        """

        # Các action chỉ đọc dữ liệu
        read_only_actions = {
            "search_flights",
            "get_flight_detail",
        }

        # Các action có thể thay đổi trạng thái
        state_changing_actions = {
            "hold_flight",
            "confirm_booking",
            "cancel_hold",
        }

        # Read-only action luôn được phép
        if action in read_only_actions:
            return {
                "allowed": True,
                "reason": "Read-only action is allowed.",
            }

        # State-changing action yêu cầu passenger_name
        if action in state_changing_actions:
            if not state.get("passenger_name"):
                return {
                    "allowed": False,
                    "reason": (
                        "Passenger name is required "
                        "for state-changing actions."
                    ),
                }

            return {
                "allowed": True,
                "reason": (
                    "Required passenger information exists."
                ),
            }

        # Action không nằm trong danh sách được phép
        return {
            "allowed": False,
            "reason": "Unknown action.",
        }

    # ============================================================
    # 4. HANDOFF MECHANISM
    # ============================================================

    def handoff(
        self,
        reason: str,
        attempted_action: list,
        state: dict,
        question: str,
    ) -> dict:
        """
        Bàn giao cho con người khi agent không thể
        hoàn thành nhiệm vụ an toàn.
        """

        return {
            "stop_reason": reason,
            "attempted_action": attempted_action,
            "state": state,
            "question_for_human": question,
        }

    # ============================================================
    # 5. BEFORE TOOL
    # ============================================================

    def before_tool(
        self,
        action: str,
        args: dict,
        state: dict,
        loop_detector: LoopDetector,
    ) -> dict:
        """
        Kiểm tra trước khi Agent được phép gọi Tool.

        Kiểm tra:
        1. Authorization
        2. Loop detection
        """

        # --------------------------------------------------------
        # Authorization
        # --------------------------------------------------------

        auth = self.check_authorization(
            action,
            state,
        )

        if not auth["allowed"]:
            return {
                "allowed": False,
                "stop": True,
                "reason": auth["reason"],
            }

        # --------------------------------------------------------
        # Loop detection
        # --------------------------------------------------------

        loop_reason = loop_detector.check(
            tool=action,
            args=args,
        )

        if loop_reason:
            return {
                "allowed": False,
                "stop": True,
                "reason": loop_reason,
            }

        return {
            "allowed": True,
            "stop": False,
            "reason": "",
        }

    # ============================================================
    # 6. AFTER TOOL
    # ============================================================

    def after_tool(
        self,
        action: str,
        args: dict,
        result: dict,
        state: dict,
        loop_detector: LoopDetector,
    ) -> dict:
        """
        Kiểm tra sau khi Tool thực thi.

        Kiểm tra:
        1. Loop thông qua observation
        2. Trạng thái có tiến triển hay không
        3. Điều kiện hoàn thành
        4. Handoff nếu cần
        """

        # --------------------------------------------------------
        # Loop / observation / progress
        # --------------------------------------------------------

        loop_reason = loop_detector.check(
            tool=action,
            args=args,
            observation=result,
            progress=state.get("status"),
        )

        if loop_reason:
            return {
                "continue": False,
                "completed": False,
                "handoff": self.handoff(
                    reason=loop_reason,
                    attempted_action=[action],
                    state=state,
                    question=(
                        "Cần người dùng kiểm tra hoặc "
                        "quyết định bước tiếp theo."
                    ),
                ),
            }

        # --------------------------------------------------------
        # Completion
        # --------------------------------------------------------

        completion = self.check_completion(state)

        if completion["completed"]:
            return {
                "continue": False,
                "completed": True,
                "handoff": None,
            }

        # --------------------------------------------------------
        # Continue
        # --------------------------------------------------------

        return {
            "continue": True,
            "completed": False,
            "handoff": None,
        }
