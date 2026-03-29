-- Migration 034: Add plan column to swarm_sessions
-- Stores the initial approved plan from the worker's planning phase

ALTER TABLE swarm_sessions ADD COLUMN plan TEXT NULL AFTER telemetry;
