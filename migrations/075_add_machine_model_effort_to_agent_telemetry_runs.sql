-- 075_add_machine_model_effort_to_agent_telemetry_runs.sql
--
-- Req #3098: capture WHICH machine, WHICH Claude model, and WHAT effort level
-- ran each agent-context telemetry capture.
--
-- agent_telemetry_runs (migration 069) already stores `captured_at` (WHEN) and
-- `harness_version` (Claude Code build), surfaced in the /agents/context header
-- under req #3065. It has no columns for WHERE the capture ran, or under which
-- model/effort — some historical runs mention these informally in free-text
-- `source_note` (e.g. "WSL Test on machine_fk=3", "per-call model:sonnet
-- override"), but that is prose, not queryable/displayable data.
--
-- machine_fk: nullable FK to `machines` (req #2943, migration 064), same
-- convention as swarm_sessions/swarm_starts/dev_servers: ON UPDATE CASCADE ON
-- DELETE RESTRICT (a machine with capture history cannot be hard-deleted;
-- retire it via `closed` instead).
--
-- ai_model / effort: NOT NULL with a fixed DEFAULT ('opus' / 'high') for BOTH
-- the backfill of the 3 pre-existing rows AND all future inserts. This mirrors
-- swarm_starts/swarm_completes (migration 065) rather than
-- requirements/swarm_sessions (whose ai_model/effort are user-editable current
-- settings, and whose swarm_sessions.effort default was later bumped to
-- 'xhigh'): a telemetry run is a terminal capture-log row recording what
-- already happened, not a setting someone edits going forward, so a single
-- fixed default for "unknown historical value" is correct permanently, the
-- same reasoning migration 065 gives for swarm_starts/swarm_completes.
--
-- No structured backfill of the 3 existing runs' free-text source_note here —
-- filed as explicitly optional/low-priority in req #3098; parsing prose
-- reliably for 3 rows isn't worth the misattribution risk. They land on the
-- column DEFAULT like migration 065's unparseable-telemetry rows do.

ALTER TABLE agent_telemetry_runs
    ADD COLUMN ai_model   VARCHAR(16) NOT NULL DEFAULT 'opus' AFTER source_note,
    ADD COLUMN effort     VARCHAR(16) NOT NULL DEFAULT 'high' AFTER ai_model,
    ADD COLUMN machine_fk INT         NULL                    AFTER effort,
    ADD CONSTRAINT fk_agent_telemetry_runs_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;
