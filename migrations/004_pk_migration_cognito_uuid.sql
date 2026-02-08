-- Migration 004: Change profiles PK from INT to VARCHAR(64)
-- Supports using Cognito username (UUID) as the profiles primary key
-- This migration is data-dependent and was applied once in production.
-- It is preserved here as historical record of the schema change.

USE darwin;

-- Drop all foreign keys referencing profiles.id
ALTER TABLE domains DROP FOREIGN KEY domains_ibfk_1;
ALTER TABLE areas DROP FOREIGN KEY areas_ibfk_1;
ALTER TABLE tasks DROP FOREIGN KEY tasks_ibfk_1;

-- Remove duplicate test record
DELETE FROM profiles WHERE id = 1;

-- Replace INT id with VARCHAR(64) id
ALTER TABLE profiles DROP COLUMN id;
ALTER TABLE profiles ADD COLUMN id VARCHAR(64) PRIMARY KEY NOT NULL UNIQUE;

-- Set existing user's Cognito UUID as their new PK
UPDATE profiles
SET id = "3af9d78e-db31-4892-ab42-d1a731b724dd"
WHERE email = "darwintestuser@proton.me";

-- Update domains: widen creator_fk, set value, re-add FK
ALTER TABLE domains MODIFY COLUMN creator_fk VARCHAR(64) NOT NULL;
UPDATE domains SET creator_fk = "3af9d78e-db31-4892-ab42-d1a731b724dd";
ALTER TABLE domains
ADD CONSTRAINT domains_ibfk_1 FOREIGN KEY (creator_fk)
    REFERENCES profiles(id) ON UPDATE CASCADE ON DELETE CASCADE;

-- Update areas: widen creator_fk, set value, re-add FK
ALTER TABLE areas MODIFY COLUMN creator_fk VARCHAR(64) NOT NULL;
UPDATE areas SET creator_fk = "3af9d78e-db31-4892-ab42-d1a731b724dd";
ALTER TABLE areas
ADD CONSTRAINT areas_ibfk_1 FOREIGN KEY (creator_fk)
    REFERENCES profiles(id) ON UPDATE CASCADE ON DELETE CASCADE;

-- Update tasks: widen creator_fk, set value, re-add FK
ALTER TABLE tasks MODIFY COLUMN creator_fk VARCHAR(64) NOT NULL;
UPDATE tasks SET creator_fk = "3af9d78e-db31-4892-ab42-d1a731b724dd";
ALTER TABLE tasks
ADD CONSTRAINT tasks_ibfk_1 FOREIGN KEY (creator_fk)
    REFERENCES profiles(id) ON UPDATE CASCADE ON DELETE CASCADE;
