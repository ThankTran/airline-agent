from typing import TypedDict

class BookingState(TypedDict, total=False):
    # Thông tin yêu cầu
    origin: str
    destination: str
    date: str
    passenger_name: str

    # Trạng thái đặt chỗ
    flight_id: str
    hold_id: str
    booking_id: str

    # Kết quả
    status: str
    error: str