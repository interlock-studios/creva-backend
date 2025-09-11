#!/bin/bash

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Config
PROJECT_ID="${PROJECT_ID:-sets-ai}"
SECURITY_POLICY_NAME="${SECURITY_POLICY_NAME:-workout-parser-security-policy-allowlist}"
BACKEND_SERVICE_NAME="${BACKEND_SERVICE_NAME:-workout-parser-backend-v2}"

echo -e "${BLUE}🛡️ Creating STRICT Cloud Armor allowlist policy${NC}"
echo -e "${YELLOW}This will DENY all traffic by default and ALLOW only active API endpoints.${NC}"

# Create policy (idempotent)
gcloud compute security-policies create "$SECURITY_POLICY_NAME" \
  --description "Strict allowlist: only active API endpoints allowed; everything else denied" \
  --project="$PROJECT_ID" 2>/dev/null || echo "Policy $SECURITY_POLICY_NAME already exists"

echo -e "${YELLOW}Cleaning existing rules to avoid conflicts (keeping default)...${NC}"
EXISTING_RULE_PRIORITIES=$(gcloud compute security-policies describe "$SECURITY_POLICY_NAME" \
  --project="$PROJECT_ID" --format="get(rules[].priority)" 2>/dev/null || true)
if [ -n "$EXISTING_RULE_PRIORITIES" ]; then
  # Delete all existing non-default rules to ensure clean slate
  while IFS= read -r p; do
    if [[ "$p" =~ ^[0-9]+$ ]] && [ "$p" != "2147483647" ]; then
      gcloud compute security-policies rules delete "$p" \
        --security-policy="$SECURITY_POLICY_NAME" \
        --project="$PROJECT_ID" --quiet || true
    fi
  done <<< "$EXISTING_RULE_PRIORITIES"
fi

echo -e "${BLUE}Skipping WAF deny rules to avoid false positives; rely on pure path allowlist.${NC}"

echo -e "${BLUE}Adding path ALLOW rules for active endpoints...${NC}"
# Enumerated active endpoints (from FastAPI routers)
# Public endpoints:
gcloud compute security-policies rules create 1000 \
  --security-policy="$SECURITY_POLICY_NAME" \
  --expression "request.path == '/health' || request.path == '/status' || request.path.startsWith('/health/') || request.path.startsWith('/metrics/')" \
  --action=allow \
  --description="Allow health, status, metrics" \
  --project="$PROJECT_ID" || gcloud compute security-policies rules update 1000 \
  --security-policy="$SECURITY_POLICY_NAME" \
  --expression "request.path == '/health' || request.path == '/status' || request.path.startsWith('/health/') || request.path.startsWith('/metrics/')" \
  --action=allow \
  --description="Allow health, status, metrics" \
  --project="$PROJECT_ID"

# Core API endpoints
gcloud compute security-policies rules create 1010 \
  --security-policy="$SECURITY_POLICY_NAME" \
  --expression "request.path == '/process' || request.path.startsWith('/status/')" \
  --action=allow \
  --description="Allow processing and job status" \
  --project="$PROJECT_ID" || gcloud compute security-policies rules update 1010 \
  --security-policy="$SECURITY_POLICY_NAME" \
  --expression "request.path == '/process' || request.path.startsWith('/status/')" \
  --action=allow \
  --description="Allow processing and job status" \
  --project="$PROJECT_ID"

# Non-production admin/test endpoints are blocked by app, but keep explicit allows only for non-prod docs
echo -e "${YELLOW}Optionally allowing docs in non-production via header guard...${NC}"
# We cannot detect environment at the edge reliably; safest is NOT to allow docs globally.
# So do NOT add /docs, /redoc, /openapi.json in allowlist.

echo -e "${BLUE}Adding rate limit for /process to mitigate abuse...${NC}"
gcloud compute security-policies rules create 990 \
  --security-policy="$SECURITY_POLICY_NAME" \
  --expression "request.path == '/process'" \
  --action "rate-based-ban" \
  --rate-limit-threshold-count=300 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=180 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --description="Rate limit /process" \
  --project="$PROJECT_ID" || gcloud compute security-policies rules update 990 \
  --security-policy="$SECURITY_POLICY_NAME" \
  --expression "request.path == '/process'" \
  --action "rate-based-ban" \
  --rate-limit-threshold-count=300 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=180 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --description="Rate limit /process" \
  --project="$PROJECT_ID"

echo -e "${BLUE}Skipping explicit deny lists; default deny will catch unknown paths.${NC}"

echo -e "${BLUE}Setting DEFAULT DENY catch-all...${NC}"
gcloud compute security-policies rules update 2147483647 \
  --security-policy="$SECURITY_POLICY_NAME" \
  --action=deny-403 \
  --description="Default deny all" \
  --project="$PROJECT_ID"

echo -e "${YELLOW}Attaching policy to backend service: ${BACKEND_SERVICE_NAME}${NC}"
gcloud compute backend-services update "$BACKEND_SERVICE_NAME" \
  --global \
  --security-policy="$SECURITY_POLICY_NAME" \
  --project="$PROJECT_ID"

echo -e "${GREEN}✅ Strict allowlist policy applied.${NC}"
echo -e "${BLUE}Policy: $SECURITY_POLICY_NAME${NC}"
echo -e "${BLUE}Backend: $BACKEND_SERVICE_NAME${NC}"

echo -e "${YELLOW}Tip:${NC} Use 'make security-logs' to watch edge denials."


