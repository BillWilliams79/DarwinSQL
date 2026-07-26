-- 074_add_agent_telemetry_row_docs.sql
--
-- Req #3096: Per-document actual-token capture for architecture/autoload docs.
--
-- PROBLEM. agent_telemetry_rows (migration 069) stores only an AGGREGATE per-agent
-- autoload_tokens figure (the whole autoload set's actual-token weight) plus
-- docs_loaded/docs_expected COUNTS. There is no per-document breakdown of WHICH
-- document contributed HOW MANY actual tokens anywhere that reaches the UI — the
-- only existing per-document figure is agent-context-telemetry.py's chars/4
-- ESTIMATE, which is transient (scripts/agents/out/telemetry/<slug>.json only)
-- and never persisted. This is the storage half of closing that gap — extract-
-- actual-tokens.py now attributes each turn-to-turn transcript usage delta to the
-- single autoload document Read that caused it (real tokenizer, never chars/4).
--
-- SHAPE. One more parent/child level under the existing run -> rows shape
-- (agent_telemetry_runs -> agent_telemetry_rows): agent_telemetry_row_docs is a
-- child of agent_telemetry_rows ONLY, FK'd to its immediate parent alone — no
-- redundant run_fk (the `builds -> branches` precedent: builds carries only
-- branch_fk, not a denormalized project_fk, even though builds -> branches ->
-- build_projects is a real 3-level chain). No FK to architecture_documents
-- either: agent_telemetry_rows.agent_name is already plain text, not FK'd to
-- agents.id, because this is a historical log/snapshot table whose rows must
-- keep meaning even if the live registry entry it was measured against is later
-- renamed or deleted — doc_path follows that same convention.
--
-- row_fk CASCADEs: the row is the container for its own documents, same as the
-- run is the container for its rows. actual_tokens is NOT NULL (unlike the
-- nullable token columns on the parent row) — a doc row only exists once it has
-- been measured, so there is no "phase not applicable" case here to leave NULL.
--
-- PRODUCTION table (darwin + darwin_dev), same call as its parent — the report
-- route renders in the deployed app, so the rows must live in production `darwin`.

CREATE TABLE agent_telemetry_row_docs (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    row_fk          INT          NOT NULL,                    -- agent_telemetry_rows(id), CASCADE
    doc_path        VARCHAR(512) NOT NULL,                     -- repo-relative location, e.g. "memory/aws-architecture.md"
    actual_tokens   INT          NOT NULL,                     -- real-tokenizer weight of this one document
    sort_order      SMALLINT     NULL,                         -- render order within the row (autoload_documents order)
    creator_fk      VARCHAR(64)  NOT NULL,
    create_ts       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_telemetry_row_docs_row
        FOREIGN KEY (row_fk) REFERENCES agent_telemetry_rows (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_agent_telemetry_row_docs_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_agent_telemetry_row_docs_row_fk ON agent_telemetry_row_docs (row_fk);
