"""Production snapshot freshness guard for DarwinSQL seed/import scripts.

Shared by `seed_build_projects.py` and `import_builds_json.py` (req #2691) so
both scripts apply the same rule: a production data mutation may proceed only
if a `darwin-pre-migration-*` manual RDS snapshot exists in `available` status
and was created within `SNAPSHOT_FRESHNESS_HOURS` (24h). Matches CLAUDE.md
§ Schema Migration Workflow Step 0.
"""
import subprocess
import sys
from datetime import datetime, timedelta, timezone

SNAPSHOT_FRESHNESS_HOURS = 24


def assert_recent_production_snapshot(operation_label='mutate'):
    """Exit with non-zero if no recent darwin-pre-migration-* snapshot exists.

    `operation_label` is included in the abort message so callers ("seed" vs.
    "import") read naturally in the failure output.
    """
    try:
        out = subprocess.check_output(
            [
                'aws', 'rds', 'describe-db-snapshots',
                '--db-instance-identifier', 'darwin',
                '--snapshot-type', 'manual',
                '--query',
                "DBSnapshots[?starts_with(DBSnapshotIdentifier,`darwin-pre-migration-`) "
                "&& Status==`available`].[DBSnapshotIdentifier,SnapshotCreateTime]",
                '--output', 'text',
            ],
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        sys.exit(
            f"ABORT: cannot verify production snapshot via "
            f"`aws rds describe-db-snapshots`: {e}. "
            f"Refusing to {operation_label} production without a recent rollback point."
        )
    cutoff = datetime.now(timezone.utc) - timedelta(hours=SNAPSHOT_FRESHNESS_HOURS)
    fresh = []
    for line in out.strip().splitlines():
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        snap_id, created = parts[0], parts[1]
        try:
            ts = datetime.fromisoformat(created.replace('Z', '+00:00'))
        except ValueError:
            continue
        if ts >= cutoff:
            fresh.append((snap_id, ts.isoformat()))
    if not fresh:
        sys.exit(
            f"ABORT: no available darwin-pre-migration-* snapshot newer than "
            f"{SNAPSHOT_FRESHNESS_HOURS}h. Create one before {operation_label}ing production:\n"
            f"  TS=$(date +%Y%m%d-%H%M%S)\n"
            f"  aws rds create-db-snapshot --db-instance-identifier darwin "
            f"--db-snapshot-identifier darwin-pre-migration-NNN-${{TS}}\n"
            f"  aws rds wait db-snapshot-available --db-snapshot-identifier "
            f"darwin-pre-migration-NNN-${{TS}}"
        )
    print(f"production snapshot guard ok — found {len(fresh)} fresh snapshot(s):")
    for snap_id, ts in fresh:
        print(f"  - {snap_id} @ {ts}")
