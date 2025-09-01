#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ID="sets-ai"
DOMAIN="api.setsai.app"
LB_NAME="workout-parser-global-lb"
BACKEND_SERVICE_NAME="workout-parser-backend"
URL_MAP_NAME="workout-parser-url-map"
TARGET_PROXY_NAME="workout-parser-target-proxy"
FORWARDING_RULE_NAME="workout-parser-forwarding-rule"
SSL_CERT_NAME="setsai-ssl-cert"

echo -e "${BLUE}🌍 Setting up Global Load Balancer with Custom Domain${NC}"
echo -e "${BLUE}Domain: ${DOMAIN}${NC}"

# 1. Create managed SSL certificate
echo -e "${YELLOW}🔒 Creating managed SSL certificate for ${DOMAIN}...${NC}"
gcloud compute ssl-certificates create $SSL_CERT_NAME \
    --domains=$DOMAIN \
    --global \
    --project=$PROJECT_ID

# 2. Create backend service
echo -e "${YELLOW}📋 Creating backend service...${NC}"
gcloud compute backend-services create $BACKEND_SERVICE_NAME \
    --global \
    --protocol=HTTP \
    --port-name=http \
    --timeout=300 \
    --project=$PROJECT_ID

# 3. Add regional backends
echo -e "${YELLOW}🌎 Adding regional backends...${NC}"
REGIONS=("us-central1" "us-east1" "europe-west1" "asia-southeast1")

for region in "${REGIONS[@]}"; do
    echo -e "${BLUE}Adding backend for $region...${NC}"
    
    # Create serverless NEG for Cloud Run service
    gcloud compute network-endpoint-groups create workout-parser-neg-$region \
        --region=$region \
        --network-endpoint-type=serverless \
        --cloud-run-service=workout-parser-v2 \
        --project=$PROJECT_ID || echo "NEG already exists for $region"
    
    # Add backend to backend service
    gcloud compute backend-services add-backend $BACKEND_SERVICE_NAME \
        --global \
        --network-endpoint-group=workout-parser-neg-$region \
        --network-endpoint-group-region=$region \
        --project=$PROJECT_ID
done

# 4. Create URL map
echo -e "${YELLOW}🗺️ Creating URL map...${NC}"
gcloud compute url-maps create $URL_MAP_NAME \
    --default-backend-service=$BACKEND_SERVICE_NAME \
    --global \
    --project=$PROJECT_ID

# 5. Create target HTTPS proxy (with SSL)
echo -e "${YELLOW}🎯 Creating target HTTPS proxy...${NC}"
gcloud compute target-https-proxies create $TARGET_PROXY_NAME \
    --url-map=$URL_MAP_NAME \
    --ssl-certificates=$SSL_CERT_NAME \
    --global \
    --project=$PROJECT_ID

# 6. Create global forwarding rule for HTTPS
echo -e "${YELLOW}🌐 Creating global HTTPS forwarding rule...${NC}"
gcloud compute forwarding-rules create $FORWARDING_RULE_NAME \
    --global \
    --target-https-proxy=$TARGET_PROXY_NAME \
    --ports=443 \
    --project=$PROJECT_ID

# 7. Create HTTP to HTTPS redirect
echo -e "${YELLOW}🔄 Setting up HTTP to HTTPS redirect...${NC}"
gcloud compute url-maps create ${URL_MAP_NAME}-redirect \
    --default-url-redirect-response-code=301 \
    --default-url-redirect-https-redirect \
    --global \
    --project=$PROJECT_ID

gcloud compute target-http-proxies create ${TARGET_PROXY_NAME}-redirect \
    --url-map=${URL_MAP_NAME}-redirect \
    --global \
    --project=$PROJECT_ID

gcloud compute forwarding-rules create ${FORWARDING_RULE_NAME}-redirect \
    --global \
    --target-http-proxy=${TARGET_PROXY_NAME}-redirect \
    --ports=80 \
    --project=$PROJECT_ID

# 8. Get the global IP
echo -e "${GREEN}✅ Global Load Balancer setup complete!${NC}"
GLOBAL_IP=$(gcloud compute forwarding-rules describe $FORWARDING_RULE_NAME --global --format="value(IPAddress)" --project=$PROJECT_ID)

echo -e "${GREEN}🎉 Your global endpoint is ready:${NC}"
echo -e "${BLUE}Global IP: $GLOBAL_IP${NC}"
echo -e "${BLUE}Domain: https://$DOMAIN${NC}"
echo ""
echo -e "${YELLOW}📋 DNS Setup Required:${NC}"
echo -e "${BLUE}Add this A record to your DNS:${NC}"
echo -e "${GREEN}Name: api${NC}"
echo -e "${GREEN}Type: A${NC}"
echo -e "${GREEN}Value: $GLOBAL_IP${NC}"
echo -e "${GREEN}TTL: 300${NC}"
echo ""
echo -e "${YELLOW}⏰ Notes:${NC}"
echo -e "• SSL certificate will be provisioned automatically (takes 10-60 minutes)"
echo -e "• DNS propagation may take up to 24 hours"
echo -e "• Load balancer will be active in 5-10 minutes"
echo ""
echo -e "${BLUE}💰 Estimated cost: ~$18/month for the load balancer${NC}"

# Test when ready
echo -e "${YELLOW}🧪 Testing will be available after DNS setup...${NC}"
echo -e "${BLUE}Test command: curl -s https://$DOMAIN/health | jq .${NC}"

