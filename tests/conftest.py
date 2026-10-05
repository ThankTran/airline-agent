import pytest
from airline_agent.database import reset_database

@pytest.fixture(autouse=True)
def clean_mock_database():
    reset_database()
    yield
    reset_database()
