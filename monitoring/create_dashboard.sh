#!/bin/bash
set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PROJECT_ID="sets-ai"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed. Please install it first."
    exit 1
fi

# Set the project
print_status "Setting project to ${PROJECT_ID}..."
gcloud config set project "${PROJECT_ID}" || {
    print_error "Failed to set project. Make sure you have access to ${PROJECT_ID}"
    exit 1
}

# Enable Monitoring API if not already enabled
print_status "Enabling Monitoring API..."
gcloud services enable monitoring.googleapis.com || {
    print_error "Failed to enable Monitoring API"
    exit 1
}

# Create the dashboard
print_status "Creating Firebase App Check monitoring dashboard..."
DASHBOARD_ID=$(gcloud monitoring dashboards create \
    --config-from-file=monitoring/comprehensive_appcheck_dashboard.json \
    --format="value(name)")

if [[ $? -eq 0 && -n "$DASHBOARD_ID" ]]; then
    # Extract the dashboard ID from the full name
    DASHBOARD_SHORT_ID=$(basename "$DASHBOARD_ID")
    print_status "✅ Dashboard created successfully!"
    print_status "Dashboard ID: ${DASHBOARD_SHORT_ID}"
    print_status "🌐 View dashboard at: https://console.cloud.google.com/monitoring/dashboards/custom/${DASHBOARD_SHORT_ID}?project=${PROJECT_ID}"
else
    print_error "Failed to create dashboard"
    exit 1
fi

# Create alerting policies
print_status "Creating alerting policies for App Check monitoring..."

# Alert for high percentage of unverified requests
cat > /tmp/unverified_requests_alert.json << EOF
{
  "displayName": "High Unverified App Check Requests",
  "documentation": {
    "content": "Alert when more than 80% of requests are unverified, indicating you should consider enabling App Check enforcement.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Unverified request rate > 80%",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"workout-parser\" AND jsonPayload.event_type=\"appcheck_metric\" AND jsonPayload.metric=\"unverified\"",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_RATE",
            "crossSeriesReducer": "REDUCE_SUM"
          }
        ],
        "comparison": "COMPARISON_GT",
        "thresholdValue": 80.0,
        "duration": "300s"
      }
    }
  ],
  "enabled": true,
  "notificationChannels": [],
  "alertStrategy": {
    "autoClose": "1800s"
  }
}
EOF

ALERT_ID=$(gcloud alpha monitoring policies create \
    --config-from-file=/tmp/unverified_requests_alert.json \
    --format="value(name)" 2>/dev/null || echo "")

if [[ -n "$ALERT_ID" ]]; then
    print_status "✅ Alert policy created for unverified requests"
else
    print_warning "Could not create alert policy (may require alpha APIs)"
fi

# Alert for App Check service health
cat > /tmp/appcheck_service_alert.json << EOF
{
  "displayName": "App Check Service Unhealthy",
  "documentation": {
    "content": "Alert when App Check service reports as unhealthy in the /health endpoint.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "App Check service unhealthy",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"workout-parser\" AND jsonPayload.services.app_check=\"unhealthy\"",
        "aggregations": [
          {
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_COUNT",
            "crossSeriesReducer": "REDUCE_SUM"
          }
        ],
        "comparison": "COMPARISON_GT",
        "thresholdValue": 0,
        "duration": "60s"
      }
    }
  ],
  "enabled": true,
  "notificationChannels": [],
  "alertStrategy": {
    "autoClose": "300s"
  }
}
EOF

HEALTH_ALERT_ID=$(gcloud alpha monitoring policies create \
    --config-from-file=/tmp/appcheck_service_alert.json \
    --format="value(name)" 2>/dev/null || echo "")

if [[ -n "$HEALTH_ALERT_ID" ]]; then
    print_status "✅ Alert policy created for App Check service health"
else
    print_warning "Could not create health alert policy (may require alpha APIs)"
fi

# Clean up temp files
rm -f /tmp/unverified_requests_alert.json /tmp/appcheck_service_alert.json

print_status "🎉 Monitoring setup complete!"
print_status ""
print_status "📊 Your Firebase App Check dashboard is ready at:"
print_status "   https://console.cloud.google.com/monitoring/dashboards/custom/${DASHBOARD_SHORT_ID}?project=${PROJECT_ID}"
print_status ""
print_status "📈 You can now monitor:"
print_status "   • Verified vs Unverified request rates"
print_status "   • App Check token validation success"
print_status "   • API performance and error rates"
print_status "   • Top app IDs making requests"
print_status ""
print_status "🔔 To set up notifications:"
print_status "   1. Go to https://console.cloud.google.com/monitoring/alerting/policies?project=${PROJECT_ID}"
print_status "   2. Configure notification channels (email, Slack, etc.)"
print_status "   3. Edit the alert policies to add your notification channels"
print_status ""
print_status "🛡️ When you see >80% verified requests consistently, enable strict mode with:"
print_status "   APPCHECK_REQUIRED=true make deploy"
