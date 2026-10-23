-- 20261023090122_rename_epics_to_initiatives.sql
--
-- Req #3777 — PASS 1 of the plan-vocabulary rename (req #3772): EPICS BECOME
-- INITIATIVES, everywhere the schema names them. Pass 2 (Steps → Epics) claims
-- the vacated `epics` name in its own migration, after this one has deployed
-- and the census has proved the name means nothing anywhere
-- (memory/cross-stack-rename-guide.md § 2, vacate then claim).
--
-- SHAPE.    RENAME TABLE for the table (metadata-only; InnoDB FKs from
--           pipeline_steps / swarm_sessions / orchestration_claims /
--           engine_states / engine_decision_records follow the rename
--           automatically). Constraint and index names do NOT follow a RENAME
--           TABLE, so every `*_epic*` constraint is DROP FOREIGN KEY + ADD
--           CONSTRAINT under its new name (MySQL has no RENAME CONSTRAINT for
--           foreign keys) and every plain index is RENAME INDEX. The two VIRTUAL
--           generated columns whose expressions name `epic_fk`
--           (`orchestration_claims.epic_key`, `engine_states.epic_key`) are
--           dropped and re-added under the new names, because MySQL refuses to
--           RENAME COLUMN a column a generated column's expression still
--           references (error 3108) — and each of those tables is ONE ALTER
--           that drops the renamed FK, the unique key and the generated
--           column, renames the column and re-adds all of them: separate
--           statements fail part-way (dropping `uq_orchestration_claims_scope`
--           alone strands `fk_oc_pipeline` without a leftmost index) and DDL
--           is not transactional. Template: 20260812184333 — with one
--           difference, measured on a scratch copy: `fk_oc_pipeline` and
--           `fk_es_pipeline` KEEP their names, and MySQL refuses to DROP and
--           re-ADD the same constraint name in one statement (error 1826), so
--           they stay in place; the unique key they lean on is dropped and
--           re-added within the same ALTER, so they are never without one.
--
--           `uq_orchestration_claims_scope` is the single-orchestrator guarantee
--           of req #3224 (per machine since req #3678) and `uq_engine_states_scope`
--           its Engine 2 twin (req #3756); both exist again, under the same key
--           names, before this file ends.
--
-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261023090122_rename_epics_to_initiatives.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261023090122_rename_epics_to_initiatives.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20261023090122` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20261023090122 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

SET FOREIGN_KEY_CHECKS = 0;

-- --- The table — one atomic statement, FKs follow automatically ------------
RENAME TABLE epics TO initiatives;

-- --- initiatives: its status column, three FK constraints and its index -----
ALTER TABLE initiatives
    RENAME COLUMN epic_status TO initiative_status,
    DROP FOREIGN KEY fk_epics_pipeline,
    ADD CONSTRAINT fk_initiatives_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    DROP FOREIGN KEY fk_epics_category,
    ADD CONSTRAINT fk_initiatives_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    DROP FOREIGN KEY fk_epics_creator,
    ADD CONSTRAINT fk_initiatives_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    RENAME INDEX ix_epics_pipeline_fk TO ix_initiatives_pipeline_fk;

-- --- pipeline_steps: the containment column, its FK and its index ----------
ALTER TABLE pipeline_steps
    DROP FOREIGN KEY fk_pipeline_steps_epic,
    RENAME COLUMN epic_fk TO initiative_fk,
    ADD CONSTRAINT fk_pipeline_steps_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    RENAME INDEX ix_pipeline_steps_epic_fk TO ix_pipeline_steps_initiative_fk;

-- --- swarm_sessions: the orchestration attribution column and its FK -------
ALTER TABLE swarm_sessions
    DROP FOREIGN KEY fk_swarm_sessions_epic,
    RENAME COLUMN epic_fk TO initiative_fk,
    ADD CONSTRAINT fk_swarm_sessions_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE SET NULL;

-- --- orchestration_claims: the scope column, its generated key, the unique
-- --- key over it, its index and its FKs — ONE statement (see SHAPE) --------
ALTER TABLE orchestration_claims
    DROP INDEX uq_orchestration_claims_scope,
    DROP INDEX ix_orchestration_claims_epic_fk,
    DROP FOREIGN KEY fk_oc_epic,
    DROP COLUMN epic_key,
    RENAME COLUMN epic_fk TO initiative_fk,
    ADD COLUMN initiative_key INT GENERATED ALWAYS AS (COALESCE(initiative_fk, 0)) VIRTUAL
        AFTER initiative_fk,
    ADD UNIQUE KEY uq_orchestration_claims_scope (pipeline_fk, initiative_key, machine_key),
    ADD KEY ix_orchestration_claims_initiative_fk (initiative_fk),
    ADD CONSTRAINT fk_oc_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE;

-- --- engine_states: the same shape (req #3756's scope key) -----------------
ALTER TABLE engine_states
    DROP INDEX uq_engine_states_scope,
    DROP INDEX ix_engine_states_epic_fk,
    DROP FOREIGN KEY fk_es_epic,
    DROP COLUMN epic_key,
    RENAME COLUMN epic_fk TO initiative_fk,
    ADD COLUMN initiative_key INT GENERATED ALWAYS AS (COALESCE(initiative_fk, 0)) VIRTUAL
        AFTER initiative_fk,
    ADD UNIQUE KEY uq_engine_states_scope (pipeline_fk, initiative_key, machine_fk),
    ADD KEY ix_engine_states_initiative_fk (initiative_fk),
    ADD CONSTRAINT fk_es_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE;

-- --- engine_decision_records: the scope column, its FK and its index -------
-- (`ix_engine_decision_records_scope` names no tier and follows the column.)
ALTER TABLE engine_decision_records
    DROP FOREIGN KEY fk_edr_epic,
    RENAME COLUMN epic_fk TO initiative_fk,
    ADD CONSTRAINT fk_edr_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    RENAME INDEX ix_engine_decision_records_epic_fk TO ix_engine_decision_records_initiative_fk;

SET FOREIGN_KEY_CHECKS = 1;
