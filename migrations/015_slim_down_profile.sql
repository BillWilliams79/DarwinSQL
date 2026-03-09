-- Migration 015: Slim down profile
-- Remove region, userPoolId, subject, userName columns from profiles.
-- These are Cognito infrastructure details that duplicate JWT data or are unused.

ALTER TABLE profiles
    DROP COLUMN region,
    DROP COLUMN userPoolId,
    DROP COLUMN subject,
    DROP COLUMN userName;
