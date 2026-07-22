-- 068_effort_default_high.sql
--
-- Req #3007: New model/effort defaults — Opus and High.
--
-- The default effort for NEW requirements and swarm sessions moves from
-- 'xhigh' to 'high'. Model default was already 'opus' (migration 062), so this
-- migration only touches effort.
--
-- Why this matters at the schema level: the Darwin front-end creates a new
-- requirement with a POST body that omits `effort` (and `ai_model`) entirely
-- (RequirementDetail.jsx), so the persisted value comes from the column
-- DEFAULT — exactly the way `ai_model` lands on 'opus'. Migration 063 had
-- deliberately bumped the effort default to 'xhigh'; this reverses only that
-- bump so front-end-created requirements are born 'high'. The MCP create paths
-- (server.py / db.py) now also pass 'high' explicitly (req #3007), and
-- swarm_starts / swarm_completes already default to 'high' (req #2949) — this
-- brings requirements + swarm_sessions in line.
--
-- Data note: this changes the DEFAULT for future inserts only. Existing rows
-- are untouched (a stored 'xhigh' remains a valid, intentional value).
--
-- Value domain is unchanged: low | medium | high | xhigh | ultracode.

ALTER TABLE requirements
    ALTER COLUMN effort SET DEFAULT 'high';

ALTER TABLE swarm_sessions
    ALTER COLUMN effort SET DEFAULT 'high';
