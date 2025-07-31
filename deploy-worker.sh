#!/bin/bash

# Deploy script for worker service
# This script helps deploy the worker service separately from the main API

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Deploying TikTok Workout Parser Worker Service${NC}"

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}PROJECT_ID not set. Reading from .env file...${NC}"
    export $(grep -v '^#' .env | xargs)
    PROJECT_ID=$GOOGLE_CLOUD_PROJECT_ID
fi

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID or GOOGLE_CLOUD_PROJECT_ID not set${NC}"
    echo "Please set your Google Cloud project ID:"
    echo "  export PROJECT_ID=your-project-id"
    exit 1
fi

echo -e "${GREEN}Using project: $PROJECT_ID${NC}"

# Set defaults
REGION=${REGION:-us-central1}
SERVICE_NAME=${SERVICE_NAME:-tiktok-workout-worker}

# Create service account if it doesn't exist
echo -e "${YELLOW}Checking service account...${NC}"
if ! gcloud iam service-accounts describe tiktok-workout-worker@$PROJECT_ID.iam.gserviceaccount.com --project=$PROJECT_ID >/dev/null 2>&1; then
    echo "Creating service account..."
    gcloud iam service-accounts create tiktok-workout-worker \
        --display-name="TikTok Workout Worker Service Account" \
        --project=$PROJECT_ID
    
    # Grant necessary permissions
    echo "Granting permissions..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:tiktok-workout-worker@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/datastore.user"
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:tiktok-workout-worker@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/aiplatform.user"
else
    echo -e "${GREEN}Service account already exists${NC}"
fi

# Build and deploy using Cloud Build
echo -e "${YELLOW}Starting Cloud Build for worker service...${NC}"
gcloud builds submit \
    --config=cloudbuild-worker.yaml \
    --substitutions=_SERVICE_NAME=$SERVICE_NAME \
    --project=$PROJECT_ID

echo -e "${GREEN}Worker deployment complete!${NC}"
echo ""
echo "Worker service URL:"
gcloud run services describe $SERVICE_NAME --region=$REGION --project=$PROJECT_ID --format='value(status.url)'
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Set up environment variables for multiple service accounts:"
echo "   - GOOGLE_SERVICE_ACCOUNT_FILES (comma-separated paths)"
echo "   - GOOGLE_SERVICE_ACCOUNT_JSONS (|||separated JSON strings)"
echo "   - GEMINI_LOCATIONS (comma-separated locations, e.g., us-central1,us-east1)"
echo ""
echo "2. Monitor worker health:"
echo "   curl https://your-worker-url/health"
echo ""
echo "3. Check worker stats:"
echo "   curl https://your-worker-url/worker/stats"