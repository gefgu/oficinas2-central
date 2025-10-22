import time
import numpy as np
import requests
from typing import List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from sklearn.cluster import DBSCAN

from transport_mode_model import predict_transport_mode

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
    Keeps ALL trajectory points between visits (trip_number is not None).
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
        geometry=[
            Point(visit["longitude"], visit["latitude"]) for visit in visits_data
        ],
        crs="EPSG:4326",
    )

    # Find hexagons that contain visit locations using spatial join
    visit_hexagons_gdf = gpd.sjoin(visits_gdf, h3_gdf, how="inner", predicate="within")
    visit_hexagon_indices = set(visit_hexagons_gdf.index_right.unique())

    print(f"Found {len(visit_hexagon_indices)} hexagons containing visits")

    if not visit_hexagon_indices:
        print("No visit hexagons found, returning original trajectories")
        return trajectories_data

    # Create GeoDataFrame for trajectory points
    trajectory_gdf = gpd.GeoDataFrame(
        trajectories_data,
        geometry=[
            Point(traj["longitude"], traj["latitude"]) for traj in trajectories_data
        ],
        crs="EPSG:4326",
    )

    # Get only the hexagons that contain visits for efficiency
    visit_hexagons_subset = h3_gdf.iloc[list(visit_hexagon_indices)]

    # Use spatial join to find which trajectory points are in visit hexagons
    trajectory_in_visit_hexagons = gpd.sjoin(
        trajectory_gdf, visit_hexagons_subset, how="left", predicate="within"
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
    kept_trip_count = 0

    for i, trajectory in enumerate(trajectories_data):
        trip_num = trajectory.get("trip_number")
        visit_num = trajectory.get("visit_number")
        
        # ALWAYS keep trajectory points (trip_number is not None)
        if trip_num is not None:
            # This is a trajectory point between visits - keep it regardless
            anonymized_trajectories.append(trajectory)
            kept_trip_count += 1
            continue
        
        # For visit points (visit_number is not None), apply the first/last 30 rule
        if visit_num is not None:
            # Check if this trajectory point is in a visit hexagon
            if pd.notna(trajectory_in_visit_hexagons.iloc[i]["index_right"]):
                # Determine if this point should be kept (first 30 or last 30 of the visit)
                should_keep = False
                if visit_num in visit_groups:
                    visit_points = visit_groups[visit_num]
                    total_points = len(visit_points)

                    # Find position of current point in this visit's sequence
                    position_in_visit = next(
                        (
                            idx
                            for idx, (orig_idx, _) in enumerate(visit_points)
                            if orig_idx == i
                        ),
                        None,
                    )

                    if position_in_visit is not None:
                        # Keep first 30 or last 30 points
                        if position_in_visit < 30 or position_in_visit >= total_points - 30:
                            should_keep = True

                if should_keep:
                    # This point is in a visit hexagon and within first/last 30 - anonymize it
                    hex_idx = int(trajectory_in_visit_hexagons.iloc[i]["index_right"])
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
                # Visit point not in hexagon - keep it
                anonymized_trajectories.append(trajectory)

    print(
        f"Anonymized {anonymized_count} out of {len(trajectories_data)} trajectory points"
    )
    print(f"Skipped {skipped_middle_count} middle points from visits")
    print(f"Kept {kept_trip_count} trip trajectory points (between visits)")
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
    print(
        f"Warning: Could not find random point in polygon after {max_attempts} attempts, using centroid"
    )
    centroid = polygon_geometry.centroid
    return centroid.y, centroid.x

def identify_stationary_points(trajectory_gdf, eps_meters=100, min_samples=60, temporal_eps_minutes=15):
    """
    Use spatio-temporal DBSCAN to identify stationary points vs trajectory points.
    
    Parameters:
    - trajectory_gdf: GeoDataFrame with trajectory points
    - eps_meters: maximum spatial distance (in meters) between points in a cluster
    - min_samples: minimum number of points to form a stationary cluster
    - temporal_eps_minutes: maximum temporal gap (in minutes) to separate visits
    
    Returns:
    - GeoDataFrame with additional columns: 'cluster', 'is_stationary', 'stationary_label'
    """
    # Convert to a projected CRS for distance calculations in meters
    gdf_projected = trajectory_gdf.to_crs(epsg=3857)
    
    # Extract spatial coordinates
    spatial_coords = np.column_stack([gdf_projected.geometry.x, gdf_projected.geometry.y])
    
    # Convert timestamps to seconds since first point
    timestamps = (trajectory_gdf['timestamp'] - trajectory_gdf['timestamp'].min()).dt.total_seconds()
    
    # Scale temporal dimension to match spatial importance
    # 1 minute = 60 seconds = 60 meters equivalent (adjust this ratio as needed)
    temporal_scale = 60  # seconds per equivalent meter
    temporal_coords = (timestamps / temporal_scale).values.reshape(-1, 1)
    
    # Combine spatial and temporal coordinates
    # This creates 3D space: (X_meters, Y_meters, Time_scaled)
    coords = np.column_stack([spatial_coords, temporal_coords])
    
    # Calculate appropriate eps for 3D space
    # Use Euclidean distance: sqrt(dx² + dy² + dt²)
    # For points to cluster: spatial_dist <= eps_meters AND temporal_gap <= temporal_eps_minutes
    temporal_eps_scaled = (temporal_eps_minutes * 60) / temporal_scale  # minutes to scaled units
    eps_3d = np.sqrt(eps_meters**2 + temporal_eps_scaled**2)
    
    # Apply DBSCAN in 3D space
    dbscan = DBSCAN(eps=eps_3d, min_samples=min_samples, metric='euclidean')
    clusters = dbscan.fit_predict(coords)
    
    # Add cluster labels to dataframe
    result_gdf = trajectory_gdf.copy()
    result_gdf['cluster'] = clusters
    result_gdf['is_stationary'] = result_gdf['cluster'] != -1
    result_gdf['stationary_label'] = result_gdf.apply(
        lambda row: f"Stationary_{row['cluster']}" if row['is_stationary'] else "Trajectory",
        axis=1
    )
    
    # Calculate statistics
    n_stationary = result_gdf['is_stationary'].sum()
    n_trajectory = (~result_gdf['is_stationary']).sum()
    n_clusters = len(set(clusters)) - (1 if -1 in clusters else 0)
    
    print(f"Spatio-Temporal DBSCAN Results:")
    print(f"- Temporal separation threshold: {temporal_eps_minutes} minutes")
    print(f"- Spatial threshold: {eps_meters}m, Temporal scale: {temporal_scale}s/meter-equiv")
    print(f"- Combined 3D epsilon: {eps_3d:.1f}")
    print(f"- Total points: {len(result_gdf)}")
    print(f"- Stationary points: {n_stationary} ({n_stationary/len(result_gdf)*100:.1f}%)")
    print(f"- Trajectory points: {n_trajectory} ({n_trajectory/len(result_gdf)*100:.1f}%)")
    print(f"- Number of stationary clusters: {n_clusters}")
    
    # Print cluster statistics
    if n_clusters > 0:
        print(f"\nCluster details:")
        for cluster_id in sorted(result_gdf[result_gdf['is_stationary']]['cluster'].unique()):
            cluster_points = result_gdf[result_gdf['cluster'] == cluster_id]
            duration_seconds = (cluster_points['timestamp'].max() - cluster_points['timestamp'].min()).total_seconds()
            print(f"  Cluster {cluster_id}: {len(cluster_points)} points, "
                  f"{duration_seconds/60:.1f} minutes")
    
    return result_gdf


def detect_visits_from_trajectory(
    coordenadas, uid, min_duration_minutes=10, eps_meters=100, min_samples=60
):
    """
    Detect visits from a trajectory using DBSCAN clustering to identify stationary points.

    Logic:
    - Uses DBSCAN to identify clusters of stationary points
    - Each cluster that meets minimum duration becomes a visit
    - Points between visits are trajectory points with trip numbers
    - Trip numbers start from 1 and increment sequentially between visits
    - Visit location is the centroid of the cluster

    Args:
        coordenadas: List of (lat, lon, timestamp) tuples
        uid: User identifier
        min_duration_minutes: Minimum time to spend at a location to be considered a visit
        eps_meters: Maximum distance between points in a cluster (default: 100m)
        min_samples: Minimum points to form a stationary cluster (default: 60)

    Returns:
        Tuple of (visits_data, trajectories_data)
    """
    if not coordenadas:
        return [], []

    # Convert to DataFrame for easier handling
    trajectory_data = []
    for lat, lon, timestamp in coordenadas:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        trajectory_data.append({
            "latitude": lat,
            "longitude": lon,
            "timestamp": timestamp
        })
    
    trajectory_df = pd.DataFrame(trajectory_data)
    
    # Create GeoDataFrame for DBSCAN analysis
    trajectory_gdf = gpd.GeoDataFrame(
        trajectory_df,
        geometry=[Point(row.longitude, row.latitude) for _, row in trajectory_df.iterrows()],
        crs="EPSG:4326"
    )
    
    # Identify stationary points using DBSCAN
    result_gdf = identify_stationary_points(
        trajectory_gdf, 
        eps_meters=eps_meters, 
        min_samples=min_samples
    )
    
    visits_data = []
    trajectories_data = []
    visit_number = 1
    
    # Process each stationary cluster to create visits
    stationary_clusters = result_gdf[result_gdf['is_stationary']]['cluster'].unique()
    
    cluster_to_visit = {}  # Map cluster ID to visit number
    visit_times = {}  # Map visit number to (arrive_time, depart_time)
    
    for cluster_id in sorted(stationary_clusters):
        cluster_points = result_gdf[result_gdf['cluster'] == cluster_id].copy()
        
        # Check if cluster meets minimum duration requirement
        arrive_time = cluster_points['timestamp'].min()
        depart_time = cluster_points['timestamp'].max()
        duration = depart_time - arrive_time
        
        if duration >= timedelta(minutes=min_duration_minutes):
            # Calculate centroid (average location) of the cluster
            avg_lat = cluster_points['latitude'].mean()
            avg_lon = cluster_points['longitude'].mean()
            
            visits_data.append({
                "uid": uid,
                "visit_number": visit_number,
                "arrive_time": arrive_time,
                "depart_time": depart_time,
                "latitude": avg_lat,
                "longitude": avg_lon,
                "purpose": None,
                "mode_of_transport": None,
            })
            
            cluster_to_visit[cluster_id] = visit_number
            visit_times[visit_number] = (arrive_time, depart_time)
            visit_number += 1
        else:
            # Cluster doesn't meet duration requirement, treat as trajectory
            cluster_to_visit[cluster_id] = None
    
    # Sort visits by arrival time
    sorted_visits = sorted(visit_times.items(), key=lambda x: x[1][0])  # Sort by arrive_time
    
    # Build trajectories with appropriate trip/visit numbers
    current_trip_number = 1
    
    for idx, row in result_gdf.iterrows():
        timestamp = row['timestamp']
        
        if row['is_stationary'] and row['cluster'] in cluster_to_visit:
            visit_num = cluster_to_visit[row['cluster']]
            
            if visit_num is not None:
                # This point belongs to a valid visit
                trajectories_data.append({
                    "uid": uid,
                    "latitude": row['latitude'],
                    "longitude": row['longitude'],
                    "timestamp": row['timestamp'],
                    "trip_number": None,
                    "visit_number": visit_num,
                })
            else:
                # Stationary but didn't meet duration - treat as trajectory
                # Determine trip number based on temporal position relative to visits
                trip_num = None
                
                for i, (v_num, (arrive_time, depart_time)) in enumerate(sorted_visits):
                    if timestamp < arrive_time:
                        # Before this visit, so trip number is i+1
                        trip_num = i + 1
                        break
                    elif i < len(sorted_visits) - 1:
                        # Check if between this visit and next
                        next_arrive = sorted_visits[i + 1][1][0]
                        if depart_time <= timestamp < next_arrive:
                            trip_num = i + 2  # Trip to next visit
                            break
                
                # If after all visits, assign trip number after last visit
                if trip_num is None and sorted_visits:
                    trip_num = len(sorted_visits) + 1
                elif trip_num is None:
                    trip_num = 1  # No visits found
                
                trajectories_data.append({
                    "uid": uid,
                    "latitude": row['latitude'],
                    "longitude": row['longitude'],
                    "timestamp": row['timestamp'],
                    "trip_number": trip_num,
                    "visit_number": None,
                })
        else:
            # Trajectory point (not stationary)
            # Determine trip number based on temporal position relative to visits
            trip_num = None
            
            # Check position relative to visits
            for i, (v_num, (arrive_time, depart_time)) in enumerate(sorted_visits):
                if timestamp < arrive_time:
                    # Before this visit
                    trip_num = i + 1
                    break
                elif i < len(sorted_visits) - 1:
                    # Check if between this visit and next
                    next_arrive = sorted_visits[i + 1][1][0]
                    if depart_time <= timestamp < next_arrive:
                        trip_num = i + 2 # Trip to next visit
                        break
            
            # If after all visits, assign trip number after last visit
            if trip_num is None and sorted_visits:
                trip_num = len(sorted_visits) + 1
            elif trip_num is None:
                trip_num = 1  # No visits found, all points are one trip
            
            trajectories_data.append({
                "uid": uid,
                "latitude": row['latitude'],
                "longitude": row['longitude'],
                "timestamp": row['timestamp'],
                "trip_number": trip_num,
                "visit_number": None,
            })
    
    print(f"\nTrip assignment summary:")
    trips_df = pd.DataFrame(trajectories_data)
    if not trips_df.empty:
        trajectory_trips = trips_df[trips_df['trip_number'].notna()]
        if not trajectory_trips.empty:
            trip_counts = trajectory_trips['trip_number'].value_counts().sort_index()
            for trip_num, count in trip_counts.items():
                print(f"  Trip {int(trip_num)}: {count} trajectory points")
                # Print time range for this trip
                trip_points = trajectory_trips[trajectory_trips['trip_number'] == trip_num]
                start_time = trip_points['timestamp'].min()
                end_time = trip_points['timestamp'].max()
                print(f"    Time range: {start_time} to {end_time}")
    
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
    trajectories_df = (
        pd.DataFrame(anonymized_trajectories)
        if anonymized_trajectories
        else pd.DataFrame()
    )

    # Insert visits into database
    if visits_data:
        visits_df = pd.DataFrame(visits_data)
        visits_df = classify_visits(visits_df, trajectories_df)
        con.sql(
            """INSERT INTO visit (uid, visit_number, arrive_time, depart_time, latitude, longitude, purpose, mode_of_transport)
                 SELECT uid, visit_number, arrive_time, depart_time, latitude, longitude, purpose, mode_of_transport FROM visits_df"""
        )

    # Insert anonymized trajectories into database
    if not trajectories_df.empty:
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
        max_visit = max(visit["visit_number"] for visit in visits_data)
        print(f"Total visits: {max_visit}")


def classify_visits(visits_df, trajectories_df):
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
    visits_df = classify_transport_in_visits(visits_df, trajectories_df)

    # Drop temporary columns if you don't want to keep them
    visits_df = visits_df.drop(
        columns=["Bairro", "HOUR", "DAY_OF_WEEK"], errors="ignore"
    )

    return visits_df


def classify_transport_in_visits(visits_df, trajectories_df):
    # Initialize mode_of_transport column
    visits_df["mode_of_transport"] = "UNKNOWN"

    # Get unique uid from visits
    uid = visits_df["uid"].iloc[0] if not visits_df.empty else None

    if uid is not None and not trajectories_df.empty:
        # Filter trajectories for this uid
        user_trajectories = trajectories_df[trajectories_df["uid"] == uid]

        # Group by trip_number (movement between visits)
        trip_groups = user_trajectories[
            user_trajectories["trip_number"].notna()
        ].groupby("trip_number")

        for trip_num, trip_data in trip_groups:
            if len(trip_data) < 2:
                print(f"Skipping trip {trip_num}: not enough points")
                continue

            # Prepare data for transport mode prediction
            trip_df = trip_data[["latitude", "longitude", "timestamp"]].copy()
            trip_df = trip_df.rename(
                columns={"latitude": "lat", "longitude": "lon", "timestamp": "time"}
            )
            trip_df = trip_df.sort_values("time")

            try:
                # Predict transport mode for this trip
                transport_mode = predict_transport_mode(trip_df)

                # Assign to the destination visit (trip goes TO visit N)
                visit_mask = visits_df["visit_number"] == trip_num
                if visit_mask.any():
                    visits_df.loc[visit_mask, "mode_of_transport"] = (
                        transport_mode.upper()
                    )
                    print(f"Assigned mode '{transport_mode}' to visit {trip_num}")

            except Exception as e:
                print(f"Error predicting transport mode for trip {trip_num}: {e}")
                # Keep default "UNKNOWN"
            print(
                f"Mode of transport distribution: {visits_df['mode_of_transport'].value_counts().to_dict()}"
            )

    return visits_df


def get_recent_trajectory_data():
    con = get_db()

    # Get the most recent uid with unvalidated visits
    most_recent_uid_query = con.sql(
        """
        SELECT uid FROM visit
        WHERE validated = FALSE
        ORDER BY created_at DESC
        LIMIT 1
    """
    )

    if most_recent_uid_query.df().empty:
        return [], []

    most_recent_uid = most_recent_uid_query.df()["uid"].iloc[0]

    # Get all unvalidated visits for this uid
    recent_visits = con.sql(
        f"""
        SELECT * FROM visit
        WHERE uid = {most_recent_uid}
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

    # Use only the most recent uid
    unique_uids = [int(most_recent_uid)]

    # Get corresponding trajectories for these visits
    trajectories_data = []

    for uid in unique_uids:
        uid = int(uid)  # Convert to Python int
        
        # Get all trajectory points for this uid that are trips (not visit points)
        trajectory_query = con.sql(
            f"""
            SELECT * FROM trajectory
            WHERE uid = {uid} AND trip_number IS NOT NULL
            ORDER BY trip_number, timestamp ASC
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

            # Group by trip_number
            for trip_number in trajectory_df["trip_number"].unique():
                trip_points = trajectory_df[trajectory_df["trip_number"] == trip_number]
                trajectory_points = trip_points.to_dict("records")
                
                # Get start and end times for this trajectory
                start_time = trip_points["timestamp"].min()
                end_time = trip_points["timestamp"].max()

                trajectories_data.append(
                    {
                        "uid": uid,
                        "trip_number": int(trip_number),
                        "trajectory_points": trajectory_points,
                        "point_count": len(trajectory_points),
                        "start_time": start_time,
                        "end_time": end_time,
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
