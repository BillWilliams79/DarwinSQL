#!/bin/bash
# get-e2e-token.sh — Print a fresh Cognito IdToken for the E2E test user (req #3002)
#
# Used by verify-lambda-policy.sh to make authenticated requests against the
# live Darwin API Gateway when verifying route authorization post-cleanup.
#
# Requires E2E_TEST_USERNAME, E2E_TEST_PASSWORD, COGNITO_CLIENT_ID,
# COGNITO_CLIENT_SECRET — source them first (USER_PASSWORD_AUTH needs only the
# app client id/secret, not the user pool id):
#   . ~/.darwin-credentials/e2e_test_credentials.sh
#
# Usage:
#   TOKEN=$(bash DarwinSQL/scripts/get-e2e-token.sh)

set -eo pipefail

for var in E2E_TEST_USERNAME E2E_TEST_PASSWORD COGNITO_CLIENT_ID COGNITO_CLIENT_SECRET; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var not set — source ~/.darwin-credentials/e2e_test_credentials.sh first" >&2
        exit 1
    fi
done

python3 - << 'PYEOF'
import base64
import hashlib
import hmac
import os
import sys

import boto3

username = os.environ["E2E_TEST_USERNAME"]
password = os.environ["E2E_TEST_PASSWORD"]
client_id = os.environ["COGNITO_CLIENT_ID"]
client_secret = os.environ["COGNITO_CLIENT_SECRET"]
region = os.environ.get("AWS_DEFAULT_REGION", "us-west-1")

message = (username + client_id).encode("utf-8")
key = client_secret.encode("utf-8")
secret_hash = base64.b64encode(hmac.new(key, message, hashlib.sha256).digest()).decode("utf-8")

client = boto3.client("cognito-idp", region_name=region)
try:
    resp = client.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": password,
            "SECRET_HASH": secret_hash,
        },
        ClientId=client_id,
    )
except Exception as exc:
    print(f"ERROR: Cognito initiate_auth failed: {exc}", file=sys.stderr)
    sys.exit(1)

print(resp["AuthenticationResult"]["IdToken"])
PYEOF
