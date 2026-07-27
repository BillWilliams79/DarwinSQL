-- 074_agent_telemetry_breakdown.sql
--
-- Req #3095 — ground-truth breakdown of the Claude Code base token figure.
--
-- PROBLEM. `agent_telemetry_rows.cc_base_tokens` is a single number computed by
-- SUBTRACTION (cc_base = initial - claude_md - charter_stub - probe_prompt) — it has
-- never been a sum of independently-measured pieces, despite the glossary defining
-- "Claude Code" as harness instructions + tool schemas + skills listing + MCP listing.
--
-- FEASIBILITY (verified empirically, req #3095). Claude Code's own `/context` command,
-- scripted non-interactively (`claude -p "/context" --resume <session_id> --model
-- <model> --output-format json`), reports a categorized breakdown — System prompt,
-- System tools, MCP tools, Skills, Custom agents, Memory files, Messages, Compact
-- buffer, Free space — as real numbers (cross-checked against real API `usage` for the
-- same turn to within a few percent, far tighter than a chars/4-style estimate could
-- ever produce). `scripts/agents/context-breakdown-probe.py` captures this. These five
-- new columns store the first four glossary pieces plus a fifth real, measurable
-- category (other-custom-agent listing) that was not in the original glossary but is
-- part of the same breakdown.
--
-- SHAPE. Five new nullable INT columns on `agent_telemetry_rows`, matching how
-- `claude_md_tokens`/`charter_stub_tokens` are already modeled — a fixed, small,
-- well-known set of named pieces, not a variable-length collection, so a child table
-- (à la test_runs -> test_results) is not warranted here. All ACTUAL tokens (never
-- chars/4). NULL where a row's breakdown was not captured — never fabricated; an
-- existing run's rows simply get NULL in these columns until re-captured.
--
-- PRODUCTION table (darwin + darwin_dev), matching migration 069 — the report route
-- renders in the deployed app, so the columns must exist in production `darwin`;
-- darwin_dev carries the same schema for dev review.

ALTER TABLE agent_telemetry_rows
    ADD COLUMN system_prompt_tokens  INT NULL AFTER cc_base_tokens,   -- harness instructions (Claude Code's "System prompt" category)
    ADD COLUMN system_tools_tokens   INT NULL AFTER system_prompt_tokens,  -- built-in tool schemas ("System tools")
    ADD COLUMN mcp_tools_tokens      INT NULL AFTER system_tools_tokens,   -- MCP tools/resources listing ("MCP tools")
    ADD COLUMN skills_tokens         INT NULL AFTER mcp_tools_tokens,      -- available-skills listing ("Skills")
    ADD COLUMN custom_agents_tokens  INT NULL AFTER skills_tokens;         -- other-custom-agent listing ("Custom agents")
