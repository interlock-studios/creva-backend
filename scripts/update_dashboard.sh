#!/bin/bash

# Update Google Cloud Monitoring Dashboard
# This script updates the production dashboard with the new 11-region configuration

set -e

echo "🌍 Updating MASSIVE Global Dashboard (11 Regions)..."

# Get the project ID
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: No project configured. Run 'gcloud config set project YOUR_PROJECT_ID'"
    exit 1
fi

# Dashboard ID from the URL
DASHBOARD_ID="4fc2c0fa-8141-4031-a04d-09f512e2f6ae"

# Update the dashboard
echo "📊 Updating dashboard: $DASHBOARD_ID"
gcloud monitoring dashboards update $DASHBOARD_ID \
    --config-from-file=monitoring/dashboards/production_dashboard.json \
    --project=$PROJECT_ID

echo "✅ Dashboard updated successfully!"
echo "🌐 View your updated dashboard at:"
echo "https://console.cloud.google.com/monitoring/dashboards/builder/$DASHBOARD_ID?project=$PROJECT_ID"

echo ""
echo "🎯 New Features:"
echo "  • 🌍 MASSIVE Global Latency Comparison - All 11 Regions"
echo "  • 🌍 MASSIVE Global Request Distribution - All 11 Regions"
echo "  • 🇺🇸 US: Central (Primary), East, West"
echo "  • 🇪🇺 Europe: West1 (Belgium), West4 (Netherlands), North (Finland)"
echo "  • 🌏 Asia: Southeast (Singapore), Northeast (Tokyo), South (Mumbai)"
echo "  • 🇦🇺 Australia: Southeast (Sydney)"
echo "  • 🇧🇷 South America: East (São Paulo)"
echo ""
echo "💰 Cost: Only $15/month for 1 warm instance (us-central1)"
echo "🚀 All other 10 regions scale to zero = $0 when idle!"
