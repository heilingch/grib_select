import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

def plot_wind_comparison(comparisons: pd.DataFrame, model_name: str, output_path: str = None):
    """
    Plots Wind Speed and Direction comparison.
    """
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    
    # Wind Speed
    ax1.plot(comparisons.index, comparisons['wind_speed'], label='Observed', color='black', linewidth=2)
    ax1.plot(comparisons.index, comparisons['model_wind_speed'], label=f'{model_name}', linestyle='--')
    ax1.set_ylabel('Wind Speed (knots)')
    ax1.legend()
    ax1.set_title(f"Wind Comparison: {model_name} vs Observed")
    
    # Wind Direction
    ax2.scatter(comparisons.index, comparisons['wind_dir'], label='Observed', color='black', s=10)
    ax2.scatter(comparisons.index, comparisons['model_wind_dir'], label=f'{model_name}', marker='x', s=10)
    ax2.set_ylabel('Wind Direction (deg)')
    ax2.set_ylim(0, 360)
    ax2.legend()
    
    # Pressure (if available)
    if 'pressure' in comparisons.columns and 'model_pressure' in comparisons.columns:
        ax3.plot(comparisons.index, comparisons['pressure'], label='Observed', color='black', linewidth=2)
        ax3.plot(comparisons.index, comparisons['model_pressure'], label=f'{model_name}', linestyle='--')
        ax3.set_ylabel('Pressure (hPa)')
        ax3.legend()
        
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path)
    else:
        plt.show() 
    plt.close()

def plot_metar_data(df: pd.DataFrame, station_name: str, output_path: str = None):
    """
    Plots basic METAR data: Wind and Pressure.
    """
    if df.empty:
        print("No data to plot.")
        return
        
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    # Wind
    ax1.plot(df.index, df['wind_speed'], label='Wind Speed (kts)', color='blue')
    ax1.set_ylabel('Speed (knots)')
    ax1.legend(loc='upper left')
    ax1.grid(True)
    
    # Create twin axis for wind dir if needed, or just separate
    # Let's keep it simple.
    ax1.set_title(f"METAR Data: {station_name}")
    
    if 'pressure' in df.columns:
        ax2.plot(df.index, df['pressure'], label='Pressure (hPa)', color='orange')
        ax2.set_ylabel('Pressure (hPa)')
        ax2.legend()
        ax2.grid(True)
        
    if output_path:
        plt.savefig(output_path)
    else:
        plt.show()
    plt.close()
    
def plot_grib_data(df: pd.DataFrame, title: str, output_path: str = None):
    """
    Plots extracted GRIB data series.
    """
    if df.empty:
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    ax1.plot(df.index, df['wind_speed'], label='Model Wind Speed', color='green')
    ax1.set_ylabel('Knots')
    ax1.set_title(f"GRIB Data: {title}")
    ax1.legend()
    ax1.grid(True)
    
    if 'pressure' in df.columns:
        ax2.plot(df.index, df['pressure'], label='Model Pressure', color='red')
        ax2.set_ylabel('hPa')
        ax2.legend()
        ax2.grid(True)

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
    sns.barplot(x=models, y=rmses)
    plt.title("Model Accuracy (Vector RMSE)")
    plt.ylabel("Wind Vector Error (knots)")
    
    if output_path:
        plt.savefig(output_path)
    plt.close()
