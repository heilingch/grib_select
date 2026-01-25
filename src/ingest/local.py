import pandas as pd
import numpy as np

def read_local_data(filepath: str) -> pd.DataFrame:
    """
    Reads local instrument data from a CSV file.
    
    Expected format:
    - timestamp: UNIX timestamp (int or float) or ISO string
    - lat: Latitude (float)
    - lon: Longitude (float)
    - wind_speed: Wind speed in knots (float)
    - wind_dir: Wind direction in degrees (float, 0-360)
    - pressure: Air pressure in hPa/mbar (float) - Optional
    
    Returns:
    - pd.DataFrame with a datetime index.
    """
    try:
        df = pd.read_csv(filepath)
        
        # Standardize timestamp column
        if 'timestamp' in df.columns:
            # Check if it looks like a unix timestamp (large numbers)
            if pd.api.types.is_numeric_dtype(df['timestamp']):
                df['time'] = pd.to_datetime(df['timestamp'], unit='s')
            else:
                df['time'] = pd.to_datetime(df['timestamp'])
        else:
            raise ValueError("CSV must contain a 'timestamp' column.")
            
        df = df.set_index('time').sort_index()
        
        # Required columns validation
        required_cols = ['lat', 'lon', 'wind_speed', 'wind_dir']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
            
        return df
        
    except Exception as e:
        raise ValueError(f"Failed to read local data file: {e}")
