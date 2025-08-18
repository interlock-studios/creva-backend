#!/bin/bash
set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

print_header() {
    echo -e "${BLUE}[DEPLOY]${NC} $1"
}

print_success() {
    echo -e "${PURPLE}[SUCCESS]${NC} $1"
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

print_header "🚀 Deploying Comprehensive Sets AI Analytics Dashboard"
echo ""

# Create the comprehensive dashboard
print_status "Creating comprehensive analytics dashboard..."
DASHBOARD_ID=$(gcloud monitoring dashboards create \
    --config-from-file=monitoring/sets_ai_analytics_dashboard.json \
    --format="value(name)")

if [[ $? -eq 0 && -n "$DASHBOARD_ID" ]]; then
    # Extract the dashboard ID from the full name
    DASHBOARD_SHORT_ID=$(basename "$DASHBOARD_ID")
    print_success "✅ Comprehensive dashboard created successfully!"
    print_status "Dashboard ID: ${DASHBOARD_SHORT_ID}"
    print_status ""
    print_header "🌐 Your New Analytics Dashboard:"
    echo -e "${BLUE}https://console.cloud.google.com/monitoring/dashboards/custom/${DASHBOARD_SHORT_ID}?project=${PROJECT_ID}${NC}"
else
    print_error "Failed to create comprehensive dashboard"
    exit 1
fi

# Generate some test data
print_status ""
print_status "🧪 Generating test data to populate dashboard..."
for i in {1..3}; do
    curl -s -X POST "https://workout-parser-341666880405.us-central1.run.app/process" \
        -H "Content-Type: application/json" \
        -d "{\"url\": \"https://www.tiktok.com/@dashtest$i/video/123\"}" > /dev/null || true
    sleep 1
done

print_status ""
print_success "🎉 Deployment Complete!"
print_status ""
print_header "📊 Your Comprehensive Analytics Dashboard Includes:"
echo ""
echo -e "${GREEN}🛡️  APP CHECK SECURITY:${NC}"
echo "   • ✅ Verified request counts with sparklines"
echo "   • ❌ Unverified request tracking"
echo "   • 🚫 Invalid token monitoring"
echo "   • 🎯 Real-time verification rate percentage"
echo ""
echo -e "${BLUE}📈 API PERFORMANCE:${NC}"
echo "   • 🚀 Response latency (95th percentile & average)"
echo "   • 📊 Request volume and error rates"
echo "   • 🖥️  Cloud Run instance scaling"
echo "   • 💾 Memory and CPU utilization"
echo ""
echo -e "${PURPLE}📋 OPERATIONAL INSIGHTS:${NC}"
echo "   • 🔄 Processing queue status"
echo "   • 📊 Daily request summaries"
echo "   • 🎯 App Check adoption trends with thresholds"
echo "   • 📋 System health indicators"
echo ""
echo -e "${YELLOW}🎯 KEY FEATURES:${NC}"
echo "   • Real-time metrics with proper aggregation"
echo "   • Visual thresholds for decision making"
echo "   • Sparklines for trend visualization"
echo "   • Color-coded status indicators"
echo ""
print_header "🔗 Quick Links:"
echo -e "   Dashboard: ${BLUE}https://console.cloud.google.com/monitoring/dashboards/custom/${DASHBOARD_SHORT_ID}?project=${PROJECT_ID}${NC}"
echo -e "   Logs:      ${BLUE}https://console.cloud.google.com/logs/query?project=${PROJECT_ID}${NC}"
echo -e "   Metrics:   ${BLUE}https://console.cloud.google.com/monitoring/metrics-explorer?project=${PROJECT_ID}${NC}"
echo ""
print_status "⏱️  Dashboard will populate with data within 2-5 minutes"
print_status "🔄 Make API calls to see real-time updates"
