#!/bin/bash
# verify-lambda-policy.sh — Live-gated verification for the req #3002 Lambda
# resource-policy cleanup on RestApi-MySql-Lambda.
#
# NOT part of the hermetic test suite (tests/deploy/test-add-api-route-policy.sh
# covers add-api-route.sh's Step 9 logic with a mocked `aws`). This script hits
# real AWS + the real live Darwin API and needs darwinroot admin credentials and
# e2e test credentials sourced first — same rationale as BASE_URL-gated
# Playwright production tests. Rerun any time you want to reconfirm the policy
# is still minimal and every route is still authorized.
#
# Requires:
#   . ~/.darwin-credentials/aws_credentials.sh
#   . ~/.darwin-credentials/e2e_test_credentials.sh
#
# Usage:
#   bash DarwinSQL/scripts/verify-lambda-policy.sh <pre-cleanup-backup.json>
#
# <pre-cleanup-backup.json> is the full `aws lambda get-policy` envelope
# captured BEFORE the req #3002 cleanup ran (DarwinSQL/scripts/backups/
# lambda-policy-<UTC-timestamp>.json). It is the baseline for the structural
# diff — required so this script proves what actually changed, not just what
# the live policy looks like in isolation.

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

API_ID="k5j0ftr527"
LAMBDA_ARN="arn:aws:lambda:us-west-1:617853379785:function:RestApi-MySql-Lambda"
REGION="us-west-1"
STAGE="eng"
BASE_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/${STAGE}"

# The 23 Sids req #3002 removes — the redundant apigateway-darwin-<table>
# statements, all fully subsumed by apigateway-darwin-wildcard.
REMOVED_SIDS=(
    apigateway-darwin-features apigateway-darwin-test_cases
    apigateway-darwin-feature_test_cases apigateway-darwin-test_plans
    apigateway-darwin-test_plan_cases apigateway-darwin-test_runs
    apigateway-darwin-test_results apigateway-darwin-swarm_starts
    apigateway-darwin-swarm_start_sessions apigateway-darwin-agents
    apigateway-darwin-swarm_completes apigateway-darwin-swarm_complete_sessions
    apigateway-darwin-customers apigateway-darwin-build_projects
    apigateway-darwin-branches apigateway-darwin-builds
    apigateway-darwin-customer_releases apigateway-darwin-swarm_undos
    apigateway-darwin-machines apigateway-darwin-instructions
    apigateway-darwin-architecture_documents apigateway-darwin-agent_documents
    apigateway-darwin-agent_instructions
)

FAIL=0
pass() { echo "    PASS: $1"; }
fail() { echo "    FAIL: $1" >&2; FAIL=1; }

BACKUP_FILE="${1:-}"
if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "Usage: $0 <pre-cleanup-backup.json>" >&2
    echo "  (the full 'aws lambda get-policy' envelope captured before cleanup)" >&2
    exit 2
fi

for var in E2E_TEST_USERNAME E2E_TEST_PASSWORD COGNITO_CLIENT_ID COGNITO_CLIENT_SECRET; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var not set — source ~/.darwin-credentials/e2e_test_credentials.sh first" >&2
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# 1. Structural diff — live policy vs. the pre-cleanup backup
# ---------------------------------------------------------------------------
echo "1. Structural diff (live policy vs. $BACKUP_FILE)"

BEFORE_SIDS=$(jq -r '.Policy | fromjson | .Statement[].Sid' "$BACKUP_FILE" | sort)
LIVE_POLICY_TEXT=$(aws lambda get-policy --function-name "$LAMBDA_ARN" --query Policy --output text)
AFTER_SIDS=$(echo "$LIVE_POLICY_TEXT" | jq -r '.Statement[].Sid' | sort)
LIVE_BYTES=$(printf '%s' "$LIVE_POLICY_TEXT" | wc -c | tr -d ' ')

REMOVED_ACTUAL=$(comm -23 <(echo "$BEFORE_SIDS") <(echo "$AFTER_SIDS"))
ADDED_ACTUAL=$(comm -13 <(echo "$BEFORE_SIDS") <(echo "$AFTER_SIDS"))
EXPECTED_REMOVED=$(printf '%s\n' "${REMOVED_SIDS[@]}" | sort)

if [ "$REMOVED_ACTUAL" = "$EXPECTED_REMOVED" ]; then
    pass "exactly the 23 target Sids were removed, nothing more / nothing less"
else
    fail "removed-Sid set does not match the expected 23 — diff:"
    diff <(echo "$EXPECTED_REMOVED") <(echo "$REMOVED_ACTUAL") >&2 || true
fi

if [ -z "$ADDED_ACTUAL" ]; then
    pass "no new statements appeared (six-API isolation intact)"
else
    fail "unexpected new statements present: $ADDED_ACTUAL"
fi

echo "    live policy size: ${LIVE_BYTES} bytes"

# ---------------------------------------------------------------------------
# 2. Authorization regression — every existing /darwin/* and /darwin_dev/*
#    route must still be AUTHORIZED to invoke the Lambda after the cleanup.
#
#    We deliberately do NOT assert 2xx. Many routes legitimately return a
#    non-2xx status even with perfect authorization:
#      * The Build Visualizer tables (builds, branches, build_projects,
#        customers, customer_releases, ...) are a DEV-ONLY / private feature
#        that does not exist in production `darwin` (see
#        memory/builds-architect-charter.md and build-visualizer-design.md),
#        so /darwin/builds etc. correctly return an app-level 500
#        "Table 'darwin.builds' doesn't exist".
#      * The e2e user has no rows in some production tables, yielding app-level
#        404/200-empty responses.
#    Those are correct behavior and must not be flagged.
#
#    A Lambda resource-policy gap is INVISIBLE in the client status code — it
#    surfaces as a generic API Gateway 500, indistinguishable from an app 500.
#    The authoritative signal lives in the API Gateway execution log:
#    "not authorized to perform: lambda:InvokeFunction". So we fire authenticated
#    traffic at every route, then assert ZERO such events in the log window.
#    (excludes /darwin/jwt: separate Lambda, not covered by this policy.)
# ---------------------------------------------------------------------------
echo "2. Authorization regression — fire authenticated GET at every route, then scan execution logs"

TOKEN=$(bash "$SCRIPT_DIR/get-e2e-token.sh")
EXEC_LOG_GROUP="API-Gateway-Execution-Logs_${API_ID}/${STAGE}"
WINDOW_START_MS=$(( $(date +%s) * 1000 ))

ROUTES=$(aws apigateway get-resources --rest-api-id "$API_ID" --output json \
    | jq -r '.items[].path' \
    | grep -E '^/darwin(_dev)?(/.+)?$' \
    | grep -v '^/darwin/jwt$' \
    | sort)

ROUTE_COUNT=0
FORBIDDEN=0
while IFS= read -r route; do
    [ -z "$route" ] && continue
    ROUTE_COUNT=$((ROUTE_COUNT + 1))
    STATUS=$(curl -s -o /dev/null -w '%{http_code}' \
        -H "Authorization: Bearer $TOKEN" \
        "${BASE_URL}${route}")
    # A 403 is a client-visible authorization rejection (Cognito authorizer or
    # "Missing Authentication Token" for a nonexistent route/method). With a
    # valid token against enumerated real routes it should never happen; flag
    # it if it does. A resource-policy denial is NOT a 403 — it is a 500 and is
    # caught by the execution-log scan below.
    if [ "$STATUS" = "403" ]; then
        fail "GET $route -> 403 (authorizer / missing-auth-token rejection)"
        FORBIDDEN=$((FORBIDDEN + 1))
    fi
done <<< "$ROUTES"
echo "    fired $ROUTE_COUNT authenticated requests; $FORBIDDEN returned 403"

# Give the API Gateway execution logs time to propagate, then scan the window
# for the Lambda-invoke authorization-failure marker (the only reliable
# resource-policy-gap signal).
echo "    waiting ~20s for execution logs to propagate..."
sleep 20

# --query 'length(events)' emits one count per pagination page, so sum across
# lines (awk) rather than string-comparing a single value.
AUTH_RAW=$(aws logs filter-log-events \
    --log-group-name "$EXEC_LOG_GROUP" \
    --start-time "$WINDOW_START_MS" \
    --filter-pattern '?"not authorized to perform: lambda:InvokeFunction" ?"Missing Authentication Token"' \
    --region "$REGION" \
    --query 'length(events)' --output text 2>/dev/null)
AUTH_RC=$?

if [ "$AUTH_RC" -ne 0 ]; then
    fail "could not read execution logs at $EXEC_LOG_GROUP to confirm authorization"
else
    AUTH_FAILURES=$(echo "$AUTH_RAW" | awk '{s += $1} END {print s + 0}')
    if [ "$AUTH_FAILURES" -eq 0 ]; then
        pass "zero lambda:InvokeFunction authorization failures across $ROUTE_COUNT routes (authorization intact)"
    else
        fail "$AUTH_FAILURES authorization-failure event(s) in execution logs — cleanup may have removed a live grant"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "==> verify-lambda-policy: ALL CHECKS PASSED"
    exit 0
else
    echo "==> verify-lambda-policy: FAILURES DETECTED — see above" >&2
    exit 1
fi
