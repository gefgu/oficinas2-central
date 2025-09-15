from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple
import duckdb
from .utils import get_sample_trajectories

con = duckdb.connect(database='./dados.db')

# Create FastAPI instance
app = FastAPI(title="Simple FastAPI Server", version="1.0.0")

# Define a model for the ESP data
class ESPData(BaseModel):
    coordenadas: List[Tuple[float, float, float]]



# Root endpoint
@app.get("/")
async def root():
    return {"message": "Hello World! FastAPI is running!"}

@app.post("/")
async def root(message):
    print(message)
    return {"message": "Hello World! FastAPI is running!"}

@app.post("/esp/")
async def recebe_mensagem_esp(data: ESPData):
    for coord in data.coordenadas:
        con.execute("""
        INSERT INTO coordenadas (uid, latitude, longitude, timestamp) 
        VALUES (1, ?, ?, ?)", (coord[0], coord[1], coord[2])
    """)
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