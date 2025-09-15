from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple
import duckdb
from .utils import get_sample_trajectories
import pandas as pd

# Create FastAPI instance
app = FastAPI(title="Simple FastAPI Server", version="1.0.0")

# Define a model for the ESP data
class ESPData(BaseModel):
    coordenadas: List[Tuple[float, float, str]]

# Global connection (will be overridden in tests)
_default_con = duckdb.connect(database='./dados.db')

def get_db():
    """Dependency to get database connection"""
    return getattr(app.state, 'con', _default_con)


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
    con = get_db()
    df = pd.DataFrame(data.coordenadas, columns=['latitude', 'longitude', 'timestamp'])
    df["uid"] = con.sql("SELECT COALESCE(MAX(uid), 0) + 2 FROM coordenadas").fetchone()[0]

    print(df.head())

    con.sql("""INSERT INTO coordenadas (uid, latitude, longitude, timestamp)
             SELECT uid, latitude, longitude, timestamp FROM df""")

    return {"coordenadas": data.coordenadas}

@app.get("/verify-coordinates/")
async def verifica_coordenadas():
    # result = con.execute("SELECT * FROM coordenadas").fetchall()
    result = get_sample_trajectories()
    return result

@app.get("/app/")
async def esp_me_manda_mensagem(data: ESPData):

    return {"message": "ESP me manda mensagem!", "coordenadas": data.coordenadas}

@app.get("/app-envia/")
async def esp_me_manda_mensagem(data: ESPData):
    return {"message": "ESP me manda mensagem!", "dado": data.dado}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)