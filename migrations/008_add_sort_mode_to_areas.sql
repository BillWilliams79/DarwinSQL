-- Migration 008: Add sort_mode column to areas tables
-- Persists per-area sort mode preference (priority vs hand) in the database
-- instead of localStorage. Default 'priority' matches existing behavior.

ALTER TABLE areas ADD COLUMN sort_mode VARCHAR(8) NOT NULL DEFAULT 'priority';
