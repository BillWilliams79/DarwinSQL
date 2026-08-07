"""
`seed_pipelines_darwin_dev.sql` must agree with the counts printed inside it. (req #3147)

This module is deliberately FILESYSTEM-ONLY — it opens no database connection and
needs no credentials, because everything it asserts is a property of two files on
disk. That is why it overrides conftest's autouse `seed_test_profile` fixture
below: the fixture must be checkable on any machine, in CI, and inside a
`deployed` swarm worker that has no DB access.

    python3 -m pytest tests/test_seed_pipelines_fixture.py -q     # no env vars needed

WHAT WENT WRONG (the reason this file exists)
---------------------------------------------
`memory/database.md` § Seed data carried a hand-copied row-count summary of the
darwin_dev pipelines fixture: "4 epics, 20 features, 54 requirements, 34 steps,
55 links, 40 dep rows". Five of those six numbers were wrong by 2026-08-01 (only
the epic count survived). They had drifted at least twice — once when the fixture
was re-seeded, once when req #3123 regenerated it with the `requirements.tracking`
flag — and nothing failed either time, so the summary went on reading as
authoritative.

Worse: the requirement filed to fix the drift published its OWN hand-count, and
three of its five numbers were wrong too (41/66/44 against a real 42/68/46). A
naive parse of this file undercounts for two specific reasons, and both are
permanent properties of the fixture rather than accidents:

  * `pipeline_step_deps` is emitted as TWO separate INSERT blocks. The
    reconstructed s0.4 dual-condition gate is kept apart from the rest so its
    provenance cannot be mistaken. Count one block and you lose the other.
  * the string literals are real Darwin prose. Requirement titles carry `;`, `#`,
    `(` and `,`; `pipeline_steps.notes` carries `--` (`--no-hardlinks` appears in
    the notes of two steps). Splitting or comment-stripping without quote
    awareness mis-parses them.

THE CONTRACT
------------
The generator (`scripts/seed_pipelines_darwin_dev.py`) computes its counts from
the rows it is emitting and writes them into the `.sql` it produces. This module
re-derives them from the SQL's own INSERT tuples, with a quote- and comment-aware
parser, and fails on any disagreement. Seven families are covered — a closed
enumeration, matching the table in `memory/database.md` § Seed data:

  1. `-- Source plan:` header — plan rows, distinct requirements, epics, features
  2. `-- ## Id allocation` — the epics / features / pipelines id ranges
  3. `-- ## plan step id -> pipeline_steps.id` — the whole offset map
  4. `-- * multi-req steps ... 1(5), 33(2), ...` — the launch-unit pairs
  5. `-- Epics (N)` / `-- Features (N)` / ... — the per-INSERT block captions
  6. `-- reproduces the plan's own state field for N of M rows` + the exception list
  7. `-- (this plan has N of them)` and the footer `SELECT COUNT(*) ... -- N` crib

So the numbers stay true across a regeneration for free, and a hand-edit that
changes a row count in a file whose header says "do not hand-edit" shows up as a
red test instead of as a silent lie.

It intentionally hard-codes NO expected count. Pinning 42 here would just move the
drift surface into the test suite, which is the mistake being undone.

WHAT THIS DOES NOT CATCH
------------------------
Only the seven count/id families above. Two other kinds of claim in the file are
deliberately outside that boundary, so do not read a green run as covering them:

  * Row CONTENT. A hand-edited `requirement_status`, title, `tracking` flag or
    dep target passes green — and status is exactly what derived step state reads
    (design rule 1).
  * The structural acceptance criteria the header narrates: `req-less step 7`,
    `dual-condition gate step 3`, `cross-epic step 19`, `Flagged as containers in
    this generation: #3083`, and the `machine_fk` remap `(2->74, 3->75)`.

The defence for both is regenerating rather than hand-editing.
"""
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
    """No-op override — test_seed_pipelines_fixture.py is filesystem-only."""
    yield {}


HERE = os.path.dirname(os.path.abspath(__file__))
DARWINSQL_ROOT = os.path.dirname(HERE)
SEED_SQL = os.path.join(DARWINSQL_ROOT, 'scripts', 'seed_pipelines_darwin_dev.sql')

# DarwinSQL is its own git repo but is always checked out INSIDE the DarwinAI
# workspace (see CLAUDE.md § Repository Layout), so the doc it is described in
# sits one level up. A standalone DarwinSQL clone has no sibling `memory/`;
# that case skips rather than fails.
WORKSPACE_ROOT = os.path.dirname(DARWINSQL_ROOT)
DATABASE_MD = os.path.join(WORKSPACE_ROOT, 'memory', 'database.md')


# ---------------------------------------------------------------------------
# SQL parsing — quote-aware and comment-aware, because this fixture defeats
# every shortcut (see the module docstring).
#
# Both blanking passes below preserve LENGTH and newlines, replacing removed
# characters with spaces rather than deleting them. That keeps every offset in
# the blanked text identical to the same offset in the raw file, which is what
# lets a comment caption be tied POSITIONALLY to the INSERT block beneath it
# instead of by a fragile ordinal.
# ---------------------------------------------------------------------------

def _blank(text, start, end):
    """Replace text[start:end] with spaces, preserving newlines and length."""
    return ''.join(' ' if c != '\n' else '\n' for c in text[start:end])


def _blank_comments(sql):
    """Blank `-- ...`, `# ...` and `/* ... */`, never touching string literals.

    MySQL accepts all three comment forms, and this fixture is exactly the file
    where a naive stripper goes wrong: `--` and `#` both occur inside literals.
    A quote closed by the doubled form (`don''t`, the only escape the generator
    emits) reopens on the second quote, so quote parity is preserved without a
    special case; the backslash branch covers MySQL's other escape form if the
    generator ever switches to it.
    """
    out = []
    i, n = 0, len(sql)
    quote = None
    while i < n:
        ch = sql[i]
        if quote:
            if ch == '\\':                       # escaped char inside a literal
                out.append(sql[i:i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
            out.append(ch)
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if sql.startswith('--', i) or ch == '#':
            nl = sql.find('\n', i)
            end = n if nl < 0 else nl            # keep the newline itself
            out.append(_blank(sql, i, end))
            i = end
            continue
        if sql.startswith('/*', i):
            close = sql.find('*/', i + 2)
            end = n if close < 0 else close + 2
            out.append(_blank(sql, i, end))
            i = end
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _blank_literals(text):
    """Blank the CONTENTS of every string literal, keeping the quotes and length.

    Used by the production-reference guard: a requirement legitimately titled
    "Junction scoping on darwin.pipeline_step_deps" must not be mistaken for a
    schema-qualified table reference.
    """
    out = []
    i, n = 0, len(text)
    quote = None
    while i < n:
        ch = text[i]
        if quote:
            if ch == '\\':
                out.append(_blank(text, i, min(i + 2, n)))
                i += 2
                continue
            if ch == quote:
                quote = None
                out.append(ch)
            else:
                out.append(' ' if ch != '\n' else '\n')
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        out.append(ch)
        i += 1
    return ''.join(out)


# A VALUES list ends at the statement `;` or at an upsert clause, whichever comes
# first. Without the second stop, a parenthesis inside `ON DUPLICATE KEY UPDATE`
# (e.g. `title = COALESCE(new.title, title)`) would be counted as another row and
# fail the header assertion with a message blaming the header.
_VALUES_END = re.compile(r'\bON\s+DUPLICATE\b', re.I)

_INSERT_RE = re.compile(
    r'INSERT\s+(?:IGNORE\s+)?INTO\s+([`\w.]+)\s*\(([^)]*)\)\s*VALUES', re.I
)


def _top_level_tuples(segment):
    """Yield the text inside each top-level `( ... )` of one VALUES list.

    Quote-aware, so `;`, `#`, `(` and `,` inside a title are inert.
    """
    depth = 0
    quote = None
    start = None
    i, n = 0, len(segment)
    while i < n:
        ch = segment[i]
        if quote:
            if ch == '\\':
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == '(':
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                yield segment[start:i]
        elif depth == 0:
            if ch == ';':
                return
            if (ch in 'oO') and _VALUES_END.match(segment, i):
                return
        i += 1


def _split_top_level_commas(text):
    """Split a tuple's (or a column list's) fields on top-level commas only."""
    fields = []
    depth = 0
    quote = None
    buf = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == '\\':
                i += 1
                if i < n:
                    buf.append(text[i])
                i += 1
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            fields.append(''.join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    fields.append(''.join(buf).strip())
    return fields


class Block:
    """One `INSERT INTO <table> (<columns>) VALUES ...` statement."""

    def __init__(self, table, columns, tuples, start):
        self.table = table
        self.columns = columns
        self.tuples = tuples
        self.start = start

    def column(self, tuple_text, name):
        """Field value by COLUMN NAME, so a reorder cannot silently shift an index."""
        assert name in self.columns, (
            f"`{self.table}` has no column `{name}`; it has {self.columns}"
        )
        fields = _split_top_level_commas(tuple_text)
        assert len(fields) == len(self.columns), (
            f"`{self.table}` row has {len(fields)} fields for "
            f"{len(self.columns)} columns: {tuple_text[:80]!r}"
        )
        return fields[self.columns.index(name)]


class _Rows(dict):
    """Row lookup that explains a miss instead of raising a bare KeyError."""

    def __missing__(self, table):
        raise AssertionError(
            f"no INSERT rows parsed for `{table}` — either the fixture stopped "
            f"inserting it, or its target is schema-qualified (see "
            f"test_fixture_targets_darwin_dev_and_never_production). Parsed: "
            f"{sorted(self)}"
        )


@pytest.fixture(scope="module")
def seed_sql():
    assert os.path.isfile(SEED_SQL), f"fixture SQL missing: {SEED_SQL}"
    with open(SEED_SQL, encoding='utf-8') as handle:
        return handle.read()


@pytest.fixture(scope="module")
def blocks(seed_sql):
    """[Block, ...] in file order. `start` is an offset into the RAW file."""
    body = _blank_comments(seed_sql)
    assert len(body) == len(seed_sql), "comment blanking must preserve offsets"
    found = [
        Block(
            table=match.group(1).replace('`', ''),
            columns=[c.strip().strip('`') for c in _split_top_level_commas(match.group(2))],
            tuples=list(_top_level_tuples(body[match.end():])),
            start=match.start(),
        )
        for match in _INSERT_RE.finditer(body)
    ]
    assert found, "no INSERT ... VALUES blocks parsed — the fixture or the parser is broken"
    return found


@pytest.fixture(scope="module")
def rows(blocks):
    """{table: [tuple_text, ...]} accumulated across ALL blocks for that table.

    Accumulating across blocks is the point: `pipeline_step_deps` is emitted
    twice and a per-block count silently loses the dual-condition gate row.
    """
    collected = _Rows()
    for block in blocks:
        collected.setdefault(block.table, []).extend(block.tuples)
    return collected


@pytest.fixture(scope="module")
def by_table(blocks):
    """{table: [Block, ...]} — for the column-name lookups."""
    collected = _Rows()
    for block in blocks:
        collected.setdefault(block.table, []).append(block)
    return collected


def _ints(block, name):
    return [int(block.column(t, name)) for t in block.tuples]


# ---------------------------------------------------------------------------
# 1. The header block
# ---------------------------------------------------------------------------

def test_header_source_plan_counts_match_the_rows(seed_sql, rows):
    """`-- Source plan: ...` must describe the rows the same file goes on to insert."""
    match = re.search(
        r'--\s*Source plan:\s*requirement\s*#(\d+),\s*(\d+)\s*rows,\s*'
        r'(\d+)\s*distinct requirements,\s*\n'
        r'--\s*(\d+)\s*epics,\s*(\d+)\s*features\.',
        seed_sql,
    )
    assert match, "header `-- Source plan:` block not found or reformatted"

    _req_id, steps, requirements, epics, features = (int(g) for g in match.groups())

    for label, claimed, table in (
        ('plan rows', steps, 'pipeline_steps'),
        ('distinct requirements', requirements, 'requirements'),
        ('epics', epics, 'epics'),
        ('features', features, 'features'),
    ):
        assert claimed == len(rows[table]), (
            f"header says {claimed} {label}, file inserts {len(rows[table])} "
            f"{table} rows"
        )


def test_header_names_the_generating_plan_requirement(seed_sql):
    """The provenance claim in memory/database.md must be the one the file makes."""
    match = re.search(r'--\s*Source plan:\s*requirement\s*#(\d+),', seed_sql)
    assert match, "header `-- Source plan:` block not found"
    assert int(match.group(1)) == 3083, (
        "the fixture's source plan changed; memory/database.md § Seed data names "
        "req #3083 and must be updated with it"
    )


def test_header_states_production_carries_the_live_plan(seed_sql):
    """Req #3147: production `darwin` is NOT empty — the live-plan cutover landed.

    memory/database.md § Seed data sends readers here for the authoritative
    counts, so the header must not repeat the claim the doc was just corrected
    for. This is asserted POSITIVELY — the header must state the current truth —
    because the false version can be reworded indefinitely while the true one
    cannot be stated by accident. Rewording the generator's text is therefore
    expected to fail this test; update both together.

    This DOES hardcode prose, which is the move this module refuses for numbers
    (see the closing note in the module docstring). The trade is deliberate and
    the asymmetry is the reason: a count is derived data, so pinning it here just
    relocates the drift surface, whereas this sentence is load-bearing safety
    text with no derivation to check it against. A test that fails on a reword is
    the cost of having any check at all, and the message below says what to do.
    """
    end = seed_sql.find('SET NAMES')
    assert end > 0, "`SET NAMES` not found — cannot delimit the header comment"
    header = ' '.join(
        re.sub(r'^\s*--\s?', '', line) for line in seed_sql[:end].split('\n')
    ).lower()

    for phrase in ('never apply this file to production', 'cutover has since landed'):
        assert phrase in header, (
            f"header no longer states that production carries the live plan "
            f"(missing {phrase!r}). Production `darwin` is NOT empty: the "
            f"cutover landed and it holds the real plan. Fix the text in "
            f"seed_pipelines_darwin_dev.py and REGENERATE — do not hand-edit "
            f"the .sql — then update this assertion to match."
        )


# ---------------------------------------------------------------------------
# 2. The id allocation table
# ---------------------------------------------------------------------------

def test_id_allocation_ranges_match_the_rows(seed_sql, by_table):
    """`--   features   9001..9023` must be the range the file actually inserts."""
    for table in ('epics', 'features'):
        match = re.search(rf'--\s+{table}\s+(\d+)\.\.(\d+)\s*$', seed_sql, re.M)
        assert match, f"id-allocation line for `{table}` not found or reformatted"
        low, high = int(match.group(1)), int(match.group(2))

        ids = sorted(i for block in by_table[table] for i in _ints(block, 'id'))
        assert (ids[0], ids[-1]) == (low, high), (
            f"id allocation claims {table} {low}..{high}, file inserts "
            f"{ids[0]}..{ids[-1]}"
        )
        assert ids == list(range(low, high + 1)), (
            f"{table} ids are not the contiguous range {low}..{high} the id "
            f"allocation block claims: {ids}"
        )

    match = re.search(r'--\s+pipelines\s+(\d+)\s*$', seed_sql, re.M)
    assert match, "id-allocation line for `pipelines` not found or reformatted"
    ids = [i for block in by_table['pipelines'] for i in _ints(block, 'id')]
    assert ids == [int(match.group(1))], (
        f"id allocation claims pipelines {match.group(1)}, file inserts {ids}"
    )


# ---------------------------------------------------------------------------
# 3. The plan-step -> pipeline_steps.id map
# ---------------------------------------------------------------------------

def test_plan_step_id_map_is_complete_and_correctly_offset(seed_sql, by_table):
    """`--   1->9001, 2->9002, ...` must cover every step, at the stated offset."""
    offset_match = re.search(r'--\s*OFFSET BY (\d+)\.', seed_sql)
    assert offset_match, "the `-- OFFSET BY N.` statement was not found"
    offset = int(offset_match.group(1))

    section = re.search(
        r'## plan step id -> pipeline_steps\.id(.*?)\n--\s*##', seed_sql, re.S
    )
    assert section, "the `## plan step id -> pipeline_steps.id` section was not found"
    pairs = [(int(a), int(b)) for a, b in re.findall(r'(\d+)->(\d+)', section.group(1))]
    assert pairs, "the step-id map lists no `N->M` pairs"
    # Dict-building would collapse a repeated entry silently, and a duplicate is
    # how a map stays the right LENGTH while losing a step.
    sources = [a for a, _ in pairs]
    assert len(sources) == len(set(sources)), (
        f"the step-id map lists a plan step more than once: "
        f"{sorted({a for a in sources if sources.count(a) > 1})}"
    )
    mapped = dict(pairs)

    wrong = {a: b for a, b in mapped.items() if b != a + offset}
    assert not wrong, f"step-id map entries not offset by {offset}: {wrong}"

    actual = {i for block in by_table['pipeline_steps'] for i in _ints(block, 'id')}
    assert set(mapped.values()) == actual, (
        f"step-id map covers {len(mapped)} steps but the file inserts "
        f"{len(actual)}; missing from the map: "
        f"{sorted(actual - set(mapped.values()))}; in the map but not inserted: "
        f"{sorted(set(mapped.values()) - actual)}"
    )


# ---------------------------------------------------------------------------
# 4. The multi-requirement launch units
# ---------------------------------------------------------------------------

def test_multi_req_step_pairs_match_the_links(seed_sql, by_table):
    """`--   1(5), 33(2), 12(7), ...` — the launch units of >1 requirement (rule 2)."""
    section = re.search(
        r'multi-req steps(.*?)\.\s*\n--\s*\*', seed_sql, re.S
    )
    assert section, "the `multi-req steps` acceptance block was not found"
    claimed = {int(s): int(c) for s, c in re.findall(r'(\d+)\((\d+)\)', section.group(1))}
    assert claimed, "the multi-req block lists no `step(count)` pairs"

    offset_match = re.search(r'--\s*OFFSET BY (\d+)\.', seed_sql)
    assert offset_match, "the `-- OFFSET BY N.` statement was not found"
    offset = int(offset_match.group(1))

    per_step = {}
    for block in by_table['pipeline_step_requirements']:
        for tup in block.tuples:
            step = int(block.column(tup, 'step_fk')) - offset
            per_step[step] = per_step.get(step, 0) + 1
    actual = {step: n for step, n in per_step.items() if n > 1}

    assert claimed == actual, (
        f"multi-req pairs claim {sorted(claimed.items())}, links give "
        f"{sorted(actual.items())}"
    )


# ---------------------------------------------------------------------------
# 5. The per-block captions
# ---------------------------------------------------------------------------

# (caption regex, table). Each caption is tied POSITIONALLY to the next INSERT
# block for that table — never to an ordinal — so reordering the file cannot
# silently re-point a caption at the wrong block.
BLOCK_CAPTIONS = (
    (r'--\s*Epics \((\d+)\)', 'epics'),
    (r'--\s*Features \((\d+)\)', 'features'),
    (r'--\s*Requirements \((\d+)\)', 'requirements'),
    (r'--\s*Steps \((\d+)\)', 'pipeline_steps'),
    (r'--\s*Step -> requirement links \((\d+)\)', 'pipeline_step_requirements'),
    # The plan-derived edges; the reconstructed dual-condition gate follows in
    # its own block, below this caption's block, and is not counted here.
    (r'--\s*Dependency edges from the plan \((\d+)\)', 'pipeline_step_deps'),
)


def test_block_captions_match_the_rows_beneath_them(seed_sql, blocks):
    """`-- Epics (4)`-style captions are the first counts a reader sees. Pin them."""
    for pattern, table in BLOCK_CAPTIONS:
        found = list(re.finditer(pattern, seed_sql))
        assert len(found) == 1, (
            f"caption {pattern!r} matched {len(found)} times; it must identify "
            f"exactly one block"
        )
        caption = found[0]
        below = [b for b in blocks if b.table == table and b.start > caption.end()]
        assert below, f"no `{table}` INSERT block follows the caption {pattern!r}"
        actual = len(below[0].tuples)
        assert int(caption.group(1)) == actual, (
            f"caption claims {caption.group(1)} for the {table} block beneath it, "
            f"found {actual}"
        )


# ---------------------------------------------------------------------------
# 6. The derivation-parity tally
# ---------------------------------------------------------------------------

def test_derivation_parity_tally_matches_its_own_exception_list(seed_sql, rows, by_table):
    """`reproduces ... for 37 of 42 rows` + 5 listed exceptions must total 42.

    Full parity is a LEGITIMATE end state, not a failure: the generator has an
    explicit zero-divergence branch that emits "No divergences this generation"
    and no `-- step N ...` lines at all. Asserting an exception list
    unconditionally would turn a correct regeneration red, which is the inverse
    of the generator's own discipline ("EVERY claim below is gated on having
    actually found the thing it claims"). So the two cases are checked
    separately, and the zero case is pinned rather than merely tolerated.
    """
    match = re.search(
        r"reproduces the plan's own `state` field for (\d+)\s*\n--\s*of (\d+) rows",
        seed_sql,
    )
    assert match, "the derivation-parity sentence was not found or was reformatted"
    matched, total = int(match.group(1)), int(match.group(2))

    assert total == len(rows['pipeline_steps']), (
        f"parity tally is out of {total} rows, file inserts "
        f"{len(rows['pipeline_steps'])} pipeline_steps"
    )

    exceptions = re.findall(
        r'--\s+step (\d+)\s+plan says \w+\s+derivation says \w+', seed_sql
    )
    assert matched + len(exceptions) == total, (
        f"parity tally says {matched} of {total} match, but {len(exceptions)} "
        f"exceptions are listed ({matched} + {len(exceptions)} != {total})"
    )

    if matched == total:
        assert 'No divergences this generation' in seed_sql, (
            "parity is complete but the file does not say so; the generator's "
            "zero-divergence branch emits 'No divergences this generation'"
        )
        return

    assert exceptions, (
        f"parity tally says {matched} of {total}, so {total - matched} exceptions "
        f"must be listed, but the exception list is empty"
    )
    assert len(exceptions) == len(set(exceptions)), (
        f"the parity exception list names a step twice: {exceptions}"
    )

    # The tally itself is not re-derivable from this file — it needs the plan's
    # stored `state`, which the fixture deliberately does not carry. The step ids
    # ARE, so at least hold the list to naming steps that exist.
    offset_match = re.search(r'--\s*OFFSET BY (\d+)\.', seed_sql)
    assert offset_match, "the `-- OFFSET BY N.` statement was not found"
    offset = int(offset_match.group(1))
    step_ids = {i for block in by_table['pipeline_steps'] for i in _ints(block, 'id')}
    bogus = sorted({int(s) for s in exceptions if int(s) + offset not in step_ids})
    assert not bogus, (
        f"parity exception list names steps the file never inserts: {bogus}"
    )


# ---------------------------------------------------------------------------
# 7. The teardown note and the footer crib
# ---------------------------------------------------------------------------

def test_step_to_step_edge_count_in_the_teardown_note_is_right(seed_sql, by_table):
    """The teardown rationale says how many step-to-step edges the plan has."""
    match = re.search(r'--\s*\(this plan has (\d+) of them\)', seed_sql)
    assert match, "teardown note's step-to-step edge count not found or reformatted"
    # One dep row = one condition: a step-to-step edge has dep_step_fk set, a
    # wall-clock gate has it NULL. Resolved by COLUMN NAME, not by index.
    edges = sum(
        1
        for block in by_table['pipeline_step_deps']
        for tup in block.tuples
        if block.column(tup, 'dep_step_fk').strip().upper() != 'NULL'
    )
    assert int(match.group(1)) == edges, (
        f"teardown note claims {match.group(1)} step-to-step edges, file inserts "
        f"{edges} dep rows with a non-NULL dep_step_fk"
    )


FOOTER_TABLES = ('pipeline_steps', 'pipeline_step_requirements', 'pipeline_step_deps')


def test_footer_verification_counts_match_the_rows(seed_sql, rows):
    """The `-- SELECT COUNT(*) ... -- N` crib must match what the file inserts."""
    claimed = re.findall(
        r'--\s*SELECT COUNT\(\*\)\s+FROM\s+(\w+)[^\n]*?;\s*--\s*(\d+)', seed_sql
    )
    tables = [table for table, _ in claimed]
    assert len(tables) == len(set(tables)), (
        f"footer verification block names a table more than once: {tables}"
    )
    assert set(tables) == set(FOOTER_TABLES), (
        f"footer verification block covers {sorted(tables)}, expected "
        f"{sorted(FOOTER_TABLES)}"
    )
    for table, count in claimed:
        assert int(count) == len(rows[table]), (
            f"footer claims {count} rows for {table}, file inserts {len(rows[table])}"
        )


def test_dep_rows_span_more_than_one_insert_block(blocks):
    """Pin the trap: counting a single block undercounts pipeline_step_deps."""
    dep_blocks = [b for b in blocks if b.table == 'pipeline_step_deps']
    assert len(dep_blocks) >= 2, (
        "the reconstructed dual-condition gate is expected in its own INSERT "
        "block; if that changed, this module's docstring and the note in "
        "memory/database.md § Seed data are stale"
    )


# ---------------------------------------------------------------------------
# Other id-allocation claims memory/database.md § Seed data makes
# ---------------------------------------------------------------------------

def test_step_ids_are_unique_and_in_the_9000_band(by_table):
    """`pipeline_steps.id` is 9000 + the plan step id — so 9001..9999, no repeats."""
    ids = [i for block in by_table['pipeline_steps'] for i in _ints(block, 'id')]
    assert len(ids) == len(set(ids)), "duplicate pipeline_steps.id in the fixture"
    assert all(9000 < i < 10000 for i in ids), (
        f"pipeline_steps.id outside the 9000 fixture band: "
        f"{sorted(i for i in ids if not 9000 < i < 10000)}"
    )


def test_fixture_owns_its_project_and_category(by_table):
    """The fixture creates project/category 9001 rather than borrowing production ids."""
    for table in ('projects', 'categories'):
        ids = [i for block in by_table[table] for i in _ints(block, 'id')]
        assert ids == [9001], f"{table} fixture row ids are {ids}, expected [9001]"


# ---------------------------------------------------------------------------
# darwin_dev only
# ---------------------------------------------------------------------------

def test_fixture_targets_darwin_dev_and_never_production(seed_sql, blocks):
    """*** darwin_dev ONLY. *** Production `darwin` must never be a target here.

    This used to assert a `USE darwin_dev;` statement was PRESENT. Req #3196
    reversed that: a `USE` re-points whoever executes it, so it protects the
    fixture only until somebody types the other database name, and the same
    mechanism aimed at production is what wrote three rows there on 2026-08-01.
    The target is now declared as a CONSTRAINT the caller is checked against —
    `-- darwin:targets = darwin_dev`, enforced by DarwinSQL/scripts/db_guard.py
    before a connection is opened, with a list that omits `darwin` acting as an
    absolute production ban. `test_sql_targets.py` pins the absence of `USE`
    across the whole corpus.
    """
    body = _blank_comments(seed_sql)

    assert re.search(r'^\s*--\s*darwin:targets\s*=\s*darwin_dev\s*$', seed_sql, re.M), (
        "no `-- darwin:targets = darwin_dev` declaration — the target database "
        "must be declared, and this fixture is darwin_dev ONLY"
    )
    assert not re.findall(r'^\s*USE\s+`?(\w+)`?\s*;', body, re.I | re.M), (
        "the fixture carries a `USE <db>;` statement, which overrides the "
        "caller's target (req #3196)"
    )

    # A schema-qualified `darwin.epics` (or ``darwin`.`epics``) would reach
    # production regardless of the declared target. Block table names are
    # backtick-stripped.
    qualified = sorted({b.table for b in blocks if '.' in b.table})
    assert not qualified, (
        f"schema-qualified INSERT targets bypass the darwin_dev target "
        f"declaration: {qualified}"
    )
    # Literals are blanked first: a requirement legitimately titled "...scoping on
    # darwin.pipeline_step_deps" is prose, not a table reference.
    stray = re.findall(r'`?\bdarwin`?\s*\.\s*`?\w+', _blank_literals(body))
    assert not stray, f"production-qualified references in the fixture body: {stray}"


# ---------------------------------------------------------------------------
# The doc section itself
# ---------------------------------------------------------------------------

PATH_TOKEN = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:sql|py|md|js)\b')


def _seed_data_section():
    if not os.path.isfile(DATABASE_MD):
        pytest.skip(f"standalone DarwinSQL checkout — no {DATABASE_MD}")
    with open(DATABASE_MD, encoding='utf-8') as handle:
        text = handle.read()
    match = re.search(r'^### Seed data$(.*?)(?=^#{1,3} )', text, re.S | re.M)
    assert match, "memory/database.md has no `### Seed data` section"
    return match.group(1)


def test_every_path_named_in_the_doc_section_exists():
    """Req #3147 acceptance: no path named in § Seed data is absent from the repo.

    The requirement was filed partly because the section named three scripts
    believed missing. They are present; this asserts it instead of
    re-investigating it.
    """
    section = _seed_data_section()
    # Only repo-relative paths — a bare `.sql` or `load_sql.py` written inline as
    # prose carries no directory and is not a path claim.
    paths = sorted({t.group(0) for t in PATH_TOKEN.finditer(section) if '/' in t.group(0)})
    assert paths, "§ Seed data names no file paths at all — did the section move?"

    missing = [p for p in paths if not os.path.exists(os.path.join(WORKSPACE_ROOT, p))]
    assert not missing, f"§ Seed data names paths that do not exist: {missing}"


def test_doc_section_points_at_this_module():
    """The section must name the test that keeps its claims honest."""
    section = _seed_data_section()
    assert 'DarwinSQL/tests/test_seed_pipelines_fixture.py' in section, (
        "§ Seed data no longer names the module that verifies the fixture's counts"
    )
