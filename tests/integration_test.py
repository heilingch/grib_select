import pandas as pd
import xarray as xr
import numpy as np
import os
import sys
import subprocess

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

def create_dummy_data():
    os.makedirs('tests/data', exist_ok=True)
    
    # 1. Local Data
    dates = pd.date_range(start='2024-01-01 12:00', periods=24, freq='1h')
    local_df = pd.DataFrame({
        'timestamp': dates.astype(np.int64) // 10**9,
        'lat': np.linspace(40, 41, 24),
        'lon': np.linspace(10, 11, 24),
        'wind_speed': np.random.normal(15, 2, 24),
        'wind_dir': np.random.normal(180, 10, 24) % 360,
        'pressure': np.random.normal(1013, 2, 24)
    })
    local_csv = 'tests/data/local_log.csv'
    local_df.to_csv(local_csv, index=False)
    print(f"Created {local_csv}")
    
    # 2. Model Data (NetCDF acting as GRIB)
    # Create a grid covering the boat path
    lats = np.linspace(39, 42, 10)
    lons = np.linspace(9, 12, 10)
    times = pd.date_range(start='2024-01-01 10:00', periods=30, freq='1h')
    
    # Create variables
    u10 = np.random.normal(0, 5, (30, 10, 10)) # Time, Lat, Lon
    v10 = np.random.normal(15, 5, (30, 10, 10)) # Southerly wind approx
    msl = np.random.normal(101300, 200, (30, 10, 10))
    
    ds = xr.Dataset(
        data_vars={
            'u10': (('time', 'latitude', 'longitude'), u10),
            'v10': (('time', 'latitude', 'longitude'), v10),
            'msl': (('time', 'latitude', 'longitude'), msl),
        },
        coords={
            'time': times,
            'latitude': lats,
            'longitude': lons
        }
    )
    
    model_nc = 'tests/data/model_A.nc'
    ds.to_netcdf(model_nc)
    print(f"Created {model_nc}")
    
    return local_csv, model_nc

def run_pipeline(local_csv, model_nc):
    cmd = [
        sys.executable, 'src/main.py',
        '--local', local_csv,
        '--gribs', model_nc,
        '--output', 'tests/output',
        '--hours', '24'
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        print("Pipeline failed!")
        sys.exit(1)
        
    # Check outputs
    expected_plot = 'tests/output/model_A.nc_vs_Local.png'
    if os.path.exists(expected_plot):
        print(f"Success! Plot generated: {expected_plot}")
    else:
        print(f"Error: Plot not found at {expected_plot}")
        sys.exit(1)

if __name__ == "__main__":
    local, model = create_dummy_data()
    run_pipeline(local, model)
