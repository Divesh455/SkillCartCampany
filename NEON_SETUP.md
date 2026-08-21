# Deploying Database Exclusively on Neon DB

This guide provides step-by-step instructions to deploy and seed your PostgreSQL database exclusively on **[Neon DB](https://neon.tech)** (serverless Postgres) and connect your **SkillCart Company API**.

---

## Workspace Architecture

- **`api/`**: Contains FastAPI application code, dependencies, and container startup configurations.
- **`database/`**: Contains schema definitions (`schema.sql`), seeding scripts (`seed.py`), and dataset files (`data/jobs_150.json`).

---

## Step 1: Create a Neon DB Project

1. Go to [Neon.tech](https://neon.tech) and log in or create a free account.
2. Click **New Project**.
3. Name your project (e.g. `skillcart-db`) and select your preferred region.
4. Click **Create Project**.

---

## Step 2: Get Your Neon DB Connection String

1. In the Neon Console, navigate to **Dashboard** or **Connection Details**.
2. Select **PostgreSQL**.
3. Copy your Connection String:

   ```text
   postgresql://alex:AbCd1234EfGh@ep-cool-darkness-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

   > [!NOTE]
   > Ensure `?sslmode=require` is present at the end of the connection string.

---

## Step 3: Run Database Migration & Seeding

You can seed your database schema (`schema.sql`) and 150 jobs dataset (`data/jobs_150.json`) directly into Neon DB using `database/seed.py`.

### PowerShell (Windows)

```powershell
$env:DATABASE_URL="postgresql://neondb_owner:npg_FNHO4PmC2tcX@ep-wild-bird-ay7034g0-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
python database/seed.py
```

### Bash / macOS / Linux

```bash
DATABASE_URL="postgresql://<user>:<password>@<ep-id>.neon.tech/neondb?sslmode=require" python database/seed.py
```

Expected Output:

```text
Connecting to database at ep-cool-darkness-123456.us-east-2.aws.neon.tech:5432/neondb...
Detected Neon DB connection string. Ensure sslmode=require is present.
Database is ready.
Applied schema (12 statements).
Seeded 150 job records into the database.
```

---

## Step 4: Connect API Service to Neon DB

### Render Deployment

1. Go to [Render Dashboard](https://dashboard.render.com/) -> **New +** -> **Web Service**.
2. Connect your repository and select **Docker** (or use `api/render.yaml`).
3. Set **Docker Build Context** to `.` and **Dockerfile Path** to `api/Dockerfile`.
4. Add Environment Variable:
   - **Key**: `DATABASE_URL`
   - **Value**: `postgresql://<user>:<password>@<ep-id>.neon.tech/neondb?sslmode=require`

### Railway Deployment

```bash
railway up
railway variables set 'DATABASE_URL=postgresql://<user>:<password>@<ep-id>.neon.tech/neondb?sslmode=require'
```

### Running API Locally

```bash
cd api
pip install -r requirements.txt
$env:DATABASE_URL="postgresql://<user>:<password>@<ep-id>.neon.tech/neondb?sslmode=require"
uvicorn main:app --reload
```
