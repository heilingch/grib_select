import pandas as pd
import numpy as np
import xarray as xr
from ingest.grib import extract_point_data

def calculate_errors(observed_df: pd.DataFrame, model_data: pd.DataFrame):
    """
    Calculates errors between observed and model, returns a DataFrame with error metrics.
    """
    # Merge on time (requires them to be aligned or reindexed)
    # model_data should be same index as observed_df
    
    comparisons = observed_df.copy()
    comparisons['model_wind_speed'] = model_data['wind_speed']
    comparisons['model_wind_dir'] = model_data['wind_dir']
    
    if 'pressure' in observed_df.columns and 'pressure' in model_data.columns:
        comparisons['model_pressure'] = model_data['pressure']
        comparisons['pressure_error'] = comparisons['model_pressure'] - comparisons['pressure']
    
    # Calculate scalar errors
    comparisons['ws_error'] = comparisons['model_wind_speed'] - comparisons['wind_speed'] # Bias
    
    # Calculate Vector Error for wind
    # Convert to U/V
    obs_u = -comparisons['wind_speed'] * np.sin(np.radians(comparisons['wind_dir']))
    obs_v = -comparisons['wind_speed'] * np.cos(np.radians(comparisons['wind_dir']))
    
    mod_u = -comparisons['model_wind_speed'] * np.sin(np.radians(comparisons['model_wind_dir']))
    mod_v = -comparisons['model_wind_speed'] * np.cos(np.radians(comparisons['model_wind_dir']))
    
    comparisons['u_error'] = mod_u - obs_u
    comparisons['v_error'] = mod_v - obs_v
    comparisons['vector_rmse'] = np.sqrt(comparisons['u_error']**2 + comparisons['v_error']**2)
    
    return comparisons

def compare_model_to_observations(model_ds: xr.Dataset, observations: pd.DataFrame, lat_col='lat', lon_col='lon'):
    """
    Iterates through observations and extracts corresponding model data.
    This can be slow for many points; for efficiency, we might want to vectorize 
    but xarray interp is decent.
    """
    model_results = []
    
    # If observations are stationary (Airport), lat/lon is constant.
    # If moving (Boat), lat/lon changes per row.
    
    # Check if lat/lon are columns
    is_trajectory = lat_col in observations.columns and lon_col in observations.columns
    
    # Pre-calculate model data for each observation timestamp
    # Optimization: If observations are regularly spaced, we can interp 1D in time first?
    # No, boat moves in space.
    
    for time, row in observations.iterrows():
        lat = row[lat_col] if is_trajectory else observations.attrs.get('lat')
        lon = row[lon_col] if is_trajectory else observations.attrs.get('lon')
        
        # Extract from GRIB
        # Note: Time in GRIB is often 'valid_time' or 'step' + 'time'. 
        # xarray with cfgrib usually parses this into 'time' or 'valid_time'.
        
        # We try to extract at the specific time
        # This extract_point_data might do spatial interp. 
        # For time, it's better to pass the timestamp.
        
        # Optimization: Batch extraction is better. 
        # But let's use the simple loop for clarity first as datasets aren't huge (usually < 1000 observations).
        
        datum = extract_point_data(model_ds, lat, lon, time)
        if datum:
            datum['time'] = time
            model_results.append(datum)
            
    if not model_results:
        return pd.DataFrame()
        
    model_df = pd.DataFrame(model_results).set_index('time')
    return model_df

def compute_metrics(comparisons: pd.DataFrame):
    """
    Aggregates errors into summary metrics (RMS, Bias, etc)
    """
    metrics = {}
    metrics['ws_bias'] = comparisons['ws_error'].mean()
    metrics['ws_rmse'] = np.sqrt((comparisons['ws_error']**2).mean())
    metrics['vector_rmse'] = comparisons['vector_rmse'].mean()
    
    if 'pressure_error' in comparisons.columns:
        metrics['pressure_rmse'] = np.sqrt((comparisons['pressure_error']**2).mean())
        
    return metrics
