#!/usr/bin/env python3
"""
Seed darwin_dev with a Sample Project for the Build Visualizer (req #2606).

Idempotent — uses natural-key UPSERTs so re-runs leave the same state.

Creates:
  1 build_projects row     "Sample Project"
  1 trunk branch           (release type, project.trunk_branch_fk → here)
  35 trunk builds          positions 0..34
  3 above-side release branches  (release-1, release-2 — segment changes)
  1 sample-release branch        (Sample/Sprint Release exemplar)
  6 sub-branches                 (hotfix, bootleg, csr × 2, dev)
  ~5 dev branches off m6        (dev-a, br20, br21, br22)
  ~30 sub-branch builds          across all sub-branches
  7 customer_releases events     HP→sr1, NVIDIA→sr2, Cisco→sr3,
                                  HP+NVIDIA+Cisco+Google→r2c

Fails fast if customers (HP/NVIDIA/Cisco/Google) are missing — they MUST be
seeded by req #2604's own seed first (already done).

Usage:
    cd Lambda-Rest && . exports.sh && python3 ../DarwinSQL/scripts/seed_build_projects.py
"""
import os
import sys

import pymysql

TARGET_DATABASE = 'darwin_dev'

# Bill Williams primary user — owns the demo data
DEFAULT_CREATOR_FK = '37df7531-000d-4470-8be4-1792d8261f69'
BUILD_PROJECTS_CATEGORY_NAME = 'Build Projects'

# Demo project shape — derived from Topology/build-visualizer/builds.json
# Each tuple: (slug, branch_type, parent_branch_slug, parent_build_slug, build_count,
#              segment_major, segment_minor, segment_initial_build_number, name)
# slug is the in-script lookup key only (NOT stored in SQL).
# The trunk has segment_* declared for segment 0.
# Above-side release branches declare their NEXT trunk identity in segment_*.
DEMO_BRANCHES = [
    # slug,             branch_type,        parent_build_slug, builds_count, major, minor, name
    # Trunk: major/minor are the project's starting identity. No segment bumps.
    # Above-side releases: major/minor = the release's own identity (e.g. 5.1).
    # Sub-branches inherit major/minor from their parent build's branch at
    # creation time (the seed copies the value explicitly).
    ('trunk',           'release',          None,           35,  5,  0,  'Main'),
    ('release-1',       'release',          'm8',           3,   5,  1,  'Release 1'),
    ('release-2',       'release',          'm18',          3,   5,  2,  'Release 2'),
    ('sample-release',  'sample-release',   'm4',           4,   5,  0,  'Sample Release\nSprint Release'),
    ('r1-hotfix',       'hotfix',           'r1-3',         3,   5,  1,  'R1 Hot Fix'),
    ('r1-bootleg',      'bootleg',          'r1-3',         2,   5,  1,  'R1 Bootleg'),
    ('r1-csr-1',        'csr',              'r1-3',         2,   5,  1,  'R1 CSR'),
    ('r2-hotfix',       'hotfix',           'r2-3',         3,   5,  2,  'R2 Hot Fix'),
    ('r2-csr',          'csr',              'r2-3',         3,   5,  2,  'R2 CSR'),
    ('dev-a',           'development',      'm6',           3,   5,  0,  'Development Branches'),
    ('br20',            'development',      'm6',           1,   5,  0,  'Branch 20'),
    ('br21',            'development',      'm6',           1,   5,  0,  'Branch 21'),
]

# (branch_slug, position) -> stable build slug we use as a lookup key.
# Position is 0-indexed. Slug pattern: trunk=m{n}, release-N=r{N}-{n}, sample-release=sr{n}, etc.
def build_slug(branch_slug, position):
    if branch_slug == 'trunk':
        return f'm{position + 1}'
    if branch_slug == 'release-1':
        return f'r1-{position + 1}'
    if branch_slug == 'release-2':
        return f'r2-{position + 1}'
    if branch_slug == 'sample-release':
        return f'sr{position + 1}'
    if branch_slug == 'r1-hotfix':
        return f'h1-{position + 1}'
    if branch_slug == 'r1-bootleg':
        return f'bl1-{position + 1}'
    if branch_slug == 'r1-csr-1':
        return f'csr1-{position + 1}'
    if branch_slug == 'r2-hotfix':
        return f'h2-{position + 1}'
    if branch_slug == 'r2-csr':
        return f'csr2-{position + 1}'
    if branch_slug == 'dev-a':
        return f'da{position + 1}'
    if branch_slug == 'br20':
        return f'b20-{position + 1}'
    if branch_slug == 'br21':
        return f'b21-{position + 1}'
    return f'{branch_slug}-{position + 1}'


# Maps shipping-customer name to the build slug it received.
# Each row = one customer_releases row.
RELEASE_EVENTS = [
    ('HP',     'sr1'),
    ('NVIDIA', 'sr2'),
    ('Cisco',  'sr3'),
    ('HP',     'r2-3'),  # r2c in builds.json = r2-3 here (3rd build of release-2)
    ('NVIDIA', 'r2-3'),
    ('Cisco',  'r2-3'),
    ('Google', 'r2-3'),
]


def get_admin_connection():
    return pymysql.connect(
        host=os.environ['endpoint'],
        user=os.environ['username'],
        password=os.environ['db_password'],
        database=TARGET_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def upsert_category(cur):
    """UPSERT 'Build Projects' category for the demo creator. Returns id."""
    cur.execute(
        "SELECT id FROM categories WHERE category_name=%s AND creator_fk=%s",
        (BUILD_PROJECTS_CATEGORY_NAME, DEFAULT_CREATOR_FK),
    )
    row = cur.fetchone()
    if row:
        return row['id']
    # Categories require project_fk NOT NULL — reuse any existing project for this creator
    cur.execute(
        "SELECT id FROM projects WHERE creator_fk=%s ORDER BY id LIMIT 1",
        (DEFAULT_CREATOR_FK,),
    )
    proj_row = cur.fetchone()
    if not proj_row:
        sys.exit(f"ABORT: no projects row for creator {DEFAULT_CREATOR_FK}; cannot create category")
    cur.execute(
        "INSERT INTO categories (category_name, project_fk, creator_fk) VALUES (%s, %s, %s)",
        (BUILD_PROJECTS_CATEGORY_NAME, proj_row['id'], DEFAULT_CREATOR_FK),
    )
    return cur.lastrowid


def upsert_project(cur, category_id):
    """UPSERT 'Sample Project' build_projects row. Returns id."""
    cur.execute(
        "SELECT id FROM build_projects WHERE title=%s AND creator_fk=%s",
        ('Sample Project', DEFAULT_CREATOR_FK),
    )
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute(
        """INSERT INTO build_projects
           (title, description, project_status, category_fk, creator_fk)
           VALUES (%s, %s, %s, %s, %s)""",
        ('Sample Project',
         'Demo project for the Build Visualizer. Trunk = a release-type Branch the project links to via trunk_branch_fk.',
         'active', category_id, DEFAULT_CREATOR_FK),
    )
    return cur.lastrowid


def upsert_branch(cur, project_id, branch_type, name, parent_build_id, major, minor):
    """UPSERT one branch. Lookup key: (project_id, branch_type, name).

    parent_build_fk is INTENTIONALLY excluded from the lookup — branches are
    inserted in two passes (parent_build_fk patched after builds exist).
    Re-running with the same (project, branch_type, name) updates major/minor
    rather than inserting a duplicate.
    """
    cur.execute(
        "SELECT id FROM branches WHERE project_fk=%s AND branch_type=%s AND name<=>%s",
        (project_id, branch_type, name),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE branches SET major=%s, minor=%s WHERE id=%s",
            (major, minor, row['id']),
        )
        return row['id']
    cur.execute(
        """INSERT INTO branches
           (project_fk, branch_type, name, major, minor, parent_build_fk, creator_fk)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (project_id, branch_type, name, major, minor, parent_build_id, DEFAULT_CREATOR_FK),
    )
    return cur.lastrowid


def upsert_build(cur, branch_id, position, build_number, branch_number,
                 dot_color=None, approved_for_release=0):
    """UPSERT one build. Lookup key: (branch_id, position). UNIQUE constraint.

    build_number (B) and branch_number (b) are computed by the caller at seed
    time using the version-scheme rules — matching what the UI would compute
    once at build creation.
    """
    cur.execute(
        "SELECT id FROM builds WHERE branch_fk=%s AND position=%s",
        (branch_id, position),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            """UPDATE builds SET build_number=%s, branch_number=%s,
                     dot_color=%s, approved_for_release=%s WHERE id=%s""",
            (build_number, branch_number, dot_color, approved_for_release, row['id']),
        )
        return row['id']
    cur.execute(
        """INSERT INTO builds (branch_fk, position, build_number, branch_number,
                               dot_color, approved_for_release, creator_fk)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (branch_id, position, build_number, branch_number,
         dot_color, approved_for_release, DEFAULT_CREATOR_FK),
    )
    return cur.lastrowid


# Compute the build_number (B) and branch_number (b) for a build at
# (branch_type, position_within_branch, parent_trunk_build_number,
#  ord0_among_same_type_siblings_off_same_parent_build,
#  ord1_among_same_type_siblings_off_same_parent_build,
#  trunk_starting_build_number).
# Mirrors the design-guide §4.2 rules.
def compute_build_numbers(branch_type, position, parent_trunk_build_number,
                          ord0, ord1, trunk_starting_build_number):
    if branch_type == 'release_trunk_marker':  # internal marker; trunk handled separately
        return None
    if parent_trunk_build_number is None:
        # Trunk: monotonic from starting_build_number
        return trunk_starting_build_number + position, 0
    # Sub-branches: build_number FROZEN at parent's value; branch_number per type
    B = parent_trunk_build_number
    if branch_type in ('release', 'sample-release'):
        b = position + 1
    elif branch_type == 'csr':
        b = ord1 * 1000 + position + 1
    elif branch_type == 'hotfix':
        b = 6000 + ord0 * 100 + position + 1
    elif branch_type == 'development':
        b = 7000 + ord0 * 100 + position + 1
    elif branch_type == 'bootleg':
        b = 9000 + ord0 * 100 + position + 1
    else:
        b = position + 1
    return B, b


def upsert_release_event(cur, customer_id, build_id, notes=None):
    """UPSERT one customer_releases row. UNIQUE(customer_fk, build_fk)."""
    cur.execute(
        "SELECT id FROM customer_releases WHERE customer_fk=%s AND build_fk=%s",
        (customer_id, build_id),
    )
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute(
        """INSERT INTO customer_releases (customer_fk, build_fk, release_notes, creator_fk)
           VALUES (%s, %s, %s, %s)""",
        (customer_id, build_id, notes, DEFAULT_CREATOR_FK),
    )
    return cur.lastrowid


def lookup_customer_id(cur, customer_name):
    cur.execute(
        "SELECT id FROM customers WHERE customer_name=%s AND creator_fk=%s",
        (customer_name, DEFAULT_CREATOR_FK),
    )
    row = cur.fetchone()
    if not row:
        sys.exit(f"ABORT: customer '{customer_name}' not seeded — run req #2604 customers seed first")
    return row['id']


def main():
    conn = get_admin_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE() AS db")
        actual = cur.fetchone()['db']
        if actual != TARGET_DATABASE:
            sys.exit(f"ABORT: expected '{TARGET_DATABASE}', got '{actual}'")

        category_id = upsert_category(cur)
        print(f"category '{BUILD_PROJECTS_CATEGORY_NAME}' id={category_id}")

        project_id = upsert_project(cur, category_id)
        print(f"project 'Sample Project' id={project_id}")

        # Pass 1: create every branch row (parent_build_fk left NULL — patched
        # later once builds exist). Trunk is created first since it has no
        # parent_build dependency.
        branch_id_by_slug = {}
        for (slug, btype, parent_build_slug, count, major, minor, name) in DEMO_BRANCHES:
            bid = upsert_branch(cur, project_id, btype, name, None, major, minor)
            branch_id_by_slug[slug] = bid

        trunk_id = branch_id_by_slug['trunk']
        cur.execute(
            "UPDATE build_projects SET trunk_branch_fk=%s WHERE id=%s",
            (trunk_id, project_id),
        )
        print(f"trunk branch id={trunk_id}; project.trunk_branch_fk linked")

        # Pass 2: insert builds. Trunk builds get monotonic B; sub-branch builds
        # need their parent-trunk-build's B (FROZEN) — computed lazily as we
        # walk DEMO_BRANCHES (trunk is first, so its B values are known by the
        # time sub-branches are processed).
        TRUNK_STARTING_BUILD_NUMBER = 1
        build_id_by_slug = {}
        # parent_build_slug -> trunk B at that build (for FROZEN inheritance)
        # Populated as trunk builds are inserted.
        trunk_build_number_by_slug = {}

        # Count siblings for ord0/ord1 — group sub-branches by (branch_type, parent_build_slug).
        from collections import defaultdict
        sibling_ord = defaultdict(int)
        ord0_by_slug = {}
        for (slug, btype, parent_build_slug, count, major, minor, name) in DEMO_BRANCHES:
            if parent_build_slug is None:
                continue  # trunk
            key = (btype, parent_build_slug)
            ord0_by_slug[slug] = sibling_ord[key]
            sibling_ord[key] += 1

        for (slug, btype, parent_build_slug, count, major, minor, name) in DEMO_BRANCHES:
            branch_id = branch_id_by_slug[slug]
            for pos in range(count):
                if parent_build_slug is None:
                    # Trunk
                    B = TRUNK_STARTING_BUILD_NUMBER + pos
                    b = 0
                else:
                    parent_B = trunk_build_number_by_slug.get(parent_build_slug)
                    # If parent isn't on trunk (e.g., r1-hotfix off r1-3), walk
                    # up one level — r1-3 itself inherits from trunk's m8.
                    if parent_B is None:
                        # Find which trunk build the parent branch's parent_build is
                        # (one level up). For seed simplicity, trace via metadata.
                        for (s2, bt2, pb2, c2, mj2, mn2, n2) in DEMO_BRANCHES:
                            if s2 == None:
                                continue
                            # find a sub-branch whose any build matches parent_build_slug
                            for p2 in range(c2):
                                if build_slug(s2, p2) == parent_build_slug:
                                    # s2's parent_build_slug (one up) should be on trunk
                                    parent_B = trunk_build_number_by_slug.get(pb2)
                                    break
                            if parent_B is not None:
                                break
                    ord0 = ord0_by_slug.get(slug, 0)
                    ord1 = ord0 + 1
                    B, b = compute_build_numbers(btype, pos, parent_B, ord0, ord1, TRUNK_STARTING_BUILD_NUMBER)
                build = upsert_build(cur, branch_id, pos, B, b)
                build_id_by_slug[build_slug(slug, pos)] = build
                if parent_build_slug is None:
                    trunk_build_number_by_slug[build_slug(slug, pos)] = B
        print(f"builds inserted: {len(build_id_by_slug)} total")

        # Pass 3: patch parent_build_fk on each non-trunk branch
        for (slug, btype, parent_build_slug, count, major, minor, name) in DEMO_BRANCHES:
            if not parent_build_slug:
                continue
            branch_id = branch_id_by_slug[slug]
            parent_build_id = build_id_by_slug.get(parent_build_slug)
            if not parent_build_id:
                sys.exit(f"ABORT: parent build '{parent_build_slug}' not found for branch '{slug}'")
            cur.execute(
                "UPDATE branches SET parent_build_fk=%s WHERE id=%s",
                (parent_build_id, branch_id),
            )

        # Customer releases — fail-fast on missing customer
        for (customer_name, target_build_slug) in RELEASE_EVENTS:
            customer_id = lookup_customer_id(cur, customer_name)
            build_id = build_id_by_slug.get(target_build_slug)
            if not build_id:
                sys.exit(f"ABORT: build '{target_build_slug}' not found for release to {customer_name}")
            upsert_release_event(cur, customer_id, build_id)
            # Mark build approved_for_release=1 + clear dot_color
            cur.execute(
                "UPDATE builds SET approved_for_release=1, dot_color=NULL WHERE id=%s",
                (build_id,),
            )
        print(f"customer_releases events inserted: {len(RELEASE_EVENTS)}")

        # Final summary
        cur.execute("SELECT COUNT(*) AS n FROM build_projects WHERE creator_fk=%s", (DEFAULT_CREATOR_FK,))
        print(f"  build_projects: {cur.fetchone()['n']}")
        cur.execute("SELECT COUNT(*) AS n FROM branches WHERE project_fk=%s", (project_id,))
        print(f"  branches:       {cur.fetchone()['n']}")
        cur.execute(
            "SELECT COUNT(*) AS n FROM builds WHERE branch_fk IN (SELECT id FROM branches WHERE project_fk=%s)",
            (project_id,),
        )
        print(f"  builds:         {cur.fetchone()['n']}")
        cur.execute("SELECT COUNT(*) AS n FROM customer_releases WHERE creator_fk=%s", (DEFAULT_CREATOR_FK,))
        print(f"  customer_releases: {cur.fetchone()['n']}")

    conn.close()
    print("done.")


if __name__ == '__main__':
    main()
