#!/usr/bin/env python3
"""Lock-view review fixture, darwin_dev only. (req #3761)

    . Lambda-Rest/exports.sh
    python3 DarwinSQL/scripts/seed_lock_view_dev.py darwin_dev                 # plan 10, idempotent
    python3 DarwinSQL/scripts/seed_lock_view_dev.py darwin_dev --pipeline 7
    python3 DarwinSQL/scripts/seed_lock_view_dev.py darwin_dev --reset --destructive

WHY THIS EXISTS. req #3761 adds the Lock view to the plan visualizer
(`/swarm/pipeline/<id>?mode=lock`): pipeline -> initiatives -> epics with the
lock cascade, the paused marks and the engine holders. Reviewing it on the dev
server needs a plan that shows every one of those, and a plan only shows what its
rows hold. This tops a plan up to the minimum the acceptance names: at least one
LOCKED INITIATIVE, one LOCKED EPIC, one PAUSED INITIATIVE and live ENGINE CLAIMS
(a lead and a subscriber on one initiative, a lead on another). It never
overwrites a state that is already there: a plan that already has a locked
initiative keeps that one and is not given a second.

THE CLAIMS ARE LIVE ON PURPOSE. A claim is stale ten minutes after its last
heartbeat (`orchestrationHolder.STALE_AFTER_SECONDS`), and a seeded heartbeat
that aged would turn the holder outlines grey while the reviewer was looking at
them. So the heartbeat is stamped far in the future; `heartbeatAgeSeconds`
floors a negative age at zero, which reads as "alive". The rows are marked by a
reserved terminal pid (`FIXTURE_TERMINAL_PIDS`) so `--reset` removes exactly
these and no real claim.

THE TARGET IS THE CALLER'S, same discipline as `seed_priority_polish_dev.py`:
through `db_guard`, before a connection opens. Never production.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_guard  # noqa: E402

TARGETS = ['darwin_dev']

# Reserved so --reset can find the fixture's own claims and nothing else.
FIXTURE_TERMINAL_PIDS = (71001, 71002, 71003)
LIVE_FOREVER = '2030-01-01 00:00:00'


def plan_rows(cur, pipeline_id):
    cur.execute('SELECT id, creator_fk, title FROM pipelines WHERE id = %s', (pipeline_id,))
    plan = cur.fetchone()
    if not plan:
        return None, [], []
    cur.execute('SELECT id, title, locked, initiative_status FROM initiatives '
                'WHERE pipeline_fk = %s ORDER BY id', (pipeline_id,))
    initiatives = cur.fetchall()
    cur.execute('SELECT e.id, e.initiative_fk, e.locked FROM epics e '
                'JOIN initiatives i ON i.id = e.initiative_fk '
                'WHERE i.pipeline_fk = %s ORDER BY e.id', (pipeline_id,))
    return plan, initiatives, cur.fetchall()


def top_up(cur, pipeline_id):
    plan, initiatives, epics = plan_rows(cur, pipeline_id)
    if not plan:
        raise SystemExit(f'REFUSED: pipeline {pipeline_id} does not exist in this database.')
    if len(initiatives) < 2:
        raise SystemExit(f'REFUSED: pipeline {pipeline_id} needs at least two initiatives '
                         f'to show locked, paused and held side by side (has {len(initiatives)}).')
    done = []

    if not any(int(i['locked']) for i in initiatives):
        victim = initiatives[-1]
        cur.execute('UPDATE initiatives SET locked = 1 WHERE id = %s', (victim['id'],))
        done.append(f"locked initiative {victim['id']}")

    # An epic locked in its own right, in an initiative that is not itself locked,
    # so the epic lock is visible apart from the cascade.
    free = [e for e in epics
            if not any(int(i['locked']) for i in initiatives if i['id'] == e['initiative_fk'])]
    if not any(int(e['locked']) for e in free) and free:
        cur.execute('UPDATE epics SET locked = 1 WHERE id = %s', (free[0]['id'],))
        done.append(f"locked epic {free[0]['id']}")

    paused_ids = {i['id'] for i in initiatives if i['initiative_status'] == 'paused'}
    if not paused_ids:
        victim = next((i for i in initiatives if not int(i['locked'])), initiatives[0])
        cur.execute("UPDATE initiatives SET initiative_status = 'paused' WHERE id = %s",
                    (victim['id'],))
        paused_ids.add(victim['id'])
        done.append(f"paused initiative {victim['id']}")

    cur.execute('SELECT id FROM machines WHERE closed = 0 ORDER BY id LIMIT 2')
    machines = [m['id'] for m in cur.fetchall()]
    cur.execute('SELECT COUNT(*) AS n FROM orchestration_claims '
                'WHERE pipeline_fk = %s AND terminal_pid IN %s',
                (pipeline_id, FIXTURE_TERMINAL_PIDS))
    if machines and cur.fetchone()['n'] == 0:
        # Held initiatives are the unpaused ones, so the outline and the pause
        # mark are not on the same band.
        held = [i for i in initiatives if i['id'] not in paused_ids] or initiatives
        lead_m, sub_m = machines[0], machines[-1]
        claims = [(held[0]['id'], lead_m, FIXTURE_TERMINAL_PIDS[0])]
        if sub_m != lead_m:
            claims.append((held[0]['id'], sub_m, FIXTURE_TERMINAL_PIDS[1]))
        if len(held) > 1:
            claims.append((held[1]['id'], sub_m, FIXTURE_TERMINAL_PIDS[2]))
        for initiative_id, machine_id, pid in claims:
            cur.execute(
                'INSERT INTO orchestration_claims '
                '(pipeline_fk, initiative_fk, machine_fk, terminal_pid, engine_pid, '
                ' creator_fk, update_ts) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (pipeline_id, initiative_id, machine_id, pid, pid + 100,
                 plan['creator_fk'], LIVE_FOREVER))
            done.append(f'claim initiative {initiative_id} on machine {machine_id}')
    return done


def reset(cur, pipeline_id):
    cur.execute('DELETE FROM orchestration_claims WHERE pipeline_fk = %s AND terminal_pid IN %s',
                (pipeline_id, FIXTURE_TERMINAL_PIDS))
    return cur.rowcount


def main():
    parser = argparse.ArgumentParser(
        prog='seed_lock_view_dev.py',
        description="Top a plan up with the Lock view's review states (req #3761). Never production.")
    db_guard.add_target_arguments(parser, override_file_target=False)
    parser.add_argument('--pipeline', type=int, default=10,
                        help='the plan to top up (default 10, "Tip of the Spear")')
    parser.add_argument('--reset', action='store_true',
                        help="Delete this fixture's own engine claims first, then re-seed.")
    args = parser.parse_args()

    try:
        db_guard.require_database(args.database, production=args.production)
        db_guard.require_declared_target(args.database, TARGETS, 'seed_lock_view_dev.py',
                                         overridable=False)
        if args.reset and not args.destructive:
            raise db_guard.GuardError(
                "REFUSED: --reset DELETEs this fixture's own engine claims. "
                'Re-run with --destructive to confirm.')
        conn = db_guard.connect(args.database)
    except db_guard.GuardError as exc:
        print(exc, file=sys.stderr)
        return 2

    db_guard.banner(args.database, 'seed_lock_view_dev.py fixture', TARGETS)

    try:
        with conn.cursor() as cur:
            removed = reset(cur, args.pipeline) if args.reset else None
            done = top_up(cur, args.pipeline)
        conn.commit()
    except SystemExit as exc:
        conn.rollback()
        print(exc, file=sys.stderr)
        return 2
    except Exception as exc:
        conn.rollback()
        print(f'status=error database={args.database}\nerror={exc}', file=sys.stderr)
        return 1
    finally:
        conn.close()

    if removed is not None:
        print(f'removed claims={removed}')
    print('\n'.join(done) if done else 'nothing to add: the plan already shows every state')
    return 0


if __name__ == '__main__':
    sys.exit(main())
