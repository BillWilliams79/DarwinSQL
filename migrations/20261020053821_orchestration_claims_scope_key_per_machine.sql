-- 20261020053821_orchestration_claims_scope_key_per_machine.sql
--
-- Req #3678: let a SECOND MACHINE join a scope another machine is already
-- orchestrating, as a SUBSCRIBER that launches only its own machine's work.
--
-- PROBLEM.  `uq_orchestration_claims_scope (pipeline_fk, epic_key)` allows ONE
--           row per scope, full stop. Machine-aware orchestration (req #3678)
--           makes the first machine into a scope its LEAD (it launches work
--           pinned to "Any" and to itself) and every later machine a SUBSCRIBER
--           (it launches only requirements pinned to it). A subscriber has to
--           hold a claim row like the lead does — that row is what makes it
--           visible to every machine and to the UI, and what heartbeats it —
--           and the current key refuses that row on the same scope.
--
-- SHAPE.    The key gains the machine: (pipeline_fk, epic_key, machine_key),
--           with `machine_key = COALESCE(machine_fk, 0)` VIRTUAL for exactly the
--           reason `epic_key` exists — MySQL treats NULLs in a UNIQUE index as
--           DISTINCT, so a key over the nullable `machine_fk` directly would let
--           two identity-less claims of one scope both insert. A SAME-MACHINE
--           duplicate of a scope is still refused AT THE DATABASE, which is the
--           one orchestrator per machine per scope rule; who is LEAD and who is
--           SUBSCRIBER across machines is DERIVED from the rows (lowest id
--           wins), never stored — see darwin-mcp/services/orchestration_claims.py
--           `resolve_roles`. Drop and add are ONE statement because the key is
--           also the index `fk_oc_pipeline` rests on.
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
--               DarwinSQL/migrations/20261020053821_orchestration_claims_scope_key_per_machine.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261020053821_orchestration_claims_scope_key_per_machine.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20261020053821` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20261020053821 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.



ALTER TABLE orchestration_claims
    ADD COLUMN machine_key INT AS (COALESCE(machine_fk, 0)) VIRTUAL
        COMMENT 'req #3678: carries uq_orchestration_claims_scope; NULL machine folds to 0'
        AFTER machine_fk,
    DROP INDEX uq_orchestration_claims_scope,
    ADD UNIQUE KEY uq_orchestration_claims_scope (pipeline_fk, epic_key, machine_key);
