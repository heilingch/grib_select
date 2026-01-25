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
        plt.show() # In a generic script this might fail if no X server, but requested plots so assuming capable.
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
