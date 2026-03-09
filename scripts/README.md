# DarwinSQL Scripts

## Script Inventory

| Script | Purpose |
|--------|---------|
| `cleanup_darwin_dev.py` | Remove orphaned test data from darwin_dev |
| `cleanup_e2e.py` | Comprehensive E2E test data cleanup (darwin or darwin_dev) |
| `seed_darwin_dev.py` | Create darwin_dev database, all 11 tables, and seed E2E test users |
| `seed_e2e_workers.py` | Seed 8 parallel E2E worker profiles |
| `recreate_darwin_dev.sql` | Drop and recreate all 11 darwin_dev tables from scratch |

## Guardrails

All cleanup and seed scripts share 5 safety layers:

1. **Hardcoded database**: Connects to `darwin_dev` only (literal string, not env var)
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
```

## Prerequisites

Environment variables (from `exports.sh`):
- `endpoint` — RDS MySQL hostname
- `username` — Database username
- `db_password` — Database password
