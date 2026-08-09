-- 20260809024954_add_orchestration_claims_parallel_era_reservation_columns.sql
--
-- Req #3369: let `orchestration_claims` reserve a 2.0 (pipeline2_*) scope as
-- well as a 1.0 one, so the single-orchestrator guarantee still holds when a
-- human is orchestrating pipeline 2 in 1.0 and its 2.0 image at the same time.
--
-- PROBLEM.  memory/pipeline-2-first-principles.md stage 1 said this table is
--           "re-pointed rather than created". memory/pipeline-2-data-architecture.md
--           § 9.4 overturns that: a reservation is a MUTUAL-EXCLUSION device,
--           so two separate tables (1.0's and a hypothetical 2.0-only one)
--           would not exclude each other at all — the exact double-launch
--           req #3224 exists to prevent. And re-pointing the existing FKs at
--           the 2.0 tables does not produce sharing, it produces a 2.0-ONLY
--           table, for three independent reasons:
--
--             * An FK is a static declaration, not an alternation. Point
--               `fk_oc_pipeline` at `pipeline2_pipelines` and every 1.0 claim
--               fails FK 1452 — 1.0 orchestration stops working outright,
--               while 1.0 is the very plan that builds 2.0.
--             * Mutual exclusion ACROSS two id spaces is not expressible as
--               an FK at all — it needs a service-layer predicate reading
--               rows from both eras, and re-pointing deletes the ability to
--               STORE the rows that predicate would read.
--             * The two AUTO_INCREMENT sequences are a HAZARD, not a
--               guarantee: where they overlap, a 1.0 `pipeline_fk` would
--               numerically satisfy a 2.0 FK while naming a DIFFERENT plan —
--               silent mis-scoping instead of a hard error, strictly worse
--               for a mutual-exclusion device than simply failing.
--
-- SHAPE.    ONE table serving BOTH eras. `pipeline2_fk` / `epic2_fk`, both
--           NULLable, sit BESIDE the existing `pipeline_fk` / `epic_fk` pair
--           rather than replacing them. `pipeline_fk` — NOT NULL since
--           migration 20260801150404 — becomes NULLable here too: era is
--           discriminated by WHICH PAIR IS NON-NULL, and that discrimination
--           is meaningless unless a 2.0-only claim can leave the 1.0 pair
--           empty.
--
--           `epic2_key = COALESCE(epic2_fk, 0)` is the SAME generated-column
--           trick `epic_key` already carries, needed a second time for the
--           same reason req #3224 recorded: MySQL treats NULLs in a UNIQUE
--           index as DISTINCT, so a key written directly over a nullable
--           `epic2_fk` would let TWO 2.0 whole-plan claims on one 2.0
--           pipeline both insert — exactly the collision the constraint
--           exists to stop.
--
--           TWO SEPARATE UNIQUE KEYS, not one widened key, and this is a
--           correction worth stating plainly. `pipeline_fk` is now NULLable
--           on every 2.0 claim, and MySQL's NULL-is-distinct rule means ANY
--           NULL column in a composite key exempts that row from the whole
--           key — so a single key over all four columns would let two 2.0
--           whole-plan claims on the SAME 2.0 pipeline both insert (both rows
--           read `pipeline_fk = NULL`, and NULL is never equal to NULL for
--           uniqueness purposes), identical to the bug `epic_key` was built
--           to close. `uq_orchestration_claims_scope` (unchanged) governs 1.0
--           duplicates; the new `uq_orchestration_claims_scope2` governs 2.0
--           duplicates. Rows of the OTHER era carry NULL in the columns the
--           key does not apply to and are correctly exempt from it — which is
--           what makes two separate keys sufficient rather than a gap.
--
--           BOTH-OR-NEITHER IS AN APPLICATION-LAYER REFUSAL, not a SQL CHECK
--           constraint — Darwin does not use CHECK constraints (see
--           memory/new-data-type-pattern.md and migration
--           20260808101938's `machines.max_live_sessions`: "negative is
--           refused in the application layer, since Darwin does not use CHECK
--           constraints"). `darwin-mcp/services/orchestration_claims.py`
--           refuses a `claim_orchestration` call that names no scope (both
--           pairs NULL) or both scopes (both pairs non-NULL) before ever
--           reaching the database, exactly as `machines.max_live_sessions`
--           refuses a negative ceiling in Lambda-Rest rather than in DDL.
--
--           Both new FKs are `ON DELETE CASCADE`/`ON UPDATE CASCADE`, matching
--           the existing 1.0 pair: a reservation on a deleted 2.0 plan or
--           epic is a reservation on nothing and should not survive it.
--
--           THE CROSS-ERA REFUSAL ITSELF — "a 2.0 claim on a plan whose 1.0
--           image is already claimed is refused, and vice versa" — is also a
--           SERVICE predicate and also lives in
--           `darwin-mcp/services/orchestration_claims.py`, not here: the
--           mapping between a 1.0 plan/epic id and its 2.0 image is DATA (the
--           importer's own id map, scripts/swarm/import_plan_1to2.py), and no
--           schema constraint can read it.
--
--           TRANSITIONAL, and said so in the code it lives in: this whole
--           additive shape exists only for the parallel era. #3356 phase 4
--           drops the 1.0 columns and renames the 2.0 ones at eradication —
--           this migration is that moment's clean seam, not a permanent
--           design.
--
-- TARGET.   No `-- darwin:targets` declaration: this migration is safe on
--           both `darwin_dev` and `darwin`, like the table's original
--           migration (20260801150404).
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260809024954_add_orchestration_claims_parallel_era_reservation_columns.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260809024954_add_orchestration_claims_parallel_era_reservation_columns.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20260809024954` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20260809024954 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

ALTER TABLE orchestration_claims
    MODIFY COLUMN pipeline_fk INT NULL,                  -- 1.0 scope; NULL on a 2.0 claim
    ADD COLUMN pipeline2_fk   INT NULL DEFAULT NULL,      -- 2.0 scope; NULL on a 1.0 claim
    ADD COLUMN epic2_fk       INT NULL DEFAULT NULL,      -- NULL = 2.0 whole-plan scope
    -- Carries the SECOND unique key, the same trick as epic_key, needed again
    -- for the same reason (see SHAPE above).
    ADD COLUMN epic2_key      INT GENERATED ALWAYS AS (COALESCE(epic2_fk, 0)) VIRTUAL;

ALTER TABLE orchestration_claims
    ADD CONSTRAINT fk_oc_pipeline2
        FOREIGN KEY (pipeline2_fk) REFERENCES pipeline2_pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    ADD CONSTRAINT fk_oc_epic2
        FOREIGN KEY (epic2_fk) REFERENCES pipeline2_epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    ADD UNIQUE KEY uq_orchestration_claims_scope2 (pipeline2_fk, epic2_key);

CREATE INDEX ix_orchestration_claims_epic2_fk ON orchestration_claims (epic2_fk);
