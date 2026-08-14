#!/usr/bin/env python3
"""The canonical domains / areas / tasks fixture for a non-production database. (req #3196)

    . Lambda-Rest/exports.sh
    python3 DarwinSQL/scripts/seed_domains_dev.py darwin_dev            # idempotent
    python3 DarwinSQL/scripts/seed_domains_dev.py darwin_dev --reset    # rebuild it

WHY THIS EXISTS. On 2026-08-01 (req #3186 session 2518) `recreate_darwin_dev.sql`
reset `darwin_dev` to empty tables. Everything else was rebuilt from a canonical
seed — the pipeline fixture, requirements, epics, the since-retired Feature
catalog, phase fixtures, build-viz — but `areas` and `tasks` had no canonical
seed, so they came back
empty and NOBODY KNEW WHAT THEY HAD HELD. Measured 2026-08-07: `domains` 6 (all
of them e2e-worker leftovers), `areas` 0, `tasks` 0. The real dev account had no
domain data at all.

THE DECISION (req #3196 scope item 4): RESEED, with this file as the fixture of
record. The alternative — accept empty and record it — would leave Darwin's
primary view, `/taskcards`, unreviewable on the dev server: an empty page is
indistinguishable from a broken one, which is the recurring trap already
documented in memory/database.md § Seeding darwin_dev. A fixture that lives in
the repo also means the next reset is a re-run of this script rather than
another archaeology problem.

WHAT IT IS NOT. Not a copy of production. The shape is chosen to exercise the
views — an open and a closed domain, open and closed areas, priority and
non-priority tasks, done and not-done, a task with no area — not to reproduce
anyone's real data. Task text is obviously synthetic on purpose.

THE TARGET IS THE CALLER'S, and production is banned the same way
`recreate_darwin_dev.sql` bans it: through `db_guard`, before a connection opens.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_guard  # noqa: E402

# Non-production only, enforced by db_guard.require_declared_target — the same
# absolute production ban the .sql files declare with `-- darwin:targets`.
TARGETS = ['darwin_dev']

# The dev-server login (`Bill W`). Seeding anyone else produces rows the browser
# never shows, because every read is scoped by creator_fk.
CREATOR_FK = '37df7531-000d-4470-8be4-1792d8261f69'

# domain_name / area_name are VARCHAR(32).
#   (domain_name, closed, sort_order, [ (area_name, closed, sort_order, [tasks]) ])
#   task: (description, priority, done)
FIXTURE = [
    ('Home', 0, 1, [
        ('Kitchen', 0, 1, [
            ('Fixture task — replace the tap washer', 1, 0),
            ('Fixture task — descale the kettle', 0, 0),
            ('Fixture task — order dishwasher salt', 0, 1),
        ]),
        ('Garden', 0, 2, [
            ('Fixture task — prune the apple tree', 1, 0),
            ('Fixture task — mulch the raised beds', 0, 0),
            ('Fixture task — fix the gate latch', 0, 1),
            ('Fixture task — sharpen the mower blade', 0, 0),
        ]),
        ('Garage (closed)', 1, 3, [
            ('Fixture task — sort the paint shelf', 0, 0),
        ]),
    ]),
    ('Work', 0, 2, [
        ('Planning', 0, 1, [
            ('Fixture task — draft next quarter goals', 1, 0),
            ('Fixture task — review the roadmap', 1, 0),
            ('Fixture task — book the offsite room', 0, 1),
        ]),
        ('Admin', 0, 2, [
            ('Fixture task — file the expense report', 0, 0),
            ('Fixture task — renew the parking permit', 0, 0),
        ]),
        ('Reading', 0, 3, [
            ('Fixture task — finish the design paper', 0, 0),
            ('Fixture task — skim the release notes', 0, 1),
            ('Fixture task — write up the reading notes', 1, 0),
        ]),
    ]),
    ('Health', 0, 3, [
        ('Training', 0, 1, [
            ('Fixture task — 40km ride Saturday', 1, 0),
            ('Fixture task — swim session Tuesday', 0, 0),
            ('Fixture task — replace the bar tape', 0, 1),
        ]),
        ('Appointments', 0, 2, [
            ('Fixture task — book the dental check', 1, 0),
            ('Fixture task — collect the prescription', 0, 0),
        ]),
    ]),
    ('Archive (closed)', 1, 4, [
        ('Old projects', 1, 1, [
            ('Fixture task — archived, nothing to do', 0, 1),
        ]),
    ]),
]

# One task deliberately has no area: `tasks.area_fk` is NULLable and the views
# have to cope. Nothing else in the fixture exercises that path.
ORPHAN_TASK = ('Fixture task — unfiled, no area (area_fk IS NULL)', 0, 0)

FIXTURE_DOMAIN_NAMES = [d[0] for d in FIXTURE]
FIXTURE_AREA_NAMES = sorted({a[0] for _, _, _, areas in FIXTURE for a in areas})
FIXTURE_TASK_DESCRIPTIONS = sorted(
    {t[0] for _, _, _, areas in FIXTURE for a in areas for t in a[3]}
    | {ORPHAN_TASK[0]}
)


def counts(cur):
    out = {}
    for table in ('domains', 'areas', 'tasks'):
        cur.execute(f'SELECT COUNT(*) AS n FROM `{table}` WHERE creator_fk = %s',
                    (CREATOR_FK,))
        out[table] = cur.fetchone()['n']
    return out


def _in(values):
    return ', '.join(['%s'] * len(values))


def delete_fixture(cur):
    """Remove ONLY the rows this fixture itself creates, leaves-first.

    IT DELETES BY THE FIXTURE'S OWN VALUES, NOT BY CONTAINER (req #3196 review,
    W5). An earlier version deleted every task under any area under a domain
    named `Home`, which destroys hand-made rows a reviewer put there — and worse,
    `areas.domain_fk`, `tasks.area_fk` and `recurring_tasks.area_fk` are all
    ON DELETE CASCADE, so deleting a fixture domain reached `recurring_tasks`, a
    table this script never names, never counts and never re-seeds.

    So the cascade is never allowed to fire on anything: before removing a
    container, this REFUSES if the container still holds a row the fixture did
    not create. A reset that would take a stranger's data with it is a stop, not
    a shrug — leaving a domain behind is recoverable, deleting rows nobody can
    identify is not.
    """
    cur.execute(
        f'DELETE FROM tasks WHERE creator_fk = %s '
        f'AND description IN ({_in(FIXTURE_TASK_DESCRIPTIONS)})',
        (CREATOR_FK, *FIXTURE_TASK_DESCRIPTIONS),
    )
    tasks_gone = cur.rowcount

    # Fixture areas, identified by (domain name, area name) — ids, so the
    # survivor checks below and the DELETEs address exactly the same rows.
    cur.execute(
        f'SELECT a.id FROM areas a JOIN domains d ON a.domain_fk = d.id '
        f'WHERE d.creator_fk = %s AND d.domain_name IN ({_in(FIXTURE_DOMAIN_NAMES)}) '
        f'AND a.area_name IN ({_in(FIXTURE_AREA_NAMES)})',
        (CREATOR_FK, *FIXTURE_DOMAIN_NAMES, *FIXTURE_AREA_NAMES),
    )
    area_ids = [r['id'] for r in cur.fetchall()]

    if area_ids:
        for table in ('tasks', 'recurring_tasks'):
            cur.execute(
                f'SELECT COUNT(*) AS n FROM `{table}` WHERE area_fk IN ({_in(area_ids)})',
                tuple(area_ids),
            )
            stranded = cur.fetchone()['n']
            if stranded:
                raise RuntimeError(
                    f'refusing --reset: {stranded} row(s) in `{table}` sit under a '
                    f'fixture area and were not created by this fixture. Deleting '
                    f'the area would CASCADE and take them with it. Move or delete '
                    f'them deliberately first.'
                )
        cur.execute(f'DELETE FROM areas WHERE id IN ({_in(area_ids)})', tuple(area_ids))
    areas_gone = cur.rowcount if area_ids else 0

    cur.execute(
        f'SELECT id FROM domains WHERE creator_fk = %s '
        f'AND domain_name IN ({_in(FIXTURE_DOMAIN_NAMES)})',
        (CREATOR_FK, *FIXTURE_DOMAIN_NAMES),
    )
    domain_ids = [r['id'] for r in cur.fetchall()]

    if domain_ids:
        cur.execute(
            f'SELECT COUNT(*) AS n FROM areas WHERE domain_fk IN ({_in(domain_ids)})',
            tuple(domain_ids),
        )
        stranded = cur.fetchone()['n']
        if stranded:
            raise RuntimeError(
                f'refusing --reset: {stranded} area(s) remain under a fixture domain '
                f'and were not created by this fixture. Deleting the domain would '
                f'CASCADE into them and their tasks. Move or delete them first.'
            )
        cur.execute(f'DELETE FROM domains WHERE id IN ({_in(domain_ids)})',
                    tuple(domain_ids))
    domains_gone = cur.rowcount if domain_ids else 0

    return {'domains': domains_gone, 'areas': areas_gone, 'tasks': tasks_gone}


def seed(cur):
    inserted = {'domains': 0, 'areas': 0, 'tasks': 0}
    for domain_name, domain_closed, domain_sort, areas in FIXTURE:
        cur.execute(
            'SELECT id FROM domains WHERE creator_fk = %s AND domain_name = %s',
            (CREATOR_FK, domain_name),
        )
        row = cur.fetchone()
        if row:
            domain_id = row['id']
        else:
            cur.execute(
                'INSERT INTO domains (domain_name, creator_fk, closed, sort_order) '
                'VALUES (%s, %s, %s, %s)',
                (domain_name, CREATOR_FK, domain_closed, domain_sort),
            )
            domain_id = cur.lastrowid
            inserted['domains'] += 1

        for area_name, area_closed, area_sort, tasks in areas:
            cur.execute(
                'SELECT id FROM areas WHERE creator_fk = %s AND domain_fk = %s '
                'AND area_name = %s',
                (CREATOR_FK, domain_id, area_name),
            )
            row = cur.fetchone()
            if row:
                area_id = row['id']
            else:
                cur.execute(
                    'INSERT INTO areas (area_name, domain_fk, creator_fk, closed, sort_order) '
                    'VALUES (%s, %s, %s, %s, %s)',
                    (area_name, domain_id, CREATOR_FK, area_closed, area_sort),
                )
                area_id = cur.lastrowid
                inserted['areas'] += 1

            for sort_order, (description, priority, done) in enumerate(tasks, start=1):
                cur.execute(
                    'SELECT id FROM tasks WHERE creator_fk = %s AND area_fk = %s '
                    'AND description = %s',
                    (CREATOR_FK, area_id, description),
                )
                if cur.fetchone():
                    continue
                cur.execute(
                    'INSERT INTO tasks (priority, done, description, area_fk, creator_fk, '
                    'sort_order, done_ts) VALUES (%s, %s, %s, %s, %s, %s, '
                    'CASE WHEN %s = 1 THEN CURRENT_TIMESTAMP ELSE NULL END)',
                    (priority, done, description, area_id, CREATOR_FK, sort_order, done),
                )
                inserted['tasks'] += 1

    description, priority, done = ORPHAN_TASK
    cur.execute(
        'SELECT id FROM tasks WHERE creator_fk = %s AND area_fk IS NULL '
        'AND description = %s',
        (CREATOR_FK, description),
    )
    if not cur.fetchone():
        cur.execute(
            'INSERT INTO tasks (priority, done, description, area_fk, creator_fk, sort_order) '
            'VALUES (%s, %s, %s, NULL, %s, 1)',
            (priority, done, description, CREATOR_FK),
        )
        inserted['tasks'] += 1
    return inserted


def main():
    parser = argparse.ArgumentParser(
        prog='seed_domains_dev.py',
        description='Seed the canonical domains/areas/tasks fixture. Never production.',
    )
    # No --override-file-target: TARGETS is a constant in this file, not a header
    # somebody may reasonably want to bypass, so there is nothing to override.
    db_guard.add_target_arguments(parser, override_file_target=False)
    parser.add_argument('--reset', action='store_true',
                        help="Delete this fixture's own rows first, then re-seed.")
    args = parser.parse_args()

    try:
        db_guard.require_database(args.database, production=args.production)
        db_guard.require_declared_target(args.database, TARGETS, 'seed_domains_dev.py',
                                         overridable=False)
        if args.reset and not args.destructive:
            raise db_guard.GuardError(
                'REFUSED: --reset DELETEs this fixture\'s domains, areas and tasks. '
                'Re-run with --destructive to confirm.'
            )
        conn = db_guard.connect(args.database)
    except db_guard.GuardError as exc:
        print(exc, file=sys.stderr)
        return 2

    db_guard.banner(args.database, 'seed_domains_dev.py fixture', TARGETS)

    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM profiles WHERE id = %s', (CREATOR_FK,))
            if not cur.fetchone():
                print(f'REFUSED: profile {CREATOR_FK} does not exist in '
                      f'{args.database!r}; seed it first (seed_darwin_dev.py).',
                      file=sys.stderr)
                return 2
            before = counts(cur)
            removed = delete_fixture(cur) if args.reset else None
            inserted = seed(cur)
            after = counts(cur)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f'status=error database={args.database}\nerror={exc}', file=sys.stderr)
        return 1
    finally:
        conn.close()

    if removed:
        print(f'removed domains={removed["domains"]} areas={removed["areas"]} '
              f'tasks={removed["tasks"]}')
    print(f'inserted domains={inserted["domains"]} areas={inserted["areas"]} '
          f'tasks={inserted["tasks"]}')
    print(f'before {before}')
    print(f'after  {after}')
    print(f'status=ok database={args.database} creator_fk={CREATOR_FK}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
