import sys
import os
import shutil
import glob
from datetime import datetime

# Ensure we're running from project root
if os.getcwd().endswith('tests'):
    os.chdir('..')

sys.path.append('src')

from workflow import GribSelectorSession

def test_autosave():
    print("--- 1. Testing Session Init (Check for Timestamp) ---")
    session = GribSelectorSession()
    
    # Test Data setup
    grib_file = 'tests/data/gfs_0_25.2026-01-30T19-06-17Z.grb2'
    if not os.path.exists(grib_file):
        print("Test GRIB not found.")
        return

    session.add_grib(grib_file)
    session.load_metar('LDSP', hours=24) # Ensure we have data
    
    print("\n--- 2. Testing report_meteogram Explicit Save ---")
    # Clean output dir first to be sure
    if os.path.exists('output'):
        for f in glob.glob('output/*.png'):
            os.remove(f)
            
    # Should NOT save by default
    session.report_meteogram(station_name='LDSP')
    files = glob.glob('output/*meteogram*.png')
    if not files:
        print("✅ Correct: Meteogram NOT saved by default.")
    else:
        print(f"❌ Error: Meteogram saved when it shouldn't be: {files}")

    # Should save with save=True
    session.report_meteogram(station_name='LDSP', save=True)
    files = glob.glob('output/*meteogram*.png')
    if files:
        print(f"✅ Meteogram saved with save=True: {files[0]}")
    else:
        print("❌ Meteogram NOT saved with save=True.")
        
    print("\n--- 3. Testing save_plots() Batch Save ---")
    
    # Mock comparisons data to enable plotting
    session.run_comparison()
    
    # interactive plot should NOT save
    try:
        session.plot_interactive()
        files = glob.glob('output/*comparison*.png')
        if not files:
             print("✅ Correct: Interactive plot NOT auto-saved.")
        else:
             print(f"❌ Error: Interactive plot auto-saved: {files}")
    except:
        pass

    # Batch save
    session.save_plots()
    files = glob.glob('output/*comparison*.png')
    if files:
        print(f"✅ Batch save successful: Found {len(files)} comparisons.")
    else:
        print("❌ Batch save failed.")

if __name__ == "__main__":
    test_autosave()
