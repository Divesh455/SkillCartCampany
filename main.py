import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import create_engine, text

RAW_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@db:5432/careerdb"
)
# Some providers (Railway, Heroku) hand out "postgres://" -- SQLAlchemy
# with psycopg2 wants "postgresql://".
DATABASE_URL = RAW_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(
    title="AI Career Platform API",
    description="Read-only API over the seeded job postings database.",
    version="1.0.0",
)


def row_to_dict(row):
    return dict(row._mapping)


def fetch_child_list(conn, table, column, job_id):
    rows = conn.execute(
        text(f"SELECT {column} FROM {table} WHERE job_id = :job_id ORDER BY position"),
        {"job_id": job_id},
    ).fetchall()
    return [r[0] for r in rows]


@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/roles/summary")
def roles_summary():
    """Job count grouped by role — mirrors the role distribution table."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT job_title, COUNT(*) AS jobs
                FROM jobs
                GROUP BY job_title
                ORDER BY jobs DESC
            """)
        ).fetchall()
    return [row_to_dict(r) for r in rows]


@app.get("/companies")
def list_companies(limit: int = Query(20, le=100), offset: int = 0):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM companies ORDER BY id LIMIT :limit OFFSET :offset"),
            {"limit": limit, "offset": offset},
        ).fetchall()
        total = conn.execute(text("SELECT COUNT(*) FROM companies")).scalar()
    return {"total": total, "limit": limit, "offset": offset, "items": [row_to_dict(r) for r in rows]}


@app.get("/companies/{company_id}")
def get_company(company_id: int):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM companies WHERE id = :id"), {"id": company_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Company not found")
        jobs = conn.execute(
            text("SELECT id, job_title, location, status FROM jobs WHERE company_id = :id"),
            {"id": company_id},
        ).fetchall()
    company = row_to_dict(row)
    company["jobs"] = [row_to_dict(j) for j in jobs]
    return company


@app.get("/jobs")
def list_jobs(
    role: Optional[str] = None,
    location: Optional[str] = None,
    work_mode: Optional[str] = None,
    min_experience: Optional[int] = None,
    max_salary: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
):
    """List jobs with optional filters. All filters are optional and combinable."""
    clauses = []
    params = {"limit": limit, "offset": offset}

    if role:
        clauses.append("j.job_title ILIKE :role")
        params["role"] = f"%{role}%"
    if location:
        clauses.append("j.location ILIKE :location")
        params["location"] = f"%{location}%"
    if work_mode:
        clauses.append("j.work_mode = :work_mode")
        params["work_mode"] = work_mode
    if min_experience is not None:
        clauses.append("j.experience_max >= :min_experience")
        params["min_experience"] = min_experience
    if max_salary is not None:
        clauses.append("j.salary_min <= :max_salary")
        params["max_salary"] = max_salary
    if status:
        clauses.append("j.status = :status")
        params["status"] = status

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    query = f"""
        SELECT j.id, j.job_title, j.department, j.employment_type, j.work_mode,
               j.location, j.experience_min, j.experience_max,
               j.salary_min, j.salary_max, j.currency, j.status, j.posted_date,
               c.company_name, c.industry
        FROM jobs j
        JOIN companies c ON c.id = j.company_id
        {where_sql}
        ORDER BY j.id
        LIMIT :limit OFFSET :offset
    """
    count_query = f"SELECT COUNT(*) FROM jobs j JOIN companies c ON c.id = j.company_id {where_sql}"

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).fetchall()
        total = conn.execute(text(count_query), params).scalar()

    return {"total": total, "limit": limit, "offset": offset, "items": [row_to_dict(r) for r in rows]}


@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    with engine.connect() as conn:
        job_row = conn.execute(text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}).fetchone()
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found")

        job = row_to_dict(job_row)
        company_row = conn.execute(
            text("SELECT * FROM companies WHERE id = :id"), {"id": job["company_id"]}
        ).fetchone()

        job["company"] = row_to_dict(company_row) if company_row else None
        job["responsibilities"] = fetch_child_list(conn, "job_responsibilities", "item", job_id)
        job["professional_skills"] = fetch_child_list(conn, "job_professional_skills", "skill", job_id)
        job["required_skills"] = fetch_child_list(conn, "job_required_skills", "skill", job_id)
        job["preferred_skills"] = fetch_child_list(conn, "job_preferred_skills", "skill", job_id)
        job["benefits"] = fetch_child_list(conn, "job_benefits", "benefit", job_id)

    return job
