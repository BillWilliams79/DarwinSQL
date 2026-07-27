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

darwin_dev ONLY. Production `darwin` stays empty until the Primary's live-plan
cutover, which is a separate doctrine-governed act.
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
MANUAL_COMPLETION = {'7': '2026-07-26 01:30:00'}


def step_id(plan_step):
    """plan step id -> pipeline_steps.id."""
    return STEP_BASE + int(plan_step)


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

    live = {r['id']: r for r in mcp_read('darwin://requirements') if isinstance(r, dict)}

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
    w('-- *** darwin_dev ONLY. *** Production `darwin` stays EMPTY until the Primary\'s')
    w('-- live-plan cutover, which is a separate doctrine-governed act. Do not apply')
    w('-- this file to `darwin`.')
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
    w('--   * req-less step        step 7 — no requirement links; completed_at is the')
    w('--                          manual stamp, the one case the column exists for.')
    w('--   * dual-condition gate  step 3 — two dep rows of different kinds (step 1 +')
    w('--                          a wall-clock row). RECONSTRUCTED from req #3080 stage 0')
    w('--                          (s0.4); the live PLAN-JSON has no T: tokens because the')
    w('--                          normalization dropped them. The ONLY dep row here not')
    w('--                          present in the live plan.')
    w('--   * multi-req steps      steps 1, 12, 13, 19, 33 — launch units of 5, 7, 5, 3 and')
    w('--                          2 requirements (design rule 2).')
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
    w('-- ## KNOWN DIVERGENCE — derived state vs the plan\'s stored `state` (STEP 19)')
    w('--')
    w('-- Deriving state from this fixture reproduces the plan\'s own `state` field for 33')
    w('-- of 34 rows. Step 19 is the exception: the plan says done, the derivation says')
    w('-- Running, because the step links #3083 — the TRACKING requirement — and a')
    w('-- tracking requirement stays in `development` for the entire life of the plan it')
    w('-- describes. The fixture is NOT adjusted to match. It stores no state at all, by')
    w('-- design, and hand-correcting the inputs to make a rule come out right is exactly')
    w('-- the move design rule 1 forbids.')
    w('--')
    w('-- The divergence is a REAL INPUT for the derivation engine (req #3112) and the')
    w('-- Primary doctrine (req #3116): a plan\'s own tracking requirement is a container,')
    w('-- not work, and a step that links one will pin itself Running forever unless the')
    w('-- rule excludes it. Recorded here rather than smoothed away so the engine work')
    w('-- has the case in hand.')
    w('')
    w('-- The plan text carries em-dashes, ellipses and other non-ASCII; declare the')
    w('-- connection charset so a loader that does not default to utf8mb4 cannot mangle')
    w('-- or reject it. Load with DarwinSQL/scripts/load_sql.py (quote-aware splitter —')
    w('-- titles here contain both semicolons and # characters inside string literals).')
    w('SET NAMES utf8mb4;')
    w('USE darwin_dev;')
    w('')
    w('-- ---------------------------------------------------------------------------')
    w('-- Teardown — FK-safe order, scoped to this fixture\'s ids.')
    w('--')
    w('-- pipeline_step_deps goes FIRST and explicitly: dep_step_fk is ON DELETE')
    w('-- RESTRICT, so deleting the pipeline while step-to-step edges exist is refused')
    w('-- (this plan has 30 of them). That two-phase teardown is the documented contract')
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
      'started_at, completed_at) VALUES')
    values = []
    for rid in req_ids:
        src = live.get(rid, {})
        title = src.get('title') or f'Requirement #{rid} (not resolvable at fixture-generation time)'
        machine = MACHINE_MAP.get(src.get('machine_fk'))
        values.append('  (%d, %s, %s, %s, %s, %s, %d, %s, %s, %d, %s, %s)' % (
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
    w('-- title is the plan summary cut to VARCHAR(256) at a word boundary; `notes` holds')
    w('-- the full untruncated text, including the evidence and disposition prose.')
    w('-- ---------------------------------------------------------------------------')
    w('INSERT INTO pipeline_steps (id, pipeline_fk, title, run, notes, completed_at, '
      'creator_fk) VALUES')
    values = []
    for row in rows:
        summary = ' '.join(row['summary'].split())
        title = short_title(summary)
        notes = summary if title != summary else None
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
