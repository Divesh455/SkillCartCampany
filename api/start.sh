#!/bin/sh
set -e

echo ">>> Step 1: applying schema + seeding data (if seed script present)"
if [ -f "database/seed.py" ]; then
    python database/seed.py
elif [ -f "../database/seed.py" ]; then
    python ../database/seed.py
elif [ -f "/app/database/seed.py" ]; then
    python /app/database/seed.py
elif [ -f "seed.py" ]; then
    python seed.py
else
    echo "Seed script not found, proceeding directly to API startup."
fi

echo ">>> Step 2: starting API server"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"

