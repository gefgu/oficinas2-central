import pandas as pd
import requests
import os
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.utils import handle_raw_trajectories

if __name__ == "__main__":
    # Set to development mode for testing
    os.environ['PRODUCTION_MODE'] = 'false'
    
    sample_df = pd.read_csv("../dados/sample_detailed_trajectory_user_53308444_2.csv")
    sample_data = sample_df[["lat", "lon", "timestamp"]].values.tolist()
    handle_raw_trajectories(sample_data)

    # # Replace with your actual server URL
    # server_url = "http://192.168.1.83:8000"  # Adjust port if needed
    
    # try:
    #     response = requests.post(f"{server_url}/trajectories/", json={"coordenadas": sample_data})
        
    #     if response.status_code == 200:
    #         print("Data sent successfully!")
    #         print(f"Response: {response.json()}")
    #     else:
    #         print(f"Error: {response.status_code}")
    #         print(f"Response: {response.text}")
            
    # except requests.exceptions.RequestException as e:
    #     print(f"Request failed: {e}")