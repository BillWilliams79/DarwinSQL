#!/bin/bash
# add-api-route.sh — Add a new /{database}/{table_name} route to Darwin API Gateway
#
# Usage:
#   ./add-api-route.sh <table_name>                              # create /darwin route (prod)
#   ./add-api-route.sh --database=darwin_dev <table_name>        # create /darwin_dev route (dev)
#   ./add-api-route.sh --database=darwin --no-deploy <table>     # skip stage deployment
#   ./add-api-route.sh --dry-run <table_name>                    # print commands without executing
#   ./add-api-route.sh --list                                    # list existing resources
#
# Requires: darwinroot credentials loaded via . ~/.darwin-credentials/aws_credentials.sh
#
# Creates two methods: ANY (Cognito-authenticated) + OPTIONS (CORS preflight).
# Optionally adds Lambda resource policy and deploys to eng stage.
#
# Req #2380 changes (2026-04-21):
#   - --database={darwin|darwin_dev}: select prod or dev parent resource.
#   - --no-deploy: suppress the per-route create-deployment. Used when batching
#     many route creations so a single final deploy covers them all.
#
# Req #3002 changes (2026-07-22, root fix):
#   - Step 9 no longer calls lambda:AddPermission for either database. Both
#     /darwin/* and /darwin_dev/* are authorized by a single per-database wildcard
#     resource-policy statement (apigateway-{database}-wildcard, req #2380). A
#     per-table lambda:AddPermission call always SUCCEEDS with a brand-new Sid
#     (lambda:AddPermission only raises ResourceConflictException on a duplicate
#     Sid, never because a wildcard already covers the route) — so the old "will
#     NO-OP safely" claim was false, and every route added since April 2026 had
#     silently deposited a redundant ~350-byte statement toward the Lambda's
#     20 KB resource-policy ceiling (shared by 6 APIs).
#   - Step 9 now VERIFIES wildcard coverage via source-ARN pattern match
#     (aws lambda get-policy, read-only) before skipping. If the wildcard is
#     confirmed present, the route needs no additional statement — zero AWS
#     mutation, zero bytes added. If the wildcard is NOT found, that is a real
#     authorization gap: the script exits with an error rather than silently
#     adding a per-table statement or silently continuing. Fixing a genuine gap
#     requires an AWS Architect consult (data-architect-charter.md), not a
#     script-level workaround.

set -eo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_ID="k5j0ftr527"
PARENT_ID_DARWIN="6k3i3k"           # /darwin resource
PARENT_ID_DARWIN_DEV="l80osi"       # /darwin_dev resource
AUTHORIZER_ID="vd4o3k"              # DarwinAppAuthorizer (COGNITO_USER_POOLS)
LAMBDA_ARN="arn:aws:lambda:us-west-1:617853379785:function:RestApi-MySql-Lambda"
ACCOUNT_ID="617853379785"
REGION="us-west-1"
STAGE="eng"

CORS_ALLOW_HEADERS="'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token'"
CORS_ALLOW_METHODS="'DELETE,GET,HEAD,OPTIONS,PATCH,POST,PUT'"
CORS_ALLOW_ORIGIN="'*'"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
DRY_RUN=0
LIST_MODE=0
NO_DEPLOY=0
DATABASE="darwin"       # default: prod
TABLE_NAME=""

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --list) LIST_MODE=1 ;;
        --no-deploy) NO_DEPLOY=1 ;;
        --database=*) DATABASE="${arg#--database=}" ;;
        *) TABLE_NAME="$arg" ;;
    esac
done

# Validate database selection + map to parent resource ID.
case "$DATABASE" in
    darwin)     PARENT_ID="$PARENT_ID_DARWIN" ;;
    darwin_dev) PARENT_ID="$PARENT_ID_DARWIN_DEV" ;;
    *)
        echo "ERROR: --database must be 'darwin' or 'darwin_dev' (got '$DATABASE')" >&2
        exit 2
        ;;
esac

# ---------------------------------------------------------------------------
# List mode
# ---------------------------------------------------------------------------
if [ "$LIST_MODE" -eq 1 ]; then
    echo "Existing API Gateway resources:"
    aws apigateway get-resources --rest-api-id "$API_ID" \
        --query 'items[*].[id,path]' \
        --output table
    exit 0
fi

if [ -z "$TABLE_NAME" ]; then
    echo "Usage: $0 [--dry-run] [--list] [--database=darwin|darwin_dev] [--no-deploy] <table_name>"
    exit 1
fi

# ---------------------------------------------------------------------------
# Helper: run or print a command
# ---------------------------------------------------------------------------
run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[DRY-RUN] $*"
    else
        eval "$@"
    fi
}

echo "==> Adding API Gateway route: /${DATABASE}/${TABLE_NAME}"
[ "$DRY_RUN" -eq 1 ] && echo "    (dry-run mode — no changes will be made)"
[ "$NO_DEPLOY" -eq 1 ] && echo "    (--no-deploy: stage deployment will be skipped)"

# ---------------------------------------------------------------------------
# Step 1: Create resource
# ---------------------------------------------------------------------------
echo "Step 1: Creating resource /${DATABASE}/${TABLE_NAME}..."
if [ "$DRY_RUN" -eq 0 ]; then
    RESOURCE_ID=$(aws apigateway create-resource \
        --rest-api-id "$API_ID" \
        --parent-id "$PARENT_ID" \
        --path-part "$TABLE_NAME" \
        --query 'id' --output text)
    echo "    Resource ID: $RESOURCE_ID"
else
    echo "[DRY-RUN] aws apigateway create-resource --rest-api-id $API_ID --parent-id $PARENT_ID --path-part $TABLE_NAME"
    RESOURCE_ID="RESOURCE_ID_PLACEHOLDER"
fi

# ---------------------------------------------------------------------------
# Step 2: ANY method with Cognito authorizer
# ---------------------------------------------------------------------------
echo "Step 2: Adding ANY method (Cognito auth)..."
run "aws apigateway put-method \
    --rest-api-id \"$API_ID\" \
    --resource-id \"$RESOURCE_ID\" \
    --http-method ANY \
    --authorization-type COGNITO_USER_POOLS \
    --authorizer-id \"$AUTHORIZER_ID\" \
    --no-api-key-required"

# ---------------------------------------------------------------------------
# Step 3: ANY integration (Lambda proxy)
# ---------------------------------------------------------------------------
echo "Step 3: Integrating ANY method with Lambda..."
run "aws apigateway put-integration \
    --rest-api-id \"$API_ID\" \
    --resource-id \"$RESOURCE_ID\" \
    --http-method ANY \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri \"arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations\" \
    --passthrough-behavior WHEN_NO_MATCH \
    --content-handling CONVERT_TO_TEXT"

# ---------------------------------------------------------------------------
# Step 4: ANY method response
# ---------------------------------------------------------------------------
echo "Step 4: Adding ANY method response (200)..."
run "aws apigateway put-method-response \
    --rest-api-id \"$API_ID\" \
    --resource-id \"$RESOURCE_ID\" \
    --http-method ANY \
    --status-code 200 \
    --response-models 'application/json=Empty'"

# ---------------------------------------------------------------------------
# Step 5: OPTIONS method (unauthenticated for CORS preflight)
# ---------------------------------------------------------------------------
echo "Step 5: Adding OPTIONS method (CORS preflight)..."
run "aws apigateway put-method \
    --rest-api-id \"$API_ID\" \
    --resource-id \"$RESOURCE_ID\" \
    --http-method OPTIONS \
    --authorization-type NONE \
    --no-api-key-required"

# ---------------------------------------------------------------------------
# Step 6: OPTIONS integration (MOCK)
# ---------------------------------------------------------------------------
echo "Step 6: Integrating OPTIONS with MOCK..."
if [ "$DRY_RUN" -eq 1 ]; then
    echo "[DRY-RUN] aws apigateway put-integration --rest-api-id $API_ID --resource-id $RESOURCE_ID --http-method OPTIONS --type MOCK --passthrough-behavior WHEN_NO_MATCH --request-templates 'application/json={\"statusCode\": 200}'"
else
    aws apigateway put-integration \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method OPTIONS \
        --type MOCK \
        --passthrough-behavior WHEN_NO_MATCH \
        --request-templates '{"application/json":"{\"statusCode\": 200}"}'
fi

# ---------------------------------------------------------------------------
# Step 7: OPTIONS method response with CORS headers
# ---------------------------------------------------------------------------
echo "Step 7: Adding OPTIONS method response (200 with CORS headers)..."
run "aws apigateway put-method-response \
    --rest-api-id \"$API_ID\" \
    --resource-id \"$RESOURCE_ID\" \
    --http-method OPTIONS \
    --status-code 200 \
    --response-parameters 'method.response.header.Access-Control-Allow-Headers=false,method.response.header.Access-Control-Allow-Methods=false,method.response.header.Access-Control-Allow-Origin=false' \
    --response-models 'application/json=Empty'"

# ---------------------------------------------------------------------------
# Step 8: OPTIONS integration response with CORS values
# ---------------------------------------------------------------------------
echo "Step 8: Adding OPTIONS integration response (CORS values)..."
if [ "$DRY_RUN" -eq 1 ]; then
    echo "[DRY-RUN] aws apigateway put-integration-response (CORS headers for $TABLE_NAME)"
else
    aws apigateway put-integration-response \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method OPTIONS \
        --status-code 200 \
        --response-parameters "{\"method.response.header.Access-Control-Allow-Headers\":\"'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token'\",\"method.response.header.Access-Control-Allow-Methods\":\"'DELETE,GET,HEAD,OPTIONS,PATCH,POST,PUT'\",\"method.response.header.Access-Control-Allow-Origin\":\"'*'\"}"
fi

# ---------------------------------------------------------------------------
# Step 9: Lambda resource policy — verify wildcard coverage, add nothing
#
# Both /darwin/* and /darwin_dev/* are authorized by a single per-database
# wildcard statement (apigateway-{database}-wildcard, req #2380). This tool
# never emits a per-table statement. Instead it VERIFIES the wildcard actually
# covers this route (read-only aws lambda get-policy + source-ARN match) before
# skipping. A missing wildcard is a real authorization gap — the script exits
# with an error rather than silently adding a per-table statement or silently
# continuing. There is no --skip-permission flag: the verification IS the logic.
# ---------------------------------------------------------------------------
echo "Step 9: Verifying Lambda resource-policy wildcard coverage..."
WILDCARD_SID="apigateway-${DATABASE}-wildcard"
WILDCARD_ARN="arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*/${DATABASE}/*"

if ! POLICY_JSON=$(aws lambda get-policy \
    --function-name "$LAMBDA_ARN" \
    --query Policy --output text 2>/tmp/get-policy-err); then
    echo "ERROR: could not read the Lambda resource policy for $LAMBDA_ARN — cannot" >&2
    echo "       verify wildcard coverage for /${DATABASE}/${TABLE_NAME}. Aborting" >&2
    echo "       rather than assuming coverage or adding a per-table statement." >&2
    cat /tmp/get-policy-err >&2
    exit 1
fi
if [ -z "$POLICY_JSON" ]; then
    echo "ERROR: Lambda resource policy for $LAMBDA_ARN came back empty — cannot" >&2
    echo "       verify wildcard coverage for /${DATABASE}/${TABLE_NAME}. Aborting" >&2
    echo "       rather than assuming coverage or adding a per-table statement." >&2
    exit 1
fi

WILDCARD_COVERS=$(echo "$POLICY_JSON" | jq -r \
    --arg sid "$WILDCARD_SID" --arg arn "$WILDCARD_ARN" \
    '[.Statement[] | select(.Sid == $sid) | select(.Condition.ArnLike."AWS:SourceArn" == $arn)] | length')

if [ "$WILDCARD_COVERS" -gt 0 ]; then
    echo "    OK: ${WILDCARD_SID} covers /${DATABASE}/* — no per-table statement needed."
else
    echo "ERROR: ${WILDCARD_SID} (source ARN ${WILDCARD_ARN}) was NOT found in the" >&2
    echo "       Lambda resource policy. This is a real authorization gap for" >&2
    echo "       /${DATABASE}/${TABLE_NAME}, not something to skip past. Consult the" >&2
    echo "       AWS Architect (see memory/data-architect-charter.md, 'API routes'" >&2
    echo "       section) to repair or reintroduce the wildcard before proceeding." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 10: Deploy to eng stage (skipped when --no-deploy)
# ---------------------------------------------------------------------------
if [ "$NO_DEPLOY" -eq 1 ]; then
    echo "Step 10: SKIP (--no-deploy). Remember to run create-deployment after batching."
else
    echo "Step 10: Deploying to stage '${STAGE}'..."
    run "aws apigateway create-deployment \
        --rest-api-id \"$API_ID\" \
        --stage-name \"$STAGE\" \
        --description \"Add /${DATABASE}/${TABLE_NAME} route\""
fi

echo ""
echo "==> Route /${DATABASE}/${TABLE_NAME} created successfully."
echo "    URL: https://${API_ID}.execute-api.${REGION}.amazonaws.com/${STAGE}/${DATABASE}/${TABLE_NAME}"
