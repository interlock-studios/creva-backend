#!/bin/bash

# Cleanup script to delete unused Cloud Run services
# Keeps only: us-central1, us-east1, us-west1, europe-west1, europe-west4

set -e

PROJECT_ID="${PROJECT_ID:-creva-e6435}"
SERVICE_NAME="${SERVICE_NAME:-creva-parser}"
WORKER_NAME="${WORKER_NAME:-creva-parser-worker}"

# Regions to DELETE (unused/old)
REGIONS_TO_DELETE=(
  "europe-north1"
  "asia-southeast1"
  "asia-northeast1"
  "asia-south1"
  "australia-southeast1"
  "southamerica-east1"
)

echo "🧹 Cleaning up unused Cloud Run services..."
echo "Project: $PROJECT_ID"
echo "Services: $SERVICE_NAME, $WORKER_NAME"
echo ""

for region in "${REGIONS_TO_DELETE[@]}"; do
  echo "🗑️  Deleting services in region: $region"
  
  # Delete API service
  echo "  - Deleting $SERVICE_NAME..."
  if gcloud run services describe "$SERVICE_NAME" --region="$region" --project="$PROJECT_ID" &>/dev/null; then
    gcloud run services delete "$SERVICE_NAME" \
      --region="$region" \
      --project="$PROJECT_ID" \
      --quiet || echo "    ⚠️  Failed to delete $SERVICE_NAME in $region"
  else
    echo "    ℹ️  $SERVICE_NAME not found in $region (already deleted)"
  fi
  
  # Delete Worker service
  echo "  - Deleting $WORKER_NAME..."
  if gcloud run services describe "$WORKER_NAME" --region="$region" --project="$PROJECT_ID" &>/dev/null; then
    gcloud run services delete "$WORKER_NAME" \
      --region="$region" \
      --project="$PROJECT_ID" \
      --quiet || echo "    ⚠️  Failed to delete $WORKER_NAME in $region"
  else
    echo "    ℹ️  $WORKER_NAME not found in $region (already deleted)"
  fi
  
  echo ""
done

echo "✅ Cleanup complete!"
echo ""
echo "Remaining active regions:"
echo "  - us-central1 (primary)"
echo "  - us-east1"
echo "  - us-west1"
echo "  - europe-west1"
echo "  - europe-west4"

