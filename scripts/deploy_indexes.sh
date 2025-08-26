#!/bin/bash

# Deploy Firestore indexes for optimized queue queries
# Run this script to create the necessary indexes for the queue system

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT_ID:-$(gcloud config get-value project)}

if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID not set. Please set GOOGLE_CLOUD_PROJECT_ID or configure gcloud project."
    exit 1
fi

echo "Deploying Firestore indexes for project: $PROJECT_ID"

# Check if Firebase CLI is available
if ! command -v firebase &> /dev/null; then
    echo "Error: Firebase CLI not found. Please install it with: npm install -g firebase-tools"
    exit 1
fi

# Deploy the indexes using Firebase CLI
firebase use "$PROJECT_ID"
firebase deploy --only firestore:indexes --project="$PROJECT_ID"

echo "✅ Firestore indexes deployed successfully!"
echo "Note: Index creation may take several minutes to complete in the background."
echo "Check status at: https://console.cloud.google.com/firestore/indexes?project=$PROJECT_ID"
