# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

Creva Backend is a Python FastAPI service that transforms TikTok and Instagram videos into structured creator content data. The system features:

- **Multi-Platform Support**: TikTok and Instagram video processing
- **Transcript Extraction**: Priority #1 - Full text from video audio
- **Hook Detection**: Identify attention-grabbing opening lines
- **Hybrid Processing**: Direct processing for low traffic, queue-based for high traffic
- **AI-Powered Analysis**: Google Gemini for transcription and analysis
- **Smart Caching**: Firestore cache with 365+ day TTL for instant results
- **Cloud Deployment**: Google Cloud Run on `creva-e6435`

---

## Infrastructure

### GCP Project: `creva-e6435`

All services run on the dedicated Creva Google Cloud project.

```
Cloud Run Services:
├── creva-parser          (API service)
└── creva-parser-worker   (Background processing)

Firebase/Firestore: creva-e6435
├── parser_cache          (365+ day video cache)
├── processing_queue      (Job queue)
└── processing_results    (Completed jobs)

Service Account: creva-parser@creva-e6435.iam.gserviceaccount.com
```

---

## Common Commands

### Development
```bash
# Setup and dependencies
make setup                 # Initial project setup (creates venv, installs deps)
make install               # Install/update dependencies
source .venv/bin/activate  # Activate virtual environment

# Running the application
make dev                   # Start both API and Worker services with auto-reload
make dev-api               # Start only API service (port 8080)
make dev-worker            # Start only Worker service (port 8081)
make dev-force             # Force restart (kills existing processes)

# Testing and validation
make test                  # Run test suite with pytest
make lint                  # Run all linters (black, flake8, mypy, bandit)
make format                # Format code with black
make validate              # Run all validation checks
```

### Docker Development
```bash
make docker-build          # Build Docker image locally
make docker-run            # Run containerized app locally
make docker-test           # Build and test Docker image
```

### Cloud Deployment
```bash
# Google Cloud setup
make setup-gcp             # Configure GCP project and enable APIs
make create-secrets        # Store API keys in Secret Manager

# Deployment
make deploy                # Deploy to production (Cloud Run)
make deploy-preview        # Deploy single-region preview
make logs                  # View production logs
```

---

## Architecture

### Core Services

| Service | File | Purpose |
|---------|------|---------|
| API | `main.py` | FastAPI HTTP endpoints |
| Worker | `src/worker/worker_service.py` | Background video processing |
| Cache | `src/services/cache_service.py` | Firestore caching (365+ days) |
| Queue | `src/services/queue_service.py` | Job queue management |
| GenAI | `src/services/genai_service.py` | Gemini AI transcription |

### Processing Flow

```
1. Request → POST /process with video URL
2. Platform Detection → TikTok or Instagram
3. Cache Check → If cached (365+ days), return instantly
4. If Not Cached:
   ├── Low Traffic → Process directly
   └── High Traffic → Queue for worker
5. Processing:
   ├── Download video via ScrapeCreators
   ├── Extract audio
   ├── Transcribe with Gemini AI
   ├── Identify hook (first 30 seconds)
   └── Cache result for 365+ days
6. Return structured JSON
```

### Response Model

```python
class CreatorContent(BaseModel):
    title: str                    # Video title
    description: Optional[str]    # Video description
    image: Optional[str]          # Thumbnail URL
    transcript: Optional[str]     # Full transcript (Priority #1)
    hook: Optional[str]           # Opening hook (Priority #2)
    creator: Optional[str]        # Creator username
    platform: Optional[str]       # "tiktok" or "instagram"
    tags: Optional[List[str]]     # Hashtags
    cached: Optional[bool]        # Whether from cache
```

---

## Key Files

### API Layer
- `main.py` - FastAPI application entry point
- `src/api/process.py` - Video processing endpoint
- `src/api/health.py` - Health check endpoint

### Services
- `src/services/tiktok_scraper.py` - TikTok video scraping
- `src/services/instagram_scraper.py` - Instagram video scraping
- `src/services/genai_service.py` - Gemini AI integration
- `src/services/cache_service.py` - Firestore caching
- `src/services/queue_service.py` - Job queue

### Worker
- `src/worker/worker_service.py` - Background worker
- `src/worker/video_processor.py` - Video processing pipeline

### Models
- `src/models/responses.py` - Response schemas

---

## Cache Strategy

### Why 365+ Day Cache?

Video content is immutable:
- Transcripts don't change
- Hooks don't change
- Metadata doesn't change

**Example:**
- December 10: Joe saves MrBeast video → Full processing (10-30s)
- April 15: Stacy saves same video → Instant cached result (<1s)

**Benefits:**
- Massive cost savings (no duplicate API calls)
- Instant UX for popular videos
- Reduced load on ScrapeCreators/Gemini

---

## Environment Variables

### Required
```bash
GOOGLE_CLOUD_PROJECT_ID=creva-e6435
SCRAPECREATORS_API_KEY=<your-api-key>
```

### Optional
```bash
ENVIRONMENT=development    # development|staging|production
PORT=8080                  # API port
WORKER_PORT=8081           # Worker port
LOG_LEVEL=INFO             # DEBUG|INFO|WARNING|ERROR
```

---

## Testing

### Local Testing
```bash
# Start services
make dev

# Test health
curl http://localhost:8080/health

# Test video processing
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123"}'
```

### Run Test Suite
```bash
make test                  # Run all tests
make lint                  # Check code quality
make validate              # Full validation
```

---

## Deployment Checklist

1. ✅ Service account exists: `creva-parser@creva-e6435.iam.gserviceaccount.com`
2. ✅ Secrets configured in Secret Manager
3. ✅ Firestore indexes deployed
4. ✅ Cloud Run services deployed
5. ✅ Health endpoints responding
6. ✅ Cache working (test with duplicate URL)

---

## Troubleshooting

### "Service account not found"
```bash
gcloud iam service-accounts create creva-parser \
  --display-name="Creva Parser Service Account" \
  --project=creva-e6435
```

### "Permission denied" on Vertex AI
```bash
make fix-genai-permissions
```

### Worker not processing
```bash
curl http://localhost:8081/health
make dev-force  # Restart services
```

### Firestore index errors
```bash
make setup-firestore
# Or click the link in the error message
```
