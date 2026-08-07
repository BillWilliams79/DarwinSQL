"""No .sql file under DarwinSQL/ may choose its own database. (req #3196)

WHAT WENT WRONG (the reason this file exists)
---------------------------------------------
`USE <db>;` is a STATEMENT, not a declaration. It re-points the session the
moment it executes, so a file carrying `USE darwin;` overrides whatever database
the caller connected to — silently, with no warning and no error. On 2026-08-01
a code-review probe described as targeting a scratch database executed against
PRODUCTION and wrote three rows (`profiles` 'probe', `swarm_sessions` id=1,
`pipelines` id=77; all removed, production re-verified). The operator believed
the connection's default database governed. `DarwinSQL/schema.sql:8` decided
otherwise.

It was never one line. `schema.sql`, `history/darwin_instantiate.sql` (twice),
migrations 001-006, `scripts/recreate_darwin_dev.sql` and
`scripts/seed_pipelines_darwin_dev.sql` all carried one.

THE CONTRACT
------------
    Forbidden   USE <db>;   CREATE DATABASE <db>;   — an IMPERATIVE that
                                                      overrides the caller
    Allowed     -- darwin:targets = darwin_dev      — a CONSTRAINT the caller
                -- darwin:destructive                 is checked against

A `darwin:targets` list that omits `darwin` is an absolute production ban; see
`DarwinSQL/scripts/db_guard.py`, which enforces all of this at execution time.
This module pins the corpus so the next hardcoded target fails the build instead
of a production write.

Like `test_migration_naming.py`, this module is deliberately FILESYSTEM-ONLY —
it opens no database and needs no credentials, so it runs on any machine, in CI,
and inside a `deployed` swarm worker with no DB access:

    python3 -m pytest tests/test_sql_targets.py -q     # no env vars needed
"""
import glob
import os
import re
import sys

import pytest

DARWINSQL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(DARWINSQL_ROOT, 'scripts'))

import db_guard  # noqa: E402  (needs the path insert above)


# ---------------------------------------------------------------------------
# This module needs no database. Override conftest's session-scoped autouse
# seeding fixture (which pulls in db_connection and therefore credentials).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def seed_test_profile():
    """No-op override — test_sql_targets.py is filesystem-only."""
    yield {}


def _all_sql_files():
    return sorted(glob.glob(os.path.join(DARWINSQL_ROOT, '**', '*.sql'), recursive=True))


def _relative(path):
    return os.path.relpath(path, DARWINSQL_ROOT)


# ---------------------------------------------------------------------------
# The corpus
# ---------------------------------------------------------------------------

def test_there_are_sql_files_to_check():
    """A glob that silently matches nothing would make every test below vacuous."""
    files = _all_sql_files()
    assert len(files) > 50, f'only {len(files)} .sql files found under {DARWINSQL_ROOT}'


@pytest.mark.parametrize('path', _all_sql_files(), ids=_relative)
def test_no_sql_file_hardcodes_a_database_target(path):
    """*** The acceptance criterion of req #3196. ***

    Checked against PARSED STATEMENTS, not raw lines: `-- USE darwin;` in
    `history/darwin_instantiate.sql` is archaeology, and a requirement title
    containing the word inside a string literal is prose. Neither is a target.
    """
    with open(path, 'r') as handle:
        offending = db_guard.hardcoded_target_statements(handle.read())
    assert not offending, (
        f'{_relative(path)} hardcodes its own database target: '
        f'{[" ".join(s.split())[:70] for s in offending]}. '
        f'A USE/CREATE DATABASE statement overrides whatever database the caller '
        f'connected to. Delete it; declare `-- darwin:targets = <db>` if the file '
        f'may only be applied to certain databases.'
    )


# Every leading token the corpus actually uses, plus the near neighbours a new
# migration would plausibly reach for. PREPARE / EXECUTE / DEALLOCATE are here
# because several migrations build DDL dynamically to look up a MySQL-auto-named
# constraint before dropping it (009, 016, 041, 20260727091519).
SQL_VERBS = (
    'CREATE', 'ALTER', 'DROP', 'INSERT', 'UPDATE', 'DELETE', 'SELECT', 'SET',
    'RENAME', 'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE', 'FLUSH', 'START',
    'COMMIT', 'ROLLBACK', 'CALL', 'DO', 'ANALYZE', 'OPTIMIZE', 'WITH',
    'PREPARE', 'EXECUTE', 'DEALLOCATE',
)


@pytest.mark.parametrize('path', _all_sql_files(), ids=_relative)
def test_every_parsed_statement_starts_with_a_sql_verb(path):
    """A statement that starts mid-sentence means the splitter cut one in half.

    This is the general form of the bug that made `schema.sql` unloadable: an
    inline `-- friendly name; auto-registration seeds it` comment split its own
    CREATE TABLE, and the second fragment began with the word `auto`. Checking
    the FIRST TOKEN of every statement in the whole corpus catches that class
    without having to predict which comment style causes it next time.
    """
    with open(path, 'r') as handle:
        statements = db_guard.parse_statements(handle.read())
    bad = [s for s in statements if s.split(None, 1)[0].upper() not in SQL_VERBS]
    assert not bad, (
        f'{_relative(path)} parses into statement(s) that do not begin with a SQL '
        f'verb — the splitter cut a statement in half: '
        f'{[" ".join(s.split())[:70] for s in bad[:3]]}'
    )


@pytest.mark.parametrize('path', _all_sql_files(), ids=_relative)
def test_target_declarations_are_well_formed(path):
    """A malformed declaration must fail here, not at 3am against production."""
    with open(path, 'r') as handle:
        targets = db_guard.declared_targets(handle.read())  # raises GuardError if bad
    if targets is not None:
        assert targets, f'{_relative(path)} declares an empty target list'


# ---------------------------------------------------------------------------
# The files whose target genuinely is restricted
# ---------------------------------------------------------------------------

RESTRICTED = {
    'scripts/recreate_darwin_dev.sql': ['darwin_dev'],
    'scripts/seed_pipelines_darwin_dev.sql': ['darwin_dev'],
    'migrations/057_drop_build_visualizer_from_production.sql': ['darwin'],
}


@pytest.mark.parametrize('relpath,expected', sorted(RESTRICTED.items()))
def test_restricted_files_declare_their_target(relpath, expected):
    path = os.path.join(DARWINSQL_ROOT, relpath)
    assert os.path.exists(path), f'{relpath} is gone — update RESTRICTED'
    with open(path) as handle:
        assert db_guard.declared_targets(handle.read()) == expected


def test_recreate_darwin_dev_is_declared_destructive():
    """It DROPs 52 tables. `--destructive` is the only way it runs."""
    path = os.path.join(DARWINSQL_ROOT, 'scripts', 'recreate_darwin_dev.sql')
    with open(path) as handle:
        body = handle.read()
    assert db_guard.is_destructive(body)
    assert 'darwin' not in db_guard.declared_targets(body), (
        'recreate_darwin_dev.sql must never list production as a target — that '
        'list is the absolute ban'
    )


def test_the_declaration_rules_are_enforced_for_ad_hoc_sql_too():
    """*** A rule that holds in one entry point and not another is not a rule. ***

    `check_sql_text` used to live inside `check_file`, so only the file loader
    consulted a `-- darwin:targets` declaration. Measured during the req #3196
    review: `query.py darwin -e "$(cat recreate_darwin_dev.sql)" --production
    --write` passed every guard and reached `connect()` — 52 production tables
    behind an ABSOLUTE ban that three documents call unoverridable.
    """
    path = os.path.join(DARWINSQL_ROOT, 'scripts', 'recreate_darwin_dev.sql')
    with open(path) as handle:
        body = handle.read()
    with pytest.raises(db_guard.GuardError, match='ABSOLUTE ban'):
        db_guard.check_sql_text(body, 'darwin', '-e', production=True,
                                destructive=True)


def test_seed_darwin_dev_cannot_be_pointed_at_production():
    """`seed_darwin_dev.py` holds the repo's last session-repointing `USE` — in
    PYTHON, so the corpus glob above cannot see it. It is safe only because its
    target is a non-production literal; pin that, since nothing else does."""
    path = os.path.join(DARWINSQL_ROOT, 'scripts', 'seed_darwin_dev.py')
    with open(path) as handle:
        source = handle.read()
    match = re.search(r"^TARGET_DATABASE\s*=\s*'([^']+)'", source, re.M)
    assert match, 'seed_darwin_dev.py no longer defines TARGET_DATABASE as a literal'
    assert not db_guard.is_production(match.group(1)), (
        f'seed_darwin_dev.py targets {match.group(1)!r} — it CREATEs a database '
        f'and issues USE, so a production target there is the whole req #3196 '
        f'defect with a Python wrapper'
    )


def test_scratch_db_cannot_address_a_real_database():
    """`scratch_db.py` is the only tool that runs CREATE DATABASE. Its guard is
    the NAME, because the statement IS the target and cannot be guarded by
    'the caller names it'."""
    sys.path.insert(0, os.path.join(DARWINSQL_ROOT, 'scripts'))
    import scratch_db

    for name in ('darwin', 'darwin_dev', 'DARWIN', 'scratch', 'darwin_scratch'):
        with pytest.raises(db_guard.GuardError, match='not a scratch database'):
            scratch_db.require_scratch_name(name)
    assert scratch_db.require_scratch_name('darwin_scratch_parity') == 'darwin_scratch_parity'


def test_seed_pipelines_generator_emits_no_use_statement():
    """The fixture .sql is GENERATED. Fixing the output without fixing the
    generator would put the `USE` back on the next regeneration."""
    path = os.path.join(DARWINSQL_ROOT, 'scripts', 'seed_pipelines_darwin_dev.py')
    with open(path) as handle:
        source = handle.read()
    assert "w('USE " not in source, (
        'seed_pipelines_darwin_dev.py emits a USE statement into the fixture'
    )
    assert "w('-- darwin:targets = darwin_dev')" in source, (
        'seed_pipelines_darwin_dev.py must emit the darwin_dev target declaration'
    )


# ---------------------------------------------------------------------------
# The guard itself
# ---------------------------------------------------------------------------

def test_production_needs_naming_twice():
    with pytest.raises(db_guard.GuardError, match='PRODUCTION'):
        db_guard.require_database('darwin')
    assert db_guard.require_database('darwin', production=True) == 'darwin'


def test_production_flag_on_a_non_production_database_is_refused():
    """Otherwise --production becomes a flag people always type."""
    with pytest.raises(db_guard.GuardError, match='disagree'):
        db_guard.require_database('darwin_dev', production=True)


def test_a_target_must_be_named_and_be_an_identifier():
    with pytest.raises(db_guard.GuardError, match='no target database'):
        db_guard.require_database('')
    with pytest.raises(db_guard.GuardError, match='identifier'):
        db_guard.require_database('darwin_dev; DROP DATABASE darwin')
    with pytest.raises(db_guard.GuardError, match='identifier'):
        db_guard.require_database('`darwin`')


def test_a_declared_ban_on_production_is_absolute():
    """No flag combination reaches production when the file excludes it."""
    for override in (False, True):
        with pytest.raises(db_guard.GuardError, match='ABSOLUTE ban'):
            db_guard.require_declared_target(
                'darwin', ['darwin_dev'], 'recreate_darwin_dev.sql', override=override)


def test_a_production_only_file_may_not_be_aimed_elsewhere():
    """Migration 057 drops tables `darwin_dev` deliberately keeps. Applying it
    there is never a parity load, so the override does not reach it either."""
    for override in (False, True):
        with pytest.raises(db_guard.GuardError, match='no flag overrides it'):
            db_guard.require_declared_target(
                'darwin_dev', ['darwin'], '057.sql', override=override)


def test_migration_057_is_declared_destructive():
    path = os.path.join(DARWINSQL_ROOT, 'migrations',
                        '057_drop_build_visualizer_from_production.sql')
    with open(path) as handle:
        assert db_guard.is_destructive(handle.read())


def test_a_non_production_target_outside_the_declaration_needs_the_override():
    with pytest.raises(db_guard.GuardError, match='override-file-target'):
        db_guard.require_declared_target('scratch', ['darwin_dev'], 'f.sql')
    # Allowed with the flag — the schema-parity gate loads into a scratch DB.
    db_guard.require_declared_target('scratch', ['darwin_dev'], 'f.sql', override=True)
    # No declaration means no restriction.
    db_guard.require_declared_target('scratch', None, 'f.sql')


def test_destructive_files_need_the_flag():
    body = '-- darwin:destructive\nDROP TABLE t;'
    with pytest.raises(db_guard.GuardError, match='darwin:destructive'):
        db_guard.require_destructive_ack(body, 'f.sql')
    db_guard.require_destructive_ack(body, 'f.sql', destructive=True)


def test_two_target_declarations_are_ambiguous_and_refused():
    with pytest.raises(db_guard.GuardError, match='ambiguous'):
        db_guard.declared_targets('-- darwin:targets = darwin_dev\n'
                                  '-- darwin:targets = darwin\n')


def test_a_hardcoded_target_is_refused_not_stripped():
    with pytest.raises(db_guard.GuardError, match='hardcodes its own database'):
        db_guard.require_no_hardcoded_target('USE darwin;\nSELECT 1;', 'f.sql')
    with pytest.raises(db_guard.GuardError, match='hardcodes its own database'):
        db_guard.require_no_hardcoded_target('CREATE DATABASE darwin;', 'f.sql')


# ---------------------------------------------------------------------------
# The statement splitter — the predicate everything above rests on
# ---------------------------------------------------------------------------

def test_a_semicolon_inside_an_inline_comment_does_not_split_a_statement():
    """*** The bug that made schema.sql unloadable. ***

    `-- friendly name; auto-registration seeds it` is ONE comment to MySQL. The
    pre-#3196 splitter dropped only FULL-LINE comments, so it cut the CREATE
    TABLE in half at that `;` and the first half — truncated at `NOT NULL,` —
    was a syntax error partway through a DDL file. Measured: schema.sql created
    7 of 53 tables and stopped. It hit migrations 064, 067 and 069 too.
    """
    ddl = ('CREATE TABLE machines (\n'
           '    id INT NOT NULL,\n'
           '    title VARCHAR(256) NOT NULL,   -- friendly name; auto-registration seeds it\n'
           '    hostname VARCHAR(128) NOT NULL -- auto-detected; the match key; UNIQUE\n'
           ');\n')
    statements = db_guard.parse_statements(ddl)
    assert len(statements) == 1, f'split into {len(statements)}: {statements}'
    assert statements[0].startswith('CREATE TABLE machines')
    assert 'hostname VARCHAR(128) NOT NULL' in statements[0]
    assert 'friendly name' not in statements[0], 'comment text leaked into the statement'


def test_hash_and_block_comments_do_not_split_either():
    assert len(db_guard.parse_statements('SELECT 1 # a; b\n, 2;')) == 1
    assert len(db_guard.parse_statements('SELECT /* a; b */ 1;')) == 1


def test_semicolons_hashes_and_dashes_inside_literals_survive_intact():
    """The corpus reason the splitter is hand-rolled: requirement titles carry
    `;` and `#`, and pipeline_steps.notes carries `--no-hardlinks`."""
    sql = ("INSERT INTO t (a) VALUES "
           "('from local mirrors; retire git-worktree machinery #3079 --no-hardlinks');")
    statements = db_guard.parse_statements(sql)
    assert len(statements) == 1
    assert 'retire git-worktree machinery #3079 --no-hardlinks' in statements[0]
    # Doubled '' is MySQL's escape — it lands back inside the string.
    assert len(db_guard.parse_statements("INSERT INTO t VALUES ('it''s; fine');")) == 1
    # Double quotes are string literals here (no ANSI_QUOTES) — migration 004 uses them.
    assert len(db_guard.parse_statements('UPDATE t SET a = "x; y";')) == 1
    # A backslash escape does not end the literal.
    assert len(db_guard.parse_statements(r"INSERT INTO t VALUES ('a\'; b');")) == 1


def test_a_double_dash_without_trailing_whitespace_is_not_a_comment():
    """MySQL requires the whitespace. `--` glued to a token stays in the statement."""
    assert db_guard.parse_statements('SELECT 1--2;') == ['SELECT 1--2']


def test_an_unterminated_comment_or_literal_is_refused_not_truncated():
    """*** Silence is the failure mode this whole requirement is about. ***

    An unclosed `/*` used to discard everything after it: the loader applied the
    prefix and printed `status=ok`, and the audit called the file clean while a
    live `USE darwin;` sat inside the unterminated comment, plainly visible to
    the `mysql` CLI. Truncation and success must never be the same outcome.
    """
    hidden = 'CREATE TABLE a (id INT);\n/* oops\nUSE darwin;\nCREATE TABLE b (id INT);\n'
    with pytest.raises(db_guard.GuardError, match='unterminated /\\* block comment'):
        db_guard.parse_statements(hidden)
    with pytest.raises(db_guard.GuardError, match='unterminated'):
        db_guard.parse_statements("INSERT INTO t VALUES ('never closed;")


def test_create_schema_is_a_hardcoded_target_too():
    """`SCHEMA` is an exact MySQL synonym for `DATABASE`."""
    for statement in ('CREATE SCHEMA darwin;', 'DROP DATABASE darwin;',
                      'DROP SCHEMA darwin;', 'ALTER DATABASE darwin CHARACTER SET utf8;'):
        assert db_guard.hardcoded_target_statements(statement), statement


def test_an_unrecognised_darwin_directive_is_refused_not_ignored():
    """*** A typo used to silently mean NO restriction. ***

    `-- darwin:target = darwin_dev` (singular) in `recreate_darwin_dev.sql`
    would have removed both the production ban and the destructive gate while
    still reading, to a human, as protected.
    """
    for typo in ('-- darwin:target = darwin_dev',
                 '-- darwin:targets: darwin_dev',
                 '-- darwin:destructiv',
                 '-- darwin:targets ='):
        with pytest.raises(db_guard.GuardError, match='unrecognised directive'):
            db_guard.declared_targets(typo)
    # Any run of leading dashes is a comment to MySQL, so it is a directive here.
    assert db_guard.declared_targets('---- darwin:targets = darwin_dev') == ['darwin_dev']
    # Prose that MENTIONS the directive mid-sentence is not a claim.
    assert db_guard.declared_targets('-- `darwin:targets` omits darwin, so ...') is None
    # Nor is an MCP resource URI — schema.sql and migration 076 both open a
    # comment with one, and refusing a legitimate file is its own defect.
    assert db_guard.declared_targets('-- darwin://pipeline/{id} carries the plan.') is None


def test_a_database_name_is_matched_whole_and_case_insensitively():
    """Python's `$` also matches before a trailing newline: `'darwin\\n'` passed
    the old anchor AND compared unequal to `'darwin'`, so production classified
    as non-production."""
    with pytest.raises(db_guard.GuardError, match='identifier'):
        db_guard.require_database('darwin\n')
    for variant in ('DARWIN', 'Darwin'):
        assert db_guard.is_production(variant), variant
        with pytest.raises(db_guard.GuardError, match='PRODUCTION'):
            db_guard.require_database(variant)


def test_the_declared_target_ban_is_not_overridable_where_there_is_no_flag():
    """A refusal must not recommend a flag its own caller then refuses."""
    with pytest.raises(db_guard.GuardError, match='no flag for this'):
        db_guard.require_declared_target('scratch', ['darwin_dev'], 'seed.py',
                                         overridable=False)


def test_the_word_use_in_a_comment_or_a_literal_is_not_a_target():
    """False positives here would block legitimate files, which is its own defect."""
    db_guard.require_no_hardcoded_target('-- USE darwin;\nSELECT 1;', 'f.sql')
    db_guard.require_no_hardcoded_target(
        "INSERT INTO requirements (title) VALUES ('do not\nUSE darwin; ever');", 'f.sql')
    db_guard.require_no_hardcoded_target('SELECT * FROM user_integrations;', 'f.sql')
