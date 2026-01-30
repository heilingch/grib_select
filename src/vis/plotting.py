import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

def apply_style(ax):
    """Applies common style: Gridlines, etc."""
    ax.grid(True, color='grey', linestyle='--', alpha=0.8)

def plot_multi_model_comparison(obs_df: pd.DataFrame, model_data_dict: dict, obs_name: str, output_path: str = None):
    """
    Plots Observed data vs Multiple Models.
    model_data_dict: { 'ModelName': comparison_df, ... }
    comparison_df should have 'model_wind_speed', 'model_wind_dir', etc.
    """
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    
    # --- 1. Wind Speed ---
    # Plot Observation
    ax1.plot(obs_df.index, obs_df['wind_speed'], label=f'Observed ({obs_name})', color='black', linewidth=2.5, zorder=10)
    
    # Plot Models
    # Generate colors
    if len(model_data_dict) > 0:
        colors = plt.cm.tab10(np.linspace(0, 1, len(model_data_dict)))
    else:
        colors = []
    
    for (model_name, df), color in zip(model_data_dict.items(), colors):
        if 'model_wind_speed' in df.columns:
            ax1.plot(df.index, df['model_wind_speed'], label=model_name, linestyle='--', color=color, linewidth=1.5)
            
    ax1.set_ylabel('Wind Speed (knots)')
    ax1.set_title(f"Wind Comparison: {obs_name}")
    ax1.legend()
    apply_style(ax1)
    
    # --- 2. Wind Direction ---
    ax2.scatter(obs_df.index, obs_df['wind_dir'], label='Observed', color='black', s=20, zorder=10)
    
    for (model_name, df), color in zip(model_data_dict.items(), colors):
        if 'model_wind_dir' in df.columns:
            # Use scatter for direction to avoid wrapping lines 360->0
            ax2.scatter(df.index, df['model_wind_dir'], label=model_name, marker='x', s=15, color=color)
            
    ax2.set_ylabel('Wind Direction (deg)')
    ax2.set_ylim(0, 360)
    # ax2.legend() # Legend on top chart is usually enough
    apply_style(ax2)
    
    # --- 3. Pressure ---
    has_pressure = 'pressure' in obs_df.columns
    if has_pressure:
        ax3.plot(obs_df.index, obs_df['pressure'], label='Observed', color='black', linewidth=2.5, zorder=10)
        
    for (model_name, df), color in zip(model_data_dict.items(), colors):
        if 'model_pressure' in df.columns:
            ax3.plot(df.index, df['model_pressure'], label=model_name, linestyle='--', color=color, linewidth=1.5)
            
    ax3.set_ylabel('Pressure (hPa)')
    apply_style(ax3)
    
    # --- Zoom / Limits ---
    # Set x-limits to encompass all valid data
    # Union of indices
    all_indices = [obs_df.index] + [df.index for df in model_data_dict.values()]
    if all_indices:
        combined_index = pd.Index([])
        for idx in all_indices:
            combined_index = combined_index.union(idx)
            
        if not combined_index.empty:
            ax3.set_xlim(combined_index.min(), combined_index.max())

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
