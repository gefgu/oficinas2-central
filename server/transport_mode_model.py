import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
import glob
import os.path
import datetime
import os
from math import atan2, degrees, sin, cos, sqrt, radians
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import warnings
import pickle

warnings.filterwarnings('ignore')

# Load
with open("random_forest_model.pkl", "rb") as f:
    rf_classifier = pickle.load(f)


mode_names = ['walk', 'bike', 'bus', 'car', 'subway','train', 'airplane', 'boat', 'run', 'motorcycle', 'taxi']
mode_ids = {s : i + 1 for i, s in enumerate(mode_names)}
id_modes = {i + 1: s for i, s in enumerate(mode_names)}  # Reverse mapping

def map_transport_mode(mode):
    """
    Map detailed transport modes to simplified categories.
    
    Args:
        mode: Original transport mode string (lowercase)
    
    Returns:
        Simplified transport mode category
    """
    mode_lower = mode.lower()
    
    # Walk + Run -> Walk
    if mode_lower in ['walk', 'run']:
        return 'Walk'
    
    # Bike + Motorcycle -> Two-Wheeler
    elif mode_lower in ['bike', 'motorcycle']:
        return 'Two-Wheeler'
    
    # Car + Taxi -> Car
    elif mode_lower in ['car', 'taxi']:
        return 'Car'
    
    # Keep Bus
    elif mode_lower == 'bus':
        return 'Bus'
    
    # Map others (subway, train, airplane, boat) to Others
    else:
        return 'Others'

def read_labels(labels_file):
    labels = pd.read_csv(labels_file, skiprows=1, header=None,
                         parse_dates=[[0, 1], [2, 3]],
                         infer_datetime_format=True, delim_whitespace=True)
    labels.columns = ['start_time', 'end_time', 'label']
    labels['label'] = [mode_ids[i] if i in mode_ids else 0 for i in labels['label']]
    return labels

def apply_labels(points, labels):
    indices = labels['start_time'].searchsorted(points['time'], side='right') - 1
    no_label = (indices < 0) | (points['time'].values >= labels['end_time'].iloc[indices].values)
    points['label'] = labels['label'].iloc[indices].values
    points.loc[no_label, 'label'] = 0


def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

def calculate_bearing(lat1, lon1, lat2, lon2):
    delta_lon = np.radians(lon2 - lon1)
    lat1, lat2 = np.radians(lat1), np.radians(lat2)
    y = np.sin(delta_lon) * np.cos(lat2)
    x = np.cos(lat1)*np.sin(lat2) - np.sin(lat1)*np.cos(lat2)*np.cos(delta_lon)
    bearing = (np.degrees(np.arctan2(y, x)) + 360) % 360
    return bearing

def predict_transport_mode(df):
    """
    Predict transport mode for a trajectory.
    
    Args:
        df: DataFrame with columns ['lat', 'lon', 'time']
        return_mode: 
            - 'most_common': Returns the most frequently predicted mode (voting)
            - 'avg_probability': Returns mode with highest average probability
            - 'all': Returns all predictions for each point
        simplify: If True, maps predictions to simplified categories
    
    Returns:
        Single transport mode (string) or list of predictions
    """
    df = df.copy()  # Avoid modifying original dataframe
    df['time'] = pd.to_datetime(df['time'])
    df['time_diff'] = df['time'].diff().dt.total_seconds()
    df['month'] = df['time'].dt.month
    df['day'] = df['time'].dt.day
    df['hour'] = df['time'].dt.hour

    df['distance'] = calculate_distance(df['lat'].shift(), df['lon'].shift(), df['lat'], df['lon'])
    df['speed'] = df['distance'] / df['time_diff']
    df['acceleration'] = df['speed'].diff() / df['time_diff']
    df['bearing'] = calculate_bearing(df['lat'].shift(), df['lon'].shift(), df['lat'], df['lon'])
    df = df.dropna()
    df['alt'] = None  # Assuming altitude is not available in test data

    df_features = df[['alt', 'time_diff', 'distance', 'speed', 'acceleration', 'bearing', 'month', 'day', 'hour']]

    X_new = df_features.copy()
    y_pred_new = rf_classifier.predict(X_new)
    
    # Use voting: most frequently predicted mode
    mode_counts = pd.Series(y_pred_new).value_counts()
    most_common_mode_id = mode_counts.idxmax()
    most_common_mode = id_modes.get(most_common_mode_id, 'unknown')

    if most_common_mode == 'unknown' and len(mode_counts) > 1:
        second_most_common_mode_id = mode_counts.index[1]
        most_common_mode = id_modes.get(second_most_common_mode_id, 'unknown')


    most_common_mode = map_transport_mode(most_common_mode)
    
    print(f"Transport mode prediction (voting): {most_common_mode}")
    print(f"Mode distribution: {dict(mode_counts)}")
    return most_common_mode


if __name__ == "__main__":
    test = pd.read_csv("./test_trajectory.csv")

    test = test.rename(columns={"latitude": "lat", "longitude": "lon", "timestamp": "time"})
    test = test[test["trip_number"] == 1]
    test = test[["lat", "lon", "time"]]
    predicted_mode = predict_transport_mode(test, simplify=True)
    print(f"\nFinal simplified prediction: {predicted_mode}")