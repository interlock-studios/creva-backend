#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ID="zest-45e51"
DOMAIN="api.zestai.app"
BACKEND_SERVICE_NAME="zest-parser-backend"
URL_MAP_NAME="zest-parser-url-map"
TARGET_PROXY_NAME="zest-parser-target-proxy"
FORWARDING_RULE_NAME="zest-parser-forwarding-rule"
SSL_CERT_NAME="zestai-ssl-cert"

echo -e "${BLUE}🌍 Setting up Global Load Balancer with Custom Domain${NC}"
echo -e "${BLUE}Domain: ${DOMAIN}${NC}"

# 1. SSL certificate already created, check status
echo -e "${YELLOW}🔒 Checking SSL certificate status...${NC}"
gcloud compute ssl-certificates describe $SSL_CERT_NAME --global --project=$PROJECT_ID

# 2. Create backend service (without timeout for serverless)
echo -e "${YELLOW}📋 Creating backend service...${NC}"
gcloud compute backend-services create $BACKEND_SERVICE_NAME \
    --global \
    --protocol=HTTP \
    --project=$PROJECT_ID || echo "Backend service already exists"

# 2.1. Setup SAFE Cloud Armor security policy
echo -e "${YELLOW}🛡️ Setting up SAFE Cloud Armor security policy...${NC}"
SECURITY_POLICY_NAME="workout-parser-security-policy-safe"

# Create security policy if it doesn't exist
gcloud compute security-policies create $SECURITY_POLICY_NAME \
    --description "Security policy for workout parser API" \
    --project=$PROJECT_ID 2>/dev/null || echo "Security policy already exists"

# Add SAFE DDoS protection (higher than app limits)
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
    --project=$PROJECT_ID 2>/dev/null || echo "DDoS rule already exists"

# Add SQL injection protection
gcloud compute security-policies rules create 3000 \
    --security-policy=$SECURITY_POLICY_NAME \
    --expression "evaluatePreconfiguredExpr('sqli-stable')" \
    --action=deny-403 \
    --description="Block SQL injection attempts" \
    --project=$PROJECT_ID 2>/dev/null || echo "SQL injection rule already exists"

# Add default allow rule
gcloud compute security-policies rules create 2147483647 \
    --security-policy=$SECURITY_POLICY_NAME \
    --expression "true" \
    --action=allow \
    --description="Default allow rule" \
    --project=$PROJECT_ID 2>/dev/null || echo "Default rule already exists"

# Attach security policy to backend service
gcloud compute backend-services update $BACKEND_SERVICE_NAME \
    --global \
    --security-policy=$SECURITY_POLICY_NAME \
    --project=$PROJECT_ID || echo "Security policy already attached"

# 3. Add regional backends (NEGs already exist)
echo -e "${YELLOW}🌎 Adding regional backends...${NC}"
REGIONS=("us-central1" "us-east1" "europe-west1" "asia-southeast1")

for region in "${REGIONS[@]}"; do
    echo -e "${BLUE}Adding backend for $region...${NC}"
    
    # Add backend to backend service
    gcloud compute backend-services add-backend $BACKEND_SERVICE_NAME \
        --global \
        --network-endpoint-group=zest-parser-neg-$region \
        --network-endpoint-group-region=$region \
        --project=$PROJECT_ID || echo "Backend already added for $region"
done

# 4. Create URL map
echo -e "${YELLOW}🗺️ Creating URL map...${NC}"
gcloud compute url-maps create $URL_MAP_NAME \
    --default-service=$BACKEND_SERVICE_NAME \
    --global \
    --project=$PROJECT_ID || echo "URL map already exists"

# 5. Create target HTTPS proxy
echo -e "${YELLOW}🎯 Creating target HTTPS proxy...${NC}"
gcloud compute target-https-proxies create $TARGET_PROXY_NAME \
    --url-map=$URL_MAP_NAME \
    --ssl-certificates=$SSL_CERT_NAME \
    --global \
    --project=$PROJECT_ID || echo "HTTPS proxy already exists"

# 6. Create global forwarding rule for HTTPS
echo -e "${YELLOW}🌐 Creating global HTTPS forwarding rule...${NC}"
gcloud compute forwarding-rules create $FORWARDING_RULE_NAME \
    --global \
    --target-https-proxy=$TARGET_PROXY_NAME \
    --ports=443 \
    --project=$PROJECT_ID || echo "HTTPS forwarding rule already exists"

# 7. Create HTTP redirect
echo -e "${YELLOW}🔄 Setting up HTTP to HTTPS redirect...${NC}"
gcloud compute url-maps create ${URL_MAP_NAME}-redirect \
    --global \
    --project=$PROJECT_ID || echo "Redirect URL map already exists"

# Add redirect rule
gcloud compute url-maps edit ${URL_MAP_NAME}-redirect --global --project=$PROJECT_ID || echo "Manual redirect setup needed"

gcloud compute target-http-proxies create ${TARGET_PROXY_NAME}-redirect \
    --url-map=${URL_MAP_NAME}-redirect \
    --global \
    --project=$PROJECT_ID || echo "HTTP proxy already exists"

gcloud compute forwarding-rules create ${FORWARDING_RULE_NAME}-redirect \
    --global \
    --target-http-proxy=${TARGET_PROXY_NAME}-redirect \
    --ports=80 \
    --project=$PROJECT_ID || echo "HTTP forwarding rule already exists"

# 8. Get the global IP
echo -e "${GREEN}✅ Getting global IP...${NC}"
GLOBAL_IP=$(gcloud compute forwarding-rules describe $FORWARDING_RULE_NAME --global --format="value(IPAddress)" --project=$PROJECT_ID 2>/dev/null)

if [ -z "$GLOBAL_IP" ]; then
    echo -e "${YELLOW}⏰ Load balancer still setting up, checking in a moment...${NC}"
    sleep 10
    GLOBAL_IP=$(gcloud compute forwarding-rules describe $FORWARDING_RULE_NAME --global --format="value(IPAddress)" --project=$PROJECT_ID 2>/dev/null)
fi

echo -e "${GREEN}🎉 Your global endpoint setup:${NC}"
echo -e "${BLUE}Global IP: $GLOBAL_IP${NC}"
echo -e "${BLUE}Domain: https://$DOMAIN${NC}"
echo ""
echo -e "${YELLOW}📋 DNS Setup Required:${NC}"
echo -e "${BLUE}Add this A record to your DNS:${NC}"
echo -e "${GREEN}Name: api${NC}"
echo -e "${GREEN}Type: A${NC}"
echo -e "${GREEN}Value: $GLOBAL_IP${NC}"
echo -e "${GREEN}TTL: 300${NC}"

