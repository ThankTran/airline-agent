from airline_agent.booking_graph import build_booking_graph


graph = build_booking_graph()


initial_state = {
    "origin": "SGN",
    "destination": "HAN",
    "date": "2026-10-15",
    "passenger_name": "Nguyen Van A",
}


result = graph.invoke(initial_state)

print("=== KẾT QUẢ ===")
print(result)