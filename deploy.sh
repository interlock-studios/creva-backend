#!/bin/bash
set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="sets-ai"
SERVICE_NAME="workout-parser-v2"
REGION="us-central1"
ARTIFACT_REGISTRY="us-central1-docker.pkg.dev"
REPOSITORY="${ARTIFACT_REGISTRY}/${PROJECT_ID}/${SERVICE_NAME}"

# Default environment
ENVIRONMENT="${ENVIRONMENT:-production}"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed. Please install it first."
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install it first."
    exit 1
fi

# Verify Google Cloud authentication
print_status "Verifying Google Cloud authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    print_error "Not authenticated with Google Cloud. Run 'gcloud auth login'"
    exit 1
fi

# Set the project
print_status "Setting project to ${PROJECT_ID}..."
gcloud config set project "${PROJECT_ID}" || {
    print_error "Failed to set project. Make sure you have access to ${PROJECT_ID}"
    exit 1
}

# Check if Artifact Registry repository exists, create if not
print_status "Checking Artifact Registry repository..."
if ! gcloud artifacts repositories describe "${SERVICE_NAME}" --location="${REGION}" &> /dev/null; then
    print_warning "Artifact Registry repository not found. Creating..."
    gcloud artifacts repositories create "${SERVICE_NAME}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="Docker repository for ${SERVICE_NAME}" || {
        print_error "Failed to create Artifact Registry repository"
        exit 1
    }
fi

# Configure Docker for Artifact Registry
print_status "Configuring Docker authentication for Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet || {
    print_error "Failed to configure Docker authentication"
    exit 1
}

# Generate image tag with timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
IMAGE_TAG="${REPOSITORY}/${SERVICE_NAME}:${TIMESTAMP}"
LATEST_TAG="${REPOSITORY}/${SERVICE_NAME}:latest"
ENV_TAG="${REPOSITORY}/${SERVICE_NAME}:${ENVIRONMENT}"

# Build the Docker image
print_status "Building Docker image..."
docker buildx build \
    --platform linux/amd64 \
    -t "${IMAGE_TAG}" \
    -t "${LATEST_TAG}" \
    -t "${ENV_TAG}" \
    --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    --build-arg VERSION="${TIMESTAMP}" \
    . || {
    print_error "Docker build failed"
    exit 1
}

# Push the image to Artifact Registry
print_status "Pushing image to Artifact Registry..."
docker push "${IMAGE_TAG}" || {
    print_error "Failed to push image"
    exit 1
}
docker push "${LATEST_TAG}"
docker push "${ENV_TAG}"

# Prepare Cloud Run deployment args
DEPLOY_ARGS=(
    "${SERVICE_NAME}"
    "--image" "${IMAGE_TAG}"
    "--platform" "managed"
    "--region" "${REGION}"
    "--allow-unauthenticated"
    "--memory" "2Gi"
    "--cpu" "2"
    "--timeout" "900"
    "--max-instances" "10"
    "--min-instances" "0"
    "--concurrency" "100"
    "--cpu-throttling"
    "--execution-environment" "gen2"
    "--service-account" "${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
)

# Add environment-specific configurations
if [[ "${ENVIRONMENT}" == "production" ]]; then
    DEPLOY_ARGS+=(
        "--min-instances" "1"
        "--cpu-boost"
    )
else
    DEPLOY_ARGS+=(
        "--tag" "${ENVIRONMENT}"
        "--no-traffic"
    )
fi

# Check if service account exists
SERVICE_ACCOUNT="${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT}" &> /dev/null; then
    print_status "Creating service account..."
    gcloud iam service-accounts create "${SERVICE_NAME}" \
        --display-name="${SERVICE_NAME} Service Account" || {
        print_error "Failed to create service account"
        exit 1
    }
    
    # Grant necessary permissions
    print_status "Granting permissions to service account..."
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${SERVICE_ACCOUNT}" \
        --role="roles/aiplatform.user" --quiet
else
    print_status "Service account already exists: ${SERVICE_ACCOUNT}"
fi

# Check if secrets exist in Secret Manager
print_status "Verifying secrets in Secret Manager..."
SECRETS_MISSING=false

if ! gcloud secrets describe "scrapecreators-api-key" &> /dev/null; then
    print_warning "Secret 'scrapecreators-api-key' not found in Secret Manager"
    print_warning "Create it with: gcloud secrets create scrapecreators-api-key --data-file=- < <(echo -n 'YOUR_API_KEY')"
    SECRETS_MISSING=true
fi

if [[ "${SECRETS_MISSING}" == "true" ]]; then
    print_error "Required secrets are missing. Please create them before deploying."
    exit 1
fi

# Grant secret access to service account
print_status "Granting secret access to service account..."
gcloud secrets add-iam-policy-binding "scrapecreators-api-key" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" --quiet || true

# Set environment variables using Secret Manager
DEPLOY_ARGS+=(
    "--set-env-vars" "GOOGLE_CLOUD_PROJECT_ID=${PROJECT_ID}"
    "--set-env-vars" "ENVIRONMENT=${ENVIRONMENT}"
    "--set-env-vars" "RATE_LIMIT_REQUESTS=999999"
    "--set-env-vars" "RATE_LIMIT_WINDOW=60"
    "--set-secrets" "SCRAPECREATORS_API_KEY=scrapecreators-api-key:latest"
)

# Deploy to Cloud Run
print_status "Deploying to Cloud Run (environment: ${ENVIRONMENT})..."
gcloud run deploy "${DEPLOY_ARGS[@]}" || {
    print_error "Deployment failed"
    exit 1
}

# Get the service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --platform managed \
    --region "${REGION}" \
    --format 'value(status.url)')

# Validate deployment health
print_status "Validating deployment health..."

# Wait for service to be ready (max 5 minutes)
for i in {1..30}; do
    print_status "Health check attempt $i/30..."
    
    if curl -f -s --max-time 10 "${SERVICE_URL}/health" > /dev/null; then
        print_status "✅ Health check passed!"
        break
    fi
    
    if [ $i -eq 30 ]; then
        print_error "❌ Health check failed after 5 minutes"
        
        if [[ "${ENVIRONMENT}" == "production" ]]; then
            print_error "Rolling back deployment..."
            
            # Get previous revision
            PREVIOUS_REVISION=$(gcloud run revisions list \
                --service="${SERVICE_NAME}" --region="${REGION}" \
                --format='value(metadata.name)' --limit=2 | tail -n 1)
            
            if [ ! -z "$PREVIOUS_REVISION" ]; then
                print_warning "Rolling back to revision: $PREVIOUS_REVISION"
                gcloud run services update-traffic "${SERVICE_NAME}" \
                    --to-revisions="$PREVIOUS_REVISION=100" \
                    --region="${REGION}"
            fi
        fi
        
        exit 1
    fi
    
    sleep 10
done

# Run smoke tests
print_status "Running smoke tests..."

# Test health endpoint structure
HEALTH_RESPONSE=$(curl -s "${SERVICE_URL}/health")
if ! echo "$HEALTH_RESPONSE" | jq -e '.status' > /dev/null 2>&1; then
    print_error "❌ Health endpoint returned invalid JSON"
    exit 1
fi

HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status')
if [ "$HEALTH_STATUS" != "healthy" ] && [ "$HEALTH_STATUS" != "degraded" ]; then
    print_error "❌ Health status is: $HEALTH_STATUS"
    exit 1
fi

print_status "✅ Health validation passed!"

# If staging, show how to route traffic
if [[ "${ENVIRONMENT}" != "production" ]]; then
    print_warning "Deployed to staging. To route traffic to this revision:"
    print_warning "gcloud run services update-traffic ${SERVICE_NAME} --to-tags=${ENVIRONMENT}=100 --region=${REGION}"
    print_warning "Staging URL: ${SERVICE_URL}/tag/${ENVIRONMENT}"
else
    print_status "Production URL: ${SERVICE_URL}"
fi

print_status "✅ API deployment complete!"

# Deploy Worker Service
print_status "Deploying Worker Service..."

# Check if worker service account exists
WORKER_SA="workout-parser-v2-worker@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "${WORKER_SA}" >/dev/null 2>&1; then
    print_status "Creating worker service account..."
    gcloud iam service-accounts create workout-parser-v2-worker \
        --display-name="Workout Parser V2 Worker Service Account"
    
    # Grant necessary permissions
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${WORKER_SA}" \
        --role="roles/datastore.user" \
        --quiet
    
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${WORKER_SA}" \
        --role="roles/aiplatform.user" \
        --quiet
fi

# Deploy worker service
gcloud run deploy workout-parser-v2-worker \
    --image "${IMAGE_TAG}" \
    --region "${REGION}" \
    --platform managed \
    --allow-unauthenticated \
    --memory 4Gi \
    --cpu 4 \
    --timeout 300 \
    --concurrency 10 \
    --max-instances 50 \
    --min-instances 3 \
    --cpu-boost \
    --port 8081 \
    --command python \
    --args=-m,src.worker.worker_service \
    --set-env-vars "GOOGLE_CLOUD_PROJECT_ID=${PROJECT_ID},ENVIRONMENT=${ENVIRONMENT},WORKER_BATCH_SIZE=10,WORKER_POLLING_INTERVAL=1,RATE_LIMIT_REQUESTS=999999,RATE_LIMIT_WINDOW=60" \
    --set-secrets "SCRAPECREATORS_API_KEY=scrapecreators-api-key:latest" \
    --service-account "${WORKER_SA}" || {
    print_warning "Worker deployment failed, but API is deployed successfully"
}

# Get worker service URL
WORKER_URL=$(gcloud run services describe workout-parser-v2-worker \
    --platform managed \
    --region "${REGION}" \
    --format 'value(status.url)' 2>/dev/null || echo "Worker not deployed")

print_status "✅ Deployment complete!"
print_status "🚀 Services deployed:"
echo ""
echo "API Service: ${SERVICE_URL}"
echo "Worker Service: ${WORKER_URL}"
echo ""
print_status "Test your API:"
echo ""
echo "curl -X GET \"${SERVICE_URL}/health\""
echo ""
echo "curl -X POST \"${SERVICE_URL}/process\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"url\": \"https://www.tiktok.com/@lastairbender222/video/7518493301046119710\"}'"