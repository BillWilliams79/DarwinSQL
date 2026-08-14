#!/usr/bin/env python3
"""'Priority Polish' colour-key review fixture, darwin_dev only. (req #3503)

    . Lambda-Rest/exports.sh
    python3 DarwinSQL/scripts/seed_priority_polish_dev.py darwin_dev            # idempotent
    python3 DarwinSQL/scripts/seed_priority_polish_dev.py darwin_dev --reset    # rebuild it

WHY THIS EXISTS. req #3503 reworked the Pipeline plan visualizer's requirement
colour scales (State/Autonomy/Machine) and their stack-order sort. Reviewing
that on the dev server needs one requirement per `requirement_status` value —
seven of them — each carrying a `coordination_type` so both scales have
something to colour and sort. Production carries no such set on demand; this
script is the reviewable fixture.

THE PAIRING (user directive, verbatim): "Make priority polish have a set of
requirements that include one each of the status values, and then the
corresponding settings for autonomy in order — Authoring/Discuss is first,
then Approved, Planned is second, and so on. If you need extra default
values, choose the green one." `requirement_status` runs seven long
(REQ_STATUS_ORDER) and `coordination_type` only four (AUTONOMY_ORDER), so the
first four statuses pair one-to-one with the ladder and the remaining three
(met, deferred, wontfix) all take `deployed` — the green rung — as the
directive's own named filler.

THE TARGET IS THE CALLER'S, same discipline as `seed_domains_dev.py`: through
`db_guard`, before a connection opens. Never production — this is throwaway
review data, not a roadmap entry.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_guard  # noqa: E402

# Non-production only — this is disposable review data, never a real
# requirement, and req #3503's own requirement already lives in production.
TARGETS = ['darwin_dev']

# The dev-server login (`Bill W`) — same as `seed_domains_dev.py`'s CREATOR_FK.
# Everything the app reads is scoped by creator_fk, so seeding anyone else
# produces rows the browser never shows.
CREATOR_FK = '37df7531-000d-4470-8be4-1792d8261f69'

PROJECT_FK = 1  # 'Darwin' — the same project every other darwin_dev category sits under.

CATEGORY_NAME = 'Priority Polish'
# A neutral slate — this category exists to hold colour-scale TEST rows, so it
# borrows no meaning from an existing production category's colour.
CATEGORY_COLOR = '#8fa4c4'

# (requirement_status, coordination_type) — REQ_STATUS_ORDER order, paired
# one-to-one against AUTONOMY_ORDER for the first four, `deployed` (the green
# rung) as filler for the three the ladder ran out for. See module docstring.
FIXTURE = [
    ('authoring', 'discuss'),
    ('approved', 'planned'),
    ('swarm_ready', 'implemented'),
    ('development', 'deployed'),
    ('met', 'deployed'),
    ('deferred', 'deployed'),
    ('wontfix', 'deployed'),
]

TITLE_PREFIX = 'Priority Polish fixture'


def _title(status, coordination):
    return f'{TITLE_PREFIX} — {status} / {coordination}'


def ensure_category(cur):
    cur.execute(
        'SELECT id FROM categories WHERE creator_fk = %s AND project_fk = %s '
        'AND category_name = %s',
        (CREATOR_FK, PROJECT_FK, CATEGORY_NAME),
    )
    row = cur.fetchone()
    if row:
        return row['id'], False
    cur.execute(
        'INSERT INTO categories (category_name, project_fk, creator_fk, color, sort_order) '
        'VALUES (%s, %s, %s, %s, %s)',
        (CATEGORY_NAME, PROJECT_FK, CREATOR_FK, CATEGORY_COLOR, 99),
    )
    return cur.lastrowid, True


def seed(cur, category_id):
    inserted = 0
    for status, coordination in FIXTURE:
        title = _title(status, coordination)
        cur.execute(
            'SELECT id FROM requirements WHERE creator_fk = %s AND category_fk = %s '
            'AND title = %s',
            (CREATOR_FK, category_id, title),
        )
        if cur.fetchone():
            continue
        # `completed_at`/`deferred_at` mirror what a real requirement in each
        # terminal status would carry — req #3122's `met`/`wontfix`
        # terminal-timestamp convention, and `deferred_at` alongside it.
        completed_at_sql = 'CURRENT_TIMESTAMP' if status in ('met', 'wontfix') else 'NULL'
        deferred_at_sql = 'CURRENT_TIMESTAMP' if status == 'deferred' else 'NULL'
        cur.execute(
            'INSERT INTO requirements '
            '(title, description, requirement_status, coordination_type, '
            ' ai_model, effort, category_fk, creator_fk, completed_at, deferred_at) '
            f'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, {completed_at_sql}, {deferred_at_sql})',
            (title,
             f'Fixture requirement (req #3503) — requirement_status={status!r}, '
             f'coordination_type={coordination!r}. Exists only to give the Pipeline plan '
             "visualizer's State/Autonomy colour keys something of every value to draw "
             'and sort during manual UI review.',
             status, coordination, 'opus', 'high', category_id, CREATOR_FK),
        )
        inserted += 1
    return inserted


def delete_fixture(cur, category_id):
    cur.execute(
        'DELETE FROM requirements WHERE creator_fk = %s AND category_fk = %s '
        "AND title LIKE %s",
        (CREATOR_FK, category_id, f'{TITLE_PREFIX}%'),
    )
    return cur.rowcount


def main():
    parser = argparse.ArgumentParser(
        prog='seed_priority_polish_dev.py',
        description="Seed the 'Priority Polish' status/autonomy colour-key fixture "
                     '(req #3503). Never production.',
    )
    db_guard.add_target_arguments(parser, override_file_target=False)
    parser.add_argument('--reset', action='store_true',
                        help="Delete this fixture's own requirement rows first, "
                             're-seed after (the category itself is kept).')
    args = parser.parse_args()

    try:
        db_guard.require_database(args.database, production=args.production)
        db_guard.require_declared_target(args.database, TARGETS, 'seed_priority_polish_dev.py',
                                         overridable=False)
        if args.reset and not args.destructive:
            raise db_guard.GuardError(
                "REFUSED: --reset DELETEs this fixture's own requirement rows. "
                'Re-run with --destructive to confirm.'
            )
        conn = db_guard.connect(args.database)
    except db_guard.GuardError as exc:
        print(exc, file=sys.stderr)
        return 2

    db_guard.banner(args.database, 'seed_priority_polish_dev.py fixture', TARGETS)

    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM profiles WHERE id = %s', (CREATOR_FK,))
            if not cur.fetchone():
                print(f'REFUSED: profile {CREATOR_FK} does not exist in '
                      f'{args.database!r}; seed it first (seed_darwin_dev.py).',
                      file=sys.stderr)
                return 2
            category_id, category_created = ensure_category(cur)
            removed = delete_fixture(cur, category_id) if args.reset else None
            inserted = seed(cur, category_id)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f'status=error database={args.database}\nerror={exc}', file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(f'category_id={category_id} category_created={category_created}')
    if removed is not None:
        print(f'removed requirements={removed}')
    print(f'inserted requirements={inserted}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
