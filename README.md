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

## Company write endpoint

The API now includes `POST /companies/upsert` to create a company or
update an existing one and sync its related jobs in the same request.

- If `company.id` is sent, that company row is updated.
- If `company.id` is omitted and `company.company_name` already exists,
  that company row is updated.
- If a job inside `jobs` has an `id`, that job is updated.
- If a job inside `jobs` does not have an `id`, a new job is created.
- If `replace_existing_jobs` is `true`, any existing jobs for the
  company that are not included in the request are deleted.

Example payload:

```json
{
  "company": {
    "company_name": "Acme Technologies Pvt. Ltd.",
    "industry": "Software",
    "company_size": "201-500 employees",
    "headquarters": "Bengaluru, Karnataka, India",
    "website": "https://acme.example.com",
    "linkedin_url": "https://www.linkedin.com/company/acme",
    "logo_url": "https://acme.example.com/logo.png",
    "description": "Product engineering company."
  },
  "jobs": [
    {
      "job_title": "Backend Developer",
      "department": "Engineering",
      "employment_type": "Full-time",
      "work_mode": "Hybrid",
      "location": "Bengaluru, Karnataka, India",
      "openings": 2,
      "experience_min": 3,
      "experience_max": 5,
      "salary_min": 1200000,
      "salary_max": 1800000,
      "currency": "INR",
      "project_role": "Backend API Developer",
      "project_role_description": "Build internal and public APIs.",
      "summary": "Python backend role.",
      "education": "Bachelor's degree in Computer Science or similar.",
      "additional_information": "Immediate joiners preferred.",
      "posted_date": "2026-07-29",
      "application_deadline": "2026-08-15",
      "status": "OPEN",
      "responsibilities": [
        "Build API services",
        "Review pull requests"
      ],
      "professional_skills": [
        "System design",
        "Debugging"
      ],
      "required_skills": [
        "Python",
        "FastAPI",
        "PostgreSQL"
      ],
      "preferred_skills": [
        "Docker",
        "AWS"
      ],
      "benefits": [
        "Health insurance",
        "Flexible hours"
      ]
    }
  ],
  "replace_existing_jobs": false
}
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
