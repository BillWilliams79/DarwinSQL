# DarwinSQL Scripts

## Script Inventory

| Script | Purpose |
|--------|---------|
| `new-migration.sh` | **Allocate a new migration file.** The only sanctioned way to create one — stamps a unique `YYYYMMDDHHMMSS_description.sql` from the UTC clock instead of `max(NNN)+1` off a stale clone, which produced three duplicate prefixes on main (046, 050, 074). Never hand-pick a migration filename (req #3121) |
| `cleanup_darwin_dev.py` | Remove orphaned test data from darwin_dev |
| `cleanup_e2e.py` | Comprehensive E2E test data cleanup (darwin or darwin_dev) |
| `seed_darwin_dev.py` | Create darwin_dev database, its tables, and seed E2E test users |
| `seed_e2e_workers.py` | Seed 8 parallel E2E worker profiles |
| `recreate_darwin_dev.sql` | Drop and recreate all 52 darwin_dev tables from scratch (req #3111) |
| `add-api-route.sh` | Add a new /darwin/{table} route to Darwin API Gateway (ANY + OPTIONS, CORS, verifies Lambda wildcard coverage, deploy) |
| `verify-lambda-policy.sh` | Live-gated check that the RestApi-MySql-Lambda resource policy is minimal + every route still authorized (req #3002) |
| `get-e2e-token.sh` | Print a fresh Cognito IdToken for the E2E test user (used by verify-lambda-policy.sh) |
| `db_guard.py` | **The one place that decides which database a statement hits** (req #3196). Explicit target, production named twice, file target declarations, destructive confirmation, loud banner. Imported by every script below that opens a connection |
| `load_sql.py` | Apply a .sql file to exactly the database you name, in one transaction. This machine has no `mysql` CLI; the splitter is quote-aware because fixture literals contain `;` and `#` (req #3111) |
| `query.py` | The guarded ad-hoc engineering query. Read-only unless `--write`. Use this instead of hand-rolling `pymysql.connect()` (req #3196) |
| `scratch_db.py` | Create/drop a throwaway `darwin_scratch_*` database for the schema-parity gate. The only tool that runs `CREATE DATABASE`; guarded by the NAME, so it cannot address `darwin` or `darwin_dev` (req #3196) |
| `seed_domains_dev.py` | The canonical `domains`/`areas`/`tasks` fixture — 4 domains / 9 areas / 23 tasks for the dev login. Idempotent; `--reset --destructive` rebuilds (req #3196) |
| `seed_pipelines_darwin_dev.py` | Generate `seed_pipelines_darwin_dev.sql` from the LIVE req #3083 PLAN-JSON — the Substrate Rebuild plan as pipelines data (req #3111) |
| `seed_pipelines_darwin_dev.sql` | GENERATED. Declares `-- darwin:targets = darwin_dev`, so it is unaimable at production. Regenerate, never hand-edit |

## The target database is the caller's (req #3196)

`USE <db>;` is a STATEMENT, not a declaration — it re-points the session the moment it executes,
overriding whatever database the caller connected to. On 2026-08-01 that sent a probe aimed at a
scratch database into production. **No .sql file under `DarwinSQL/` may name its own database**;
`tests/test_sql_targets.py` fails the build on the next one, and `load_sql.py` refuses such a file
rather than silently stripping the statement.

A file whose target genuinely IS restricted declares a CONSTRAINT instead:

```sql
-- darwin:targets = darwin_dev     -- may ONLY be applied to darwin_dev
-- darwin:destructive              -- drops data; requires --destructive
```

Two absolutes, unoverridable by any flag: a target list that omits `darwin` is a production ban,
and a production-only file may not be aimed anywhere else. `--override-file-target` exists for one
case only — a dev-shaped file loaded into a scratch database for the schema-parity gate.

## Guardrails

All cleanup and seed scripts share 5 safety layers:

1. **The caller names the database, and production is named twice** — `db_guard.require_database`
   refuses `darwin` without `--production`, and refuses `--production` on anything else. (The
   older scripts still carry a hardcoded `darwin_dev` literal; `db_guard` is the pattern for
   anything new.)
2. **Runtime verification**: `SELECT DATABASE()` check before any mutation
3. **Table validation**: Only operates on known tables
4. **Dry-run default**: `--execute` flag required for actual deletes (cleanup scripts)
5. **No DDL in cleanup**: Only `DELETE FROM ... WHERE` — never DROP or TRUNCATE

## Cleanup Patterns

| Pattern | Source | Column |
|---------|--------|--------|
| `cognito-test-%` | Lambda-Cognito tests | profiles.id, *.creator_fk |
| `pytest-%` | Lambda-Rest tests | profiles.id, *.creator_fk |
| `schema-test-%` | DarwinSQL schema tests | profiles.id, *.creator_fk |
| 9 exact UUIDs | E2E test workers | *.creator_fk |

Deletion order respects foreign keys: priority_sessions → priorities → swarm_sessions → categories → projects → tasks → areas → domains → profiles.

## Usage

```bash
# Source credentials (from any Lambda directory)
cd Lambda-Rest && . exports.sh

# Dry run — see what would be deleted
python3 ../DarwinSQL/scripts/cleanup_darwin_dev.py

# Execute cleanup
python3 ../DarwinSQL/scripts/cleanup_darwin_dev.py --execute

# Seed darwin_dev from scratch
python3 ../DarwinSQL/scripts/seed_darwin_dev.py

# Seed worker profiles
python3 ../DarwinSQL/scripts/seed_e2e_workers.py
python3 ../DarwinSQL/scripts/seed_e2e_workers.py --database darwin

# Seed the domains/areas/tasks fixture
python3 ../DarwinSQL/scripts/seed_domains_dev.py darwin_dev

# Ask a question (read-only); change something (--write)
python3 ../DarwinSQL/scripts/query.py darwin_dev -e "SELECT COUNT(*) FROM tasks"

# Apply a file — production needs --production
python3 ../DarwinSQL/scripts/load_sql.py ../DarwinSQL/migrations/<MIG>.sql darwin_dev
python3 ../DarwinSQL/scripts/load_sql.py ../DarwinSQL/migrations/<MIG>.sql darwin --production

# Reset darwin_dev to canonical tables (DROPs 52 tables)
python3 ../DarwinSQL/scripts/load_sql.py \
  ../DarwinSQL/scripts/recreate_darwin_dev.sql darwin_dev --destructive

# Schema-parity gate — a scratch database for each schema-of-record file
python3 ../DarwinSQL/scripts/scratch_db.py create darwin_scratch_a
python3 ../DarwinSQL/scripts/load_sql.py ../DarwinSQL/schema.sql darwin_scratch_a
python3 ../DarwinSQL/scripts/scratch_db.py drop darwin_scratch_a --destructive
```

## add-api-route.sh

Adds a new `/darwin/{table_name}` resource to the Darwin REST API (API ID `k5j0ftr527`).
Requires darwinroot AWS credentials (`~/.darwin-credentials/aws_credentials.sh`).

```bash
# Load darwinroot credentials first
. ~/.darwin-credentials/aws_credentials.sh

# Dry run — print commands without executing
./DarwinSQL/scripts/add-api-route.sh --dry-run <table_name>

# Create route (ANY + OPTIONS methods, deploy to eng). Step 9 verifies the
# apigateway-{database}-wildcard resource-policy statement covers the route and
# adds NO per-table statement; it errors out if the wildcard is missing (a real
# authorization gap). No per-table lambda:AddPermission is ever emitted (req #3002).
./DarwinSQL/scripts/add-api-route.sh <table_name>

# List existing resources
./DarwinSQL/scripts/add-api-route.sh --list
```

## Prerequisites

Environment variables (from `exports.sh`):
- `endpoint` — RDS MySQL hostname
- `username` — Database username
- `db_password` — Database password
