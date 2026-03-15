-- Migration 020: Add theme_mode column to profiles
-- Stores user preference for light/dark mode

ALTER TABLE profiles
    ADD COLUMN theme_mode VARCHAR(8) NOT NULL DEFAULT 'light' AFTER timezone;
