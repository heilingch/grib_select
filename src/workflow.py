import pandas as pd
import xarray as xr
import os
import matplotlib.pyplot as plt
from ipywidgets import interact, Dropdown, Output, VBox
from IPython.display import display, clear_output

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

    def list_nearby_stations(self):
        """
        Returns a DataFrame of stations within the coverage of loaded models.
        """
        if not self.models:
            print("No models loaded. Cannot determine coverage area.")
            return pd.DataFrame()
            
        # Determine global bounds
        lat_min, lat_max = 90, -90
        lon_min, lon_max = 180, -180
        
        has_bounds = False
        for name, ds in self.models.items():
            try:
                # Use dataset coordinates
                ds_lat_min = float(ds.latitude.min())
                ds_lat_max = float(ds.latitude.max())
                ds_lon_min = float(ds.longitude.min())
                ds_lon_max = float(ds.longitude.max())
                
                lat_min = min(lat_min, ds_lat_min)
                lat_max = max(lat_max, ds_lat_max) # Fixed: was max(lat_min, ...) which is wrong
                lon_min = min(lon_min, ds_lon_min)
                lon_max = max(lon_max, ds_lon_max)
                has_bounds = True
            except Exception as e:
                print(f"Could not determine bounds for {name}: {e}")
        
        if not has_bounds:
            return pd.DataFrame()
            
        print(f"Searching stations in Lat [{lat_min:.2f}, {lat_max:.2f}], Lon [{lon_min:.2f}, {lon_max:.2f}]...")
        return find_nearby_stations(lat_min, lat_max, lon_min, lon_max)

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
        
        # Initialize comparisons dict structure
        for obs_name in self.observations:
            self.comparisons[obs_name] = {}

        for model_name, ds in self.models.items():
            model_metrics_list = []
            for obs_name, obs_df in self.observations.items():
                try:
                    res = compare_model_to_observations(ds, obs_df)
                    if not res.empty:
                        full_df = calculate_errors(obs_df, res)
                        
                        # Store in nested dict
                        self.comparisons[obs_name][model_name] = full_df
                        
                        m = compute_metrics(full_df)
                        model_metrics_list.append(m)
                        print(f"  Processed {model_name} vs {obs_name} (RMSE: {m['vector_rmse']:.2f} kts)")
                except Exception as e:
                    print(f"  Error comparing {model_name} vs {obs_name}: {e}")
            
            if model_metrics_list:
                # Average metrics for this model across all observations
                avg_rmse = sum(x['vector_rmse'] for x in model_metrics_list) / len(model_metrics_list)
                model_metric = {'vector_rmse': avg_rmse}
                
                # Average pressure RMSE if available
                pressure_rmses = [x['pressure_rmse'] for x in model_metrics_list if 'pressure_rmse' in x]
                if pressure_rmses:
                    model_metric['pressure_rmse'] = sum(pressure_rmses) / len(pressure_rmses)
                    
                self.metrics[model_name] = model_metric

        print("Comparison complete.")

    def plot_interactive(self):
        """Displays an interactive widget to explore results."""
        if not self.comparisons:
            print("No results to plot. Run comparison first.")
            return

        # Keys are Observation names now
        obs_names = list(self.comparisons.keys())
        dropdown = Dropdown(options=obs_names, description='Observation:', layout={'width': '300px'})
        out = Output()

        def on_change(change):
            if change['type'] == 'change' and change['name'] == 'value':
                with out:
                    clear_output(wait=True)
                    obs_name = change['new']
                    model_data = self.comparisons.get(obs_name, {})
                    
                    if not model_data:
                        print("No model data for this observation.")
                        return
                        
                    obs_df = self.observations[obs_name]
                    plot_multi_model_comparison(obs_df, model_data, obs_name)
                    plt.show()

        dropdown.observe(on_change)
        
        # Initial Plot
        with out:
            k = obs_names[0]
            model_data = self.comparisons.get(k, {})
            obs_df = self.observations[k]
            plot_multi_model_comparison(obs_df, model_data, k)
            plt.show()
            
        return VBox([dropdown, out])

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
        if not self.metrics:
            print("No metrics available. Run comparison first.")
            return pd.DataFrame()
        
        data = []
        for m, v in self.metrics.items():
            rmse = v['vector_rmse']
            
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
                'Model': m, 
                'Wind RMSE (kts)': round(rmse, 2),
                'Quality': quality
            }
            
            if 'pressure_rmse' in v:
                row['Pressure RMSE (hPa)'] = round(v['pressure_rmse'], 2)
                
            data.append(row)
        
        df = pd.DataFrame(data).sort_values('Wind RMSE (kts)')
        
        # Print guidance
        print("\n📊 RMSE Interpretation Guide:")
        print("   Wind: <3=Excellent, 3-5=Good, 5-8=Fair, 8-12=Poor, >12=Unreliable")
        print("   Pressure: <1=Excellent, 1-2=Good, >2=Poor\n")
        
        return df
