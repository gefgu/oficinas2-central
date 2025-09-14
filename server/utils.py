import time
import requests
from typing import List, Dict, Any
from datetime import datetime
from data import sample_trajectories
import json

def get_sample_trajectories():
    return json.dumps(sample_trajectories)