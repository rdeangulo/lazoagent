#!/usr/bin/env bash
# Refresh the Shopify CLI's cached access token and mirror it into .env.
#
# The CLI stores an OAuth session with a refresh token. Running any CLI
# command exercises the refresh logic and updates the cached access token.
# We then extract it from the CLI config and write it into the backend's
# .env as SHOPIFY_ACCESS_TOKEN so the backend can keep calling the Admin API.
#
# This is a stopgap until LAZO has its own Shopify Developer organization
# and a proper Custom App with an offline (non-expiring) token.

set -euo pipefail

STORE="lazo-colombia.myshopify.com"
PROJECT_DIR="$HOME/Documents/Lazo/lazoagent"
ENV_PATH="$PROJECT_DIR/.env"
CONFIG_PATH="$HOME/Library/Preferences/shopify-cli-store-nodejs/config.json"
SCOPES="read_orders,read_customers,read_fulfillments"

log() { echo "[$(date -u +%FT%TZ)] $*"; }

# Exercise the session — CLI refreshes the cached token using the stored refresh token
if ! shopify store execute --store "$STORE" --query 'query { shop { name } }' --json >/dev/null 2>&1; then
    log "store execute failed; stored auth may be expired — attempting full auth"
    shopify store auth --store "$STORE" --scopes "$SCOPES" --json >/dev/null 2>&1 || {
        log "shopify store auth failed — interactive browser re-login required"
        exit 2
    }
fi

TOKEN=$(python3 - "$CONFIG_PATH" "$STORE" <<'PY'
import json, sys

config_path, store = sys.argv[1], sys.argv[2]
with open(config_path) as f:
    data = json.load(f)

for org in data.values():
    sessions = (((org.get("myshopify") or {}).get("com") or {}).get("sessionsByUserId") or {})
    for session in sessions.values():
        if session.get("store") == store:
            print(session.get("accessToken", ""))
            sys.exit(0)
sys.exit(1)
PY
)

if [ -z "${TOKEN}" ]; then
    log "no token found in CLI config for $STORE"
    exit 3
fi

if grep -q '^SHOPIFY_ACCESS_TOKEN=' "$ENV_PATH"; then
    sed -i '' -E "s|^SHOPIFY_ACCESS_TOKEN=.*|SHOPIFY_ACCESS_TOKEN=${TOKEN}|" "$ENV_PATH"
else
    echo "SHOPIFY_ACCESS_TOKEN=${TOKEN}" >> "$ENV_PATH"
fi

log "refreshed Shopify token for $STORE (prefix ${TOKEN:0:10})"
