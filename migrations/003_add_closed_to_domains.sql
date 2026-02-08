-- Migration 003: Add closed column to domains
-- Supports ability to close (hide) domains from task plan view

USE darwin;

ALTER TABLE domains
ADD COLUMN closed TINYINT NOT NULL DEFAULT 0;
