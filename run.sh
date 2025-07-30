#!/bin/bash
# TikTok Workout Parser - Run Script

# Load environment variables from .env.local if it exists
if [ -f .env.local ]; then
    export $(cat .env.local | xargs)
fi

# Set Google Cloud project if not already set
if [ -z "$GOOGLE_CLOUD_PROJECT_ID" ]; then
    export GOOGLE_CLOUD_PROJECT_ID="sets-ai"
fi

echo "🚀 Starting TikTok Workout Parser"
echo "📁 Google Cloud Project: $GOOGLE_CLOUD_PROJECT_ID"
echo "🤖 AI Model: Gemini 2.5 Flash"
echo "🌐 API will be available at: http://localhost:8080"
echo ""

# Run the application
python main.py