CREATE TABLE IF NOT EXISTS `historical_release_timing_profiles` (
  `id` varchar(36) NOT NULL,
  `profile_key` varchar(64) NOT NULL,
  `school_id` varchar(36) DEFAULT NULL,
  `school_name` varchar(255) NOT NULL,
  `school_name_normalized` varchar(255) NOT NULL,
  `sample_count` int NOT NULL DEFAULT 0,
  `peak_hour` int DEFAULT NULL,
  `peak_hour_bucket` varchar(32) DEFAULT NULL,
  `window_start_md` varchar(16) DEFAULT NULL,
  `window_end_md` varchar(16) DEFAULT NULL,
  `consistency_ratio` double DEFAULT NULL,
  `meta_json` json NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_historical_release_timing_profiles_profile_key` (`profile_key`),
  KEY `ix_historical_release_timing_profiles_school_name_normalized` (`school_name_normalized`),
  KEY `ix_historical_release_timing_profiles_peak_hour` (`peak_hour`),
  KEY `ix_historical_release_timing_profiles_peak_hour_bucket` (`peak_hour_bucket`),
  KEY `ix_historical_release_timing_profiles_school_id` (`school_id`),
  CONSTRAINT `fk_historical_release_timing_profiles_school_id`
    FOREIGN KEY (`school_id`) REFERENCES `schools` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
