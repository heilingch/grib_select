# GRIB Select Analysis Tool - User Manual

This tool allows sailors and meteorologists to compare multiple weather models (GRIB files) against real-world observations (METAR stations or local boat data) to identify the most accurate model for a specific region and time.

## 🚀 Quick Start Workflow

```python
from workflow import GribSelectorSession

# 1. Initialize Session
session = GribSelectorSession()
# Output: 01.02.2026 - 20:30:00

# 2. Load Data
session.add_grib('data/gfs_0_25.grb2')
session.add_grib('data/ecmwf_0_1.grb2')
session.load_metar('LDSP', hours=48)  # Load last 48h of data for Split

# 3. Explore
session.report_grib()                 # View model coverage
session.list_nearby_stations()        # Find airports in model area

# 4. Compare & Visualize
session.run_comparison()              # Calculate errors (RMSE)
session.plot_interactive()            # View interactive plots
session.get_ranking()                 # See which model won

# 5. Save Results
session.save_plots()                  # Save all comparisons to ./output/
```

---

## 📚 Function Reference

### 1. Initialization
#### `session = GribSelectorSession()`
Initializes a new analysis session.
- **Output**: Prints the current timestamp (e.g., `01.02.2026 - 20:14:35`).

### 2. Loading Data

#### `session.add_grib(filepath)`
Loads a GRIB2 file into the session.
- **filepath** (str): Path to the `.grb2` file.
- *Note*: You can add multiple GRIB files to compare them.

#### `session.load_metar(station_id, hours=48)`
Fetches historical weather data for an airport/weather station.
- **station_id** (str): ICAO code (e.g., `'LDSP'` for Split, `'EGLL'` for Heathrow). Case-insensitive.
- **hours** (int): Number of hours of history to fetch (default: 48).

#### `session.load_local_data(filepath)`
Loads local weather data from a CSV file (e.g., from boat instruments).
- **filepath** (str): Path to CSV. expected columns: `time`, `lat`, `lon`, `wind_speed`, `wind_dir`, `pressure`.

### 3. Exploration & Reporting

#### `session.report_grib()`
Prints a summary table of all loaded GRIB files, including:
- Time range (Start / End)
- Geographic coverage (Lat / Lon bounds)

#### `session.list_nearby_stations(grib_range_only=True)`
Finds weather stations (airports) relevant to your data.
- **grib_range_only** (bool): 
    - `True` (default): Lists only stations inside the bounding box of your loaded GRIBs.
    - `False`: Lists all global stations from the cache (useful if you haven't loaded GRIBs yet).
- **Output**: Returns a list with ID, Name, and Type (e.g., `medium_airport`).

#### `session.report_meteogram(model_name=None, station_name=None, lat=None, lon=None, save=False)`
Generates a detailed meteogram (Wind Speed, Direction Barbs, Pressure) for a specific location.

**Usage Options:**
1. **By Station**: `session.report_meteogram(station_name='LDSP')`
2. **By Coordinates**: `session.report_meteogram(lat=42.5, lon=16.2)`
3. **Save to File**: `session.report_meteogram(..., save=True)` (Saves to `./output/`)

*Note*: If multiple models are loaded, you must specify `model_name` (e.g., `'gfs_0_25.grb2'`).

### 4. Analysis

#### `session.run_comparison()`
Runs the core analysis engine.
1. Extracts model data at every observation point (Time/Lat/Lon).
2. Calculates errors (RMSE) for Vector Wind and Pressure.
3. Prints progress with a progress bar.

#### `session.plot_interactive()`
Displays a widget to browse comparison plots for different stations.
- **Plots Shown**:
    - **Wind Speed**: Model vs Observation lines.
    - **Wind Direction**: Scatter plot (Models vs Observation).
    - **Pressure**: Trend lines.
- *Note*: This function **updates the display** in the notebook but does not save files.

#### `session.get_ranking()`
Returns a scorecard ranking models by accuracy (Wind RMSE).
- **Quality Ratings**:
    - ⭐⭐⭐ **Excellent** (< 3 kts error)
    - ⭐⭐ **Good** (3-5 kts)
    - ⭐ **Fair** (5-8 kts)
    - ⚠️ **Poor** (8-12 kts)
    - ❌ **Unreliable** (> 12 kts)

### 5. Saving Results

#### `session.save_plots(output_dir="output")`
Batch saves all comparison plots to disk.
- **Filenames**: `YYYYMMDD_HHMMSS_comparison_STATION.png`
- **Output**: Creates the directory if it doesn't exist.
