#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID="zest-45e51"
LB_NAME="workout-parser-global-lb"
BACKEND_SERVICE_NAME="workout-parser-backend"
URL_MAP_NAME="workout-parser-url-map"
TARGET_PROXY_NAME="workout-parser-target-proxy"
FORWARDING_RULE_NAME="workout-parser-forwarding-rule"

echo -e "${BLUE}🌍 Setting up Global Load Balancer for Multi-Region API${NC}"

# 1. Create backend service
echo -e "${YELLOW}📋 Creating backend service...${NC}"
gcloud compute backend-services create $BACKEND_SERVICE_NAME \
    --global \
    --protocol=HTTP \
    --port-name=http \
    --health-checks-region=global \
    --project=$PROJECT_ID

# 2. Add regional backends
echo -e "${YELLOW}🌎 Adding regional backends...${NC}"
REGIONS=("us-central1" "us-east1" "europe-west1" "asia-southeast1")

for region in "${REGIONS[@]}"; do
    echo -e "${BLUE}Adding backend for $region...${NC}"
    
    # Create serverless NEG for Cloud Run service
    gcloud compute network-endpoint-groups create workout-parser-neg-$region \
        --region=$region \
        --network-endpoint-type=serverless \
        --cloud-run-service=workout-parser-v2 \
        --project=$PROJECT_ID
    
    # Add backend to backend service
    gcloud compute backend-services add-backend $BACKEND_SERVICE_NAME \
        --global \
        --network-endpoint-group=workout-parser-neg-$region \
        --network-endpoint-group-region=$region \
        --project=$PROJECT_ID
done

# 3. Create URL map
echo -e "${YELLOW}🗺️ Creating URL map...${NC}"
gcloud compute url-maps create $URL_MAP_NAME \
    --default-backend-service=$BACKEND_SERVICE_NAME \
    --global \
    --project=$PROJECT_ID

# 4. Create target HTTP proxy
echo -e "${YELLOW}🎯 Creating target proxy...${NC}"
gcloud compute target-http-proxies create $TARGET_PROXY_NAME \
    --url-map=$URL_MAP_NAME \
    --global \
    --project=$PROJECT_ID

# 5. Create global forwarding rule
echo -e "${YELLOW}🌐 Creating global forwarding rule...${NC}"
gcloud compute forwarding-rules create $FORWARDING_RULE_NAME \
    --global \
    --target-http-proxy=$TARGET_PROXY_NAME \
    --ports=80 \
    --project=$PROJECT_ID

# 6. Get the global IP
echo -e "${GREEN}✅ Global Load Balancer setup complete!${NC}"
GLOBAL_IP=$(gcloud compute forwarding-rules describe $FORWARDING_RULE_NAME --global --format="value(IPAddress)" --project=$PROJECT_ID)

echo -e "${GREEN}🎉 Your global endpoint is ready:${NC}"
echo -e "${BLUE}Global IP: $GLOBAL_IP${NC}"
echo -e "${BLUE}Global URL: http://$GLOBAL_IP${NC}"
echo -e "${YELLOW}Note: It may take 5-10 minutes for the load balancer to be fully active${NC}"

# Test the endpoint
echo -e "${YELLOW}🧪 Testing global endpoint...${NC}"
sleep 30
curl -s "http://$GLOBAL_IP/health" | jq . || echo "Load balancer still propagating..."

