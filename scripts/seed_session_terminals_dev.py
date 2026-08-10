#!/usr/bin/env python3
"""Terminal-window fixtures for the Sessions views. (req #3455)

    . Lambda-Rest/exports.sh
    python3 DarwinSQL/scripts/seed_session_terminals_dev.py darwin_dev                 # idempotent
    python3 DarwinSQL/scripts/seed_session_terminals_dev.py darwin_dev --reset --destructive
    python3 DarwinSQL/scripts/seed_session_terminals_dev.py darwin_dev --live-window 23234

WHY THIS EXISTS. Req #3455 puts a Terminal chip on the Sessions grid and the
session detail page, clickable when the window is on the machine the browser is
running on. Reviewing that needs sessions that HAVE terminals, and `darwin_dev`
had zero `swarm_sessions` rows of any kind (measured 2026-08-09) — so the page
was not merely un-reviewable, it was empty, which is the "indistinguishable from
broken" trap in memory/database.md § Seeding darwin_dev.

Production cannot stand in for it: `swarm_sessions.terminal_window_id` is only
written by a launcher running THIS code, and the production DDL is a user gate
on an `implemented` requirement, so production rows carry NULL by design.

WHAT IT IS NOT. Not a copy of production, and the terminal values are not real
except for the one described below. The shape is chosen to exercise every branch
of Darwin/src/SwarmView/terminalFocus.js on one screen — that is the point of it:

  1. LOCAL, LIVE       a darwin-machine session whose window id is a REAL live
                       iTerm2 window (pass --live-window). Chip is clickable AND
                       clicking it actually focuses that window. THE happy path.
  2. LOCAL, GONE       a darwin-machine session whose window id belongs to
                       nothing. Chip is clickable and the click must produce the
                       honest "that window is gone" alert rather than a silent
                       no-op — the acceptance criterion that is hardest to
                       produce on demand against a live Mac.
  3. REMOTE            a wsl-machine session with a Windows Terminal handle
                       (`swarm-2`). Shown, NOT clickable: the requirement says
                       do not offer the link for a session on another machine.
  4. NO HANDLE         a session with a window NUMBER but no handle. Shown, not
                       clickable — there is nothing durable to click.
  5. NOT RECORDED      a session with neither. Renders as an em-dash. Every
                       pre-#3455 session looks like this and must not be dressed
                       up as a window.

Rows 1 and 2 both sit on the `darwin` machine ON PURPOSE: terminalFocus.js only
offers a link when EXACTLY ONE open machine matches the browser's platform
family, so a second darwin machine here would silently turn every chip
un-clickable and make the fixture prove the opposite of what it is for.

THE TARGET IS THE CALLER'S, and production is banned before a connection opens,
through db_guard — the same absolute ban the .sql fixtures declare with
`-- darwin:targets`.
"""
import argparse
import os
import platform
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_guard  # noqa: E402

# Non-production only, enforced by db_guard.require_declared_target.
TARGETS = ['darwin_dev']

# The dev-server login (`Bill W`). Every read is scoped by creator_fk, so
# seeding anyone else produces rows the browser never shows.
CREATOR_FK = '37df7531-000d-4470-8be4-1792d8261f69'

# Namespaced so --reset can find exactly this fixture's rows and nothing else,
# matching seed_session_phases_dev.py's `__phaseseed/` convention.
PREFIX = '__termseed/'

# Used ONLY when a real window cannot be resolved (no iTerm2, not macOS).
# Deliberately implausible so it can never accidentally address a real window.
PLACEHOLDER_WINDOW = '999001'


def resolve_live_window():
    """The id of a REAL, currently-open iTerm2 window, or None.

    WHY THIS IS AUTOMATIC RATHER THAN A FLAG YOU REMEMBER. It used to default to
    PLACEHOLDER_WINDOW, so any run without `--live-window` produced a row
    labelled "Terminal is live — click focuses it" that pointed at nothing. The
    req #3460 data-harmony re-seed did exactly that, and the next click reported
    "that window is gone" — the FIXTURE lying, indistinguishable from the
    feature being broken, which is precisely the class of defect #3460 exists to
    eliminate. A fixture whose correctness depends on remembering a flag is the
    same failure as a rule that has to be remembered every time.

    Resolved fresh on every run, because window ids do not survive a reboot or a
    closed window — a stored one goes stale exactly like the column it seeds.

    Returns (window_id, window_number). THIS SHELL'S OWN WINDOW WINS over iTerm's
    `current window`: the launcher exports both `ITERM_WINDOW_ID` and
    `SWARM_TERMINAL_NUMBER`, so the pair is guaranteed to AGREE. `current window`
    is whatever happens to be frontmost when the seed runs, which produced a row
    whose handle pointed at one window while its label said "Window 4" — a chip
    that focuses something other than what it names is its own small lie.
    """
    env_id = (os.environ.get('ITERM_WINDOW_ID') or '').strip()
    env_num = (os.environ.get('SWARM_TERMINAL_NUMBER') or '').strip()
    if env_id.isdigit():
        return env_id, (int(env_num) if env_num.isdigit() else None)

    if platform.system() != 'Darwin':
        return None, None
    try:
        running = subprocess.run(
            ['osascript', '-e', 'application "iTerm2" is running'],
            capture_output=True, text=True, timeout=10)
        if running.stdout.strip() != 'true':
            return None, None
        got = subprocess.run(
            ['osascript', '-e',
             'tell application "iTerm2" to return id of current window'],
            capture_output=True, text=True, timeout=10)
        window_id = got.stdout.strip()
        # No number to pair with a frontmost-window guess: the ⌥⌘N hotkey is not
        # readable from here. The caller labels the row by handle instead of
        # printing a number that might name a different window.
        return (window_id, None) if window_id.isdigit() else (None, None)
    except Exception:
        return None, None


def ambiguous_families(cur):
    """{platform: [ids]} for every family with MORE THAN ONE open machine."""
    cur.execute("SELECT id, title, platform FROM machines WHERE closed = 0 ORDER BY id")
    by_platform = {}
    for row in cur.fetchall():
        by_platform.setdefault(row['platform'], []).append((row['id'], row['title']))
    return {p: rows for p, rows in by_platform.items() if len(rows) > 1}


def disambiguate(cur, families):
    """Close the `devseed-` duplicates so each platform family has one open machine.

    OPT-IN (--disambiguate-machines) and deliberately narrow: it only ever closes
    a machine whose title starts with `devseed-`, and only when its family has
    more than one open row. Closing is reversible (`closed=1`, nothing deleted).

    Why it is needed at all: terminalFocus.js offers a link only when EXACTLY ONE
    open machine matches the browser's platform family — a deliberate refusal to
    guess, since guessing between two Macs would focus a window on the wrong
    desk. `darwin_dev` carries a second open `darwin` machine from an unrelated
    plan fixture (`devseed-plan-Mac mini`), so without this every chip renders
    correctly-but-unhelpfully as unknown-host and the clickable path — the whole
    point of the fixture — cannot be reviewed.

    NEVER touches a real machine row, so re-running the plan fixture that created
    the duplicates simply re-opens them and this can be re-run.
    """
    closed = []
    # `family`, not `platform` — the latter is now an imported module
    # (resolve_live_window uses it) and a loop variable of that name shadows it.
    for family, rows in families.items():
        keep = [r for r in rows if not r[1].startswith('devseed-')]
        # Only close duplicates when a genuine row survives to be the answer.
        # Closing every row of a family would replace ambiguity with absence.
        if not keep:
            continue
        for machine_id, title in rows:
            if title.startswith('devseed-'):
                cur.execute("UPDATE machines SET closed = 1 WHERE id = %s", (machine_id,))
                closed.append(f'{machine_id}:{title}')
    return closed


def machines(cur):
    """The open machine of each platform family, and whether it is unambiguous.

    Returns {platform: id} including ONLY families with exactly one open
    machine — the same rule terminalFocus.js::resolveThisMachineId applies. A
    family with two is reported as missing so the caller warns instead of
    seeding a fixture that renders un-clickable for a reason nobody can see.
    """
    cur.execute("SELECT id, platform FROM machines WHERE closed = 0 ORDER BY id")
    by_platform = {}
    for row in cur.fetchall():
        by_platform.setdefault(row['platform'], []).append(row['id'])
    return {p: ids[0] for p, ids in by_platform.items() if len(ids) == 1}


def fixtures(mac_fk, wsl_fk, live_window, live_is_real, live_number):
    """(name, title, status, machine_fk, terminal_window_id, terminal_number, req_id).

    EVERY fixture names a real requirement. They used to carry `source_ref =
    NULL`, which made them the only rows in the Sessions table with no
    requirement — a state no real session can reach, since `/swarm-start`
    always creates a session from one. The fixture was inventing an impossible
    row and the reader could not tell that from a bug in the column.
    """
    # The title must not claim more than the data supports. When no real window
    # could be resolved this row is a SECOND gone-window case, and saying so is
    # the whole point — the previous version kept the "click focuses it" label
    # and sent the reviewer hunting a bug in the feature.
    live_title = ('Terminal is live — click focuses it' if live_is_real else
                  'Terminal NOT live (no window resolved at seed time) — click reports it gone')
    return [
        ('local-live',  live_title,
         'active',    mac_fk, live_window, live_number, 3455),
        ('local-gone',  'Terminal is gone — click says so',
         'completed', mac_fk, '999999',    5,           3455),
        # The wsl fixture points at the Windows follow-on on purpose: it is the
        # requirement that will make this very row clickable one day.
        ('remote-wt',   'Terminal on the other machine — shown, not clickable',
         'active',     wsl_fk, 'swarm-2',   2,          3457),
        ('no-handle',   'Window number but no handle — nothing to click',
         'review',    mac_fk, None,        8,           3455),
        ('not-recorded', 'No terminal recorded — renders as an em-dash',
         'completed', mac_fk, None,        None,        3460),
    ]


def delete_fixture(cur):
    cur.execute("DELETE FROM swarm_sessions WHERE task_name LIKE %s", (PREFIX + '%',))
    return cur.rowcount


def seed(cur, rows):
    """Insert (or re-point) one row per fixture. Idempotent on task_name.

    UPDATE rather than INSERT-on-conflict because `swarm_sessions` has no unique
    key on task_name — a second run must not double the fixture.
    """
    inserted = updated = 0
    for name, title, status, machine_fk, window_id, window_num, req_id in rows:
        task_name = PREFIX + name
        source_ref = f'requirement:{req_id}'
        cur.execute("SELECT id FROM swarm_sessions WHERE task_name = %s", (task_name,))
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE swarm_sessions SET title=%s, swarm_status=%s, machine_fk=%s, "
                "terminal_window_id=%s, terminal_number=%s, source_type=%s, source_ref=%s "
                "WHERE id=%s",
                (title, status, machine_fk, window_id, window_num,
                 'roadmap', source_ref, existing['id']))
            updated += 1
        else:
            cur.execute(
                "INSERT INTO swarm_sessions "
                "(branch, task_name, source_type, source_ref, title, swarm_status, "
                " ai_model, effort, machine_fk, terminal_window_id, terminal_number, "
                " started_at, creator_fk) "
                "VALUES (%s,%s,'roadmap',%s,%s,%s,'opus','high',%s,%s,%s,NOW(),%s)",
                (f'feature/3455-{name}', task_name, source_ref, title, status,
                 machine_fk, window_id, window_num, CREATOR_FK))
            inserted += 1
    return inserted, updated


def main():
    parser = argparse.ArgumentParser(
        description='Seed terminal-window fixtures for the Sessions views (req #3455).')
    db_guard.add_target_arguments(parser, override_file_target=False)
    parser.add_argument('--reset', action='store_true',
                        help="DELETE this fixture's rows before re-seeding.")
    parser.add_argument('--disambiguate-machines', action='store_true',
                        help='Close `devseed-` duplicate machines so each platform family '
                             'has exactly one open row — otherwise the local chips render '
                             'as unknown-host and the clickable path cannot be reviewed. '
                             'Reversible; never touches a real machine.')
    parser.add_argument('--live-window', default=None,
                        help='A REAL iTerm2 window id for the happy-path chip. DEFAULT: '
                             'resolved automatically from the current iTerm2 window, so a '
                             'plain re-seed always produces a genuinely clickable row. Pass '
                             'this only to target a specific window.')
    args = parser.parse_args()

    try:
        db_guard.require_database(args.database, production=args.production)
        db_guard.require_declared_target(args.database, TARGETS,
                                         'seed_session_terminals_dev.py',
                                         overridable=False)
        if args.reset and not args.destructive:
            raise db_guard.GuardError(
                "REFUSED: --reset DELETEs this fixture's swarm_sessions rows. "
                "Re-run with --destructive to confirm.")
        conn = db_guard.connect(args.database)
    except db_guard.GuardError as exc:
        print(exc, file=sys.stderr)
        return 2

    db_guard.banner(args.database, 'seed_session_terminals_dev.py fixture', TARGETS)

    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM profiles WHERE id = %s', (CREATOR_FK,))
            if not cur.fetchone():
                print(f'REFUSED: profile {CREATOR_FK} does not exist in '
                      f'{args.database!r}; seed it first (seed_darwin_dev.py).',
                      file=sys.stderr)
                return 2

            disambiguated = []
            if args.disambiguate_machines:
                disambiguated = disambiguate(cur, ambiguous_families(cur))

            unique = machines(cur)
            mac_fk, wsl_fk = unique.get('darwin'), unique.get('wsl')
            # Warned, not fatal: the fixture is still worth having with a NULL
            # machine, and a silent un-clickable chip is the failure mode this
            # message exists to pre-empt.
            if mac_fk is None:
                print('warning: no single open `darwin` machine — the local chips will '
                      'render as unknown-host, not as links', file=sys.stderr)
            if wsl_fk is None:
                print('warning: no single open `wsl` machine — the remote chip will not '
                      'demonstrate the other-machine case', file=sys.stderr)

            # Resolve the live window HERE rather than defaulting it, so the
            # common `seed_session_terminals_dev.py darwin_dev` produces a
            # genuinely clickable row without anyone remembering a flag.
            if args.live_window:
                live_window, live_number = args.live_window, None
            else:
                live_window, live_number = resolve_live_window()
            live_is_real = bool(live_window)
            if not live_is_real:
                live_window, live_number = PLACEHOLDER_WINDOW, 4
                print('warning: no live iTerm2 window resolved — the happy-path row will '
                      'report "gone" when clicked, and is labelled to say so. Re-run from '
                      'an iTerm2 window, or pass --live-window <id>.', file=sys.stderr)

            removed = delete_fixture(cur) if args.reset else 0
            inserted, updated = seed(
                cur, fixtures(mac_fk, wsl_fk, live_window, live_is_real, live_number))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f'status=error database={args.database}\nerror={exc}', file=sys.stderr)
        return 1
    finally:
        conn.close()

    if disambiguated:
        print('closed_duplicate_machines=' + ','.join(disambiguated))
    if removed:
        print(f'removed={removed}')
    print(f'inserted={inserted} updated={updated}')
    print(f"live_window={live_window} live_is_real={live_is_real} mac_machine_fk={mac_fk} wsl_machine_fk={wsl_fk}")
    print(f'status=ok database={args.database} creator_fk={CREATOR_FK}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
