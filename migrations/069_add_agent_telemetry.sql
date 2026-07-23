-- 069_add_agent_telemetry.sql
--
-- Req #3031: Persist agent-context telemetry runs + render the actual-token view.
--
-- PROBLEM. Req #3009/#3025 produced a one-off actual-token characterization of the
-- agents pattern (write-up: memory/agent-context-telemetry.md; visual spec artifact
-- 660a8b6b-b215-4b7a-b5a4-91c31e82460d). It was a snapshot in a markdown table — not
-- stored, not repeatable, not viewable. We want to WATCH context cost move as the
-- registry, the skill set, the MCP surface, and the Claude Code harness change, so
-- each capture must persist as data and the published view must render from it.
--
-- SHAPE. A run header + N per-agent rows — the parent/child shape Darwin already has
-- (test_runs -> test_results). The run is the container: deleting it CASCADEs its
-- rows. Every capture is the SAME schema with a VARIABLE number of agent rows —
-- nothing here assumes a fixed roster, so a future run with more/fewer agents (or a
-- reviewer/primary alongside the architects) stores and renders as-is.
--
-- All token columns are ACTUAL tokens (real tokenizer via transcript usage deltas),
-- never chars/4 estimates. They are nullable where a phase does not apply: PrimaryAI
-- is a top-level session with no boot/autoload phase; the Code Reviewer bundles its
-- charter stub into CC base.
--
-- PRODUCTION tables (darwin + darwin_dev). The report route renders in the deployed
-- app, so the rows must live in production `darwin`; darwin_dev carries the same
-- schema for dev review. Same call as the agents registry (migration 067) and
-- `machines` (migration 064): first-class production concern, NOT darwin_dev-only.
--
-- Log/infrastructure tables describing the tooling itself, so — same call as
-- `machines`/`swarm_starts` — NO `title`, NO status enum, NO `closed` flag, and NO
-- `category_fk`. `label` is the human name; `captured_at` is the event timestamp.

-- ---------------------------------------------------------------------------
-- agent_telemetry_runs — one row per capture (the run header).
--
-- `agent_count` is the value the capture recorded at write time (denormalized for a
-- cheap list view); the live COUNT of child rows is the display source of truth, the
-- same relationship swarm_starts.session_count has to its junction.
-- ---------------------------------------------------------------------------
CREATE TABLE agent_telemetry_runs (
    id               INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    captured_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- when this capture ran
    label            VARCHAR(256) NOT NULL,                            -- human name, e.g. "2026-07-22 baseline"
    agent_count      INT          NOT NULL DEFAULT 0,                  -- rows recorded at capture time (live COUNT is canon)
    harness_version  VARCHAR(64)  NULL,                                -- Claude Code harness version at capture
    source_note      TEXT         NULL,                                -- freeform provenance / method note
    creator_fk       VARCHAR(64)  NOT NULL,
    create_ts        TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts        TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_telemetry_runs_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_agent_telemetry_runs_captured_at ON agent_telemetry_runs (captured_at);

-- ---------------------------------------------------------------------------
-- agent_telemetry_rows — one row per agent measured in a run (variable N).
--
-- run_fk CASCADEs: the run is the container, deleting it takes its rows. Token
-- columns are ACTUAL tokens, nullable where the phase is n/a. `sort_order` fixes the
-- render order within a run (architects first, PrimaryAI last, matching the published
-- artifact) independent of insertion order. `footnote` holds the per-row asterisk/
-- dagger text the artifact carries (Code Reviewer's pinned-tools note, PrimaryAI's
-- top-level-session note).
-- ---------------------------------------------------------------------------
CREATE TABLE agent_telemetry_rows (
    id                          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    run_fk                      INT          NOT NULL,
    agent_name                  VARCHAR(128) NOT NULL,                        -- display label, e.g. "AWS", "Darwin PrimaryAI"
    role                        VARCHAR(16)  NOT NULL DEFAULT 'architect',    -- architect|reviewer|primary
    session_kind                VARCHAR(16)  NOT NULL DEFAULT 'subagent',     -- subagent|top_level
    boot_time_ms                INT          NULL,                            -- sequential boot latency; NULL for PrimaryAI
    cc_base_tokens              INT          NULL,                            -- Claude Code base (harness + tool schemas + listings)
    claude_md_tokens            INT          NULL,                            -- CLAUDE.md
    charter_stub_tokens         INT          NULL,                            -- charter stub; NULL when bundled/n/a
    boot_payload_tokens         INT          NULL,                            -- context added by the boot call; NULL for PrimaryAI
    autoload_tokens             INT          NULL,                            -- context added by reading autoload docs; NULL for PrimaryAI
    docs_loaded                 INT          NULL,                            -- autoload documents actually loaded
    docs_expected               INT          NULL,                            -- autoload documents expected
    start_work_context_tokens   INT          NULL,                            -- total ready-to-work context (the /context figure)
    footnote                    VARCHAR(512) NULL,                            -- per-row caveat text (the artifact's *, dagger)
    sort_order                  SMALLINT     NULL,                            -- render order within the run
    creator_fk                  VARCHAR(64)  NOT NULL,
    create_ts                   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts                   TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_telemetry_rows_run
        FOREIGN KEY (run_fk) REFERENCES agent_telemetry_runs (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_agent_telemetry_rows_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_agent_telemetry_rows_run_fk ON agent_telemetry_rows (run_fk);
