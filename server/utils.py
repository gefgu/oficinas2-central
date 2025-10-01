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
    """
    Anonymize trajectory data by replacing points with random locations within H3 hexagons.
    Points that fall within the same H3 hexagon as visit locations are randomized within that hexagon.
    Only keeps the first 30 and last 30 anonymized points for each visit to reduce storage.
    """
    if not trajectories_data or not visits_data:
        return trajectories_data

    # Load H3 hexagons
    h3_gdf = load_h3_hexagons()
    if h3_gdf is None:
        print("Could not load H3 hexagons, returning original trajectories")
        return trajectories_data

    # Ensure consistent CRS
    if h3_gdf.crs is None:
        h3_gdf = h3_gdf.set_crs("EPSG:4326")
    elif h3_gdf.crs != "EPSG:4326":
        h3_gdf = h3_gdf.to_crs("EPSG:4326")

    # Create GeoDataFrame for visits
    visits_gdf = gpd.GeoDataFrame(
        visits_data,
        geometry=[Point(visit["longitude"], visit["latitude"]) for visit in visits_data],
        crs="EPSG:4326"
    )

    # Find hexagons that contain visit locations using spatial join
    visit_hexagons_gdf = gpd.sjoin(visits_gdf, h3_gdf, how='inner', predicate='within')
    visit_hexagon_indices = set(visit_hexagons_gdf.index_right.unique())

    print(f"Found {len(visit_hexagon_indices)} hexagons containing visits")

    if not visit_hexagon_indices:
        print("No visit hexagons found, returning original trajectories")
        return trajectories_data

    # Create GeoDataFrame for trajectory points
    trajectory_gdf = gpd.GeoDataFrame(
        trajectories_data,
        geometry=[Point(traj["longitude"], traj["latitude"]) for traj in trajectories_data],
        crs="EPSG:4326"
    )

    # Get only the hexagons that contain visits for efficiency
    visit_hexagons_subset = h3_gdf.iloc[list(visit_hexagon_indices)]

    # Use spatial join to find which trajectory points are in visit hexagons
    trajectory_in_visit_hexagons = gpd.sjoin(
        trajectory_gdf, 
        visit_hexagons_subset, 
        how='left', 
        predicate='within'
    )

    # Group trajectory points by visit_number to handle each visit separately
    visit_groups = {}
    for i, trajectory in enumerate(trajectories_data):
        visit_num = trajectory.get("visit_number")
        if visit_num is not None:
            if visit_num not in visit_groups:
                visit_groups[visit_num] = []
            visit_groups[visit_num].append((i, trajectory))

    # Process trajectories
    anonymized_trajectories = []
    anonymized_count = 0
    skipped_middle_count = 0

    for i, trajectory in enumerate(trajectories_data):
        # Check if this trajectory point is in a visit hexagon
        if pd.notna(trajectory_in_visit_hexagons.iloc[i]['index_right']):
            visit_num = trajectory.get("visit_number")
            
            # Determine if this point should be kept (first 30 or last 30 of the visit)
            should_keep = False
            if visit_num is not None and visit_num in visit_groups:
                visit_points = visit_groups[visit_num]
                total_points = len(visit_points)
                
                # Find position of current point in this visit's sequence
                position_in_visit = next(
                    (idx for idx, (orig_idx, _) in enumerate(visit_points) if orig_idx == i),
                    None
                )
                
                if position_in_visit is not None:
                    # Keep first 30 or last 30 points
                    if position_in_visit < 30 or position_in_visit >= total_points - 30:
                        should_keep = True

            if should_keep:
                # This point is in a visit hexagon and within first/last 30 - anonymize it
                hex_idx = int(trajectory_in_visit_hexagons.iloc[i]['index_right'])
                hex_geometry = h3_gdf.iloc[hex_idx].geometry

                # Generate random point within this hexagon
                new_lat, new_lon = generate_random_point_in_polygon(hex_geometry)

                # Create anonymized trajectory point
                anonymized_trajectory = trajectory.copy()
                anonymized_trajectory["latitude"] = new_lat
                anonymized_trajectory["longitude"] = new_lon
                anonymized_trajectories.append(anonymized_trajectory)
                anonymized_count += 1
            else:
                # Skip middle points of visits
                skipped_middle_count += 1
        else:
            # Keep original point if not in a visit hexagon (movement between visits)
            anonymized_trajectories.append(trajectory)

    print(f"Anonymized {anonymized_count} out of {len(trajectories_data)} trajectory points")
    print(f"Skipped {skipped_middle_count} middle points from visits")
    print(f"Kept {len(anonymized_trajectories)} total trajectory points")
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
    for attempt in range(max_attempts):
        random_lat = random.uniform(min_lat, max_lat)
        random_lon = random.uniform(min_lon, max_lon)
        point = Point(random_lon, random_lat)

        if polygon_geometry.contains(point):
            return random_lat, random_lon

    # Fallback to centroid if no valid point found
    print(f"Warning: Could not find random point in polygon after {max_attempts} attempts, using centroid")
    centroid = polygon_geometry.centroid
    return centroid.y, centroid.x


def detect_visits_from_trajectory(coordenadas, uid, min_duration_minutes=10, movement_threshold_meters=300):
    """
    Detect visits from a trajectory based on staying at locations for a minimum duration.
    
    Logic:
    - If trajectory starts with a stay → Visit 1 (no trip number yet)
    - Movement between visits → Trip N (from Visit N to Visit N+1)
    - If trajectory ends with a stay → Final Visit
    
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
    visit_number = 1
    current_trip_number = None  # No trip until we start moving between visits
    
    # Track visit state
    current_visit_start = None
    current_visit_location = None
    current_visit_coords = []
    in_visit = False
    
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
        
        if moved and in_visit:
            # User moved - close current visit if it meets duration requirement
            if current_visit_start and current_visit_location:
                visit_duration = timestamp - current_visit_start
                if visit_duration >= timedelta(minutes=min_duration_minutes):
                    # Calculate average location during the visit
                    avg_lat = sum(coord[0] for coord in current_visit_coords) / len(current_visit_coords)
                    avg_lon = sum(coord[1] for coord in current_visit_coords) / len(current_visit_coords)
                    
                    visits_data.append({
                        "uid": uid,
                        "visit_number": visit_number,
                        "arrive_time": current_visit_start,
                        "depart_time": timestamp,
                        "latitude": avg_lat,
                        "longitude": avg_lon,
                        "purpose": None,
                        "mode_of_transport": None,
                    })
                    
                    visit_number += 1
            
            # Reset visit tracking and start trip
            current_visit_start = None
            current_visit_location = None
            current_visit_coords = []
            in_visit = False
            current_trip_number = visit_number  # Trip TO the next visit
        
        elif not moved and not in_visit:
            # User stopped moving - start potential visit
            current_visit_start = timestamp
            current_visit_location = (lat, lon)
            current_visit_coords = [(lat, lon)]
            in_visit = True
            
        elif not moved and in_visit:
            # Continue current visit
            current_visit_coords.append((lat, lon))
        
        # Add trajectory point with appropriate trip number
        # Points during visits get None, points during movement get trip number
        trajectories_data.append({
            "uid": uid,
            "latitude": lat,
            "longitude": lon,
            "timestamp": timestamp,
            "trip_number": current_trip_number if not in_visit else None,
            "visit_number": visit_number if in_visit else None,
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
                "visit_number": visit_number,
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
            """INSERT INTO visit (uid, visit_number, arrive_time, depart_time, latitude, longitude, purpose, mode_of_transport)
                 SELECT uid, visit_number, arrive_time, depart_time, latitude, longitude, purpose, mode_of_transport FROM visits_df"""
        )

    # Insert anonymized trajectories into database
    if anonymized_trajectories:
        trajectories_df = pd.DataFrame(anonymized_trajectories)
        con.sql(
            """INSERT INTO trajectory (uid, latitude, longitude, timestamp, trip_number, visit_number)
                 SELECT uid, latitude, longitude, timestamp, trip_number, visit_number FROM trajectories_df"""
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
        max_visit = max(visit['visit_number'] for visit in visits_data)
        print(f"Total visits: {max_visit}")


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

    # Get unique combinations of uid and visit_number from recent visits
    uid_trip_combinations = visits_df[["uid", "visit_number"]].drop_duplicates()

    # Get corresponding trajectories for these visits
    trajectories_data = []

    for _, row in uid_trip_combinations.iterrows():
        uid = int(row["uid"])  # Convert to Python int
        visit_number = int(row["visit_number"])  # Convert to Python int

        # Get trajectory points for this specific uid and visit_number
        trajectory_query = con.sql(
            f"""
            SELECT * FROM trajectory
            WHERE uid = {uid} AND visit_number = {visit_number}
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
            numeric_columns = ["uid", "visit_number", "latitude", "longitude"]
            for col in numeric_columns:
                if col in trajectory_df.columns:
                    if col in ["uid", "visit_number"]:
                        trajectory_df[col] = trajectory_df[col].astype(int)
                    else:
                        trajectory_df[col] = trajectory_df[col].astype(float)

            # Convert to list of dictionaries for easier handling
            trajectory_points = trajectory_df.to_dict("records")

            trajectories_data.append(
                {
                    "uid": uid,
                    "visit_number": visit_number,
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
        WHERE uid = {visit.uid} AND visit_number = {visit.visit_number}
        """
        )
