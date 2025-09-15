from fastapi.testclient import TestClient
import pytest
from .main import app
import pandas as pd
import duckdb
import pytest


client = TestClient(app)

@pytest.fixture
def test_db():
    test_con = duckdb.connect(database=':memory:')

    test_con.sql("""
    CREATE TABLE
    coordenadas (uid INTEGER, 
                latitude DOUBLE, 
                longitude DOUBLE, 
                timestamp TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
    """)

    # Store the test connection in app state
    app.state.con = test_con

    yield test_con

    # Clean up
    if hasattr(app.state, 'con'):
        delattr(app.state, 'con')
    test_con.close()


def test_read_server_running():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World! FastAPI is running!"}


def test_trajectories_receive_endpoint(test_db):
    sample_df = pd.read_csv('../dados/sample_detailed_trajectory_user_53308444.csv')
    sample_data = sample_df[['lat', 'lon', 'timestamp']].values.tolist()
    # print(sample_data)

    past_count = test_db.execute("SELECT COUNT(*) FROM coordenadas").fetchone()[0]
    assert past_count == 0

    response = client.post("/trajectories/", json={"coordenadas": sample_data})
    assert response.status_code == 200

    result = test_db.execute("SELECT COUNT(*) FROM coordenadas").fetchone()[0]
    assert result == len(sample_data)

    sample_row = test_db.execute("SELECT * FROM coordenadas ORDER BY created_at, timestamp LIMIT 1").fetchone()
    # print(sample_row, sample_data[0])
    assert sample_row[1] == sample_data[0][0]