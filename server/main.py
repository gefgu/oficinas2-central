import json
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple
import duckdb
import pandas as pd

# When running as module vs directly
try:
    from .server.database import get_db
    from .utils import get_recent_trajectory_data, handle_raw_trajectories, update_visit_data
except ImportError:
    from server.database import get_db
    from utils import get_recent_trajectory_data, handle_raw_trajectories, update_visit_data

# Create FastAPI instance
app = FastAPI(title="Simple FastAPI Server", version="1.0.0")

# Define a model for the ESP data
class ESPData(BaseModel):
    coordenadas: List[Tuple[float, float, str]]

class VisitData(BaseModel):
    visits: List['VisitItem']

class VisitItem(BaseModel):
    uid: int
    visit_number: int
    purpose: str
    mode_of_transport: str

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Hello World! FastAPI is running!"}

@app.post("/")
async def root(message: List[dict]):
    print(message)
    return {"message": "Hello World! FastAPI is running!"}

@app.post("/trajectories/")
async def receive_trajectory_data(data: List[dict]):
    coordenadas = [
        (point['latitude'], point['longitude'], point['timestamp'])
        for point in data
    ]

    print(f"Quantidade de Pontos Recebidos: {len(coordenadas)}")

    handle_raw_trajectories(coordenadas)
    return {"coordenadas": coordenadas}

@app.get("/trajectories/")
async def get_trajectory_data():
    visits_data, trajectory_data = get_recent_trajectory_data()
    
    # if len(visits_data) < 1 or len(trajectory_data) < 1:
    #     return {"detail": "Not authorized"}
    
    response = {
        "visits": visits_data,
        "trajectory": trajectory_data
    }

    json.dump(response, open("latest_trajectory_data.json", "w"), indent=4, ensure_ascii=False)

    return response

@app.put("/trajectories/")
async def update_trajectory_data(dados: VisitData):
    # Update the visit data in the database
    update_visit_data(dados)
    return {"message": "Trajectory data updated successfully"}

if __name__ == "__main__":
    # Note: For development, it's recommended to run with uvicorn directly for auto-reload:
    # python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
    # This allows the server to automatically restart when code changes are detected.
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)