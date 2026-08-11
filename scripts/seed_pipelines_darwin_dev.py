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

NO FEATURE LAYER (req #3355). This fixture used to emit `features` rows and a
`requirements.feature_fk` link, because that chain — requirement -> feature ->
epic — was 1.0's ONLY path from a requirement to its epic, and the fixture
demonstrated req #3080 design rule 10 (a launch unit spanning epics) through it.
Migration 20260811033413 DROPPED `features`, `feature_test_cases` and
`requirements.feature_fk`, and there is nothing in 1.0 to rewire the chain to: a
bare 1.0 requirement carries no epic of its own, and only Pipeline 2.0's
`pipeline2_steps.epic_fk` answers the question now. So the demonstration is gone
rather than reworked — 1.0 itself is being wound down (req #3356). `epics` are
UNAFFECTED and still emitted: only the Feature layer between them and the
requirements went away.
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
# cross-database hazard `machine_ref` exists for. Borrowing them happens to work on
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
PIPELINE_ID = 9001      # pipelines        9001

# pipeline_steps.id = STEP_BASE + the plan's step id. NOT the bare step id: those
# start at 1, so a fixture load would leave AUTO_INCREMENT sitting just above the
# plan's highest step, and the next step created organically through the app would
# take an id the plan claims the moment it grows — a 1062 mid-load, after teardown.
# Offsetting into the same 9000 band as the other fixture rows keeps the mapping
# trivially readable (plan step 12 -> 9012) and collision-free.
STEP_BASE = 9000

# The plan's requirements carry PRODUCTION machine_fk values and `machine_fk` is
# ON DELETE RESTRICT, so a value darwin_dev has no row for fails the whole load
# with a 1452. This used to be a HARDCODED id map, `{2: 74, 3: 75}` — production
# id -> the id the same machine happened to hold in darwin_dev — and it broke
# exactly the way a hardcoded cross-database id map breaks: darwin_dev was rebuilt,
# its machines re-registered as ids 2 and 3, and 74/75 stopped existing. Measured
# 2026-08-11: the fixture aborted at the requirements INSERT on
# `fk_requirements_machine`, having emitted every earlier statement correctly.
#
# So the id is not carried across the databases at all any more. The generator
# reads the machine's HOSTNAME — a natural key, and the key machines register
# themselves under — and emits a scalar subquery that resolves it against
# WHICHEVER machines table the file is loaded into:
#
#     machine_fk = (SELECT id FROM machines WHERE hostname = 'Macmini')
#
# A hostname darwin_dev does not know yields NULL, which is the documented "Any"
# fallback the old map also produced for an unmapped value — so an unknown machine
# still degrades to NULL rather than aborting the load.
PIPELINE_MACHINE = 2            # the plan's own machine, by PRODUCTION id (Mac Mini)


def machine_ref(prod_machine_id, hostnames):
    """SQL for `requirements.machine_fk` / `pipelines.machine_fk`.

    Resolved at LOAD time against the target database's own `machines` table, so
    the fixture carries no assumption about which ids darwin_dev holds. NULL
    ("Any") for a machine the plan does not pin or the target does not know.
    """
    host = hostnames.get(prod_machine_id)
    if not host:
        return 'NULL'
    return '(SELECT id FROM machines WHERE hostname = %s)' % q(host)


# CROSS_EPIC used to live here (req #3355 removed it). It filed requirement #3105
# under the Swarm Substrate Rebuild epic through a feature of its own, so the
# fixture could demonstrate design rule 10 — a launch unit spanning epics, which
# is only expressible when labels attach at the requirement. `requirements.feature_fk`
# is gone, so there is no per-requirement label to disagree with the step's epic
# and nothing left to demonstrate. #3105 is NOT lost from the fixture: plan step 19
# links it directly (`reqs` = [3080, 3083, 3105]), so it arrives through the same
# step link as every other requirement here, and the epic it used to add by hand —
# Swarm Substrate Rebuild — is already the first epic the plan's own rows produce.
# Verified against the live plan before the constant was deleted: the requirement
# set is 67 rows with or without it.

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

    # ---- machines: production id -> hostname, read LIVE ------------------
    # ABORT on an empty read rather than generating from it, for the same reason
    # the truncation guard above exists: every machine would silently resolve to
    # NULL, the fixture would LOAD CLEAN, and every requirement would claim it is
    # pinned to no machine. A wrong fixture that loads is worse than no fixture.
    machine_rows = mcp_read('darwin://machines')
    machine_hosts = {
        m['id']: m['hostname']
        for m in machine_rows
        if isinstance(m, dict) and m.get('id') is not None and m.get('hostname')
    }
    if not machine_hosts:
        raise SystemExit(
            'darwin://machines returned no usable rows — refusing to generate a '
            'fixture in which every machine_fk resolves to NULL. Check the read '
            'and re-run.')
    if PIPELINE_MACHINE not in machine_hosts:
        raise SystemExit(
            "machine #%d — the machine this plan ran on — is absent from "
            "darwin://machines, so the pipeline row's own machine_fk cannot be "
            "resolved. Check the machines registry and re-run." % PIPELINE_MACHINE)

    # ---- epics: first-appearance order in the plan ----------------------
    # Each plan row still carries a `feature` label as well as an `epic` one, and
    # it is now deliberately UNREAD (req #3355) — there is no table to put it in.
    # Left in the PLAN-JSON rather than stripped: the plan is the user's document
    # and this generator is only a reader of it.
    epic_names = []
    for row in rows:
        if row['epic'] not in epic_names:
            epic_names.append(row['epic'])
    epic_id = {name: EPIC_BASE + i + 1 for i, name in enumerate(epic_names)}

    # ---- the requirement set: every requirement a step actually links ----
    # Derived straight from the step links, which is the only association left
    # after req #3355 dropped `requirements.feature_fk`. It used to be derived
    # from the requirement -> feature map, which carried the same set plus
    # whatever CROSS_EPIC added by hand; the plan links #3105 on step 19 anyway,
    # so the two agree row-for-row on the live plan.
    req_ids = sorted({rid for row in rows for rid in row['reqs']})

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
    w('--              %d epics.' % len(epic_names))
    w('--')
    w('-- NO FEATURE LAYER (req #3355). Migration 20260811033413 dropped `features`,')
    w('-- `feature_test_cases` and `requirements.feature_fk`, so this fixture emits')
    w('-- neither the feature rows nor the requirement->feature link it used to. A')
    w('-- requirement reaches this plan through its STEP LINK and nothing else. Epics')
    w('-- are unaffected and still emitted.')
    w('--')
    w('-- ## Id allocation (explicit, so this file is idempotent and self-scoping)')
    w('--')
    w('--   epics                %d..%d' % (EPIC_BASE + 1, EPIC_BASE + len(epic_names)))
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
    w('--   * dropped-without-     requirements the user pulled from the plan (#3065/#3074')
    w('--     residue              era) simply are not here — no tombstones, no residue.')
    w('--')
    w('-- Requirement rows are upserted with their LIVE metadata (title, status, model,')
    w('-- effort) because step state is DERIVED from requirement status (design rule 1):')
    w('-- without real statuses the fixture would render every step Scheduled and prove')
    w('-- nothing. machine_fk carries no cross-database id: the plan\'s production')
    w('-- machine is emitted as a HOSTNAME lookup resolved against whichever `machines`')
    w('-- table this file is loaded into (%s), so a rebuilt darwin_dev'
      % ', '.join('#%d=%s' % (k, v) for k, v in sorted(machine_hosts.items())))
    w('-- re-registering its machines under new ids cannot break the load. A hostname')
    w('-- the target does not know resolves to NULL ("Any").')
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
    w('--')
    w('-- There is no `features` teardown any more, and no requirement detach before it')
    w('-- (req #3355): migration 20260811033413 dropped the table and the')
    w('-- `requirements.feature_fk` column that used to need clearing first.')
    w('--')
    w('-- Scoped to the EXACT ids this file is about to insert, never a BETWEEN range.')
    w('-- Explicit ids at %d+ leave AUTO_INCREMENT immediately above the fixture band, so'
      % (EPIC_BASE + 1))
    w('-- the next organically-created row lands exactly where a growing range would')
    w('-- expand — and a later plan with one more epic label would delete it.')
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
    w('-- Epics (%d) — one per distinct epic label in the plan. Since req #3355 dropped' % len(epic_names))
    w('-- the Feature layer, nothing in this fixture points at them: a requirement now')
    w('-- reaches its epic only through the step that links it.')
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

    # ---- requirement stubs ----------------------------------------------
    w('-- ---------------------------------------------------------------------------')
    w('-- Requirements (%d) — every requirement some step links, upserted with live' % len(req_ids))
    w('-- metadata. pipeline_step_requirements.requirement_fk is ON DELETE RESTRICT, so')
    w('-- every referenced requirement must exist before the junction rows load.')
    w('--')
    w('-- ON DUPLICATE KEY UPDATE, not plain INSERT: darwin_dev already holds some of')
    w('-- these ids, and the fixture must refresh their status (step state is derived')
    w('-- from it) without disturbing anything else about the row.')
    w('-- ---------------------------------------------------------------------------')
    w('INSERT INTO requirements (id, title, requirement_status, coordination_type, '
      'ai_model, effort, category_fk, creator_fk, machine_fk, '
      'tracking, started_at, completed_at) VALUES')
    values = []
    for rid in req_ids:
        src = live.get(rid, {})
        title = src.get('title') or f'Requirement #{rid} (not resolvable at fixture-generation time)'
        machine = machine_ref(src.get('machine_fk'), machine_hosts)
        values.append('  (%d, %s, %s, %s, %s, %s, %d, %s, %s, %d, %s, %s)' % (
            rid,
            q(title[:256]),
            q(src.get('requirement_status') or 'authoring'),
            q(src.get('coordination_type') or 'implemented'),
            q(src.get('ai_model') or 'opus'),
            q(src.get('effort') or 'high'),
            FIXTURE_CATEGORY,
            q(CREATOR),
            machine,
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
    w('  (%d, %s, %s, %s, %s, %s, %s);' % (
        PIPELINE_ID, q(plan['plan']), q(goal), q('active'),
        machine_ref(PIPELINE_MACHINE, machine_hosts),
        q(CREATOR), q('2026-07-24 00:00:00')))
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
        print(f'  {len(epic_names)} epics, {len(req_ids)} requirements, '
              f'{len(rows)} steps, {len(links)} links, {len(step_deps)} deps')


if __name__ == '__main__':
    main()
