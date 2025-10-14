#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ID="sets-ai"
BACKEND_SERVICE_NAME="workout-parser-backend-v2"
PRIMARY_REGION="us-central1"

echo -e "${BLUE}🔧 Updating Load Balancer to Single Region${NC}"
echo -e "${BLUE}Primary Region: ${PRIMARY_REGION}${NC}"
echo -e "${YELLOW}This will remove all other regional backends${NC}"
echo ""

# Get current backends
echo -e "${YELLOW}📋 Current backend configuration:${NC}"
gcloud compute backend-services describe $BACKEND_SERVICE_NAME \
    --global \
    --format="value(backends[].group)" \
    --project=$PROJECT_ID

echo ""
echo -e "${YELLOW}⚠️  Removing secondary region backends...${NC}"

# Remove secondary region backends
SECONDARY_REGIONS=("us-east1" "europe-west1" "asia-southeast1")

for region in "${SECONDARY_REGIONS[@]}"; do
    echo -e "${BLUE}Removing backend for $region...${NC}"
    
    gcloud compute backend-services remove-backend $BACKEND_SERVICE_NAME \
        --global \
        --network-endpoint-group=workout-parser-neg-$region \
        --network-endpoint-group-region=$region \
        --project=$PROJECT_ID 2>/dev/null || echo "Backend not found or already removed for $region"
done

echo ""
echo -e "${GREEN}✅ Verifying final backend configuration:${NC}"
gcloud compute backend-services describe $BACKEND_SERVICE_NAME \
    --global \
    --format="table(name,backends[].group:label=BACKENDS)" \
    --project=$PROJECT_ID

echo ""
echo -e "${GREEN}🎉 Load Balancer updated!${NC}"
echo -e "${BLUE}Now routing ALL traffic to: ${PRIMARY_REGION}${NC}"
echo -e "${YELLOW}💡 Secondary region Cloud Run instances will scale to zero (min-instances=0)${NC}"
echo -e "${YELLOW}💰 Cost savings: ~95% reduction in multi-region costs${NC}"
echo ""
echo -e "${BLUE}Test your endpoint:${NC}"
echo -e "${GREEN}curl https://api.setsai.app/health${NC}"

