from copy import deepcopy

INITIAL_FLIGHTS = [
    {
        "flight_id": "VN001", "airline": "Vietnam Airlines",
        "origin": "HAN", "destination": "SGN", "date": "2026-10-15",
        "departure": "08:00", "arrival": "10:00", "price": 2_500_000,
        "currency": "VND", "available_seats": 5, "status": "available",
        "baggage": "20kg", "cabin": "Economy",
    },
    {
        "flight_id": "VN002", "airline": "Vietnam Airlines",
        "origin": "SGN", "destination": "HAN", "date": "2026-10-15",
        "departure": "14:00", "arrival": "16:00", "price": 2_500_000,
        "currency": "VND", "available_seats": 5, "status": "available",
        "baggage": "20kg", "cabin": "Economy",
    },
    {
        "flight_id": "VN007", "airline": "Vietnam Airlines",
        "origin": "SGN", "destination": "HAN", "date": "2026-10-15",
        "departure": "18:00", "arrival": "20:00", "price": 2_200_000,
        "currency": "VND", "available_seats": 3, "status": "available",
        "baggage": "20kg", "cabin": "Economy",
    },
    {
        "flight_id": "VN008", "airline": "Vietnam Airlines",
        "origin": "SGN", "destination": "HAN", "date": "2026-10-15",
        "departure": "20:30", "arrival": "22:30", "price": 2_000_000,
        "currency": "VND", "available_seats": 0, "status": "sold_out",
        "baggage": "20kg", "cabin": "Economy",
    },
    {
        "flight_id": "VN003", "airline": "Vietnam Airlines",
        "origin": "HAN", "destination": "DAL", "date": "2026-10-16",
        "departure": "09:00", "arrival": "11:00", "price": 1_500_000,
        "currency": "VND", "available_seats": 10, "status": "available",
        "baggage": "20kg", "cabin": "Economy",
    },
    {
        "flight_id": "VN004", "airline": "Vietnam Airlines",
        "origin": "DAL", "destination": "HAN", "date": "2026-10-17",
        "departure": "10:00", "arrival": "12:00", "price": 1_500_000,
        "currency": "VND", "available_seats": 10, "status": "available",
        "baggage": "20kg", "cabin": "Economy",
    },
    {
        "flight_id": "VN005", "airline": "Vietnam Airlines",
        "origin": "HAN", "destination": "DNG", "date": "2026-10-18",
        "departure": "11:00", "arrival": "13:00", "price": 1_800_000,
        "currency": "VND", "available_seats": 8, "status": "available",
        "baggage": "20kg", "cabin": "Economy",
    },
    {
        "flight_id": "VN006", "airline": "Vietnam Airlines",
        "origin": "DNG", "destination": "HAN", "date": "2026-10-19",
        "departure": "14:00", "arrival": "16:00", "price": 1_800_000,
        "currency": "VND", "available_seats": 8, "status": "available",
        "baggage": "20kg", "cabin": "Economy",
    },
]

FLIGHTS = deepcopy(INITIAL_FLIGHTS)
HOLDS = {}
BOOKINGS = {}


def reset_database() -> None:
    """Reset mock DB để mỗi scenario/agent được đánh giá công bằng."""
    FLIGHTS.clear()
    FLIGHTS.extend(deepcopy(INITIAL_FLIGHTS))
    HOLDS.clear()
    BOOKINGS.clear()


def get_flight_by_id(flight_id: str):
    flight_id = (flight_id or "").upper()
    return next(
        (
            f for f in FLIGHTS 
                if f["flight_id"] == flight_id), None)
