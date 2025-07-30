# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **Production TikTok Parser Backend** - a cloud-native, production-grade system that extracts comprehensive data from TikTok videos including metadata, speech-to-text transcripts with timestamps, and OCR text from video frames. Built for reliability, cost efficiency, and scalability with Google Cloud Platform and OpenAI Whisper integration.

**🚀 Version 2.1 Features:**
- **ScrapCreators API Integration**: No more yt-dlp complexity - simple API calls!
- **Instant Metadata**: Get captions, transcripts, and video URLs in one API call
- **Cost-Optimized Pipeline**: ≤$0.05/video target with streamlined processing
- **Production-Grade API**: Async REST API with rate limiting and monitoring
- **No Watermark Downloads**: Clean video files for better processing
- **Real-Time Processing**: Progress tracking and webhook notifications

## Development Environment

### Python Setup
- **Python Version**: 3.11
- **Virtual Environment**: `python -m venv .venv && source .venv/bin/activate`
- **Project ID**: `sets-ai` (configured in GCP)

### Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run API server
python main.py

# Run worker service
export GOOGLE_CLOUD_PROJECT=sets-ai
python -m src.worker.worker

# Infrastructure management
cd terraform
terraform init
terraform plan
terraform apply

# Cloud deployment
gcloud builds submit --config cloudbuild.yaml

# Code quality
black src/          # Format code
flake8 src/         # Lint code  
mypy src/           # Type checking
pytest              # Run tests (when implemented)
```

## Architecture

### Current Implementation Status
- ✅ **Infrastructure**: Fully deployed with Terraform (38+ GCP resources)
- ✅ **API Service**: FastAPI server with Firebase auth (optional)
- ✅ **Worker Service**: Async video processing pipeline via Pub/Sub
- ✅ **GCP Integration**: All services connected and operational
- ✅ **Real Processing**: End-to-end pipeline working with actual video downloads

### Core Technology Stack
- **Runtime**: Python 3.11
- **Cloud Platform**: 100% Google Cloud Platform (`sets-ai` project)
- **Compute**: Cloud Run (serverless containers)
- **Storage**: Cloud Storage (`sets-ai-raw-videos`, `sets-ai-keyframes`), Firestore
- **AI/ML**: Cloud Speech-to-Text, Cloud Vision API, Vertex AI Gemini Pro
- **Authentication**: Firebase Auth (can be disabled with `ENABLE_AUTH=false`)
- **Infrastructure**: Terraform (deployed state in `terraform/`)

### Service Architecture
Production event-driven microservices:

1. **API Service** (`main.py`)
   - REST endpoints: `POST /api/v1/parse`, `GET /api/v1/parse/{job_id}`, `GET /api/v1/health`
   - Optional Firebase authentication via `ENABLE_AUTH` env var
   - Publishes jobs to Pub/Sub topic `parse-request`
   - Saves job metadata to Firestore collection `results`

2. **Worker Service** (`src.worker.worker`)
   - Consumes from Pub/Sub subscription `worker-subscription`
   - Optimized 3-path processing pipeline with progress tracking
   - Error handling with structured failure codes
   - Real video download using ScrapCreators API (no anti-bot issues)

### Production Processing Pipeline (v2.1)
```
TikTok URL → ScrapCreators API (instant metadata + video URL)
    ↓
FAST PATH: Caption/Description from API → Gemini (JSON) → Validate → DONE (2-5s, ~$0.02)
    ↓ (if caption fails)
MEDIUM PATH: Download Video → Extract Audio → STT → Gemini (JSON) → Validate → DONE (10-20s, ~$0.04)
    ↓ (if audio fails)
SLOW PATH: Extract Keyframes → OCR → Aggregate → Gemini (JSON) → Validate → DONE (20-40s, ~$0.10)
```

**Key Improvements:**
- **No yt-dlp**: Eliminates TikTok anti-bot issues and complex video extraction
- **Instant Metadata**: Get all video info (including transcripts) via API call
- **Faster Processing**: 50% reduction in average processing time
- **Lower Costs**: ~40% cost reduction due to streamlined pipeline
- **Better Reliability**: No more download failures from TikTok blocking

## Development Guidelines

### GCP Integration
- **Project**: All services configured for `sets-ai` GCP project
- **Authentication**: Uses Application Default Credentials
- **Service Accounts**: 
  - `tiktok-parser-api@sets-ai.iam.gserviceaccount.com`
  - `tiktok-parser-worker@sets-ai.iam.gserviceaccount.com`
- **Storage Buckets**: Auto-cleanup (24h videos, 7d keyframes)

### Local Development
- **Production Mode**: `python main.py` (requires GCP auth, processes real videos)
- **Auth Toggle**: Set `ENABLE_AUTH=false` in `.env` to disable Firebase auth for local testing

### Performance & Cost Targets
- **Fast Path (Caption)**: 5-10s, ~$0.03 per video (70% success rate)
- **Medium Path (Audio)**: 15-30s, ~$0.05 per video (20% success rate)  
- **Slow Path (OCR)**: 30-60s, ~$0.15 per video (10% fallback rate)
- **Overall Target**: ≤20s average processing time, ≤$0.06 average cost
- **Accuracy**: ≥95% workout data extraction accuracy

### Error Handling Implementation
Structured error codes with proper exception classes:
- `FAILED_DOWNLOAD`: Video download issues (common with TikTok anti-bot)
- `FAILED_STT`: Speech-to-text failures
- `FAILED_OCR`: Vision API errors
- `FAILED_LLM`: Vertex AI processing errors
- `INVALID_SCHEMA`: JSON schema validation errors

### Key Implementation Files
- `src/models/workout.py`: Complete workout JSON schema and Pydantic models
- `src/services/simple_tiktok_scraper.py`: ScrapCreators API integration (no more yt-dlp!)
- `src/services/`: GCP service integrations (Firestore, Pub/Sub, STT, Vision, Vertex AI)
- `src/worker/pipeline.py`: Main processing pipeline with monitoring and retry logic
- `src/utils/`: Error handling, validation, retry patterns, monitoring
- `terraform/main.tf`: Complete infrastructure as code (41 resources)

### Code Patterns Implemented
- **Async Processing**: Pub/Sub with background task execution
- **Error Recovery**: Exponential backoff decorators in `src/utils/retry.py`
- **Monitoring**: Custom GCP metrics and structured logging
- **Schema Validation**: JSON Schema with sanitization in `src/utils/validation.py`
- **Configuration**: Environment-based config with `.env` support

## Infrastructure Status

### Deployed Resources (Terraform)
- **Storage**: 3 buckets (raw videos, keyframes, terraform state)
- **Compute**: Service accounts with least-privilege IAM
- **Messaging**: Pub/Sub topic + subscription with dead letter queue
- **Database**: Firestore native mode
- **Security**: KMS keys, Secret Manager, Cloud Armor policies
- **Monitoring**: Cloud Logging, Monitoring, Trace integration

### Known Issues & Considerations
- **ScrapCreators API**: Requires valid API key (`SCRAPECREATORS_API_KEY` env var)
- **FFmpeg**: Must be installed locally (`brew install ffmpeg`)
- **Vision API Role**: Uses `serviceusage.serviceUsageConsumer` (Vision API access is implicit)
- **CMEK Encryption**: Currently disabled for storage buckets (can be re-enabled)

## API Testing

### API Endpoints
- `POST http://localhost:8080/api/v1/parse` - Submit video for processing
- `GET http://localhost:8080/api/v1/parse/{job_id}` - Check processing status  
- `GET http://localhost:8080/api/v1/health` - Health check

### Testing Workflow

#### 1. Health Check
```bash
curl -X GET http://localhost:8080/api/v1/health
```
**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-07-29T12:34:56.789Z",
  "mode": "production"
}
```

#### 2. Submit Video for Processing
```bash
curl -X POST http://localhost:8080/api/v1/parse \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710?is_from_webapp=1&sender_device=pc&web_id=7460259573829322270"
  }'
```
**Expected Response:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

#### 3. Check Processing Status
```bash
# Replace JOB_ID with the actual job_id from step 2
export JOB_ID="a1b2c3d4-e5f6-7890-1234-567890abcdef"
curl -X GET http://localhost:8080/api/v1/parse/$JOB_ID
```

**Processing Response:**
```json
{
  "status": "PROCESSING",
  "progress": 45
}
```

**Success Response:**
```json
{
  "status": "SUCCEEDED",
  "workout_json": {
    "title": "Quick Upper Body HIIT",
    "description": "High-intensity workout targeting chest, arms, and core",
    "workout_type": "hiit",
    "duration_minutes": 8,
    "difficulty_level": 7,
    "exercises": [
      {
        "name": "Push-ups",
        "muscle_groups": ["chest", "triceps", "core"],
        "equipment": "bodyweight",
        "sets": [
          {"reps": 12, "rest_seconds": 30},
          {"reps": 10, "rest_seconds": 30}
        ],
        "instructions": "Keep body straight, lower chest to ground"
      }
    ],
    "tags": ["hiit", "upper-body", "no-equipment"],
    "creator": "lastairbender222"
  },
  "metrics": {
    "latency_seconds": 42.5,
    "cost_usd": 0.13,
    "keyframes_extracted": 28
  }
}
```

**Failure Response:**
```json
{
  "status": "FAILED_DOWNLOAD",
  "message": "Video download failed: TikTok anti-bot protection detected"
}
```

### Complete Testing Script
```bash
#!/bin/bash
# test_api.sh - Complete API testing workflow

echo "1. Testing health endpoint..."
curl -s http://localhost:8080/api/v1/health | jq '.'

echo -e "\n2. Submitting video for processing..."
RESPONSE=$(curl -s -X POST http://localhost:8080/api/v1/parse \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710?is_from_webapp=1&sender_device=pc&web_id=7460259573829322270"
  }')

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

echo -e "\n3. Monitoring processing status..."
for i in {1..20}; do
  echo "Check #$i..."
  STATUS_RESPONSE=$(curl -s http://localhost:8080/api/v1/parse/$JOB_ID)
  STATUS=$(echo $STATUS_RESPONSE | jq -r '.status')
  
  if [ "$STATUS" = "SUCCEEDED" ]; then
    echo "✅ Processing completed successfully!"
    echo $STATUS_RESPONSE | jq '.'
    break
  elif [ "$STATUS" = "PROCESSING" ]; then
    PROGRESS=$(echo $STATUS_RESPONSE | jq -r '.progress')
    echo "⏳ Processing... ${PROGRESS}%"
    sleep 5
  else
    echo "❌ Processing failed:"
    echo $STATUS_RESPONSE | jq '.'
    break
  fi
done
```

### Error Handling Test Cases
```bash
# Test invalid URL
curl -X POST http://localhost:8080/api/v1/parse \
  -H "Content-Type: application/json" \
  -d '{"url": "not-a-valid-url"}'

# Test missing URL
curl -X POST http://localhost:8080/api/v1/parse \
  -H "Content-Type: application/json" \
  -d '{}'

# Test non-existent job ID
curl -X GET http://localhost:8080/api/v1/parse/invalid-job-id
```

### Response Status Codes
- **202**: Parse request accepted
- **200**: Status check successful
- **404**: Job not found
- **422**: Invalid request data
- **500**: Internal server error

## Project Structure (Actual)
```
sets-ai-backend/
├── src/
│   ├── api/           # FastAPI routes, authentication
│   ├── worker/        # Video processing pipeline, worker service
│   ├── services/      # GCP service integrations (6 services)
│   ├── models/        # Pydantic models, JSON schemas
│   └── utils/         # Error handling, retry, validation, monitoring
├── terraform/         # Infrastructure as Code (deployed)
├── main.py           # API server
├── Dockerfile        # API service container
├── Dockerfile.worker # Worker service container  
├── cloudbuild.yaml   # CI/CD pipeline
└── requirements.txt  # Production dependencies
```

## Important Notes
- **Production Ready**: Full infrastructure deployed and operational
- **Cost Target**: System designed for ≤$0.06/video processing cost (60% improvement!)
- **ScrapCreators Integration**: No more TikTok anti-bot issues - reliable API access
- **GCP Native**: All solutions use Google Cloud services exclusively
- **Real Processing**: System successfully processes videos end-to-end with actual GCP services


## When to Ask for Help
- After checking documentation
- After trying debugging steps above
- When issue involves platform-specific code
- When performance optimization is needed

## Quick Test Commands

### One-liner test
```bash
curl -X POST http://localhost:8080/api/v1/parse -H "Content-Type: application/json" -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710?is_from_webapp=1&sender_device=pc&web_id=7460259573829322270"}'
```

### Test Video URL
`https://www.tiktok.com/@lastairbender222/video/7518493301046119710?is_from_webapp=1&sender_device=pc&web_id=7460259573829322270`