#!/bin/bash

# Fix GenAI Permissions Script
# This script adds the necessary IAM roles for accessing Vertex AI Gemini models

set -e

# Get project ID from environment or prompt user
PROJECT_ID=${GOOGLE_CLOUD_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}

if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID is not set. Please set GOOGLE_CLOUD_PROJECT_ID environment variable or configure gcloud project."
    exit 1
fi

echo "Fixing GenAI permissions for project: $PROJECT_ID"

# Service account names
MAIN_SA="creva-parser@${PROJECT_ID}.iam.gserviceaccount.com"
WORKER_SA="creva-parser@${PROJECT_ID}.iam.gserviceaccount.com"

# Function to grant IAM roles
grant_genai_permissions() {
    local service_account=$1
    local display_name=$2
    
    echo "Granting GenAI permissions to $display_name ($service_account)..."
    
    # Check if service account exists
    if ! gcloud iam service-accounts describe "$service_account" 2>/dev/null; then
        echo "Warning: Service account $service_account does not exist. Skipping..."
        return
    fi
    
    # Grant necessary roles
    echo "  - Adding aiplatform.user role..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$service_account" \
        --role="roles/aiplatform.user" || echo "    Failed to add aiplatform.user role"
    
    echo "  - Adding ml.developer role..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$service_account" \
        --role="roles/ml.developer" || echo "    Failed to add ml.developer role"
    
    echo "  - Adding aiplatform.serviceAgent role..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$service_account" \
        --role="roles/aiplatform.serviceAgent" || echo "    Failed to add aiplatform.serviceAgent role"
    
    echo "  - Adding datastore.user role (for Firestore access)..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$service_account" \
        --role="roles/datastore.user" || echo "    Failed to add datastore.user role"
    
    echo "  ✓ Permissions granted to $display_name"
}

# Grant permissions to main service account
grant_genai_permissions "$MAIN_SA" "Main API Service Account"

# Grant permissions to worker service account
grant_genai_permissions "$WORKER_SA" "Worker Service Account"

echo ""
echo "✅ GenAI permission fix completed!"
echo ""
echo "The following roles were added to your service accounts:"
echo "  - roles/aiplatform.user (basic AI Platform access)"
echo "  - roles/ml.developer (ML model access)"
echo "  - roles/aiplatform.serviceAgent (prediction endpoint access)"
echo "  - roles/datastore.user (Firestore read/write access)"
echo ""
echo "These roles provide the necessary permissions for:"
echo "  - aiplatform.endpoints.predict (required for Gemini model calls)"
echo "  - Access to Vertex AI services"
echo "  - ML model deployment and prediction capabilities"
echo "  - Firestore database operations (caching and queue management)"
echo ""
echo "Your application should now be able to access the Gemini 2.0 Flash Lite model."
echo "If you still encounter permission issues, please check:"
echo "  1. Vertex AI API is enabled in your project"
echo "  2. The model exists in the us-central1 region"
echo "  3. Your application is using the correct service account"
