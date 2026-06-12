#!/usr/bin/env python3
"""Seed darwin_dev with session phase-accumulator fixtures (req #2332).

Provides the two data categories the downstream visualizer/stats requirements
(#2823 broad pan, #2824 single-requirement isolation, #2825 stats) need on day one:

  1. MIGRATED   — instrumented=0, whole total in legacy_secs, phase buckets 0.
                  Mirrors what migration 059 did to pre-#2332 rows (no fabricated split).
  2. NATIVE     — instrumented=1, realistic per-phase buckets, one per coordination
                  type (deployed has review_secs=0; discuss has waiting_secs>0), plus
                  one in-flight native session still accruing.

Idempotent: deletes prior fixtures (task_name LIKE '__phaseseed/%') then re-inserts.
Targets darwin_dev ONLY.

Usage:
    cd Lambda-Rest && . exports.sh && python3 ../DarwinSQL/scripts/seed_session_phases_dev.py
"""
import os
import sys
import pymysql

PREFIX = "__phaseseed/"
BUCKETS = ["starting_secs", "waiting_secs", "planning_secs", "implementing_secs",
           "review_secs", "completion_secs", "paused_secs", "legacy_secs"]


def conn():
    for var in ("endpoint", "username", "db_password"):
        if var not in os.environ:
            sys.exit(f"Error: {var} not set. Run: . exports.sh (from Lambda-Rest/)")
    return pymysql.connect(host=os.environ["endpoint"], user=os.environ["username"],
                           password=os.environ["db_password"], database="darwin_dev",
                           autocommit=True, cursorclass=pymysql.cursors.DictCursor)


def creator(cur):
    cur.execute("SELECT creator_fk FROM swarm_sessions ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if not row:
        cur.execute("SELECT id FROM profiles LIMIT 1")
        p = cur.fetchone()
        if not p:
            sys.exit("No profiles in darwin_dev to own seed rows.")
        return p["id"]
    return row["creator_fk"]


def insert(cur, cfk, name, title, status, coord, instrumented, buckets,
           completed=True, total_offset_days=1):
    """Insert one fixture. started_at/completed_at are derived so the self-audit
    (Σbuckets+legacy ≈ completed_at-started_at) balances exactly."""
    total = sum(buckets.get(b, 0) for b in BUCKETS)
    cols = {b: buckets.get(b, 0) for b in BUCKETS}
    cols.update({
        "task_name": PREFIX + name,
        "branch": f"feature/{name}",
        "source_type": "roadmap",
        "title": title,
        "swarm_status": status,
        "instrumented": instrumented,
        "creator_fk": cfk,
    })
    # started_at = completed_at - total; completed rows terminal (last_transition_at NULL),
    # in-flight rows keep accruing (last_transition_at = NOW()).
    if completed:
        started_expr = f"NOW() - INTERVAL {total_offset_days} DAY - INTERVAL {total} SECOND"
        completed_expr = f"NOW() - INTERVAL {total_offset_days} DAY"
        ltrans_expr = "NULL"
    else:
        started_expr = f"NOW() - INTERVAL {total} SECOND"
        completed_expr = "NULL"
        ltrans_expr = "NOW()"
    keys = list(cols.keys())
    placeholders = ", ".join(["%s"] * len(keys))
    sql = (f"INSERT INTO swarm_sessions ({', '.join(keys)}, started_at, completed_at, last_transition_at) "
           f"VALUES ({placeholders}, {started_expr}, {completed_expr}, {ltrans_expr})")
    cur.execute(sql, [cols[k] for k in keys])


# Demo requirements (req #2332): one requirement per session status, each tied to a
# session in that status via source_ref="requirement:<id>" — which is how the
# requirements page derives a requirement's session-status indicator. Lets you see
# every status value on the requirements page.
DEMO_STATUS_PHASES = {
    'starting':   {},
    'waiting':    {'starting_secs': 30},
    'planning':   {'starting_secs': 30},
    'active':     {'starting_secs': 30, 'planning_secs': 200},
    'review':     {'starting_secs': 30, 'planning_secs': 200, 'implementing_secs': 1500},
    'paused':     {'starting_secs': 30, 'planning_secs': 200, 'implementing_secs': 800},
    'completing': {'starting_secs': 30, 'planning_secs': 200, 'implementing_secs': 1500, 'review_secs': 900},
    'completed':  {'starting_secs': 30, 'planning_secs': 200, 'implementing_secs': 1500,
                   'review_secs': 900, 'completion_secs': 80},
}


def insert_demo(cur, cfk, status, phases):
    """Create a demo requirement + a linked session in `status` (with phase data)."""
    cur.execute(
        "INSERT INTO requirements (title, description, requirement_status, category_fk, "
        "creator_fk, coordination_type) VALUES (%s, %s, %s, %s, %s, %s)",
        (f"DEMO 2332: session is {status}",
         f"Demo for req #2332 — its linked swarm session is in '{status}' status, so this "
         f"requirement's session-status indicator shows '{status}' on the requirements page.",
         'development', 1, cfk, 'implemented'))
    req_id = cur.lastrowid

    total = sum(phases.values())
    completed = (status == 'completed')
    cols = {b: phases.get(b, 0) for b in BUCKETS}
    cols.update({
        'task_name': PREFIX + 'demo-' + status,
        'branch': f'feature/demo-{status}',
        'source_type': 'roadmap',
        'source_ref': f'requirement:{req_id}',   # ← drives the requirement-page status icon
        'title': f'DEMO session ({status})',
        'swarm_status': status,
        'instrumented': 1,
        'creator_fk': cfk,
    })
    if completed:
        started, comp, ltr = (f"NOW() - INTERVAL 1 DAY - INTERVAL {total} SECOND",
                              "NOW() - INTERVAL 1 DAY", "NULL")
    else:
        started, comp, ltr = (f"NOW() - INTERVAL {total} SECOND", "NULL", "NOW()")
    keys = list(cols.keys())
    ph = ", ".join(["%s"] * len(keys))
    cur.execute(
        f"INSERT INTO swarm_sessions ({', '.join(keys)}, started_at, completed_at, last_transition_at) "
        f"VALUES ({ph}, {started}, {comp}, {ltr})", [cols[k] for k in keys])
    sess_id = cur.lastrowid
    if status == 'paused':
        cur.execute("UPDATE swarm_sessions SET pre_pause_status='active' WHERE id=%s", (sess_id,))
    cur.execute("INSERT INTO requirement_sessions (requirement_fk, session_fk) VALUES (%s, %s)",
                (req_id, sess_id))
    return req_id, sess_id


def main():
    c = conn()
    with c.cursor() as cur:
        cfk = creator(cur)
        cur.execute("DELETE FROM swarm_sessions WHERE task_name LIKE %s", (PREFIX + "%",))
        cur.execute("DELETE FROM requirements WHERE title LIKE %s", ("DEMO 2332:%",))
        print(f"cleared prior fixtures: {cur.rowcount}")

        # --- MIGRATED (instrumented=0, legacy lump only) ---
        insert(cur, cfk, "migrated-old-feature-a", "Migrated: legacy completed session A",
               "completed", "implemented", 0, {"legacy_secs": 5400}, total_offset_days=20)
        insert(cur, cfk, "migrated-old-feature-b", "Migrated: legacy completed session B",
               "completed", "planned", 0, {"legacy_secs": 12600}, total_offset_days=15)
        insert(cur, cfk, "migrated-inflight", "Migrated: legacy in-flight (partial)",
               "active", "implemented", 0, {"legacy_secs": 3000}, completed=False)

        # --- NATIVE (instrumented=1, real phase buckets), one per coordination type ---
        insert(cur, cfk, "native-deployed", "Native: deployed (no review phase)",
               "completed", "deployed", 1,
               {"starting_secs": 45, "planning_secs": 120, "implementing_secs": 900,
                "review_secs": 0, "completion_secs": 70}, total_offset_days=2)
        insert(cur, cfk, "native-implemented", "Native: implemented (review by human)",
               "completed", "implemented", 1,
               {"starting_secs": 50, "planning_secs": 200, "implementing_secs": 1500,
                "review_secs": 1800, "completion_secs": 90}, total_offset_days=3)
        insert(cur, cfk, "native-planned", "Native: planned (planning incl. approval wait)",
               "completed", "planned", 1,
               {"starting_secs": 40, "planning_secs": 600, "implementing_secs": 2400,
                "review_secs": 1200, "completion_secs": 85}, total_offset_days=4)
        insert(cur, cfk, "native-discuss", "Native: discuss (idle wait then directed work)",
               "completed", "discuss", 1,
               {"starting_secs": 30, "waiting_secs": 3600, "planning_secs": 300,
                "implementing_secs": 800, "review_secs": 400, "completion_secs": 60},
               total_offset_days=5)
        insert(cur, cfk, "native-paused", "Native: paused mid-implementation then resumed",
               "completed", "implemented", 1,
               {"starting_secs": 48, "planning_secs": 180, "implementing_secs": 1100,
                "paused_secs": 7200, "review_secs": 600, "completion_secs": 75},
               total_offset_days=6)
        # full-spread completed session: EVERY phase bucket nonzero, so the detail
        # page shows a complete breakdown (agentic + machine + human all present).
        insert(cur, cfk, "native-full-spread", "Native: FULL phase spread (every bucket nonzero)",
               "completed", "planned", 1,
               {"starting_secs": 60, "waiting_secs": 120, "planning_secs": 300,
                "implementing_secs": 1800, "review_secs": 900, "completion_secs": 90,
                "paused_secs": 600}, total_offset_days=1)
        # in-flight native: currently planning, accruing
        insert(cur, cfk, "native-inflight-planning", "Native: in-flight, currently planning",
               "planning", "planned", 1, {"starting_secs": 35}, completed=False)
        # in-flight native: discuss worker currently waiting on the user
        insert(cur, cfk, "native-inflight-waiting", "Native: in-flight, discuss waiting on user",
               "waiting", "discuss", 1, {"starting_secs": 22}, completed=False)
        # in-flight native: currently paused (pre_pause_status recorded) — shows resume-restore data
        insert(cur, cfk, "native-inflight-paused", "Native: in-flight, paused mid-implementation",
               "paused", "implemented", 1, {"starting_secs": 40, "planning_secs": 150, "implementing_secs": 900},
               completed=False)
        # the engine sets pre_pause_status on a real pause; the seed inserts directly, so set it
        # explicitly to mirror a session paused while in 'active' (implementing).
        cur.execute("UPDATE swarm_sessions SET pre_pause_status='active' "
                    "WHERE task_name='__phaseseed/native-inflight-paused'")

        # --- DEMO requirements: one per session status, each tied to a requirement so
        #     the requirements page shows every status indicator (req #2332) ---
        demo = []
        for st in ['starting', 'waiting', 'planning', 'active', 'review', 'paused',
                   'completing', 'completed']:
            rid, sid = insert_demo(cur, cfk, st, DEMO_STATUS_PHASES[st])
            demo.append((st, rid, sid))
        print("demo requirements (category 'Swarm', requirement_status='development'):")
        for st, rid, sid in demo:
            print(f"  {st:11} → requirement #{rid}  (session #{sid})")

        # --- verify self-audit balance on the inserted fixtures ---
        cur.execute(
            "SELECT task_name, instrumented, "
            "  (starting_secs+waiting_secs+planning_secs+implementing_secs+review_secs+"
            "   completion_secs+paused_secs+legacy_secs) AS bucket_sum, "
            "  TIMESTAMPDIFF(SECOND, started_at, COALESCE(completed_at, last_transition_at)) AS span "
            "FROM swarm_sessions WHERE task_name LIKE %s ORDER BY id", (PREFIX + "%",))
        rows = cur.fetchall()
        bad = [r for r in rows if r["bucket_sum"] != r["span"]]
        for r in rows:
            flag = "OK " if r["bucket_sum"] == r["span"] else "BAD"
            print(f"  {flag} {r['task_name']:42} instr={r['instrumented']} "
                  f"sum={r['bucket_sum']} span={r['span']}")
        print(f"\nseeded {len(rows)} fixtures ({sum(1 for r in rows if r['instrumented']==0)} migrated, "
              f"{sum(1 for r in rows if r['instrumented']==1)} native)")
        if bad:
            sys.exit(f"AUDIT FAILED on {len(bad)} rows")
        print("self-audit: ALL BALANCED")


if __name__ == "__main__":
    main()
