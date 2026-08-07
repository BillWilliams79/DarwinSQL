#!/usr/bin/env python3
"""Apply a .sql file to a Darwin database. The loader this machine lacks.

    . Lambda-Rest/exports.sh
    python3 DarwinSQL/scripts/load_sql.py <file.sql> <database> [flags]

    python3 DarwinSQL/scripts/load_sql.py migrations/<MIG>.sql darwin_dev
    python3 DarwinSQL/scripts/load_sql.py migrations/<MIG>.sql darwin --production

There is no `mysql` CLI on the Mac mini, so the migration/fixture instructions in
memory/database.md have no executable on this host. This is that command.

THE TARGET IS THE CALLER'S, AND ONLY THE CALLER'S (req #3196). Every rule about
which database gets hit lives in `db_guard.py`, which also owns the statement
splitter this file used to carry — one implementation, so the loader, the guard
and `tests/test_sql_targets.py` cannot disagree about what a statement is.

What changed in #3196: this loader used to SILENTLY STRIP a `USE`/`CREATE
DATABASE` statement. That kept the loader itself safe and left every other
caller — the `mysql` CLI, a hand-written probe, another machine — exposed, while
saying nothing about the fact that the file disagreed with the operator. It now
REFUSES. The corpus carries no such statement (pinned by a test), so the refusal
only ever fires on a file that has just acquired one.

Everything runs in ONE transaction and rolls back on the first failure, so a
half-applied fixture is not a state this can produce. (DDL still self-commits in
MySQL — that is a server property, not something the loader can undo.)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_guard  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        prog='load_sql.py',
        description='Apply a .sql file to exactly the database you name.',
    )
    parser.add_argument('path', metavar='file.sql', help='The .sql file to apply.')
    db_guard.add_target_arguments(parser)
    args = parser.parse_args()

    try:
        statements, targets = db_guard.check_file(
            args.path, args.database,
            production=args.production,
            destructive=args.destructive,
            override_file_target=args.override_file_target,
        )
    except db_guard.GuardError as exc:
        print(exc, file=sys.stderr)
        return 2
    except OSError as exc:
        print(f'ERROR: cannot read {args.path}: {exc}', file=sys.stderr)
        return 2

    db_guard.banner(args.database, args.path, targets)

    try:
        conn = db_guard.connect(args.database)
    except db_guard.GuardError as exc:
        print(exc, file=sys.stderr)
        return 2

    try:
        with conn.cursor() as cur:
            for statement in statements:
                print('->', ' '.join(statement.split())[:88])
                cur.execute(statement)
        conn.commit()
        print(f'status=ok statements={len(statements)} database={args.database}')
    except Exception as exc:
        conn.rollback()
        print(f'status=error database={args.database}\nerror={exc}', file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
