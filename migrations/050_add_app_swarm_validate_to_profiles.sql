-- Migration 050: Add Swarm Validate app toggle to profiles (req #2611)
-- Splits Features / Test Cases / Test Plans / Test Runs out of the SWARM
-- app into a separate "Swarm Validate" app. Disabled by default so existing
-- users continue to see those nav links inside SWARM until they opt in.

ALTER TABLE profiles
    ADD COLUMN app_swarm_validate TINYINT(1) NOT NULL DEFAULT 0 AFTER app_solar;
