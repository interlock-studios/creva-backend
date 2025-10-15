#!/bin/bash

# Simple global endpoint using Cloud Run domain mapping
PROJECT_ID="zest-45e51"
SERVICE_NAME="zest-parser"

echo "🌍 Setting up simple global endpoint..."

# Get the default Cloud Run domain for us-central1 (primary)
PRIMARY_URL=$(gcloud run services describe $SERVICE_NAME --region=us-central1 --format="value(status.url)" --project=$PROJECT_ID)

echo "✅ Your global endpoint options:"
echo ""
echo "🎯 Primary endpoint (fastest setup):"
echo "   $PRIMARY_URL"
echo ""
echo "🌎 Regional endpoints:"
echo "   US Central: https://zest-parser-g4zcestszq-uc.a.run.app"
echo "   US East:    https://zest-parser-g4zcestszq-ue.a.run.app" 
echo "   Europe:     https://zest-parser-g4zcestszq-ew.a.run.app"
echo "   Asia:       https://zest-parser-g4zcestszq-as.a.run.app"
echo ""
echo "💡 For true global load balancing, run: ./setup-global-lb.sh"

