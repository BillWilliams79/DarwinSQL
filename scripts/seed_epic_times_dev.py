#!/usr/bin/env python3
"""Epic start/end time fixtures for the Pipeline plan visualizer. (req #3825)

    . Lambda-Rest/exports.sh
    python3 DarwinSQL/scripts/seed_epic_times_dev.py darwin_dev                 # idempotent
    python3 DarwinSQL/scripts/seed_epic_times_dev.py darwin_dev --reset --destructive

A plain run never rewrites a plan already present under PLAN_TITLE, so a
darwin_dev holding a fixture from an EARLIER version of this script keeps it
until re-seeded with `--reset --destructive`.

WHY THIS EXISTS. Req #3825 draws an epic card's START (its requirements' first
swarm start) in the card's lower-left corner and its END (the last requirement
coming back closed, once no work is open) in the lower-right. Both are derived
from rows `darwin_dev` does not otherwise hold together — linked swarm sessions
with `started_at`, and met requirements with `completed_at` — so without this
the time line renders blank, which is indistinguishable from broken.

A SIMULATION OF PRODUCTION, NOT A CASE LIST. The shapes are the ones measured
across production's 280 epics on 2026-10-23 (read-only): 220 epics hold one
requirement and the rest 2-21; 160 finished epics spanned under 2 hours, 54
2-12 hours, 15 12-24 hours and 11 more than a day; 4 requirements were
relaunched (two sessions — the START is the FIRST); one Primary-executed
requirement's only session is its closeout record, written 30 seconds AFTER
the requirement closed (epic 160 — it must show no start, never a start after
its end); and 8 epics were closed wontfix / deferred without ever launching.
Stamps are relative to NOW, two days back, so the plan spans several day
columns and both AM and PM:

  Initiative "Shipped"     a chain of finished epics — single, relaunched,
                           a wide 5-requirement epic crossing noon, a
                           Primary closeout (end only), a deferral closing an
                           epic (its END is the deferral — needs the
                           Lambda-Rest `deferred_at` projection deployed)
  Initiative "In flight"   a multi-day epic finished today, a running epic
                           (met + development + queued: start only), a
                           requirement with no session yet (its own
                           started_at), an epic holding a tracking container
                           (ignored), a never-launched wontfix (end only),
                           and queued work downstream (no time line)

THE TARGET IS THE CALLER'S, and production is banned before a connection opens,
through db_guard.
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_guard  # noqa: E402

TARGETS = ['darwin_dev']

# The dev-server login. Every read is scoped by creator_fk.
CREATOR_FK = '37df7531-000d-4470-8be4-1792d8261f69'

PLAN_TITLE = 'seed-3825: Epic start/end times'
PREFIX = '__epicseed/'
# PREFIX as a LIKE pattern: `_` is a one-character wildcard there.
PREFIX_LIKE = PREFIX.replace('_', '\\_') + '%'

# Each requirement: (title, status, session starts as hours-ago, own
# started_at hours-ago, closed hours-ago, tracking). `closed` stamps
# `completed_at` for met / wontfix and `deferred_at` for deferred — exactly
# what darwin-mcp's status transition writes, which also CLEARS `started_at`
# on every closed requirement. A session start of 'closeout' is the Primary's
# record, 30 seconds after the close.
R = lambda title, status, sessions=(), own=None, closed=None, tracking=False: (
    title, status, list(sessions), own, closed, tracking)

INITIATIVES = [
    ('Shipped', [
        ('ship-1', 'Schema groundwork', [], [
            R('Add the columns', 'met', [46.0], closed=45.3)]),
        ('ship-2', 'Read service (relaunched)', ['ship-1'], [
            R('Read service', 'met', [44.0, 41.5], closed=40.2)]),
        ('ship-3', 'Toolbar controls', ['ship-2'], [
            R('Time toggle', 'met', [39.5], closed=38.9),
            R('Closed toggle polish', 'met', [39.4], closed=37.7),
            R('Width ladder', 'met', [38.0], closed=36.1),
            R('Colour chips', 'met', [37.2], closed=35.0),
            R('Keyboard focus', 'met', [36.0], closed=33.6)]),
        ('ship-4', 'Primary-run verification', ['ship-3'], [
            R('Verification battery (Primary)', 'met', ['closeout'], closed=30.0)]),
        ('ship-5', 'Docs pass', ['ship-3'], [
            R('Guide chapter', 'met', [29.0], closed=28.2),
            R('Old appendix', 'deferred', closed=26.5)]),
    ]),
    ('In flight', [
        ('fly-1', 'Engine rewrite (multi-day)', ['ship-4'], [
            R('Engine rewrite', 'met', [27.0], closed=3.2)]),
        ('fly-2', 'Visualizer wiring', ['fly-1'], [
            R('Card time line', 'met', [6.5], closed=4.8),
            R('Canvas draw', 'development', [2.75], own=2.75),
            R('Thumbnail draw', 'swarm_ready')]),
        ('fly-3', 'Primary-run fix in progress', ['fly-1'], [
            R('Hotfix (no session yet)', 'development', own=1.25)]),
        ('fly-4', 'Plan container epic', ['fly-1'], [
            R('Plan tracker', 'development', [48.0], own=48.0, tracking=True),
            R('Measure', 'met', [9.0], closed=8.4)]),
        ('fly-5', 'Abandoned idea', ['ship-5'], [
            R('Idea', 'wontfix', closed=20.0)]),
        ('fly-6', 'Release notes', ['fly-2'], [
            R('Write notes', 'swarm_ready'),
            R('Publish', 'authoring')]),
    ]),
]


def stamp(now, hours):
    return None if hours is None else (now - datetime.timedelta(hours=hours)).strftime(
        '%Y-%m-%d %H:%M:%S')


def existing_plan(cur):
    cur.execute('SELECT id FROM pipelines WHERE title = %s AND creator_fk = %s',
                (PLAN_TITLE, CREATOR_FK))
    row = cur.fetchone()
    return row['id'] if row else None


def delete_fixture(cur):
    delete_plan(cur, existing_plan(cur))
    cur.execute('DELETE FROM swarm_sessions WHERE task_name LIKE %s AND creator_fk = %s',
                (PREFIX_LIKE, CREATOR_FK))
    cur.execute('DELETE FROM requirements WHERE title LIKE %s AND creator_fk = %s',
                (PREFIX_LIKE, CREATOR_FK))


def delete_plan(cur, plan_id):
    if plan_id is not None:
        cur.execute('SELECT s.id FROM epics s JOIN initiatives i ON i.id = s.initiative_fk '
                    'WHERE i.pipeline_fk = %s', (plan_id,))
        epic_ids = [r['id'] for r in cur.fetchall()]
        if epic_ids:
            marks = ','.join(['%s'] * len(epic_ids))
            cur.execute(f'DELETE FROM epic_deps WHERE epic_fk IN ({marks})', epic_ids)
            cur.execute(f'DELETE FROM epic_requirements WHERE epic_fk IN ({marks})',
                        epic_ids)
            cur.execute(f'DELETE FROM epics WHERE id IN ({marks})', epic_ids)
        cur.execute('DELETE FROM initiatives WHERE pipeline_fk = %s', (plan_id,))
        cur.execute('DELETE FROM pipelines WHERE id = %s', (plan_id,))


def seed(cur, category_fk):
    now = datetime.datetime.utcnow().replace(microsecond=0)
    cur.execute("INSERT INTO pipelines (title, description, pipeline_status, creator_fk) "
                "VALUES (%s, %s, 'active', %s)",
                (PLAN_TITLE, 'Req #3825 review fixture: production-shaped epic start/end times.',
                 CREATOR_FK))
    plan_id = cur.lastrowid
    epic_ids = {}
    for order, (initiative_title, epics) in enumerate(INITIATIVES, start=1):
        cur.execute("INSERT INTO initiatives (pipeline_fk, title, category_fk, sort_order, "
                    "creator_fk) VALUES (%s, %s, %s, %s, %s)",
                    (plan_id, initiative_title, category_fk, order, CREATOR_FK))
        initiative_id = cur.lastrowid
        for key, title, deps, reqs in epics:
            cur.execute("INSERT INTO epics (initiative_fk, title, run, checkpoint, "
                        "creator_fk) VALUES (%s, %s, 'auto', 0, %s)",
                        (initiative_id, title, CREATOR_FK))
            epic_ids[key] = cur.lastrowid
            for dep in deps:
                cur.execute('INSERT INTO epic_deps (epic_fk, dep_epic_fk) '
                            'VALUES (%s, %s)', (epic_ids[key], epic_ids[dep]))
            for rtitle, status, sessions, own_h, closed_h, tracking in reqs:
                completed_h = closed_h if status in ('met', 'wontfix') else None
                deferred_h = closed_h if status == 'deferred' else None
                cur.execute(
                    "INSERT INTO requirements (title, requirement_status, category_fk, "
                    "coordination_type, ai_model, effort, tracking, started_at, completed_at, "
                    "deferred_at, creator_fk) "
                    "VALUES (%s, %s, %s, 'implemented', 'opus', 'high', %s, %s, %s, %s, %s)",
                    (PREFIX + rtitle, status, category_fk, 1 if tracking else 0,
                     stamp(now, own_h), stamp(now, completed_h), stamp(now, deferred_h),
                     CREATOR_FK))
                req_id = cur.lastrowid
                cur.execute('INSERT INTO epic_requirements (epic_fk, requirement_fk) '
                            'VALUES (%s, %s)', (epic_ids[key], req_id))
                for i, session_h in enumerate(sessions):
                    if session_h == 'closeout':
                        session_h = closed_h - 30 / 3600
                    live = status == 'development' and i == len(sessions) - 1
                    cur.execute(
                        "INSERT INTO swarm_sessions (task_name, title, swarm_status, source_ref, "
                        "started_at, creator_fk) VALUES (%s, %s, %s, %s, %s, %s)",
                        (f'{PREFIX}{req_id}-{i}', rtitle, 'active' if live else 'completed',
                         f'requirement:{req_id}', stamp(now, session_h), CREATOR_FK))
                    cur.execute('INSERT INTO requirement_sessions (requirement_fk, session_fk) '
                                'VALUES (%s, %s)', (req_id, cur.lastrowid))
    return plan_id


def main():
    parser = argparse.ArgumentParser(
        description='Seed epic start/end time fixtures for the plan visualizer (req #3825).')
    db_guard.add_target_arguments(parser, override_file_target=False)
    parser.add_argument('--reset', action='store_true',
                        help="DELETE this fixture's rows before re-seeding.")
    args = parser.parse_args()

    try:
        db_guard.require_database(args.database, production=args.production)
        db_guard.require_declared_target(args.database, TARGETS,
                                         'seed_epic_times_dev.py', overridable=False)
        if args.reset and not args.destructive:
            raise db_guard.GuardError(
                "REFUSED: --reset DELETEs this fixture's rows. "
                "Re-run with --destructive to confirm.")
        conn = db_guard.connect(args.database)
    except db_guard.GuardError as exc:
        print(exc, file=sys.stderr)
        return 2

    db_guard.banner(args.database, 'seed_epic_times_dev.py fixture', TARGETS)

    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM profiles WHERE id = %s', (CREATOR_FK,))
            if not cur.fetchone():
                print(f'REFUSED: profile {CREATOR_FK} does not exist in {args.database!r}.',
                      file=sys.stderr)
                return 2
            if args.reset:
                delete_fixture(cur)
            plan_id = existing_plan(cur)
            created = plan_id is None
            if created:
                cur.execute("SELECT id FROM categories WHERE creator_fk = %s AND closed = 0 "
                            "ORDER BY id LIMIT 1", (CREATOR_FK,))
                category = cur.fetchone()
                if not category:
                    print('REFUSED: no open category to file the fixture under.',
                          file=sys.stderr)
                    return 2
                plan_id = seed(cur, category['id'])
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f'status=error database={args.database}\nerror={exc}', file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(f"status=ok database={args.database} pipeline={plan_id} "
          f"{'created' if created else 'already-present'}")
    print(f'open=/swarm/pipeline/{plan_id}?mode=plan')
    return 0


if __name__ == '__main__':
    sys.exit(main())
