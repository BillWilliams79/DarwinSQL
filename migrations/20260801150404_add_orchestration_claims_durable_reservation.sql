-- 20260801150404_add_orchestration_claims_durable_reservation.sql
--
-- Req #3224: make the single-orchestrator guarantee DURABLE AND SHARED, so it
-- crosses a machine boundary and so a user can see who is orchestrating what,
-- from where.
--
-- PROBLEM.  The guarantee is enforced today against a MACHINE-LOCAL registry —
--           one JSON file per scope under /tmp/darwin-pipeline-engine — and
--           liveness is decided by asking whether a pid is alive. The CONFLICT
--           RULE itself is sound and is not changing: design rule 10 gives a
--           step exactly one dominant label, so step -> orchestrator is a
--           function, a whole-plan scope conflicts with every scope on its plan
--           symmetrically, two different epics of one plan partition cleanly,
--           and two plans never interact.
--
--           But NOTHING IN IT CROSSES A MACHINE BOUNDARY. Two machines can each
--           claim the same scope, neither sees the other's file, and both
--           orchestrate the same steps -- duplicate swarm sessions on ONE
--           requirement, which is the precise failure the whole rule exists to
--           prevent. And it cannot simply be pointed at a shared store, because
--           `kill(pid, 0)` is only answerable on the machine that owns the pid:
--           a claim written by the Mac is un-interrogatable from WSL.
--
--           So the fact that has to become shared data is not just "this scope
--           is taken" but "...and here is the evidence it is still ALIVE",
--           expressed in something both machines can read.
--
-- SHAPE.    ONE row per reserved scope. Claimed before orchestrating, released
--           after, carrying WHO holds it.
--
--           `pipeline_fk` + `epic_fk` ARE the scope. There is deliberately no
--           `scope` string column: `pipeline:2` / `epic:7@2` is a RENDERING of
--           those two ids, and storing it would be design rule 1's
--           derived-never-stored failure inside the very feature that exists to
--           make one fact authoritative. NULL `epic_fk` = whole-plan scope, and
--           NULL is the honest value -- a whole-plan claim is not "the claim for
--           epic zero", it names no epic at all.
--
--           `epic_key` IS WHAT MAKES THE INSERT ATOMIC, and it is the one piece
--           of this table that is not obvious. The uniqueness constraint is the
--           entire point of the design: it makes a duplicate claim of the SAME
--           scope impossible AT THE DATABASE rather than by timing, and a
--           duplicate-key rejection is already mapped to a clean 409 by this
--           stack (req #3059). But MySQL treats NULLs in a UNIQUE index as
--           DISTINCT -- so `UNIQUE (pipeline_fk, epic_fk)` would let TWO
--           whole-plan claims on one plan both insert successfully, which is
--           exactly the collision the constraint was added to stop, silently
--           permitted by the constraint itself.
--
--           A VIRTUAL generated column carrying `COALESCE(epic_fk, 0)` folds
--           "no epic" into a real value the index can compare, while `epic_fk`
--           stays NULL-able and keeps its foreign key. Precedent in this schema:
--           `agent_documents.owned_document_fk` / `.principles_agent_fk` carry
--           their UNIQUE keys the same way (migration 073 / req #3129).
--           The alternative -- `epic_fk NOT NULL DEFAULT 0` -- would require
--           dropping the FK to epics, because no `epics` row has id 0.
--
--           WHO IS THREE FACTS, and all three already exist elsewhere; none is
--           reinvented here:
--             * `machine_fk`   -> `machines`, resolved (and auto-registered) by
--                                 scripts/swarm/machine-identity.sh and injected
--                                 at the darwin-tool.sh chokepoint, exactly as
--                                 req #2943 does for a dev-server claim.
--             * `terminal_pid` -> the Claude Code CLI process, resolved through
--                                 the tiered contract ~/.claude/statusline.sh
--                                 already uses (CLAUDE_PID -> nearest `claude`
--                                 ancestor -> PPID).
--             * `engine_pid`   -> the pipeline_engine.py process.
--
--           `engine_pid` IS DIAGNOSTIC AND DISPLAY ONLY. It must never be read
--           as liveness. A pid is meaningful only on the machine that owns it,
--           and pids wrap (macOS at 99999) -- interrogating a remote pid is the
--           mistake this whole requirement exists to correct. It is here so a
--           human can find and kill the process, not so software can ask
--           whether it is alive.
--
--           LIVENESS IS HEARTBEAT AGE, AND THE CLOCK IS THE DATABASE'S.
--           `claimed_at` is DB-stamped on insert and `update_ts` is DB-stamped
--           on every update, so the holder's own clock never enters the
--           arithmetic -- a machine with a fast clock cannot make its claim look
--           permanently fresh, nor a slow one permanently stale. The reader's
--           clock still does; it is bounded by NTP on all three participants and
--           is three orders of magnitude under the staleness threshold.
--
--           `polls` IS THE HEARTBEAT'S PAYLOAD, and it is load-bearing for a
--           MySQL reason: `ON UPDATE CURRENT_TIMESTAMP` fires only when a column
--           value actually CHANGES. A heartbeat that rewrote a column to the
--           value it already held would be a no-op at the database and would not
--           move `update_ts` at all -- the liveness signal would freeze while the
--           engine ran perfectly. The holder's cycle counter is monotonic within
--           a claim, so it always changes, and it is real information rather
--           than a nonce.
--
--           NO `heartbeat_at` COLUMN. A second timestamp written by the CLIENT
--           would be a second answer to "when was this last alive" that can
--           disagree with `update_ts`, and the client-stamped one is the WRONG
--           answer across machines. One fact, one column, and it is the one the
--           database maintains for free.
--
--           STALENESS THRESHOLD: 600 SECONDS, enforced in the application (see
--           darwin-mcp/services/orchestration_claims.py), not here -- a schema
--           cannot express "old enough to steal". 600 s is TEN default engine
--           cycles. The engine heartbeats BEFORE its plan read, so a cycle whose
--           read fails still heartbeats; it self-terminates DEGRADED after five
--           consecutive failed reads (~5 min) and heartbeats throughout; and
--           mcp-restart-if-stale.sh restarts the shared daemon on ANY concurrent
--           session's merge, which an orchestration run produces a stream of. So
--           a live engine legitimately misses cycles, and the threshold errs
--           LONG on purpose: reclaiming early steals a running orchestrator's
--           scope, while reclaiming late costs a dead scope ten idle minutes.
--
--           NOT MERGED WITH PAUSE, and the distinction is why this is a new
--           table rather than columns on `pipelines` / `epics` beside
--           `pipeline_status` / `epic_status` (req #3223). A RESERVATION is a
--           live claim tied to a running process, released when it ends, and
--           RECLAIMED on staleness. A PAUSE is a user INTENTION that outlives
--           every process and is expected to still be there tomorrow with
--           nothing running -- it must NEVER be reclaimed. Sharing a column
--           would mean a staleness sweep could silently unpause a plan.
--
--           NO `closed` COLUMN AND NO SOFT DELETE. A released reservation is not
--           a retired one, it is gone; a row that exists means a scope is
--           claimed, and that is the only reading the constraint can enforce.
--           This is a coordination table, like `dev_servers`, not content.
--
--           INDEXES. The UNIQUE key covers every lookup by scope and by plan
--           (`pipeline_fk` is its leading column). `ix_orchestration_claims_epic_fk`
--           exists for the epic-scoped read the UI makes and because MySQL wants
--           an index behind the FK anyway.
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands — the
--           only difference is the trailing database name, so read it twice:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260801150404_add_orchestration_claims_durable_reservation.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260801150404_add_orchestration_claims_durable_reservation.sql darwin
--
--           The production command above requires
--           `bash scripts/db/rds-snapshot.sh 20260801150404` to report status=ok
--           first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20260801150404 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

CREATE TABLE IF NOT EXISTS orchestration_claims (
    id            INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    pipeline_fk   INT          NOT NULL,                -- the plan this claim covers
    epic_fk       INT          NULL DEFAULT NULL,       -- NULL = whole-plan scope
    -- Carries the UNIQUE key. MySQL treats NULLs in a UNIQUE index as distinct,
    -- so the key CANNOT be written over epic_fk directly — see SHAPE above.
    epic_key      INT          AS (COALESCE(epic_fk, 0)) VIRTUAL,
    machine_fk    INT          NULL DEFAULT NULL,       -- WHERE it runs
    terminal_pid  INT          NULL DEFAULT NULL,       -- the Claude Code CLI process
    engine_pid    INT          NULL DEFAULT NULL,       -- DIAGNOSTIC ONLY, never liveness
    polls         INT          NOT NULL DEFAULT 0,      -- the heartbeat payload
    claimed_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creator_fk    VARCHAR(64)  NOT NULL,
    create_ts     TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    -- THE LIVENESS CLOCK. DB-stamped on every heartbeat; NULL until the first
    -- one, which is why every reader falls back to claimed_at.
    update_ts     TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_orchestration_claims_scope (pipeline_fk, epic_key),
    CONSTRAINT fk_oc_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_oc_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    -- RESTRICT, matching every other machine_fk in this schema (dev_servers,
    -- swarm_sessions, swarm_starts, requirements, pipelines): a machine with a
    -- live claim against it is a machine that is still in use.
    CONSTRAINT fk_oc_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_oc_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_orchestration_claims_epic_fk ON orchestration_claims (epic_fk);
