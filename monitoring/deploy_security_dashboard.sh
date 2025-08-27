#!/bin/bash

# Deploy Security Monitoring Dashboard to Google Cloud Monitoring
# This script creates a comprehensive security dashboard for monitoring threats and attacks

set -e

# Configuration
PROJECT_ID=${GOOGLE_CLOUD_PROJECT_ID:-$(gcloud config get-value project)}
DASHBOARD_FILE="security_dashboard.json"

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: PROJECT_ID not set. Please set GOOGLE_CLOUD_PROJECT_ID environment variable or configure gcloud."
    exit 1
fi

echo "🛡️  Deploying Security Monitoring Dashboard..."
echo "📋 Project: $PROJECT_ID"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

# Check if the dashboard file exists
if [ ! -f "$DASHBOARD_FILE" ]; then
    echo "❌ Error: Dashboard file '$DASHBOARD_FILE' not found."
    exit 1
fi

# Create the dashboard
echo "📊 Creating security monitoring dashboard..."

DASHBOARD_ID=$(gcloud monitoring dashboards create \
    --config-from-file="$DASHBOARD_FILE" \
    --project="$PROJECT_ID" \
    --format="value(name)" | sed 's/.*\///')

if [ $? -eq 0 ]; then
    echo "✅ Security dashboard created successfully!"
    echo "🔗 Dashboard ID: $DASHBOARD_ID"
    echo "🌐 View at: https://console.cloud.google.com/monitoring/dashboards/custom/$DASHBOARD_ID?project=$PROJECT_ID"
    
    echo ""
    echo "🛡️  Security Dashboard Features:"
    echo "   • Real-time security event monitoring"
    echo "   • Rate limit violation tracking"
    echo "   • Invalid App Check token detection"
    echo "   • Attack pattern analysis"
    echo "   • Suspicious IP address identification"
    echo "   • Comprehensive security event logs"
    
    echo ""
    echo "📈 Recommended Alerts to Set Up:"
    echo "   1. Security events > 10 per hour"
    echo "   2. Rate limit violations > 50 per hour"
    echo "   3. Invalid tokens > 20 per hour"
    echo "   4. Path traversal attempts > 5 per hour"
    
else
    echo "❌ Failed to create security dashboard"
    exit 1
fi
