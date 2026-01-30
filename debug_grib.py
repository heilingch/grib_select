import xarray as xr
import sys
import os

filepath = 'tests/data/gfs_0_25.2026-01-30T19-06-17Z.grb2'

print(f"Inspecting {filepath}...")

try:
    # Try opening as list of datasets
    dss = xr.open_dataset(filepath, engine='cfgrib', backend_kwargs={'indexpath': ''})
    print("Opened as single dataset (unexpected given errors)")
    print(dss)
except Exception as e:
    print(f"Single load failed: {e}")
    try:
        # Try returning list
        # Note: xr.open_dataset doesn't return list, need open_datasets (plural) doesn't exist in top level standardly for cfgrib?
        # cfgrib.open_datasets is the way if using library directly, or we can iterate.
        import cfgrib
        dss = cfgrib.open_datasets(filepath)
        print(f"Returned {len(dss)} datasets.")
        for i, ds in enumerate(dss):
            print(f"\n--- Dataset {i} ---")
            print(ds)
            print("Vars:", list(ds.data_vars))
            print("Coords:", list(ds.coords))
    except Exception as e2:
        print(f"List load failed: {e2}")
