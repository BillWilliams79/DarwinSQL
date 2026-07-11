-- 065_add_ai_model_effort_to_starts_completes.sql
--
-- Req #2949: promote ai_model/effort to dedicated, queryable columns on
-- swarm_starts and swarm_completes, mirroring the columns swarm_sessions
-- already has (req #2909 migration 062, req #2916 migration 063). Today the
-- same fact is buried in the `telemetry` TEXT blob (the TOKEN_TELEMETRY JSON
-- written by scripts/swarm/telemetry-capture.sh, keys "model" / "effort"),
-- which requires JSON-parsing free text for a cost-by-model rollup and
-- carries a "[1m]" context-window suffix on primary-session rows
-- (e.g. sonnet[1m]) that needs normalizing.
--
-- Value domains match swarm_sessions:
--   ai_model  VARCHAR(16) NOT NULL DEFAULT 'opus'  -- haiku|sonnet|opus|fable
--   effort    VARCHAR(16) NOT NULL DEFAULT 'high'  -- low|medium|high|xhigh|ultracode
-- Unlike swarm_sessions.effort (whose column DEFAULT was later bumped to
-- 'xhigh' for new rows, req #2916), swarm_starts/swarm_completes keep 'high'
-- as the default for BOTH the backfill and future inserts — these are
-- terminal log rows written once at finalize time with a real telemetry-
-- derived value, not user-editable settings that need a "current" default.
--
-- NOT NULL mirrors requirements.coordination_type (req #2745) and the
-- ai_model/effort precedent above: an unset model/effort is not a
-- meaningful state for a cost-recording row.
--
-- Backfill: ADD COLUMN ... DEFAULT already backfills every historical row to
-- 'opus'/'high'. The UPDATE below then overwrites ONLY rows whose telemetry
-- blob contains a well-formed TOKEN_TELEMETRY JSON payload with a valid,
-- normalizable model/effort — everything else (NULL telemetry, no marker,
-- malformed JSON, or a value outside the enum after normalization, e.g.
-- "unknown") is left at the column DEFAULT rather than fabricating a
-- precise-looking guess.
--
-- Parsing approach: the telemetry text always ends with the JSON payload as
-- the LAST thing appended (see skill-finalize.sh / primary-complete-
-- finalize.sh / swarm-complete.md), immediately after a 'TOKEN_TELEMETRY:'
-- marker line (worker swarm_completes rows use a 'COMPLETE_TOKEN_TELEMETRY:'
-- marker, which still ends in the substring 'TOKEN_TELEMETRY:'). MySQL's
-- SUBSTRING_INDEX(str, delim, -1) returns everything after the LAST
-- occurrence of delim, so it recovers the JSON payload regardless of which
-- marker variant was used. JSON_VALID() guards against malformed/absent
-- payloads before JSON_EXTRACT runs (JSON_EXTRACT errors on invalid JSON).
--
-- Normalization mirrors scripts/swarm/normalize_model_effort.py (the live-
-- write helper) — keep both in sync if the enum domains change:
--   model:  REGEXP_REPLACE(raw, '\\[[^]]*\\]$', '') strips a trailing
--           bracketed suffix ('sonnet[1m]' -> 'sonnet'), then validated
--           against the enum.
--   effort: 'max' -> 'ultracode', then validated against the enum.

ALTER TABLE swarm_starts
    ADD COLUMN ai_model VARCHAR(16) NOT NULL DEFAULT 'opus' AFTER session_count,
    ADD COLUMN effort   VARCHAR(16) NOT NULL DEFAULT 'high' AFTER ai_model;

ALTER TABLE swarm_completes
    ADD COLUMN ai_model VARCHAR(16) NOT NULL DEFAULT 'opus' AFTER session_count,
    ADD COLUMN effort   VARCHAR(16) NOT NULL DEFAULT 'high' AFTER ai_model;

-- --- Backfill swarm_starts ---
UPDATE swarm_starts s
JOIN (
    SELECT
        id,
        TRIM(SUBSTRING_INDEX(telemetry, 'TOKEN_TELEMETRY:', -1)) AS json_text
    FROM swarm_starts
    WHERE telemetry IS NOT NULL
      AND telemetry LIKE '%TOKEN_TELEMETRY:%'
) t ON t.id = s.id AND JSON_VALID(t.json_text)
SET
    s.ai_model = CASE REGEXP_REPLACE(
                        JSON_UNQUOTE(JSON_EXTRACT(t.json_text, '$.model')),
                        '\\[[^]]*\\]$', '')
                     WHEN 'haiku'  THEN 'haiku'
                     WHEN 'sonnet' THEN 'sonnet'
                     WHEN 'opus'   THEN 'opus'
                     WHEN 'fable'  THEN 'fable'
                     ELSE 'opus'
                 END,
    s.effort = CASE
                   WHEN JSON_UNQUOTE(JSON_EXTRACT(t.json_text, '$.effort')) = 'max' THEN 'ultracode'
                   WHEN JSON_UNQUOTE(JSON_EXTRACT(t.json_text, '$.effort'))
                        IN ('low', 'medium', 'high', 'xhigh', 'ultracode')
                       THEN JSON_UNQUOTE(JSON_EXTRACT(t.json_text, '$.effort'))
                   ELSE 'high'
               END;

-- --- Backfill swarm_completes ---
UPDATE swarm_completes c
JOIN (
    SELECT
        id,
        TRIM(SUBSTRING_INDEX(telemetry, 'TOKEN_TELEMETRY:', -1)) AS json_text
    FROM swarm_completes
    WHERE telemetry IS NOT NULL
      AND telemetry LIKE '%TOKEN_TELEMETRY:%'
) t ON t.id = c.id AND JSON_VALID(t.json_text)
SET
    c.ai_model = CASE REGEXP_REPLACE(
                        JSON_UNQUOTE(JSON_EXTRACT(t.json_text, '$.model')),
                        '\\[[^]]*\\]$', '')
                     WHEN 'haiku'  THEN 'haiku'
                     WHEN 'sonnet' THEN 'sonnet'
                     WHEN 'opus'   THEN 'opus'
                     WHEN 'fable'  THEN 'fable'
                     ELSE 'opus'
                 END,
    c.effort = CASE
                   WHEN JSON_UNQUOTE(JSON_EXTRACT(t.json_text, '$.effort')) = 'max' THEN 'ultracode'
                   WHEN JSON_UNQUOTE(JSON_EXTRACT(t.json_text, '$.effort'))
                        IN ('low', 'medium', 'high', 'xhigh', 'ultracode')
                       THEN JSON_UNQUOTE(JSON_EXTRACT(t.json_text, '$.effort'))
                   ELSE 'high'
               END;
