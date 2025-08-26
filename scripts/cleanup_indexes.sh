#!/bin/bash

# Clean up duplicate/unnecessary Firestore indexes
# This script removes redundant indexes that were created during development

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT_ID:-$(gcloud config get-value project)}

if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID not set. Please set GOOGLE_CLOUD_PROJECT_ID or configure gcloud project."
    exit 1
fi

echo "Cleaning up duplicate Firestore indexes for project: $PROJECT_ID"

# List of index IDs to delete (keeping only the priority-based one)
# We keep CICAgOi36pgK (status + priority_value + created_at) - this is our main index
INDEXES_TO_DELETE=(
    "CICAgJiUpoMJ"  # url, created_at
    "CICAgJim14AK"  # status, url, created_at  
    "CICAgJj7z4EK"  # status, created_at
    "CICAgJjF9oIK" # status, url, created_at
    "CICAgOi39IkK" # url, localization, status, created_at
    "CICAgJjFvYoK" # status (array), created_at
    "CICAgOi3kJAK" # status, created_at
    "CICAgJjFqZMK" # url, localization, created_at
)

echo "The following indexes will be deleted:"
for index_id in "${INDEXES_TO_DELETE[@]}"; do
    echo "  - $index_id"
done

read -p "Do you want to proceed? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Delete each index
for index_id in "${INDEXES_TO_DELETE[@]}"; do
    echo "Deleting index: $index_id"
    gcloud firestore indexes composite delete "$index_id" \
        --project="$PROJECT_ID" \
        --quiet || echo "Failed to delete $index_id (might already be deleted)"
done

echo "✅ Index cleanup complete!"
echo "Remaining indexes should be:"
echo "  - The new priority-based composite index (status + priority_value + created_at)"
echo "  - Any other necessary single-field indexes"
