#!/usr/bin/env python3
"""Create or drop a THROWAWAY database for the schema-parity gate. (req #3196)

    . Lambda-Rest/exports.sh
    python3 DarwinSQL/scripts/scratch_db.py create darwin_scratch_parity
    python3 DarwinSQL/scripts/scratch_db.py drop   darwin_scratch_parity --destructive
    python3 DarwinSQL/scripts/scratch_db.py list

WHY THIS EXISTS. `memory/database.md` § Schema-of-Record Parity tells the
operator to load `schema.sql` and `recreate_darwin_dev.sql` into a scratch
database and diff `INFORMATION_SCHEMA.COLUMNS` for a zero-diff. That is the only
use `--override-file-target` exists for. But req #3196 removed
`CREATE DATABASE IF NOT EXISTS darwin;` from `schema.sql` (correctly — a file
must not name its own target) and `query.py` refuses `CREATE DATABASE` (also
correctly — it is a hardcoded target). This machine has no `mysql` CLI, and
`seed_darwin_dev.py` hardcodes `darwin_dev`. So the parity gate had no way to
create its scratch database at all, and a gate nobody can run is not a gate.

WHY IT IS ITS OWN TOOL RATHER THAN A FLAG ON `query.py`. `CREATE DATABASE` is
the one statement whose entire content is a database name, so a tool that runs
it cannot be guarded by "the caller names the target" — the statement IS the
target. What CAN be guarded is the NAME. Every name here must match
`darwin_scratch_[A-Za-z0-9_]+`, which `darwin` and `darwin_dev` cannot satisfy,
so this file is structurally unable to address anything real. That is a stronger
guarantee than a confirmation flag, and it needs no flag to state it.

`drop` additionally requires `--destructive`, because a scratch database that
somebody left a day's work in is still a day's work.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_guard  # noqa: E402

SCRATCH_NAME = re.compile(r'darwin_scratch_[A-Za-z0-9_]+')


def require_scratch_name(name):
    if not SCRATCH_NAME.fullmatch(name):
        raise db_guard.GuardError(
            f'REFUSED: {name!r} is not a scratch database name. This tool only '
            f'addresses names matching `darwin_scratch_<suffix>` — which `darwin` '
            f'and `darwin_dev` cannot match, by construction. Rename, or use the '
            f'right tool for a real database.'
        )
    # Belt and braces: the pattern already excludes both, but a future edit to
    # the pattern must not be able to quietly open this up.
    if db_guard.is_production(name) or name.lower() == 'darwin_dev':
        raise db_guard.GuardError(f'REFUSED: {name!r} is not a scratch database.')
    return name


def main():
    parser = argparse.ArgumentParser(
        prog='scratch_db.py',
        description='Create or drop a throwaway darwin_scratch_* database.',
    )
    parser.add_argument('action', choices=('create', 'drop', 'list'))
    parser.add_argument('name', nargs='?',
                        help='darwin_scratch_<suffix>. Omitted for `list`.')
    parser.add_argument('--destructive', action='store_true',
                        help='Required for `drop`.')
    args = parser.parse_args()

    try:
        if args.action != 'list':
            if not args.name:
                raise db_guard.GuardError(
                    f'REFUSED: `{args.action}` needs a database name.')
            require_scratch_name(args.name)
        if args.action == 'drop' and not args.destructive:
            raise db_guard.GuardError(
                f'REFUSED: dropping {args.name!r} destroys everything in it. '
                f'Re-run with --destructive.')
        # No database selected: `CREATE DATABASE` needs none, and selecting one
        # would be a target this tool has no business naming.
        conn = db_guard.connect(None, autocommit=True)
    except db_guard.GuardError as exc:
        print(exc, file=sys.stderr)
        return 2

    try:
        with conn.cursor() as cur:
            if args.action == 'list':
                cur.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA "
                            "WHERE SCHEMA_NAME LIKE 'darwin\\_scratch\\_%'")
                names = [r['SCHEMA_NAME'] for r in cur.fetchall()]
                for name in names:
                    print(name)
                print(f'status=ok scratch_databases={len(names)}')
                return 0

            print(f'--- {args.action} {args.name} on {os.environ.get("endpoint")} ---',
                  file=sys.stderr)
            if args.action == 'create':
                cur.execute(f'CREATE DATABASE IF NOT EXISTS `{args.name}`')
            else:
                cur.execute(f'DROP DATABASE IF EXISTS `{args.name}`')
        print(f'status=ok action={args.action} database={args.name}')
    except Exception as exc:
        print(f'status=error action={args.action} database={args.name}\nerror={exc}',
              file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
