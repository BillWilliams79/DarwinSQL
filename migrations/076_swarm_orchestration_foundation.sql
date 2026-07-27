-- 076_swarm_orchestration_foundation.sql
--
-- Req #3111 (epic: Swarm Orchestration Feature, plan step 38 / wave 1): the schema
-- foundation for pipelines-as-data — the agile hierarchy (Epic > Feature > Story) plus
-- the execution artifact (pipeline > step > requirement links + dependency edges).
--
-- WHY THIS SHAPE. Req #3080 rejected a coded DAG (LangChain/LangGraph, 2026-07-25): the
-- 2026-07-25 Substrate Rebuild plan mutated ~12 times under contact with reality, and a
-- static graph would have needed a rewrite each time. What is durable is the ARTIFACT —
-- a plan held as data, rendered live, interpreted by a judgment-capable Primary Claude.
-- These tables are that artifact and nothing more.
--
-- THE DESIGN RULES THIS DDL ENCODES (req #3080; each names a real failure it prevents):
--
--   Rule 1 — STEP STATE IS DERIVED, NEVER STORED. There is deliberately NO state/status
--   column on pipeline_steps. A step's state is computed from its linked requirements:
--   any linked requirement in `development` => Running; all terminal (met/deferred/
--   wontfix) => Complete; else Scheduled. The POC's step 13 launched five sessions while
--   the plan still read "Scheduled" because the launch and the plan edit were two
--   separate manual actions; a column that can disagree with reality is the bug, so the
--   column does not exist. `pipeline_steps.completed_at` is the ONE exception and is
--   scoped precisely: it is the manual-completion stamp for a step with ZERO linked
--   requirements (fixture case: plan step 7, "record the regression baseline"), which
--   has nothing to derive from. A requirement-backed step derives its state and MUST
--   leave completed_at NULL — an application-layer invariant, not a CHECK constraint
--   (Darwin validates in the application layer; see memory/new-data-type-pattern.md).
--
--   Rule 3 — DISPLAY ORDER IS COMPUTED AT RENDER. There is deliberately NO seq/sort_order
--   column on pipeline_steps. Order is topological, then state bands (Complete > Running
--   > Scheduled, absolute), then execution streams, then anchor clustering — recomputed
--   every render and self-checked by the renderer (req #3112). Stored row order is
--   insertion history and must never drive display; four "plan reads out of order"
--   regressions in one day came from letting it try.
--
--   Rule 4 — DEPENDENCIES REFERENCE STABLE STEP IDS. `pipeline_steps.id` is assigned once
--   by AUTO_INCREMENT and is never renumbered and never reused. Deps are structured rows
--   (pipeline_step_deps), never prose. `pipeline_step_deps.dep_step_fk` is ON DELETE
--   RESTRICT so a step that something else gates on CANNOT be deleted or merged away —
--   the FK is the enforcement, not a convention.
--
--   Rule 10 — LABELS ATTACH AT THE REQUIREMENT LEVEL. Epic/feature hang off the
--   requirement (requirements.feature_fk -> features.epic_fk -> epics), never off the
--   step, because a launch unit may legitimately cross epics: fixture step 19 batches
--   #3080/#3083 (Swarm Orchestration Feature) together with #3105 (a Swarm Substrate
--   Rebuild requirement) in ONE swarm-start. The step derives its dominant label at
--   render time, so a mixed batch mislabels nothing. The POC had to pick one label for a
--   3-substrate + 2-app batch and got it wrong.
--
-- MVP DISCIPLINE. No `epics.epic_status` (an epic is open until its features are done —
-- a second lifecycle to hand-maintain buys nothing). No `kind` discriminator on
-- pipeline_steps (the req #3080 sketch proposed swarm_req|primary_task|gate|review|
-- canary|manual; the discuss session collapsed it to `run` auto|manual, because every
-- other value was decoration the renderer never needed). No gate_expr text column — deps
-- are rows.
--
-- Tables and their baseline class (memory/new-data-type-pattern.md):
--   epics                      CONTENT   (title, description, closed, sort_order, category_fk)
--   pipelines                  EXECUTION (status enum, started_at/completed_at; no closed,
--                                        no sort_order, no category_fk)
--   pipeline_steps             EXECUTION (title from the plan row; no closed/sort_order/category_fk)
--   pipeline_step_requirements JUNCTION  (composite PK, no id/creator_fk/timestamps)
--   pipeline_step_deps         EDGE      (surrogate id — an edge is addressable and a step
--                                        may carry several; no creator_fk, it inherits the
--                                        step's ownership)
--
-- Applied: darwin_dev then production `darwin` (req #3111 is coordination_type=deployed).

-- ---------------------------------------------------------------------------
-- 1. epics — the top of the agile hierarchy: Epic > Feature > Story(requirement).
--
-- Content table with the full baseline. category_fk is RESTRICT (an epic cannot be
-- orphaned by deleting its category — move it first), matching requirements/features.
-- description is NULL-able: an epic's title is often the whole story ("Swarm Substrate
-- Rebuild"), unlike features.description which is NOT NULL.
-- ---------------------------------------------------------------------------
CREATE TABLE epics (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title        VARCHAR(256) NOT NULL,
    description  TEXT         NULL,
    category_fk  INT          NOT NULL,
    creator_fk   VARCHAR(64)  NOT NULL,
    closed       TINYINT(1)   NOT NULL DEFAULT 0,
    sort_order   SMALLINT     NULL,
    create_ts    TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts    TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_epics_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_epics_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- 2. features.epic_fk — features are the middle tier. Darwin's existing `features`
-- table is the landing zone named by memory/pipeline-plan-tracking.md, so this is an
-- ALTER, not a new table.
--
-- NULL-able + ON DELETE SET NULL: features predate epics (9 rows live in darwin_dev
-- today) and a feature without an epic is legitimate, so deleting an epic must demote
-- its features rather than destroy them. SET NULL is the only policy that permits the
-- column to be NOT NULL-free AND the delete to succeed.
-- ---------------------------------------------------------------------------
ALTER TABLE features
    ADD COLUMN epic_fk INT NULL DEFAULT NULL AFTER feature_status,
    ADD CONSTRAINT fk_features_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE SET NULL;

-- ---------------------------------------------------------------------------
-- 3. requirements.feature_fk — the story tier. THIS is where epic/feature labels
-- attach (design rule 10); pipeline_steps carry no label column at all.
--
-- NULL-able + SET NULL for the same reason as epic_fk: the overwhelming majority of
-- Darwin's requirements have no feature and never will, and deleting a feature must
-- not delete requirement history.
--
-- NOTE (req #3078): `requirements` is one of the four tables darwin-mcp reads through
-- an explicit `fields=` projection. services/common.py::TABLE_COLUMNS gains feature_fk
-- in the same change set (LIST tier — a small int, cheap to carry), and the production
-- DDL below lands BEFORE the daemon restarts on the new code. A column the code names
-- and the database lacks turns the ENTIRE read into a 400, which would take out
-- darwin://requirements/open and the /swarm-start happy path with it.
-- ---------------------------------------------------------------------------
-- No AFTER clause — the column appends LAST, which is what schema.sql declares.
-- `requirements` already carries pre-existing ordinal drift between the live
-- databases and schema.sql (machine_fk / sort_order / affected_repos sit in a
-- different order than the file declares, from migration 066). Appending is the
-- only placement that lands identically in darwin_dev, production, and a fresh
-- schema.sql run, so this migration adds no new drift to that column order.
ALTER TABLE requirements
    ADD COLUMN feature_fk INT NULL DEFAULT NULL,
    ADD CONSTRAINT fk_requirements_feature
        FOREIGN KEY (feature_fk) REFERENCES features (id)
        ON UPDATE CASCADE ON DELETE SET NULL;

-- ---------------------------------------------------------------------------
-- 4. pipelines — the execution container. One row per durable multi-requirement plan.
--
-- pipeline_status is the ONE hand-controlled lifecycle in this feature and that is
-- deliberate: it is the human's/Primary's declaration of intent about the plan as a
-- whole (draft|active|paused|completed|aborted), not an observation about work, so
-- there is nothing to derive it from. Contrast pipeline_steps, whose state IS an
-- observation and therefore has no column (design rule 1).
--
-- Execution table: no `closed` (it closes via terminal status), no `sort_order`
-- (chronological), no `category_fk` (a plan spans categories — the fixture plan spans
-- Swarm and Agents).
--
-- started_at is NULL-able here, deviating from the baseline execution-table pattern's
-- `started_at NOT NULL DEFAULT CURRENT_TIMESTAMP` (swarm_sessions, test_runs). Those
-- rows are born running; a pipeline is born `draft` and may sit unstarted for days, so
-- a creation-time stamp in started_at would be a lie. Both stamps are set on transition.
--
-- machine_fk is RESTRICT, matching every other machine reference in the schema
-- (swarm_sessions, swarm_starts, dev_servers, requirements): a machine with history
-- pointing at it cannot be deleted out from under that history.
-- ---------------------------------------------------------------------------
CREATE TABLE pipelines (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256) NOT NULL,
    description     TEXT         NULL,                    -- the goal
    pipeline_status VARCHAR(16)  NOT NULL DEFAULT 'draft',-- draft|active|paused|completed|aborted
    machine_fk      INT          NULL DEFAULT NULL,       -- NULL = any machine
    creator_fk      VARCHAR(64)  NOT NULL,
    started_at      TIMESTAMP    NULL,                    -- set on draft -> active
    completed_at    TIMESTAMP    NULL,                    -- set on -> completed|aborted
    create_ts       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_pipelines_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_pipelines_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- 5. pipeline_steps — one row per plan row. A step is a LAUNCH UNIT (design rule 2):
-- requirements sharing an identical (gate, run-mode, machine) tuple are ONE step with N
-- requirements, not N steps. The fixture carries eight multi-requirement steps
-- (1, 12, 13, 19, 33, 38, 39, 40 — the largest is step 12's seven-way parallel launch)
-- for exactly this reason: the POC rendered five same-gate rows as scattered singles
-- until they were merged by hand.
--
-- Columns that are ABSENT are as much of the design as the ones present:
--   * no state/status  — derived (rule 1)
--   * no seq/sort_order — computed at render (rule 3)
--   * no epic/feature   — attached at the requirement (rule 10)
--   * no gate_expr text — deps are rows (rule 4)
--
-- pipeline_fk CASCADEs: the pipeline is the container, and deleting a plan takes its
-- steps. `notes` is the evidence/findings/disposition field and must hold prose like
-- "gate passed WITH exceptions: 3709/3713, 4 pre-existing failures dispositioned into
-- #3061" — a real fixture value (plan step 6-era gate) that a status enum could never
-- express.
-- ---------------------------------------------------------------------------
CREATE TABLE pipeline_steps (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,  -- STABLE: never renumbered, never reused
    pipeline_fk  INT          NOT NULL,
    title        VARCHAR(256) NOT NULL,                             -- the step summary
    run          VARCHAR(8)   NOT NULL DEFAULT 'auto',              -- auto|manual
    notes        TEXT         NULL,                                 -- evidence / findings / dispositions
    completed_at TIMESTAMP    NULL,                                 -- manual stamp ONLY for zero-requirement steps
    creator_fk   VARCHAR(64)  NOT NULL,
    create_ts    TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts    TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_pipeline_steps_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_pipeline_steps_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_pipeline_steps_pipeline_fk ON pipeline_steps (pipeline_fk);

-- ---------------------------------------------------------------------------
-- 6. pipeline_step_requirements — which requirements a step launches. Junction:
-- composite PK, no id, no creator_fk, no timestamps.
--
-- ASYMMETRIC FK policy, and the asymmetry is the point:
--   step_fk        CASCADE  — the links are part of the step; deleting the step takes them.
--   requirement_fk RESTRICT — a requirement that appears in a plan CANNOT be deleted.
-- The junction-table default is CASCADE on both sides (memory/new-data-type-pattern.md),
-- and this deviates deliberately: silently dropping a requirement out of an execution
-- plan is exactly the "residue" failure mode req #3080 rule 7 is about. Dropping a step
-- from a plan is a plan edit (delete the junction row); deleting the requirement itself
-- must be blocked while any plan still references it.
-- ---------------------------------------------------------------------------
CREATE TABLE pipeline_step_requirements (
    step_fk        INT NOT NULL,
    requirement_fk INT NOT NULL,
    PRIMARY KEY (step_fk, requirement_fk),
    CONSTRAINT fk_psr_step
        FOREIGN KEY (step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_psr_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX ix_psr_requirement_fk ON pipeline_step_requirements (requirement_fk);

-- ---------------------------------------------------------------------------
-- 7. pipeline_step_deps — the dependency edges. Structured rows, never prose (rule 4).
--
-- Each row is ONE condition on ONE step. CONVENTION (application-enforced, not a CHECK —
-- Darwin validates in the application layer): exactly one of dep_step_fk / time_at is
-- set per row.
--   dep_step_fk set, time_at NULL  => "wait for step N"
--   dep_step_fk NULL, time_at set  => "wait until <timestamp>" (the plan's T:<ISO8601> token)
--
-- A DUAL-CONDITION GATE IS SIMPLY TWO ROWS ON ONE STEP. The real case this must
-- represent (req #3080, plan stage 0): s0.4 waited on requirement #3050's session
-- completing AND a 2-hour wall-clock gate at 06:31:38 PDT — two independent wait
-- mechanisms on one step. Modeling that as two rows rather than a gate_expr string is
-- what keeps the renderer's topological sort and the watchdog's polling both able to
-- read it.
--
-- dep_step_fk is ON DELETE RESTRICT — design rule 4's teeth. A step that another step
-- gates on cannot be deleted or merged away; the delete fails at the database rather
-- than silently orphaning the graph. (step_fk CASCADEs: deleting a step takes the
-- conditions ON it, which is the step's own data.)
--
-- UNIQUE(step_fk, dep_step_fk) forbids duplicate step-to-step edges. MySQL treats NULLs
-- as distinct in a UNIQUE key, so this deliberately does NOT constrain time_at rows: a
-- step may legitimately carry more than one time condition, and the composite would
-- otherwise collapse them.
--
-- No creator_fk: an edge is not independently owned — it inherits the step's ownership
-- and dies with it, the same call the junction above makes.
--
-- OPERATIONAL CONSEQUENCE — DELETING A PIPELINE IS TWO PHASES. Because dep_step_fk is
-- RESTRICT, a plain `DELETE FROM pipelines WHERE id = ?` FAILS as soon as any step gates
-- on another: MySQL evaluates the RESTRICT while cascading pipeline -> steps and refuses,
-- even though the referencing dep row is itself part of that same cascade. The supported
-- teardown is:
--
--   DELETE FROM pipeline_step_deps
--    WHERE step_fk IN (SELECT id FROM pipeline_steps WHERE pipeline_fk = ?);
--   DELETE FROM pipelines WHERE id = ?;   -- steps + requirement links cascade
--
-- Any delete_pipeline implementation (MCP tool, UI action) MUST follow that order. This
-- is the deliberate price of design rule 4 — MySQL cannot express "block a referenced
-- step from vanishing UNLESS the whole graph is going" — and it buys a side benefit: a
-- plan cannot be destroyed by a single careless statement. Pinned by
-- tests/test_constraints.py::test_deleting_a_pipeline_with_internal_deps_is_refused.
-- ---------------------------------------------------------------------------
CREATE TABLE pipeline_step_deps (
    id          INT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    step_fk     INT       NOT NULL,
    dep_step_fk INT       NULL,          -- gate on another step
    time_at     TIMESTAMP NULL,          -- gate on wall clock (plan's T:<ISO8601>)
    UNIQUE KEY uq_pipeline_step_deps (step_fk, dep_step_fk),
    CONSTRAINT fk_psd_step
        FOREIGN KEY (step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_psd_dep_step
        FOREIGN KEY (dep_step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX ix_psd_dep_step_fk ON pipeline_step_deps (dep_step_fk);
