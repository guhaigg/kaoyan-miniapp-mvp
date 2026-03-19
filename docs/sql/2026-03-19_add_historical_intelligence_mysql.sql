-- Historical adjustment intelligence tables for MySQL.

CREATE TABLE IF NOT EXISTS historical_adjustment_profiles (
  id VARCHAR(36) NOT NULL PRIMARY KEY,
  profile_key VARCHAR(64) NOT NULL,
  year INT NOT NULL,
  source_type VARCHAR(32) NOT NULL,
  source_dataset_key VARCHAR(128) NOT NULL,
  school_id VARCHAR(36) NULL,
  school_name VARCHAR(255) NOT NULL,
  school_name_normalized VARCHAR(255) NOT NULL,
  school_code VARCHAR(32) NULL,
  region_name VARCHAR(64) NULL,
  school_tier VARCHAR(64) NULL,
  department_name VARCHAR(255) NULL,
  department_name_normalized VARCHAR(255) NULL,
  major_code VARCHAR(32) NULL,
  major_name VARCHAR(255) NULL,
  major_name_normalized VARCHAR(255) NULL,
  study_mode VARCHAR(32) NULL,
  sample_count INT NOT NULL DEFAULT 0,
  vacancy_count INT NULL,
  min_score INT NULL,
  avg_score DOUBLE NULL,
  max_score INT NULL,
  meta_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  CONSTRAINT uq_historical_adjustment_profiles_profile_key UNIQUE (profile_key),
  CONSTRAINT fk_historical_adjustment_profiles_school_id FOREIGN KEY (school_id) REFERENCES schools (id)
);

CREATE INDEX ix_historical_adjustment_profiles_lookup
  ON historical_adjustment_profiles (school_name_normalized, major_code, major_name_normalized, study_mode);
CREATE INDEX ix_historical_adjustment_profiles_year_source
  ON historical_adjustment_profiles (year, source_type);

CREATE TABLE IF NOT EXISTS mentor_evaluations (
  id VARCHAR(36) NOT NULL PRIMARY KEY,
  review_key VARCHAR(64) NOT NULL,
  source_dataset_key VARCHAR(128) NOT NULL,
  school_name VARCHAR(255) NOT NULL,
  school_name_normalized VARCHAR(255) NOT NULL,
  department_name VARCHAR(255) NULL,
  department_name_normalized VARCHAR(255) NULL,
  mentor_name VARCHAR(255) NOT NULL,
  mentor_name_normalized VARCHAR(255) NOT NULL,
  review_text LONGTEXT NOT NULL,
  review_tags JSON NOT NULL,
  risk_level VARCHAR(32) NULL,
  meta_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  CONSTRAINT uq_mentor_evaluations_review_key UNIQUE (review_key)
);

CREATE INDEX ix_mentor_evaluations_school_department
  ON mentor_evaluations (school_name_normalized, department_name_normalized);
