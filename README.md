# Clinical Trial Patient Demand Calculator

This repository contains a small collection of tools and a Streamlit dashboard to estimate patient-level product demand for clinical trials. It also includes a Jupyter-friendly notebook that embeds the Streamlit UI for quick exploration.

## Contents

- `math_simulations.ipynb` - Notebook with demo and Streamlit-embedded app.
- `setup_venv.sh` - Helper script to create a venv, install dependencies, and register a Jupyter kernel.
- `requirements.txt` - Python dependencies used by the project.

## Quickstart

Prerequisites: Python 3.10+ and Git.

From the project root:

1. Create and configure the virtual environment (default name: `.venv2`):

```bash
./setup_venv.sh
```

You can customize the venv name or the Python binary:

```bash
./setup_venv.sh --name .venv3 --python python3.11
```

2. Activate the venv and run Jupyter Notebook (or JupyterLab):

```bash
source .venv2/bin/activate
jupyter notebook
```

3. Open `math_simulations.ipynb` and run the cells. If using the Streamlit-embedded cell, ensure `streamlit-jupyter` is installed (it's included in `requirements.txt`).

## Running the Streamlit app standalone

If you'd like to run the Streamlit app outside the notebook (normal Streamlit experience):

```bash
source .venv2/bin/activate
streamlit run clinical_demand_app.py
```

Replace `clinical_demand_app.py` with the appropriate script if you moved or renamed the app file.

## CI

A GitHub Actions workflow is included that installs dependencies and runs a basic syntax check on Python files. See `.github/workflows/ci.yml` for details.

## Git

Virtual environments are ignored by `.gitignore`. Do not commit the `.venv*/` directories.

## Contributing

Create a new branch, open a pull request, and CI will validate the repository.

---
If you want a different CI configuration (tests, formatters, or additional checks), tell me which tools you prefer (pytest, flake8, black, mypy, etc.) and I'll add them.
