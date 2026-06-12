"""Schema tests for swarm_sessions phase accumulators (req #2332, migration 059).

Verifies the new columns exist with correct types/defaults and that the
migration-059 backfill left every pre-existing row self-audit-balanced
(Σ buckets + legacy_secs ≈ started_at..completed_at).
"""

PHASE_BUCKETS = ['starting_secs', 'waiting_secs', 'planning_secs', 'implementing_secs',
                 'review_secs', 'completion_secs', 'paused_secs', 'legacy_secs']


def test_phase_columns_exist_with_types(db_connection):
    """All req #2332 columns present: 8 INT buckets, last_transition_at, instrumented."""
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE swarm_sessions")
        cols = {row['Field']: row for row in cur.fetchall()}

    for b in PHASE_BUCKETS:
        assert b in cols, f"missing bucket column {b}"
        assert cols[b]['Type'] == 'int', f"{b} type {cols[b]['Type']}"
        assert cols[b]['Null'] == 'NO', f"{b} should be NOT NULL"
        assert cols[b]['Default'] == '0', f"{b} default {cols[b]['Default']}"

    assert 'last_transition_at' in cols
    assert cols['last_transition_at']['Type'] == 'timestamp'
    assert cols['last_transition_at']['Null'] == 'YES'

    assert 'instrumented' in cols
    assert cols['instrumented']['Type'].startswith('tinyint')
    assert cols['instrumented']['Null'] == 'NO'
    assert cols['instrumented']['Default'] == '1'

    assert 'pre_pause_status' in cols
    assert cols['pre_pause_status']['Type'] == 'varchar(16)'
    assert cols['pre_pause_status']['Null'] == 'YES'


def test_backfill_self_audit_balances(db_connection):
    """Every legacy (instrumented=0) row's buckets+legacy sum to its wall span.

    Migration 059 puts the whole known total in legacy_secs (no fabricated split),
    so for legacy rows: Σbuckets == legacy_secs == started..completed (or ..NOW for
    in-flight, captured by last_transition_at at backfill time).
    """
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT id, instrumented, started_at, completed_at, last_transition_at, "
            "  (starting_secs+waiting_secs+planning_secs+implementing_secs+review_secs+"
            "   completion_secs+paused_secs+legacy_secs) AS bucket_sum, "
            "  TIMESTAMPDIFF(SECOND, COALESCE(started_at, create_ts), "
            "                COALESCE(completed_at, last_transition_at)) AS span "
            "FROM swarm_sessions WHERE instrumented = 0 AND started_at IS NOT NULL")
        rows = cur.fetchall()

    # Allow a tiny tolerance for rows whose span endpoint is NOW()-based (the
    # backfill stamped last_transition_at=NOW() for in-flight rows; a few seconds
    # may have elapsed between backfill and this read on a fresh apply).
    unbalanced = [r for r in rows if r['span'] is not None and abs(r['bucket_sum'] - r['span']) > 5]
    assert not unbalanced, f"legacy rows not balanced: {[(r['id'], r['bucket_sum'], r['span']) for r in unbalanced]}"


def test_legacy_rows_have_no_phase_split(db_connection):
    """instrumented=0 rows keep their whole total in legacy_secs — phase buckets stay 0."""
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM swarm_sessions "
            "WHERE instrumented = 0 AND (starting_secs+waiting_secs+planning_secs+"
            "implementing_secs+review_secs+completion_secs+paused_secs) > 0")
        assert cur.fetchone()['n'] == 0, "legacy rows must not carry a fabricated phase split"
