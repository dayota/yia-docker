#!/bin/sh
set -eu

if [ ! -f requirements.txt ]; then
    echo "Python application requires requirements.txt in $(pwd)" >&2
    exit 66
fi
if [ ! -f main.py ]; then
    echo "FastAPI application requires main.py in $(pwd)" >&2
    exit 66
fi
if [ ! -x .venv/bin/python ]; then
    python -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check --no-input -r requirements.txt
exec .venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port "${YIA_PYTHON_PORT}" --reload
