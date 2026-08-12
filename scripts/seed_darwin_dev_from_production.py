#!/usr/bin/env python3
"""Refresh darwin_dev with a full server-side copy of production darwin data. (req #3484)

    . Lambda-Rest/exports.sh
    python3 DarwinSQL/scripts/seed_darwin_dev_from_production.py --confirm-production-source
    python3 DarwinSQL/scripts/seed_darwin_dev_from_production.py --confirm-production-source --dry-run
    python3 DarwinSQL/scripts/seed_darwin_dev_from_production.py --confirm-production-source --only tasks,areas

WHY THIS EXISTS (req #3460, scoped down to a v1 by the user 2026-08-11).
`darwin_dev` is a stale, hand-seeded fixture that drifts from production data —
measured cost in req #3419: a filter that looked broken on the dev server was
actually correct, because `darwin_dev`'s residue population was zero while
production's was not. req #3460 describes a fuller per-session-database design
(still `discuss`) with open questions about API Gateway routing and lifecycle.
This script is the simple, always-available piece that does not wait on any of
that: point it at production, it makes darwin_dev match, in place.

BOTH DATABASES ARE ON THE SAME RDS INSTANCE, so the whole operation is one
connection and one round trip per table — no dump, no network transfer of the
data itself. Same-instance `INSERT ... SELECT` across schemas runs entirely
server-side.

TARGET IS ALWAYS darwin_dev. The source is always production darwin — that is
the whole point of this script, so it is not a parameter. Reading production
still needs an explicit, separate confirmation (`--confirm-production-source`)
because db_guard's target-naming pair (name + --production) is a WRITE-target
guard and this script's write target is darwin_dev, always non-production; the
unusual thing here is the READ side reaching production, which nothing in
db_guard checks by itself.

NEVER WRITES TO darwin. Every statement that names `darwin` in this script is a
SELECT. `darwin_dev` is the only side ever TRUNCATEd or INSERTed into.

PER TABLE: SET FOREIGN_KEY_CHECKS=0 (session-scoped, so table order does not
matter and TRUNCATE is not blocked by an FK reference), TRUNCATE the darwin_dev
side (also resets its AUTO_INCREMENT counter), INSERT INTO darwin_dev.<t>
(<cols>) SELECT <cols> FROM darwin.<t> using an EXPLICIT column list intersected
between the two live tables (never `SELECT *` — column order drift between two
independently-migrated tables would silently shift data into the wrong column).
A table whose column sets do not match exactly is SKIPPED and reported, never
partially copied.

Only tables that exist on BOTH sides are touched. A table present on only one
side is reported and left alone — creating or dropping a table is the schema
migration workflow's job, not a data-seed script's.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_guard  # noqa: E402

TARGET = 'darwin_dev'
SOURCE = 'darwin'  # production, always


def table_columns(cur, schema, table):
    """Column names in ordinal order, excluding GENERATED columns.

    A generated column (e.g. `agent_documents.owned_document_fk`) computes its
    own value and MySQL refuses any INSERT that names it at all — not just a
    mismatched one. Measured: including it broke the very first non-trivial
    table copied.
    """
    cur.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND EXTRA NOT LIKE '%%GENERATED%%' "
        "ORDER BY ORDINAL_POSITION",
        (schema, table),
    )
    return [r['COLUMN_NAME'] for r in cur.fetchall()]


def table_names(cur, schema):
    cur.execute(
        'SELECT TABLE_NAME FROM information_schema.TABLES '
        'WHERE TABLE_SCHEMA=%s AND TABLE_TYPE=%s',
        (schema, 'BASE TABLE'),
    )
    return {r['TABLE_NAME'] for r in cur.fetchall()}


def row_count(cur, schema, table):
    cur.execute(f'SELECT COUNT(*) AS n FROM `{schema}`.`{table}`')
    return cur.fetchone()['n']


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--confirm-production-source', action='store_true',
                        help='Confirm you mean to READ production darwin. Required.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Report what would be copied without touching darwin_dev.')
    parser.add_argument('--only', default=None,
                        help='Comma-separated table subset (default: every common table).')
    args = parser.parse_args()

    db_guard.require_database(TARGET, production=False)

    if not args.confirm_production_source:
        print('REFUSED: this script reads production `darwin` as its source. '
              'Pass --confirm-production-source to confirm that is what you mean.',
              file=sys.stderr)
        sys.exit(1)

    db_guard.banner(TARGET, os.path.basename(__file__))
    print(f'  SOURCE (read-only): {SOURCE} — PRODUCTION', file=sys.stderr)

    conn = db_guard.connect(TARGET, autocommit=True)
    try:
        with conn.cursor() as cur:
            target_tables = table_names(cur, TARGET)
            source_tables = table_names(cur, SOURCE)
            common = sorted(target_tables & source_tables)
            only_target = sorted(target_tables - source_tables)
            only_source = sorted(source_tables - target_tables)

            if args.only:
                requested = {t.strip() for t in args.only.split(',') if t.strip()}
                missing = requested - set(common)
                if missing:
                    print(f'REFUSED: --only names table(s) not common to both '
                          f'databases: {", ".join(sorted(missing))}', file=sys.stderr)
                    sys.exit(1)
                common = sorted(requested)

            if only_target:
                print(f'  darwin_dev-only (left alone): {", ".join(only_target)}', file=sys.stderr)
            if only_source:
                print(f'  darwin-only (left alone): {", ".join(only_source)}', file=sys.stderr)

            plan = []
            skipped = []
            for t in common:
                target_cols = table_columns(cur, TARGET, t)
                source_cols = table_columns(cur, SOURCE, t)
                if set(target_cols) != set(source_cols):
                    skipped.append((t, target_cols, source_cols))
                    continue
                plan.append((t, target_cols))

            if skipped:
                print(f'  SKIPPED (column mismatch, not copied): '
                      f'{", ".join(t for t, _, _ in skipped)}', file=sys.stderr)
                for t, tc, sc in skipped:
                    print(f'    {t}: darwin_dev={tc} vs darwin={sc}', file=sys.stderr)

            if args.dry_run:
                print('  DRY RUN — no writes', file=sys.stderr)
                for t, _ in plan:
                    before = row_count(cur, TARGET, t)
                    after = row_count(cur, SOURCE, t)
                    print(f'    {t}: darwin_dev={before} rows -> would become darwin={after} rows')
                print(f'status=dry-run tables_planned={len(plan)} tables_skipped={len(skipped)}')
                return

            cur.execute('SET FOREIGN_KEY_CHECKS=0')
            results = []
            t0 = time.time()
            try:
                for t, cols in plan:
                    col_list = ', '.join(f'`{c}`' for c in cols)
                    before = row_count(cur, TARGET, t)
                    cur.execute(f'TRUNCATE TABLE `{TARGET}`.`{t}`')
                    cur.execute(
                        f'INSERT INTO `{TARGET}`.`{t}` ({col_list}) '
                        f'SELECT {col_list} FROM `{SOURCE}`.`{t}`'
                    )
                    after = row_count(cur, TARGET, t)
                    results.append((t, before, after))
                    print(f'  {t}: {before} -> {after} rows', file=sys.stderr)
            finally:
                cur.execute('SET FOREIGN_KEY_CHECKS=1')
            elapsed = time.time() - t0

            total_before = sum(r[1] for r in results)
            total_after = sum(r[2] for r in results)
            print(f'status=ok tables_copied={len(results)} tables_skipped={len(skipped)} '
                  f'rows_before={total_before} rows_after={total_after} '
                  f'elapsed_s={elapsed:.1f}')
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        main()
    except db_guard.GuardError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
