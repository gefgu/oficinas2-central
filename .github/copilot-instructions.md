# Oficinas2 Central - AI Agent Instructions

## Project Overview
Privacy-focused trajectory analysis system that processes GPS data from ESP devices to detect visits and predict transport modes/purposes. Core focus: **location privacy through H3-based anonymization** while maintaining analytical utility.

## Architecture & Data Flow

### 1. Trajectory Processing Pipeline (server/utils.py)
**Entry Point:** `handle_raw_trajectories(coordenadas)` receives raw GPS data → processes through:

1. **Visit Detection** (`detect_visits_from_trajectory`): Uses DBSCAN clustering (eps=100m, min_samples=60) to identify stationary points vs moving trajectories
   - Clusters meeting min_duration (10 min) become visits
   - Points between visits tagged as trips with sequential trip_numbers
   - Visit locations calculated as cluster centroids

2. **Privacy Anonymization** (`anonymize_trajectories`): 
   - Loads H3 hexagons from `dados/Curitiba_resolution_10.geojson`
   - For visit points in H3 hexagons: keeps only first/last 30 points, randomizes within hexagon bounds
   - **Always preserves ALL trajectory points** (trip_number != None) between visits
   - Critical: This is privacy-by-design, not optional filtering

3. **ML Classification**:
   - **Purpose prediction** (`classify_visits`): LightGBM model trained on Foursquare Curitiba data
     - Features: Bairro (neighborhood), Hour, Day of Week
     - Model: `modelos/lgb_purpose_model.pkl`, encoders: `modelos/lgb_purpose_encoders.pkl`
   - **Transport mode** (`classify_transport_in_visits`): Random Forest on trip trajectories
     - Features: speed, acceleration, bearing, distance, time_diff
     - Model: `server/random_forest_model.pkl`
     - Maps modes to simplified categories: Walk, Two-Wheeler, Car, Bus, Others

### 2. Database (DuckDB)
Two tables via `server/db_commands.py`:
- **trajectory**: Raw anonymized GPS points with trip_number/visit_number
- **visit**: Aggregated visits with arrive/depart times, predicted purpose/mode, validated flag

Uses environment-based DB switching:
- `PRODUCTION_MODE=true` → `dados.db`
- `PRODUCTION_MODE=false` → `dados_test.db`
- Tests use in-memory DB via `set_test_db(con)`

### 3. FastAPI Endpoints (server/main.py)
- `POST /trajectories/`: Receive GPS data from ESP devices
- `GET /trajectories/`: Fetch recent unvalidated visits (last 10 min)
- `PUT /trajectories/`: Update visits with user-confirmed purpose/mode

## Development Workflow

### Running the Server
```bash
cd server
source ../fastapi_env/bin/activate
# Set environment: export PRODUCTION_MODE=false for testing
python main.py  # Runs on 0.0.0.0:8000
```

### Testing
```bash
pytest server/test_main.py  # Uses in-memory DuckDB, mocks all components
```
Test pattern: Inject test DB via `set_test_db()` fixture, verify both trajectory/visit table states.

### Model Training (notebooks/)
1. **modelo_de_transporte.ipynb**: Train transport mode classifier on GeoLife dataset
2. **modelo_proposito_foursquare.ipynb**: Train purpose classifier on Foursquare Curitiba check-ins
3. Export to `modelos/` directory (purpose) or `server/` (transport)

## Critical Implementation Details

### DBSCAN Parameters
- **eps_meters=100**: Maximum cluster radius (tuned for walking speed detection)
- **min_samples=60**: ~1 minute at 1Hz sampling prevents brief stops from becoming visits
- Clustering in EPSG:3857 (meters), not EPSG:4326 (degrees)

### Import Pattern Quirk
```python
try:
    from .server.database import get_db  # When imported as module
except ImportError:
    from server.database import get_db   # When run directly
```
Both patterns exist throughout codebase - needed for different execution contexts.

### H3 Anonymization Logic
- Only visit points in H3 hexagons get randomized (first/last 30)
- Middle visit points SKIPPED entirely (reduces storage, enhances privacy)
- Trip points NEVER anonymized (movement patterns preserved for transport classification)
- Random point generation uses rejection sampling within polygon bounds

### Model Encoding
- Purpose model uses LabelEncoder for both features and labels - must handle unknown neighborhoods
- Transport mode mapping consolidates 11 classes → 5 simplified categories (see `map_transport_mode()`)

## Data Files & External Dependencies
- **dados/Curitiba_resolution_10.geojson**: H3 hexagon grid for Curitiba
- **dados/bairros_curitiba.zip**: Neighborhood boundaries for spatial joins
- **dados/geolife/**: GeoLife GPS trajectory dataset (ignored in .gitignore)
- **fastapi_env/**: Python virtual environment (not in git)

## Common Pitfalls
1. **Missing dependencies**: No requirements.txt - check imports in utils.py for needed packages
2. **CRS mismatches**: Always verify geodataframe CRS, convert to EPSG:4326 for consistency
3. **Model file paths**: Notebooks use `../modelos/`, server uses relative paths - adjust per context
4. **Datetime handling**: Trajectories store ISO timestamps, convert for JSON serialization
5. **NumPy types in JSON**: Must call `.item()` on numpy scalars before serialization

## Code Conventions
- Use GeoDataFrame for spatial operations (geopandas)
- Explicit type conversions before DB insertion (int, float, not numpy types)
- Print debug info during processing (visit counts, anonymization stats, cluster details)
- Functions return tuples of (visits_data, trajectories_data) not single merged structure
