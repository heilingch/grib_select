import xarray as xr
import pandas as pd
import numpy as np
import os



def load_grib_dataset(filepath: str) -> xr.Dataset:
    """
    Loads a GRIB file into an xarray Dataset.
    Handles mixed-layer GRIBs by loading 10m wind and MSL pressure separately and merging.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"GRIB file not found: {filepath}")
        
    try:
        if filepath.endswith('.nc'):
             return xr.open_dataset(filepath)
             
        # GRIB loading strategy:
        # 1. Attempt using specific filters ("backend_kwargs") avoids "mixed level" errors.
        #    We specifically want 10m Wind and MSL Pressure.
        
        datasets = []
        
        # --- 1. Wind (10m height) ---
        try:
            ds_wind = xr.open_dataset(
                filepath, 
                engine='cfgrib', 
                backend_kwargs={'filter_by_keys': {'typeOfLevel': 'heightAboveGround', 'level': 10}}
            )
            # Rename common variants to standard names
            rename_map = {}
            if 'u' in ds_wind: rename_map['u'] = 'u10'
            if 'v' in ds_wind: rename_map['v'] = 'v10'
            if '10u' in ds_wind: rename_map['10u'] = 'u10'
            if '10v' in ds_wind: rename_map['10v'] = 'v10'
            
            if rename_map:
                ds_wind = ds_wind.rename(rename_map)
                
            if 'u10' in ds_wind and 'v10' in ds_wind:
                datasets.append(ds_wind[['u10', 'v10']])
            else:
                print("Warning: 10m Wind (u10/v10) not found in GRIB 10m level.")
        except Exception as e:
            # print(f"Debug: Failed to load 10m wind: {e}")
            pass
            
        # --- 2. Pressure (Mean Sea Level) ---
        try:
            ds_msl = xr.open_dataset(
                filepath, 
                engine='cfgrib', 
                backend_kwargs={'filter_by_keys': {'typeOfLevel': 'meanSeaLevel'}}
            )
            # Rename variants
            rename_map = {}
            if 'prmsl' in ds_msl: rename_map['prmsl'] = 'msl'
            # GFS sometimes puts it in 'surface' with paramId, but 'meanSeaLevel' is standard GRIB2
            
            if rename_map:
                ds_msl = ds_msl.rename(rename_map)
                
            if 'msl' in ds_msl:
                datasets.append(ds_msl[['msl']])
        except Exception:
            pass
            
        if not datasets:
            # Final Fallback: Try generic load (might fail with DatasetBuildError but worth a shot if filters failed)
            try:
                ds = xr.open_dataset(filepath, engine='cfgrib')
                return ds
            except Exception:
                raise ValueError("Could not extract Wind (10m) or Pressure (MSL) from GRIB. Check if the file contains these variables.")
            
        # Merge components
        # compat='override' is risky if grids don't match, but usually they do for same model run.
        combined = xr.merge(datasets, compat='override')
        return combined
            
    except Exception as e:
        raise ValueError(f"Error loading GRIB file {filepath}: {e}")

def get_grib_metadata(filepath: str) -> dict:
    """
    Extracts metadata from a GRIB file: Bounds and Time range.
    """
    try:
        ds = load_grib_dataset(filepath)
        
        # Spatial Bounds
        lat_min = float(ds.latitude.min())
        lat_max = float(ds.latitude.max())
        lon_min = float(ds.longitude.min())
        lon_max = float(ds.longitude.max())
        
        # Time Range
        times = []
        if 'time' in ds.coords and ds.time.size > 1:
            times = ds.time.values
        elif 'valid_time' in ds.coords:
            times = ds.valid_time.values
        elif 'step' in ds.coords:
             # Construct from time + step
             # Usually 'time' is scalar ref time
             if 'time' in ds.coords:
                 ref = pd.to_datetime(ds.time.values)
                 steps = pd.to_timedelta(ds.step.values)
                 times = ref + steps
             
        if len(times) > 0:
            times = np.sort(times)
            start = pd.to_datetime(times[0])
            end = pd.to_datetime(times[-1])
        else:
            start = None
            end = None
            
        return {
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lon_min': lon_min,
            'lon_max': lon_max,
            'start_time': start,
            'end_time': end,
            'file': os.path.basename(filepath)
        }
    except Exception as e:
        print(f"Metadata error {filepath}: {e}")
        return {}

def extract_point_data(ds: xr.Dataset, lat: float, lon: float, time: pd.Timestamp = None) -> dict:
    """
    Extracts wind and pressure data for a specific location and optional time.
    Interpolaes spatially.
    """
    ds_lon_min = ds.longitude.min().item()
    target_lon = lon
    if ds_lon_min >= 0 and target_lon < 0:
         target_lon += 360
         
    try:
        subset = ds.interp(latitude=lat, longitude=target_lon, method='linear')
        
        if time:
            # Time Interpolation Logic
            # Goal: Get data at 'time'. 'ds' might have 'time', 'valid_time', or 'step'.
            
            # Check for valid_time
            if 'valid_time' in subset.coords:
                # Often valid_time is a coordinate dependent on step
                # We need to swap dims if step is the dim
                if 'step' in subset.dims and 'valid_time' not in subset.dims:
                     if 'valid_time' in subset.coords:
                         subset = subset.swap_dims({'step': 'valid_time'})
                
                if 'valid_time' in subset.dims:
                     # Ensure TZ awareness matches
                     vt_index = subset.indexes['valid_time']
                     is_tz = hasattr(vt_index, 'tz') and vt_index.tz is not None
                     if is_tz and time.tzinfo is None:
                         time = time.tz_localize('UTC')
                     elif not is_tz and time.tzinfo is not None:
                         time = time.tz_convert(None)
                         
                     subset = subset.interp(valid_time=time, method='linear')
                     
            elif 'time' in subset.dims:
                 subset = subset.interp(time=time, method='linear')
                 
            # If we failed to interpolate time (e.g. still has step dim), we might return array
            
        
        data = {}
        
        # Helper to safely get scalar
        def get_val(var):
            if var not in subset: return None
            val = subset[var].values
            if val.ndim == 0: return val.item()
            # If array, perhaps took nearest or time interp failed
            # If size 1, return item
            if val.size == 1: return val.item()
            # If array, return first? Or raise?
            return val.flatten()[0] # Fallback
            
        u = get_val('u10')
        v = get_val('v10')
        
        if u is not None and v is not None:
             data['wind_speed'] = np.sqrt(u**2 + v**2) * 1.94384
             data['wind_dir'] = (270 - np.arctan2(v, u) * 180 / np.pi) % 360
             
        p = get_val('msl')
        if p is not None:
            data['pressure'] = p / 100.0
            
        return data
        
    except Exception as e:
        print(f"Extraction error: {e}")
        return None
