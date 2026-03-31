-- Migration 036: Create user_integrations table
-- Stores OAuth tokens for external service integrations (e.g., Strava).
-- DB-backed so tokens persist across devices. Lambda-Rest auto-scopes
-- via creator_fk — no Lambda code changes needed for CRUD.

CREATE TABLE user_integrations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  creator_fk VARCHAR(36) NOT NULL,
  provider VARCHAR(50) NOT NULL,
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  expires_at INT NOT NULL,
  athlete_data JSON,
  create_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  update_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_creator_provider (creator_fk, provider)
);
