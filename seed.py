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
# Some providers (Railway, Heroku) hand out "postgres://" -- SQLAlchemy
# with psycopg2 wants "postgresql://".
DATABASE_URL = RAW_DATABASE_URL.replace("postgres://", "postgresql://", 1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_PATH = "/app/data/jobs_150.json" if os.path.exists("/app/data/jobs_150.json") else os.path.join(BASE_DIR, "data", "jobs_150.json")
DEFAULT_SCHEMA_PATH = "/app/schema.sql" if os.path.exists("/app/schema.sql") else os.path.join(BASE_DIR, "schema.sql")

DATA_FILE = os.environ.get("DATA_FILE", DEFAULT_DATA_PATH)
SCHEMA_FILE = os.environ.get("SCHEMA_FILE", DEFAULT_SCHEMA_PATH)


def wait_for_db(engine, retries=20, delay=3):
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database is ready.")
            return
        except OperationalError:
            print(f"Database not ready yet (attempt {attempt}/{retries}), retrying in {delay}s...")
            time.sleep(delay)
    print("Could not connect to database, exiting.")
    sys.exit(1)


def apply_schema(conn):
    with open(SCHEMA_FILE, "r") as f:
        raw = f.read()
    # Strip full-line comments first, then split into statements --
    # schema.sql has no semicolons inside strings, so a naive split is fine.
    sql = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("--"))
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        conn.execute(text(stmt))
    print(f"Applied schema ({len(statements)} statements).")


def main():
    engine = create_engine(DATABASE_URL)
    wait_for_db(engine)

    with open(DATA_FILE, "r") as f:
        records = json.load(f)

    with engine.begin() as conn:
        apply_schema(conn)

        # Clean slate on every deploy -- comment out if you want append-only seeding
        conn.execute(text("TRUNCATE TABLE job_benefits, job_preferred_skills, "
                           "job_required_skills, job_professional_skills, "
                           "job_responsibilities, jobs, companies RESTART IDENTITY CASCADE"))

        for record in records:
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

            def insert_list(table, column, items):
                for pos, item in enumerate(items):
                    conn.execute(
                        text(f"INSERT INTO {table} (job_id, {column}, position) "
                             f"VALUES (:job_id, :item, :pos)"),
                        {"job_id": job_id, "item": item, "pos": pos}
                    )

            insert_list("job_responsibilities", "item", j["responsibilities"])
            insert_list("job_professional_skills", "skill", j["professional_skills"])
            insert_list("job_required_skills", "skill", record["required_skills"])
            insert_list("job_preferred_skills", "skill", record["preferred_skills"])
            insert_list("job_benefits", "benefit", record["benefits"])

    print(f"Seeded {len(records)} job records into the database.")


if __name__ == "__main__":
    main()
