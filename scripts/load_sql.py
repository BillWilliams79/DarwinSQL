#!/usr/bin/env python3
"""Apply a .sql file to a Darwin database. The loader this machine lacks.

    . Lambda-Rest/exports.sh
    python3 DarwinSQL/scripts/load_sql.py <file.sql> <database>

There is no `mysql` CLI on the Mac mini, so the migration/fixture instructions in
memory/database.md ("mysql -u <user> -p darwin_dev < migrations/NNN.sql") have no
executable on this host. This is that command.

WHY A HAND-ROLLED SPLITTER. Splitting on a bare `;` is wrong for Darwin's fixture
files: `seed_pipelines_darwin_dev.sql` carries requirement titles containing both
semicolons ("...from local mirrors; retire git-worktree machinery...") and `#`
characters ("...CORRECTED 2026-07-26: #3079 completed..."), inside string
literals. A naive split produces syntax errors; a `#`-comment stripper silently
truncates the text it stores. So:

  * statements split on `;` only OUTSIDE a single-quoted string;
  * `''` (MySQL's doubled-quote escape) and backslash escapes both honoured;
  * only FULL-LINE `--` comments are removed — an inline `--` is never assumed to
    start a comment, because it may be inside a literal;
  * `#` is left alone entirely.

Everything runs in ONE transaction and rolls back on the first failure, so a
half-applied fixture is not a state this can produce. (DDL still self-commits in
MySQL — that is a server property, not something the loader can undo.)
"""
import os
import sys

import pymysql


def split_statements(text):
    """Split SQL on `;` that is not inside a single-quoted string literal."""
    statements, buf, in_string, escaped = [], [], False, False
    for char in text:
        if escaped:
            buf.append(char)
            escaped = False
            continue
        if char == '\\' and in_string:
            buf.append(char)
            escaped = True
            continue
        if char == "'":
            # A doubled '' inside a literal reads as close-then-open, which lands
            # back in the string — the same place MySQL's own parser ends up.
            in_string = not in_string
            buf.append(char)
            continue
        if char == ';' and not in_string:
            statements.append(''.join(buf))
            buf = []
            continue
        buf.append(char)
    if ''.join(buf).strip():
        statements.append(''.join(buf))
    return statements


def strip_full_line_comments(text):
    return '\n'.join(line for line in text.split('\n')
                     if not line.lstrip().startswith('--'))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    path, database = sys.argv[1], sys.argv[2]

    missing = [v for v in ('endpoint', 'username', 'db_password') if not os.environ.get(v)]
    if missing:
        sys.exit(f'ERROR: {", ".join(missing)} not set — source Lambda-Rest/exports.sh first')

    body = strip_full_line_comments(open(path).read())
    statements = [s.strip() for s in split_statements(body) if s.strip()]
    # `USE`/`CREATE DATABASE` are declarations for the mysql CLI; the connection
    # below already names the target, and honouring a stray USE would let a file
    # redirect itself at a database the caller did not ask for.
    statements = [s for s in statements
                  if not s.upper().startswith(('USE ', 'CREATE DATABASE'))]

    conn = pymysql.connect(host=os.environ['endpoint'], user=os.environ['username'],
                           password=os.environ['db_password'], database=database,
                           charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
                           autocommit=False)
    try:
        with conn.cursor() as cur:
            for statement in statements:
                print('->', ' '.join(statement.split())[:88])
                cur.execute(statement)
        conn.commit()
        print(f'status=ok statements={len(statements)} database={database}')
    except Exception as exc:
        conn.rollback()
        print(f'status=error database={database}\nerror={exc}', file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
