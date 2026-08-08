#!/usr/bin/env python3
"""Which database does this statement hit? Answered once, out loud. (req #3196)

THE INCIDENT THIS EXISTS FOR (2026-08-01, req #3186 session 2518)
-----------------------------------------------------------------
A code-review probe described as targeting a scratch database executed against
PRODUCTION and wrote three rows. The operator believed the connection's default
database governed. It did not: `DarwinSQL/schema.sql` carried `USE darwin;`,
which is a STATEMENT, not a declaration — it re-points the session the moment it
executes, regardless of how the connection was opened. The file outranked the
operator, silently.

THE FIX IS TO REPLACE AN IMPERATIVE WITH A DECLARATION
------------------------------------------------------
`USE <db>;` tells the server "go here". Nothing in a SQL file should be able to
say that, because the caller already chose. So every `USE`/`CREATE DATABASE` is
gone from the corpus (pinned by `DarwinSQL/tests/test_sql_targets.py`), and a
file that needs a restricted target says so as a CONSTRAINT the caller is
checked against:

    -- darwin:targets = darwin_dev          may ONLY be applied to darwin_dev
    -- darwin:targets = darwin              production-only (migration 057)
    -- darwin:destructive                   drops data; requires --destructive

A `targets` list that omits `darwin` is an ABSOLUTE production ban. No flag
overrides it — that is the whole point of `recreate_darwin_dev.sql`, which drops
52 tables and must never be aimable at production even by an operator who types
every confirmation on offer.

THE THREE RULES
---------------
1. THE CALLER NAMES THE TARGET. There is no default database anywhere in this
   module. A missing name is an error, never an assumption.
2. PRODUCTION MUST BE NAMED TWICE — once by name (`darwin`) and once by intent
   (`--production`). Two independent tokens, so no single typo reaches it. The
   pair is checked BOTH ways: `--production` on a non-production database is
   also refused, which is what stops `--production` becoming a flag people
   append out of habit. (The `--destructive` pair is deliberately NOT symmetric:
   a spurious `--production` means the operator misunderstood where they are, a
   spurious `--destructive` means they were being careful. Only the first is a
   confusion worth stopping.)
3. THE TARGET IS ANNOUNCED BEFORE ANY STATEMENT RUNS. Silence is how the
   incident happened. `banner()` prints host, database, file and the production
   verdict on stderr every single time.

WHY THE STATEMENT SPLITTER LIVES HERE. The `USE`-refusal has to inspect real
parsed statements, not lines: `-- USE darwin;` in a comment is archaeology and a
requirement title containing the word is prose. `load_sql.py` needs the same
split to execute, and `test_sql_targets.py` needs it to audit the tree — one
implementation, so the three can never disagree about what a statement is.
"""
import os
import re
import sys

# The one production database. `darwin_dev` and any scratch database are not.
PRODUCTION_DATABASES = frozenset({'darwin'})

# A database name is a SQL identifier. Same charset restriction Lambda-Rest
# applies to body keys (CLAUDE.md § Single DB Gateway Rule): no normalizer can
# enumerate what MySQL's lexer discards, so refuse anything outside the set.
#
# `fullmatch`, NOT `re.match(r'…$')`: Python's `$` also matches BEFORE a trailing
# newline, so `'darwin\n'` passed the old anchor AND compared unequal to
# `'darwin'`, which classified production as non-production — the one judgment
# this module exists to get right. Measured during the req #3196 review.
_IDENTIFIER = re.compile(r'[A-Za-z0-9_$]+')

# A directive may be written with any run of leading dashes, or with `#`.
_COMMENT_LEAD = r'(?:-{2,}|\#)'
_TARGETS_DECL = re.compile(
    rf'^[ \t]*{_COMMENT_LEAD}[ \t]*darwin:targets[ \t]*=[ \t]*(.*)$', re.I | re.M)
_DESTRUCTIVE_DECL = re.compile(
    rf'^[ \t]*{_COMMENT_LEAD}[ \t]*darwin:destructive[ \t]*$', re.I | re.M)

# Every comment that OPENS with `darwin:` is a directive claim and must be a
# KNOWN one. Without this the parser failed OPEN: `-- darwin:target = darwin_dev`
# (singular) parsed as no declaration at all, silently removing both the
# production ban and the destructive gate from a file that plainly meant to
# carry them. Anchored at the start of the comment on purpose — prose that
# merely MENTIONS `darwin:targets` mid-sentence is not a claim.
#
# The name must begin with a LETTER, which is what keeps `-- darwin://pipeline/{id}`
# out: MCP resource URIs are ordinary prose in this codebase's comments (schema.sql
# and migration 076 both open a comment with one), and a guard that refuses a
# legitimate file is its own defect.
_DIRECTIVE_CLAIM = re.compile(
    rf'^[ \t]*{_COMMENT_LEAD}[ \t]*darwin:(?P<rest>[A-Za-z].*)$', re.I | re.M)
_KNOWN_DIRECTIVES = (
    re.compile(r'^targets[ \t]*=[ \t]*\S.*$', re.I),
    re.compile(r'^destructive[ \t]*$', re.I),
)

# Matched against a fully-parsed statement, never a raw line. `SCHEMA` is an
# exact MySQL synonym for `DATABASE`, so every verb is listed both ways.
_HARDCODED_TARGET = re.compile(
    r'^(USE|(CREATE|DROP|ALTER)\s+(DATABASE|SCHEMA))\b', re.I)


class GuardError(Exception):
    """A refusal. The message is the whole explanation — print it and stop."""


# ---------------------------------------------------------------------------
# Statement splitting
# ---------------------------------------------------------------------------

QUOTE_CHARS = {"'", '"', '`'}


def split_statements(text):
    """Split SQL into statements: ONE pass that knows quotes AND comments.

    WHY A HAND-ROLLED SPLITTER. Splitting on a bare `;` is wrong for Darwin's
    corpus in BOTH directions.

    A `;` inside a STRING LITERAL is not a separator.
    `seed_pipelines_darwin_dev.sql` carries requirement titles containing both
    semicolons ("...from local mirrors; retire git-worktree machinery...") and
    `#` characters ("...CORRECTED 2026-07-26: #3079 completed..."), and
    `pipeline_steps.notes` carries `--` (`--no-hardlinks`). Splitting or
    comment-stripping through those corrupts the text being stored.

    A `;` inside a COMMENT is not a separator either — and THAT half was
    missing until req #3196. The previous splitter dropped only FULL-LINE `--`
    comments and deliberately left inline ones alone ("an inline `--` may be
    inside a literal"), so an ordinary DDL comment cut its own statement in
    half:

        title VARCHAR(256) NOT NULL,   -- friendly name; auto-registration seeds it

    MySQL reads that comment to end-of-line and sees one CREATE TABLE. The
    splitter saw two statements, the first of them truncated at `NOT NULL,` —
    a syntax error partway through a DDL file, and DDL self-commits, so the
    file half-applies. It made `schema.sql` and migrations 064, 067 and 069
    unloadable through the sanctioned loader. Measured 2026-08-07: `schema.sql`
    created 7 of 53 tables and then failed.

    The fix is to track both in one scan, which is also what makes the
    "an inline `--` may be inside a literal" objection go away — inside a
    literal, comment syntax is never examined, and inside a comment, quote
    syntax is never examined.

    Handled: `'…'` and `"…"` string literals (default `sql_mode` has no
    ANSI_QUOTES, so `"` is a literal here — migration 004 uses them), backtick
    identifiers, the doubled-quote escape (`''` reads as close-then-open, which
    lands back in the string exactly where MySQL's parser ends up), backslash
    escapes, `-- ` to end of line (MySQL requires the trailing whitespace, so
    `a--b` is not a comment), `#` to end of line, and `/* … */` blocks. The
    corpus contains no `/*! … */` conditional-execution comments; if one is ever
    added it would be treated as a comment and silently NOT executed, so check
    for that before introducing one.
    """
    statements, buf = [], []
    i, n = 0, len(text)
    quote = None
    while i < n:
        char = text[i]

        if quote is not None:
            if char == '\\' and quote != '`' and i + 1 < n:
                buf.append(char)
                buf.append(text[i + 1])
                i += 2
                continue
            if char == quote:
                quote = None
            buf.append(char)
            i += 1
            continue

        if char in QUOTE_CHARS:
            quote = char
            buf.append(char)
            i += 1
            continue

        if char == '#' or (text.startswith('--', i)
                           and (i + 2 >= n or text[i + 2] in ' \t\r\n')):
            newline = text.find('\n', i)
            i = n if newline == -1 else newline  # keep the newline as whitespace
            continue

        if text.startswith('/*', i):
            close = text.find('*/', i + 2)
            if close == -1:
                raise GuardError(
                    f'REFUSED: unterminated /* block comment at offset {i}. '
                    f'Everything after it would be DISCARDED — the loader would '
                    f'apply the prefix and report status=ok, and the audit would '
                    f'call the file clean while a live USE sat inside the '
                    f'unclosed comment. Close it.'
                )
            i = close + 2
            continue

        if char == ';':
            statements.append(''.join(buf))
            buf = []
            i += 1
            continue

        buf.append(char)
        i += 1

    if quote is not None:
        raise GuardError(
            f'REFUSED: unterminated {quote!r} literal — the rest of the file was '
            f'swallowed into one statement, so any `;` and any USE inside it are '
            f'invisible to both the loader and the audit. Close it.'
        )

    if ''.join(buf).strip():
        statements.append(''.join(buf))
    return statements


def parse_statements(sql_text):
    """The executable statements of a .sql file, in order. Comments removed."""
    return [s.strip() for s in split_statements(sql_text) if s.strip()]


def hardcoded_target_statements(sql_text):
    """Every statement that names a database instead of letting the caller.

    This is the predicate `test_sql_targets.py` audits the tree with and the one
    `require_no_hardcoded_target()` refuses on — deliberately the same function,
    so a file that passes the test can never be refused at execution time.
    """
    return [s for s in parse_statements(sql_text)
            if _HARDCODED_TARGET.match(s)]


# ---------------------------------------------------------------------------
# File declarations
# ---------------------------------------------------------------------------

def require_known_directives(sql_text):
    """A comment that OPENS with `darwin:` must be a directive we recognise.

    Without this the parser failed OPEN. `-- darwin:target = darwin_dev`
    (singular), `-- darwin:targets: darwin_dev` (colon) and
    `-- darwin:destructiv` each parsed as NO declaration at all — so a
    one-character typo in `recreate_darwin_dev.sql` would silently remove both
    the production ban and the destructive gate, and the file would load
    anywhere. A guard whose typo mode is "no protection" is worse than no
    guard, because it still reads as protected.
    """
    for match in _DIRECTIVE_CLAIM.finditer(sql_text):
        rest = match.group('rest').rstrip()
        if not any(known.match(rest) for known in _KNOWN_DIRECTIVES):
            raise GuardError(
                f'REFUSED: unrecognised directive `darwin:{rest}`. A comment that '
                f'opens with `darwin:` claims to be a directive, and an unknown '
                f'one would silently mean NO restriction. The two that exist are:\n'
                f'    -- darwin:targets = <db>[, <db>]\n'
                f'    -- darwin:destructive'
            )


def declared_targets(sql_text):
    """The `-- darwin:targets = a, b` allowlist, or None if the file declares none.

    None means "no restriction" — the ordinary case for a migration that applies
    to both databases. It does NOT mean "production is fine": rule 2 governs
    that independently, and always.
    """
    require_known_directives(sql_text)
    found = _TARGETS_DECL.findall(sql_text)
    if not found:
        return None
    if len(found) > 1:
        raise GuardError(
            f'REFUSED: {len(found)} `-- darwin:targets` declarations in one file. '
            f'A file has one target list or none; two is ambiguous and the guard '
            f'will not pick.'
        )
    names = [n.strip().strip('`') for n in found[0].split(',')]
    names = [n for n in names if n]
    if not names:
        raise GuardError(
            'REFUSED: `-- darwin:targets` declared with an empty list. Name the '
            'databases this file may be applied to, or delete the line.'
        )
    for name in names:
        if not _IDENTIFIER.fullmatch(name):
            raise GuardError(
                f'REFUSED: `-- darwin:targets` names {name!r}, which is not a '
                f'database identifier ([A-Za-z0-9_$]+).'
            )
    return names


def is_destructive(sql_text):
    return bool(_DESTRUCTIVE_DECL.search(sql_text))


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------

def is_production(database):
    """Case-INSENSITIVE, deliberately.

    Whether MySQL resolves `DARWIN` to `darwin` depends on the server's
    `lower_case_table_names`, which nothing in this repo asserts and which this
    module cannot see before it has already decided. Folding the case here is
    wrong in only one direction — it would demand `--production` for a database
    genuinely named `DARWIN` that is not production, which does not exist.
    """
    return database.lower() in {name.lower() for name in PRODUCTION_DATABASES}


def require_database(database, production=False):
    """Rule 1 + rule 2. Returns the validated database name."""
    if not database:
        raise GuardError(
            'REFUSED: no target database. This tool has no default — name the '
            'database explicitly (`darwin_dev`, or `darwin` with --production).'
        )
    if not _IDENTIFIER.fullmatch(database):
        raise GuardError(
            f'REFUSED: {database!r} is not a database identifier '
            f'([A-Za-z0-9_$]+).'
        )
    if is_production(database) and not production:
        raise GuardError(
            f'REFUSED: {database!r} is PRODUCTION. Production must be named '
            f'twice — by name and by intent. Re-run with --production if that '
            f'is genuinely what you mean.'
        )
    if not is_production(database) and production:
        raise GuardError(
            f'REFUSED: --production was passed but the target is {database!r}, '
            f'which is not production. The flag and the name disagree; fix '
            f'whichever one is wrong rather than letting --production become a '
            f'flag you always type.'
        )
    return database


def require_no_hardcoded_target(sql_text, path):
    """Rule: a file may not choose its own database.

    Historically `load_sql.py` STRIPPED these statements. That kept the loader
    safe and left everyone else exposed — the `mysql` CLI, a hand-written probe,
    another machine — while telling the operator nothing about the disagreement.
    A refusal is the honest form: the file and the caller disagree about where
    the statements go, and that is not a conflict a tool should resolve quietly.
    """
    offending = hardcoded_target_statements(sql_text)
    if offending:
        preview = '\n'.join(f'    {" ".join(s.split())[:88]}' for s in offending[:5])
        raise GuardError(
            f'REFUSED: {path} hardcodes its own database target '
            f'({len(offending)} statement(s)):\n{preview}\n'
            f'  A `USE`/`CREATE DATABASE` statement re-points the session and '
            f'overrides the target you named. Delete it; if the file may only be '
            f'applied to certain databases, declare that instead:\n'
            f'    -- darwin:targets = darwin_dev'
        )


def require_declared_target(database, targets, path, override=False,
                            overridable=True):
    """Rule: honour the file's own allowlist, and never let it reach production.

    `--override-file-target` exists for ONE case — loading a dev-shaped file into
    a scratch database for the schema-parity gate — so it is refused in both
    directions that are not that case. A file that omits production may never
    reach production, and a file that NAMES production may never be aimed
    anywhere else: migration 057 drops the build-visualizer tables, which
    `darwin_dev` deliberately keeps, so "057 somewhere other than production" is
    never a parity load and always a mistake.

    `overridable=False` is for callers that HAVE no such flag — a seed script's
    target list is a constant in its own source, not a file header somebody may
    reasonably want to bypass. Without it the refusal recommended a flag the
    calling script then refused, which is a guard arguing with itself.
    """
    if targets is None or database in targets:
        return
    if is_production(database):
        raise GuardError(
            f'REFUSED: {path} declares targets = {", ".join(targets)}, '
            f'which does not include {database!r}. A target list that omits '
            f'production is an ABSOLUTE ban — no flag overrides it.'
        )
    if any(is_production(t) for t in targets):
        raise GuardError(
            f'REFUSED: {path} declares targets = {", ".join(targets)}, '
            f'a PRODUCTION target, and you named {database!r}. A production-only '
            f'file applied elsewhere is a mistake, not a parity load — no flag '
            f'overrides it.'
        )
    if not overridable:
        raise GuardError(
            f'REFUSED: {path} may only be applied to '
            f'{", ".join(targets)}, and you named {database!r}. Its target list '
            f'is a constant in its own source, so there is no flag for this.'
        )
    if not override:
        raise GuardError(
            f'REFUSED: {path} declares targets = {", ".join(targets)}, '
            f'which does not include {database!r}. Pass --override-file-target if '
            f'you are deliberately applying it elsewhere (a scratch database for '
            f'the schema-parity gate is the intended use).'
        )
    print(f'WARNING: applying {path} to {database!r}, outside its declared '
          f'targets ({", ".join(targets)}) — --override-file-target given.',
          file=sys.stderr)


def require_destructive_ack(sql_text, path, destructive=False):
    """Rule: a file that declares itself destructive needs saying so out loud."""
    if is_destructive(sql_text) and not destructive:
        raise GuardError(
            f'REFUSED: {path} declares `-- darwin:destructive` — it DROPS data. '
            f'Re-run with --destructive to confirm you mean to lose whatever is '
            f'in the target database.'
        )


def check_sql_text(sql_text, database, source, production=False,
                   destructive=False, override_file_target=False,
                   overridable=True):
    """Every rule, in order, over a body of SQL. Returns (statements, targets).

    THE RULES BELONG TO THE TEXT, NOT TO THE TOOL (req #3196 review, C1). This
    used to live inside `check_file`, so only the file loader consulted a
    `darwin:targets` declaration — and `query.py -e "$(cat
    recreate_darwin_dev.sql)" darwin --production --write` walked straight past
    the ABSOLUTE production ban that three documents promise is unoverridable,
    with the splitter erasing the declaration as a comment on the way. A rule
    that holds in one entry point and not another is not a rule.

    Raises GuardError on the first refusal. Nothing has connected yet when it
    does, so a refusal is always a no-op against every database.
    """
    require_database(database, production=production)
    require_no_hardcoded_target(sql_text, source)
    targets = declared_targets(sql_text)
    require_declared_target(database, targets, source,
                            override=override_file_target,
                            overridable=overridable)
    require_destructive_ack(sql_text, source, destructive=destructive)
    return parse_statements(sql_text), targets


def check_file(path, database, production=False, destructive=False,
               override_file_target=False):
    """`check_sql_text` over one .sql file. The target is validated BEFORE the
    file is opened, so a bad target never even reads from disk."""
    require_database(database, production=production)
    with open(path, 'r') as handle:
        sql_text = handle.read()
    return check_sql_text(sql_text, database, path, production=production,
                          destructive=destructive,
                          override_file_target=override_file_target)


# ---------------------------------------------------------------------------
# Connecting
# ---------------------------------------------------------------------------

REQUIRED_ENV = ('endpoint', 'username', 'db_password')


def banner(database, source, targets=None):
    """Rule 3. Announce the target on stderr before anything executes."""
    endpoint = os.environ.get('endpoint', '<unset>')
    verdict = 'YES — PRODUCTION' if database in PRODUCTION_DATABASES else 'no'
    lines = [
        '=' * 72,
        f'  TARGET DATABASE : {database}',
        f'  PRODUCTION      : {verdict}',
        f'  HOST            : {endpoint}',
        f'  SOURCE          : {source}',
    ]
    if targets:
        lines.append(f'  FILE DECLARES   : darwin:targets = {", ".join(targets)}')
    lines.append('=' * 72)
    print('\n'.join(lines), file=sys.stderr)


def connect(database, autocommit=False):
    """Open a connection to exactly `database`. No default, no fallback.

    `database=None` selects NO database and is reserved for `scratch_db.py`,
    whose whole job is `CREATE DATABASE` — a statement that needs no current
    database and whose target it would be wrong to imply by selecting one.
    Every other caller passes a name that `require_database` has validated.
    """
    import pymysql  # imported here so the policy above needs no driver installed

    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        raise GuardError(
            f'REFUSED: {", ".join(missing)} not set — source Lambda-Rest/exports.sh '
            f'first (see memory/database.md § exports.sh when Lambda-Rest is NOT '
            f'in the session).'
        )
    return pymysql.connect(
        host=os.environ['endpoint'],
        user=os.environ['username'],
        password=os.environ['db_password'],
        database=database,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=autocommit,
    )


def add_target_arguments(parser, database_help='Target database — named explicitly, no default.',
                         destructive=True, override_file_target=True):
    """The flag set every guarded tool shares, so they cannot drift apart.

    A tool that would REFUSE a flag does not advertise it: `--destructive` and
    `--override-file-target` used to appear in `query.py --help` and abort if
    used. A flag whose only documented behaviour is to fail is worse than a
    missing one — argparse's own "unrecognized arguments" is the honest error.
    """
    parser.add_argument('database', help=database_help)
    parser.add_argument('--production', action='store_true',
                        help="Confirm you mean production `darwin`. Required to reach it.")
    if destructive:
        parser.add_argument('--destructive', action='store_true',
                            help='Confirm a file that declares `-- darwin:destructive`.')
    if override_file_target:
        parser.add_argument('--override-file-target', action='store_true',
                            help="Apply a file outside its declared `-- darwin:targets`. "
                                 "Never reaches production.")
    return parser
