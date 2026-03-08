import pandas as pd
import xarray as xr
import numpy as np
import os
import matplotlib.pyplot as plt
from ipywidgets import interact, Dropdown, Output, VBox, HBox
from IPython.display import display, clear_output
import warnings
from datetime import datetime

# Suppress warnings from cfgrib/xarray
warnings.filterwarnings("ignore", category=FutureWarning, message=".*decode_timedelta.*")

from ingest.local import read_local_data
from ingest.grib import load_grib_dataset
from ingest.metar import fetch_metar, find_nearby_stations
from analysis.compare import compare_model_to_observations, calculate_errors, compute_metrics
from vis.plotting import plot_multi_model_comparison, plot_model_ranking

class GribSelectorSession:
    def __init__(self):
        self.observations = {}
        self.models = {} # path -> dataset
        self.comparisons = {} # obs_name -> { model_name -> df }
        self.metrics = {} # "Model" -> list of metrics
        
        # Print formatted timestamp as requested
        now_str = datetime.now().strftime("%d.%m.%Y - %H:%M:%S")
        print(f"{now_str}")
        print("Session initialized.")

    def load_local_data(self, filepath):
        """Loads local boat data from CSV."""
        if not os.path.exists(filepath):
            print(f"Error: File not found {filepath}")
            return
        
        try:
            df = read_local_data(filepath)
            self.observations['Local_Boat'] = df
            print(f"Loaded {len(df)} local data points.")
        except Exception as e:
            print(f"Failed to load local data: {e}")

    def load_metar(self, station_id, hours=48):
        """Fetches METAR data."""
        try:
            print(f"Fetching METAR for {station_id}...")
            df = fetch_metar(station_id, hours=hours)
            if not df.empty:
                # Ensure dummy lat/lon if missing (for demo robustness)
                if 'lat' not in df.attrs: 
                     df.attrs['lat'] = 0.0
                     df.attrs['lon'] = 0.0
                self.observations[f'METAR_{station_id}'] = df
                print(f"Loaded {len(df)} METAR records.")
            else:
                print(f"No data found for {station_id}")
        except Exception as e:
            print(f"Error fetching METAR: {e}")

    def add_grib(self, filepath):
        """Adds a GRIB/NetCDF model file to the session."""
        if not os.path.exists(filepath):
            print(f"Error: File not found {filepath}")
            return

        try:
            ds = load_grib_dataset(filepath)
            name = os.path.basename(filepath)
            self.models[name] = ds
            print(f"Added model: {name}")
        except Exception as e:
            print(f"Failed to load GRIB {filepath}: {e}")

    def report_grib(self):
        """Prints metadata for all loaded GRIB files."""
        if not self.models:
            print("No GRIB files loaded.")
            return

        print(f"{'File':<40} {'Start':<20} {'End':<20} {'Lat Range':<15} {'Lon Range':<15}")
        print("-" * 115)
        
        # Since we only store the dataset, we might not have the path handy if not stored.
        # But we use the key as the name.
        
        for name, ds in self.models.items():
            # Calculate metadata from dataset directly since we might not have path
            try:
                # Re-use logic from get_grib_metadata but on dataset
                lat_min = float(ds.latitude.min())
                lat_max = float(ds.latitude.max())
                lon_min = float(ds.longitude.min())
                lon_max = float(ds.longitude.max())
                
                times = []
                if 'time' in ds.coords and ds.time.size > 1: times = ds.time.values
                elif 'valid_time' in ds.coords: times = ds.valid_time.values
                elif 'step' in ds.coords and 'time' in ds.coords:
                     times = pd.to_datetime(ds.time.values) + pd.to_timedelta(ds.step.values)
                
                if len(times) > 0:
                     times = np.sort(times)
                     start = str(pd.to_datetime(times.min()))
                     end = str(pd.to_datetime(times.max()))
                else:
                     start = "N/A"
                     end = "N/A"
                     
                print(f"{name[:38]:<40} {start[:19]:<20} {end[:19]:<20} [{lat_min:.1f}, {lat_max:.1f}]   [{lon_min:.1f}, {lon_max:.1f}]")
            except Exception as e:
                print(f"{name:<40} Error extracting metadata: {e}")

    def report_meteogram(self, model_name: str = None, station_name: str = None, lat: float = None, lon: float = None, save: bool = False):
        """
        Plots a meteogram for a specific model at a location.
        
        Args:
            model_name (str): Name of the model (file basename). If None and only one model loaded, uses it.
            station_name (str): ICAO code of station (e.g. 'LDSP')
            lat (float): Latitude (if station_name not provided)
            lon (float): Longitude (if station_name not provided)
            save (bool): If True, saves the plot to ./output/ folder.
        """
        # Auto-select model if unique
        if model_name is None:
            if len(self.models) == 1:
                model_name = next(iter(self.models.keys()))
                print(f"Using model: {model_name}")
            else:
                print("Please specify 'model_name'. Available available models:")
                for m in self.models.keys(): print(f" - {m}")
                return

        if model_name not in self.models:
            print(f"Model {model_name} not found.")
            return

        ds = self.models[model_name]
        
        # Determine location
        if station_name:
            station_name = station_name.upper()
            obs_key = station_name
            # Try finding with METAR_ prefix if not found directly
            if station_name not in self.observations and f"METAR_{station_name}" in self.observations:
                obs_key = f"METAR_{station_name}"
            
            if obs_key not in self.observations:
                print(f"Station {station_name} not found in loaded observations. Please load_metar('{station_name}') first or provide lat/lon.")
                return
            obs = self.observations[obs_key]
            target_lat = obs.attrs.get('lat')
            target_lon = obs.attrs.get('lon')
            title = f"Meteogram: {model_name} @ {station_name}"
        elif lat is not None and lon is not None:
            target_lat = lat
            target_lon = lon
            title = f"Meteogram: {model_name} @ ({lat:.2f}, {lon:.2f})"
        else:
            print("Must specify either station_name or lat/lon.")
            return
            
        # Check time range of model
        # We want the whole time series available in the model
        times = None
        if 'valid_time' in ds.coords: times = ds.valid_time.values
        elif 'time' in ds.coords: times = ds.time.values
        
        if times is None:
             print("Could not determine time range.")
             return
             
        # Extract entire time series using vectorized extraction
        from ingest.grib import extract_point_data
        print(f"Extracting time series for {len(times)} time points...")
        df = extract_point_data(ds, target_lat, target_lon, times)
        
        if df is not None and not df.empty:
            from vis.plotting import plot_meteogram
            
            output_path = None
            if save:
                output_dir = "output"
                os.makedirs(output_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Sanitize filename components
                safe_model = model_name.replace(" ", "_").replace("/", "_")
                safe_loc = station_name if station_name else f"{target_lat:.2f}_{target_lon:.2f}"
                safe_loc = safe_loc.replace(" ", "_")
                
                filename = f"{timestamp}_meteogram_{safe_model}_{safe_loc}.png"
                output_path = os.path.join(output_dir, filename)
            
            plot_meteogram(df, title=title, output_path=output_path)
        else:
            print("Failed to extract data for meteogram.")

    
    def list_nearby_stations(self, grib_range_only=True):
        """
        Returns a DataFrame of stations.
        
        Args:
            grib_range_only (bool): If True, restricts search to the bounding box 
                                    of the loaded GRIB models.
        """
        lat_min, lat_max, lon_min, lon_max = None, None, None, None
        
        if grib_range_only:
            # Determine bounds from models
            try:
                 # Union of all model bounds
                 for ds in self.models.values():
                     lats = ds.latitude.values
                     lons = ds.longitude.values
                     
                     curr_lat_min, curr_lat_max = lats.min(), lats.max()
                     curr_lon_min, curr_lon_max = lons.min(), lons.max()
                     
                     if lat_min is None: 
                         lat_min, lat_max = curr_lat_min, curr_lat_max
                         lon_min, lon_max = curr_lon_min, curr_lon_max
                     else:
                         lat_min = min(lat_min, curr_lat_min)
                         lat_max = max(lat_max, curr_lat_max)
                         lon_min = min(lon_min, curr_lon_min)
                         lon_max = max(lon_max, curr_lon_max)
            except:
                 pass
                 
            if lat_min is None:
                 print("Could not determine model bounds. Add a model first or use grib_range_only=False.")
                 return pd.DataFrame()
                 
            # Add small buffer to bounds (e.g. 0.5 deg)
            lat_min -= 0.5; lat_max += 0.5
            lon_min -= 0.5; lon_max += 0.5
            
            print(f"Searching stations in Model Bounds (buffered): Lat [{lat_min:.2f}, {lat_max:.2f}], Lon [{lon_min:.2f}, {lon_max:.2f}]...")
            df = find_nearby_stations(lat_min, lat_max, lon_min, lon_max)
        else:
            # Global or very wide range?
            # actually find_nearby_stations expects bounds.
            # If False, we probably want *all* stations or prompt user?
            # Let's revert to a very wide box or just return the whole cached list
            from ingest.metar import get_station_list
            print("Returning all cached stations...")
            df = get_station_list()

        if df.empty:
            print("No stations found.")
            return df
            
        return df

    def run_comparison(self):
        """Runs the comparison engine for all loaded models vs observations."""
        self.comparisons = {} # Reset
        self.metrics = {}
        
        if not self.observations:
            print("No observations loaded. Please load local data or METAR first.")
            return

        if not self.models:
            print("No models loaded. Please add GRIB files.")
            return

        print("Running comparison...")
        from tqdm.notebook import tqdm
        
        # Initialize comparisons dict structure
        for obs_name in self.observations:
            self.comparisons[obs_name] = {}

        # Create a list of tasks to iterate over for the progress bar
        tasks = []
        for model_name, ds in self.models.items():
            for obs_name, obs_df in self.observations.items():
                tasks.append((model_name, ds, obs_name, obs_df))
        
        print(f"Comparing {len(self.models)} models vs {len(self.observations)} stations...")
        
        # Using tqdm for progress tracking
        pbar = tqdm(total=len(tasks), desc="Processing Comparisons")
        
        # Revert to nested loop but with tqdm on the outer or combined
        # Let's simple tqdm the outer loop (models) and inner (obs)
        
        for model_name, ds in self.models.items():
            model_metrics_list = []
            
            # Inner loop with tqdm? Or just one big bar? 
            # Users prefer one big bar usually.
            # But we need to aggregate metrics per model.
            
            for obs_name, obs_df in self.observations.items():
                pbar.set_description(f"Comp: {model_name} vs {obs_name}")
                try:
                    res = pd.DataFrame() # Default
                    
                    # Check extraction method
                    lat_col = 'lat' if 'lat' in obs_df.columns else None
                    lon_col = 'lon' if 'lon' in obs_df.columns else None
                    
                    is_trajectory = False
                    if lat_col and lon_col:
                        # Only treat as trajectory if coordinates actually change (moving vessel)
                        # or if we are unsure. For METAR, they are usually constant.
                        if obs_df[lat_col].nunique() > 1 or obs_df[lon_col].nunique() > 1:
                             is_trajectory = True
                    
                    if is_trajectory:
                        res = compare_model_to_observations(ds, obs_df)
                    else:
                        # Static station extraction
                        lat = obs_df.attrs.get('lat')
                        lon = obs_df.attrs.get('lon')
                        
                        if lat is not None and lon is not None:
                            from ingest.grib import extract_point_data
                            model_df = extract_point_data(ds, lat, lon, obs_df.index)
                            if model_df is not None and not model_df.empty:
                                res = model_df
                            
                    if not res.empty:
                        full_df = calculate_errors(obs_df, res)
                        self.comparisons[obs_name][model_name] = full_df
                        m = compute_metrics(full_df)
                        model_metrics_list.append(m)
                    pbar.update(1) # Update progress bar for each observation comparison
                except Exception as e:
                    # Log but continue
                    pbar.write(f"  Error comparing {model_name} vs {obs_name}: {e}")
                    pbar.update(1) # Still update progress bar even on error
            
            # Aggregate metrics for this model
            if model_metrics_list:
                avg_rmse = sum(x['vector_rmse'] for x in model_metrics_list) / len(model_metrics_list)
                model_metric = {'vector_rmse': avg_rmse}
                pressure_rmses = [x['pressure_rmse'] for x in model_metrics_list if 'pressure_rmse' in x]
                if pressure_rmses:
                    model_metric['pressure_rmse'] = sum(pressure_rmses) / len(pressure_rmses)
                self.metrics[model_name] = model_metric
        
        pbar.close() # Close the progress bar
        print("Comparison complete.")

    def plot_interactive(self):
        """Displays an interactive widget to explore results."""
        if not self.comparisons:
            print("No results to plot. Run comparison first.")
            return
            
        print("Note: To save all plots to 'output/' directory, run: session.save_plots()")

        # Keys are Observation names now
        obs_names = list(self.comparisons.keys())
        obs_dropdown = Dropdown(options=obs_names, description='Observation:', layout={'width': '300px'})
        
        time_options = ['Auto (GRIB Range)', 'All Data', 'Past 12h + Forecast', 'Past 24h + Forecast', 'Past 48h + Forecast']
        time_dropdown = Dropdown(options=time_options, value='Auto (GRIB Range)', description='Timeframe:', layout={'width': '300px'})
        
        out = Output()

        def update_plot():
            with out:
                clear_output(wait=True)
                obs_name = obs_dropdown.value
                time_mode = time_dropdown.value
                model_data = self.comparisons.get(obs_name, {})
                
                if not model_data:
                    print("No model data for this observation.")
                    return
                    
                obs_df = self.observations[obs_name]
                
                start_time = None
                end_time = None
                
                if time_mode == 'Auto (GRIB Range)':
                    all_times = pd.Index([])
                    for df in model_data.values():
                        all_times = all_times.union(df.index)
                    if not all_times.empty:
                        start_time = all_times.min() - pd.Timedelta(hours=6)
                        end_time = all_times.max() + pd.Timedelta(hours=6)
                elif time_mode != 'All Data':
                    # Parse hours from e.g. 'Past 24h + Forecast'
                    hours = int(time_mode.split(' ')[1].replace('h', ''))
                    
                    # Anchor "now" to the start of the model data (or latest observation)
                    model_times = pd.Index([])
                    for df in model_data.values():
                        model_times = model_times.union(df.index)
                        
                    if not model_times.empty:
                        base_time = model_times.min()
                        end_time = model_times.max() + pd.Timedelta(hours=6)
                    elif not obs_df.empty:
                        base_time = obs_df.index.max()
                        end_time = None
                    else:
                        base_time = pd.Timestamp.now()
                        end_time = None
                        
                    start_time = base_time - pd.Timedelta(hours=hours)

                plot_obs_df = obs_df
                plot_model_data = model_data
                
                plot_multi_model_comparison(plot_obs_df, plot_model_data, obs_name, start_time=start_time, end_time=end_time)
                plt.show()

        def on_change(change):
            if change['type'] == 'change' and change['name'] == 'value':
                update_plot()

        obs_dropdown.observe(on_change)
        time_dropdown.observe(on_change)
        
        # Initial Plot
        update_plot()
            
        return VBox([HBox([obs_dropdown, time_dropdown]), out])

    def save_plots(self, output_dir="output"):
        """
        Saves all comparison plots to the specified directory.
        Generated filenames include timestamp and station name.
        """
        if not self.comparisons:
            print("No comparisons to save. Run run_comparison() first.")
            return
            
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"Saving {len(self.comparisons)} plots to '{output_dir}/'...")
        
        count = 0
        from vis.plotting import plot_multi_model_comparison
        
        for obs_name, model_data in self.comparisons.items():
            try:
                obs_df = self.observations[obs_name]
                safe_obs = obs_name.replace(" ", "_").replace("/", "_")
                filename = f"{timestamp}_comparison_{safe_obs}.png"
                output_path = os.path.join(output_dir, filename)
                
                # output_path triggers savefig instead of show
                plot_multi_model_comparison(obs_df, model_data, obs_name, output_path=output_path)
                print(f"  Saved: {filename}")
                count += 1
            except Exception as e:
                print(f"  Failed to save {obs_name}: {e}")
                
        print(f"Successfully saved {count} plots.")

    def get_ranking(self):
        """
        Returns a pandas DataFrame of model rankings with interpretation guide.
        
        RMSE Interpretation (Wind Vector):
        - < 3 kts: Excellent - Model is highly accurate for tactical decisions
        - 3-5 kts: Good - Reliable for route planning, expect minor variations
        - 5-8 kts: Fair - Use with caution, consider averaging with other models
        - 8-12 kts: Poor - Significant errors, verify with other sources
        - > 12 kts: Unreliable - Do not use for navigation decisions
        
        Pressure RMSE:
        - < 1 hPa: Excellent
        - 1-2 hPa: Good
        - > 2 hPa: Poor
        """
        if not self.metrics and not self.comparisons:
            print("No metrics available. Run comparison first.")
            return pd.DataFrame()
        
        data = []
        
        # We iterate through comparisons to get ALL pairs, not just the model average
        for obs_name, model_dict in self.comparisons.items():
            for model_name, df in model_dict.items():
                m = compute_metrics(df)
                rmse = m['vector_rmse']
            
                # Determine quality rating
                if rmse < 3:
                    quality = "⭐⭐⭐ Excellent"
                elif rmse < 5:
                    quality = "⭐⭐ Good"
                elif rmse < 8:
                    quality = "⭐ Fair"
                elif rmse < 12:
                    quality = "⚠️ Poor"
                else:
                    quality = "❌ Unreliable"
                    
                row = {
                    'Model': model_name,
                    'Station': obs_name, 
                    'Wind RMSE (kts)': round(rmse, 2),
                    'Quality': quality
                }
                
                if 'pressure_rmse' in m:
                    row['Pressure RMSE (hPa)'] = round(m['pressure_rmse'], 2)
                    
                data.append(row)
        
        df = pd.DataFrame(data).sort_values('Wind RMSE (kts)')
        
        # Print guidance
        print("\n📊 RMSE Interpretation Guide:")
        print("   Wind: <3=Excellent, 3-5=Good, 5-8=Fair, 8-12=Poor, >12=Unreliable")
        print("   Pressure: <1=Excellent, 1-2=Good, >2=Poor\n")
        
        return df
