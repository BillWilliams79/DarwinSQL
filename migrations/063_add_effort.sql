-- 063_add_effort.sql
--
-- Req #2916: Effort on requirements and swarm sessions.
--
-- Adds `effort` — the Claude Code effort level the swarm worker session runs
-- with — to both `requirements` (the user's choice, edited directly below
-- Model on the detail page) and `swarm_sessions` (the value captured at launch
-- so the session record is self-describing after the fact). Mirrors the
-- ai_model pattern (req #2909, migration 062).
--
-- Value domain: low | medium | high | xhigh | ultracode (lowercase).
-- `ultracode` is the user-facing name for the CLI's top level; swarm injection
-- maps it to `claude --effort max`.
--
-- Default 'xhigh' for NEW rows; all pre-#2916 rows are assumed 'high' (the
-- documented backfill rule). Two-step ALTER: ADD COLUMN with DEFAULT 'high'
-- backfills every historical row to 'high', then the DEFAULT is bumped to
-- 'xhigh' so future inserts land on the new default.
--
-- NOT NULL mirrors requirements.coordination_type (req #2745) and ai_model
-- (req #2909): an unset effort is not a meaningful state.

ALTER TABLE requirements
    ADD COLUMN effort VARCHAR(16) NOT NULL DEFAULT 'high' AFTER ai_model;
ALTER TABLE requirements
    ALTER COLUMN effort SET DEFAULT 'xhigh';

ALTER TABLE swarm_sessions
    ADD COLUMN effort VARCHAR(16) NOT NULL DEFAULT 'high' AFTER ai_model;
ALTER TABLE swarm_sessions
    ALTER COLUMN effort SET DEFAULT 'xhigh';
