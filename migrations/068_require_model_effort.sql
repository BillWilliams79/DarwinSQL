-- 068_require_model_effort.sql
--
-- Req #3007: model + effort must be explicitly provided when creating a
-- requirement — the DATABASE must not silently supply them.
--
-- Background: the front-end's new-requirement POST (RequirementDetail.jsx)
-- historically omitted ai_model/effort, so the persisted values came from the
-- column DEFAULT ('opus' / 'xhigh'). A hidden DB default is unmanageable — a
-- wrong default lands on rows invisibly and nobody can tell why until the
-- schema is inspected. That is exactly how new requirements silently became
-- 'xhigh' instead of the intended 'high'.
--
-- Fix: DROP the DEFAULT on requirements.ai_model and requirements.effort so the
-- value MUST come from the caller. The front-end now sends both explicitly, and
-- the MCP create_requirement path already does (validating against
-- VALID_AI_MODELS / VALID_EFFORTS in darwin-mcp/db.py). Columns stay NOT NULL.
--
-- NOTE on enforcement: this instance runs sql_mode WITHOUT STRICT_TRANS_TABLES,
-- so an INSERT that omits a NOT NULL no-default column inserts '' with a warning
-- rather than erroring. Hard fail-loud therefore requires enabling strict mode.
-- Until then, enforcement lives in the application layer (front-end + MCP always
-- provide the values); dropping the default guarantees the DB itself never
-- fabricates one — so a genuinely missing value shows up as an obviously-invalid
-- '' rather than a plausible-but-wrong 'xhigh' that hides the omission.
--
-- swarm_sessions.effort keeps a 'high' default: sessions are system-created via
-- MCP (always explicit), and req #3007 sets their default effort to 'high'
-- (was 'xhigh' from migration 063). ai_model there already defaults to 'opus'.

ALTER TABLE requirements ALTER COLUMN ai_model DROP DEFAULT;
ALTER TABLE requirements ALTER COLUMN effort   DROP DEFAULT;

ALTER TABLE swarm_sessions ALTER COLUMN effort SET DEFAULT 'high';
