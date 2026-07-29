# Deploy to Railway (simple version — one service)

This is a simplified version: **one service** instead of two. On every
deploy it seeds the database first, then starts the API. No separate
"seed" service, no restart-policy fiddling.

Tested locally end-to-end before being handed to you: fresh Postgres →
schema created → 150 jobs loaded → API served real responses.

## Steps

```bash
npm i -g @railway/cli
railway login

cd railway-app
railway init                      # name your project

railway add -d postgres           # adds the database

railway up                        # builds and deploys THIS folder as one service
```

After `railway up` finishes, set the database connection:

```bash
railway variables set 'DATABASE_URL=${{Postgres.DATABASE_URL}}'
```
(Single quotes — PowerShell mangles `${{ }}` inside double quotes.)

This triggers a fresh deploy automatically. Watch it:

```bash
railway logs
```

You should see, in order:
```
>>> Step 1: applying schema + seeding data
Applied schema (12 statements).
Seeded 150 job records into the database.
>>> Step 2: starting API server
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Get a public URL

In the Railway dashboard: click your service → **Settings** →
**Networking** → **Generate Domain**.

Test it:
```bash
curl https://<your-app>.up.railway.app/health
curl https://<your-app>.up.railway.app/roles/summary
```

## If the build still fails

Run:
```bash
railway logs --build
```
This shows the actual build error (package install failure, etc.) —
paste that exact text if you need help, not just "Deploy failed".

## Files

- `Dockerfile` — builds one image with everything
- `start.sh` — runs `seed.py` then starts the API (`CMD` in the Dockerfile)
- `seed.py` — creates the schema (if missing) and loads `data/jobs_150.json`
- `main.py` — the FastAPI app (`/health`, `/jobs`, `/companies`, etc.)
- `schema.sql` — table definitions
- `railway.json` — tells Railway explicitly to use the Dockerfile
  (avoids any auto-detection ambiguity)
