"""
DarwinSQL migration FILENAME invariants. (req #3121)

This module is deliberately FILESYSTEM-ONLY — it opens no database connection
and needs no credentials, because everything it asserts is a property of the
`migrations/` directory listing. That is why it overrides conftest's autouse
`seed_test_profile` fixture below: the naming contract must be checkable on any
machine, in CI, and inside a `deployed` swarm worker that has no DB access.

    python3 -m pytest tests/test_migration_naming.py -q     # no env vars needed

WHAT WENT WRONG (the reason this file exists)
---------------------------------------------
Migration numbers were hand-picked as max(NNN)+1 read off the author's own clone
of `migrations/`. That listing is a snapshot of `main` frozen at branch time, so
two concurrent swarm sessions — or any session whose clone predates a sibling's
merge — allocate the SAME number. It happened three times before anyone noticed:
046, 050 and 074 each carry two unrelated migrations on origin/main.

The collisions were silent because each pair happened to touch disjoint tables.
Two same-numbered migrations touching the SAME table would apply in arbitrary
alphabetical-suffix order, and "migration 074" is ambiguous in every downstream
artifact: the memory/database.md ledger, the `darwin-pre-migration-074-*` RDS
snapshot id, and any conversation about what shipped.

THE CONTRACT
------------
    New era     YYYYMMDDHHMMSS_description.sql   14-digit UTC stamp, allocated
                                                 by DarwinSQL/scripts/new-migration.sh
    Legacy era  NNN_description.sql              001-076 — FROZEN, a closed set

A 14-digit stamp comes from the clock, not from shared mutable state, so two
sessions would have to create a migration in the same UTC SECOND to tie. All
14-digit stamps sort strictly after every legacy `0NN_` file ('0' < '2'), so
lexicographic filename order is still apply order and
`test_migrations._get_dependency_ordered_migrations()` needed no change.

Full rationale, rejected alternatives, and the collision manifest live in
memory/database.md § Migration Number Allocation.
"""
import datetime
import glob
import os
import re

import pytest


# ---------------------------------------------------------------------------
# This module needs no database. Override conftest's session-scoped autouse
# seeding fixture (which pulls in db_connection and therefore credentials) with
# a no-op, so these tests run anywhere.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def seed_test_profile():
    """No-op override — test_migration_naming.py is filesystem-only."""
    yield {}


# ---------------------------------------------------------------------------
# The frozen legacy era
# ---------------------------------------------------------------------------

# The last integer migration ever allocated. Migration 077 does not exist and
# never will: the integer era closed with req #3121. Raising this number
# re-opens the collision class and is therefore not a maintenance step — it is
# a reversal of the decision in memory/database.md § Migration Number Allocation.
LEGACY_CEILING = 76

# The three known duplicate prefixes on origin/main, grandfathered by EXACT
# filename. All six files are already applied to production `darwin` and to
# `darwin_dev`; renaming them would break the correspondence between each file
# and the `darwin-pre-migration-<NNN>-*` snapshot taken when it was applied, for
# no functional gain. The canonical unambiguous handle for any file in a pair is
# its FULL FILENAME, never the bare number.
#
# This mapping is a closed historical record. Nothing may be added to it.
GRANDFATHERED_COLLISIONS = {
    '046': (
        '046_add_requirements_sort_order_back.sql',   # req #2417
        '046_add_swarm_starts.sql',                   # req #2422
    ),
    '050': (
        '050_add_app_swarm_validate_to_profiles.sql',  # req #2611
        '050_add_build_data_model.sql',                # req #2606
    ),
    '074': (
        '074_add_agent_telemetry_row_docs.sql',        # req #3096
        '074_agent_telemetry_breakdown.sql',           # req #3095
    ),
}

LEGACY_RE = re.compile(r'^(\d{3})_([a-z0-9]+(?:_[a-z0-9]+)*)\.sql$')
TIMESTAMP_RE = re.compile(r'^(\d{14})_([a-z0-9]+(?:_[a-z0-9]+)*)\.sql$')


def _migrations_dir():
    """Absolute path to DarwinSQL/migrations/."""
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(tests_dir), 'migrations')


def _migration_filenames():
    """Every migration filename, sorted. Basenames only."""
    files = sorted(
        os.path.basename(p)
        for p in glob.glob(os.path.join(_migrations_dir(), '*.sql'))
    )
    assert files, f"no migration files found in {_migrations_dir()}"
    return files


def _prefix(filename):
    """The digits before the first underscore, as a string (never int)."""
    return filename.split('_', 1)[0]


# ---------------------------------------------------------------------------
# Test: every filename matches the naming contract
# ---------------------------------------------------------------------------

# COVERS: SCH-029
def test_every_migration_filename_matches_the_naming_contract():
    """Each file is a legacy 3-digit or a new-era 14-digit UTC stamp.

    Anything else — a bare description, a 4-digit number, an uppercase or
    hyphenated slug — fails here rather than silently joining the directory.
    """
    bad = []
    for name in _migration_filenames():
        if not (LEGACY_RE.match(name) or TIMESTAMP_RE.match(name)):
            bad.append(name)

    assert not bad, (
        "migration filenames must be either NNN_lower_snake.sql (legacy, "
        f"001-{LEGACY_CEILING:03d}) or YYYYMMDDHHMMSS_lower_snake.sql (new era, "
        "allocated by DarwinSQL/scripts/new-migration.sh). Offenders: "
        + ', '.join(bad)
    )


def test_new_era_prefixes_are_real_utc_timestamps():
    """A 14-digit prefix must parse as a calendar date-time, not just digits.

    `20261332000000` is 14 digits and would sort fine, but it is not a moment in
    time and would tell a future reader nothing. It also usually means the stamp
    was typed by hand instead of allocated.
    """
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    horizon = now + datetime.timedelta(days=1)

    for name in _migration_filenames():
        m = TIMESTAMP_RE.match(name)
        if not m:
            continue
        stamp = m.group(1)
        try:
            when = datetime.datetime.strptime(stamp, '%Y%m%d%H%M%S')
        except ValueError as exc:
            pytest.fail(f"{name}: prefix {stamp} is not a valid UTC timestamp ({exc})")

        # The timestamp era began with req #3121 in July 2026. An earlier stamp
        # would sort among nothing and signals a mistyped year.
        assert when.year >= 2026, (
            f"{name}: prefix {stamp} predates the timestamp era (req #3121, 2026-07)"
        )
        # A future stamp sorts after migrations that do not exist yet, which
        # silently corrupts apply order. One day of tolerance absorbs any
        # plausible clock skew across the fleet.
        assert when <= horizon, (
            f"{name}: prefix {stamp} is more than a day in the future — check the "
            "machine clock; new-migration.sh stamps with `date -u`"
        )


# ---------------------------------------------------------------------------
# Test: no duplicate prefixes (the core invariant)
# ---------------------------------------------------------------------------

def test_no_duplicate_migration_prefixes_outside_the_frozen_allowlist():
    """THE test. Any new duplicate prefix fails the build.

    This is the gate that makes req #3121's failure class dead: 046, 050 and 074
    are grandfathered by exact filename, and every other prefix must be unique.
    A fourth collision — integer or timestamp — cannot merge.
    """
    by_prefix = {}
    for name in _migration_filenames():
        by_prefix.setdefault(_prefix(name), []).append(name)

    duplicates = {p: sorted(n) for p, n in by_prefix.items() if len(n) > 1}
    allowed = {p: sorted(n) for p, n in GRANDFATHERED_COLLISIONS.items()}

    unexpected = {p: n for p, n in duplicates.items() if allowed.get(p) != n}

    assert not unexpected, (
        "duplicate migration prefix(es) detected:\n"
        + '\n'.join(f"  {p}: {', '.join(n)}" for p, n in sorted(unexpected.items()))
        + "\n\nNever hand-pick a migration number. Allocate the file with:\n"
          "  bash DarwinSQL/scripts/new-migration.sh <description> --req <id>\n"
          "See memory/database.md § Migration Number Allocation."
    )


def test_the_grandfathered_collisions_are_exactly_the_known_six_files():
    """The allow-list is a historical record, not a maintenance surface.

    If one of the six is renamed or deleted, this fails — so the allow-list can
    never rot into a blanket exemption that quietly covers a NEW collision.
    """
    present = set(_migration_filenames())
    expected = {n for pair in GRANDFATHERED_COLLISIONS.values() for n in pair}

    missing = sorted(expected - present)
    assert not missing, (
        "grandfathered collision file(s) no longer on disk: " + ', '.join(missing)
        + ". These six files are applied to production; if one was deliberately "
          "renamed, update GRANDFATHERED_COLLISIONS and memory/database.md "
          "§ Migration Number Allocation together."
    )

    # Exactly three pairs, two files each — no room for a fourth to be slipped in.
    assert len(GRANDFATHERED_COLLISIONS) == 3
    assert all(len(pair) == 2 for pair in GRANDFATHERED_COLLISIONS.values())
    assert len(expected) == 6


# ---------------------------------------------------------------------------
# Test: the integer era is closed
# ---------------------------------------------------------------------------

def test_the_legacy_integer_era_is_closed():
    """No 3-digit migration above the frozen ceiling may ever be added.

    Uniqueness alone would not kill the class: an author could still hand-pick
    077, and the NEXT session with a stale clone would hand-pick 077 too — the
    collision would only be caught after both had been applied to darwin_dev.
    Closing the era means there is no number left to guess.
    """
    over = []
    for name in _migration_filenames():
        m = LEGACY_RE.match(name)
        if m and int(m.group(1)) > LEGACY_CEILING:
            over.append(name)

    assert not over, (
        f"the 3-digit migration era is frozen at {LEGACY_CEILING:03d} (req #3121). "
        "New migrations use a UTC timestamp: "
        "bash DarwinSQL/scripts/new-migration.sh <description> --req <id>. "
        "Offenders: " + ', '.join(over)
    )


def test_the_legacy_era_is_contiguous_and_complete():
    """001-076 all present, nothing below 001. Guards accidental deletion.

    The legacy set is closed, so its membership is a constant: every integer in
    [1, 76] is represented exactly once (or twice, for the three grandfathered
    prefixes) and no integer outside that range appears.
    """
    legacy_nums = sorted({
        int(m.group(1))
        for m in (LEGACY_RE.match(n) for n in _migration_filenames())
        if m
    })

    assert legacy_nums == list(range(1, LEGACY_CEILING + 1)), (
        "the frozen legacy migration set 001-076 has changed. Missing: "
        f"{sorted(set(range(1, LEGACY_CEILING + 1)) - set(legacy_nums))}, "
        f"unexpected: {sorted(set(legacy_nums) - set(range(1, LEGACY_CEILING + 1)))}"
    )


# ---------------------------------------------------------------------------
# Test: ordering invariants the rest of the suite depends on
# ---------------------------------------------------------------------------

def test_new_era_files_sort_after_every_legacy_file():
    """Lexicographic filename order must remain apply order across the cutover.

    `test_migrations._get_dependency_ordered_migrations()` orders by
    `sorted(glob(...))`. Legacy prefixes all start with '0'; timestamps start
    with '2'; '0' < '2', so the eras never interleave. This test would catch a
    future scheme change that broke that (e.g. dropping the zero-padding).
    """
    names = _migration_filenames()
    legacy = [n for n in names if LEGACY_RE.match(n)]
    modern = [n for n in names if TIMESTAMP_RE.match(n)]

    # Prove the invariant even before the first timestamp migration lands: the
    # whole cutover rests on '0' < '2', so check it against the SMALLEST stamp
    # the new era can ever produce rather than only against files that exist.
    # Without this the test would sit vacuously skipped until someone shipped a
    # timestamp migration — i.e. exactly when it is too late to find out.
    earliest_possible = '20000000000000_a.sql'
    assert max(legacy) < earliest_possible, (
        f"legacy file {max(legacy)} sorts after the earliest possible timestamp "
        f"name {earliest_possible} — the two eras would interleave"
    )

    if not modern:
        pytest.skip("no timestamp-era migrations on disk yet (invariant proven above)")

    assert max(legacy) < min(modern), (
        f"legacy file {max(legacy)} sorts after timestamp file {min(modern)} — "
        "apply order and filename order have diverged"
    )


def test_every_prefix_parses_as_an_int():
    """`_get_dependency_ordered_migrations()` calls int(basename.split('_')[0]).

    Both eras must survive that call unchanged. int('20260727043000') is fine on
    Python's arbitrary-precision ints; a non-numeric prefix would raise there and
    take the whole migration suite down with a ValueError instead of a clear
    naming failure here.
    """
    for name in _migration_filenames():
        prefix = _prefix(name)
        try:
            value = int(prefix)
        except ValueError:
            pytest.fail(f"{name}: prefix {prefix!r} is not an integer")
        assert value > 0, f"{name}: prefix must be positive, got {value}"

    # The early/mid/late partition in _get_dependency_ordered_migrations() keys
    # off `num <= 8`. Only the legacy 001-008 files may fall in that bucket; a
    # timestamp never can, but assert it rather than assume it.
    early = [n for n in _migration_filenames() if int(_prefix(n)) <= 8]
    assert all(LEGACY_RE.match(n) for n in early)
    assert len(early) == 8


def test_no_migration_file_is_comment_only():
    """A migration that contains no SQL statement is a silent no-op.

    `new-migration.sh` deliberately writes a comment-only header template, so
    "create the file, then write the DDL into it" is now the routine first step
    of every schema change — which makes "forgot the second half" a live failure
    mode. `test_migrations.py` strips `--` comments and skips empty statements,
    so an unfilled migration passes the entire rest of the suite while changing
    nothing. It would then be recorded as applied to darwin_dev AND production.

    The comment rule here is a deliberate LINE-LEVEL SUBSET of the one in
    `test_migrations._apply_migration()` (which truncates each line at an inline
    `--` and also handles `#`). A subset is sufficient — and safer — for this
    check: `new-migration.sh` writes whole-line `--` comments only, and a
    line-level rule cannot mistake a `--` or `#` inside a string literal for the
    start of a comment. Erring toward "this file has content" means this test
    can only ever miss an empty file, never falsely condemn a real one.
    """
    empty = []
    for name in _migration_filenames():
        with open(os.path.join(_migrations_dir(), name), encoding='utf-8') as fh:
            body = fh.read()
        statements = '\n'.join(
            line for line in body.splitlines()
            if line.strip() and not line.strip().startswith(('--', '#'))
        ).strip()
        if not statements:
            empty.append(name)

    assert not empty, (
        "migration file(s) contain only comments — the DDL was never written: "
        + ', '.join(empty)
    )


# ---------------------------------------------------------------------------
# Test: the allocator is present
# ---------------------------------------------------------------------------

def test_the_allocator_script_exists():
    """Every doc now points at new-migration.sh; it must actually be there.

    The naming rules above are only enforceable because there is a one-command
    way to obey them. If the script goes missing, authors go back to hand-picking
    numbers and the collision class comes back.
    """
    script = os.path.join(
        os.path.dirname(_migrations_dir()), 'scripts', 'new-migration.sh'
    )
    assert os.path.isfile(script), f"missing migration allocator: {script}"

    body = open(script, encoding='utf-8').read()
    assert 'date -u +%Y%m%d%H%M%S' in body, (
        "new-migration.sh must stamp in UTC — a local-time stamp sorts wrong "
        "across a DST boundary and differs between machines in the fleet"
    )
