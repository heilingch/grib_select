import xarray as xr
import pandas as pd
import numpy as np
import os

def load_grib_dataset(filepath: str) -> xr.Dataset:
    """
    Loads a GRIB file into an xarray Dataset.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"GRIB file not found: {filepath}")
        
    # filter_by_keys={'typeOfLevel': 'surface'} is common for weather models 
    # to avoid mixing multiple vertical levels which can confuse xarray
    # However, for general boat use, we usually care about 10m wind and MSL pressure.
    # We might need to load multiple messages if they are in different 'typeOfLevel'.
    
    try:
        if filepath.endswith('.nc'):
             ds = xr.open_dataset(filepath)
        else:
            # Try loading with default backend (cfgrib)
            ds = xr.open_dataset(filepath, engine='cfgrib')
        return ds
    except Exception as e:
        # Sometimes GRIBs have mixed levels, we might need to try distinct backend_kwargs
        # For now, let's propagate the error but in a real tool we'd try to be more robust
        raise ValueError(f"Error loading GRIB file {filepath}: {e}")

def extract_point_data(ds: xr.Dataset, lat: float, lon: float, time: pd.Timestamp = None) -> dict:
    """
    Extracts wind and pressure data for a specific location and optional time.
    Interpolaes spatially.
    """
    # GRIB data is often 0-360 longitude, while user might provide -180 to 180.
    # Normalize longitude to GRIB format if needed.
    # Assuming GRIB might be 0..360 or -180..180
    
    ds_lon_min = ds.longitude.min().item()
    ds_lon_max = ds.longitude.max().item()
    
    target_lon = lon
    if ds_lon_min >= 0 and target_lon < 0:
         target_lon += 360
         
    # Nearest neighbor or linear interpolation
    try:
        # Select nearest point or interpolate
        # We use .sel(method='nearest') for speed and simplicity for now, 
        # but .interp() is better for "precise weather routing".
        
        subset = ds.interp(latitude=lat, longitude=target_lon, method='linear')
        
        if time:
            # Handle Timezone Mismatch
            # Xarray/NetCDF time is often naive. If ds time is naive, convert input time to naive (UTC).
            ds_time_index = ds.indexes.get('time')
            if ds_time_index is None:
                ds_time_index = ds.indexes.get('valid_time')
            
            if ds_time_index is not None:
                is_ds_tz_aware = hasattr(ds_time_index, 'tz') and ds_time_index.tz is not None
                is_input_tz_aware = hasattr(time, 'tzinfo') and time.tzinfo is not None
                
                if is_ds_tz_aware and not is_input_tz_aware:
                    time = time.replace(tzinfo=None).tz_localize('UTC') # Assume UTC if naive
                elif not is_ds_tz_aware and is_input_tz_aware:
                    time = time.tz_convert(None) # Strip TZ to match naive dataset
            
            # Interpolate in time if needed, or select nearest
            subset = subset.interp(time=time, method='linear')
            
        # Extract variables. Variable names vary by model (ECMWF vs GFS).
        # Common names: 
        # u10, v10 (10 metre U/V wind component)
        # msl (Mean sea level pressure)
        # tp (Total precipitation)
        
        data = {}
        
        # Wind components
        if 'u10' in subset and 'v10' in subset:
            u = subset['u10'].values.item()
            v = subset['v10'].values.item()
            data['wind_speed'] = np.sqrt(u**2 + v**2) * 1.94384 # m/s to knots
            data['wind_dir'] = (270 - np.arctan2(v, u) * 180 / np.pi) % 360
            
        # Pressure
        if 'msl' in subset:
            data['pressure'] = subset['msl'].values.item() / 100.0 # Pa to hPa
            
        return data
        
    except Exception as e:
        print(f"Extraction error: {e}")
        return None
