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
        url = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
        # IEM API: day2 is exclusive, so extend to tomorrow to get today's data
        query_end = end_time + timedelta(days=1)
        params = {
            'station': station_id,
            'data': ['sknt', 'drct', 'mslp', 'alti', 'lat', 'lon'],
            'year1': start_time.year,
            'month1': start_time.month,
            'day1': start_time.day,
            'year2': query_end.year,
            'month2': query_end.month,
            'day2': query_end.day,
            'tz': 'Etc/UTC',
            'format': 'onlycomma',
            'latlon': 'yes',
            'missing': 'null'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        # Parse CSV
        from io import StringIO
        csv_data = StringIO(response.text)
        new_df = pd.read_csv(csv_data)
        
        # Rename columns to match our internal schema
        new_df = new_df.rename(columns={
            'valid': 'time',
            'sknt': 'wind_speed',
            'drct': 'wind_dir',
            'mslp': 'pressure'
        })
        
        # Use 'alti' (altimeter in inches Hg) as fallback for pressure
        # Convert: 1 inHg = 33.8639 hPa
        if 'alti' in new_df.columns:
            # Fill missing pressure with converted altimeter
            alti_hpa = new_df['alti'] * 33.8639
            new_df['pressure'] = new_df['pressure'].fillna(alti_hpa)
        
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
        
        # ALWAYS set lat/lon attrs from the data columns (they're preserved in the DataFrame)
        if 'lat' in combined.columns and not combined['lat'].isna().all():
            combined.attrs['lat'] = combined['lat'].dropna().iloc[0]
        if 'lon' in combined.columns and not combined['lon'].isna().all():
            combined.attrs['lon'] = combined['lon'].dropna().iloc[0]
        
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
        # Use pandas directly which handles the download
        df = pd.read_csv(url)
        
        # Filter: Include small airports as they are often useful for sailors (coastal strips)
        # But filter out closed, heliports, seaplane base (maybe keep seaplane?)
        # Let's keep small, medium, large.
        df = df[df['type'].isin(['large_airport', 'medium_airport', 'small_airport'])]
        
        # Ensure we have ICAO code (ident)
        df = df.dropna(subset=['ident'])
        
        # Create a clean name: Municipality (Name) or just Name
        def format_name(row):
            name = row['name']
            muni = row['municipality'] if pd.notna(row['municipality']) else ""
            
            # Clean up common airport suffixes for display
            name = name.replace(" Airport", "").replace(" International", "")
            
            if muni and muni not in name:
                return f"{muni} ({name})"
            return name

        df['display_name'] = df.apply(format_name, axis=1)
        
        # Normalize
        out_df = pd.DataFrame({
            'id': df['ident'], # ICAO
            'name': df['display_name'],
            'lat': df['latitude_deg'],
            'lon': df['longitude_deg'],
            'type': df['type'] # Useful for filtering/highlighting
        })
        
        out_df.to_csv(STATION_CACHE_FILE, index=False)
        return out_df
    except Exception as e:
        print(f"Failed to download station list: {e}")
        # Return fallback
        return pd.DataFrame([
            {'id': 'LDSP', 'name': 'Split (Kastela)', 'lat': 43.53, 'lon': 16.30, 'type': 'medium_airport'},
            {'id': 'LDZD', 'name': 'Zadar (Zemunik)', 'lat': 44.10, 'lon': 15.34, 'type': 'medium_airport'},
            {'id': 'LDDU', 'name': 'Dubrovnik (Cilipi)', 'lat': 42.56, 'lon': 18.26, 'type': 'medium_airport'},
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
