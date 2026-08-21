-- ============================================================
-- Schema for AI Career Platform job postings
-- Written for PostgreSQL. MySQL notes are called out inline
-- (swap SERIAL -> INT AUTO_INCREMENT, TEXT[] not available, etc.)
-- ============================================================

CREATE TABLE IF NOT EXISTS companies (
    id                SERIAL PRIMARY KEY,
    company_name      VARCHAR(255) NOT NULL UNIQUE,
    industry          VARCHAR(255),
    company_size      VARCHAR(50),
    headquarters      VARCHAR(255),
    website           VARCHAR(255),
    linkedin_url      VARCHAR(255),
    logo_url          VARCHAR(255),
    description       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id                        SERIAL PRIMARY KEY,
    company_id                INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    job_title                 VARCHAR(255) NOT NULL,
    department                VARCHAR(255),
    employment_type           VARCHAR(100),
    work_mode                 VARCHAR(50),
    location                  VARCHAR(255),
    openings                  INTEGER DEFAULT 1,
    experience_min            INTEGER,
    experience_max            INTEGER,
    salary_min                NUMERIC(12, 2),
    salary_max                NUMERIC(12, 2),
    currency                  VARCHAR(10) DEFAULT 'INR',
    project_role               VARCHAR(255),
    project_role_description  TEXT,
    summary                   TEXT,
    education                 TEXT,
    additional_information    TEXT,
    posted_date                DATE,
    application_deadline      DATE,
    status                    VARCHAR(30) DEFAULT 'OPEN',
    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- One row per bullet point, keeps things queryable/filterable
-- (e.g. "find all jobs requiring Kubernetes") without JSON parsing.

CREATE TABLE IF NOT EXISTS job_responsibilities (
    id       SERIAL PRIMARY KEY,
    job_id   INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    item     TEXT NOT NULL,
    position SMALLINT
);

CREATE TABLE IF NOT EXISTS job_professional_skills (
    id       SERIAL PRIMARY KEY,
    job_id   INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill    TEXT NOT NULL,
    position SMALLINT
);

CREATE TABLE IF NOT EXISTS job_required_skills (
    id       SERIAL PRIMARY KEY,
    job_id   INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill    TEXT NOT NULL,
    position SMALLINT
);

CREATE TABLE IF NOT EXISTS job_preferred_skills (
    id       SERIAL PRIMARY KEY,
    job_id   INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill    TEXT NOT NULL,
    position SMALLINT
);

CREATE TABLE IF NOT EXISTS job_benefits (
    id       SERIAL PRIMARY KEY,
    job_id   INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    benefit  TEXT NOT NULL,
    position SMALLINT
);

-- Helpful indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_jobs_title       ON jobs(job_title);
CREATE INDEX IF NOT EXISTS idx_jobs_location     ON jobs(location);
CREATE INDEX IF NOT EXISTS idx_jobs_status       ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company_id   ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_req_skill_text    ON job_required_skills(skill);
