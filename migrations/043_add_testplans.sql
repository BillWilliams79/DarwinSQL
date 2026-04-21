-- 043_add_testplans.sql
--
-- Req #2380 Phase 2: add the test_plans + test_plan_cases tables.
-- Depends on migration 042 (Phase 1 tables) being live.
--
-- test_plans       — organizational grouping of test_cases (title + optional
--                    markdown description + category_fk). A plan is executed
--                    by a test_run (Phase 3).
-- test_plan_cases  — junction with execution ordering (sort_order).
--                    Composite PK, no id column.
--
-- FK policy:
--   category_fk  → categories(id)  ON DELETE RESTRICT
--   creator_fk   → profiles(id)    ON DELETE CASCADE
--   junction both sides            ON DELETE CASCADE

CREATE TABLE test_plans (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NULL,
    category_fk     INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_test_plans_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_test_plans_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE test_plan_cases (
    test_plan_fk    INT             NOT NULL,
    test_case_fk    INT             NOT NULL,
    sort_order      SMALLINT        NULL,
    PRIMARY KEY (test_plan_fk, test_case_fk),
    CONSTRAINT fk_tpc_plan
        FOREIGN KEY (test_plan_fk) REFERENCES test_plans (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_tpc_case
        FOREIGN KEY (test_case_fk) REFERENCES test_cases (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
