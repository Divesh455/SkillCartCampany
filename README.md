# SkillCart Company — API & Database Architecture

This repository is organized into a clean separation of concerns with **API code** on one side and **Database code** on the other.

---

## Workspace Structure

```text
SkillCartCampany/
├── api/                       # API Codebase
│   ├── main.py                # FastAPI endpoints, models, & routes
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile             # Container definition for API
│   ├── start.sh               # Service startup script
│   ├── render.yaml            # Render deployment spec
│   ├── railway.json           # Railway deployment spec
│   └── .dockerignore          # Docker ignore file
│
├── database/                  # Database Codebase
│   ├── schema.sql             # SQL table definitions
│   ├── seed.py                # Database migration & seeding script
│   └── data/
│       └── jobs_150.json      # Job postings dataset (150 records)
│
├── NEON_SETUP.md              # Complete guide to deploying DB on Neon
└── README.md                  # Project overview & documentation
```

---

## 1. Database Setup (Neon DB)

To deploy your database exclusively on **[Neon DB](https://neon.tech)**:

1. Refer to [NEON_SETUP.md](NEON_SETUP.md) for full setup instructions.
2. Obtain your Neon connection string (`postgresql://<user>:<password>@<ep-id>.neon.tech/neondb?sslmode=require`).
3. Run the database migration and seeder:
   ```powershell
   $env:DATABASE_URL="postgresql://<user>:<password>@<ep-id>.neon.tech/neondb?sslmode=require"
   python database/seed.py
   ```

---

## 2. API Setup & Local Running

```bash
# Navigate to API directory
cd api

# Install dependencies
pip install -r requirements.txt

# Start API server
uvicorn main:app --reload
```

Interactive OpenAPI docs will be available at [http://localhost:8000/docs](http://localhost:8000/docs).
