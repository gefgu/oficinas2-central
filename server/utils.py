import time
import requests
from typing import List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd

# When running as module vs directly
try:
    from .server.database import get_db
except ImportError:
    from server.database import get_db

# from .data import sample_trajectories
import json
import math
import geopandas as gpd
import pickle
import joblib
from shapely.geometry import Point, Polygon
import random


# def get_sample_trajectories():
# return json.dumps(sample_trajectories)


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in meters using Haversine formula"""
    R = 6371000  # Earth's radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def load_h3_hexagons():
    """Load H3 hexagons from the GeoJSON file"""
    try:
        h3_gdf = gpd.read_file("../dados/Curitiba_resolution_10.geojson")
        return h3_gdf
    except FileNotFoundError:
        print("H3 hexagons file not found at ../dados/Curitiba_resolution_10.geojson")
        return None


def anonymize_trajectories(trajectories_data, visits_data):
    return trajectories_data
    """
    Anonymize trajectory data by replacing points with random locations within H3 hexagons.
    Points that fall within the same H3 hexagon as visit locations are randomized within that hexagon.
    """
    if not trajectories_data or not visits_data:
        return trajectories_data

    # Load H3 hexagons
    h3_gdf = load_h3_hexagons()
    if h3_gdf is None:
        print("Could not load H3 hexagons, returning original trajectories")
        return trajectories_data

    # Find hexagons that contain visit locations
    visit_hexagons = set()
    for visit in visits_data:
        visit_point = Point(visit["longitude"], visit["latitude"])
        # Find which hexagon contains this visit
        for idx, row in h3_gdf.iterrows():
            if row.geometry.contains(visit_point):
                visit_hexagons.add(idx)
                break

    print(f"Found {len(visit_hexagons)} hexagons containing visits")

    # Process each trajectory point
    anonymized_trajectories = []
    anonymized_count = 0

    for trajectory in trajectories_data:
        lat, lon = trajectory["latitude"], trajectory["longitude"]
        traj_point = Point(lon, lat)

        # Check if this point is in a hexagon that contains visits
        point_anonymized = False
        for hex_idx in visit_hexagons:
            hex_geometry = h3_gdf.iloc[hex_idx].geometry
            if hex_geometry.contains(traj_point):
                # Generate random point within this hexagon
                new_lat, new_lon = generate_random_point_in_polygon(hex_geometry)

                # Create anonymized trajectory point
                anonymized_trajectory = trajectory.copy()
                anonymized_trajectory["latitude"] = new_lat
                anonymized_trajectory["longitude"] = new_lon
                anonymized_trajectories.append(anonymized_trajectory)
                anonymized_count += 1
                point_anonymized = True
                break

        if not point_anonymized:
            # Keep original point if not in a visit hexagon
            anonymized_trajectories.append(trajectory)

    print(
        f"Anonymized {anonymized_count} out of {len(trajectories_data)} trajectory points"
    )
    return anonymized_trajectories


def generate_random_point_in_polygon(polygon_geometry):
    """
    Generate a random point within a polygon geometry.
    Uses bounding box approach with rejection sampling.
    """
    # Get bounding box
    bounds = polygon_geometry.bounds
    min_lon, min_lat, max_lon, max_lat = bounds

    # Generate random point within bounding box that falls inside polygon
    max_attempts = 100
    for _ in range(max_attempts):
        random_lat = random.uniform(min_lat, max_lat)
        random_lon = random.uniform(min_lon, max_lon)
        point = Point(random_lon, random_lat)

        if polygon_geometry.contains(point):
            return random_lat, random_lon

    # Fallback to centroid if no valid point found
    centroid = polygon_geometry.centroid
    return centroid.y, centroid.x


def detect_visits_from_trajectory(coordenadas, uid, min_duration_minutes=10, movement_threshold_meters=300):
    """
    Detect visits from a trajectory based on staying at locations for a minimum duration.
    
    Args:
        coordenadas: List of (lat, lon, timestamp) tuples
        uid: User identifier
        min_duration_minutes: Minimum time to spend at a location to be considered a visit
        movement_threshold_meters: Distance threshold to consider as movement
    
    Returns:
        Tuple of (visits_data, trajectories_data)
    """
    if not coordenadas:
        return [], []
    
    visits_data = []
    trajectories_data = []
    trip_number = 1
    
    # Track visit state
    current_visit_start = None
    current_visit_location = None
    current_visit_coords = []  # Store all coordinates during current visit
    
    for i, (lat, lon, timestamp) in enumerate(coordenadas):
        # Convert timestamp if it's a string
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        
        # Check if user moved significantly from current visit location
        moved = False
        if current_visit_location:
            distance = calculate_distance(
                lat, lon, current_visit_location[0], current_visit_location[1]
            )
            moved = distance > movement_threshold_meters
        
        if moved:
            # User moved - close current visit if it meets duration requirement
            if current_visit_start and current_visit_location:
                visit_duration = timestamp - current_visit_start
                if visit_duration >= timedelta(minutes=min_duration_minutes):
                    # Calculate average location during the visit
                    avg_lat = sum(coord[0] for coord in current_visit_coords) / len(current_visit_coords)
                    avg_lon = sum(coord[1] for coord in current_visit_coords) / len(current_visit_coords)
                    
                    visits_data.append({
                        "uid": uid,
                        "trip_number": trip_number,
                        "arrive_time": current_visit_start,
                        "depart_time": timestamp,
                        "latitude": avg_lat,
                        "longitude": avg_lon,
                        "purpose": None,
                        "mode_of_transport": None,
                    })
                    
                    # Increment trip number for next trip
                    trip_number += 1
            
            # Reset visit tracking since user is moving
            current_visit_start = None
            current_visit_location = None
            current_visit_coords = []
        
        else:
            # User didn't move significantly - start/continue visit
            if not current_visit_start:
                current_visit_start = timestamp
                current_visit_location = (lat, lon)
                current_visit_coords = [(lat, lon)]
            else:
                # Add to current visit coordinates
                current_visit_coords.append((lat, lon))
        
        # Add all points to trajectory data with current trip number
        trajectories_data.append({
            "uid": uid,
            "latitude": lat,
            "longitude": lon,
            "timestamp": timestamp,
            "trip_number": trip_number,
        })
    
    # Handle final visit if trajectory ends during a stay
    if current_visit_start and current_visit_location and current_visit_coords:
        final_timestamp = coordenadas[-1][2]
        if isinstance(final_timestamp, str):
            final_timestamp = datetime.fromisoformat(
                final_timestamp.replace("Z", "+00:00")
            )
        
        visit_duration = final_timestamp - current_visit_start
        if visit_duration >= timedelta(minutes=min_duration_minutes):
            # Calculate average location during the visit
            avg_lat = sum(coord[0] for coord in current_visit_coords) / len(current_visit_coords)
            avg_lon = sum(coord[1] for coord in current_visit_coords) / len(current_visit_coords)
            
            visits_data.append({
                "uid": uid,
                "trip_number": trip_number,
                "arrive_time": current_visit_start,
                "depart_time": final_timestamp,
                "latitude": avg_lat,
                "longitude": avg_lon,
                "purpose": None,
                "mode_of_transport": None,
            })
    
    return visits_data, trajectories_data

def handle_raw_trajectories(coordenadas):
    con = get_db()

    # Get next available uid from trajectory table instead of coordenadas
    uid = con.sql("SELECT COALESCE(MAX(uid), 0) + 1 FROM trajectory").fetchone()[0]

    if not coordenadas:
        return

    # Use the new visit detection function
    visits_data, trajectories_data = detect_visits_from_trajectory(coordenadas, uid)

    # Anonymize trajectories before inserting into database
    anonymized_trajectories = anonymize_trajectories(trajectories_data, visits_data)

    # Insert visits into database
    if visits_data:
        visits_df = pd.DataFrame(visits_data)
        visits_df = classify_visits(visits_df)
        con.sql(
            """INSERT INTO visit (uid, trip_number, arrive_time, depart_time, latitude, longitude, purpose, mode_of_transport)
                 SELECT uid, trip_number, arrive_time, depart_time, latitude, longitude, purpose, mode_of_transport FROM visits_df"""
        )

    # Insert anonymized trajectories into database
    if anonymized_trajectories:
        trajectories_df = pd.DataFrame(anonymized_trajectories)
        con.sql(
            """INSERT INTO trajectory (uid, latitude, longitude, timestamp, trip_number)
                 SELECT uid, latitude, longitude, timestamp, trip_number FROM trajectories_df"""
        )
        number_of_inserted = con.sql(
            f"SELECT COUNT(*) FROM trajectory WHERE uid = {uid}"
        ).fetchone()[0]
        print(
            f"Inserted {number_of_inserted} anonymized trajectory points for uid {uid}"
        )

    print(f"Processed {len(trajectories_data)} trajectory points")
    print(f"Detected {len(visits_data)} visits")
    if visits_data:
        max_trip = max(visit['trip_number'] for visit in visits_data)
        print(f"Total trips: {max_trip}")


def classify_visits(visits_df):
    if visits_df.empty:
        return visits_df

    # Load the neighborhood boundaries
    gdf = gpd.read_file("../dados/bairros_curitiba.zip")

    # Load the trained model and encoders
    try:
        model = joblib.load("../modelos/lgb_purpose_model.pkl")
        with open("../modelos/lgb_purpose_encoders.pkl", "rb") as f:
            encoders = pickle.load(f)

        le_bairro = encoders["le_bairro"]
        le_purpose = encoders["le_purpose"]

    except FileNotFoundError as e:
        print(f"Model files not found: {e}")
        # Fallback to default values
        visits_df["mode_of_transport"] = "CAR"
        visits_df["purpose"] = "WORK"
        return visits_df

    # Create GeoDataFrame from visits
    visits_gdf = gpd.GeoDataFrame(
        visits_df,
        geometry=[
            Point(row.longitude, row.latitude) for _, row in visits_df.iterrows()
        ],
        crs="EPSG:4326",
    )

    # Ensure both have the same CRS
    if gdf.crs != visits_gdf.crs:
        gdf = gdf.to_crs(visits_gdf.crs)

    # Spatial join to get neighborhood (bairro)
    visits_with_bairro = gpd.sjoin(visits_gdf, gdf, how="left", predicate="within")

    # Get the neighborhood column name (adjust based on your shapefile)
    # Common column names: 'NOME', 'nome', 'bairro', 'Bairro'
    bairro_column = "NOME"
    visits_df["Bairro"] = visits_with_bairro[bairro_column].fillna("Unknown")

    # Extract time features from arrive_time
    visits_df["arrive_time"] = pd.to_datetime(visits_df["arrive_time"])
    visits_df["HOUR"] = visits_df["arrive_time"].dt.hour
    visits_df["DAY_OF_WEEK"] = visits_df["arrive_time"].dt.dayofweek

    # Prepare features for prediction
    X_features = visits_df[["Bairro", "HOUR", "DAY_OF_WEEK"]].copy()

    # Handle unknown neighborhoods
    known_bairros = set(le_bairro.classes_)
    X_features["Bairro"] = X_features["Bairro"].apply(
        lambda x: x if x in known_bairros else "Unknown"
    )

    # If 'Unknown' is not in the original training set, map to most common bairro
    if "Unknown" not in known_bairros:
        # Get the most frequent bairro from training (first class in encoder)
        most_common_bairro = le_bairro.classes_[0]
        X_features["Bairro"] = X_features["Bairro"].replace(
            "Unknown", most_common_bairro
        )

    # Encode features
    try:
        X_encoded = X_features.copy()
        X_encoded["Bairro"] = le_bairro.transform(X_features["Bairro"])

        # Make predictions
        y_pred_encoded = model.predict(X_encoded)

        # Decode predictions back to purpose labels
        visits_df["purpose"] = le_purpose.inverse_transform(y_pred_encoded)

        print(f"Successfully classified {len(visits_df)} visits")
        print(f"Purpose distribution: {visits_df['purpose'].value_counts().to_dict()}")

    except Exception as e:
        print(f"Error during prediction: {e}")
        # Fallback to default purpose
        visits_df["purpose"] = "OTHER"

    # Set mode of transport (you can improve this later with additional models)
    visits_df["mode_of_transport"] = "CAR"

    # Drop temporary columns if you don't want to keep them
    visits_df = visits_df.drop(
        columns=["Bairro", "HOUR", "DAY_OF_WEEK"], errors="ignore"
    )

    return visits_df


def get_recent_trajectory_data():
    con = get_db()

    # Get recent visits
    recent_visits = con.sql(
        """
        SELECT * FROM visit
        WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '10 minutes'
        AND validated = FALSE
        ORDER BY created_at DESC
    """
    )

    if recent_visits.df().empty:
        return [], []

    visits_df = recent_visits.df()

    # Convert datetime columns to strings for JSON serialization
    datetime_columns = ["arrive_time", "depart_time", "created_at"]
    for col in datetime_columns:
        if col in visits_df.columns:
            visits_df[col] = visits_df[col].dt.strftime("%Y-%m-%d %H:%M:%S")

    # Get unique combinations of uid and trip_number from recent visits
    uid_trip_combinations = visits_df[["uid", "trip_number"]].drop_duplicates()

    # Get corresponding trajectories for these visits
    trajectories_data = []

    for _, row in uid_trip_combinations.iterrows():
        uid = int(row["uid"])  # Convert to Python int
        trip_number = int(row["trip_number"])  # Convert to Python int

        # Get trajectory points for this specific uid and trip_number
        trajectory_query = con.sql(
            f"""
            SELECT * FROM trajectory
            WHERE uid = {uid} AND trip_number = {trip_number}
            ORDER BY timestamp ASC
        """
        )

        if not trajectory_query.df().empty:
            trajectory_df = trajectory_query.df()

            # Convert timestamp column to string for JSON serialization
            if "timestamp" in trajectory_df.columns:
                trajectory_df["timestamp"] = trajectory_df["timestamp"].dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            if "created_at" in trajectory_df.columns:
                trajectory_df["created_at"] = trajectory_df["created_at"].dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

            # Convert numeric columns to Python native types
            numeric_columns = ["uid", "trip_number", "latitude", "longitude"]
            for col in numeric_columns:
                if col in trajectory_df.columns:
                    if col in ["uid", "trip_number"]:
                        trajectory_df[col] = trajectory_df[col].astype(int)
                    else:
                        trajectory_df[col] = trajectory_df[col].astype(float)

            # Convert to list of dictionaries for easier handling
            trajectory_points = trajectory_df.to_dict("records")

            trajectories_data.append(
                {
                    "uid": uid,
                    "trip_number": trip_number,
                    "trajectory_points": trajectory_points,
                    "point_count": len(trajectory_points),
                }
            )

    # Convert visits to list of dictionaries and handle numpy types
    visits_data = visits_df.to_dict("records")

    # Convert numpy types to Python native types in visits_data
    for visit in visits_data:
        for key, value in visit.items():
            if hasattr(value, "item"):  # numpy scalar
                visit[key] = value.item()
            elif pd.isna(value):  # Handle NaN values
                visit[key] = None

    print(f"Found {len(visits_data)} recent visits")
    print(f"Found {len(trajectories_data)} corresponding trajectories")

    return visits_data, trajectories_data


def update_visit_data(dados):
    con = get_db()

    for visit in dados.visits:
        con.sql(
            f"""
        UPDATE visit
        SET purpose = '{visit.purpose}', 
        mode_of_transport = '{visit.mode_of_transport}', 
        validated = TRUE
        WHERE uid = {visit.uid} AND trip_number = {visit.trip_number}
        """
        )
