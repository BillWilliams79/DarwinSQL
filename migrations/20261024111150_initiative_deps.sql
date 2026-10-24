-- 20261024111150_initiative_deps.sql
--
-- Req #3823: an initiative can depend on another initiative of the same plan.
--
-- PROBLEM.  Only epics depend on epics (`epic_deps`). To say "initiative B
--           waits for all of initiative A" an author hand-wires a barrier
--           edge from each of B's epics to each of A's, and redoes it every
--           time either initiative gains an epic.
--
-- SHAPE.    One junction, `initiative_deps`, ONE ROW = ONE EDGE ("initiative_fk
--           waits for dep_initiative_fk"), the shape of `epic_deps`:
--             * surrogate `id` (the REST client's bulk delete targets `id`)
--               plus UNIQUE (initiative_fk, dep_initiative_fk), total because
--               both columns are NOT NULL;
--             * `initiative_fk` ON DELETE CASCADE — an initiative's own edges
--               are its data and go with it;
--             * `dep_initiative_fk` ON DELETE RESTRICT — design rule 4's teeth,
--               as on `epic_deps.dep_epic_fk`: an initiative something waits on
--               cannot be deleted until that edge is removed.
--           No creator_fk: ownership is DERIVED through `initiative_fk`
--           (Lambda-Rest auth_utils JUNCTION_OWNERSHIP, req #3122). The hold
--           itself is never stored — it is recomputed from requirement statuses
--           on every read (Lambda-Rest pipeline2_derive.py). Same-plan, no
--           self-edge and no cycle (on the combined initiative + epic graph)
--           are enforced at the gateway, not here: each is a rule between two
--           rows' parents, which a CHECK cannot express.
--
-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file. A
--           `USE` is a statement, not a declaration: it re-points the session
--           the moment it executes and overrides whatever database the caller
--           named — which on 2026-08-01 sent a dev-aimed apply to production.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--           If this migration may only be applied to ONE database, say so as a
--           constraint instead: `-- darwin:targets = darwin`.
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261024111150_initiative_deps.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261024111150_initiative_deps.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20261024111150` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20261024111150 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.


CREATE TABLE initiative_deps (
    id                INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    initiative_fk     INT NOT NULL,                         -- the initiative that waits
    dep_initiative_fk INT NOT NULL,                         -- the initiative it waits for
    UNIQUE KEY uq_initiative_deps (initiative_fk, dep_initiative_fk),
    CONSTRAINT fk_id_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_id_dep_initiative
        FOREIGN KEY (dep_initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX ix_id_dep_initiative_fk ON initiative_deps (dep_initiative_fk);
