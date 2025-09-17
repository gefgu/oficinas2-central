from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple
import duckdb
# from .utils import get_sample_trajectories
import pandas as pd
from .server.database import get_db
from .utils import get_recent_trajectory_data, handle_raw_trajectories

# Create FastAPI instance
app = FastAPI(title="Simple FastAPI Server", version="1.0.0")

# Define a model for the ESP data
class ESPData(BaseModel):
    coordenadas: List[Tuple[float, float, str]]

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Hello World! FastAPI is running!"}

@app.post("/")
async def root(message):
    print(message)
    return {"message": "Hello World! FastAPI is running!"}

@app.post("/trajectories/")
async def receive_trajectory_data(data: ESPData):
    handle_raw_trajectories(data.coordenadas)
    return {"coordenadas": data.coordenadas}

@app.get("/trajectories/")
async def get_trajectory_data():
    visits_data, trajectory_data = get_recent_trajectory_data()
    
    if len(visits_data) < 1 or len(trajectory_data) < 1:
        return {"detail": "Not authorized"}
    
    return {
        "visits": visits_data,
        "trajectory": trajectory_data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)