-- Migration 032: Add telemetry column to swarm_sessions
--
-- telemetry: free-form text scratchpad for skills to append debug/diagnostic data
--            (terminal name issues, dev server problems, MCP failures, etc.)
--            Any skill may read/modify/write this field.

ALTER TABLE swarm_sessions
    ADD COLUMN telemetry TEXT NULL AFTER complete_summary;
