# DarwinSQL Scripts

## cleanup_darwin2.py

Removes orphaned test data from the `darwin2` test database after test runs.

### Guardrails

The script has 5 safety layers preventing any operation on production:

1. **Hardcoded database**: Connects to `darwin2` only (literal string)
2. **Runtime verification**: `SELECT DATABASE()` check before any DELETE
3. **Table suffix validation**: Only operates on `*2` tables
4. **Dry-run default**: `--execute` flag required for actual deletes
5. **No DDL**: Only `DELETE FROM ... WHERE` — never DROP or TRUNCATE

### Cleanup Patterns

| Pattern | Source | Column |
|---------|--------|--------|
| `cognito-test-%` | Lambda-Cognito tests | profiles2.id, *.creator_fk |
| `pytest-%` | Lambda-Rest tests | profiles2.id, *.creator_fk |

Deletion order respects foreign keys: tasks2 → areas2 → domains2 → profiles2.

### Usage

```bash
# Source credentials (from any Lambda directory)
cd Lambda-Rest && . exports.sh

# Dry run — see what would be deleted
python3 ../DarwinSQL/scripts/cleanup_darwin2.py

# Execute cleanup
python3 ../DarwinSQL/scripts/cleanup_darwin2.py --execute

# Chain after test run
pytest tests/ -v && python3 ../DarwinSQL/scripts/cleanup_darwin2.py --execute
```

### Prerequisites

Environment variables (from `exports.sh`):
- `endpoint` — RDS MySQL hostname
- `username` — Database username
- `db_password` — Database password
