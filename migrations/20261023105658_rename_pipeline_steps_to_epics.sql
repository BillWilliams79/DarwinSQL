-- 20261023105658_rename_pipeline_steps_to_epics.sql
--
-- Req #3780 — PASS 2 of the plan-vocabulary rename (req #3772): STEPS BECOME
-- EPICS, everywhere the schema names them. Pass 1 (req #3777, migration
-- 20261023090122) renamed the table that held the name `epics` to
-- `initiatives` and deployed; the census then proved `epic` meant nothing
-- anywhere in the system, and this file claims the vacated name
-- (memory/cross-stack-rename-guide.md § 2, vacate then claim).
--
-- THE HANDOFF ACROSS TWO FILES IS DELIBERATE. `epics` was vacated by
-- 20261023090122 and is claimed here, with a deploy between — the one genuine
-- split a vacate-then-claim rename produces on purpose. Nothing read `epics` in
-- the gap: pass 1's deployed code reads `initiatives`. The pair is recorded in
-- DarwinSQL/tests/test_no_split_drop_rename.py GRANDFATHERED_SPLIT_PAIRS with
-- that reason (guide § 3.1).
--
-- SHAPE.    ONE atomic RENAME TABLE chain for the three tables (metadata-only;
--           InnoDB FKs from engine_outcomes follow the rename automatically).
--           Constraint and index names do NOT follow a RENAME TABLE, so every
--           `*_step*` / `*_pipeline_steps_*` constraint is DROP FOREIGN KEY +
--           ADD CONSTRAINT under its new name (MySQL has no RENAME CONSTRAINT
--           for foreign keys) and every plain index is RENAME INDEX. The
--           junction columns are RENAME COLUMN in the same ALTER as their FKs.
--           The two FK columns that had NO explicit index — `step_fk` on the
--           requirement junction and `step_fk` on engine_outcomes — carry the
--           auto-index InnoDB named after the FK (`fk_psr_step`, `fk_eo_step`);
--           those indexes are renamed too, so a fresh CREATE from schema.sql
--           (which auto-names them `fk_er_epic` / `fk_eo_epic`) and this
--           migration leave byte-identical SHOW CREATE TABLE output for the
--           schema-parity gate. `completed_at` is already gone (req #3752,
--           migration 20261022024615), so nothing else moves.
--
--           Template: 20261023090122 (pass 1). No generated column names a
--           renamed column here, so no DROP COLUMN / ADD COLUMN is needed.
--
-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261023105658_rename_pipeline_steps_to_epics.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261023105658_rename_pipeline_steps_to_epics.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20261023105658` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20261023105658 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

SET FOREIGN_KEY_CHECKS = 0;

-- --- The three tables — one atomic statement, FKs follow automatically -----
RENAME TABLE pipeline_steps TO epics,
             pipeline_step_requirements TO epic_requirements,
             pipeline_step_deps TO epic_deps;

-- --- epics: two FK constraints and its index --------------------------------
ALTER TABLE epics
    DROP FOREIGN KEY fk_pipeline_steps_initiative,
    ADD CONSTRAINT fk_epics_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    DROP FOREIGN KEY fk_pipeline_steps_creator,
    ADD CONSTRAINT fk_epics_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    RENAME INDEX ix_pipeline_steps_initiative_fk TO ix_epics_initiative_fk;

-- --- epic_requirements: the seat column, both FKs and the FK auto-index ------
ALTER TABLE epic_requirements
    DROP FOREIGN KEY fk_psr_step,
    DROP FOREIGN KEY fk_psr_requirement,
    RENAME COLUMN step_fk TO epic_fk,
    RENAME INDEX fk_psr_step TO fk_er_epic,
    ADD CONSTRAINT fk_er_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    ADD CONSTRAINT fk_er_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE CASCADE;

-- --- epic_deps: both edge columns, the unique key, both FKs and the index ----
ALTER TABLE epic_deps
    DROP FOREIGN KEY fk_psd_step,
    DROP FOREIGN KEY fk_psd_dep_step,
    RENAME COLUMN step_fk TO epic_fk,
    RENAME COLUMN dep_step_fk TO dep_epic_fk,
    RENAME INDEX uq_pipeline_step_deps TO uq_epic_deps,
    RENAME INDEX ix_psd_dep_step_fk TO ix_ed_dep_epic_fk,
    ADD CONSTRAINT fk_ed_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    ADD CONSTRAINT fk_ed_dep_epic
        FOREIGN KEY (dep_epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

-- --- engine_outcomes (req #3756): the epic the admitted item sat on ---------
ALTER TABLE engine_outcomes
    DROP FOREIGN KEY fk_eo_step,
    RENAME COLUMN step_fk TO epic_fk,
    RENAME INDEX fk_eo_step TO fk_eo_epic,
    ADD CONSTRAINT fk_eo_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE SET NULL;

SET FOREIGN_KEY_CHECKS = 1;
