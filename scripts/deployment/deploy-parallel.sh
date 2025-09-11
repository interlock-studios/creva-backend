#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="${SERVICE_NAME:-workout-parser-v2}"
PROJECT_ID="${PROJECT_ID:-sets-ai}"
PRIMARY_REGION="${PRIMARY_REGION:-us-central1}"
SECONDARY_REGIONS="${SECONDARY_REGIONS:-us-east1,us-west1,europe-west1,europe-west4,europe-north1,asia-southeast1,asia-northeast1,asia-south1,australia-southeast1,southamerica-east1}"
ENVIRONMENT="${ENVIRONMENT:-production}"
SINGLE_REGION="${SINGLE_REGION:-false}"

echo -e "${BLUE}🚀 Starting PARALLEL Multi-Region Deployment${NC}"
echo "Project: ${PROJECT_ID}"
echo "Service: ${SERVICE_NAME}"
echo "Environment: ${ENVIRONMENT}"
echo "Primary Region: ${PRIMARY_REGION}"

if [ "$SINGLE_REGION" = "true" ]; then
    echo "Mode: Single Region Only"
else
    echo "Secondary Regions: ${SECONDARY_REGIONS}"
    echo "Mode: Multi-Region PARALLEL"
fi

# Set project
echo -e "${YELLOW}📋 Setting up Google Cloud project...${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "${YELLOW}🔧 Enabling required APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com --quiet 2>/dev/null || true

if [ "$SINGLE_REGION" = "true" ]; then
    
    echo -e "${YELLOW}🏗️ Building and deploying to single region...${NC}"
    gcloud builds submit --tag ${PRIMARY_REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:${ENVIRONMENT} .

    # Deploy to Cloud Run
    echo -e "${GREEN}🚀 Deploying to Cloud Run (${PRIMARY_REGION})...${NC}"
    gcloud run deploy ${SERVICE_NAME} \
        --image ${PRIMARY_REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:${ENVIRONMENT} \
        --region ${PRIMARY_REGION} \
        --platform managed \
        --allow-unauthenticated \
        --memory 2Gi \
        --cpu 2 \
        --max-instances 50 \
        --min-instances 1 \
        --concurrency 80 \
        --set-env-vars "GOOGLE_CLOUD_PROJECT_ID=${PROJECT_ID},ENVIRONMENT=${ENVIRONMENT},MAX_CONCURRENT_PROCESSING=60,RATE_LIMIT_REQUESTS=40,MAX_DIRECT_PROCESSING=15,GEMINI_REGIONS=${PRIMARY_REGION}" \
        --quiet
else
    # Multi-region deployment - build once, deploy to all regions IN PARALLEL
    echo -e "${YELLOW}🏗️ Building Docker image...${NC}"
    gcloud builds submit --tag ${PRIMARY_REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:${ENVIRONMENT} .

    # Deploy to primary region first
    echo -e "${GREEN}🚀 Deploying to Primary Region (${PRIMARY_REGION})...${NC}"
    GEMINI_REGIONS_FORMATTED="${PRIMARY_REGION} ${SECONDARY_REGIONS//,/ }"
    
    # Deploy API service to primary
    echo -e "${BLUE}Deploying API service to ${PRIMARY_REGION}...${NC}"
    gcloud run deploy ${SERVICE_NAME} \
        --image ${PRIMARY_REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:${ENVIRONMENT} \
        --region ${PRIMARY_REGION} \
        --platform managed \
        --allow-unauthenticated \
        --memory 2Gi \
        --cpu 1 \
        --max-instances 50 \
        --min-instances 1 \
        --concurrency 80 \
        --timeout 900 \
        --cpu-throttling \
        --execution-environment gen2 \
        --set-env-vars "GOOGLE_CLOUD_PROJECT_ID=${PROJECT_ID},ENVIRONMENT=${ENVIRONMENT},MAX_CONCURRENT_PROCESSING=60,RATE_LIMIT_REQUESTS=40,MAX_DIRECT_PROCESSING=15,GEMINI_REGIONS=${GEMINI_REGIONS_FORMATTED},CLOUD_RUN_REGION=${PRIMARY_REGION},APPCHECK_REQUIRED=true" \
        --set-secrets "SCRAPECREATORS_API_KEY=scrapecreators-api-key:latest" \
        --quiet

    # Deploy Worker service to primary
    echo -e "${BLUE}Deploying Worker service to ${PRIMARY_REGION}...${NC}"
    gcloud run deploy ${SERVICE_NAME}-worker \
        --image ${PRIMARY_REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:${ENVIRONMENT} \
        --region ${PRIMARY_REGION} \
        --platform managed \
        --allow-unauthenticated \
        --memory 1Gi \
        --cpu 1 \
        --max-instances 10 \
        --min-instances 0 \
        --concurrency 1 \
        --timeout 3600 \
        --cpu-throttling \
        --execution-environment gen2 \
        --set-env-vars "GOOGLE_CLOUD_PROJECT_ID=${PROJECT_ID},ENVIRONMENT=${ENVIRONMENT},CLOUD_RUN_REGION=${PRIMARY_REGION}" \
        --set-secrets "SCRAPECREATORS_API_KEY=scrapecreators-api-key:latest" \
        --command "uvicorn" \
        --args "src.worker.worker_service:app,--host,0.0.0.0,--port,8080,--workers,1" \
        --quiet

    # Function to deploy to a single region
    deploy_to_region() {
        local region=$1
        local log_file="/tmp/deploy_${region}.log"
        
        echo -e "${BLUE}[${region}] Starting deployment...${NC}" | tee -a "$log_file"
        
        # Deploy API service
        echo -e "${BLUE}[${region}] Deploying API service...${NC}" | tee -a "$log_file"
        if gcloud run deploy ${SERVICE_NAME} \
            --image ${PRIMARY_REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:${ENVIRONMENT} \
            --region $region \
            --platform managed \
            --allow-unauthenticated \
            --memory 2Gi \
            --cpu 1 \
            --max-instances 50 \
            --min-instances 0 \
            --concurrency 80 \
            --timeout 900 \
            --cpu-throttling \
            --execution-environment gen2 \
            --set-env-vars "GOOGLE_CLOUD_PROJECT_ID=${PROJECT_ID},ENVIRONMENT=${ENVIRONMENT},MAX_CONCURRENT_PROCESSING=60,RATE_LIMIT_REQUESTS=40,MAX_DIRECT_PROCESSING=15,GEMINI_REGIONS=${GEMINI_REGIONS_FORMATTED},CLOUD_RUN_REGION=$region,APPCHECK_REQUIRED=true" \
            --set-secrets "SCRAPECREATORS_API_KEY=scrapecreators-api-key:latest" \
            --quiet >> "$log_file" 2>&1; then
            echo -e "${GREEN}[${region}] ✅ API service deployed successfully${NC}"
        else
            echo -e "${YELLOW}[${region}] ⚠️  API service deployment failed${NC}"
        fi

        # Deploy Worker service
        echo -e "${BLUE}[${region}] Deploying Worker service...${NC}" | tee -a "$log_file"
        if gcloud run deploy ${SERVICE_NAME}-worker \
            --image ${PRIMARY_REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:${ENVIRONMENT} \
            --region $region \
            --platform managed \
            --allow-unauthenticated \
            --memory 1Gi \
            --cpu 1 \
            --max-instances 10 \
            --min-instances 0 \
            --concurrency 1 \
            --timeout 3600 \
            --cpu-throttling \
            --execution-environment gen2 \
            --set-env-vars "GOOGLE_CLOUD_PROJECT_ID=${PROJECT_ID},ENVIRONMENT=${ENVIRONMENT},CLOUD_RUN_REGION=$region" \
            --set-secrets "SCRAPECREATORS_API_KEY=scrapecreators-api-key:latest" \
            --command "uvicorn" \
            --args "src.worker.worker_service:app,--host,0.0.0.0,--port,8080,--workers,1" \
            --quiet >> "$log_file" 2>&1; then
            echo -e "${GREEN}[${region}] ✅ Worker service deployed successfully${NC}"
        else
            echo -e "${YELLOW}[${region}] ⚠️  Worker service deployment failed${NC}"
        fi
        
        echo -e "${GREEN}[${region}] 🎉 Region deployment completed${NC}"
    }

    # Export the function so it can be used by parallel processes
    export -f deploy_to_region
    export SERVICE_NAME PROJECT_ID PRIMARY_REGION ENVIRONMENT GEMINI_REGIONS_FORMATTED
    export RED GREEN YELLOW BLUE NC

    # Deploy to secondary regions IN PARALLEL
    echo -e "${GREEN}🌍 Deploying to Secondary Regions IN PARALLEL...${NC}"
    echo -e "${YELLOW}⚡ This will be MUCH faster than sequential deployment!${NC}"
    
    # Convert comma-separated regions to array and run parallel deployments
    IFS=',' read -ra REGIONS <<< "${SECONDARY_REGIONS}"
    
    # Use GNU parallel if available, otherwise use background processes
    if command -v parallel >/dev/null 2>&1; then
        echo -e "${BLUE}Using GNU parallel for maximum speed...${NC}"
        printf '%s\n' "${REGIONS[@]}" | parallel -j 10 deploy_to_region {}
    else
        echo -e "${BLUE}Using background processes for parallel deployment...${NC}"
        pids=()
        
        for region in "${REGIONS[@]}"; do
            region=$(echo $region | xargs)  # trim whitespace
            deploy_to_region "$region" &
            pids+=($!)
        done
        
        # Wait for all deployments to complete
        echo -e "${YELLOW}⏳ Waiting for all ${#pids[@]} parallel deployments to complete...${NC}"
        for pid in "${pids[@]}"; do
            wait $pid
        done
    fi

    echo -e "${GREEN}🎉 All deployments completed!${NC}"
    
    # Show deployment logs summary
    echo -e "${BLUE}📋 Deployment Summary:${NC}"
    for region in "${REGIONS[@]}"; do
        region=$(echo $region | xargs)
        log_file="/tmp/deploy_${region}.log"
        if [ -f "$log_file" ]; then
            echo -e "${BLUE}--- ${region} ---${NC}"
            tail -5 "$log_file" 2>/dev/null || echo "No log available"
        fi
    done
fi

echo -e "${GREEN}🚀 Multi-Region Deployment Complete!${NC}"
echo -e "${BLUE}Primary Region: ${PRIMARY_REGION}${NC}"
if [ "$SINGLE_REGION" != "true" ]; then
    echo -e "${BLUE}Secondary Regions: ${SECONDARY_REGIONS}${NC}"
fi

# Clean up log files
rm -f /tmp/deploy_*.log 2>/dev/null || true
