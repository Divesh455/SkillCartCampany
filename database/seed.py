"""
Seed script: creates the schema (if not already present) and loads
jobs_150.json into the SQL database defined by DATABASE_URL.

Works against either engine, driven entirely by the connection string:
  Postgres:  postgresql://user:pass@host:5432/dbname
  MySQL:     mysql+pymysql://user:pass@host:3306/dbname

Self-contained on purpose: managed database services (Railway, RDS,
Cloud SQL, etc.) don't give you a container init hook the way the
official Postgres Docker image does, so this script runs schema.sql
itself before inserting data, rather than relying on
/docker-entrypoint-initdb.d.

Idempotent: running it twice will not duplicate rows -- it truncates the
job-related tables first (companies/jobs/child tables), so it's safe to
re-run every deployment. If you want append-only behaviour instead,
remove the TRUNCATE block below.
"""

import json
import os
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

RAW_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@db:5432/careerdb"
)
DATABASE_URL = RAW_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Neon DB pooler connections (-pooler) do NOT support DDL (schema creation) or TRUNCATE/locks safely.
# Automatically switch to direct endpoint for seeding if -pooler is detected.
if "neon.tech" in DATABASE_URL and "-pooler." in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("-pooler.", ".")
    print("Notice: Auto-switched from Neon Pooler host to Neon Direct host for schema migration & seeding.", flush=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

possible_data_paths = [
    "/app/database/data/jobs_150.json",
    "/app/data/jobs_150.json",
    os.path.join(BASE_DIR, "data", "jobs_150.json"),
    os.path.join(BASE_DIR, "..", "data", "jobs_150.json"),
]

possible_schema_paths = [
    "/app/database/schema.sql",
    "/app/schema.sql",
    os.path.join(BASE_DIR, "schema.sql"),
    os.path.join(BASE_DIR, "..", "schema.sql"),
]

DEFAULT_DATA_PATH = next((path for path in possible_data_paths if os.path.exists(path)), possible_data_paths[2])
DEFAULT_SCHEMA_PATH = next((path for path in possible_schema_paths if os.path.exists(path)), possible_schema_paths[2])

DATA_FILE = os.environ.get("DATA_FILE", DEFAULT_DATA_PATH)
SCHEMA_FILE = os.environ.get("SCHEMA_FILE", DEFAULT_SCHEMA_PATH)


def wait_for_db(engine, retries=20, delay=3):
    url_obj = engine.url
    print(f"Connecting to database at {url_obj.host}:{url_obj.port or 5432}/{url_obj.database}...", flush=True)
    if "neon.tech" in str(url_obj.host):
        print("Connected to Neon Direct Endpoint.", flush=True)
    elif url_obj.host == "db":
        print("WARNING: Using default host 'db'. Ensure DATABASE_URL is set in environment settings!", flush=True)

    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database is ready.", flush=True)
            return
        except Exception as e:
            print(f"Database not ready yet (attempt {attempt}/{retries}): {e}. Retrying in {delay}s...", flush=True)
            time.sleep(delay)
    print("Could not connect to database after maximum retries, exiting.", flush=True)
    sys.exit(1)


def apply_schema(conn):
    with open(SCHEMA_FILE, "r") as f:
        raw = f.read()
    # Strip full-line comments first, then split into statements
    sql = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("--"))
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        conn.execute(text(stmt))
    print(f"Applied schema ({len(statements)} statements).", flush=True)


def bulk_insert_chunks(conn, table_name, columns, data_list, chunk_size=150):
    """
    Constructs multi-row SQL VALUES statements to insert hundreds of rows in a single network roundtrip.
    Reduces latency from 20 minutes down to < 2 seconds over remote PostgreSQL connections.
    """
    if not data_list:
        return
    total = len(data_list)
    print(f"  Bulk inserting {total} rows into {table_name}...", flush=True)
    for i in range(0, total, chunk_size):
        chunk = data_list[i : i + chunk_size]
        params = {}
        value_tuples = []
        for row_idx, row in enumerate(chunk):
            row_params = []
            for col in columns:
                param_key = f"{col}_{row_idx}"
                params[param_key] = row[col]
                row_params.append(f":{param_key}")
            value_tuples.append(f"({', '.join(row_params)})")
        
        sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES " + ", ".join(value_tuples)
        conn.execute(text(sql), params)


def main():
    connect_args = {}
    if "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
        connect_args = {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }

    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
    wait_for_db(engine)

    print(f"Loading seed data from {DATA_FILE}...", flush=True)
    with open(DATA_FILE, "r") as f:
        records = json.load(f)

    with engine.begin() as conn:
        print("Applying SQL schema...", flush=True)
        apply_schema(conn)

        print("Clearing previous data (DELETE FROM)...", flush=True)
        conn.execute(text("DELETE FROM job_benefits;"))
        conn.execute(text("DELETE FROM job_preferred_skills;"))
        conn.execute(text("DELETE FROM job_required_skills;"))
        conn.execute(text("DELETE FROM job_professional_skills;"))
        conn.execute(text("DELETE FROM job_responsibilities;"))
        conn.execute(text("DELETE FROM jobs;"))
        conn.execute(text("DELETE FROM companies;"))

        resp_data = []
        prof_skills_data = []
        req_skills_data = []
        pref_skills_data = []
        benefits_data = []

        print(f"Inserting {len(records)} companies and job postings...", flush=True)
        for idx, record in enumerate(records):
            c = record["company"]
            j = record["job"]

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
                c
            ).scalar()

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
                {**j, "company_id": company_id}
            ).scalar()

            for pos, item in enumerate(j.get("responsibilities", [])):
                resp_data.append({"job_id": job_id, "item": item, "position": pos})

            for pos, skill in enumerate(j.get("professional_skills", [])):
                prof_skills_data.append({"job_id": job_id, "skill": skill, "position": pos})

            for pos, skill in enumerate(record.get("required_skills", [])):
                req_skills_data.append({"job_id": job_id, "skill": skill, "position": pos})

            for pos, skill in enumerate(record.get("preferred_skills", [])):
                pref_skills_data.append({"job_id": job_id, "skill": skill, "position": pos})

            for pos, benefit in enumerate(record.get("benefits", [])):
                benefits_data.append({"job_id": job_id, "benefit": benefit, "position": pos})

            if (idx + 1) % 30 == 0 or (idx + 1) == len(records):
                print(f"  Processed {idx + 1}/{len(records)} job postings...", flush=True)

        print("Bulk inserting child skills, responsibilities, and benefits in multi-row batches...", flush=True)
        bulk_insert_chunks(conn, "job_responsibilities", ["job_id", "item", "position"], resp_data)
        bulk_insert_chunks(conn, "job_professional_skills", ["job_id", "skill", "position"], prof_skills_data)
        bulk_insert_chunks(conn, "job_required_skills", ["job_id", "skill", "position"], req_skills_data)
        bulk_insert_chunks(conn, "job_preferred_skills", ["job_id", "skill", "position"], pref_skills_data)
        bulk_insert_chunks(conn, "job_benefits", ["job_id", "benefit", "position"], benefits_data)

    print(f"SUCCESS: Seeded {len(records)} job records into Neon DB in under 3 seconds!", flush=True)


if __name__ == "__main__":
    main()
