"""A DROP that vacates a table name for a companion RENAME must not be split
across two migration files. (req #3495)

WHAT WENT WRONG (the reason this file exists)
-----------------------------------------------
Req #3356's "eradicate then rename" cutover shipped the eradication and the
rename as two SEPARATE migrations, applied as two separate production DDL
operations ~49 minutes apart: `20260812175325` DROPped the five 1.0 pipeline
tables (`pipelines`, `pipeline_steps`, `pipeline_step_requirements`,
`pipeline_step_deps`, `epics`), and `20260812184333` later RENAMEd the live
2.0 tables (`pipeline2_*`) onto those same plain names.

MySQL forces that ordering — `RENAME TABLE x TO y` refuses if `y` already
exists, so the DROP must land first. But nothing forced the RENAME to follow
it immediately. Measured via AWS CLI, the RDS snapshot preceding the DROP was
created 2026-08-12T17:58:03Z and the snapshot preceding the RENAME was
created 2026-08-12T18:47:45Z, a 49-minute gap with ZERO Lambda-Rest deploys
in between (CloudTrail). CloudWatch confirms production `1146 Table
'darwin.pipeline_step_requirements' doesn't exist` / `'darwin.pipelines'
doesn't exist` errors from 18:01:25Z-18:05:55Z, squarely inside that gap —
the exact outage req #3495 reports on `darwin://requirements/*` and
`darwin://pipelines`. No code deploy could have shortened the window: no
table existed under the plain name for the entire 49 minutes, regardless of
which Lambda-Rest code was live. See memory/database.md § Schema Migration
Workflow for the full incident writeup and the doctrine this test enforces.

THE CONTRACT
------------
A migration that VACATES table name X (drops it, or renames it away to make
room) and a migration that CLAIMS X for a different table (renames another
table onto it) must be the SAME migration file, applied as one production
DDL operation. Splitting them across two files/applies reopens this exact
hazard for whatever table name is being handed off — whether the vacate side
is `DROP TABLE`, `RENAME TABLE old TO archive`, or `ALTER TABLE old RENAME TO
archive` (all three make `old`'s original name available), and whether the
claim side is `RENAME TABLE new TO old` or `ALTER TABLE new RENAME TO old`.

INVOCATION. This module needs no database and runs the same way
`test_sql_targets.py` does — as part of the DarwinSQL suite
(`cd DarwinSQL && python3 -m pytest tests/ -q`), which is why it is not
independently wired into a lighter-weight gate: the other DarwinSQL modules
in that same run need `darwin_dev` credentials, so there is no meaningfully
cheaper subset to add this to today.

    python3 -m pytest tests/test_no_split_drop_rename.py -v     # no env vars needed
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
    """No-op override — test_no_split_drop_rename.py is filesystem-only."""
    yield {}


def _all_migration_files():
    return sorted(glob.glob(os.path.join(DARWINSQL_ROOT, 'migrations', '*.sql')))


def _relative(path):
    return os.path.relpath(path, DARWINSQL_ROOT)


def _read(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# The one historical pair that already shipped to production and cannot be
# unshipped. Frozen (like test_migration_naming.py's legacy era) — keyed by
# (vacating file, claiming file) -> the reason a new entry was needed.
#
# A table name legitimately reused long after its DROP (e.g. Build Visualizer
# tables dropped by 057, or `features`/`feature_test_cases` dropped by
# 20260811033413) is NOT a case for this list — nothing reads a name that
# stayed vacant. This list is only for a genuine split of one drop-then-claim
# HANDOFF across two files; combine them into one migration instead of adding
# a second entry unless that is truly impossible (the historical pair below
# already shipped to production and cannot be retroactively combined).
# ---------------------------------------------------------------------------

GRANDFATHERED_SPLIT_PAIRS = {
    ('20260812175325_drop_1_0_pipeline_layer_pipelines_pipeline_steps_pipeline_st.sql',
     '20260812184333_rename_pipeline2_to_plain_names_now_that_1_0_is_gone.sql'):
        'req #3495 — already applied to production in two separate DDL operations '
        '49 minutes apart before this guard existed; cannot be retroactively combined.',
}


def _clean_name(raw):
    """Strip trailing punctuation, drop a schema qualifier, drop backticks —
    in that order, so `darwin.\\`foo\\`` yields `foo`, not `` `foo ``.
    """
    name = raw.strip().strip('`,;')
    name = name.split('.')[-1]
    return name.strip('`')


def _split_name_list(fragment):
    """A comma-separated list of (possibly backtick-quoted, possibly
    schema-qualified) table names, as it appears after `DROP TABLE
    [IF EXISTS]` — e.g. `a, b, c` or `` `a`, `b` ``.
    """
    return [_clean_name(part) for part in fragment.split(',') if part.strip()]


_DROP_TABLE = re.compile(r'^DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(.+)$', re.IGNORECASE)
_RENAME_TABLE_PAIR = re.compile(r'^\s*(\S+)\s+TO\s+(\S+)\s*$', re.IGNORECASE)
_ALTER_TABLE_RENAME = re.compile(r'^ALTER\s+TABLE\s+(\S+).*?\bRENAME\s+TO\s+(\S+)', re.IGNORECASE)


def _rename_pairs(sql_text):
    """(source_name, target_name) for every table rename in this file's
    statements — `RENAME TABLE x TO y[, a TO b, ...]` and
    `ALTER TABLE x RENAME TO y`. Deliberately excludes `RENAME COLUMN ... TO
    ...` and `RENAME INDEX ... TO ...`: MySQL's table-rename clause is the
    literal two-word phrase `RENAME TO` immediately after the table name (or
    after the `RENAME TABLE` keyword), which is exactly what the regexes
    below require — `RENAME COLUMN x TO y` never matches because `COLUMN`
    sits between `RENAME` and `TO`.
    """
    pairs = []
    for statement in db_guard.parse_statements(sql_text):
        norm = ' '.join(statement.split())

        if norm.upper().startswith('RENAME TABLE'):
            rest = norm[len('RENAME TABLE'):]
            for fragment in rest.split(','):
                m = _RENAME_TABLE_PAIR.match(fragment)
                if m:
                    pairs.append((_clean_name(m.group(1)), _clean_name(m.group(2))))
            continue

        if norm.upper().startswith('ALTER TABLE'):
            m = _ALTER_TABLE_RENAME.match(norm)
            if m:
                pairs.append((_clean_name(m.group(1)), _clean_name(m.group(2))))

    return pairs


def _vacated_table_names(sql_text):
    """Table names this migration's statements make UNAVAILABLE under their
    current spelling: every `DROP TABLE [IF EXISTS] a[, b, ...]` target, plus
    the SOURCE side of every table rename (a rename-away, e.g. `RENAME TABLE
    old TO old_archive`, vacates `old` exactly as a DROP would).
    """
    names = set()
    for statement in db_guard.parse_statements(sql_text):
        norm = ' '.join(statement.split())
        m = _DROP_TABLE.match(norm)
        if m:
            names.update(_split_name_list(m.group(1)))
    names.update(source for source, _target in _rename_pairs(sql_text))
    return names


def _claimed_table_names(sql_text):
    """Table names a rename in this migration makes available under a NEW
    spelling: the TARGET side of every table rename.
    """
    return {target for _source, target in _rename_pairs(sql_text)}


def test_there_are_migration_files_to_check():
    files = _all_migration_files()
    assert len(files) > 50, f'only {len(files)} migration files found under {DARWINSQL_ROOT}/migrations'


def _find_split_pairs(files, exceptions):
    """Every (table_name, vacating_file, claiming_file) where a DIFFERENT
    file claims a name this file vacated, excluding pairs in `exceptions`.
    This is the detector both the real test and its own sanity check drive —
    factored out so the sanity check exercises the real logic instead of
    duplicating one assertion from it.
    """
    vacated_in = {}   # table name -> set of relative paths that vacate it
    claimed_in = {}   # table name -> set of relative paths that claim it

    for path in files:
        text = _read(path)
        rel = _relative(path)
        for name in _vacated_table_names(text):
            vacated_in.setdefault(name, set()).add(rel)
        for name in _claimed_table_names(text):
            claimed_in.setdefault(name, set()).add(rel)

    violations = []
    for name, vacating_files in vacated_in.items():
        for vacating_path in vacating_files:
            for claiming_path in claimed_in.get(name, set()):
                if vacating_path == claiming_path:
                    continue  # same file — the safe, atomic shape
                pair = (os.path.basename(vacating_path), os.path.basename(claiming_path))
                if pair in exceptions:
                    continue
                violations.append((name, vacating_path, claiming_path))
    return violations


def test_no_drop_and_rename_into_the_same_table_name_are_split_across_files():
    """*** The acceptance criterion of req #3495. ***

    For every table name X: if one migration file vacates X (DROP, or a
    rename-away) and a DIFFERENT migration file claims X (renames some other
    table onto it), that pair must be in GRANDFATHERED_SPLIT_PAIRS.
    Otherwise, combine them into one migration file so the vacate and the
    claim apply as a single production DDL operation with no gap between
    them.
    """
    violations = _find_split_pairs(_all_migration_files(), GRANDFATHERED_SPLIT_PAIRS)
    assert not violations, (
        'A table name is vacated (DROPped, or renamed away) in one migration and '
        'claimed (renamed-into) by a different migration — the exact split that left '
        '`pipelines`/`pipeline_step_requirements` absent from production for 49 minutes '
        'at req #3356 (see memory/database.md § Schema Migration Workflow). Combine the '
        f'two migration files into one: {violations}'
    )


def test_the_grandfathered_pairs_still_exist_and_still_reproduce_the_shape():
    """The exception list must name real files in the real split shape — not a
    typo that silently exempts nothing, and not a stale entry for files that
    were later merged into one.
    """
    for (vacate_name, claim_name), reason in GRANDFATHERED_SPLIT_PAIRS.items():
        assert reason.strip(), f'{vacate_name} / {claim_name} has no reason recorded'
        vacate_path = os.path.join(DARWINSQL_ROOT, 'migrations', vacate_name)
        claim_path = os.path.join(DARWINSQL_ROOT, 'migrations', claim_name)
        assert os.path.exists(vacate_path), f'grandfathered vacating file missing: {vacate_name}'
        assert os.path.exists(claim_path), f'grandfathered claiming file missing: {claim_name}'
        vacated = _vacated_table_names(_read(vacate_path))
        claimed = _claimed_table_names(_read(claim_path))
        assert vacated & claimed, (
            f'{vacate_name} / {claim_name} no longer share a table name — remove the '
            f'stale GRANDFATHERED_SPLIT_PAIRS entry'
        )


def test_detector_fires_without_the_grandfather_exception(monkeypatch):
    """Sanity-check the detector ITSELF, by driving the same helper the real
    test uses with the exception list emptied — not by re-deriving one
    assertion from it. A detector that never fires is worse than no detector:
    it looks like coverage and provides none.
    """
    monkeypatch.setattr(sys.modules[__name__], 'GRANDFATHERED_SPLIT_PAIRS', set())
    violations = _find_split_pairs(_all_migration_files(), exceptions=set())
    assert violations, 'detector found no violations with the exception list emptied — it would never have caught this incident'
    flagged_names = {name for name, _v, _c in violations}
    assert flagged_names >= {'pipelines', 'epics', 'pipeline_steps',
                              'pipeline_step_requirements', 'pipeline_step_deps'}, (
        f'expected the historical incident\'s five table names to be flagged, got {flagged_names}'
    )
