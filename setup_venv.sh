#!/usr/bin/env bash
# Setup virtual environment and install requirements
# Usage: ./setup_venv.sh [--name .venv2] [--python python3]

set -euo pipefail

VENV_NAME=".venv"
PYTHON_CMD="python3"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      VENV_NAME="$2"; shift 2;;
    --python)
      PYTHON_CMD="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 [--name VENV_NAME] [--python PYTHON_CMD]"; exit 0;;
    *)
      echo "Unknown argument: $1"; exit 1;;
  esac
done

echo "Creating virtual environment at ./${VENV_NAME} using ${PYTHON_CMD}..."
${PYTHON_CMD} -m venv "${VENV_NAME}"

echo "Activating ${VENV_NAME} and upgrading pip..."
# shellcheck source=/dev/null
source "${VENV_NAME}/bin/activate"
python -m pip install --upgrade pip

if [[ -f requirements.txt ]]; then
  echo "Installing packages from requirements.txt..."
  python -m pip install -r requirements.txt
else
  echo "requirements.txt not found in $(pwd). Skipping pip install -r requirements.txt"
fi

echo "Installing ipykernel and registering kernel for this venv..."
python -m pip install ipykernel
python -m ipykernel install --user --name "${VENV_NAME}" --display-name "Python (${VENV_NAME})"

echo "Setup complete. To activate the venv in this shell run: source ${VENV_NAME}/bin/activate"
