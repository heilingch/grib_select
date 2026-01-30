import pandas as pd
import numpy as np
import xarray as xr
from ingest.grib import extract_point_data

def calculate_errors(observed_df: pd.DataFrame, model_data: pd.DataFrame):
    """
    Calculates errors between observed and model, returns a DataFrame with error metrics.
    Aligns model data to observed data index using reindex.
    """
    # Reindex model data to match observed data timestamps
    # This handles cases where indices don't perfectly align
    model_aligned = model_data.reindex(observed_df.index, method='nearest', tolerance=pd.Timedelta('30min'))
    
    comparisons = observed_df.copy()
    
    # Wind
    if 'wind_speed' in model_aligned.columns:
        comparisons['model_wind_speed'] = model_aligned['wind_speed']
    else:
        comparisons['model_wind_speed'] = np.nan
        
    if 'wind_dir' in model_aligned.columns:
        comparisons['model_wind_dir'] = model_aligned['wind_dir']
    else:
        comparisons['model_wind_dir'] = np.nan
    
    # Pressure - check both dataframes
    if 'pressure' in observed_df.columns and 'pressure' in model_aligned.columns:
        comparisons['model_pressure'] = model_aligned['pressure']
        # Only calculate error where both have valid values
        comparisons['pressure_error'] = comparisons['model_pressure'] - comparisons['pressure']
    
    # Calculate scalar errors (handles NaN gracefully)
    comparisons['ws_error'] = comparisons['model_wind_speed'] - comparisons['wind_speed']
    
    # Calculate Vector Error for wind
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
    
    skipped = 0
    for time, row in observations.iterrows():
        lat = row[lat_col] if is_trajectory else observations.attrs.get('lat')
        lon = row[lon_col] if is_trajectory else observations.attrs.get('lon')
        
        if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
            skipped += 1
            continue
        
        # Convert time to naive UTC if needed for consistency
        query_time = time
        if hasattr(query_time, 'tzinfo') and query_time.tzinfo is not None:
            query_time = query_time.tz_convert('UTC').tz_localize(None)
        
        datum = extract_point_data(model_ds, lat, lon, query_time)
        if datum and ('wind_speed' in datum or 'pressure' in datum):
            datum['time'] = time
            model_results.append(datum)
        else:
            skipped += 1
            
    if skipped > 0:
        print(f"    (Skipped {skipped} points due to missing data or invalid location)")
            
    if not model_results:
        print("    Warning: No valid model data extracted for any observation point.")
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
