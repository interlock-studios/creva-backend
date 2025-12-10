# Creva - Creator Video Parser

**Extract transcripts, hooks, and metadata from TikTok and Instagram videos for content creators!**

Send a TikTok or Instagram video URL → Get back structured data with title, description, transcript, hook, and thumbnail.

**Repository**: [github.com/interlock-studios/creva-backend](https://github.com/interlock-studios/creva-backend)

---

## 🎯 What is Creva?

Creva is a **creator workflow app** that helps content creators:
- **Save video ideas** from TikTok and Instagram
- **Extract transcripts** from talking videos (priority #1)
- **Capture hooks** (attention-grabbing opening lines)
- **Organize content** by topics and themes
- **Schedule content** for future creation
- **Track progress** (Planned → In Progress → Completed)

This backend service powers the video parsing and transcription features.

---

## 🚀 Quick Start

### Try It Now

```bash
# TikTok Video Example
curl -X POST "http://localhost:8080/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@creator/video/1234567890"}'

# Instagram Reel Example
curl -X POST "http://localhost:8080/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/reel/ABC123XYZ/"}'
```

### Response Format

```json
{
  "title": "5 Ways to Grow Your TikTok",
  "description": "Here are 5 proven strategies...",
  "image": "https://storage.googleapis.com/creva-e6435.appspot.com/video_images/abc123.jpg",
  "transcript": "Hey everyone! Today I'm going to share 5 ways to grow your TikTok account. First, you need to...",
  "hook": "Hey everyone! Today I'm going to share 5 ways to grow your TikTok account.",
  "creator": "@creator",
  "platform": "tiktok",
  "cached": false
}
```

---

## 🎯 How It Works

### Simple Flow
1. **Send TikTok/Instagram URL** → API receives your video request
2. **Detect Platform** → Automatically routes to appropriate scraper
3. **Check Cache** → If we've seen this video before, instant result!
4. **Process Content** → Download video, extract audio, transcribe with AI
5. **Return Data** → Get structured JSON with transcript and hook

### Smart Caching (365+ Days)

Video content is immutable. If Joe saves a MrBeast video in December, and Stacy saves the same video in April:
- ✅ Stacy gets **instant cached results**
- ✅ No re-processing needed
- ✅ Massive cost savings
- ✅ Reduced API load

**Cache Key**: SHA256 hash of normalized URL
**Cache Duration**: 365+ days (effectively permanent)

### Three Response Types

#### 1. Cached (Instant - Most Popular Content)
```json
{
  "title": "Creator Tips",
  "transcript": "Full transcript text...",
  "hook": "Opening hook text...",
  "cached": true
}
```

#### 2. Direct Processing (Low Traffic - ~10-30 seconds)
Same JSON as above, but takes 10-30 seconds to process.

#### 3. Queued (High Traffic)
```json
{
  "status": "queued",
  "job_id": "req123_1234567890",
  "check_url": "/status/req123_1234567890"
}
```

---

## 🏗️ Technical Overview

### Architecture
- **FastAPI** - Main API service
- **Cloud Run** - Serverless hosting on `creva-e6435`
- **Firestore** - Queue system and long-term caching
- **Worker Service** - Background video processing
- **Google Gemini AI** - Transcript and hook extraction

### Smart Processing
- **Cache First** - Popular content returns instantly
- **Direct Mode** - Process immediately when not busy
- **Queue Mode** - Background processing when at capacity
- **Auto-Scale** - Handles 1 user or 10,000 users

---

## 🚀 Quick Setup (5 minutes)

### Prerequisites
- Python 3.11
- Google Cloud account
- ScrapeCreators API key ([get one here](https://scrapecreators.com))

### Install & Run
```bash
# 1. Navigate to creva-backend
cd creva-backend
make setup

# 2. Configure .env file with:
# GOOGLE_CLOUD_PROJECT_ID=creva-e6435
# SCRAPECREATORS_API_KEY=your-api-key

# 3. Start everything
make dev
```

That's it! API runs on http://localhost:8080

### What `make dev` starts:
- **API Service** (port 8080) - Handles requests, checks cache
- **Worker Service** (port 8081) - Processes videos in background

---

## 🛠️ Development Commands

```bash
make dev          # Start both API and Worker
make dev-api      # Start only API
make dev-worker   # Start only Worker
make dev-force    # Kill existing processes and restart

make test         # Run tests
make lint         # Check code quality
make deploy       # Deploy to production
```

---

## 📡 API Endpoints

### `POST /process`
Process a TikTok or Instagram video

**Parameters:**
- `url` (required): TikTok or Instagram URL

```bash
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123"}'
```

### `GET /status/{job_id}`
Check processing status for queued jobs
```bash
curl http://localhost:8080/status/req123_1234567890
```

### `GET /health`
Health check
```bash
curl http://localhost:8080/health
```

---

## 🔧 How Processing Works

### When you send a TikTok or Instagram URL:

1. **Platform Detection** - Automatically detect TikTok or Instagram
2. **URL Validation** - Check if it's a valid URL for the detected platform
3. **Cache Check** - Look in Firestore cache (365+ day TTL)
4. **If Cached** → Return result instantly
5. **If Not Cached** → Check system capacity
6. **If Low Traffic** → Process directly (10-30 seconds)
7. **If High Traffic** → Add to queue, return job_id

### Background Processing (for queued content):
1. **Worker picks up job** from Firestore queue
2. **Download video** using platform-specific scraper
3. **Extract audio** and transcribe with Gemini AI
4. **Identify hook** - First 30 seconds / attention grabber
5. **Store result** in cache (365+ days)
6. **Update job status** to completed

---

## 🌐 Deploy to Production

```bash
# Setup Google Cloud (one time)
make setup-gcp
make create-secrets

# Deploy both API and Worker services
make deploy
```

Your API will be live at: `https://creva-parser-{hash}.run.app`

---

## 📊 Infrastructure

### GCP Configuration
- **Project**: `creva-e6435`
- **Services**: `creva-parser`, `creva-parser-worker`
- **Service Account**: `creva-parser@creva-e6435.iam.gserviceaccount.com`
- **Region**: `us-central1` (primary)

### Firebase/Firestore
- **Project**: `creva-e6435`
- **Collections**: `parser_cache`, `processing_queue`, `processing_results`
- **Storage**: `creva-e6435.appspot.com`

---

## 🔍 Troubleshooting

### Common Issues

**"API key not found"**
```bash
# Check your .env file
cat .env | grep SCRAPECREATORS_API_KEY
```

**"Worker not processing jobs"**
```bash
# Make sure both services are running
make dev
# You should see both "API started" and "Worker started"
```

**"The query requires an index"**
```bash
# Create Firestore indexes
make setup-firestore
# Or click the link in the error message
```

---

## 💰 Costs

### Google Cloud (Free Tier)
- **2 million requests/month** - FREE
- **After free tier** - ~$0.40 per million requests

### Cost Optimization
- **Long-term caching** reduces costs significantly
- If 1000 users save the same viral video, only process once
- Cache for 365+ days (videos don't change)

---

## 🏆 What Makes This Special

- **Smart Caching** - Popular videos load instantly for everyone
- **Transcript Extraction** - Full text from video audio
- **Hook Detection** - Identify attention-grabbing openers
- **Production Ready** - Handles failures, retries, monitoring
- **Cost Efficient** - Process once, serve forever

---

## 👨‍💻 For Developers

### Project Structure
```
creva-backend/
├── main.py                     # Main FastAPI application
├── src/
│   ├── services/              # Core business logic services
│   │   ├── tiktok_scraper.py      # TikTok video downloading & metadata
│   │   ├── instagram_scraper.py   # Instagram video downloading & metadata
│   │   ├── url_router.py          # Platform detection and URL validation
│   │   ├── genai_service.py       # Gemini AI for transcription
│   │   ├── genai_service_pool.py  # Multiple GenAI services for workers
│   │   ├── cache_service.py       # Firestore-based result caching
│   │   ├── queue_service.py       # Firestore-based job queue
│   │   └── config_validator.py    # Environment validation
│   ├── worker/                # Background processing system
│   │   ├── worker_service.py      # Main worker process
│   │   └── video_processor.py     # Video processing pipeline
│   └── models/                # Data structures
│       └── responses.py           # Response JSON schemas
├── requirements.txt           # Python dependencies
├── Dockerfile                # Container configuration
├── cloudbuild.yaml           # Google Cloud Build configuration
├── Makefile                  # Development commands
└── README.md                 # This file
```

### Environment Variables
```bash
# Required
GOOGLE_CLOUD_PROJECT_ID=creva-e6435
SCRAPECREATORS_API_KEY=your-api-key

# Optional
ENVIRONMENT=development  # development|staging|production
PORT=8080               # API port
WORKER_PORT=8081        # Worker port
LOG_LEVEL=INFO          # DEBUG|INFO|WARNING|ERROR
```

---

## 📖 Documentation

- **[Project Structure](PROJECT_STRUCTURE.md)** - Quick guide to the codebase
- **[Scripts Directory](scripts/README.md)** - Deployment and setup scripts
- **[Docs](docs/)** - Architecture and operations guides

---

**⚠️ Proprietary Software Notice**

This software is proprietary and confidential. All rights reserved.
