-- Migration 048: Add affected_repos column to requirements (req #2583)
--
-- Per-requirement override for the worktree composition that /swarm-start
-- creates. When NULL (default), /swarm-start uses the category-default
-- sub-repos table (Swarm → [], Topology → [Darwin, Topology], everything
-- else → [Darwin]). When set, the comma-separated list overrides that
-- default. DarwinAI-Config is unconditionally first regardless (req #2232).
--
-- Motivating incident: the 2026-05-22 mega launch shipped three deployed
-- sessions (req #2425, #2566, #2568) with empty PRs. Reqs 2425 and 2566
-- were filed in the Swarm category (category default: [] = config only)
-- but described Darwin UI work — the worker spun up a worktree containing
-- only DarwinAI-Config, found no Darwin to edit, and /swarm-complete
-- closed the empty PR. Silent failure. Per-requirement override is the
-- surgical fix at the right granularity: a single category routinely
-- mixes work across sub-repos and the category-default-only model
-- doesn't reflect that.
--
-- Format: comma-separated sub-repo names (no whitespace required but
-- tolerated; the skill trims tokens). Examples: "Darwin", "Darwin,Topology",
-- "Lambda-Rest,DarwinSQL". NULL = use category default.
--
-- VARCHAR(255) is generous — the longest possible legitimate value
-- ("Darwin,DarwinSQL,Lambda-Rest,Lambda-Cognito,Lambda-JWT,Topology" ≈ 60
-- chars) fits comfortably with room for future sub-repos.

ALTER TABLE requirements
    ADD COLUMN affected_repos VARCHAR(255) NULL
    COMMENT 'Comma-separated sub-repo names override (req #2583); NULL falls back to category default.';
