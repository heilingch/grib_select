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
        # Note: typeOfLevel can be 'meanSea' or 'meanSeaLevel' depending on GRIB version
        for msl_level in ['meanSea', 'meanSeaLevel']:
            try:
                ds_msl = xr.open_dataset(
                    filepath, 
                    engine='cfgrib', 
                    backend_kwargs={'filter_by_keys': {'typeOfLevel': msl_level}}
                )
                # Rename variants to standard 'msl'
                rename_map = {}
                if 'prmsl' in ds_msl: rename_map['prmsl'] = 'msl'
                if 'sp' in ds_msl: rename_map['sp'] = 'msl'  # Surface pressure fallback
                
                if rename_map:
                    ds_msl = ds_msl.rename(rename_map)
                    
                if 'msl' in ds_msl:
                    datasets.append(ds_msl[['msl']])
                    break  # Found it, stop trying other level names
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

def extract_point_data(ds: xr.Dataset, lat, lon, time=None):
    """
    Extracts wind and pressure data.
    Supports both scalar inputs (single point) and vectorized inputs (arrays).
    """
    try:
        # --- 1. Longitude Normalization ---
        ds_lon_min = ds.longitude.min().item()
        
        # Handle scalar vs array input
        if np.ndim(lat) == 0:
            target_lon = lon
            if ds_lon_min >= 0 and target_lon < 0:
                target_lon += 360
        else:
            target_lon = np.array(lon)
            if ds_lon_min >= 0:
                 target_lon[target_lon < 0] += 360
                 
        # --- 2. Interpolation ---
        # If time is provided, we need to handle it first or concurrently
        # For batch processing (many times, one location OR many locations, one time)
        # We assume for now: lat/lon are scalar (one station) and time is Series (many times)
        # OR lat/lon are Series (trajectory) and time is Series
        
        # Simple Case: Scalar Lat/Lon, Scalar Time (Legacy)
        if np.ndim(lat) == 0 and (time is None or np.ndim(time) == 0):
             # Use existing logic for scalar
             subset = ds.interp(latitude=lat, longitude=target_lon, method='linear')
             if time is not None:
                  if 'valid_time' in subset.coords: # Swap if needed
                       if 'step' in subset.dims and 'valid_time' not in subset.dims:
                            if 'valid_time' in subset.coords: subset = subset.swap_dims({'step': 'valid_time'})
                  
                  # Handle Time Zone
                  # ... (Simplified for brevity, assuming UTC)
                  if 'valid_time' in subset.dims:
                       time_val = pd.Timestamp(time).tz_convert(None) if pd.Timestamp(time).tzinfo else time
                       subset = subset.interp(valid_time=time_val, method='linear')
                  elif 'time' in subset.dims:
                       subset = subset.interp(time=time, method='linear')
             
             data = {}
             u = subset.get('u10', subset.get('u', subset.get('10u')))
             v = subset.get('v10', subset.get('v', subset.get('10v')))
             p = subset.get('msl', subset.get('prmsl', subset.get('sp')))
             
             if u is not None and v is not None:
                  u_val = u.values.item()
                  v_val = v.values.item()
                  data['wind_speed'] = np.sqrt(u_val**2 + v_val**2) * 1.94384
                  data['wind_dir'] = (270 - np.arctan2(v_val, u_val) * 180 / np.pi) % 360
             if p is not None:
                  data['pressure'] = p.values.item() / 100.0
             return data

        # Vectorized Case: Time Series at a Point
        # lat/lon scalar, time is array/index
        if np.ndim(lat) == 0 and time is not None and len(time) > 1:
             # Spatially interpolate first (reduce to point)
             point_ds = ds.interp(latitude=lat, longitude=target_lon, method='linear')
             
             # Align time coordinates
             target_times = pd.to_datetime(time)
             if target_times.tz is not None:
                  target_times = target_times.tz_convert(None)
             
             # Handle dimension swapping
             if 'step' in point_ds.dims and 'valid_time' not in point_ds.dims and 'valid_time' in point_ds.coords:
                  point_ds = point_ds.swap_dims({'step': 'valid_time'})
             
             time_dim = 'valid_time' if 'valid_time' in point_ds.dims else 'time'
             
             # Select nearest times or interp
             # Interp is better for accuracy
             ts_ds = point_ds.interp({time_dim: target_times}, method='linear')
             
             # Extract Data
             df = pd.DataFrame(index=time)
             
             u = ts_ds.get('u10', ts_ds.get('u', ts_ds.get('10u')))
             v = ts_ds.get('v10', ts_ds.get('v', ts_ds.get('10v')))
             p = ts_ds.get('msl', ts_ds.get('prmsl', ts_ds.get('sp')))
             
             if u is not None and v is not None:
                  # Calculate wind speed/dir from vector components
                  ws = np.sqrt(u.values**2 + v.values**2) * 1.94384
                  wd = (270 - np.arctan2(v.values, u.values) * 180 / np.pi) % 360
                  df['wind_speed'] = ws
                  df['wind_dir'] = wd
             
             if p is not None:
                  df['pressure'] = p.values / 100.0
                  
             return df

    except Exception as e:
        print(f"Extraction error: {e}")
        return None
