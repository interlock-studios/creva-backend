#!/bin/bash

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Config
PROJECT_ID="${PROJECT_ID:-creva-e6435}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-creva-parser-preview}"
IMAGE_TAG="${IMAGE_TAG:-preview}"

echo -e "${BLUE}🚀 Deploying Preview Service: ${SERVICE_NAME}${NC}"
echo -e "Project: ${PROJECT_ID} | Region: ${REGION}"

gcloud config set project ${PROJECT_ID}

echo -e "${YELLOW}🏗️ Building preview image...${NC}"
# Ensure Artifact Registry repository exists
gcloud artifacts repositories create ${SERVICE_NAME} \
  --repository-format=docker \
  --location=${REGION} \
  --description="Docker repository for ${SERVICE_NAME}" 2>/dev/null || echo "Repo ${SERVICE_NAME} already exists in ${REGION}"

gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:${IMAGE_TAG} .

echo -e "${BLUE}🚀 Deploying Cloud Run preview service...${NC}"
gcloud run deploy ${SERVICE_NAME} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:${IMAGE_TAG} \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 5 \
  --min-instances 0 \
  --concurrency 40 \
  --timeout 600 \
  --cpu-throttling \
  --execution-environment gen2 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT_ID=${PROJECT_ID},ENVIRONMENT=preview,MAX_CONCURRENT_PROCESSING=40,RATE_LIMIT_REQUESTS=30,MAX_DIRECT_PROCESSING=10,GEMINI_REGIONS=${REGION},APPCHECK_REQUIRED=false" \
  --set-secrets "SCRAPECREATORS_API_KEY=scrapecreators-api-key:latest" \
  --quiet

SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
echo -e "${GREEN}✅ Preview Deployed: ${SERVICE_URL}${NC}"

echo -e "${YELLOW}🔍 Smoke tests...${NC}"
code=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/health" || true)
echo "GET /health -> $code"
code=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/status" || true)
echo "GET /status -> $code"

echo -e "${YELLOW}🧪 Happy-path process test (real TikTok)${NC}"
# Allow override via TIKTOK_TEST_URL env var; default to known sample used in admin tests
TIKTOK_TEST_URL=${TIKTOK_TEST_URL:-"https://www.tiktok.com/@stoolpresidente/video/7463250363559218474"}
echo "Testing URL: $TIKTOK_TEST_URL"
HTTP_CODE=$(curl -s -o /tmp/preview_process.json -w "%{http_code}" \
  -X POST "$SERVICE_URL/process" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"$TIKTOK_TEST_URL\"}") || HTTP_CODE=000
echo "POST /process -> $HTTP_CODE"
if [ -f /tmp/preview_process.json ]; then
  # Show concise summary if possible
  if command -v jq >/dev/null 2>&1; then
    echo "Response summary:"
    (jq '{status, message, job_id} + (has("exercises") as $h | if $h then {exercises: (.exercises | length)} else {} end)' /tmp/preview_process.json 2>/dev/null) || cat /tmp/preview_process.json
  else
    cat /tmp/preview_process.json
  fi
fi

echo -e "${GREEN}Done.${NC}"


