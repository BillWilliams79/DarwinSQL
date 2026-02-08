-- Migration 002: Add closed column to areas
-- Supports ability to close (hide) areas from task plan view

USE darwin;

ALTER TABLE areas
ADD COLUMN closed TINYINT NOT NULL DEFAULT 0;
