# Oficinas2 Central - Privacy-Focused Trajectory Analysis System

A privacy-first GPS trajectory analysis system that processes location data from ESP devices to detect visits, predict transport modes, and infer trip purposes while maintaining user privacy through H3-based spatial anonymization.

## Features

- **Privacy-by-Design**: H3 hexagon-based anonymization protects exact visit locations
- **Visit Detection**: DBSCAN clustering identifies stationary points (visits) vs movement (trips)
- **Transport Mode Classification**: Random Forest model predicts Walk, Car, Bus, Two-Wheeler, or Others
- **Purpose Prediction**: LightGBM model infers visit purposes (Home, Work, Shopping, Leisure, Other)
- **FastAPI Backend**: RESTful API for receiving GPS data and serving analysis results

## Architecture

```
ESP Device → POST /trajectories/ → DBSCAN Visit Detection → H3 Anonymization
                                           ↓
                                    ML Classification
                                    (Purpose + Transport)
                                           ↓
                                    DuckDB Storage
                                           ↓
                                    GET /trajectories/ → User Validation
                                           ↓
                                    PUT /trajectories/ → Update Database
```

### Data Flow
1. **Input**: GPS coordinates `(latitude, longitude, timestamp)` from ESP devices
2. **Visit Detection**: DBSCAN clustering (100m radius, 60 points minimum) identifies stationary locations
3. **Anonymization**: Visit points randomized within H3 hexagons; trip trajectories preserved intact
4. **Classification**: LightGBM predicts purpose; Random Forest predicts transport mode
5. **Storage**: Anonymized data stored in DuckDB with two tables: `trajectory` and `visit`
6. **Validation**: User confirms/corrects predictions via API

## Setup

### Prerequisites

- Python 3.8+
- Git

### Quick Start (Recommended)

Run the automated setup script:

```bash
git clone https://github.com/gefgu/oficinas2-central.git
cd oficinas2-central
./quickstart.sh
```

This script will:
- ✅ Create a virtual environment (`fastapi_env`)
- ✅ Install all dependencies from `requirements.txt`
- ✅ Initialize the database
- ✅ Create environment configuration
- ✅ Generate a convenient `start_server.sh` script
- ✅ Check for required data and model files

After setup completes, start the server with:
```bash
./start_server.sh
```

### Manual Setup

If you prefer to set up manually:

#### 1. Clone Repository

```bash
git clone https://github.com/gefgu/oficinas2-central.git
cd oficinas2-central
```

#### 2. Create Virtual Environment

```bash
python3 -m venv fastapi_env
source fastapi_env/bin/activate  # On Windows: fastapi_env\Scripts\activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install packages individually:
```bash
pip install fastapi uvicorn pydantic
pip install pandas numpy
pip install duckdb
pip install scikit-learn
pip install geopandas shapely
pip install lightgbm
pip install joblib
pip install python-dotenv pytest
```

#### 4. Prepare Data Files

Ensure these files exist in the `dados/` directory:

- `Curitiba_resolution_10.geojson` - H3 hexagon grid for Curitiba
- `bairros_curitiba.zip` - Neighborhood boundaries shapefile
- Sample trajectory CSVs (for testing)

#### 5. Prepare Model Files

Ensure trained models exist:

- `modelos/lgb_purpose_model.pkl` - Purpose classification model
- `modelos/lgb_purpose_encoders.pkl` - Label encoders for purpose model
- `server/random_forest_model.pkl` - Transport mode classification model

To train models from scratch, run the notebooks in `notebooks/`:
- `modelo_proposito_foursquare.ipynb` - Train purpose classifier
- `modelo_de_transporte.ipynb` - Train transport mode classifier

#### 6. Initialize Database

```bash
cd server
python3 db_commands.py  # Creates tables in dados_test.db
```

#### 7. Configure Environment (Optional)

Create a `.env` file in the `server/` directory:

```bash
# Use production database (dados.db) or test database (dados_test.db)
PRODUCTION_MODE=false
```

## Running the Server

### Development Mode

```bash
cd server
source ../fastapi_env/bin/activate
export PRODUCTION_MODE=false  # Use test database

# Recommended: Use uvicorn directly with auto-reload for development
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Alternative: Run main.py directly (no auto-reload)
# python main.py
```

The server will start on `http://0.0.0.0:8000`

**Note**: Using `uvicorn` with `--reload` automatically restarts the server when code changes are detected, making development much faster.

### Production Mode

```bash
cd server
source ../fastapi_env/bin/activate
export PRODUCTION_MODE=true  # Use production database

# For production, use uvicorn without --reload
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# Or with more workers for better performance
# python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Check Server Status

Visit `http://localhost:8000` in your browser or:

```bash
curl http://localhost:8000
# Should return: {"message":"Hello World! FastAPI is running!"}
```

### API Documentation

FastAPI provides automatic interactive documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### 1. Submit GPS Trajectories

**POST** `/trajectories/`

Receives GPS data from ESP devices, processes it through visit detection, anonymization, and ML classification.

**Request Body:**
```json
{
  "coordenadas": [
    [-25.4195, -49.2646, "2024-10-02T10:30:00"],
    [-25.4196, -49.2647, "2024-10-02T10:30:01"],
    ...
  ]
}
```

**Response:**
```json
{
  "coordenadas": [...] 
}
```

### 2. Get Recent Unvalidated Visits

**GET** `/trajectories/`

Retrieves visits from the last 10 minutes that haven't been validated by users.

**Response:**
```json
{
  "visits": [
    {
      "uid": 1,
      "visit_number": 1,
      "arrive_time": "2024-10-02 10:30:00",
      "depart_time": "2024-10-02 11:00:00",
      "latitude": -25.4195,
      "longitude": -49.2646,
      "purpose": "WORK",
      "mode_of_transport": "BUS",
      "validated": false
    }
  ],
  "trajectory": [
    {
      "uid": 1,
      "trip_number": 1,
      "trajectory_points": [...],
      "point_count": 150,
      "start_time": "2024-10-02 10:00:00",
      "end_time": "2024-10-02 10:30:00"
    }
  ]
}
```

### 3. Update Visit Data

**PUT** `/trajectories/`

Updates visits with user-validated purpose and transport mode.

**Request Body:**
```json
{
  "visits": [
    {
      "uid": 1,
      "visit_number": 1,
      "purpose": "HOME",
      "mode_of_transport": "WALK"
    }
  ]
}
```

**Response:**
```json
{
  "message": "Trajectory data updated successfully"
}
```

## Testing

### Run Unit Tests

```bash
cd server
source ../fastapi_env/bin/activate
pytest test_main.py -v
```

Tests use an in-memory DuckDB database and mock all external dependencies.

### Test Coverage

The test suite (`test_main.py`) covers:
- Server health check
- GPS data submission and processing
- Visit detection (DBSCAN clustering)
- Database insertion (trajectory and visit tables)
- Data retrieval with JSON serialization
- Visit data updates and validation

### Manual Testing

Use the provided sample trajectory files in `dados/`:

```bash
# In Python shell or notebook
import pandas as pd
sample_df = pd.read_csv("dados/sample_detailed_trajectory_user_5896225_2014-05-19.csv")
sample_data = sample_df[["lat", "lon", "timestamp"]].values.tolist()

# Send to API
import requests
response = requests.post(
    "http://localhost:8000/trajectories/",
    json={"coordenadas": sample_data}
)
print(response.json())
```

## Project Structure

```
oficinas2-central/
├── server/
│   ├── main.py                    # FastAPI application & endpoints
│   ├── utils.py                   # Core processing logic (DBSCAN, anonymization, classification)
│   ├── transport_mode_model.py    # Transport mode prediction
│   ├── db_commands.py             # Database schema creation
│   ├── database.py                # Database connection management
│   ├── test_main.py               # Unit tests
│   ├── random_forest_model.pkl    # Trained transport model
│   └── server/
│       └── database.py            # (Duplicate for import flexibility)
├── notebooks/
│   ├── modelo_proposito_foursquare.ipynb    # Train purpose model
│   └── modelo_de_transporte.ipynb           # Train transport model
├── modelos/
│   ├── lgb_purpose_model.pkl      # Trained purpose model
│   └── lgb_purpose_encoders.pkl   # Label encoders
├── dados/
│   ├── Curitiba_resolution_10.geojson       # H3 hexagons
│   ├── bairros_curitiba.zip                 # Neighborhoods
│   └── sample_*.csv                         # Test trajectories
├── fastapi_env/                   # Virtual environment (not in git)
├── .github/
│   └── copilot-instructions.md    # AI agent instructions
└── README.md
```

## Key Implementation Details

### DBSCAN Parameters
- **eps_meters=100**: Maximum 100m radius for clustering (walking distance)
- **min_samples=60**: Minimum 60 GPS points (~1 minute at 1Hz sampling) to form a visit
- Prevents brief stops from being classified as visits

### H3 Anonymization Strategy
- **Visit Points**: Only first/last 30 points kept and randomized within H3 hexagons
- **Trip Points**: ALL trajectory points preserved (needed for transport classification)
- **Middle Points**: Skipped entirely for privacy and storage efficiency

### Transport Mode Categories
Original 11 modes consolidated to 5:
- **Walk**: walk, run
- **Two-Wheeler**: bike, motorcycle  
- **Car**: car, taxi
- **Bus**: bus
- **Others**: subway, train, airplane, boat

### Purpose Categories
Predicted from Foursquare check-in data:
- HOME
- WORK
- SHOPPING
- LEISURE
- OTHER

## Database Schema

### `trajectory` Table
```sql
CREATE TABLE trajectory (
    uid INTEGER,
    latitude DOUBLE,
    longitude DOUBLE,
    timestamp TIMESTAMP,
    trip_number INTEGER,        -- Non-null for movement between visits
    visit_number INTEGER,       -- Non-null for stationary visit points
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### `visit` Table
```sql
CREATE TABLE visit (
    uid INTEGER,
    visit_number INTEGER,
    arrive_time TIMESTAMP,
    depart_time TIMESTAMP,
    latitude DOUBLE,            -- Anonymized centroid
    longitude DOUBLE,           -- Anonymized centroid
    purpose VARCHAR,            -- Predicted by LightGBM
    mode_of_transport VARCHAR,  -- Predicted by Random Forest
    validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## Development Tips

### Import Pattern
The codebase uses dual imports for flexibility:
```python
try:
    from .server.database import get_db  # When imported as module
except ImportError:
    from server.database import get_db   # When run directly
```

### Common Issues

1. **CRS Mismatches**: Always verify GeoDataFrame CRS is `EPSG:4326`
2. **NumPy Types**: Call `.item()` on numpy scalars before JSON serialization
3. **Model Paths**: Notebooks use `../modelos/`, server uses relative paths
4. **Database Selection**: Set `PRODUCTION_MODE` environment variable appropriately

### Adding New Features

- **Modify visit detection**: Edit `detect_visits_from_trajectory()` in `utils.py`
- **Change anonymization**: Edit `anonymize_trajectories()` in `utils.py`
- **Update ML models**: Retrain in notebooks, export to `modelos/` or `server/`
- **Add endpoints**: Extend `main.py` with new FastAPI routes

## Contributing

This is an academic project (Oficinas2). For contributions:

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

[Add license information]

## Contact

Repository: https://github.com/gefgu/oficinas2-central

## Acknowledgments

- GeoLife dataset for transport mode training
- Foursquare Curitiba check-ins for purpose training
- H3 spatial indexing by Uber
