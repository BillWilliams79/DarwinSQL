-- 20260809081441_add_pipeline2_epic2_attribution_columns_to_swarm_sessions.sql
--
-- Req #3350: re-point swarm-session orchestration attribution at the
-- Pipeline 2.0 step walk, so ONE decision produces BOTH columns and they
-- cannot disagree.
--
-- PROBLEM.  `swarm_sessions.pipeline_fk` / `.epic_fk` (req #3186) are
--           resolved by TWO INDEPENDENT walks over the 1.0 schema —
--           `pipeline_step_requirements -> pipeline_steps -> pipelines` and
--           `requirements -> features -> epics` — and the code's own comment
--           states the premise: "the two facts are unrelated (the schema
--           does not relate a pipeline to an epic)". Measured: 2 of 1102
--           live sessions (ids 2696, 2533; the 2026-08-04 finding cited 1 —
--           the defect kept firing) carry a non-NULL epic_fk with a NULL
--           pipeline_fk: "epic E, no plan", which under 2.0 containment
--           (an epic IS in exactly one pipeline) is unstateable.
--
-- SHAPE.    CLEAN-BREAK ATTRIBUTION (user ruling, stage-2 gate 2026-08-08):
--           `pipeline2_fk` / `epic2_fk`, both nullable, sit BESIDE the
--           existing 1.0 pair rather than replacing it — the exact shape
--           req #3369 already used for `orchestration_claims.pipeline2_fk` /
--           `.epic2_fk` (migration 20260809024954), for the same reason: an
--           FK is a static declaration, not an alternation, so re-pointing
--           the existing `swarm_sessions` FKs at the 2.0 tables would fail
--           every still-live 1.0 stamp outright (memory/pipeline-2-data-
--           architecture.md § 9.4). The darwin-mcp stamping resolver becomes
--           DUAL-ERA TRANSITIONAL GLUE: it picks the era by WHICH junction
--           seats the requirement (2.0 preferred, 1.0 fallback) and writes
--           only that era's columns, one walk producing both. No 2.0 code
--           path ever reads the 1.0 columns; both pairs are ARCHIVED AND
--           DROPPED at #3356, not retired in place.
--
--           UNLIKE `orchestration_claims`, THE FK ACTION STAYS `SET NULL`,
--           not CASCADE. `orchestration_claims` is a mutual-exclusion
--           device — a reservation on a deleted plan is a reservation on
--           nothing and should not survive it. `swarm_sessions` is HISTORY
--           (migration 20260801020944's own reasoning for the 1.0 pair,
--           reproduced here for the 2.0 pair): session history must never
--           block deleting a pipeline2 plan or epic, and a session's own
--           record of "which plan was I advancing" should not vanish just
--           because that plan was later deleted. So `pipeline2_fk` /
--           `epic2_fk` stay `ON UPDATE CASCADE ON DELETE SET NULL`, matching
--           the 1.0 pair exactly.
--
--           NO NULLABLE-FLIP NEEDED HERE. `orchestration_claims.pipeline_fk`
--           had to become nullable in its own 2.0 migration because era
--           there is discriminated by "which pair is non-NULL" on a
--           MUTUAL-EXCLUSION row. `swarm_sessions` carries no such
--           discrimination requirement — both pairs are independently
--           nullable already (`pipeline_fk`/`epic_fk` have been
--           `NULL DEFAULT NULL` since migration 20260801020944) and a
--           session's attribution can legitimately be 1.0-only, 2.0-only,
--           both, or neither.
--
-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file. A
--           `USE` is a statement, not a declaration: it re-points the session
--           the moment it executes and overrides whatever database the caller
--           named — which on 2026-08-01 sent a dev-aimed apply to production.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--           No `-- darwin:targets` declaration: additive nullable columns are
--           safe on both `darwin_dev` and `darwin`.
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260809081441_add_pipeline2_epic2_attribution_columns_to_swarm_sessions.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260809081441_add_pipeline2_epic2_attribution_columns_to_swarm_sessions.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20260809081441` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20260809081441 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

ALTER TABLE swarm_sessions
    ADD COLUMN pipeline2_fk INT NULL DEFAULT NULL,  -- 2.0 scope; stamped beside pipeline_fk
    ADD COLUMN epic2_fk     INT NULL DEFAULT NULL;  -- 2.0 scope; stamped beside epic_fk

ALTER TABLE swarm_sessions
    ADD CONSTRAINT fk_swarm_sessions_pipeline2
        FOREIGN KEY (pipeline2_fk) REFERENCES pipeline2_pipelines (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    ADD CONSTRAINT fk_swarm_sessions_epic2
        FOREIGN KEY (epic2_fk) REFERENCES pipeline2_epics (id)
        ON UPDATE CASCADE ON DELETE SET NULL;
