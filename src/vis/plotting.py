import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

def apply_style(ax):
    """Applies common style: Gridlines, etc."""
    ax.grid(True, color='grey', linestyle='--', alpha=0.8)

    display(fig)
    plt.close()

def plot_multi_model_comparison(obs_df: pd.DataFrame, model_data_dict: dict, obs_name: str, output_path: str = None, start_time=None, end_time=None):
    """
    Plots Observed data vs Multiple Models.
    model_data_dict: { 'ModelName': comparison_df, ... }
    comparison_df should have 'model_wind_speed', 'model_wind_dir', etc.
    """
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    
    # --- 1. Wind Speed ---
    # Plot Observation
    ax1.plot(obs_df.index, obs_df['wind_speed'], label=f'Observed ({obs_name})', color='black', linewidth=3, zorder=10, alpha=0.7)
    
    # Plot Models
    if len(model_data_dict) > 0:
        colors = plt.cm.tab10(np.linspace(0, 1, max(3, len(model_data_dict))))
    else:
        colors = []
    
    lines = []
    labels = []
    
    for (model_name, df), color in zip(model_data_dict.items(), colors):
        if 'model_wind_speed' in df.columns:
            l, = ax1.plot(df.index, df['model_wind_speed'], label=model_name, linestyle='--', color=color, linewidth=2)
            lines.append(l)
            labels.append(model_name)
            
    ax1.set_ylabel('Wind Speed (knots)')
    ax1.set_title(f"Wind Comparison: {obs_name}")
    ax1.grid(True, linestyle='--', alpha=0.6)
    
    # Unified Legend
    # ax1.legend(loc='upper right')
    
    # --- 2. Wind Direction ---
    ax2.scatter(obs_df.index, obs_df['wind_dir'], label='Observed', color='black', s=40, zorder=10, alpha=0.6)
    
    for (model_name, df), color in zip(model_data_dict.items(), colors):
        if 'model_wind_dir' in df.columns:
            ax2.scatter(df.index, df['model_wind_dir'], label=model_name, marker='x', s=30, color=color)
            
    ax2.set_ylabel('Wind Direction (deg)')
    ax2.set_ylim(0, 360)
    ax2.grid(True, linestyle='--', alpha=0.6)
    
    # --- 3. Pressure ---
    has_pressure = 'pressure' in obs_df.columns
    if has_pressure:
        ax3.plot(obs_df.index, obs_df['pressure'], label='Observed', color='black', linewidth=3, zorder=10, alpha=0.7)
        
    for (model_name, df), color in zip(model_data_dict.items(), colors):
        if 'model_pressure' in df.columns:
            ax3.plot(df.index, df['model_pressure'], label=model_name, linestyle='--', color=color, linewidth=2)
            
    ax3.set_ylabel('Pressure (hPa)')
    ax3.grid(True, linestyle='--', alpha=0.6)
    
    # Legend on Top Plot (Wind Speed) - Best placement with box
    # ax1 has all labels (Observed + Models) so we can just use ax1.legend()
    ax1.legend(loc='best', frameon=True, fancybox=True, framealpha=0.8)

    
    # --- Zoom / Limits ---
    # Union of indices to find absolute max limits if no bounds are specified
    all_indices = [obs_df.index] + [df.index for df in model_data_dict.values()]
    if all_indices:
        combined_index = pd.Index([])
        for idx in all_indices:
            combined_index = combined_index.union(idx)
            
        if not combined_index.empty:
            lim_start = combined_index.min()
            lim_end = combined_index.max()
            
            # Clamp limits if user requested a timeframe
            if start_time is not None:
                lim_start = start_time
            if end_time is not None:
                lim_end = end_time
                
            ax3.set_xlim(lim_start, lim_end)

    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path)
    else:
        plt.show()
    plt.close()

def plot_model_ranking(metrics_dict: dict, output_path: str = None):
    """
    Plots a bar chart of RMSE for different models.
    metrics_dict: { 'ModelA': {'vector_rmse': 5.2, ...}, 'ModelB': ... }
    """
    models = list(metrics_dict.keys())
    rmses = [m['vector_rmse'] for m in metrics_dict.values()]
    
    plt.figure(figsize=(8, 6))
    if len(models) > 0:
        ax = sns.barplot(x=models, y=rmses, hue=models, legend=False)
    plt.title("Model Accuracy (Vector RMSE)")
    plt.ylabel("Wind Vector Error (knots)")
    apply_style(plt.gca())
    
    if output_path:
        plt.savefig(output_path)
    plt.close()

def plot_meteogram(df: pd.DataFrame, title: str = None, output_path: str = None):
    """
    Plots a multi-panel meteogram for a single model/location.
    df: must have 'wind_speed', 'wind_dir', 'pressure' (msl) columns.
    """
    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    if title:
        fig.suptitle(title, fontsize=16)
        
    times = df.index
    
    # 1. Wind Speed
    ax = axes[0]
    ax.plot(times, df['wind_speed'], color='blue', linewidth=2, label='Wind Speed (10m)')
    ax.fill_between(times, df['wind_speed'], alpha=0.1, color='blue')
    ax.set_ylabel('Speed (knots)')
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(loc='upper right')
    
    # 2. Wind Barbs (Direction)
    # Resample for barbs to avoid clutter if high res
    ax = axes[1]
    # Simple autoscaling of barb density
    n_points = len(df)
    stride = max(1, n_points // 20) 
    
    subset = df.iloc[::stride]
    
    # Calculate U/V for barbs
    # Note: barbs expect U, V in knots.
    # We have speed/dir. 
    # U = -speed * sin(dir)
    # V = -speed * cos(dir)
    u = -subset['wind_speed'] * np.sin(np.radians(subset['wind_dir']))
    v = -subset['wind_speed'] * np.cos(np.radians(subset['wind_dir']))
    
    ax.barbs(subset.index, np.zeros(len(subset)), u, v, length=7)
    ax.set_yticks([])
    ax.set_ylabel('Wind Dir (10m)')
    ax.grid(True, axis='x', linestyle=':', alpha=0.6)
    
    # 3. Pressure
    ax = axes[2]
    if 'msl' in df.columns:
        p_data = df['msl'] / 100.0 # Pa to hPa
        label = 'MSL Pressure'
    elif 'pressure' in df.columns:
        p_data = df['pressure']
        label = 'Pressure'
    else:
        p_data = None
        
    if p_data is not None:
        ax.plot(times, p_data, color='purple', linewidth=2, label=label)
        ax.set_ylabel('Pressure (hPa)')
        ax.legend(loc='upper right')
        ax.grid(True, linestyle=':', alpha=0.6)
        
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    if output_path:
        plt.savefig(output_path)
        # Also show it if running interactively? Usually yes for reports, 
        # but pure save functions might not. 
        # User request implies "resulting plots should be saved...". 
        # It doesn't explicitly say "and NOT shown".
        # But usually duplicate is annoying. 
        # interactive plot returns `VBox`.
        # meteogram usually shown.
        # I'll do both print "Saved to..." and show? 
        # Actually matplotlib `show()` clears the figure.
        # `savefig` MUST appear before `show`.
        print(f"Plot saved to {output_path}")
    
    # Always show in notebook too
    plt.show()    
