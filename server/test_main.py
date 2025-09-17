from fastapi.testclient import TestClient
import pytest

from server.db_commands import create_tables
from .main import app
import pandas as pd
import duckdb
import pytest
from .server.database import set_test_db, clear_test_db


client = TestClient(app)


@pytest.fixture
def test_db():
    test_con = duckdb.connect(database=":memory:")

    # Create tables
    create_tables(test_con)

    # Set the test connection globally
    set_test_db(test_con)

    yield test_con

    # Clean up
    clear_test_db()
    test_con.close()


def test_read_server_running():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World! FastAPI is running!"}


def test_trajectories_receive_endpoint(test_db):
    sample_df = pd.read_csv("../dados/sample_detailed_trajectory_user_53308444.csv")
    sample_data = sample_df[["lat", "lon", "timestamp"]].values.tolist()
    # print(sample_data)

    past_count = test_db.execute("SELECT COUNT(*) FROM trajectory").fetchone()[0]
    assert past_count == 0

    response = client.post("/trajectories/", json={"coordenadas": sample_data})
    assert response.status_code == 200

    result = test_db.execute("SELECT COUNT(*) FROM trajectory").fetchone()[0]
    # print(result, len(sample_data))
    assert result == len(sample_data)

    sample_row = test_db.execute(
        "SELECT * FROM trajectory ORDER BY created_at, timestamp LIMIT 1"
    ).fetchone()
    # print(sample_row, sample_data[0])
    assert sample_row[1] == sample_data[0][0]

    number_of_visits = test_db.execute("SELECT COUNT(*) FROM visit").fetchone()[0]
    # print(f"Number of visits recorded: {number_of_visits}")
    assert number_of_visits == 5
    # assert 1 == 0

    response = client.get("/trajectories/")
    print(response)
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data["visits"]) == number_of_visits
    assert len(response_data["trajectory"]) == number_of_visits


def test_not_getting_trajectories(test_db):
    response = client.get("/trajectories/")
    assert response.status_code == 200
    assert response.json() == {"detail": "Not authorized"}
