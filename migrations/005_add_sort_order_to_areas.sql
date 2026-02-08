-- Migration 005: Add sort_order column to areas
-- Supports sorting areas in the UI and retaining settings across devices/logins

USE darwin;

ALTER TABLE areas
ADD COLUMN sort_order SMALLINT;
