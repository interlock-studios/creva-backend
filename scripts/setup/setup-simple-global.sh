#!/bin/bash

# Simple global endpoint using Cloud Run domain mapping
PROJECT_ID="creva-e6435"
SERVICE_NAME="creva-parser"

echo "🌍 Setting up simple global endpoint..."

# Get the default Cloud Run domain for us-central1 (primary)
PRIMARY_URL=$(gcloud run services describe $SERVICE_NAME --region=us-central1 --format="value(status.url)" --project=$PROJECT_ID)

echo "✅ Your global endpoint options:"
echo ""
echo "🎯 Primary endpoint (fastest setup):"
echo "   $PRIMARY_URL"
echo ""
echo "🌎 Regional endpoints:"
echo "   US Central: https://creva-parser-g4zcestszq-uc.a.run.app"
echo "   US East:    https://creva-parser-g4zcestszq-ue.a.run.app" 
echo "   Europe:     https://creva-parser-g4zcestszq-ew.a.run.app"
echo "   Asia:       https://creva-parser-g4zcestszq-as.a.run.app"
echo ""
echo "💡 For true global load balancing, run: ./setup-global-lb.sh"

