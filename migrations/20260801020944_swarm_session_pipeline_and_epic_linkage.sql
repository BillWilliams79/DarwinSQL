-- 20260801020944_swarm_session_pipeline_and_epic_linkage.sql
--
-- Req #3186: give a swarm session a DURABLE record of which pipeline and which
-- epic it was advancing.
--
-- PROBLEM.  A `swarm_sessions` row reaches a requirement (`requirement_sessions`)
--           and stops there. Attribution therefore ends one level BELOW where
--           orchestration operates: the data can answer "which requirement is
--           this session for" but not "which pipeline / which epic is this
--           session advancing".
--
--           Both facts are derivable today, and that derivation is the wrong
--           durable signal for two independent reasons:
--
--             * NO JOIN EXISTS AT THE GATEWAY. Lambda-Rest is a table-at-a-time
--               CRUD gateway and is the ONLY path to this data for every
--               consumer (root CLAUDE.md § Single DB Gateway Rule). Deriving
--               costs SIX list reads plus a client-side join —
--               requirement_sessions, requirements, features,
--               pipeline_step_requirements, pipeline_steps, pipelines — ON EVERY
--               RENDER, for a fact that is otherwise one column on a row already
--               being read. That per-render fan-out is what req #3080 design
--               rule 5 forbids, and it is the same argument req #3117 made when
--               it added `wall_secs_total` rather than re-summing buckets a
--               bounded list read had dropped.
--
--             * THE LINKS DERIVATION WALKS ARE MUTABLE; THE FACT IS HISTORICAL.
--               `requirements.feature_fk` and `features.epic_fk` are both
--               ON DELETE SET NULL and re-assignable at any time;
--               `pipeline_step_requirements` rows are DELETED outright by
--               `drop_pipeline_step` and rewritten by unlink/link. So a derived
--               answer CHANGES or VANISHES retroactively when the plan is edited
--               after the session finished. "Which pipeline was this session
--               advancing" has exactly one correct answer — the one true when it
--               ran — and only a stamp preserves it.
--
--           Precedent: memory/swarm-orchestration-doctrine.md §8. Req #3123 met
--           the same class of question (a durable signal the schema did not
--           carry) and chose a COLUMN over a derivation in the engine, because
--           choosing the signal is a schema decision.
--
-- SHAPE.    Two NULLable FKs on `swarm_sessions`, stamped ONCE by darwin-mcp's
--           `link_requirement_session` — the single point in the system where a
--           session's requirement becomes known — and never overwritten once
--           non-NULL.
--
--           NULLable, not NOT NULL: a session may legitimately belong to no
--           pipeline and no epic (an ad-hoc requirement outside any plan), and
--           every one of the 800+ existing rows predates the column.
--
--           ON DELETE SET NULL, not RESTRICT, on both. Session history must
--           never be the reason a pipeline or an epic cannot be deleted, and
--           RESTRICT is the grief-lock-capable action req #3125 catalogues. The
--           two columns are consequently registered in
--           `CREATOR_TABLE_REFERENCES` (Lambda-Rest/auth_utils.py) as
--           cross-tenant ATTACHMENT references — the build fails until they are.
--
--           They are independent, not one derived from the other: the schema
--           does not relate a pipeline to an epic, so a session can have either,
--           both, or neither.
--
--           Placed AFTER machine_fk, with the other "which context did this run
--           in" columns.
--
-- BACKFILL. The point of this migration, not a footnote to it. Both columns are
--           derivable for existing rows *right now*, from links that have not
--           yet been edited away — so the history is recoverable today and only
--           today. One UPDATE per column, both restricted to rows where the
--           column is still NULL so a re-run is a no-op.
--
--           ONE REQUIREMENT DECIDES, and it is the LOWEST-id one the session is
--           linked to. That matters because `requirement_sessions` is a
--           many-to-many: a session may carry several requirements, and the live
--           stamp only ever sees the ONE requirement being linked, keeping
--           whichever arrived FIRST (the stamp is write-once).
--
--           **The backfill cannot reproduce "first" exactly, and does not claim
--           to**: `requirement_sessions` carries no timestamp, so chronology is
--           not recoverable from the data. Lowest requirement id is a PROXY for
--           it — ids are monotonic, so for the ordinary session (its own
--           requirement linked at launch by session-init.sh, any later one added
--           afterwards) the proxy and the truth coincide. A session whose
--           requirements were linked out of id order can legitimately differ from
--           what a live stamp would have written. That is the honest limit of a
--           backfill over a junction with no clock; the alternative was to leave
--           928 rows unattributed.
--
--           MEASURED before this was applied to production (2026-08-01): 4 of 928
--           sessions carry more than one requirement, and ZERO of those resolve
--           to more than one distinct epic or more than one distinct pipeline. So
--           on the data this ran against, every candidate rule — lowest-id,
--           first-linked, or the union across all of a session's requirements —
--           produces identical rows. The rule below is written for the general
--           case anyway, because the next database this runs against will not
--           have been measured.
--
--           Within the chosen requirement, the pipeline backfill still picks ONE
--           pipeline when that requirement is linked into steps of several:
--           prefer `pipeline_status = 'active'`, tie-break on lowest id. That
--           part IS byte-for-byte the rule the live resolver applies
--           (`darwin-mcp/services/requirements.py::_resolve_pipeline`).
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands — the
--           only difference is the trailing database name, so read it twice:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260801020944_swarm_session_pipeline_and_epic_linkage.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260801020944_swarm_session_pipeline_and_epic_linkage.sql darwin
--
--           The production command above requires
--           `bash scripts/db/rds-snapshot.sh 20260801020944` to report status=ok
--           first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20260801020944 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

ALTER TABLE swarm_sessions
    ADD COLUMN pipeline_fk INT NULL DEFAULT NULL AFTER machine_fk,
    ADD COLUMN epic_fk     INT NULL DEFAULT NULL AFTER pipeline_fk;

ALTER TABLE swarm_sessions
    ADD CONSTRAINT fk_swarm_sessions_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    ADD CONSTRAINT fk_swarm_sessions_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE SET NULL;

-- ---------------------------------------------------------------------------
-- Backfill 1 — epic. requirement -> feature -> epic, a single-valued path at
-- every hop, so within the chosen requirement there is no tie-break to make.
--
-- The correlated subquery is scoped to the session's LOWEST requirement id
-- (`ORDER BY rs.requirement_fk ASC LIMIT 1`) rather than aggregated across all
-- of them. `MIN(f.epic_fk)` would have picked the numerically smallest EPIC id
-- across every requirement on the session — an answer that corresponds to
-- nothing, and to a different rule than the pipeline backfill's.
-- ---------------------------------------------------------------------------
UPDATE swarm_sessions s
   SET s.epic_fk = (
        SELECT f.epic_fk
          FROM requirement_sessions rs
          JOIN requirements r ON r.id = rs.requirement_fk
          JOIN features     f ON f.id = r.feature_fk
         WHERE rs.session_fk = s.id
           AND f.epic_fk IS NOT NULL
         ORDER BY rs.requirement_fk ASC
         LIMIT 1
   )
 WHERE s.epic_fk IS NULL;

-- ---------------------------------------------------------------------------
-- Backfill 2 — pipeline. Same requirement-selection rule as backfill 1, so the
-- two columns describe the same requirement rather than two different ones.
-- Within it, a requirement may be linked into steps of several pipelines: the
-- winner is `active` first, then lowest id — byte-for-byte the live resolver's
-- rule. Expressed as an ordered correlated subquery rather than a GROUP BY,
-- because MIN() cannot express "prefer active".
--
-- `WHERE s.pipeline_fk IS NULL` with a subquery that finds nothing writes NULL
-- over NULL; MySQL skips a row whose values are unchanged, so `update_ts` does
-- not fire and a re-run leaves no trace.
-- ---------------------------------------------------------------------------
UPDATE swarm_sessions s
   SET s.pipeline_fk = (
        SELECT p.id
          FROM pipeline_step_requirements psr
          JOIN pipeline_steps ps ON ps.id = psr.step_fk
          JOIN pipelines p ON p.id = ps.pipeline_fk
         WHERE psr.requirement_fk = (
                SELECT rs.requirement_fk
                  FROM requirement_sessions rs
                 WHERE rs.session_fk = s.id
                 ORDER BY rs.requirement_fk ASC
                 LIMIT 1
         )
         ORDER BY (p.pipeline_status = 'active') DESC, p.id ASC
         LIMIT 1
   )
 WHERE s.pipeline_fk IS NULL;
