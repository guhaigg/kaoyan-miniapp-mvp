CREATE TABLE IF NOT EXISTS historical_release_timing_profiles (
  id TEXT PRIMARY KEY NOT NULL,
  profile_key TEXT NOT NULL UNIQUE,
  school_id TEXT NULL REFERENCES schools(id),
  school_name TEXT NOT NULL,
  school_name_normalized TEXT NOT NULL,
  sample_count INTEGER NOT NULL DEFAULT 0,
  peak_hour INTEGER NULL,
  peak_hour_bucket TEXT NULL,
  window_start_md TEXT NULL,
  window_end_md TEXT NULL,
  consistency_ratio REAL NULL,
  meta_json JSON NOT NULL DEFAULT '{}',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_historical_release_timing_profiles_school
  ON historical_release_timing_profiles (school_name_normalized);

CREATE INDEX IF NOT EXISTS ix_historical_release_timing_profiles_peak_hour
  ON historical_release_timing_profiles (peak_hour);

CREATE INDEX IF NOT EXISTS ix_historical_release_timing_profiles_peak_hour_bucket
  ON historical_release_timing_profiles (peak_hour_bucket);
