-- 044_add_testruns.sql
--
-- Req #2380 Phase 3: add the test_runs + test_results tables.
-- Depends on migration 043 (Phase 2 tables) being live.
--
-- test_runs    — one execution of a test_plan. run_status in_progress|completed|
--                aborted. started_at set on creation; completed_at set on
--                terminal status. No closed column (execution tables close via
--                terminal status); no sort_order (chronological by started_at).
-- test_results — one per (run, case). result_status passed|failed|blocked|
--                skipped|not_run. UNIQUE (test_run_fk, test_case_fk) enforces
--                one result per case per run. executed_at set when the result
--                is actually recorded (nullable until then).
--
-- FK policy:
--   test_runs.test_plan_fk     → test_plans(id)  ON DELETE RESTRICT
--                                (a plan with run history cannot be deleted)
--   test_runs.creator_fk       → profiles(id)   ON DELETE CASCADE
--   test_results.test_run_fk   → test_runs(id)   ON DELETE CASCADE
--                                (deleting a run deletes its results)
--   test_results.test_case_fk  → test_cases(id)  ON DELETE RESTRICT
--                                (cannot delete a case with results on record)
--   test_results.creator_fk    → profiles(id)   ON DELETE CASCADE

CREATE TABLE test_runs (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    test_plan_fk    INT             NOT NULL,
    run_status      VARCHAR(16)     NOT NULL DEFAULT 'in_progress', -- in_progress|completed|aborted
    started_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP       NULL,
    notes           TEXT            NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_test_runs_plan
        FOREIGN KEY (test_plan_fk) REFERENCES test_plans (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_test_runs_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE test_results (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    test_run_fk     INT             NOT NULL,
    test_case_fk    INT             NOT NULL,
    result_status   VARCHAR(16)     NOT NULL DEFAULT 'not_run',     -- passed|failed|blocked|skipped|not_run
    actual          TEXT            NULL,
    notes           TEXT            NULL,
    executed_at     TIMESTAMP       NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_test_results_run
        FOREIGN KEY (test_run_fk) REFERENCES test_runs (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_test_results_case
        FOREIGN KEY (test_case_fk) REFERENCES test_cases (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_test_results_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_run_case UNIQUE KEY (test_run_fk, test_case_fk)
);
