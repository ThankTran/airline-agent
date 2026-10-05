from typing import Any, TypedDict


class BookingState(TypedDict, total=False):
    # Yêu cầu người dùng
    origin: str
    destination: str
    date: str
    passenger_name: str
    user_intent: str            
    user_confirmed_booking: bool    

    # Trạng thái nghiệp vụ
    flight_id: str
    hold_id: str
    booking_id: str
    excluded_flight_ids: list[str]

    # Trạng thái agent
    status: str
    error: str
    retry_count: int

    # Trace phục vụ harness/evaluation
    attempted_actions: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    handoff: dict[str, Any]
