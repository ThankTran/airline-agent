from airline_agent.booking_graph import build_booking_graph
from airline_agent.database import reset_database

reset_database()
graph = build_booking_graph()

initial_state = {
    "origin": "SGN",
    "destination": "HAN",
    "date": "2026-10-15",
    "passenger_name": "Nguyen Van A",
    "user_intent": "book",
    "user_confirmed_booking": True,
}

result = graph.invoke(initial_state)
print("=== KẾT QUẢ BASELINE LANGGRAPH ===")
print(result)
