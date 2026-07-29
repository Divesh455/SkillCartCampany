#!/bin/sh
set -e

echo ">>> Step 1: applying schema + seeding data"
python seed.py

echo ">>> Step 2: starting API server"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
