from airline_agent.tools import(
    get_flight_detail,
    search_flights,
    get_flight_details,
)

# ===========================
# Tests for tool 1
# =========================

# def test_search_flights():
#     result = search_flights.invoke(
#         {
#             "origin": "HANOI",
#             "destination": "DA LAT",
#             "date": "2023-10-03",
#         }
#     )

#     assert result["status"] == "ok", "Search flights should return status 'ok'"
#     assert result["count"] > 0, "Search flights should return at least one flight"

def test_get_flight_detail():
    result = get_flight_detail.invoke(
        {
            "flight_id": "VN001",
        }
    )

    assert result["status"] == "ok", "Get flight details should return status 'ok'"
    assert "flight" in result, "Get flight details should return flight information"
    assert result["flight"]["flight_id"] == "VN001", "Flight ID should match the requested ID"
    assert result["flight"]["origin"] == "HANOI", "Flight origin should be HANOI"
    assert result["flight"]["destination"] == "HO CHI MINH CITY", "Flight destination should be HO CHI MINH"
    assert result["flight"]["date"] == "2023-10-01", "Flight date should be 2023-10-01"
    assert result["flight"]["available_seats"] > 0, "Flight should have available seats"
    assert result["flight"]["price"] > 0, "Flight price should be greater than 0"
    assert result["flight"]["currency"] == "USD", "Flight currency should be USD"
    assert result["flight"]["baggage"] == "20kg", "Flight baggage should be 20kg"
    assert result["flight"]["cabin"] == "Economy", "Flight cabin should be Economy"
    assert result["flight"]["departure"] == "10:00", "Flight departure time should be 10:00"
    assert result["flight"]["arrival"] == "12:00", "Flight arrival time should be 12:00"
    assert result["flight"]["airline"] == "Vietnam Airlines", "Flight airline should be Vietnam Airlines"