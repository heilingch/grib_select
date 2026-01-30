import pandas as pd
import xarray as xr
import os
import matplotlib.pyplot as plt
from ipywidgets import interact, Dropdown, Output, VBox
from IPython.display import display, clear_output

from ingest.local import read_local_data
from ingest.grib import load_grib_dataset
from ingest.metar import fetch_metar
from analysis.compare import compare_model_to_observations, calculate_errors, compute_metrics
from vis.plotting import plot_wind_comparison, plot_model_ranking

class GribSelectorSession:
    def __init__(self):
        self.observations = {}
        self.models = {} # path -> dataset
        self.comparisons = {} # "Model vs Obs" -> df
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

    def run_comparison(self):
        """Runs the comparison engine for all loaded models vs observations."""
        self.comparisons = {}
        self.metrics = {}
        
        if not self.observations:
            print("No observations loaded. Please load local data or METAR first.")
            return

        if not self.models:
            print("No models loaded. Please add GRIB files.")
            return

        print("Running comparison...")
        for model_name, ds in self.models.items():
            model_metrics_list = []
            for obs_name, obs_df in self.observations.items():
                try:
                    res = compare_model_to_observations(ds, obs_df)
                    if not res.empty:
                        full_df = calculate_errors(obs_df, res)
                        key = f"{model_name} vs {obs_name}"
                        self.comparisons[key] = full_df
                        
                        m = compute_metrics(full_df)
                        model_metrics_list.append(m)
                        print(f"  Processed {key} (RMSE: {m['vector_rmse']:.2f} kts)")
                except Exception as e:
                    print(f"  Error comparing {model_name} vs {obs_name}: {e}")
            
            if model_metrics_list:
                # Average metrics for this model
                avg_rmse = sum(x['vector_rmse'] for x in model_metrics_list) / len(model_metrics_list)
                self.metrics[model_name] = {'vector_rmse': avg_rmse}

        print("Comparison complete.")

    def plot_interactive(self):
        """Displays an interactive widget to explore results."""
        if not self.comparisons:
            print("No results to plot. Run comparison first.")
            return

        keys = list(self.comparisons.keys())
        dropdown = Dropdown(options=keys, description='View:')
        out = Output()

        def on_change(change):
            if change['type'] == 'change' and change['name'] == 'value':
                with out:
                    clear_output(wait=True)
                    key = change['new']
                    df = self.comparisons[key]
                    model_name = key.split(' vs ')[0]
                    plot_wind_comparison(df, model_name)
                    plt.show()

        dropdown.observe(on_change)
        
        # Initial Plot
        with out:
            k = keys[0]
            plot_wind_comparison(self.comparisons[k], k.split(' vs ')[0])
            plt.show()
            
        return VBox([dropdown, out])

    def get_ranking(self):
        """Returns a pandas DataFrame of model rankings."""
        if not self.metrics:
            return pd.DataFrame()
        
        data = []
        for m, v in self.metrics.items():
            data.append({'Model': m, 'Vector RMSE (kts)': v['vector_rmse']})
            
        return pd.DataFrame(data).sort_values('Vector RMSE (kts)')
