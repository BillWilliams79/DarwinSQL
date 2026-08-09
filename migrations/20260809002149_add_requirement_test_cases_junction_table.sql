-- 20260809002149_add_requirement_test_cases_junction_table.sql
--
-- Req #3352: create requirement_test_cases, the junction Pipeline 2.0's
-- Feature retirement leaves unowned when test cases re-home from Feature
-- onto Requirement (memory/pipeline-2-mcp-surface.md § 6.4, § 7.6).
--
-- PROBLEM.  Stage 1 decides test cases attach to Requirement, not Feature.
--           `feature_test_cases` is the only table that links a test_case to
--           anything, and no stage-2 schema record claims the replacement —
--           left this way, the re-pointed MCP tools (req #3332) would have
--           no table to write to.
--
-- SHAPE.    `requirement_test_cases (requirement_fk, test_case_fk)`, shaped
--           directly on `feature_test_cases` which it stands beside (that
--           table is NOT dropped here — see below). Composite PRIMARY KEY,
--           both sides CASCADE: a link is neither parent's identity, and a
--           test case that loses its last requirement is still a test case.
--           The table exists because a test case asserts a deliverable and
--           Requirement, not Feature, is the level that organizes
--           deliverables — that is the whole of the design; there is no
--           second shape to weigh against it.
--
-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file. A
--           `USE` is a statement, not a declaration: it re-points the session
--           the moment it executes and overrides whatever database the caller
--           named — which on 2026-08-01 sent a dev-aimed apply to production.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--           No `-- darwin:targets` declaration here, deliberately: this is
--           ordinary DDL that will eventually apply to production too (the
--           data-architecture record's own `planned` requirement is that
--           gate), so declaring `darwin_dev` here would be a target list
--           omitting `darwin` — an ABSOLUTE, unoverridable production ban
--           per db_guard.py that would block that later requirement from
--           ever applying this exact file. Req #3352's darwin_dev-only scope
--           is enforced procedurally, by which command is actually run below.
--
-- APPLY.    darwin_dev ONLY, for this requirement. Production DDL is
--           explicitly out of scope (req #3352 body item 2) and is a later
--           requirement's gate, not this one's:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260809002149_add_requirement_test_cases_junction_table.sql darwin_dev
--
-- Migration id 20260809002149 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

CREATE TABLE IF NOT EXISTS requirement_test_cases (
    requirement_fk  INT             NOT NULL,
    test_case_fk    INT             NOT NULL,
    PRIMARY KEY (requirement_fk, test_case_fk),
    CONSTRAINT fk_rtc_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_rtc_case
        FOREIGN KEY (test_case_fk) REFERENCES test_cases (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- BACKFILL — the 28-row translation (req #3352 body item 0)
-- ---------------------------------------------------------------------------
-- `feature_test_cases` holds 28 rows in PRODUCTION today — 15 on feature 23
-- ("Aggregator Card — Combined Ride Map"), 13 on feature 24 ("Aggregator Card
-- — Photo Aggregation") — and a feature maps to MANY requirements, so there is
-- no mechanical feature -> requirement rule; each row below is a judgement
-- call, made by reading every test case's title/steps/expected text and
-- matching it against the requirement whose acceptance criteria it actually
-- asserts. Recorded here, once, because a test case carries no back-reference
-- to a feature — once `feature_test_cases` is gone (req #3334's eradication,
-- not this migration) the mapping is UNRECOVERABLE if it is not captured now.
--
-- Disposition of all 28 (test_case_fk -> requirement_fk):
--   Feature 23 ("Combined Ride Map", epic #6):
--     1  -> 3174  "Aggregator card renders first..." (hybrid manual+automated;
--                  siblings 2 and 3 both cite #3174 explicitly in their own
--                  steps text, this one does not — LOWER CONFIDENCE, flagged)
--     2  -> 3174  cites req #3174 directly (toggle persistence)
--     3  -> 3174  cites req #3174 directly (scale/cap; also mentions #3315,
--                  but #3315 is `authoring` today and the case's own describe
--                  block is the #3174 component-coverage suite)
--     9  -> 3158  describe block is req #3158 (core story acceptance)
--     10 -> 3158
--     11 -> 3158
--     12 -> 3158
--     13 -> 3158
--     14 -> 3158
--     15 -> 3158
--     16 -> 3159  describe(... req #3159): tests the coordinate feed INTO the
--                  photo layer, so it is #3159's acceptance despite sitting
--                  on feature 23
--     17 -> 3158
--     18 -> 3158
--     27 -> 3174  req #3174 body names this exact case ("Optional E2E: toggle
--                  persistence across reload") as its own recorded-not-required
--                  coverage
--     28 -> 3174  req #3174 body names this exact case ("toggle hidden outside
--                  cards view") the same way
--   Feature 24 ("Photo Aggregation", epic #6):
--     4  -> 3163  pure-function unit coverage (collectPhotosForRuns) — matches
--                  #3163's "add targeted unit coverage for new pure logic"
--     5  -> 3163
--     6  -> 3163
--     7  -> 3163
--     8  -> 3159  core story acceptance (aggregated photo markers)
--     19 -> 3159
--     20 -> 3159
--     21 -> 3159
--     22 -> 3159
--     23 -> 3159
--     24 -> 3163  pure-function unit coverage (gridFitLayout)
--     25 -> 3163  cites req #3163 directly
--     26 -> 3163  cites req #3163 directly
--
-- INSERT IGNORE, not INSERT: this migration applies to darwin_dev NOW, where
-- none of these requirement_fk/test_case_fk ids exist yet (darwin_dev's
-- `test_cases` table is empty), so every row is silently skipped there today
-- — the FK constraint failure becomes a warning per row instead of aborting
-- the whole statement. The SAME file, unmodified, is what req #3352's body
-- names as the later production apply (a separate `planned` requirement's
-- gate, not this one's) — at that point these ids DO exist and the backfill
-- lands for real. One migration file, one act, whichever database it runs
-- against — no second copy of this decision to drift from this one.
INSERT IGNORE INTO requirement_test_cases (requirement_fk, test_case_fk) VALUES
    (3174, 1), (3174, 2), (3174, 3),
    (3158, 9), (3158, 10), (3158, 11), (3158, 12), (3158, 13), (3158, 14), (3158, 15),
    (3159, 16),
    (3158, 17), (3158, 18),
    (3174, 27), (3174, 28),
    (3163, 4), (3163, 5), (3163, 6), (3163, 7),
    (3159, 8), (3159, 19), (3159, 20), (3159, 21), (3159, 22), (3159, 23),
    (3163, 24), (3163, 25), (3163, 26);
