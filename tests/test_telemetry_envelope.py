"""The SHARED TELEMETRY ENVELOPE is one definition, on four tables. (req #3202)

THIS FILE IS THE REASON DUPLICATING THE COLUMNS IS SAFE.
--------------------------------------------------------
Req #3202 weighed three shapes for "one telemetry record both domains use":

  (a) a shared `telemetry_runs` table both domains FK to — cleanest query story,
      REJECTED because Lambda-Rest has no JOIN, so it would put every run's cost
      one hop from every surface that renders it: the fan-out req #3080 design
      rule 5 forbids and req #3117 spent a requirement removing.
  (b) a shared VALUE TYPE serialized into the containers both domains already
      have — CHOSEN.
  (c) harness-only convergence — not an alternative to (b); it is (b)'s writer.

The requirement states (b)'s cost honestly: *"nothing structurally prevents
future drift."* That is true of a CONVENTION and false of a DERIVED CHECK, and
this file is the derived check. It reads the ONE declaration
(`scripts/telemetry/envelope.py`) and the actual DDL (`DarwinSQL/schema.sql`) and
fails the build if any envelope-bearing table's columns or types disagree — the
same derive-from-the-DDL mechanism `CREATOR_TABLE_REFERENCES` (req #3125) uses,
and for the same reason: a hand-maintained list of what should match is exactly
the thing that drifts.

FILESYSTEM-ONLY, DELIBERATELY. It opens no database and needs no credentials —
everything it asserts is a property of two tracked files. That is what lets it
run in CI, on any machine, and inside a `deployed` swarm worker with no DB access
(the same posture test_migration_naming.py takes, and for the same reason: a
contract only checkable where credentials exist is not checked).

    python3 -m pytest tests/test_telemetry_envelope.py -q    # no env vars needed
"""
import importlib.util
import os
import re

import pytest


# ---------------------------------------------------------------------------
# No database. Override conftest's session-scoped autouse seeding fixture
# (which pulls in db_connection and therefore credentials) with a no-op.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def seed_test_profile():
    """No-op override — this module is filesystem-only."""
    yield {}


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCHEMA_PATH = os.path.join(_REPO_ROOT, "DarwinSQL", "schema.sql")
_ENVELOPE_PATH = os.path.join(_REPO_ROOT, "scripts", "telemetry", "envelope.py")


def _load_envelope_module():
    """Import scripts/telemetry/envelope.py BY PATH.

    Not via `import telemetry.envelope`: DarwinSQL's tests run with DarwinSQL as
    the rootdir and must not depend on the repo root being importable. Loading by
    path keeps the coupling to exactly one thing — the file existing where this
    test says it does — which is itself part of the contract.
    """
    if not os.path.exists(_ENVELOPE_PATH):
        pytest.fail(
            f"{_ENVELOPE_PATH} is missing. It is the ONE declaration of the shared "
            f"telemetry envelope (req #3202); without it the four tables carrying "
            f"those columns have nothing holding them together.")
    spec = importlib.util.spec_from_file_location("darwin_telemetry_envelope",
                                                  _ENVELOPE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _declared_columns(schema_text):
    """{table: {column: normalized_type}} parsed out of schema.sql.

    Types are lowercased and stripped of anything after the closing paren, so
    `CHAR(64)` -> `char(64)` and `BIGINT NULL` -> `bigint` — the same spelling
    `ENVELOPE_COLUMN_TYPES` uses.
    """
    tables, current = {}, None
    type_pattern = (r"INT|BIGINT|SMALLINT|TINYINT|VARCHAR|CHAR|TEXT|TIMESTAMP|"
                    r"DATETIME|DATE|JSON|SET|ENUM|DECIMAL|BOOLEAN")
    for line in schema_text.splitlines():
        stripped = line.strip()
        match = re.match(r"CREATE TABLE (?:IF NOT EXISTS )?`?(\w+)`?", stripped)
        if match:
            current = match.group(1)
            tables[current] = {}
            continue
        if current is None:
            continue
        if stripped.startswith(")"):
            current = None
            continue
        col = re.match(rf"`?(\w+)`?\s+({type_pattern})\s*(\([^)]*\))?", stripped, re.I)
        if not col:
            continue
        name = col.group(1)
        if name.upper() in ("PRIMARY", "UNIQUE", "KEY", "CONSTRAINT", "FOREIGN", "INDEX"):
            continue
        # BIGINT starts with a prefix INT would also match if the alternation
        # were ordered wrongly; assert the longest match won by re-reading the
        # captured text rather than trusting the pattern order.
        base = col.group(2).lower()
        size = (col.group(3) or "").replace(" ", "")
        tables[current][name] = f"{base}{size}"
    return tables


@pytest.fixture(scope="module")
def envelope():
    return _load_envelope_module()


@pytest.fixture(scope="module")
def schema_tables():
    with open(_SCHEMA_PATH) as fh:
        return _declared_columns(fh.read())


def test_every_envelope_table_carries_every_envelope_column(envelope, schema_tables):
    """The core invariant. One record; four tables; identical columns.

    If this fails, the two domains have started measuring different things again
    — which is the exact defect req #3202 was filed against.
    """
    missing = []
    for table in envelope.ENVELOPE_TABLES:
        assert table in schema_tables, f"{table} is not declared in schema.sql"
        for column in envelope.ENVELOPE_COLUMNS:
            if column not in schema_tables[table]:
                missing.append(f"{table}.{column}")
    assert not missing, (
        "These envelope columns are missing from schema.sql:\n  "
        + "\n  ".join(missing)
        + "\n\nEvery table in ENVELOPE_TABLES must carry EVERY column in "
          "ENVELOPE_COLUMNS. Add a migration, or — if the column genuinely does "
          "not belong on all four — the envelope is the wrong home for it.")


def test_every_envelope_column_has_the_same_type_everywhere(envelope, schema_tables):
    """Same name is not enough: same NAME with a different TYPE is worse than a
    different name, because a UNION across the four tables would silently coerce.

    Notably `wall_ms` must be BIGINT on all four — a signed INT of milliseconds
    overflows at ~24.8 days and a paused `swarm_sessions` row parks for longer.
    """
    wrong = []
    for table in envelope.ENVELOPE_TABLES:
        for column, expected in envelope.ENVELOPE_COLUMN_TYPES.items():
            actual = schema_tables.get(table, {}).get(column)
            if actual is None:
                continue        # covered by the test above
            if actual != expected:
                wrong.append(f"{table}.{column}: schema says {actual}, "
                             f"envelope.py declares {expected}")
    assert not wrong, "Envelope type drift:\n  " + "\n  ".join(wrong)


def test_the_shared_context_columns_are_present_everywhere(envelope, schema_tables):
    """model / effort / machine are part of the envelope too — they were simply
    already uniform before req #3202, so the migration did not add them. Asserted
    so a future table joining ENVELOPE_TABLES cannot arrive without them."""
    missing = []
    for table in envelope.ENVELOPE_TABLES:
        for column in envelope.ENVELOPE_SHARED_CONTEXT_COLUMNS:
            if column not in schema_tables.get(table, {}):
                missing.append(f"{table}.{column}")
    assert not missing, (
        "Envelope context columns missing:\n  " + "\n  ".join(missing))


def test_every_envelope_table_declares_its_run_boundaries(envelope, schema_tables):
    """"When did this run happen" is per-table and deliberately NOT renamed:
    `captured_at` / `started_at` / `completed_at` each have live consumers, and
    renaming them to one envelope spelling would break every one for cosmetics.
    The MAPPING is the shared definition instead — so the mapping must be true."""
    bad = []
    for table, (start_col, end_col) in envelope.ENVELOPE_TIME_COLUMNS.items():
        columns = schema_tables.get(table, {})
        if start_col not in columns:
            bad.append(f"{table}: start column {start_col!r} does not exist")
        if end_col is not None and end_col not in columns:
            bad.append(f"{table}: end column {end_col!r} does not exist")
    assert not bad, "ENVELOPE_TIME_COLUMNS is out of date:\n  " + "\n  ".join(bad)


def test_no_envelope_column_is_declared_not_null(envelope):
    """NULL means NOT MEASURED (req #3117's rule), so no envelope column may be
    NOT NULL and none may carry a DEFAULT.

    A DEFAULT 0 would be the failure this rule exists to prevent, wearing a
    different hat: every one of the ~1,900 pre-envelope rows would claim to have
    measured a run that cost nothing, and no aggregate could tell them apart from
    a real zero. There is no backfill and there cannot be one — the transcripts
    those runs were measured from are rotated or deleted.
    """
    with open(_SCHEMA_PATH) as fh:
        schema_text = fh.read()

    offenders = []
    for line in schema_text.splitlines():
        stripped = line.strip()
        match = re.match(r"`?(\w+)`?\s+\S+", stripped)
        if not match or match.group(1) not in envelope.ENVELOPE_COLUMNS:
            continue
        upper = stripped.upper()
        if "NOT NULL" in upper:
            offenders.append(f"NOT NULL: {stripped}")
        if re.search(r"\bDEFAULT\b", upper):
            offenders.append(f"DEFAULT: {stripped}")
    assert not offenders, (
        "Envelope columns must be nullable with no default:\n  "
        + "\n  ".join(offenders))


def test_the_mcp_service_layer_declares_the_same_columns(envelope):
    """darwin-mcp restates the column names in `services/common.py` because the
    daemon deliberately does not import the repo-root script tree. Two lists, so
    they are held together HERE rather than by hope.

    Skipped only if darwin-mcp is not checked out beside DarwinSQL — a legitimate
    single-repo checkout, not a reason to fail.
    """
    common_path = os.path.join(_REPO_ROOT, "darwin-mcp", "services", "common.py")
    if not os.path.exists(common_path):
        pytest.skip("darwin-mcp is not present in this checkout")

    with open(common_path) as fh:
        text = fh.read()
    match = re.search(r"^ENVELOPE_FIELDS\s*=\s*\((.*?)\)", text, re.S | re.M)
    assert match, ("darwin-mcp/services/common.py no longer declares "
                   "ENVELOPE_FIELDS; the service layer and the record have "
                   "nothing holding them together.")
    declared = tuple(re.findall(r"'(\w+)'", match.group(1)))
    assert declared == tuple(envelope.ENVELOPE_COLUMNS), (
        f"darwin-mcp ENVELOPE_FIELDS {declared} != "
        f"envelope.ENVELOPE_COLUMNS {tuple(envelope.ENVELOPE_COLUMNS)}")


def test_the_frontend_reads_every_envelope_column(envelope):
    """The req #3202 acceptance is that the record is USED, not merely stored.

    Darwin's agent-context query names its columns explicitly, so a column added
    to the envelope but not to `defaultFields` is stored, invisible, and looks
    delivered. Skipped if Darwin is not checked out beside DarwinSQL.
    """
    queries_path = os.path.join(_REPO_ROOT, "Darwin", "src", "hooks", "factory",
                                "devopsQueries.js")
    if not os.path.exists(queries_path):
        pytest.skip("Darwin is not present in this checkout")

    with open(queries_path) as fh:
        text = fh.read()
    match = re.search(r"entity:\s*'agent_telemetry_runs',\s*defaultFields:\s*(.*?),\s*\n\s*fieldsInKey",
                      text, re.S)
    assert match, "could not find agent_telemetry_runs defaultFields in devopsQueries.js"
    fields = set(re.findall(r"[\w_]+", match.group(1)))
    missing = [c for c in envelope.ENVELOPE_COLUMNS if c not in fields]
    assert not missing, (
        f"agent_telemetry_runs defaultFields omits envelope columns {missing} — "
        f"they would be stored but never reach the page that renders them.")
