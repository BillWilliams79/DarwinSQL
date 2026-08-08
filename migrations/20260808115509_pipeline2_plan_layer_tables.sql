-- 20260808115509_pipeline2_plan_layer_tables.sql
--
-- Req #3337: create the five Pipeline 2.0 plan-layer tables in darwin_dev.
--
-- PROBLEM.  Pipeline 2.0 (req #3322/#3328) is a first-principles rebuild of the
--           pipeline layer onto one containment chain — Pipeline -> Epic ->
--           Step -> Requirement — where the Step is the launch unit carrying
--           many requirements. It stands up beside 1.0 on parallel tables
--           until the old era is eradicated; this migration is that stand-up.
--
-- SHAPE.    Five tables, `pipeline2_`-prefixed (the era token; not a `_v2`
--           suffix — see memory/pipeline-2-data-architecture.md § 2). Full
--           design and rationale in that document § 3; the two columns below
--           differ from it per the stage-2 gate deltas (req #3336, which win
--           where the record disagrees):
--             - `pipeline2_epics.sort_order` is NULLABLE, no default (not the
--               record's NOT NULL DEFAULT 0): NULL = derived order, a value =
--               manual placement that wins.
--             - `pipeline2_step_requirements` carries PRIMARY KEY
--               (requirement_fk) ALONE, `step_fk` NOT NULL beside it — one
--               step per requirement, structural. No composite key, and no
--               `ix_p2_psr_requirement_fk` (the PK already serves it).
--
-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file. A
--           `USE` is a statement, not a declaration: it re-points the session
--           the moment it executes and overrides whatever database the caller
--           named — which on 2026-08-01 sent a dev-aimed apply to production.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--           No `-- darwin:targets` declaration here, deliberately: unlike a
--           file with a real database-specific constraint, this migration is
--           ordinary DDL that both eras' operators will eventually run against
--           `darwin` — declaring `darwin_dev` would be a target list omitting
--           production, which db_guard.py treats as an ABSOLUTE, unoverridable
--           ban and would make it impossible for req #3339 to ever apply this
--           exact file to production. req #3337's own scope (darwin_dev only,
--           right now) is enforced procedurally — by which command is actually
--           run below — not by a DDL-level restriction on the file itself.
--
-- APPLY.    darwin_dev only, for this requirement:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260808115509_pipeline2_plan_layer_tables.sql darwin_dev
--
--           Production application is req #3339's, not this requirement's:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260808115509_pipeline2_plan_layer_tables.sql darwin --production
--
-- Migration id 20260808115509 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

-- ---------------------------------------------------------------------------
-- Pipeline 2.0 — the plan layer (req #3328 design; parallel era)
-- ---------------------------------------------------------------------------
-- FIVE tables standing BESIDE the 1.0 five, not replacing them. Both eras run
-- at once until 1.0 is eradicated, and requirements are NOT doubled: one
-- `requirements` table carries two plan layers above it, because duplicating a
-- requirement row would split its sessions, history and identity across two ids
-- for the same work.
--
-- CONTAINMENT IS IN THE DDL, NOT IN CONVENTION. An epic belongs to exactly one
-- pipeline and a step to exactly one epic, both NOT NULL. That single change is
-- what removes the session-attribution tie-break, gives epic pause a scope key,
-- makes reservation scoping a containment question rather than an inferred one,
-- and turns display order into a tree walk.
--
-- Containment STOPS at Requirement: a step ORGANIZES requirements and does not
-- own them, so membership is an edge table. Three levels of ownership, one of
-- membership — the one asymmetry in the chain, and deliberate.

CREATE TABLE IF NOT EXISTS pipeline2_pipelines (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256) NOT NULL,
    description     TEXT         NULL,                     -- the goal; PURPOSE only (design rule 11)
    pipeline_status VARCHAR(16)  NOT NULL DEFAULT 'draft', -- draft|active|paused|completed|aborted
    execution_mode  ENUM('parallel', 'serial')
                                 NOT NULL DEFAULT 'parallel', -- req #3388: parallel = every epic at
                                                              -- once; serial = one at a time, live
                                                              -- epic DERIVED. Carried forward from
                                                              -- 1.0 `pipelines` — a real plan
                                                              -- property, not 1.0-specific debt, so
                                                              -- the #3356 importer must copy it.
    machine_fk      INT          NULL DEFAULT NULL,        -- NULL = any machine
    creator_fk      VARCHAR(64)  NOT NULL,
    started_at      TIMESTAMP    NULL,                     -- derived from the status transition
    completed_at    TIMESTAMP    NULL,                     -- ditto; never passed by a caller
    create_ts       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_p2_pipelines_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_p2_pipelines_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- `pipeline_fk` NOT NULL is the containment. An epic cannot float free and
-- cannot be reached from a second plan, which is what makes `epic_status` a
-- scoped pause rather than a global one: 1.0's epic pause has no scope key, so
-- pausing an epic pauses it in every plan holding it.
--
-- `category_fk` is DISPLAY ONLY and gates nothing. An epic owns its steps; it
-- does not govern their attributes, and the work of one epic routinely spans
-- several categories. It must not be read by orchestration, launch, repo
-- resolution or any eligibility predicate — the category that matters is the one
-- on the requirement, which the requirement already carries.
--
-- `sort_order` IS LOAD-BEARING HERE, unlike in 1.0. A dependency edge may not
-- cross an epic, so epic order is the ONLY way to sequence one epic after
-- another. NULLABLE, no default (stage-2 gate ruling, req #3336, supersedes
-- this record's original NOT NULL DEFAULT 0): NULL = derived order (started
-- epics by start date earliest-first, unstarted after in creation order); a
-- non-NULL value is manual placement and wins over the derivation.
CREATE TABLE IF NOT EXISTS pipeline2_epics (
    id          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    pipeline_fk INT          NOT NULL,                     -- CONTAINMENT
    title       VARCHAR(256) NOT NULL,
    description TEXT         NULL,                         -- PURPOSE only (design rule 11)
    epic_status VARCHAR(16)  NOT NULL DEFAULT 'active',    -- active|paused; SUPPRESSION, not lifecycle
    category_fk INT          NOT NULL,                     -- DISPLAY ONLY; gates nothing
    sort_order  SMALLINT     NULL,                         -- NULL=derived order; value=manual, wins
    closed      TINYINT(1)   NOT NULL DEFAULT 0,           -- finished; distinct from paused
    creator_fk  VARCHAR(64)  NOT NULL,
    create_ts   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts   TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_p2_epics_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipeline2_pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_p2_epics_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_p2_epics_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_p2_epics_pipeline_fk ON pipeline2_epics (pipeline_fk);

-- NO `pipeline_fk`. A step's pipeline is its epic's, and § 6 shows the composed
-- read costs one FEWER gateway read without it, not one more — so storing both
-- would buy nothing and cost the invariant that they agree.
--
-- `epic_fk` NOT NULL also deletes a derivation. In 1.0 a step's epic is reached
-- through its requirements' `feature_fk` -> `features.epic_fk`, and a step with
-- no requirements INHERITS the label from a dependency: 17 of the 188 live steps
-- do exactly that. Here the epic is stored, so `label_inherited` and the whole
-- inheritance walk stop existing.
--
-- `not_before` is the time gate, as a column. 1.0 holds it as a ROW in the
-- dependency table, which forces that table to carry two condition kinds and
-- forces every derivation to branch on which kind a row is. One instant per step
-- is the same capability with one fewer shape: several time gates on one step is
-- not a lost capability, because the latest instant always wins and is therefore
-- one value. ZERO of the 175 live dependency rows is a time gate, so this is
-- kept for its stated future use — organising around token windows — and not
-- because anything depends on it today.
--
-- `completed_at` stays a manual stamp valid ONLY for a step with no GATING
-- requirement. A requirement-backed step's state is DERIVED and has no column,
-- here as in 1.0.
CREATE TABLE IF NOT EXISTS pipeline2_steps (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,  -- STABLE: never renumbered/reused
    epic_fk      INT          NOT NULL,                     -- CONTAINMENT; the pipeline is derived
    title        VARCHAR(256) NOT NULL,
    run          VARCHAR(8)   NOT NULL DEFAULT 'auto',      -- auto|manual
    not_before   TIMESTAMP    NULL,                         -- the time gate, one instant per step
    notes        TEXT         NULL,                         -- evidence / findings / dispositions
    completed_at TIMESTAMP    NULL,                         -- manual stamp; gating-requirement-free steps only
    creator_fk   VARCHAR(64)  NOT NULL,
    create_ts    TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts    TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_p2_steps_epic
        FOREIGN KEY (epic_fk) REFERENCES pipeline2_epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_p2_steps_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_p2_steps_epic_fk ON pipeline2_steps (epic_fk);

-- Membership, not ownership. Asymmetric on purpose and unchanged from 1.0:
-- `step_fk` CASCADE because the links are the step's own data, `requirement_fk`
-- RESTRICT because a requirement that appears in a plan cannot be deleted out
-- from under it. This deviates from the junction default of CASCADE on both
-- sides, deliberately.
--
-- Points at the SHARED `requirements` table, not at a doubled copy. Held here
-- rather than as a column on `requirements` because during the parallel era that
-- column would have to be doubled on the core table for the whole migration,
-- which is the mess the parallel-table scheme exists to avoid.
--
-- PRIMARY KEY (requirement_fk) ALONE — stage-2 gate ruling, req #3336, supersedes
-- this record's original composite PK: ONE STEP PER REQUIREMENT, structural (a
-- requirement must not run twice; duplicate it if it needs to run 2). `step_fk`
-- stays NOT NULL beside it. No `ix_p2_psr_requirement_fk`: the PK already serves
-- lookup by `requirement_fk`, and the `fk_p2_psr_step` FK auto-index covers
-- lookup by `step_fk` for the composed read.
CREATE TABLE IF NOT EXISTS pipeline2_step_requirements (
    step_fk        INT NOT NULL,
    requirement_fk INT NOT NULL PRIMARY KEY,
    CONSTRAINT fk_p2_psr_step
        FOREIGN KEY (step_fk) REFERENCES pipeline2_steps (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_p2_psr_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ONE ROW = ONE EDGE, and nothing else. The time gate left this table for a
-- column on the step, so `dep_step_fk` is NOT NULL and the row has exactly one
-- meaning — no condition-kind discriminator, no derivation branching on which
-- kind a row is.
--
-- THAT NOT NULL IS WHAT MAKES THE UNIQUE KEY TOTAL. 1.0 declares a
-- byte-identical `UNIQUE (step_fk, dep_step_fk)` that does NOT prevent
-- duplicates, because `dep_step_fk` is nullable there and MySQL treats NULLs in
-- a UNIQUE index as DISTINCT — so 1.0 can hold two time-gate rows on one step
-- with no constraint objecting. (Same NULL semantics that force
-- `orchestration_claims.epic_key` to exist.) Nothing exploits it today: 0 of the
-- 175 live rows is a time gate.
--
-- The surrogate `id` is RETAINED deliberately, not by inertia. `delete(table,
-- ids=[...])` is the REST client's one-round-trip bulk primitive and the only one
-- with gateway-level cross-tenant test coverage; it targets `id`. ONE live code
-- path uses it on the 1.0 dep table -- `delete_pipeline`, which deletes a whole
-- plan's edges at once and is exactly the case a per-row delete would punish.
-- (The other two dep deletes use the `where`-dict form and need no `id`.)
-- Dropping the column would buy nothing the composite UNIQUE key does not
-- already give.
--
-- `dep_step_fk` RESTRICT is design rule 4's teeth: a step something else gates
-- on cannot be deleted or merged away.
--
-- AN EDGE MAY NOT CROSS AN EPIC, and the schema cannot say so — the constraint
-- is between two rows' parents. Enforced in the service layer, the same place
-- the cycle check and the cross-pipeline check already live.
CREATE TABLE IF NOT EXISTS pipeline2_step_deps (
    id          INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    step_fk     INT NOT NULL,
    dep_step_fk INT NOT NULL,                              -- NOT NULL: the time gate is a step column now
    UNIQUE KEY uq_p2_step_deps (step_fk, dep_step_fk),
    CONSTRAINT fk_p2_psd_step
        FOREIGN KEY (step_fk) REFERENCES pipeline2_steps (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_p2_psd_dep_step
        FOREIGN KEY (dep_step_fk) REFERENCES pipeline2_steps (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX ix_p2_psd_dep_step_fk ON pipeline2_step_deps (dep_step_fk);
