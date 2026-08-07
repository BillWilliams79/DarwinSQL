#!/usr/bin/env python3
"""Run an ad-hoc engineering query against exactly the database you name. (req #3196)

    . Lambda-Rest/exports.sh
    python3 DarwinSQL/scripts/query.py darwin_dev -e "SELECT COUNT(*) FROM tasks"
    python3 DarwinSQL/scripts/query.py darwin     -e "SELECT COUNT(*) FROM tasks" --production
    python3 DarwinSQL/scripts/query.py darwin_dev -e "DELETE FROM probes" --write

WHY THIS EXISTS. Removing `USE darwin;` from the corpus fixes files. It does not
fix the thing that actually caused the 2026-08-01 incident: somebody opened a
connection by hand and guessed. `memory/database.md` used to print a bare
`pymysql.connect(..., database='darwin_dev')` recipe for exactly this, and a
recipe is a template — the next person edits the database name in it, or forgets
to. This is the same capability with the target announced, production named
twice, and writes refused unless asked for.

It is activity #3 of the Single DB Gateway Rule (CLAUDE.md) — the explicitly
user-authorized ad-hoc engineering query — and nothing else. APPLICATION reads
and writes go through Lambda-Rest; a schema change goes through a migration file
and `load_sql.py`.

THE SAME RULES AS A FILE. `-e` text goes through `db_guard.check_sql_text`, the
identical path `load_sql.py` uses, so a `-- darwin:targets` declaration pasted
in with the SQL is honoured here too. It has to be: `-e "$(cat
recreate_darwin_dev.sql)" darwin --production --write` otherwise walked straight
past that file's ABSOLUTE production ban and would have dropped 52 production
tables (req #3196 review, C1).

READ-ONLY BY DEFAULT. A probe is a question, so anything that is not a question
needs `--write`. The check is a prefix allowlist over the parsed statements,
never a denylist of dangerous verbs: a denylist is a guess about what MySQL's
grammar contains, and the point of this file is to stop guessing. `WITH` is the
one prefix that does not settle the question by itself — MySQL 8 allows a CTE at
the head of `UPDATE` and `DELETE` as well as `SELECT` — so a `WITH` statement is
resolved to its real verb by scanning at paren depth 0, and anything unresolvable
is treated as a write.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_guard  # noqa: E402

READ_ONLY_PREFIXES = ('SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN')
# The verbs a WITH clause may introduce. SELECT is the only read-only one.
CTE_VERBS = ('SELECT', 'UPDATE', 'DELETE', 'INSERT', 'REPLACE')
# `SELECT … INTO OUTFILE`/`DUMPFILE` writes the filesystem. Whether the server's
# `secure_file_priv` makes that inert is a server setting this tool cannot see,
# so it is treated as a write regardless.
_SELECT_INTO_FILE = re.compile(r'\bINTO\s+(OUTFILE|DUMPFILE)\b', re.I)

_WORD = re.compile(r'[A-Za-z_][A-Za-z_0-9$]*')


def _cte_main_verb(statement):
    """The real verb of a `WITH …` statement, or None if it cannot be resolved.

    The CTE bodies live inside parentheses, so the main verb is the first
    recognised verb at paren depth 0 after the `WITH`. Quotes are respected;
    comments are already gone by the time a statement exists.
    """
    depth = 0
    quote = None
    i, n = 0, len(statement)
    while i < n:
        char = statement[i]
        if quote is not None:
            if char == '\\' and quote != '`' and i + 1 < n:
                i += 2
                continue
            if char == quote:
                quote = None
            i += 1
            continue
        if char in db_guard.QUOTE_CHARS:
            quote = char
            i += 1
            continue
        if char == '(':
            depth += 1
            i += 1
            continue
        if char == ')':
            depth -= 1
            i += 1
            continue
        if depth == 0:
            word = _WORD.match(statement, i)
            if word:
                token = word.group(0).upper()
                if token in CTE_VERBS:
                    return token
                i = word.end()
                continue
        i += 1
    return None


def is_read_only(statement):
    tokens = statement.split(None, 1)
    if not tokens:
        return False
    first = tokens[0].upper()
    if first == 'WITH':
        return _cte_main_verb(statement) == 'SELECT'
    if first not in READ_ONLY_PREFIXES:
        return False
    if first == 'SELECT' and _SELECT_INTO_FILE.search(statement):
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        prog='query.py',
        description='Ad-hoc engineering query against exactly the database you name.',
    )
    # No --destructive / --override-file-target: this tool would refuse both, and
    # a flag whose only documented behaviour is to fail is worse than a missing
    # one. A `-- darwin:destructive` body is refused outright here — the place to
    # run a destructive file is load_sql.py, which can confirm it.
    db_guard.add_target_arguments(parser, destructive=False,
                                  override_file_target=False)
    parser.add_argument('-e', '--execute', required=True, metavar='SQL',
                        help='The SQL to run. Multiple statements may be separated by `;`.')
    parser.add_argument('--write', action='store_true',
                        help='Permit statements that are not SELECT/SHOW/DESCRIBE/EXPLAIN.')
    args = parser.parse_args()

    try:
        if db_guard.is_destructive(args.execute):
            # Refused here rather than by check_sql_text, whose message would
            # name a --destructive flag this tool deliberately does not have.
            raise db_guard.GuardError(
                'REFUSED: the SQL declares `-- darwin:destructive`. Run a '
                'destructive file through load_sql.py, which can confirm it:\n'
                '    python3 DarwinSQL/scripts/load_sql.py <file.sql> '
                '<database> --destructive'
            )
        statements, targets = db_guard.check_sql_text(
            args.execute, args.database, '-e',
            production=args.production,
            destructive=False,
            overridable=False,
        )
    except db_guard.GuardError as exc:
        print(exc, file=sys.stderr)
        return 2

    if not statements:
        print('REFUSED: -e contained no statement.', file=sys.stderr)
        return 2

    if not args.write:
        writing = [s for s in statements if not is_read_only(s)]
        if writing:
            preview = '\n'.join(f'    {" ".join(s.split())[:88]}' for s in writing[:5])
            print(f'REFUSED: {len(writing)} statement(s) are not read-only:\n{preview}\n'
                  f'  Re-run with --write if you mean to change '
                  f'{args.database!r}.', file=sys.stderr)
            return 2

    db_guard.banner(args.database, f'-e {" ".join(args.execute.split())[:60]}', targets)

    try:
        conn = db_guard.connect(args.database)
    except db_guard.GuardError as exc:
        print(exc, file=sys.stderr)
        return 2

    try:
        with conn.cursor() as cur:
            for statement in statements:
                affected = cur.execute(statement)
                rows = cur.fetchall()
                if rows:
                    for row in rows:
                        print(json.dumps(row, default=str))
                else:
                    print(f'rows_affected={affected}')
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
