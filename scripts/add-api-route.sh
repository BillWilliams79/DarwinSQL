#!/bin/bash
# add-api-route.sh — Add a new /darwin/{table_name} route to Darwin API Gateway
#
# Usage:
#   ./add-api-route.sh <table_name>           # create route
#   ./add-api-route.sh --dry-run <table_name> # print commands without executing
#   ./add-api-route.sh --list                 # list existing resources
#
# Requires: darwinroot credentials loaded via . ~/.darwin-credentials/aws_credentials.sh
#
# Creates two methods: ANY (Cognito-authenticated) + OPTIONS (CORS preflight)
# Adds Lambda resource policy and deploys to eng stage.

set -eo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_ID="k5j0ftr527"
PARENT_ID="6k3i3k"            # /darwin resource
AUTHORIZER_ID="vd4o3k"        # DarwinAppAuthorizer (COGNITO_USER_POOLS)
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
TABLE_NAME=""

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --list) LIST_MODE=1 ;;
        *) TABLE_NAME="$arg" ;;
    esac
done

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
    echo "Usage: $0 [--dry-run] [--list] <table_name>"
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

echo "==> Adding API Gateway route: /darwin/${TABLE_NAME}"
[ "$DRY_RUN" -eq 1 ] && echo "    (dry-run mode — no changes will be made)"

# ---------------------------------------------------------------------------
# Step 1: Create resource
# ---------------------------------------------------------------------------
echo "Step 1: Creating resource /darwin/${TABLE_NAME}..."
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
# Step 9: Lambda resource policy
# ---------------------------------------------------------------------------
echo "Step 9: Adding Lambda resource policy..."
STATEMENT_ID="apigateway-darwin-${TABLE_NAME}"
SOURCE_ARN="arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*/darwin/${TABLE_NAME}"
run "aws lambda add-permission \
    --function-name \"$LAMBDA_ARN\" \
    --statement-id \"$STATEMENT_ID\" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn \"$SOURCE_ARN\""

# ---------------------------------------------------------------------------
# Step 10: Deploy to eng stage
# ---------------------------------------------------------------------------
echo "Step 10: Deploying to stage '${STAGE}'..."
run "aws apigateway create-deployment \
    --rest-api-id \"$API_ID\" \
    --stage-name \"$STAGE\" \
    --description \"Add /darwin/${TABLE_NAME} route\""

echo ""
echo "==> Route /darwin/${TABLE_NAME} created successfully."
echo "    URL: https://${API_ID}.execute-api.${REGION}.amazonaws.com/${STAGE}/darwin/${TABLE_NAME}"
