import sys
import os
import pandas as pd
import numpy as np
import xarray as xr

sys.path.append(os.path.abspath('src'))
from workflow import GribSelectorSession

def test_session():
    print("Testing GribSelectorSession...")
    
    # 1. Setup Data Paths
    local_csv = 'tests/data/local_log.csv'
    model_nc = 'tests/data/model_A.nc'
    
    if not os.path.exists(local_csv):
        print("Test data missing. Re-running creation...")
        # (Assuming integration_test.py logic is available or just fail)
        # We can reuse the integration test creation logic or mock it.
        # Let's simple check existence.
        print("Please run integration_test.py first to generate data.")
        sys.exit(1)

    # 2. Run Session
    session = GribSelectorSession()
    session.load_local_data(local_csv)
    session.add_grib(model_nc)
    
    session.run_comparison()
    
    # 3. Verify Results
    ranking = session.get_ranking()
    print("Ranking:\n", ranking)
    
    if ranking.empty:
        print("FAIL: No ranking generated.")
        sys.exit(1)
        
    rmse = ranking.iloc[0]['Vector RMSE (kts)']
    if rmse > 0:
        print(f"PASS: RMSE calculated ({rmse:.2f})")
    else:
        print("FAIL: RMSE is 0 or invalid.")
        sys.exit(1)

if __name__ == "__main__":
    test_session()
