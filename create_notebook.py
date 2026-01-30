import json
import os

def create_notebook():
    # Define the notebook structure (Markdown and Code cells)
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Grib Select: Interactive Analysis\n",
                "\n",
                "This notebook allows interactive comparison of weather models against local or METAR data.\n",
                "\n",
                "### Setup"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import sys\n",
                "import os\n",
                "# Add src to path\n",
                "sys.path.append(os.path.abspath(os.path.join(os.getcwd(), '..', 'src')))\n",
                "\n",
                "from workflow import GribSelectorSession\n",
                "%matplotlib inline"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 1. Initialize Session and Load Data"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "session = GribSelectorSession()\n",
                "\n",
                "# Load Local Data\n",
                "session.load_local_data('../tests/data/local_log.csv')\n",
                "\n",
                "# Load METAR (Optional)\n",
                "# session.load_metar('LDSP', hours=48)\n",
                "\n",
                "# Add Models\n",
                "session.add_grib('../tests/data/model_A.nc')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 2. Run Analysis"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "session.run_comparison()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 3. Dashboard\n",
                "Interactive plot viewer."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "session.plot_interactive()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 4. Ranking"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "session.get_ranking()"
            ]
        }
    ]

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.8.10"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }

    with open('notebooks/Interactive_Analysis.ipynb', 'w') as f:
        json.dump(notebook, f, indent=2)
    
    print("Notebook created at notebooks/Interactive_Analysis.ipynb")

if __name__ == "__main__":
    create_notebook()
