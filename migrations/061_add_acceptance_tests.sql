-- 061_add_acceptance_tests.sql
--
-- Req #2633: New data type — Acceptance Test (AT).
--
-- An Acceptance Test is a named test gate a software release must pass before
-- the release event is approved. ATs are a reusable CATALOG (Build AT, Daily
-- AT, Sprint AT, Functional AT, OEM AT, RC AT, Cert AT); each branch is
-- assigned a set of required ATs (the branch-type -> AT matrix lives in the
-- frontend config map). A single pass/fail status is recorded PER BRANCH.
--
-- DARWIN_DEV ONLY. The Build Visualizer data model lives only in `darwin_dev`
-- after req #2760 (the 5 build-viz tables were dropped from production
-- `darwin` by migration 057). These two tables + the branches column follow
-- the same rule: apply to `darwin_dev`, never to production `darwin`. They are
-- carried in the dev-superset (schema.sql + scripts/recreate_darwin_dev.sql).
--
-- acceptance_tests          catalog table. Follows the build-viz CATALOG shape
--                           (mirrors `customers`): closed + sort_order, NO
--                           category_fk. Adds:
--                             acceptance_test_status  pass|fail (default pass)
--                             expected_wall_mins      user-set expected wall
--                                                     clock, in minutes.
-- branch_acceptance_tests   junction: which branch-level ATs apply to a branch.
--                           Composite PK, CASCADE both sides, sort_order for
--                           per-branch label stacking. (Build AT is render-only
--                           per build and is NOT stored here.)
-- branches.acceptance_test_status  single pass/fail covering the branch's
--                           branch-level ATs (drives the green/red AT glyph;
--                           build dot color + approved_for_release untouched).
--
-- No circular FKs here (acceptance_tests -> profiles; junction -> branches +
-- acceptance_tests; all referenced tables pre-exist), so no deferred ALTER /
-- FK-checks-off block is needed.

CREATE TABLE IF NOT EXISTS acceptance_tests (
    id                      INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title                   VARCHAR(256)    NOT NULL,                 -- AT name, e.g. "Sprint AT"
    description             TEXT            NULL,
    acceptance_test_status  VARCHAR(16)     NOT NULL DEFAULT 'pass',  -- pass|fail (default pass)
    expected_wall_mins      INT             NULL,                     -- user-set expected wall clock, minutes
    closed                  TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order              SMALLINT        NULL,
    creator_fk              VARCHAR(64)     NOT NULL,
    create_ts               TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts               TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_acceptance_tests_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS branch_acceptance_tests (
    branch_fk           INT         NOT NULL,
    acceptance_test_fk  INT         NOT NULL,
    sort_order          SMALLINT    NULL,   -- per-branch AT label stacking order
    PRIMARY KEY (branch_fk, acceptance_test_fk),
    CONSTRAINT fk_bat_branch
        FOREIGN KEY (branch_fk) REFERENCES branches (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_bat_acceptance_test
        FOREIGN KEY (acceptance_test_fk) REFERENCES acceptance_tests (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

ALTER TABLE branches
    ADD COLUMN acceptance_test_status VARCHAR(16) NULL DEFAULT 'pass' AFTER external_id;
