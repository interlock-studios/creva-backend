#!/bin/bash

# Deploy to Google Cloud Run
echo "🚀 Deploying TikTok Workout Parser to Google Cloud Run..."

# Set your project ID (replace with your actual project ID)
PROJECT_ID="sets-ai"

# Build and deploy
gcloud builds submit --tag gcr.io/$PROJECT_ID/tiktok-workout-parser

# Deploy to Cloud Run
gcloud run deploy tiktok-workout-parser \
  --image gcr.io/$PROJECT_ID/tiktok-workout-parser \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --max-instances 10

echo "✅ Deployment complete!"
echo "🌐 Your API is now available at the URL shown above" 