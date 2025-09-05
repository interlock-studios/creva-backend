#!/bin/bash

# Simple global endpoint using Cloud Run domain mapping
PROJECT_ID="zest-45e51"
SERVICE_NAME="workout-parser-v2"

echo "🌍 Setting up simple global endpoint..."

# Get the default Cloud Run domain for us-central1 (primary)
PRIMARY_URL=$(gcloud run services describe $SERVICE_NAME --region=us-central1 --format="value(status.url)" --project=$PROJECT_ID)

echo "✅ Your global endpoint options:"
echo ""
echo "🎯 Primary endpoint (fastest setup):"
echo "   $PRIMARY_URL"
echo ""
echo "🌎 Regional endpoints:"
echo "   US Central: https://workout-parser-v2-341666880405.us-central1.run.app"
echo "   US East:    https://workout-parser-v2-341666880405.us-east1.run.app" 
echo "   Europe:     https://workout-parser-v2-341666880405.europe-west1.run.app"
echo "   Asia:       https://workout-parser-v2-341666880405.asia-southeast1.run.app"
echo ""
echo "💡 For true global load balancing, run: ./setup-global-lb.sh"

