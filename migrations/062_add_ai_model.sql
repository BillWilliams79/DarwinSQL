-- 062_add_ai_model.sql
--
-- Req #2909: AI model type on requirements and swarm sessions.
--
-- Adds `ai_model` — which Claude model the swarm worker should run with —
-- to both `requirements` (the user's choice, set alongside autonomy) and
-- `swarm_sessions` (the value captured at launch so the session record is
-- self-describing after the fact).
--
-- Value domain: haiku | sonnet | opus | fable (lowercase; no version numbers —
-- latest is assumed). Default 'opus'; ADD COLUMN ... NOT NULL DEFAULT backfills
-- every historical row to 'opus', which is the documented assumption for all
-- pre-#2909 data.
--
-- NOT NULL mirrors requirements.coordination_type (req #2745): an unset model
-- is not a meaningful state — every requirement and session runs on some model.

ALTER TABLE requirements
    ADD COLUMN ai_model VARCHAR(16) NOT NULL DEFAULT 'opus' AFTER coordination_type;

ALTER TABLE swarm_sessions
    ADD COLUMN ai_model VARCHAR(16) NOT NULL DEFAULT 'opus' AFTER swarm_status;
