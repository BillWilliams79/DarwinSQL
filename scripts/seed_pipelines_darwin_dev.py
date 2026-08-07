#!/usr/bin/env python3
"""Generate the darwin_dev pipelines fixture from the LIVE req #3083 PLAN-JSON.

Req #3111, deliverable 3 of req #3080: translate the Substrate Rebuild plan — the
acceptance fixture for the Swarm Orchestration feature — into INSERT-ready SQL for
the tables migration 076 creates.

    python3 DarwinSQL/scripts/seed_pipelines_darwin_dev.py            # -> seed_pipelines_darwin_dev.sql
    python3 DarwinSQL/scripts/seed_pipelines_darwin_dev.py --stdout   # print instead

Run from the session/worktree root (the MCP wrapper path is relative to it). The
plan is fetched LIVE every time rather than vendored: req #3119 (plan step 42)
re-seeds darwin_dev from whatever the plan says at that point, and a vendored copy
would quietly go stale between now and then.

darwin_dev ONLY. NEVER apply the output to production `darwin`. It used to be safe
to say `darwin` was simply empty; the Primary's live-plan cutover has since landed
and production carries the real plan, so this fixture's 9001-band rows would sit
alongside live ones rather than in an empty table (req #3147).
"""
import json
import os
import re
import subprocess
import sys

REQ_ID = 3083
CREATOR = '37df7531-000d-4470-8be4-1792d8261f69'          # Bill W

# The fixture owns its project + category rather than borrowing production ids.
# The plan's requirements carry PRODUCTION category_fk values (1, 1052, ...) and
# categories.category_fk is NOT NULL with ON DELETE RESTRICT — the identical
# cross-database hazard MACHINE_MAP exists for. Borrowing them happens to work on
# today's darwin_dev only because the ids coincide; on a darwin_dev rebuilt from
# recreate_darwin_dev.sql (categories empty) the requirements INSERT would die
# with errno 1452 AFTER the teardown had already dropped the previous fixture.
# Owning the rows removes the assumption entirely. They are created idempotently
# and deliberately NOT torn down: the upserted requirements keep pointing at the
# category, and categories is RESTRICT.
FIXTURE_PROJECT = 9001
FIXTURE_CATEGORY = 9001

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'seed_pipelines_darwin_dev.sql')

# Fixture id allocation. Explicit ids (not AUTO_INCREMENT) so the file is
# idempotent, re-runnable, and its teardown can be scoped precisely.
EPIC_BASE = 9000        # epics            9001..9004
FEATURE_BASE = 9000     # features         9001..90NN
PIPELINE_ID = 9001      # pipelines        9001

# pipeline_steps.id = STEP_BASE + the plan's step id. NOT the bare step id: those
# start at 1, so a fixture load would leave AUTO_INCREMENT sitting just above the
# plan's highest step, and the next step created organically through the app would
# take an id the plan claims the moment it grows — a 1062 mid-load, after teardown.
# Offsetting into the same 9000 band as the other fixture rows keeps the mapping
# trivially readable (plan step 12 -> 9012) and collision-free.
STEP_BASE = 9000

# Production machine id -> darwin_dev machine id. The plan's requirements carry
# production machine_fk values; darwin_dev has its own machines table with
# different ids, and the FK is RESTRICT, so an unmapped value would fail the load.
MACHINE_MAP = {2: 74, 3: 75}    # Mac Mini -> Mac mini, MCHP Windows -> WSL box

# The one epic membership the plan states in prose rather than in a column.
# Plan step 19 batches #3080/#3083 (Swarm Orchestration Feature) together with
# #3105 in ONE swarm-start and says so explicitly: "cross-epic per rule 10".
# Design rule 10 exists for exactly this shape — a launch unit that spans epics —
# and the fixture cannot demonstrate the rule unless one requirement actually
# sits under a different epic than its step's dominant label. #3105 (swarm-complete
# takes the RDS snapshot without asking) is substrate doctrine, so it is filed
# under the Swarm Substrate Rebuild epic via a feature that exists for it.
CROSS_EPIC = {
    3105: ('Swarm Doctrine', 'Swarm Substrate Rebuild'),
}

# The s0.4 dual-condition gate (req #3080, plan stage 0): "#3050 session completed
# AND 2h time gate 06:31:38 PDT — DUAL-condition gate, two independent wait
# mechanisms". The live PLAN-JSON carries no T: tokens — the 2026-07-25
# normalization that renumbered 0/2a/Wx/Px ids dropped the wall-clock condition
# along with the stage numbering. It is RECONSTRUCTED here, on the step that
# actually waited on it: step 3 (#3072, the first substrate surgery) already gates
# on step 1 (the drain, which is where #3050 landed), so adding the wall-clock row
# gives step 3 two dep rows of different kinds — a genuine dual-condition gate,
# which is what the acceptance criterion asks the schema to prove it can hold.
# Flagged rather than silently blended: this row is the ONLY dep in the fixture
# not present in the live plan.
RECONSTRUCTED_TIME_GATE = ('3', '2026-07-24 06:31:38')

# Step 7 links no requirements at all ("record the all-passing regression
# baseline"), so it has nothing to derive state from — the single case
# pipeline_steps.completed_at exists for. Stamp from baseline_2c.recorded.
#
# A req-less step NOT listed here loads with completed_at NULL and derives
# Scheduled forever, so `main` names any such step in the generated header rather
# than letting it pass silently — the plan can grow one at any time.
MANUAL_COMPLETION = {'7': '2026-07-26 01:30:00'}

# Requirement statuses that count as finished when deriving a step's state
# (design rule 1). Used only to REPORT the fixture's derived-vs-stored parity in
# the header — nothing here is written to the database.
TERMINAL_STATUSES = ('met', 'deferred', 'wontfix')


def is_tracking(requirement_row):
    """True when a live requirement row carries the req #3123 CONTAINER flag.

    The gateway returns TINYINT as an int; a JSON round trip can present the same
    value as True or "1". An absent column reads as False — a database that has
    not taken migration 20260731124830 yet has no containers, which `main` then
    turns into a loud abort rather than a quiet wrong fixture.
    """
    value = (requirement_row or {}).get('tracking')
    if value is None or value == '':
        return False
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return False


def step_id(plan_step):
    """plan step id -> pipeline_steps.id."""
    return STEP_BASE + int(plan_step)


def steps_phrase(step_ids):
    """"step 7" / "steps 1, 12, 13" — a readable list for the header prose."""
    if not step_ids:
        return ''
    return '%s %s' % ('step' if len(step_ids) == 1 else 'steps', ', '.join(step_ids))


def wrap_comment(text, width=52):
    """Greedy word-wrap for a header comment body. The plan grows, so any line
    built from its contents must be able to run past one line without the
    generated SQL developing a 300-character comment."""
    lines, current = [], ''
    for word in text.split():
        candidate = word if not current else current + ' ' + word
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def derived_state(row, statuses, tracking_ids=()):
    """Design rule 1, applied to one plan row.

    Mirrors the RULES in `pipelineModel.js::deriveStepState`, translated to the
    plan's vocabulary (the engine says `running`; the plan's stored `state` field
    says `active`, and this function exists only to compare against that field).

    `statuses` maps requirement id -> requirement_status. Requirements that do
    not resolve are DROPPED, matching the engine's `.filter(Boolean)` — so a step
    whose only link is unresolvable falls through to the req-less branch rather
    than reporting Scheduled. A req-less step has nothing to derive from; it is
    Complete exactly when it carries a manual completion stamp.

    `tracking_ids` are CONTAINERS (req #3123, `requirements.tracking`) and are
    subtracted BEFORE the empty check, exactly as the engine does it — so a step
    whose links are all containers lands in the req-less branch and derives from
    its manual stamp, never Running. The subtraction has to happen here too, or
    this generator's header would report a divergence the shipped engine no
    longer produces.
    """
    exempt = set(tracking_ids)
    linked = [statuses.get(rid) for rid in row['reqs'] if rid not in exempt]
    linked = [s for s in linked if s]
    if not linked:
        return 'done' if row['step'] in MANUAL_COMPLETION else 'pending'
    if any(s == 'development' for s in linked):
        return 'active'
    if all(s in TERMINAL_STATUSES for s in linked):
        return 'done'
    return 'pending'


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def mcp_read(uri):
    out = sh('bash', 'scripts/mcp/darwin-read.sh', uri)
    return json.loads(out.splitlines()[0])


def q(value):
    """SQL literal for a Python value."""
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        # isinstance(True, int) is True, so bools must be caught FIRST or they
        # emit a bare `True`/`False`, which MySQL rejects.
        return '1' if value else '0'
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace('\\', '\\\\').replace("'", "''") + "'"


def short_title(summary, limit=256):
    """A <=256-char label for pipeline_steps.title.

    Plan summaries routinely exceed VARCHAR(256) — several run past 400 chars of
    evidence and disposition. The full text is preserved verbatim in
    pipeline_steps.notes; this is the display label, cut at a word boundary so it
    never ends mid-token.
    """
    text = ' '.join(summary.split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    if ' ' in cut:
        cut = cut[:cut.rindex(' ')]
    return cut + '…'


def main():
    plan_row = mcp_read(f'darwin://requirements/{REQ_ID}')
    match = re.search(r'<!--PLAN-JSON\n(.*?)\nPLAN-JSON-->', plan_row['description'], re.S)
    if not match:
        raise SystemExit('PLAN-JSON block not found in requirement #%d' % REQ_ID)
    plan = json.loads(match.group(1))
    rows = plan['rows']

    # ABORT on a truncated read rather than generating from it. Every list read is
    # enforced against a 1 MB payload budget (req #3078) and truncates with a
    # visible `{"_truncated": ...}` marker instead of silently — but a marker is
    # only useful if someone looks. Nothing downstream can catch a bad generation
    # here: a requirement lost to truncation would take the `'authoring'` fallback
    # below, and the fixture would LOAD CLEAN and derive the wrong step state.
    # Same guard the two swarm backfill scripts carry.
    requirement_rows = mcp_read('darwin://requirements')
    truncated = [r for r in requirement_rows if isinstance(r, dict) and '_truncated' in r]
    if truncated:
        raise SystemExit(
            'darwin://requirements came back TRUNCATED (%s) — refusing to generate a '
            'fixture from a partial requirements read. Read the requirements in '
            'bounded slices, or narrow the projection, and re-run.' % truncated[0]['_truncated'])
    live = {r['id']: r for r in requirement_rows if isinstance(r, dict) and 'id' in r}

    # ---- epics: first-appearance order in the plan ----------------------
    epic_names = []
    for row in rows:
        if row['epic'] not in epic_names:
            epic_names.append(row['epic'])
    for _, epic in CROSS_EPIC.values():
        if epic not in epic_names:
            epic_names.append(epic)
    epic_id = {name: EPIC_BASE + i + 1 for i, name in enumerate(epic_names)}

    # ---- features: (feature label, epic) pairs, first-appearance order ---
    feature_pairs = []
    for row in rows:
        pair = (row['feature'], row['epic'])
        if pair not in feature_pairs:
            feature_pairs.append(pair)
    for pair in CROSS_EPIC.values():
        if pair not in feature_pairs:
            feature_pairs.append(pair)
    feature_id = {pair: FEATURE_BASE + i + 1 for i, pair in enumerate(feature_pairs)}

    # ---- requirement -> feature ------------------------------------------
    req_feature = {}
    for row in rows:
        for rid in row['reqs']:
            req_feature.setdefault(rid, (row['feature'], row['epic']))
    req_feature.update(CROSS_EPIC)
    req_ids = sorted(req_feature)

    # ---- shape facts the header REPORTS ---------------------------------
    # Computed, never spelled out in prose: the plan grows, and a header that
    # names "steps 1, 12, 13, 19, 33" or "33 of 34 rows" from a previous
    # generation is a generated file lying about its own contents.
    by_step = {row['step']: row for row in rows}
    # `.strip()` matters: a whitespace-only title is falsy to the fallback below
    # but TRUTHY to a bare `not row.get('title')`, so it would load an empty step
    # name with nothing in the header naming it — the one case this warning is
    # for.
    untitled_steps = [row['step'] for row in rows if not (row.get('title') or '').strip()]
    reqless_steps = [row['step'] for row in rows if not row['reqs']]
    unstamped_reqless = [s for s in reqless_steps if s not in MANUAL_COMPLETION]
    multi_req_steps = [(row['step'], len(row['reqs'])) for row in rows if len(row['reqs']) > 1]
    step_to_step_edges = sum(1 for row in rows if row['deps'] != '-'
                             for token in row['deps'].split() if not token.startswith('T:'))
    statuses = {rid: live.get(rid, {}).get('requirement_status') for rid in req_ids}

    # req #3123 — the CONTAINER flag, read LIVE like every other piece of
    # requirement metadata here. Not hardcoded to REQ_ID: a plan may legitimately
    # link an epic-container requirement that is not its own tracker, and the
    # generator classifying by id "and nothing more" is exactly what the header
    # used to warn about.
    tracking_ids = {rid for rid in req_ids if is_tracking(live.get(rid, {}))}

    # FAIL LOUD if the plan's own tracker is not flagged. Silence here is the
    # dangerous outcome: the fixture would load clean and reproduce the pre-#3123
    # step-19 divergence, and the header would explain it as an open finding that
    # has in fact shipped. A generated file lying about its own contents is the
    # failure mode this generator's header notes already exist to prevent.
    #
    # The two causes are DISTINGUISHED rather than collapsed. A single message
    # blaming the migration would be a confident wrong diagnosis when the real
    # fault is a requirement missing from the read, and this generator's header
    # notes already exist because a confident wrong explanation costs more than
    # a missing one.
    if REQ_ID in req_ids and REQ_ID not in tracking_ids:
        if REQ_ID not in live:
            raise SystemExit(
                "requirement #%d — this plan's own TRACKING requirement — is referenced "
                "by the plan but ABSENT from the darwin://requirements read (the read was "
                "not truncated; that is checked separately above). Do NOT assume the "
                "migration is missing: the row itself did not come back, so every piece "
                "of its metadata this fixture emits would be a fallback value. Check the "
                "requirement exists and is readable, then re-run." % REQ_ID)
        raise SystemExit(
            "requirement #%d — this plan's own TRACKING requirement — came back with "
            "tracking=0. Apply migration "
            "20260731124830_add_requirements_tracking_container_flag.sql (which flips it) "
            "to the database this read hits, or set the flag with update_requirement, "
            "before regenerating: without it this fixture silently reproduces the "
            "pre-req-#3123 step-19 divergence." % REQ_ID)

    divergences = [(row['step'], row['state'], derived_state(row, statuses, tracking_ids))
                   for row in rows
                   if derived_state(row, statuses, tracking_ids) != row['state']]

    out = []
    w = out.append

    w('-- seed_pipelines_darwin_dev.sql')
    w('--')
    w('-- GENERATED by DarwinSQL/scripts/seed_pipelines_darwin_dev.py — do not hand-edit.')
    w('-- Regenerate after any change to the req #%d PLAN-JSON.' % REQ_ID)
    w('--')
    w('-- Req #3111 / deliverable 3 of req #3080: the 2026-07-25 Substrate Rebuild plan,')
    w('-- the acceptance fixture for the Swarm Orchestration feature, expressed in the')
    w('-- tables migration 076 creates.')
    w('--')
    w('-- *** darwin_dev ONLY. *** NEVER apply this file to production `darwin`.')
    w('-- It used to be safe to say `darwin` was simply empty. The Primary\'s live-plan')
    w('-- cutover has since landed and production carries the real plan, so these')
    w('-- 9001-band rows would sit alongside live ones rather than in an empty table')
    w('-- (req #3147).')
    w('--')
    w('-- Source plan: requirement #%d, %d rows, %d distinct requirements,'
      % (REQ_ID, len(rows), len(req_ids)))
    w('--              %d epics, %d features.' % (len(epic_names), len(feature_pairs)))
    w('--')
    w('-- ## Id allocation (explicit, so this file is idempotent and self-scoping)')
    w('--')
    w('--   epics                %d..%d' % (EPIC_BASE + 1, EPIC_BASE + len(epic_names)))
    w('--   features             %d..%d' % (FEATURE_BASE + 1, FEATURE_BASE + len(feature_pairs)))
    w('--   pipelines            %d' % PIPELINE_ID)
    w('--   pipeline_steps       %d + the plan step id (see below)' % STEP_BASE)
    w('--   projects/categories  %d / %d — owned by the fixture, created idempotently'
      % (FIXTURE_PROJECT, FIXTURE_CATEGORY))
    w('--')
    w('-- ## plan step id -> pipeline_steps.id')
    w('--')
    w('-- OFFSET BY %d. The plan\'s `step` values are already stable integers assigned' % STEP_BASE)
    w('-- once and never renumbered (req #3080 design rule 4 / the 2026-07-25')
    w('-- normalization), which is exactly the contract pipeline_steps.id carries — but')
    w('-- they start at 1. Loading them verbatim would park AUTO_INCREMENT just above the')
    w('-- plan\'s highest step, so the next step created organically through the app would')
    w('-- take an id the plan claims as soon as it grows, and the next re-seed would die')
    w('-- 1062 mid-file with the teardown already applied. The offset keeps the mapping')
    w('-- readable (plan step 12 -> %d) and collision-free. In the product these ids come' % (STEP_BASE + 12))
    w('-- from AUTO_INCREMENT; only this fixture pins them.')
    w('--')
    w('--   ' + ', '.join(f'{r["step"]}->{step_id(r["step"])}' for r in rows))
    w('--')
    w('-- ## Mutation end-states this fixture carries (acceptance criteria)')
    w('--')
    if untitled_steps:
        w('--   * %-20s %s — no `title` in the PLAN-JSON, so the step name'
          % ('UNTITLED steps', steps_phrase(untitled_steps)))
        w('--                          falls back to a truncated summary. Give them a')
        w('--                          short name in req #%d and regenerate.' % REQ_ID)
    w('--   * %-20s %s — no requirement links; completed_at is the'
      % ('req-less step' + ('s' if len(reqless_steps) != 1 else ''),
         steps_phrase(reqless_steps) or '(none in this plan)'))
    w('--                          manual stamp, the one case the column exists for.')
    if unstamped_reqless:
        w('--                          UNSTAMPED (loads NULL, derives Scheduled forever, add')
        w('--                          to MANUAL_COMPLETION): %s.' % steps_phrase(unstamped_reqless))
    w('--   * %-20s step %s — two dep rows of different kinds (step 1 +'
      % ('dual-condition gate', RECONSTRUCTED_TIME_GATE[0]))
    w('--                          a wall-clock row). RECONSTRUCTED from req #3080 stage 0')
    w('--                          (s0.4); the live PLAN-JSON has no T: tokens because the')
    w('--                          normalization dropped them. The ONLY dep row here not')
    w('--                          present in the live plan.')
    w('--   * %-20s launch units of >1 requirement, as step(count)' % 'multi-req steps')
    w('--                          pairs (design rule 2):')
    # step(count), not two parallel lists: a wrapped list of ids over a wrapped
    # list of counts would make the reader zip them across a line break.
    for line in wrap_comment(', '.join('%s(%d)' % pair for pair in multi_req_steps) + '.'):
        w('--                          ' + line)
    w('--   * cross-epic step      step 19 — #3105 sits under a different epic than the')
    w('--                          step\'s dominant label, which is why labels attach at')
    w('--                          the requirement (design rule 10).')
    w('--   * dropped-without-     requirements the user pulled from the plan (#3065/#3074')
    w('--     residue              era) simply are not here — no tombstones, no residue.')
    w('--')
    w('-- Requirement rows are upserted with their LIVE metadata (title, status, model,')
    w('-- effort) because step state is DERIVED from requirement status (design rule 1):')
    w('-- without real statuses the fixture would render every step Scheduled and prove')
    w('-- nothing. machine_fk is remapped production->darwin_dev (%s); unmappable values'
      % ', '.join(f'{k}->{v}' for k, v in sorted(MACHINE_MAP.items())))
    w('-- become NULL ("Any").')
    w('--')
    w('-- ## DERIVED STATE vs the plan\'s stored `state`')
    w('--')
    w('-- Deriving state from this fixture reproduces the plan\'s own `state` field for %d'
      % (len(rows) - len(divergences)))
    w('-- of %d rows.' % len(rows))
    w('--')
    # HISTORY, kept rather than deleted (req #3123 scope item 6). The old note
    # here said the step-19 divergence was an open finding; deleting it outright
    # would erase why the column exists, and leaving it would be a generated file
    # asserting something false about its own contents. So: state that it is
    # resolved, name the mechanism, and let the computed list above prove it.
    if tracking_ids:
        w('-- ### RESOLVED — the tracking-requirement divergence (req #3123)')
        w('--')
        w('-- This file used to carry a KNOWN DIVERGENCE note: step 19 derived Running')
        w('-- where the plan recorded done, because it links #%d — this plan\'s own' % REQ_ID)
        w('-- TRACKING requirement, a container that stays in `development` for the')
        w('-- entire life of the plan it describes. Deriving pinned the step Running')
        w('-- forever. It was the sole divergence with a cause in the engine rather')
        w('-- than in the plan.')
        w('--')
        w('-- Req #3123 shipped the durable signal that closes it:')
        w('-- `requirements.tracking` (migration 20260731124830). A container is')
        w('-- subtracted from a step\'s GATING set before state is derived, so a step')
        w('-- whose links are all containers falls through to its own completed_at')
        w('-- exactly as a link-less step does, and a MIXED step lets its remaining')
        w('-- work decide. The flag is emitted below from the LIVE requirement read,')
        w('-- never hand-set here, and generation ABORTS if #%d comes back unflagged.' % REQ_ID)
        w('--')
        w('-- Flagged as containers in this generation: %s.'
          % ', '.join('#%d' % rid for rid in sorted(tracking_ids)))
        # Whether the exemption is LOAD-BEARING right now is a fact about live
        # data, so it is computed, not asserted. A container that has since
        # closed derives correctly with or without the exemption, and a header
        # claiming this file proves the fix when it no longer can is exactly the
        # generated-file-lying-about-itself failure the notes above guard.
        load_bearing = sorted(
            rid for rid in tracking_ids
            if statuses.get(rid) not in TERMINAL_STATUSES)
        w('--')
        if load_bearing:
            w('-- The exemption is LOAD-BEARING in this generation: %s %s still open, so'
              % (', '.join('#%d' % rid for rid in load_bearing),
                 'is' if len(load_bearing) == 1 else 'are'))
            w('-- without the flag the step(s) linking it would derive Running.')
        else:
            w('-- NOTE: every flagged container is now in a TERMINAL status, so the steps')
            w('-- linking one derive the same state with or without the exemption. This')
            w('-- file therefore CARRIES the signal but no longer DEMONSTRATES it. The')
            w('-- demonstration lives in the static JS fixture,')
            w('-- Darwin/src/SwarmView/pipelines/__tests__/substrateRebuildFixture.js, which')
            w('-- pins #%d at `development` + tracking=1 on purpose (req #3169).' % REQ_ID)
    # EVERY claim below is gated on having actually found the thing it claims.
    # The numbers used to be hardcoded; the CAUSAL prose was too, and a confident
    # wrong explanation costs more than a stale count — an unconditional "the rest
    # is plan lag" would mislabel a second tracking requirement, or a requirement
    # that fell out of the live read, as drift.
    if not divergences:
        w('--')
        w('-- No divergences this generation: every step\'s derived state matches the')
        w('-- plan\'s own `state` field. Nothing to explain.')
    else:
        w('--')
        w('-- The exceptions, computed at generation time:')
        w('--')
        for step, stored, derived in divergences:
            w('--   step %-3s plan says %-8s derivation says %s' % (step, stored, derived))
        w('--')
        w('-- The fixture is NOT adjusted to match. It stores no state at all, by design,')
        w('-- and hand-correcting the inputs to make a rule come out right is exactly the')
        w('-- move design rule 1 forbids. Causes found in THIS list:')
        w('--')
        # There is deliberately NO "tracking requirement" branch here any more.
        # The abort in `main` guarantees the plan's own tracker is flagged before
        # this point, and a flagged container is subtracted from the gating set
        # before derivation — so a divergence CAUSED by a container cannot reach
        # this list. A branch for it would be unreachable code claiming to be a
        # detector, which is worse than no detector: it reads as coverage.
        #
        # The pre-req-#3123 version of this file classified by the tracker id and
        # warned that it "classifies by the plan's own tracker id and nothing
        # more". That caveat is what the flag replaced.
        others = [s for s, _, _ in divergences]
        if others:
            w('--   * PLAN LAG — %s. Here the DERIVATION is the correct value: the stored'
              % steps_phrase(others))
            w('--     `state` field is hand-maintained and drifts the moment a session')
            w('--     starts or closes. That lag is the exact failure design rule 1 names')
            w('--     (plan row 13 read "Scheduled" while five sessions ran), so these rows')
            w('--     are the product FIXING the problem rather than describing it.')
            w('--     Read them as such only after ruling out a requirement missing from')
            w('--     the live read. A tracking container is no longer a candidate cause:')
            w('--     since req #3123 containers carry `requirements.tracking`, this')
            w('--     generator reads the flag live and exempts them before deriving.')
    w('')
    w('-- The plan text carries em-dashes, ellipses and other non-ASCII; declare the')
    w('-- connection charset so a loader that does not default to utf8mb4 cannot mangle')
    w('-- or reject it. Load with DarwinSQL/scripts/load_sql.py (quote-aware splitter —')
    w('-- titles here contain both semicolons and # characters inside string literals).')
    w('SET NAMES utf8mb4;')
    w('')
    w('-- darwin_dev ONLY. This used to be enforced by a `USE darwin_dev;` statement,')
    w('-- which enforced nothing: a `USE` re-points whoever executes it, so it protects')
    w('-- the file only for as long as nobody types the other database name. The line')
    w('-- below is a CONSTRAINT the caller is checked against before a connection is')
    w('-- opened, and a target list that omits `darwin` is an absolute production ban')
    w('-- (req #3196, DarwinSQL/scripts/db_guard.py).')
    w('-- darwin:targets = darwin_dev')
    w('')
    w('-- ---------------------------------------------------------------------------')
    w('-- Teardown — FK-safe order, scoped to this fixture\'s ids.')
    w('--')
    w('-- pipeline_step_deps goes FIRST and explicitly: dep_step_fk is ON DELETE')
    w('-- RESTRICT, so deleting the pipeline while step-to-step edges exist is refused')
    w('-- (this plan has %d of them). That two-phase teardown is the documented contract'
      % step_to_step_edges)
    w('-- from migration 076 — not a quirk of this file.')
    w('-- ---------------------------------------------------------------------------')
    w('DELETE FROM pipeline_step_deps WHERE step_fk IN '
      '(SELECT id FROM pipeline_steps WHERE pipeline_fk = %d);' % PIPELINE_ID)
    w('DELETE FROM pipeline_step_requirements WHERE step_fk IN '
      '(SELECT id FROM pipeline_steps WHERE pipeline_fk = %d);' % PIPELINE_ID)
    w('DELETE FROM pipeline_steps WHERE pipeline_fk = %d;' % PIPELINE_ID)
    w('DELETE FROM pipelines WHERE id = %d;' % PIPELINE_ID)
    w('-- Detach requirements before features go, so fk_requirements_feature (SET NULL)')
    w('-- never has to fire mid-load and leave a half-linked state.')
    w('--')
    w('-- Scoped to the EXACT ids this file is about to insert, never a BETWEEN range.')
    w('-- Explicit ids at %d+ leave AUTO_INCREMENT immediately above the fixture band, so'
      % (FEATURE_BASE + 1))
    w('-- the next organically-created row lands exactly where a growing range would')
    w('-- expand — and a later plan with one more feature label would delete it.')
    w('UPDATE requirements SET feature_fk = NULL WHERE feature_fk IN (%s);'
      % ', '.join(str(feature_id[pair]) for pair in feature_pairs))
    w('DELETE FROM features WHERE id IN (%s);'
      % ', '.join(str(feature_id[pair]) for pair in feature_pairs))
    w('DELETE FROM epics WHERE id IN (%s);'
      % ', '.join(str(epic_id[name]) for name in epic_names))
    w('')

    # ---- fixture-owned project + category -------------------------------
    w('-- ---------------------------------------------------------------------------')
    w('-- The fixture\'s OWN project + category.')
    w('--')
    w('-- The plan\'s requirements carry PRODUCTION category ids, and')
    w('-- requirements.category_fk is NOT NULL -> categories ON DELETE RESTRICT — the')
    w('-- same cross-database hazard the machine_fk remap exists for. Reusing them works')
    w('-- on today\'s darwin_dev only because the ids happen to coincide; against a')
    w('-- darwin_dev rebuilt from recreate_darwin_dev.sql the load would fail 1452 AFTER')
    w('-- the teardown above had dropped the previous fixture. Owning these two rows')
    w('-- removes the assumption.')
    w('--')
    w('-- Created idempotently and deliberately NOT torn down: the upserted requirements')
    w('-- keep pointing at the category, and the FK is RESTRICT.')
    w('-- ---------------------------------------------------------------------------')
    w('INSERT INTO projects (id, project_name, creator_fk) VALUES')
    w('  (%d, %s, %s)' % (FIXTURE_PROJECT, q('Swarm Orchestration Fixture'), q(CREATOR)))
    w('AS new ON DUPLICATE KEY UPDATE project_name = new.project_name;')
    w('')
    w('INSERT INTO categories (id, category_name, project_fk, creator_fk) VALUES')
    w('  (%d, %s, %d, %s)' % (FIXTURE_CATEGORY, q('Swarm Orchestration Fixture'),
                              FIXTURE_PROJECT, q(CREATOR)))
    w('AS new ON DUPLICATE KEY UPDATE category_name = new.category_name;')
    w('')

    # ---- epics ----------------------------------------------------------
    w('-- ---------------------------------------------------------------------------')
    w('-- Epics (%d) — the top of Epic > Feature > Story.' % len(epic_names))
    w('-- ---------------------------------------------------------------------------')
    w('INSERT INTO epics (id, title, description, category_fk, creator_fk, sort_order) VALUES')
    values = []
    for i, name in enumerate(epic_names):
        values.append('  (%d, %s, %s, %d, %s, %d)' % (
            epic_id[name], q(name),
            q('Epic from the 2026-07-25 Substrate Rebuild plan (req #%d).' % REQ_ID),
            FIXTURE_CATEGORY, q(CREATOR), i))
    w(',\n'.join(values) + ';')
    w('')

    # ---- features -------------------------------------------------------
    w('-- ---------------------------------------------------------------------------')
    w('-- Features (%d) — one per distinct feature label, linked to its epic.' % len(feature_pairs))
    w('-- ---------------------------------------------------------------------------')
    w('INSERT INTO features (id, title, description, feature_status, epic_fk, '
      'category_fk, creator_fk, sort_order) VALUES')
    values = []
    for i, pair in enumerate(feature_pairs):
        label, epic = pair
        note = ('Feature under epic "%s", from the Substrate Rebuild plan (req #%d).'
                % (epic, REQ_ID))
        if pair in CROSS_EPIC.values():
            note = ('Carries the cross-epic requirement in plan step 19 — the launch unit '
                    'spans epics, which is why labels attach at the requirement '
                    '(req #3080 design rule 10).')
        values.append('  (%d, %s, %s, %s, %d, %d, %s, %d)' % (
            feature_id[pair], q(label), q(note), q('active'),
            epic_id[epic], FIXTURE_CATEGORY, q(CREATOR), i))
    w(',\n'.join(values) + ';')
    w('')

    # ---- requirement stubs ----------------------------------------------
    w('-- ---------------------------------------------------------------------------')
    w('-- Requirements (%d) — upserted with live metadata, then filed under their' % len(req_ids))
    w('-- feature. pipeline_step_requirements.requirement_fk is ON DELETE RESTRICT, so')
    w('-- every referenced requirement must exist before the junction rows load.')
    w('--')
    w('-- ON DUPLICATE KEY UPDATE, not plain INSERT: darwin_dev already holds some of')
    w('-- these ids, and the fixture must refresh their status (step state is derived')
    w('-- from it) without disturbing anything else about the row.')
    w('-- ---------------------------------------------------------------------------')
    w('INSERT INTO requirements (id, title, requirement_status, coordination_type, '
      'ai_model, effort, category_fk, creator_fk, machine_fk, feature_fk, '
      'tracking, started_at, completed_at) VALUES')
    values = []
    for rid in req_ids:
        src = live.get(rid, {})
        title = src.get('title') or f'Requirement #{rid} (not resolvable at fixture-generation time)'
        machine = MACHINE_MAP.get(src.get('machine_fk'))
        values.append('  (%d, %s, %s, %s, %s, %s, %d, %s, %s, %d, %d, %s, %s)' % (
            rid,
            q(title[:256]),
            q(src.get('requirement_status') or 'authoring'),
            q(src.get('coordination_type') or 'implemented'),
            q(src.get('ai_model') or 'opus'),
            q(src.get('effort') or 'high'),
            FIXTURE_CATEGORY,
            q(CREATOR),
            q(machine),
            feature_id[req_feature[rid]],
            1 if rid in tracking_ids else 0,
            q(src.get('started_at')),
            q(src.get('completed_at'))))
    w(',\n'.join(values))
    w('AS new ON DUPLICATE KEY UPDATE')
    w('  title = new.title,')
    w('  requirement_status = new.requirement_status,')
    w('  coordination_type = new.coordination_type,')
    w('  ai_model = new.ai_model,')
    w('  effort = new.effort,')
    w('  machine_fk = new.machine_fk,')
    w('  feature_fk = new.feature_fk,')
    # In the UPDATE arm too, not just the INSERT arm: darwin_dev already holds
    # most of these ids, so a fixture that only set the flag on first insert
    # would leave a stale 0 on the very row the exemption is about.
    w('  tracking = new.tracking,')
    w('  started_at = new.started_at,')
    w('  completed_at = new.completed_at;')
    w('')

    # ---- pipeline -------------------------------------------------------
    w('-- ---------------------------------------------------------------------------')
    w('-- The pipeline. `active` is a STORED, human/Primary-controlled declaration of')
    w('-- intent about the plan as a whole — the only hand-set lifecycle in the feature.')
    w('-- ---------------------------------------------------------------------------')
    goal = ('Recover from the .git/index corruption incident, eliminate the shared-clone '
            'corruption class, rebuild provisioning on per-session clones, then run the '
            'max-parallel feature DAG. Source of truth: requirement #%d.' % REQ_ID)
    w('INSERT INTO pipelines (id, title, description, pipeline_status, machine_fk, '
      'creator_fk, started_at) VALUES')
    w('  (%d, %s, %s, %s, %d, %s, %s);' % (
        PIPELINE_ID, q(plan['plan']), q(goal), q('active'),
        MACHINE_MAP[2], q(CREATOR), q('2026-07-24 00:00:00')))
    w('')

    # ---- steps ----------------------------------------------------------
    w('-- ---------------------------------------------------------------------------')
    w('-- Steps (%d) — one per plan row, id = plan step id.' % len(rows))
    w('--')
    w('-- NO state column is written because none exists: a step\'s state is derived from')
    w('-- its linked requirements (design rule 1). The plan\'s own `state` field')
    w('-- (done/active/pending) is therefore NOT stored — it is reproducible from the')
    w('-- requirement statuses upserted above, and storing it is exactly the hand-edited')
    w('-- field that let plan row 13 read "Scheduled" while five sessions ran.')
    w('--')
    w('-- title is the plan row\'s OWN `title` field — a short name ("Session Drain",')
    w('-- "Bounded MCP Reads"), 11-36 chars across this plan. `notes` holds the full')
    w('-- `summary` prose: the evidence, the disposition, the corrections.')
    w('--')
    w('-- Until req #3119 this loaded `short_title(summary)` into title and left the')
    w('-- plan\'s real `title` unread, so every step name was a truncated paragraph and')
    w('-- the visualizer\'s Step: Title mode showed 40 chars of description. A title is')
    w('-- a NAME, not the first line of the description — and the plan has carried the')
    w('-- names all along.')
    w('-- ---------------------------------------------------------------------------')
    w('INSERT INTO pipeline_steps (id, pipeline_fk, title, run, notes, completed_at, '
      'creator_fk) VALUES')
    values = []
    for row in rows:
        summary = ' '.join(row['summary'].split())
        # A row without its own title is a plan-authoring defect, not something to
        # paper over silently — but the fixture still has to load, so fall back to
        # the old truncation and NAME the row in the header so it gets fixed.
        plan_title = (row.get('title') or '').strip()
        title = short_title(plan_title) if plan_title else short_title(summary)
        notes = summary
        values.append('  (%d, %d, %s, %s, %s, %s, %s)' % (
            step_id(row['step']), PIPELINE_ID, q(title), q(row.get('run', 'auto')),
            q(notes), q(MANUAL_COMPLETION.get(row['step'])), q(CREATOR)))
    w(',\n'.join(values) + ';')
    w('')

    # ---- junction -------------------------------------------------------
    links = [(step_id(row['step']), rid) for row in rows for rid in row['reqs']]
    multi = [row['step'] for row in rows if len(row['reqs']) > 1]
    w('-- ---------------------------------------------------------------------------')
    w('-- Step -> requirement links (%d). A step is a LAUNCH UNIT: steps %s carry'
      % (len(links), ', '.join(multi)))
    w('-- more than one requirement because those requirements went out in ONE')
    w('-- swarm-start (design rule 2).')
    w('-- ---------------------------------------------------------------------------')
    w('INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) VALUES')
    w(',\n'.join('  (%d, %d)' % (s, r) for s, r in links) + ';')
    w('')

    # ---- deps -----------------------------------------------------------
    step_deps = []
    for row in rows:
        if row['deps'] == '-':
            continue
        for token in row['deps'].split():
            if token.startswith('T:'):
                step_deps.append((step_id(row['step']), None, token[2:]))
            else:
                step_deps.append((step_id(row['step']), step_id(token), None))
    recon_step, recon_time = RECONSTRUCTED_TIME_GATE

    w('-- ---------------------------------------------------------------------------')
    w('-- Dependency edges from the plan (%d). Structured rows, never prose' % len(step_deps))
    w('-- (design rule 4). Exactly one of dep_step_fk / time_at per row. dep_step_fk is')
    w('-- ON DELETE RESTRICT, which is what makes a referenced step undeletable.')
    w('-- ---------------------------------------------------------------------------')
    w('INSERT INTO pipeline_step_deps (step_fk, dep_step_fk, time_at) VALUES')
    w(',\n'.join('  (%d, %s, %s)' % (step, q(dep), q(when))
                 for step, dep, when in step_deps) + ';')
    w('')
    w('-- ---------------------------------------------------------------------------')
    w('-- THE DUAL-CONDITION GATE (s0.4) — reconstructed, and separated from the block')
    w('-- above so its provenance cannot be mistaken.')
    w('--')
    w('-- req #3080, plan stage 0: "s0.4 gate: #3050 session completed AND 2h time gate')
    w('-- 06:31:38 PDT (done — note: DUAL-condition gate, two independent wait')
    w('-- mechanisms)". The live PLAN-JSON carries no T: tokens: the 2026-07-25')
    w('-- normalization that replaced the 0/2a/Wx/Px ids dropped the wall-clock condition')
    w('-- with the stage numbering. This row restores it on the step that actually waited')
    w('-- on it — step %s (#3072, the first substrate surgery), which already gates on' % recon_step)
    w('-- step 1 (the drain, where #3050 landed). Step %s therefore ends up with two dep' % recon_step)
    w('-- rows of DIFFERENT kinds, which is what a dual-condition gate is and what the')
    w('-- acceptance criterion asks this schema to prove it can hold.')
    w('-- ---------------------------------------------------------------------------')
    w('INSERT INTO pipeline_step_deps (step_fk, dep_step_fk, time_at) VALUES')
    w('  (%d, NULL, %s);' % (step_id(recon_step), q(recon_time)))
    w('')
    step_deps.append((step_id(recon_step), None, recon_time))
    w('-- Verification the loader can eyeball:')
    w('--   SELECT COUNT(*) FROM pipeline_steps             WHERE pipeline_fk = %d;  -- %d'
      % (PIPELINE_ID, len(rows)))
    w('--   SELECT COUNT(*) FROM pipeline_step_requirements '
      'WHERE step_fk IN (SELECT id FROM pipeline_steps WHERE pipeline_fk = %d);  -- %d'
      % (PIPELINE_ID, len(links)))
    w('--   SELECT COUNT(*) FROM pipeline_step_deps         '
      'WHERE step_fk IN (SELECT id FROM pipeline_steps WHERE pipeline_fk = %d);  -- %d'
      % (PIPELINE_ID, len(step_deps)))

    sql = '\n'.join(out) + '\n'

    if '--stdout' in sys.argv:
        sys.stdout.write(sql)
    else:
        with open(OUT, 'w') as handle:
            handle.write(sql)
        print(f'wrote {OUT}')
        print(f'  {len(epic_names)} epics, {len(feature_pairs)} features, '
              f'{len(req_ids)} requirements, {len(rows)} steps, '
              f'{len(links)} links, {len(step_deps)} deps')


if __name__ == '__main__':
    main()
