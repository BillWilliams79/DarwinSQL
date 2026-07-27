#!/bin/bash
# new-migration.sh — Allocate a new DarwinSQL migration file. (req #3121)
#
# Usage:
#   bash DarwinSQL/scripts/new-migration.sh <description> [--req <id>] [--dry-run]
#
#   <description>  free text, e.g. "add pipeline seq column". Slugified to
#                  lower_snake_case for the filename.
#   --req <id>     Darwin requirement id, stamped into the file header.
#   --dry-run      print the path that WOULD be created, write nothing.
#
# Prints the absolute path of the created file on stdout (last line), plus
# structured key=value lines. Exit 0 on success, 1 on error.
#
# WHY THIS SCRIPT EXISTS (req #3121)
# ----------------------------------
# Migration numbers used to be hand-picked as max(NNN)+1 read off the author's
# OWN clone of migrations/. That listing is a snapshot of `main` taken at branch
# time, so two concurrent swarm sessions — or any session whose clone predates a
# sibling's merge — allocate the SAME number. It happened three times: 046, 050
# and 074 each carry two unrelated migrations on origin/main.
#
# The fix is to stop deriving the number from shared mutable state. A UTC
# timestamp taken from the clock at creation time is unique without any
# coordinator: two sessions would have to create a migration in the same SECOND
# to tie. Same reasoning Rails has used since 2008.
#
# NAMING CONTRACT (enforced by DarwinSQL/tests/test_migration_naming.py)
# ----------------------------------------------------------------------
#   New era:    YYYYMMDDHHMMSS_description.sql   (14 digits, UTC)
#   Legacy era: NNN_description.sql              (001-076, FROZEN — closed set)
#
# 14-digit stamps sort strictly after every legacy 0NN_ file ('0' < '2'), so
# lexicographic filename order remains apply order and the test suite's
# _get_dependency_ordered_migrations() needs no change.
#
# NEVER hand-pick a filename. Always use this script.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIGRATIONS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/migrations"

fail() {
    echo "status=error"
    echo "error=$1"
    exit 1
}

# ── Step 1: parse arguments ──────────────────────────────────────────────────
DESCRIPTION=""
REQ_ID=""
REQ_SEEN=0
DRY_RUN=0

END_OF_OPTS=0

while [ $# -gt 0 ]; do
    case "$1" in
        --)
            # Standard end-of-options sentinel, so a description may begin with
            # a dash without being mistaken for a flag.
            END_OF_OPTS=1
            ;;
        --dry-run)
            [ "$END_OF_OPTS" -eq 1 ] && { DESCRIPTION="${DESCRIPTION:+$DESCRIPTION }$1"; shift; continue; }
            DRY_RUN=1
            ;;
        --req)
            [ "$END_OF_OPTS" -eq 1 ] && { DESCRIPTION="${DESCRIPTION:+$DESCRIPTION }$1"; shift; continue; }
            [ $# -ge 2 ] || fail "--req requires a value"
            REQ_ID="$2"
            REQ_SEEN=1
            shift
            ;;
        --req=*)
            [ "$END_OF_OPTS" -eq 1 ] && { DESCRIPTION="${DESCRIPTION:+$DESCRIPTION }$1"; shift; continue; }
            REQ_ID="${1#--req=}"
            REQ_SEEN=1
            ;;
        -*)
            [ "$END_OF_OPTS" -eq 1 ] && { DESCRIPTION="${DESCRIPTION:+$DESCRIPTION }$1"; shift; continue; }
            fail "unknown option: $1 (usage: new-migration.sh <description> [--req <id>] [--dry-run])"
            ;;
        *)
            # Accept a multi-word description without forcing the caller to quote
            # it: every remaining positional is joined with a space.
            if [ -z "$DESCRIPTION" ]; then
                DESCRIPTION="$1"
            else
                DESCRIPTION="$DESCRIPTION $1"
            fi
            ;;
    esac
    shift
done

[ -n "$DESCRIPTION" ] || fail "description required (usage: new-migration.sh <description> [--req <id>] [--dry-run])"

# Validate on REQ_SEEN, not on REQ_ID being non-empty: `--req ""` and `--req=`
# are typos, not omissions, and must fail the same way `--req abc` does rather
# than silently leaving the `<id>` placeholder in the generated header. `--req 0`
# is likewise not a requirement id.
if [ "$REQ_SEEN" -eq 1 ]; then
    REQ_ID="${REQ_ID#\#}"
    case "$REQ_ID" in
        ''|*[!0-9]*) fail "--req must be digits only, got: '$REQ_ID'" ;;
    esac
    # Length-check BEFORE the arithmetic, same house rule as
    # scripts/db/rds-snapshot.sh: bash wraps `$((10#<wide>))` mod 2^64 silently,
    # so a 20-digit value would pass `-ge 1` on a wrapped-positive accident.
    # Darwin requirement ids are 4 digits; 9 leaves several orders of headroom.
    [ "${#REQ_ID}" -le 9 ] || fail "--req is implausibly large for a requirement id, got: $REQ_ID"
    [ "$((10#$REQ_ID))" -ge 1 ] || fail "--req must be a positive requirement id, got: $REQ_ID"
fi

[ -d "$MIGRATIONS_DIR" ] || fail "migrations directory not found: $MIGRATIONS_DIR"

# ── Step 2: slugify the description ──────────────────────────────────────────
# lowercase → non-alphanumerics to underscore → collapse runs → trim edges.
SLUG=$(printf '%s' "$DESCRIPTION" \
    | tr '[:upper:]' '[:lower:]' \
    | sed 's/[^a-z0-9]\{1,\}/_/g; s/^_\{1,\}//; s/_\{1,\}$//')

[ -n "$SLUG" ] || fail "description slugified to nothing: $DESCRIPTION"

# Keep filenames manageable. 60 chars of slug + 14 of stamp + "_.sql" is well
# under every filesystem limit and still readable in a directory listing.
if [ "${#SLUG}" -gt 60 ]; then
    SLUG="${SLUG:0:60}"
    SLUG="${SLUG%_}"
fi

# ── Step 3: allocate the timestamp ───────────────────────────────────────────
# UTC, always — a local-time stamp would sort wrong across a DST boundary and
# would differ between machines in the fleet.
#
# The same-second case is theoretical (two authors, same clone, same second) but
# costs one loop to handle: if the file already exists, wait a second and
# re-stamp rather than clobbering. Bounded so a wedged clock cannot hang.
STAMP=""
for _ in 1 2 3 4 5; do
    CANDIDATE=$(date -u +%Y%m%d%H%M%S)
    if [ ! -e "$MIGRATIONS_DIR/${CANDIDATE}_${SLUG}.sql" ] \
       && ! ls "$MIGRATIONS_DIR/${CANDIDATE}_"*.sql >/dev/null 2>&1; then
        STAMP="$CANDIDATE"
        break
    fi
    sleep 1
done

[ -n "$STAMP" ] || fail "could not allocate a free timestamp in 5 attempts (clock stuck?)"

case "$STAMP" in
    ??????????????) : ;;
    *) fail "date -u produced an unexpected stamp: $STAMP" ;;
esac

TARGET="$MIGRATIONS_DIR/${STAMP}_${SLUG}.sql"

echo "migration_id=$STAMP"
echo "slug=$SLUG"
echo "path=$TARGET"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "status=dry-run"
    exit 0
fi

# Re-check immediately before writing: the loop above may have raced.
[ -e "$TARGET" ] && fail "refusing to overwrite existing file: $TARGET"

# ── Step 4: write the header template ────────────────────────────────────────
REQ_LINE="-- Req #<id>: <one-line statement of the problem this migration solves>."
if [ -n "$REQ_ID" ]; then
    REQ_LINE="-- Req #${REQ_ID}: <one-line statement of the problem this migration solves>."
fi

cat > "$TARGET" <<EOF
-- ${STAMP}_${SLUG}.sql
--
${REQ_LINE}
--
-- PROBLEM.  <what is wrong today, in terms of the data, not the code>
--
-- SHAPE.    <the tables/columns/constraints this adds, and why this shape and
--           not the obvious alternative>
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands — the
--           only difference is the trailing database name, so read it twice:
--
--             python3 DarwinSQL/scripts/load_sql.py \\
--               DarwinSQL/migrations/${STAMP}_${SLUG}.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \\
--               DarwinSQL/migrations/${STAMP}_${SLUG}.sql darwin
--
--           The production command above requires
--           \`bash scripts/db/rds-snapshot.sh ${STAMP}\` to report status=ok
--           first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id ${STAMP} is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

EOF

echo "status=ok"
