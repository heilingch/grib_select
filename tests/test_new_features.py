import sys
import os
import shutil

# Ensure we're running from project root
if os.getcwd().endswith('tests'):
    os.chdir('..')

sys.path.append('src')

from workflow import GribSelectorSession

def test_features():
    print("--- 1. initializing Session ---")
    session = GribSelectorSession()
    
    # Test Data
    grib_file = 'tests/data/gfs_0_25.2026-01-30T19-06-17Z.grb2'
    
    print("\n--- 2. Adding GRIB ---")
    session.add_grib(grib_file)
    
    print("\n--- 3. Testing report_grib ---")
    session.report_grib()
    
    print("\n--- 4. Testing list_nearby_stations (Default: Range Only) ---")
    stations = session.list_nearby_stations()
    if not stations.empty:
        print(f"Found {len(stations)} stations within bounds.")
        print(stations[['id', 'name', 'type']].head())
    
    print("\n--- 4b. Testing list_nearby_stations (grib_range_only=False) ---")
    # This might return a huge list, so just check count
    all_stations = session.list_nearby_stations(grib_range_only=False)
    print(f"Total global stations: {len(all_stations)}")
    
    print("\n--- 5. Fetching METAR for Split (LDSP) ---")
    # This should trigger the new 'alti' fallback logic if mslp is missing
    session.load_metar('LDSP', hours=24)
    
    print("\n--- 6. Running Comparison (should show tqdm bar) ---")
    session.run_comparison()
    
    print("\n--- 7. Testing Ranking ---")
    ranking = session.get_ranking()
    try:
        from IPython.display import display
        display(ranking)
    except:
        print(ranking)
    
    print("\n--- 8. Testing copy of plot functions (Dry Run) ---")
    
    # Test Auto-model selection
    print("Testing auto-model selection...")
    session.report_meteogram(station_name='LDSP') # Should pick the only model
    
    # Test Arbitrary Lat/Lon
    print("Testing arbitrary Lat/Lon meteogram...")
    session.report_meteogram(lat=42.0, lon=16.0) # Middle of Adriatic
    
    print("Meteogram generated (check for errors above).")

if __name__ == "__main__":
    try:
        test_features()
        print("\n✅ Verification Complete!")
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
