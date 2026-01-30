
# Notebook Logic Verification Script
# replicates the cells in Interactive_Analysis.ipynb

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), 'src')))

from ingest.grib import load_grib_dataset, get_grib_metadata
from ingest.metar import fetch_metar, find_nearby_stations
from analysis.compare import compare_model_to_observations, calculate_errors, compute_metrics
from vis.plotting import plot_wind_comparison, plot_metar_data, plot_model_ranking

def test_workflow():
    print("--- 1. Load Data ---")
    GRIB_FILES = ['tests/data/gfs_0_25.2026-01-30T19-06-17Z.grb2']
    
    grib_metadata = {}
    global_bounds = {'lat_min': 90, 'lat_max': -90, 'lon_min': 180, 'lon_max': -180}
    
    for f in GRIB_FILES:
        if os.path.exists(f):
            meta = get_grib_metadata(f)
            if meta:
                grib_metadata[f] = meta
                print(f"Loaded {os.path.basename(f)}")
                # Update bounds
                global_bounds['lat_min'] = min(global_bounds['lat_min'], meta['lat_min'])
                global_bounds['lat_max'] = max(global_bounds['lat_max'], meta['lat_max'])
                global_bounds['lon_min'] = min(global_bounds['lon_min'], meta['lon_min'])
                global_bounds['lon_max'] = max(global_bounds['lon_max'], meta['lon_max'])
        else:
            print(f"File not found: {f}")
            return

    print("--- 2. Find Stations ---")
    stations_df = find_nearby_stations(
        global_bounds['lat_min'], global_bounds['lat_max'],
        global_bounds['lon_min'], global_bounds['lon_max']
    )
    
    print(f"Found {len(stations_df)} stations.")
    
    # Check for Split (LDSP)
    split = stations_df[stations_df['id'] == 'LDSP']
    if not split.empty:
        print("Success: Found Split (LDSP)")
        target_station = 'LDSP'
    else:
        print("Warning: Split (LDSP) not found in auto-search. Using manual override for test.")
        target_station = 'LDSP'

    print(f"--- 3. Analysis for {target_station} ---")
    metar_df = fetch_metar(target_station, hours=48)
    if metar_df.empty:
        print("No METAR data found.")
        return

    print(f"Fetched {len(metar_df)} METAR records.")
    
    # Plot METAR
    plot_metar_data(metar_df, target_station, output_path='output/test_notebook_metar.png')
    
    ranking = {}
    for grib_path, meta in grib_metadata.items():
        model_name = os.path.basename(grib_path)
        print(f"Comparing {model_name}...")
        
        try:
            ds = load_grib_dataset(grib_path)
            
            # Inject location
            lat = metar_df.attrs.get('lat')
            lon = metar_df.attrs.get('lon')
            
            if lat is None:
                # Find in list
                if not split.empty:
                    lat = split.iloc[0]['lat']
                    lon = split.iloc[0]['lon']
            
            # Ensure attributes set for compare logic
            metar_df.attrs['lat'] = lat
            metar_df.attrs['lon'] = lon
            
            res = compare_model_to_observations(ds, metar_df)
            if not res.empty:
                full = calculate_errors(metar_df, res)
                metrics = compute_metrics(full)
                ranking[model_name] = metrics
                print(f"RMSE: {metrics['vector_rmse']:.2f}")
                
                plot_wind_comparison(full, model_name, output_path=f"output/test_notebook_compare_{model_name}.png")
            else:
                print("No overlap.")
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    if ranking:
        print("Ranking calculated.")
        plot_model_ranking(ranking, output_path='output/test_notebook_ranking.png')

if __name__ == "__main__":
    try:
        os.makedirs("output", exist_ok=True)
        test_workflow()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
