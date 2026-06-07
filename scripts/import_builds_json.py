#!/usr/bin/env python3
"""
Import a builds.json-shaped JSON blob into the SQL build data model (req #2648).

Walks every branch and build into the SQL tables (build_projects / branches /
builds / customer_releases), preserving the iframe's slug ids in
`branches.external_id` / `builds.external_id` so the SqlBackedStorageAdapter
can round-trip the in-memory model.

Customer-release branches in the JSON (`type: 'customer-release'`) are NOT
preserved as branches — the new architecture moves customer-release events
out of the branch model and into the `customer_releases` table. Each
customer-release branch's `name` is split on '\\n' into one customer per
recipient, and one `customer_releases` row is upserted per (customer,
parent_build). The parent build is set `approved_for_release=1` since a
release event implies approval.

Idempotent:
  - build_projects: lookup by (title, creator_fk), update if found.
  - branches:       lookup by (project_fk, external_id).
  - builds:         lookup by (branch_fk, position).
  - customer_releases: UNIQUE(customer_fk, build_fk).

Fails fast if:
  - The customers referenced by any customer-release branch are missing.
  - parentBuildId references in the JSON are not satisfiable.

Usage:
    # Default import (Topology/build-visualizer/builds.json → 'Default'):
    cd Lambda-Rest && . exports.sh && \\
        python3 ../DarwinSQL/scripts/import_builds_json.py

    # Import a different JSON blob with a custom title:
    python3 ../DarwinSQL/scripts/import_builds_json.py \\
        --path /tmp/sprint-cycle.json --title 'Sprint Cycle'

    # Production (req #2691) — requires a recent darwin-pre-migration snapshot:
    cd Lambda-Rest && . exports.sh && \\
        python3 ../DarwinSQL/scripts/import_builds_json.py --db darwin
"""
import argparse
import json
import os
import sys

import pymysql

from _production_snapshot_guard import assert_recent_production_snapshot

# Bill Williams primary user — owns the imported demo data
DEFAULT_CREATOR_FK = '37df7531-000d-4470-8be4-1792d8261f69'
DEFAULT_IMPORT_TITLE = 'Default'

ALLOWED_DATABASES = ('darwin_dev', 'darwin')
PRODUCTION_DATABASE = 'darwin'

# Path to builds.json — relative to this script's repo root sibling structure:
#   DarwinSQL/scripts/import_builds_json.py
#   Topology/build-visualizer/builds.json
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BUILDS_JSON_PATH = os.path.normpath(
    os.path.join(HERE, '..', '..', 'Topology', 'build-visualizer', 'builds.json'),
)


def get_admin_connection(database):
    return pymysql.connect(
        host=os.environ['endpoint'],
        user=os.environ['username'],
        password=os.environ['db_password'],
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def assert_target_db(cur, target_database):
    cur.execute("SELECT DATABASE() AS db")
    actual = cur.fetchone()['db']
    if actual != target_database:
        sys.exit(f"ABORT: expected '{target_database}', got '{actual}'")


def upsert_project(cur, title, description):
    cur.execute(
        "SELECT id FROM build_projects WHERE title=%s AND creator_fk=%s",
        (title, DEFAULT_CREATOR_FK),
    )
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute(
        """INSERT INTO build_projects
           (title, description, project_status, creator_fk)
           VALUES (%s, %s, %s, %s)""",
        (title, description, 'active', DEFAULT_CREATOR_FK),
    )
    return cur.lastrowid


def lookup_customer_id(cur, customer_name):
    cur.execute(
        "SELECT id FROM customers WHERE customer_name=%s AND creator_fk=%s",
        (customer_name, DEFAULT_CREATOR_FK),
    )
    row = cur.fetchone()
    if not row:
        sys.exit(
            f"ABORT: customer '{customer_name}' not seeded — run req #2604 customers seed first"
        )
    return row['id']


def upsert_branch(cur, project_id, branch_type, name, parent_build_id, major, minor, external_id):
    cur.execute(
        "SELECT id FROM branches WHERE project_fk=%s AND external_id=%s",
        (project_id, external_id),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            """UPDATE branches SET branch_type=%s, name=%s, parent_build_fk=%s,
                     major=%s, minor=%s WHERE id=%s""",
            (branch_type, name, parent_build_id, major, minor, row['id']),
        )
        return row['id']
    cur.execute(
        """INSERT INTO branches
           (project_fk, branch_type, name, parent_build_fk, major, minor,
            external_id, creator_fk)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (project_id, branch_type, name, parent_build_id, major, minor,
         external_id, DEFAULT_CREATOR_FK),
    )
    return cur.lastrowid


def upsert_build(cur, branch_id, position, build_number, branch_number, external_id,
                 major=0, minor=0, dot_color=None, approved_for_release=0):
    cur.execute(
        "SELECT id FROM builds WHERE branch_fk=%s AND position=%s",
        (branch_id, position),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            """UPDATE builds SET build_number=%s, branch_number=%s, external_id=%s,
                     major=%s, minor=%s,
                     dot_color=%s, approved_for_release=%s WHERE id=%s""",
            (build_number, branch_number, external_id, major, minor,
             dot_color, approved_for_release, row['id']),
        )
        return row['id']
    cur.execute(
        """INSERT INTO builds (branch_fk, position, build_number, branch_number,
                               major, minor,
                               external_id, dot_color, approved_for_release, creator_fk)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (branch_id, position, build_number, branch_number, major, minor,
         external_id, dot_color, approved_for_release, DEFAULT_CREATOR_FK),
    )
    return cur.lastrowid


def upsert_customer_release(cur, customer_id, build_id):
    cur.execute(
        "SELECT id FROM customer_releases WHERE customer_fk=%s AND build_fk=%s",
        (customer_id, build_id),
    )
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute(
        """INSERT INTO customer_releases (customer_fk, build_fk, creator_fk)
           VALUES (%s, %s, %s)""",
        (customer_id, build_id, DEFAULT_CREATOR_FK),
    )
    return cur.lastrowid


def compute_branch_major_minor(branch_id, branches_by_id, builds_by_id,
                               trunk_segments, main_build_ids):
    """Return (major, minor) for a branch.

    The branch's M.m is computed from the trunk segment that was in effect at
    the moment the branch was created — i.e. the segment covering its origin's
    trunk index. For sub-branches off a release, walk up to the nearest main
    ancestor. This mirrors VersionEngine in app.js (§3.1 of the design memo).
    """
    branch = branches_by_id[branch_id]
    if branch['id'] == 'main' or branch.get('parentBuildId') is None:
        # Trunk row in the SQL model: stash currentMajor.currentMinor of segment 0.
        seg = trunk_segments[0] if trunk_segments else {'major': 1, 'minor': 0}
        return seg['major'], seg['minor']
    # Walk parentBuildId chain up until we hit a build on main.
    cur_build_id = branch['parentBuildId']
    while cur_build_id:
        build = builds_by_id.get(cur_build_id)
        if not build:
            break
        parent_branch_id = build['branchId']
        if parent_branch_id == 'main':
            try:
                idx = main_build_ids.index(cur_build_id)
            except ValueError:
                idx = 0
            seg = trunk_segments[0] if trunk_segments else {'major': 1, 'minor': 0}
            for s in trunk_segments or []:
                if s.get('startIdx', 0) <= idx:
                    seg = s
            return seg['major'], seg['minor']
        next_branch = branches_by_id.get(parent_branch_id)
        if not next_branch:
            break
        cur_build_id = next_branch.get('parentBuildId')
    # Degenerate fallback
    return (trunk_segments[0]['major'], trunk_segments[0]['minor']) if trunk_segments else (1, 0)


def compute_build_b(branch_type, position, ord0_among_siblings, ord1_among_siblings):
    """Compute the b (branch_number) for a sub-branch build.

    Mirrors `computeBranchNum` in `Topology/build-visualizer/app.js` (req #2614
    reserved-range scheme): 0-indexed `i`, no `+1` offset; sample-release lives
    in the 8000-block; hotfix/bootleg use stride 50; csr stride 1000; development
    stride 100. Customer-release is no longer a branch type (req #2648).
    """
    if branch_type == 'release':
        return 0
    if branch_type == 'sample-release':
        return 8000 + ord0_among_siblings * 100 + position
    if branch_type == 'csr':
        return ord1_among_siblings * 1000 + position
    if branch_type == 'hotfix':
        return 6000 + ord0_among_siblings * 50 + position
    if branch_type == 'development':
        return 7000 + ord0_among_siblings * 100 + position
    if branch_type == 'bootleg':
        return 9000 + ord0_among_siblings * 50 + position
    return position + 1


def load_builds_json(path):
    if not os.path.isfile(path):
        sys.exit(f"ABORT: builds.json not found at {path}")
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description='Import a builds.json blob into SQL.')
    parser.add_argument(
        '--path', default=DEFAULT_BUILDS_JSON_PATH,
        help='Path to the builds.json file to import (default: Topology/build-visualizer/builds.json).',
    )
    parser.add_argument(
        '--title', default=DEFAULT_IMPORT_TITLE,
        help=f"build_projects.title for the imported project (default: '{DEFAULT_IMPORT_TITLE}').",
    )
    parser.add_argument(
        '--description', default=None,
        help='build_projects.description (default: derived from source path).',
    )
    parser.add_argument(
        '--db', default='darwin_dev', choices=ALLOWED_DATABASES,
        help='Target database (default: darwin_dev). Use `darwin` for production import.',
    )
    args = parser.parse_args()
    target_database = args.db

    if target_database == PRODUCTION_DATABASE:
        print(f"WARNING: importing into PRODUCTION database '{target_database}'")
        assert_recent_production_snapshot('import')

    data = load_builds_json(args.path)
    branches = data['branches']
    builds = data['builds']
    trunk_segments = data.get('trunkSegments', [])

    branches_by_id = {br['id']: br for br in branches}
    main_branch = branches_by_id['main']
    main_build_ids = list(main_branch.get('buildIds', []))

    # Partition: customer-release branches become customer_releases events (not SQL branches).
    customer_release_branches = [br for br in branches if br.get('type') == 'customer-release']
    non_cr_branches = [br for br in branches if br.get('type') != 'customer-release']

    description = args.description or (
        f"Imported from {os.path.basename(args.path)} by import_builds_json.py."
    )

    conn = get_admin_connection(target_database)
    with conn.cursor() as cur:
        assert_target_db(cur, target_database)

        project_id = upsert_project(cur, args.title, description)
        print(f"project '{args.title}' id={project_id}")

        # Pass 1: insert every non-cr branch (parent_build_fk NULL — patched later).
        sql_branch_id_by_slug = {}
        for br in non_cr_branches:
            major, minor = compute_branch_major_minor(
                br['id'], branches_by_id, builds, trunk_segments, main_build_ids,
            )
            sql_branch_id_by_slug[br['id']] = upsert_branch(
                cur, project_id, br['type'], br.get('name', ''),
                parent_build_id=None, major=major, minor=minor, external_id=br['id'],
            )

        trunk_id = sql_branch_id_by_slug['main']
        cur.execute(
            "UPDATE build_projects SET trunk_branch_fk=%s WHERE id=%s",
            (trunk_id, project_id),
        )
        print(f"trunk branch id={trunk_id}; project.trunk_branch_fk linked")

        # Pass 2: insert builds. Trunk: monotonic B from segment.initialBuildNumber.
        # Sub-branch: B inherited from parent main-ancestor's trunk B (FROZEN);
        # b computed by branch type / position / ord-among-siblings.
        sql_build_id_by_slug = {}

        # Trunk first.
        # Build a lookup of branch M.m by slug (computed in Pass 1).
        branch_mm_by_slug = {}
        for br in non_cr_branches:
            branch_mm_by_slug[br['id']] = compute_branch_major_minor(
                br['id'], branches_by_id, builds, trunk_segments, main_build_ids,
            )

        for pos, build_id in enumerate(main_build_ids):
            seg = trunk_segments[0] if trunk_segments else {'startIdx': 0, 'initialBuildNumber': 1, 'major': 1, 'minor': 0}
            for s in trunk_segments or []:
                if s.get('startIdx', 0) <= pos:
                    seg = s
            B = seg.get('initialBuildNumber', 1) + (pos - seg.get('startIdx', 0))
            build_obj = builds.get(build_id, {})
            # Per-build M.m: from the segment covering this trunk position.
            seg_major = seg.get('major', 1)
            seg_minor = seg.get('minor', 0)
            sql_build_id_by_slug[build_id] = upsert_build(
                cur, trunk_id, pos, B, 0, build_id,
                major=seg_major, minor=seg_minor,
                dot_color=build_obj.get('dotColor'),
                approved_for_release=0,
            )

        # ord0/ord1 among same-type sibling branches sharing parentBuildId.
        # Stable across loads (matches VersionEngine._ordinal — walks branches in array order).
        from collections import defaultdict
        sibling_ord = defaultdict(int)
        ord0_by_branch_id = {}
        for br in non_cr_branches:
            if br['id'] == 'main' or br.get('parentBuildId') is None:
                continue
            key = (br['type'], br['parentBuildId'])
            ord0_by_branch_id[br['id']] = sibling_ord[key]
            sibling_ord[key] += 1

        # Sub-branches.
        for br in non_cr_branches:
            if br['id'] == 'main':
                continue
            sql_br_id = sql_branch_id_by_slug[br['id']]
            # FROZEN parent main-ancestor's trunk B.
            parent_build_id = br.get('parentBuildId')
            parent_B = None
            cur_id = parent_build_id
            while cur_id:
                build_obj = builds.get(cur_id)
                if not build_obj:
                    break
                if build_obj['branchId'] == 'main':
                    try:
                        idx = main_build_ids.index(cur_id)
                    except ValueError:
                        idx = 0
                    seg = trunk_segments[0] if trunk_segments else {'startIdx': 0, 'initialBuildNumber': 1}
                    for s in trunk_segments or []:
                        if s.get('startIdx', 0) <= idx:
                            seg = s
                    parent_B = seg.get('initialBuildNumber', 1) + (idx - seg.get('startIdx', 0))
                    break
                parent_branch = branches_by_id.get(build_obj['branchId'])
                if not parent_branch:
                    break
                cur_id = parent_branch.get('parentBuildId')

            if parent_B is None:
                parent_B = 0  # degenerate fallback

            ord0 = ord0_by_branch_id.get(br['id'], 0)
            ord1 = ord0 + 1
            # Per-build M.m: from the branch's computed M.m.
            br_major, br_minor = branch_mm_by_slug.get(br['id'], (1, 0))
            for pos, build_id in enumerate(br.get('buildIds', [])):
                b = compute_build_b(br['type'], pos, ord0, ord1)
                build_obj = builds.get(build_id, {})
                sql_build_id_by_slug[build_id] = upsert_build(
                    cur, sql_br_id, pos, parent_B, b, build_id,
                    major=br_major, minor=br_minor,
                    dot_color=build_obj.get('dotColor'),
                    approved_for_release=0,
                )
        print(f"builds inserted: {len(sql_build_id_by_slug)} total")

        # Pass 3: patch parent_build_fk on non-trunk branches.
        for br in non_cr_branches:
            if br['id'] == 'main':
                continue
            parent_build_slug = br.get('parentBuildId')
            if not parent_build_slug:
                continue
            sql_parent_build_id = sql_build_id_by_slug.get(parent_build_slug)
            if not sql_parent_build_id:
                sys.exit(
                    f"ABORT: parentBuildId '{parent_build_slug}' for branch '{br['id']}' "
                    f"does not map to any SQL build."
                )
            cur.execute(
                "UPDATE branches SET parent_build_fk=%s WHERE id=%s",
                (sql_parent_build_id, sql_branch_id_by_slug[br['id']]),
            )

        # Pass 4: customer-release branches → customer_releases events.
        events_inserted = 0
        for cr_br in customer_release_branches:
            target_build_slug = cr_br.get('parentBuildId')
            sql_build_id = sql_build_id_by_slug.get(target_build_slug)
            if not sql_build_id:
                sys.exit(
                    f"ABORT: customer-release branch '{cr_br['id']}' parent build "
                    f"'{target_build_slug}' not in SQL — JSON ordering broken?"
                )
            # Multi-line names stack: one customer per \n-separated entry.
            customer_names = [
                n.strip() for n in str(cr_br.get('name', '')).split('\n') if n.strip()
            ]
            if not customer_names:
                continue
            for cust_name in customer_names:
                cust_id = lookup_customer_id(cur, cust_name)
                upsert_customer_release(cur, cust_id, sql_build_id)
                events_inserted += 1
            # Mark the parent build approved_for_release=1.
            cur.execute(
                "UPDATE builds SET approved_for_release=1 WHERE id=%s",
                (sql_build_id,),
            )
        print(f"customer_releases events inserted: {events_inserted} "
              f"from {len(customer_release_branches)} customer-release branches")

        # Drop any pre-existing SQL branches of type='customer-release' for this
        # project — re-runs after the cleanup keep the SQL state consistent with
        # the new architecture (no customer-release branches in SQL).
        cur.execute(
            "DELETE FROM branches WHERE project_fk=%s AND branch_type=%s",
            (project_id, 'customer-release'),
        )
        dropped = cur.rowcount
        if dropped:
            print(f"dropped {dropped} legacy customer-release branch rows")

        # Final summary
        cur.execute("SELECT COUNT(*) AS n FROM branches WHERE project_fk=%s", (project_id,))
        print(f"  branches: {cur.fetchone()['n']}")
        cur.execute(
            "SELECT COUNT(*) AS n FROM builds WHERE branch_fk IN "
            "(SELECT id FROM branches WHERE project_fk=%s)",
            (project_id,),
        )
        print(f"  builds:   {cur.fetchone()['n']}")
        cur.execute(
            "SELECT COUNT(*) AS n FROM customer_releases WHERE build_fk IN "
            "(SELECT b.id FROM builds b JOIN branches br ON b.branch_fk=br.id "
            "WHERE br.project_fk=%s)",
            (project_id,),
        )
        print(f"  customer_releases: {cur.fetchone()['n']}")

    conn.close()
    print("done.")


if __name__ == '__main__':
    main()
