import requests
import os
import json
import logging
from datetime import datetime, timedelta
try:
    from metar import Metar
except ImportError:
    Metar = None
    logging.warning("python-metar not found. Raw METAR parsing will be disabled.")
import pandas as pd

CACHE_DIR = os.path.expanduser("~/.grib_select/cache/metar")
os.makedirs(CACHE_DIR, exist_ok=True)

def fetch_metar(station_id: str, hours: int = 48) -> list:
    """
    Fetches METAR history for a station. 
    Tries to retrieve from various free sources or falls back to cache.
    
    Since historical METARs are harder to get from the standard 'current' NOAA URL,
    we might rely on a service that provides history, or just 'current' if that's all we have 
    and rely on the user running this tool periodically to build history.
    
    However, for this standard 'last 48h' request, the Ogimet or Iowa State Mesonet archives are good.
    Iowa State (Mesonet) offers a great API for past data.
    """
    station_id = station_id.upper()
    
    # Try fetching from Iowa State Mesonet (IEM) which is reliable for history
    # Format: https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=LDSP&data=all&year1=...
    # Actually, they provide a CSV download.
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    cache_file = os.path.join(CACHE_DIR, f"{station_id}.json")
    
    data = []
    
    # Check cache first for "offline first" policy?
    # Actually, offline first means: try network, if fail, read cache. 
    # OR: Read cache, then update from network.
    
    # Let's load existing cache
    cached_df = pd.DataFrame()
    if os.path.exists(cache_file):
        try:
            cached_df = pd.read_json(cache_file, orient='records')
            if not cached_df.empty:
                cached_df['time'] = pd.to_datetime(cached_df['time'])
                cached_df = cached_df.set_index('time').sort_index()
        except Exception as e:
            logging.warning(f"Failed to read cache for {station_id}: {e}")

    try:
        # Construct IEM URL
        # https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=LDSP&data=tmpf&data=dwpf&data=sknt&data=drct&data=mslp&year1=2024&month1=1...
        # Easier: Generic CSV endpoint
        
        url = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
        params = {
            'station': station_id,
            'data': ['sknt', 'drct', 'mslp', 'lat', 'lon'], # Added lat, lon
            'year1': start_time.year,
            'month1': start_time.month,
            'day1': start_time.day,
            'year2': end_time.year,
            'month2': end_time.month,
            'day2': end_time.day,
            'tz': 'Etc/UTC',
            'format': 'onlycomma',
            'latlon': 'yes', # Ensure included
            'missing': 'null' # Use null for missing
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        # Parse CSV
        from io import StringIO
        # station,valid,lon,lat,sknt,drct,mslp
        csv_data = StringIO(response.text)
        new_df = pd.read_csv(csv_data)
        
        # Rename columns to match our internal schema
        new_df = new_df.rename(columns={
            'valid': 'time',
            'sknt': 'wind_speed',
            'drct': 'wind_dir',
            'mslp': 'pressure'
        })
        
        # Store lat/lon as attributes or keeping them as columns is fine if stationary.
        # But for stationary METAR, good to have it in attrs for easy access.
        if not new_df.empty:
            new_df.attrs['lat'] = new_df['lat'].iloc[0]
            new_df.attrs['lon'] = new_df['lon'].iloc[0]
            
        new_df['time'] = pd.to_datetime(new_df['time'])
        new_df = new_df.set_index('time')
        
        # Merge with cache
        if not cached_df.empty:
            combined = pd.concat([cached_df, new_df])
            combined = combined[~combined.index.duplicated(keep='last')]
            combined = combined.sort_index()
        else:
            combined = new_df.sort_index()
            
        # Save back to cache
        combined.reset_index().to_json(cache_file, orient='records', date_format='iso')
        
        return combined

    except Exception as e:
        print(f"Network error fetching METAR for {station_id}: {e}")
        # If offline, use cache
        if not cached_df.empty:
             print("Using cached data.")
             return cached_df
        else:
            print("No cached data available.")
            return pd.DataFrame()

def parse_metar_string(raw_metar: str):
    """
    Helper if we need to parse raw METAR strings directly.
    """
    try:
        obs = Metar.Metar(raw_metar)
        return {
            'time': obs.time,
            'wind_speed': obs.wind_speed.value('KT') if obs.wind_speed else None,
            'wind_dir': obs.wind_dir.value() if obs.wind_dir else None,
            'pressure': obs.press.value('MB') if obs.press else None
        }
    except Exception as e:
        return None
