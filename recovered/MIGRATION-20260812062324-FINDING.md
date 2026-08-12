# Migration stamp `20260812062324` — allocated, snapshotted, NEVER APPLIED

Closes req #3485 section C item 2. Recorded here so this investigation is never
repeated: the answer is a negative result, and a negative result that is not
written down gets re-derived.

## The question

Snapshot `darwin-pre-migration-20260812062324-20260811-232352` exists in RDS
(created 2026-08-12T06:24:05Z, 20 GB, `available`), which proves
`bash scripts/db/rds-snapshot.sh 20260812062324` ran against production. No
migration file with that stamp exists in `DarwinSQL/migrations/`, in any commit on
any ref, or anywhere on disk in the workspace. Req #3485 required identifying what
it changed and committing its file — measured against the live schema, not guessed.

## The measurement

Taken 2026-08-12, production `darwin` via `DarwinSQL/scripts/query.py` (read-only).

1. **Table set is identical.** 57 live tables, 57 declared in `schema.sql`; the
   symmetric difference is empty in both directions.
2. **Nothing was rebuilt on 2026-08-12.** `information_schema.TABLES.CREATE_TIME`
   since 2026-08-10 returns exactly two rows — `swarm_sessions` (2026-08-10
   10:34:35) and `requirements` (2026-08-11 05:04:31, which is migration
   `20260811033413` dropping `feature_fk`). InnoDB rewrites `CREATE_TIME` on a
   rebuilding `ALTER`, so no rebuilding DDL ran that day.
3. **Column-level parity holds.** Comparing every
   `TABLE.COLUMN:TYPE:NULLABLE:DEFAULT` signature in production against the same
   query on `darwin_dev` — which is rebuilt from `schema.sql`, so the comparison IS
   production-vs-committed-schema — returns **582 columns on each side** and the
   only delta is `tasks.done` / `tasks.priority` rendering as `tinyint` in
   production against `tinyint(1)` in dev. That is MySQL 8's deprecated display
   width, a rendering difference in `information_schema`, not a schema difference.
4. **The obvious candidate is refuted.** An INSTANT `ALTER` (adding a column
   default) does not rebuild a table and would evade check 2. The only open work of
   that shape is req #3434, "Give requirements.ai_model and effort a column
   DEFAULT" — and production still reports `COLUMN_DEFAULT: null, IS_NULLABLE: NO`
   on both columns, with #3434 still `swarm_ready` and `completed_at` null. It has
   not been applied.
5. **No actor.** `swarm_starts` between 2026-08-12 05:30 and 07:30 UTC holds
   nothing before id 403 (`primary req#3485`) at 06:42:19 — nineteen minutes AFTER
   the snapshot.

## The conclusion

**No DDL was applied under this stamp.** A Primary AI session investigating the
req #3355 fallout allocated the stamp and took the precautionary pre-migration
snapshot at 06:23, then pivoted without running any statement and filed req #3485
nineteen minutes later to deal with the divergence properly.

There is therefore **no migration file to reconstruct**. The gap in
`DarwinSQL/migrations/` is correct and must stay: writing a file for a migration
that never ran would put a lie in the migration history, and the next reader would
apply it. The stamp is simply burned — `new-migration.sh` allocates a unique
timestamp, so nothing else can ever collide with it.

## What was NOT a violation, and what was

The CLAUDE.md Schema Migration hard gate was **not** breached here. The gate orders
migration-file-before-DDL and snapshot-before-production-DDL; no production DDL
occurred, so nothing ran out of order. The genuine breach req #3485 names is the
OTHER one, migration `20260811033413`, whose file was applied to production while
existing in no commit — that file has since been reconstructed and is committed at
`migrations/20260811033413_drop_feature_schema_features_feature_test_cases_requirements.sql`.

## Loose end, deliberately left

The snapshot is now orphaned: it guards a migration that never happened. It is one
of **63 manual `darwin-pre-migration-*` snapshots** accumulated on the account with
no retention policy. Deleting it, and deciding a retention policy for the other 62,
is out of scope for req #3485 and is a user decision with a cost dimension.

**Do not read a cost off `AllocatedStorage`.** Every one of the 63 reports 20 GB
because that field is the DATABASE's allocated storage, not the snapshot's billed
size — RDS snapshots are incremental, so the 63 do not sum to 1,260 GB of billing.
The actual backup-storage charge is visible only in Cost Explorer and must be read
from there, never inferred from this file.
