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

test = pd.read_csv("./test_trajectory.csv")

test['time'] = pd.to_datetime(test['time'])
test['time_diff'] = test['time'].diff().dt.total_seconds()

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

test['distance'] = calculate_distance(test['lat'].shift(), test['lon'].shift(), test['lat'], test['lon'])
test['speed'] = test['distance'] / test['time_diff']
test['acceleration'] = test['speed'].diff() / test['time_diff']

def calculate_bearing(lat1, lon1, lat2, lon2):
    delta_lon = np.radians(lon2 - lon1)
    lat1, lat2 = np.radians(lat1), np.radians(lat2)
    y = np.sin(delta_lon) * np.cos(lat2)
    x = np.cos(lat1)*np.sin(lat2) - np.sin(lat1)*np.cos(lat2)*np.cos(delta_lon)
    bearing = (np.degrees(np.arctan2(y, x)) + 360) % 360
    return bearing

test['bearing'] = calculate_bearing(test['lat'].shift(), test['lon'].shift(), test['lat'], test['lon'])
test = test.dropna()

X_new = test.drop(['label','time','lat','lon'], axis=1)
y_pred_new = rf_classifier.predict(X_new)
print("Predicted labels (estimativa de veículo):", y_pred_new)