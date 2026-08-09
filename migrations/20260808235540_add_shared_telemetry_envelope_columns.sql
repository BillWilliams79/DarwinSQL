-- 20260808235540_add_shared_telemetry_envelope_columns.sql
--
-- Req #3202: give every container that records "a Claude run happened" the SAME
-- measurement envelope, defined once.
--
-- PROBLEM.  Darwin measures two things that are the same KIND of thing — a
--           Claude run — in two independently-invented shapes, and the fields
--           they genuinely share are stored twice with no guarantee they mean
--           the same thing.
--
--             * Units already disagreed. Domain A recorded wall clock in
--               SECONDS (`swarm_starts.wall_seconds`,
--               `swarm_sessions.wall_secs_total`); domain B in MILLISECONDS
--               (`agent_telemetry_rows.boot_time_ms`). Two numbers that cannot
--               be compared without knowing which is which.
--             * Token coverage was incomplete and uneven.
--               `swarm_sessions` stored `output_tokens_total` and nothing else,
--               so "what did this session cost" was unanswerable from a bounded
--               read — output alone cannot price a run when input, cache-write
--               and cache-read are billed differently. `agent_telemetry_runs`
--               stored NO run-level tokens at all.
--             * Nothing recorded WHAT WAS ASKED. There is no input prompt
--               anywhere in either domain.
--
-- SHAPE.    Eight columns, identical name and identical type on all four
--           envelope-bearing tables:
--
--             wall_ms             BIGINT   NULL   -- the ONE wall-clock unit
--             tokens_input        INT      NULL
--             tokens_cache_write  INT      NULL
--             tokens_cache_read   INT      NULL
--             tokens_output       INT      NULL
--             prompt_text         TEXT     NULL   -- bounded PREFIX, 2000 chars
--             prompt_sha256       CHAR(64) NULL   -- hash of the FULL prompt
--             prompt_chars        INT      NULL   -- length of the FULL prompt
--
--           `swarm_starts` and `swarm_completes` already carry the four
--           `tokens_*` columns with exactly these names and types, so the
--           envelope ADOPTED their spelling rather than inventing a parallel
--           one; those two tables gain only `wall_ms` and the three prompt
--           columns.
--
--           WHY THE COLUMNS AND NOT A SHARED `telemetry_runs` TABLE. A shared
--           table both domains FK to has the cleaner query story and was
--           REJECTED on a measured platform constraint, not a preference:
--           Lambda-Rest has no JOIN. Req #3186 already recorded what that costs
--           — deriving a fact that lives on another table is "SIX list reads per
--           render", the fan-out req #3080 design rule 5 forbids. Req #3117 is
--           the precedent pointing the other way: it moved a rollup ONTO the row
--           precisely because "a rollup the render path cannot read is no rollup
--           at all". A shared table would put every run's cost one hop from
--           every surface that renders it.
--
--           The stated price of duplicating columns is that nothing structurally
--           prevents drift. That is true of a convention and false of a derived
--           check: `scripts/telemetry/envelope.py` holds the ONE declaration and
--           `DarwinSQL/tests/test_telemetry_envelope.py` parses THIS schema and
--           fails the build if any envelope table's columns or types disagree
--           with it — the same derive-from-the-DDL mechanism
--           `CREATOR_TABLE_REFERENCES` (req #3125) uses.
--
--           WHY EVERY COLUMN IS NULLABLE WITH NO DEFAULT. Req #3117's rule: a
--           row that was never measured must contribute NOTHING to an aggregate
--           rather than a zero that silently drags an average down. NULL means
--           "not measured"; 0 means "measured, and it was zero". Every one of
--           the ~1,900 existing rows across these four tables is pre-envelope and
--           lands NULL, which is the correct claim about them. There is NO
--           BACKFILL and there deliberately cannot be one: the transcripts those
--           runs were measured from are rotated (90 days,
--           rotate-swarm-archive.sh) or already deleted with their worktrees, so
--           any value written now would be fabricated.
--
--           WHY wall_ms IS BIGINT WHERE THE TOKEN COUNTS ARE INT. A signed INT
--           of milliseconds overflows at ~24.8 days; `swarm_sessions` rows
--           legitimately span longer than that (a paused session accrues
--           `paused_secs` for as long as it is parked). A single run reaching
--           2.1 billion tokens is not a thing.
--
--           WHY THE PROMPT IS THREE COLUMNS AND NOT ONE. Storing the full text
--           on every row is real storage and pushes against Lambda's 6 MB
--           response cap and the 1 MB MCP list-read budget (req #3078), so
--           `prompt_text` holds a bounded 2000-char PREFIX and is declared HEAVY
--           in darwin-mcp's projection map — dropped from every list read, like
--           `telemetry` and `plan` already are. Clipping the text would destroy
--           the ability to ask "were these two runs the same prompt", so
--           `prompt_sha256` hashes the FULL text and `prompt_chars` records its
--           FULL length: the prefix is visibly a prefix and identity is still
--           exact. On CONTENT: a swarm auto-prompt names a requirement id and a
--           worktree path, both of which already live in `requirements` and
--           `swarm_sessions` under the same `creator_fk` — no new exposure class,
--           so a hash-only record would give up the answer to "what was asked"
--           in exchange for nothing.
--
--           The legacy seconds columns (`wall_seconds`, `wall_secs_total`) and
--           `output_tokens_total` are NOT dropped. They have live consumers in
--           Darwin, darwin-mcp and the swarm scripts, and they are now written
--           from the same value by the same writer, so the two units on one row
--           cannot disagree.
--
--           No FK is added, so `CREATOR_TABLE_REFERENCES` (req #3125) is
--           unchanged — these are plain scalar columns on tables that already
--           carry `creator_fk`.
--
-- ORDER OF OPERATIONS — this migration must reach PRODUCTION BEFORE the darwin-mcp
--           daemon restarts on code that declares the new columns. darwin-mcp
--           projects `fields=` on every list read of `swarm_sessions`,
--           `swarm_starts` and `swarm_completes`, and Lambda-Rest 400s the WHOLE
--           read on an unknown field name. Recorded in memory/database.md
--           § Schema Migration Workflow and in darwin-mcp/services/common.py.
--
-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file. A
--           `USE` is a statement, not a declaration: it re-points the session
--           the moment it executes and overrides whatever database the caller
--           named — which on 2026-08-01 sent a dev-aimed apply to production.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--           If this migration may only be applied to ONE database, say so as a
--           constraint instead: `-- darwin:targets = darwin`.
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260808235540_add_shared_telemetry_envelope_columns.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260808235540_add_shared_telemetry_envelope_columns.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20260808235540` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20260808235540 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

-- ---------------------------------------------------------------------------
-- Domain A — swarm session lifecycle
-- ---------------------------------------------------------------------------

-- swarm_sessions: the full envelope. The four token columns COMPLETE what
-- req #3117's `output_tokens_total` started — the same server-side rollup over
-- `phase_tokens`, now for all four priced token types instead of output alone —
-- and `wall_ms` is `wall_secs_total` in the envelope's unit. All five stay
-- server-managed (darwin-mcp rejects a caller that writes them); the three
-- prompt columns are caller-written.
ALTER TABLE swarm_sessions
    ADD COLUMN wall_ms            BIGINT   NULL AFTER output_tokens_total,
    ADD COLUMN tokens_input       INT      NULL AFTER wall_ms,
    ADD COLUMN tokens_cache_write INT      NULL AFTER tokens_input,
    ADD COLUMN tokens_cache_read  INT      NULL AFTER tokens_cache_write,
    ADD COLUMN tokens_output      INT      NULL AFTER tokens_cache_read,
    ADD COLUMN prompt_text        TEXT     NULL AFTER tokens_output,
    ADD COLUMN prompt_sha256      CHAR(64) NULL AFTER prompt_text,
    ADD COLUMN prompt_chars       INT      NULL AFTER prompt_sha256;

-- swarm_starts / swarm_completes already carry the four `tokens_*` columns with
-- exactly the envelope's names and types — that is why the envelope adopted
-- their spelling. They need only the wall-clock unit and the prompt.
ALTER TABLE swarm_starts
    ADD COLUMN wall_ms       BIGINT   NULL AFTER wall_seconds,
    ADD COLUMN prompt_text   TEXT     NULL AFTER turn_count,
    ADD COLUMN prompt_sha256 CHAR(64) NULL AFTER prompt_text,
    ADD COLUMN prompt_chars  INT      NULL AFTER prompt_sha256;

ALTER TABLE swarm_completes
    ADD COLUMN wall_ms       BIGINT   NULL AFTER wall_seconds,
    ADD COLUMN prompt_text   TEXT     NULL AFTER turn_count,
    ADD COLUMN prompt_sha256 CHAR(64) NULL AFTER prompt_text,
    ADD COLUMN prompt_chars  INT      NULL AFTER prompt_sha256;

-- ---------------------------------------------------------------------------
-- Domain B — agent context composition
-- ---------------------------------------------------------------------------

-- agent_telemetry_runs had NO run-level cost at all: `boot_time_ms` is per-AGENT
-- (on agent_telemetry_rows) and measures one agent's boot, not what the capture
-- run itself spent. The full envelope makes an agent capture comparable to a
-- swarm session for the first time. The 10-way context decomposition on
-- agent_telemetry_rows is untouched — req #3202 is explicit that the domain
-- decompositions stay and must not be flattened into the envelope.
ALTER TABLE agent_telemetry_runs
    ADD COLUMN wall_ms            BIGINT   NULL AFTER effort,
    ADD COLUMN tokens_input       INT      NULL AFTER wall_ms,
    ADD COLUMN tokens_cache_write INT      NULL AFTER tokens_input,
    ADD COLUMN tokens_cache_read  INT      NULL AFTER tokens_cache_write,
    ADD COLUMN tokens_output      INT      NULL AFTER tokens_cache_read,
    ADD COLUMN prompt_text        TEXT     NULL AFTER tokens_output,
    ADD COLUMN prompt_sha256      CHAR(64) NULL AFTER prompt_text,
    ADD COLUMN prompt_chars       INT      NULL AFTER prompt_sha256;
