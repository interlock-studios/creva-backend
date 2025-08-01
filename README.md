# Social Media Workout Parser

**Turn any TikTok or Instagram workout video into structured JSON data in seconds!**

Send a TikTok or Instagram URL → Get back structured workout data with exercises, sets, reps, and instructions.

## 🚀 Try It Now

**Live API:** https://tiktok-workout-parser-ty6tkvdynq-uc.a.run.app

```bash
# TikTok Example
curl -X POST "https://tiktok-workout-parser-ty6tkvdynq-uc.a.run.app/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'

# Instagram Example  
curl -X POST "https://tiktok-workout-parser-ty6tkvdynq-uc.a.run.app/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/reel/CS7CshJjb15/"}'
```

## 🎯 How It Works

### Simple Flow
1. **Send TikTok/Instagram URL** → API receives your request
2. **Detect Platform** → Automatically routes to appropriate scraper
3. **Check Cache** → If we've seen this video before, instant result!
4. **Process Video** → Download video, extract transcript/caption, analyze with AI
5. **Return Data** → Get structured workout JSON

### Three Response Types

#### 1. Cached (Instant - 90% of popular videos)
```json
{
  "title": "Full Body HIIT Workout",
  "workout_type": "hiit",
  "duration_minutes": 15,
  "exercises": [
    {
      "name": "Burpees",
      "sets": [{"reps": 15, "rest_seconds": 30}],
      "instructions": "Start standing, drop to plank, jump back up"
    }
  ]
}
```

#### 2. Direct Processing (Low Traffic - ~10 seconds)
Same JSON as above, but takes 10-15 seconds to process.

#### 3. Queued (High Traffic)
```json
{
  "status": "queued",
  "job_id": "req123_1234567890",
  "check_url": "/status/req123_1234567890"
}
```

Then check status:
```bash
curl "https://tiktok-workout-parser-ty6tkvdynq-uc.a.run.app/status/req123_1234567890"
```

## 🏗️ Technical Overview

### Architecture
- **FastAPI** - Main API service
- **Cloud Run** - Serverless hosting (auto-scales)
- **Firestore** - Queue system and caching
- **Worker Service** - Background video processing
- **Google Gemini AI** - Video analysis

### Smart Processing
- **Cache First** - Popular videos return instantly
- **Direct Mode** - Process immediately when not busy
- **Queue Mode** - Background processing when at capacity
- **Auto-Scale** - Handles 1 user or 10,000 users

## 🚀 Quick Setup (5 minutes)

### Prerequisites
- Python 3.11
- Google Cloud account (free tier works)
- ScrapeCreators API key ([get one here](https://scrapecreators.com))

### Install & Run
```bash
# 1. Clone and setup
git clone <repo-url>
cd sets-ai-backend
make setup

# 2. Add your API key to .env file
nano .env
# Set: SCRAPECREATORS_API_KEY=your_key_here

# 3. Start everything
make dev
```

That's it! API runs on http://localhost:8080

### What `make dev` starts:
- **API Service** (port 8080) - Handles requests, checks cache
- **Worker Service** (port 8081) - Processes videos in background

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

## 📡 API Endpoints

### `POST /process`
Process a TikTok or Instagram video
```bash
# TikTok
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123"}'

# Instagram
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/reel/ABC123/"}'
```

### `GET /status/{job_id}`
Check processing status
```bash
curl http://localhost:8080/status/req123_1234567890
```

### `GET /health`
Health check
```bash
curl http://localhost:8080/health
```

## 🔧 How Processing Works

### When you send a TikTok or Instagram URL:

1. **Platform Detection** - Automatically detect TikTok or Instagram
2. **URL Validation** - Check if it's a valid URL for the detected platform
3. **Cache Check** - Look in Firestore cache (1-week TTL)
4. **If Cached** → Return result instantly
5. **If Not Cached** → Check system capacity
6. **If Low Traffic** → Process directly (10-15 seconds)
7. **If High Traffic** → Add to queue, return job_id

### Background Processing (for queued videos):
1. **Worker picks up job** from Firestore queue
2. **Download video** using platform-specific scraper (TikTok/Instagram)
3. **Extract metadata** - transcript from TikTok, caption from Instagram
4. **Remove audio** with ffmpeg (faster AI processing)
5. **Analyze with Gemini AI** (video + transcript/caption)
6. **Store result** in cache and results collection
7. **Update job status** to completed

### Smart Features:
- **Multi-region AI** - Uses multiple Google Cloud regions
- **Retry Logic** - Handles rate limits and failures
- **Resource Cleanup** - Deletes temp files automatically
- **Correlation IDs** - Track requests through logs

## 🌐 Deploy to Production

```bash
# Setup Google Cloud (one time)
make setup-gcp
make create-secrets

# Deploy both API and Worker services
make deploy
```

Your API will be live at: `https://tiktok-workout-parser-xxx.run.app`

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

**Videos stuck in "pending" status**
```bash
# Check if worker is running
curl http://localhost:8081/health
# Restart if needed
make dev-force
```

## 💰 Costs

### Google Cloud (Free Tier)
- **2 million requests/month** - FREE
- **After free tier** - ~$0.40 per million requests

### Typical Monthly Costs
- **Personal use** (< 1,000 videos): $0-5
- **Small business** (10,000 videos): $10-30
- **High volume** (100,000 videos): $50-150

## 🏆 What Makes This Special

- **Smart Caching** - Popular videos are instant
- **Hybrid Processing** - Fast when quiet, scalable when busy
- **Production Ready** - Handles failures, retries, monitoring
- **Cost Efficient** - Only pay for what you use
- **Open Source** - Customize however you want

## 👨‍💻 For Developers

### Development Workflow

#### Starting Development
```bash
# Get everything running
make dev

# Or run services separately:
make dev-api      # Just API (port 8080)
make dev-worker   # Just Worker (port 8081)
make dev-force    # Kill existing processes and restart
```

#### Making Changes
```bash
# 1. Edit code (auto-reloads on save)
# - API code: main.py, src/services/*.py
# - Worker code: src/worker/*.py
# - Models: src/models/*.py

# 2. Test your changes
curl http://localhost:8080/health
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123"}'

# 3. Check code quality
make lint
make format
make security
```

### Testing

#### Manual Testing
```bash
# Health checks
curl http://localhost:8080/health    # API health
curl http://localhost:8081/health    # Worker health

# Test video processing (use real TikTok or Instagram URLs)
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'

# Test Instagram processing
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/reel/CS7CshJjb15/"}'

# Test error handling
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "invalid-url"}'

# Check queue status
curl http://localhost:8080/status

# Test job status (if you get a job_id)
curl http://localhost:8080/status/your_job_id_here
```

#### Testing Different Scenarios
```bash
# Test cached video (should be instant)
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'

# Test new video (will queue or process directly)
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/NEW_VIDEO_ID"}'

# Test Instagram video
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/reel/CS7CshJjb15/"}'

# Test invalid URL
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "not-a-valid-url"}'
```

#### Code Quality Checks
```bash
make validate     # Run all checks (lint + security + test)
make lint         # Check code style (black, flake8, mypy)
make format       # Auto-format code with black
make security     # Security checks (bandit, safety)
make test         # Run test suite (if tests exist)
```

### Adding New Features

#### New API Endpoint
1. Edit `main.py`
2. Add your endpoint function:
```python
@app.get("/my-endpoint")
async def my_endpoint():
    return {"message": "Hello!"}
```
3. Test with curl

#### New Service
1. Create `src/services/my_service.py`:
```python
import logging

logger = logging.getLogger(__name__)

class MyService:
    def __init__(self):
        logger.info("MyService initialized")
    
    async def do_something(self):
        # Your logic here
        return "result"
```
2. Import in `main.py` or `worker_service.py`
3. Use in your endpoints

#### Modify Video Processing
1. Edit `src/worker/video_processor.py`
2. Update the processing pipeline
3. Test with real videos

### Debugging

#### Check Logs
```bash
# Local development logs
make dev  # Shows logs from both services in real-time

# Production logs
make logs      # Recent logs
make logs-tail # Follow logs in real-time
```

#### Common Debug Commands
```bash
# Check if services are running
ps aux | grep python
lsof -i :8080  # Check what's using port 8080
lsof -i :8081  # Check what's using port 8081

# Check Firestore connection
# (Should see "Queue service connected" in logs)

# Test external services
curl -X GET "https://api.scrapecreators.com/health"  # If available
```

#### Common Issues
- **Port already in use**: Run `make dev-force`
- **Worker not processing**: Check `curl http://localhost:8081/health`
- **Firestore errors**: Run `make setup-firestore`
- **API key errors**: Check your `.env` file

### Project Structure
```
src/
├── services/           # Business logic
│   ├── tiktok_scraper.py   # Downloads TikTok videos
│   ├── instagram_scraper.py # Downloads Instagram videos
│   ├── url_router.py       # Platform detection and routing
│   ├── genai_service.py    # AI video analysis  
│   ├── cache_service.py    # Result caching
│   └── queue_service.py    # Job queue management
├── worker/             # Background processing
│   ├── worker_service.py   # Main worker process
│   └── video_processor.py  # Video manipulation (handles both platforms)
└── models/             # Data structures
    └── parser_result.py    # Workout JSON format
```

### Environment Variables
```bash
# Required
GOOGLE_CLOUD_PROJECT_ID=your-project-id
SCRAPECREATORS_API_KEY=your-api-key

# Optional
ENVIRONMENT=development  # development|staging|production
PORT=8080               # API port
WORKER_PORT=8081        # Worker port
LOG_LEVEL=INFO          # DEBUG|INFO|WARNING|ERROR
```

## 🤝 Contributing

### Quick Start
1. Fork the repo
2. Create a feature branch: `git checkout -b my-feature`
3. Make your changes
4. Test locally: `make dev` and test with curl
5. Check code quality: `make validate`
6. Commit changes: `git commit -m "Add my feature"`
7. Push and create pull request

### Code Standards
- **Python**: Follow PEP 8, use type hints
- **Async**: All I/O operations should be async
- **Error Handling**: Use custom exceptions, log with context
- **Testing**: Test manually with real TikTok URLs
- **Documentation**: Update README if you change APIs

## 📚 Project Structure

```
sets-ai-backend/
├── main.py                     # Main API service
├── src/
│   ├── services/
│   │   ├── genai_service.py    # AI video analysis
│   │   ├── tiktok_scraper.py   # TikTok video downloading
│   │   ├── instagram_scraper.py # Instagram video downloading
│   │   ├── url_router.py       # Platform detection and routing
│   │   ├── queue_service.py    # Job queue management
│   │   └── cache_service.py    # Result caching
│   └── worker/
│       ├── worker_service.py   # Background processing
│       └── video_processor.py  # Video processing logic (both platforms)
├── Makefile                    # Development commands
└── requirements.txt            # Dependencies
```

---

**Questions?** Open an issue or check the logs with `make logs`