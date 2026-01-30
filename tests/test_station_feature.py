
import sys
import os
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), 'src')))

from workflow import GribSelectorSession

def test_station_search():
    print("--- Test Station Search Feature ---")
    session = GribSelectorSession()
    
    # 1. Add GRIB
    grib_path = 'tests/data/gfs_0_25.2026-01-30T19-06-17Z.grb2'
    if not os.path.exists(grib_path):
        print(f"Test GRIB not found: {grib_path}")
        return
        
    session.add_grib(grib_path)
    
    # 2. List stations
    stations = session.list_nearby_stations()
    
    if stations.empty:
        print("No stations found.")
    else:
        print(f"Found {len(stations)} stations.")
        print(stations[['id', 'name', 'lat', 'lon']].head())
        
        # Check for our known test station
        split = stations[stations['id'] == 'LDSP']
        if not split.empty:
            print("SUCCESS: Found Split (LDSP)")
        else:
            print("FAILURE: Did not find Split (LDSP)")

if __name__ == "__main__":
    try:
        test_station_search()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
