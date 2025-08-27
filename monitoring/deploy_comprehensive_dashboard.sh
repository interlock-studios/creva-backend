#!/bin/bash

# Deploy Comprehensive Security Dashboard to Google Cloud Monitoring
# This script creates a full-featured security dashboard with App Check readiness indicators

set -e

# Configuration
PROJECT_ID=${GOOGLE_CLOUD_PROJECT_ID:-$(gcloud config get-value project)}
DASHBOARD_FILE="comprehensive_security_dashboard.json"
SERVICE_NAME=${CLOUD_RUN_SERVICE_NAME:-"workout-parser"}

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: PROJECT_ID not set. Please set GOOGLE_CLOUD_PROJECT_ID environment variable or configure gcloud."
    exit 1
fi

echo "🛡️  Deploying Comprehensive Security Dashboard..."
echo "📋 Project: $PROJECT_ID"
echo "🚀 Service: $SERVICE_NAME"
echo "=" * 60

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

# Verify authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null; then
    echo "❌ Error: Not authenticated with gcloud. Please run 'gcloud auth login'."
    exit 1
fi

# Check if the dashboard file exists
if [ ! -f "$DASHBOARD_FILE" ]; then
    echo "❌ Error: Dashboard file '$DASHBOARD_FILE' not found."
    exit 1
fi

# Validate JSON syntax
if ! python3 -m json.tool "$DASHBOARD_FILE" > /dev/null 2>&1; then
    echo "❌ Error: Invalid JSON in dashboard file '$DASHBOARD_FILE'."
    exit 1
fi

# Update dashboard with correct service name if needed
if [ "$SERVICE_NAME" != "workout-parser" ]; then
    echo "🔧 Updating dashboard for service: $SERVICE_NAME"
    sed -i.bak "s/workout-parser/$SERVICE_NAME/g" "$DASHBOARD_FILE"
fi

# Create the dashboard
echo "📊 Creating comprehensive security dashboard..."

DASHBOARD_ID=$(gcloud monitoring dashboards create \
    --config-from-file="$DASHBOARD_FILE" \
    --project="$PROJECT_ID" \
    --format="value(name)" 2>/dev/null | sed 's/.*\///')

if [ $? -eq 0 ] && [ -n "$DASHBOARD_ID" ]; then
    echo "✅ Comprehensive security dashboard created successfully!"
    echo "🔗 Dashboard ID: $DASHBOARD_ID"
    echo "🌐 View at: https://console.cloud.google.com/monitoring/dashboards/custom/$DASHBOARD_ID?project=$PROJECT_ID"
    
    echo ""
    echo "🛡️  Dashboard Features:"
    echo "   📊 App Check Readiness Indicator (🚦 RED/YELLOW/GREEN)"
    echo "   📈 Real-time security metrics and trends"
    echo "   🚨 Threat detection and attack patterns"
    echo "   📱 API performance monitoring"
    echo "   🌍 Geographic and traffic distribution"
    echo "   📋 Comprehensive security event logs"
    
    echo ""
    echo "🚦 App Check Readiness Guide:"
    echo "   🟢 GREEN (80%+ verified): Safe to enforce App Check"
    echo "   🟡 YELLOW (50-79% verified): Monitor before enforcing"
    echo "   🔴 RED (<50% verified): Do not enforce App Check yet"
    
    echo ""
    echo "📈 Recommended Monitoring Alerts:"
    echo "   1. App Check readiness drops below 70%"
    echo "   2. Security events > 10 per hour"
    echo "   3. Rate limit violations > 100 per hour"
    echo "   4. Invalid tokens > 50 per hour"
    echo "   5. Response time P95 > 5 seconds"
    
    echo ""
    echo "🔧 Next Steps:"
    echo "   1. Monitor the dashboard for 24-48 hours"
    echo "   2. When readiness indicator is GREEN, enable App Check enforcement"
    echo "   3. Set up alerting policies for security events"
    echo "   4. Review geographic distribution for unusual patterns"
    
    # Create alerting policies
    echo ""
    echo "🚨 Creating recommended alerting policies..."
    
    # App Check Readiness Alert
    cat > /tmp/appcheck_readiness_alert.yaml << EOF
displayName: "App Check Readiness Alert"
documentation:
  content: "App Check readiness has dropped below safe threshold"
conditions:
- displayName: "App Check Readiness Below 70%"
  conditionThreshold:
    filter: 'resource.type="cloud_run_revision" AND jsonPayload.readiness_percentage<70'
    comparison: COMPARISON_LESS_THAN
    thresholdValue: 70
    duration: 300s
alertStrategy:
  autoClose: 86400s
enabled: true
EOF

    # Security Events Alert  
    cat > /tmp/security_events_alert.yaml << EOF
displayName: "High Security Events Alert"
documentation:
  content: "Unusual number of security events detected"
conditions:
- displayName: "Security Events > 10/hour"
  conditionThreshold:
    filter: 'resource.type="cloud_run_revision" AND jsonPayload.security_event!=""'
    comparison: COMPARISON_GREATER_THAN
    thresholdValue: 10
    duration: 3600s
    aggregations:
    - alignmentPeriod: 3600s
      perSeriesAligner: ALIGN_COUNT
      crossSeriesReducer: REDUCE_SUM
alertStrategy:
  autoClose: 86400s
enabled: true
EOF

    # Deploy alerts (optional)
    read -p "🚨 Create recommended alerting policies? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Creating alerting policies..."
        
        gcloud alpha monitoring policies create \
            --policy-from-file=/tmp/appcheck_readiness_alert.yaml \
            --project="$PROJECT_ID" 2>/dev/null && \
            echo "✅ App Check readiness alert created"
        
        gcloud alpha monitoring policies create \
            --policy-from-file=/tmp/security_events_alert.yaml \
            --project="$PROJECT_ID" 2>/dev/null && \
            echo "✅ Security events alert created"
        
        # Cleanup temp files
        rm -f /tmp/appcheck_readiness_alert.yaml /tmp/security_events_alert.yaml
    fi
    
else
    echo "❌ Failed to create comprehensive security dashboard"
    echo "💡 Check that you have monitoring.dashboards.create permission"
    exit 1
fi

# Restore original dashboard file if we modified it
if [ -f "$DASHBOARD_FILE.bak" ]; then
    mv "$DASHBOARD_FILE.bak" "$DASHBOARD_FILE"
fi

echo ""
echo "🎉 Deployment complete! Your comprehensive security dashboard is ready."
echo "📊 Monitor App Check readiness and security metrics in real-time."
