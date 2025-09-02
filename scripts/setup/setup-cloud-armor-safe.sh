#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ID="sets-ai"
SECURITY_POLICY_NAME="workout-parser-security-policy-safe"
BACKEND_SERVICE_NAME="workout-parser-backend-v2"

echo -e "${BLUE}🛡️ Setting up SAFE Cloud Armor Security Policy (User-Friendly)${NC}"
echo -e "${YELLOW}⚠️  This policy is designed to be LESS restrictive than your app-level security${NC}"
echo -e "${YELLOW}⚠️  It only blocks obvious attacks, not legitimate users${NC}"

# 1. Create Cloud Armor security policy
echo -e "${YELLOW}🔒 Creating SAFE Cloud Armor security policy...${NC}"
gcloud compute security-policies create $SECURITY_POLICY_NAME \
    --description "SAFE security policy - only blocks obvious attacks, preserves user experience" \
    --project=$PROJECT_ID

# 2. VERY HIGH DDoS protection threshold (much higher than app-level)
echo -e "${YELLOW}🚫 Adding SAFE DDoS protection (higher than app limits)...${NC}"
gcloud compute security-policies rules create 1000 \
    --security-policy=$SECURITY_POLICY_NAME \
    --expression "true" \
    --action "rate-based-ban" \
    --rate-limit-threshold-count=500 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=300 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --project=$PROJECT_ID

echo -e "${GREEN}✅ DDoS protection: 500 req/min per IP (vs app: 200 req/min)${NC}"

# 3. Only block EXTREME geographic risks (optional - can be disabled)
echo -e "${YELLOW}🌍 Adding minimal geographic filtering (only extreme risks)...${NC}"
# Only block North Korea for now - can expand later if needed
gcloud compute security-policies rules create 2000 \
    --security-policy=$SECURITY_POLICY_NAME \
    --expression "origin.region_code == 'KP'" \
    --action=deny-403 \
    --description="Block only extreme risk countries (North Korea)" \
    --project=$PROJECT_ID

echo -e "${GREEN}✅ Geographic blocking: Only North Korea (minimal impact)${NC}"

# 4. Only block OBVIOUS SQL injection (high confidence)
echo -e "${YELLOW}💉 Adding high-confidence SQL injection protection...${NC}"
gcloud compute security-policies rules create 3000 \
    --security-policy=$SECURITY_POLICY_NAME \
    --expression "evaluatePreconfiguredExpr('sqli-stable', ['owasp-crs-v030001-id942251-sqli', 'owasp-crs-v030001-id942420-sqli', 'owasp-crs-v030001-id942431-sqli'])" \
    --action=deny-403 \
    --description="Block only high-confidence SQL injection attempts" \
    --project=$PROJECT_ID

echo -e "${GREEN}✅ SQL injection: Only high-confidence attacks blocked${NC}"

# 5. Block only OBVIOUS XSS attempts
echo -e "${YELLOW}🔗 Adding high-confidence XSS protection...${NC}"
gcloud compute security-policies rules create 3100 \
    --security-policy=$SECURITY_POLICY_NAME \
    --expression "evaluatePreconfiguredExpr('xss-stable', ['owasp-crs-v030001-id941101-xss', 'owasp-crs-v030001-id941110-xss'])" \
    --action=deny-403 \
    --description="Block only high-confidence XSS attempts" \
    --project=$PROJECT_ID

echo -e "${GREEN}✅ XSS protection: Only obvious attacks blocked${NC}"

# 6. Block only EXTREME scanner behavior
echo -e "${YELLOW}🔍 Adding scanner detection (high threshold)...${NC}"
gcloud compute security-policies rules create 3400 \
    --security-policy=$SECURITY_POLICY_NAME \
    --expression "evaluatePreconfiguredExpr('scannerdetection-stable')" \
    --action=deny-403 \
    --description="Block known security scanners only" \
    --project=$PROJECT_ID

echo -e "${GREEN}✅ Scanner detection: Only known bad scanners blocked${NC}"

# 7. VERY lenient API rate limiting (much higher than app-level)
echo -e "${YELLOW}⏱️ Adding SAFE API rate limiting (higher than app limits)...${NC}"
gcloud compute security-policies rules create 4000 \
    --security-policy=$SECURITY_POLICY_NAME \
    --expression "request.path.matches('/process')" \
    --action "rate-based-ban" \
    --rate-limit-threshold-count=300 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=180 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --project=$PROJECT_ID

echo -e "${GREEN}✅ API rate limiting: 300 req/min per IP (vs app: 200 req/min)${NC}"

# 8. Block only OBVIOUS bad bots (not legitimate tools)
echo -e "${YELLOW}🤖 Adding minimal bad bot blocking...${NC}"
gcloud compute security-policies rules create 5000 \
    --security-policy=$SECURITY_POLICY_NAME \
    --expression "has(request.headers['user-agent']) && request.headers['user-agent'].matches('(?i).*(masscan|nmap|sqlmap|nikto|dirb|gobuster|wpscan).*')" \
    --action=deny-403 \
    --description="Block only obvious attack tools, not legitimate automation" \
    --project=$PROJECT_ID

echo -e "${GREEN}✅ Bot blocking: Only obvious attack tools (curl, wget still allowed)${NC}"

# 9. Allow everything else (default rule)
echo -e "${YELLOW}✅ Adding permissive default allow rule...${NC}"
gcloud compute security-policies rules create 2147483647 \
    --security-policy=$SECURITY_POLICY_NAME \
    --expression "true" \
    --action=allow \
    --description="Default allow rule - very permissive" \
    --project=$PROJECT_ID

echo -e "${GREEN}✅ Default: Allow all other traffic${NC}"

# 10. Attach security policy to backend service
echo -e "${YELLOW}🔗 Attaching SAFE security policy to backend service...${NC}"
gcloud compute backend-services update $BACKEND_SERVICE_NAME \
    --global \
    --security-policy=$SECURITY_POLICY_NAME \
    --project=$PROJECT_ID

echo -e "${GREEN}✅ SAFE Cloud Armor security policy setup complete!${NC}"
echo -e "${BLUE}Policy Name: $SECURITY_POLICY_NAME${NC}"
echo -e "${BLUE}Attached to: $BACKEND_SERVICE_NAME${NC}"

echo -e "${GREEN}🛡️ SAFE Security features enabled (user-friendly):${NC}"
echo -e "  • DDoS protection: 500 req/min (vs app: 200 req/min)"
echo -e "  • Geographic: Only North Korea blocked"
echo -e "  • SQL injection: Only high-confidence attacks"
echo -e "  • XSS: Only obvious attempts"
echo -e "  • Scanners: Only known attack tools"
echo -e "  • API limits: 300 req/min (vs app: 200 req/min)"
echo -e "  • Bots: Only attack tools (curl/wget allowed)"

echo -e "${YELLOW}📊 This policy is SAFER than your app-level security:${NC}"
echo -e "  • Higher rate limits than application"
echo -e "  • Only blocks obvious attacks"
echo -e "  • Preserves legitimate user access"
echo -e "  • Can be gradually tightened based on logs"

echo -e "${BLUE}Monitor with:${NC}"
echo -e "make security-logs"
echo -e "make blocked-ips"
