-- Historical adjustment intelligence tables for SQLite.

CREATE TABLE IF NOT EXISTS historical_adjustment_profiles (
  id TEXT PRIMARY KEY NOT NULL,
  profile_key TEXT NOT NULL UNIQUE,
  year INTEGER NOT NULL,
  source_type TEXT NOT NULL,
  source_dataset_key TEXT NOT NULL,
  school_id TEXT NULL,
  school_name TEXT NOT NULL,
  school_name_normalized TEXT NOT NULL,
  school_code TEXT NULL,
  region_name TEXT NULL,
  city_name TEXT NULL,
  school_tier TEXT NULL,
  department_name TEXT NULL,
  department_name_normalized TEXT NULL,
  major_code TEXT NULL,
  major_name TEXT NULL,
  major_name_normalized TEXT NULL,
  study_mode TEXT NULL,
  sample_count INTEGER NOT NULL DEFAULT 0,
  vacancy_count INTEGER NULL,
  initial_score_min INTEGER NULL,
  initial_score_max INTEGER NULL,
  adjustment_score_min INTEGER NULL,
  adjustment_score_max INTEGER NULL,
  min_score INTEGER NULL,
  avg_score REAL NULL,
  max_score INTEGER NULL,
  meta_json JSON NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  FOREIGN KEY (school_id) REFERENCES schools (id)
);

CREATE INDEX IF NOT EXISTS ix_historical_adjustment_profiles_lookup
  ON historical_adjustment_profiles (school_name_normalized, major_code, major_name_normalized, study_mode);
CREATE INDEX IF NOT EXISTS ix_historical_adjustment_profiles_year_source
  ON historical_adjustment_profiles (year, source_type);

CREATE TABLE IF NOT EXISTS mentor_evaluations (
  id TEXT PRIMARY KEY NOT NULL,
  review_key TEXT NOT NULL UNIQUE,
  source_dataset_key TEXT NOT NULL,
  school_name TEXT NOT NULL,
  school_name_normalized TEXT NOT NULL,
  department_name TEXT NULL,
  department_name_normalized TEXT NULL,
  mentor_name TEXT NOT NULL,
  mentor_name_normalized TEXT NOT NULL,
  review_text TEXT NOT NULL,
  review_tags JSON NOT NULL,
  risk_level TEXT NULL,
  meta_json JSON NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_mentor_evaluations_school_department
  ON mentor_evaluations (school_name_normalized, department_name_normalized);
