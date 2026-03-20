-- Migration 026: Add application toggle columns to profiles
-- Enables users to show/hide app groups (Tasks, Maps, Swarm) from navbar.
-- Tasks and Maps enabled by default; Swarm disabled by default.

ALTER TABLE profiles
    ADD COLUMN app_tasks TINYINT(1) NOT NULL DEFAULT 1 AFTER theme_mode,
    ADD COLUMN app_maps  TINYINT(1) NOT NULL DEFAULT 1 AFTER app_tasks,
    ADD COLUMN app_swarm TINYINT(1) NOT NULL DEFAULT 0 AFTER app_maps;
