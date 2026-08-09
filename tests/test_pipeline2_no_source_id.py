"""No pipeline2_* table carries a source_id column. (req #3340, IMP-016)

FILESYSTEM-ONLY — no database connection, no Cognito identity. Everything this
file asserts is a property of `schema.sql`'s own text, so it runs anywhere,
exactly like `test_migration_naming.py`.

memory/pipeline-2-data-architecture.md § 7.1: the three id-mapped 2.0 tables
(pipeline2_pipelines, pipeline2_epics, pipeline2_steps) have no natural key
back to their 1.0 source row, and the answer is deliberately NOT a stored
`source_id` column — "schema that exists only for the migration, survives
eradication, and states a fact about a table that will not exist." The
1.0 -> 2.0 importer (`scripts/swarm/import_plan_1to2.py` in DarwinAI-Config)
instead recomputes the id map every run by positional matching. This test
holds the schema side of that decision down: the day a `source_id` column
appears on any pipeline2_* table, the design record's own reasoning has been
quietly reversed and nothing else would notice.

# COVERS: IMP-016
"""
import os
import re

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCHEMA_PATH = os.path.join(_REPO_ROOT, 'schema.sql')

_PIPELINE2_TABLES = (
    'pipeline2_pipelines', 'pipeline2_epics', 'pipeline2_steps',
    'pipeline2_step_requirements', 'pipeline2_step_deps',
)


# This module needs no database. Override conftest's session-scoped autouse
# seeding fixture (which pulls in db_connection and therefore credentials) with
# a no-op, so these tests run anywhere — same override as test_migration_naming.py.
@pytest.fixture(scope="module", autouse=True)
def seed_test_profile():
    """No-op override — this file is filesystem-only."""
    yield {}


def _table_ddl(table):
    """The full `CREATE TABLE ... );` text for one table, or None if absent."""
    with open(_SCHEMA_PATH) as f:
        text = f.read()
    match = re.search(
        r'CREATE TABLE IF NOT EXISTS %s \(.*?\n\);' % re.escape(table),
        text, re.DOTALL)
    return match.group(0) if match else None


def test_every_pipeline2_table_exists_in_schema():
    for table in _PIPELINE2_TABLES:
        assert _table_ddl(table) is not None, (
            f"{table} not found in schema.sql — this test's own regex or the "
            "table's own DDL has drifted")


def test_no_pipeline2_table_carries_a_source_id_column():
    offenders = []
    for table in _PIPELINE2_TABLES:
        ddl = _table_ddl(table)
        if ddl and re.search(r'\bsource_id\b', ddl):
            offenders.append(table)
    assert not offenders, (
        "memory/pipeline-2-data-architecture.md § 7.1: a source_id column is "
        "schema that exists only for the migration and survives eradication. "
        f"Offenders: {offenders}")
