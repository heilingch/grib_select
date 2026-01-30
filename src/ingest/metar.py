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

# --- Global Station List ---
# In a real app we'd ship a CSV or SQLite DB.
# For this demo, let's lazy load from IEM if not cached.
STATION_CACHE_FILE = os.path.join(CACHE_DIR, "stations.csv")

def get_station_list() -> pd.DataFrame:
    """
    Returns a DataFrame of global stations with 'id', 'lat', 'lon', 'name'.
    """
    if os.path.exists(STATION_CACHE_FILE):
        try:
            return pd.read_csv(STATION_CACHE_FILE)
        except:
            pass
            
    # Download from IEM
    # https://mesonet.agron.iastate.edu/sites/networks.php
    # They have a GEOJSON or CSV service. 
    # Let's try to fetch a simplified list. 
    # Actually, easy way: fetch networks for a region? No, we want global ideally.
    # The 'metar' library has a station list but it's often old.
    
    # Let's try fetching a known station list or use a small hardcoded one + dynamic.
    # PROACTIVE: Let's fetch the official IEM station list for ASOS/METAR.
    # http://mesonet.agron.iastate.edu/geojson/network/AIRPORTS.geojson
    # or CSV.
    
    url = "http://mesonet.agron.iastate.edu/sites/networks.php?network=__ALL__&format=csv"
    # This might be huge. 
    
    # Fallback: Just return empty and rely on user knowing the ID, 
    # OR define a few common ones for testing if fetch fails.
    
    # Let's simple use a minimal list for the demo if we can't fetch.
    # Actually, the user asked for "automatically search airports".
    # I will implement a fetch from a static URL that is reliable.
    # https://raw.githubusercontent.com/datasets/airport-codes/master/data/airport-codes.csv is one option but might not match ICAO.
    # http://ourairports.com/data/airports.csv
    
    try:
        # OurAirports is a good source
        url = "https://davidmegginson.github.io/ourairports-data/airports.csv"
        print("Downloading station list (once)...")
        df = pd.read_csv(url)
        # Filter for large airports to reduce noise? type == 'large_airport' or 'medium_airport'
        df = df[df['type'].isin(['large_airport', 'medium_airport'])]
        # Ensure we have ICAO
        df = df.dropna(subset=['ident'])
        
        # Normalize
        out_df = pd.DataFrame({
            'id': df['ident'], # ICAO
            'name': df['name'],
            'lat': df['latitude_deg'],
            'lon': df['longitude_deg']
        })
        
        out_df.to_csv(STATION_CACHE_FILE, index=False)
        return out_df
    except Exception as e:
        print(f"Failed to download station list: {e}")
        # Return fallback
        return pd.DataFrame([
            {'id': 'LDSP', 'name': 'Split', 'lat': 43.53, 'lon': 16.29},
            {'id': 'EGLL', 'name': 'Heathrow', 'lat': 51.47, 'lon': -0.46},
            {'id': 'KJFK', 'name': 'JFK', 'lat': 40.64, 'lon': -73.78},
        ])

def find_nearby_stations(lat_min, lat_max, lon_min, lon_max) -> pd.DataFrame:
    """
    Finds stations within the bounding box.
    """
    df = get_station_list()
    if df.empty:
        return df
        
    mask = (df['lat'] >= lat_min) & (df['lat'] <= lat_max) & \
           (df['lon'] >= lon_min) & (df['lon'] <= lon_max)
           
    return df[mask]
