-- Migration 011: Add timezone column to profiles
-- Stores IANA timezone identifier (e.g. 'America/Los_Angeles')
-- NULL means user hasn't completed setup wizard yet

ALTER TABLE profiles
    ADD COLUMN timezone VARCHAR(64) NULL AFTER userPoolId;

-- Set existing users to Pacific Time (all current users are in that zone)
UPDATE profiles SET timezone = 'America/Los_Angeles' WHERE timezone IS NULL;
