import os
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from fastapi.middleware.cors import CORSMiddleware

RAW_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@db:5432/careerdb"
)
# Some providers (Railway, Heroku) hand out "postgres://" -- SQLAlchemy
# with psycopg2 wants "postgresql://".
DATABASE_URL = RAW_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(
    title="AI Career Platform API",
    description="API over the seeded job postings database with company sync support.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

COMPANY_FIELDS = (
    "company_name",
    "industry",
    "company_size",
    "headquarters",
    "website",
    "linkedin_url",
    "logo_url",
    "description",
)

JOB_FIELDS = (
    "job_title",
    "department",
    "employment_type",
    "work_mode",
    "location",
    "openings",
    "experience_min",
    "experience_max",
    "salary_min",
    "salary_max",
    "currency",
    "project_role",
    "project_role_description",
    "summary",
    "education",
    "additional_information",
    "posted_date",
    "application_deadline",
    "status",
)

JOB_CHILDREN = (
    ("responsibilities", "job_responsibilities", "item"),
    ("professional_skills", "job_professional_skills", "skill"),
    ("required_skills", "job_required_skills", "skill"),
    ("preferred_skills", "job_preferred_skills", "skill"),
    ("benefits", "job_benefits", "benefit"),
)


class CompanyWrite(BaseModel):
    id: Optional[int] = None
    company_name: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None


class JobWrite(BaseModel):
    id: Optional[int] = None
    job_title: str
    department: Optional[str] = None
    employment_type: Optional[str] = None
    work_mode: Optional[str] = None
    location: Optional[str] = None
    openings: int = 1
    experience_min: Optional[int] = None
    experience_max: Optional[int] = None
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None
    currency: Optional[str] = "INR"
    project_role: Optional[str] = None
    project_role_description: Optional[str] = None
    summary: Optional[str] = None
    education: Optional[str] = None
    additional_information: Optional[str] = None
    posted_date: Optional[date] = None
    application_deadline: Optional[date] = None
    status: Optional[str] = "OPEN"
    responsibilities: List[str] = Field(default_factory=list)
    professional_skills: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)


class CompanySyncRequest(BaseModel):
    company: CompanyWrite
    jobs: List[JobWrite] = Field(default_factory=list)
    replace_existing_jobs: bool = False


def row_to_dict(row):
    return dict(row._mapping)


def model_dump(data):
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return data.dict()


def fetch_child_list(conn, table, column, job_id):
    rows = conn.execute(
        text(f"SELECT {column} FROM {table} WHERE job_id = :job_id ORDER BY position"),
        {"job_id": job_id},
    ).fetchall()
    return [r[0] for r in rows]


def insert_child_list(conn, table, column, job_id, items):
    for position, item in enumerate(items):
        conn.execute(
            text(
                f"INSERT INTO {table} (job_id, {column}, position) "
                "VALUES (:job_id, :item, :position)"
            ),
            {"job_id": job_id, "item": item, "position": position},
        )


def replace_job_children(conn, job_id, job_data):
    for field_name, table_name, column_name in JOB_CHILDREN:
        conn.execute(text(f"DELETE FROM {table_name} WHERE job_id = :job_id"), {"job_id": job_id})
        insert_child_list(conn, table_name, column_name, job_id, job_data.get(field_name, []))


def fetch_job_details(conn, job_id, include_company=True):
    job_row = conn.execute(text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}).fetchone()
    if not job_row:
        return None

    job = row_to_dict(job_row)
    if include_company:
        company_row = conn.execute(
            text("SELECT * FROM companies WHERE id = :id"), {"id": job["company_id"]}
        ).fetchone()
        job["company"] = row_to_dict(company_row) if company_row else None

    for field_name, table_name, column_name in JOB_CHILDREN:
        job[field_name] = fetch_child_list(conn, table_name, column_name, job_id)

    return job


def fetch_company_details(conn, company_id):
    company_row = conn.execute(
        text("SELECT * FROM companies WHERE id = :id"), {"id": company_id}
    ).fetchone()
    if not company_row:
        return None

    company = row_to_dict(company_row)
    job_rows = conn.execute(
        text("SELECT id FROM jobs WHERE company_id = :id ORDER BY id"), {"id": company_id}
    ).fetchall()
    company["jobs"] = [fetch_job_details(conn, job_row[0], include_company=False) for job_row in job_rows]
    return company


def insert_job(conn, company_id, job_data):
    insert_values = {field: job_data.get(field) for field in JOB_FIELDS}
    insert_values["company_id"] = company_id
    job_id = conn.execute(
        text("""
            INSERT INTO jobs
                (company_id, job_title, department, employment_type, work_mode,
                 location, openings, experience_min, experience_max,
                 salary_min, salary_max, currency, project_role,
                 project_role_description, summary, education,
                 additional_information, posted_date, application_deadline, status)
            VALUES
                (:company_id, :job_title, :department, :employment_type, :work_mode,
                 :location, :openings, :experience_min, :experience_max,
                 :salary_min, :salary_max, :currency, :project_role,
                 :project_role_description, :summary, :education,
                 :additional_information, :posted_date, :application_deadline, :status)
            RETURNING id
        """),
        insert_values,
    ).scalar_one()
    replace_job_children(conn, job_id, job_data)
    return job_id


def update_job(conn, company_id, job_id, job_data):
    existing_job = conn.execute(
        text("SELECT id FROM jobs WHERE id = :id AND company_id = :company_id"),
        {"id": job_id, "company_id": company_id},
    ).fetchone()
    if not existing_job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} was not found for company {company_id}",
        )

    update_values = {field: job_data.get(field) for field in JOB_FIELDS}
    update_values["id"] = job_id
    conn.execute(
        text("""
            UPDATE jobs
            SET job_title = :job_title,
                department = :department,
                employment_type = :employment_type,
                work_mode = :work_mode,
                location = :location,
                openings = :openings,
                experience_min = :experience_min,
                experience_max = :experience_max,
                salary_min = :salary_min,
                salary_max = :salary_max,
                currency = :currency,
                project_role = :project_role,
                project_role_description = :project_role_description,
                summary = :summary,
                education = :education,
                additional_information = :additional_information,
                posted_date = :posted_date,
                application_deadline = :application_deadline,
                status = :status
            WHERE id = :id
        """),
        update_values,
    )
    replace_job_children(conn, job_id, job_data)
    return job_id


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
        job = fetch_job_details(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/companies/upsert")
def upsert_company(payload: CompanySyncRequest, response: Response):
    company_data = model_dump(payload.company)
    company_id = company_data.pop("id", None)
    company_values = {field: company_data.get(field) for field in COMPANY_FIELDS}

    created_job_ids = []
    updated_job_ids = []
    deleted_job_ids = []

    try:
        with engine.begin() as conn:
            if company_id is not None:
                existing_company = conn.execute(
                    text("SELECT id FROM companies WHERE id = :id"),
                    {"id": company_id},
                ).fetchone()
                if not existing_company:
                    raise HTTPException(status_code=404, detail="Company not found")

                duplicate_company = conn.execute(
                    text("SELECT id FROM companies WHERE company_name = :company_name AND id <> :id"),
                    {"company_name": company_values["company_name"], "id": company_id},
                ).fetchone()
                if duplicate_company:
                    raise HTTPException(
                        status_code=409,
                        detail="Another company already uses this company_name",
                    )

                conn.execute(
                    text("""
                        UPDATE companies
                        SET company_name = :company_name,
                            industry = :industry,
                            company_size = :company_size,
                            headquarters = :headquarters,
                            website = :website,
                            linkedin_url = :linkedin_url,
                            logo_url = :logo_url,
                            description = :description
                        WHERE id = :id
                    """),
                    {**company_values, "id": company_id},
                )
                company_action = "updated"
            else:
                existing_company = conn.execute(
                    text("SELECT id FROM companies WHERE company_name = :company_name"),
                    {"company_name": company_values["company_name"]},
                ).fetchone()

                if existing_company:
                    company_id = existing_company[0]
                    conn.execute(
                        text("""
                            UPDATE companies
                            SET industry = :industry,
                                company_size = :company_size,
                                headquarters = :headquarters,
                                website = :website,
                                linkedin_url = :linkedin_url,
                                logo_url = :logo_url,
                                description = :description
                            WHERE id = :id
                        """),
                        {**company_values, "id": company_id},
                    )
                    company_action = "updated"
                else:
                    company_id = conn.execute(
                        text("""
                            INSERT INTO companies
                                (company_name, industry, company_size, headquarters,
                                 website, linkedin_url, logo_url, description)
                            VALUES
                                (:company_name, :industry, :company_size, :headquarters,
                                 :website, :linkedin_url, :logo_url, :description)
                            RETURNING id
                        """),
                        company_values,
                    ).scalar_one()
                    company_action = "created"

            existing_job_ids = {
                row[0]
                for row in conn.execute(
                    text("SELECT id FROM jobs WHERE company_id = :company_id"),
                    {"company_id": company_id},
                ).fetchall()
            }
            retained_job_ids = set()

            for job_payload in payload.jobs:
                job_data = model_dump(job_payload)
                job_id = job_data.pop("id", None)

                if job_id is None:
                    created_job_id = insert_job(conn, company_id, job_data)
                    created_job_ids.append(created_job_id)
                    retained_job_ids.add(created_job_id)
                else:
                    updated_job_id = update_job(conn, company_id, job_id, job_data)
                    updated_job_ids.append(updated_job_id)
                    retained_job_ids.add(updated_job_id)

            if payload.replace_existing_jobs:
                for stale_job_id in sorted(existing_job_ids - retained_job_ids):
                    conn.execute(
                        text("DELETE FROM jobs WHERE id = :id AND company_id = :company_id"),
                        {"id": stale_job_id, "company_id": company_id},
                    )
                    deleted_job_ids.append(stale_job_id)

            company = fetch_company_details(conn, company_id)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Could not save company data") from exc

    response.status_code = 201 if company_action == "created" else 200
    return {
        "action": company_action,
        "job_actions": {
            "created": created_job_ids,
            "updated": updated_job_ids,
            "deleted": deleted_job_ids,
        },
        "company": company,
    }
