# Project Structure

**Quick guide to understanding and working with the Creva backend codebase.**

## 📁 What's Where

```
creva-backend/
├── main.py                    # 🚀 Main API server - start here
├── src/
│   ├── services/              # 🔧 All the business logic
│   │   ├── tiktok_scraper.py        #   TikTok video downloading & metadata
│   │   ├── instagram_scraper.py     #   Instagram reels via ScrapeCreators
│   │   ├── url_router.py            #   Platform detection and URL validation
│   │   ├── genai_service.py         #   Gemini AI transcription
│   │   ├── genai_service_pool.py    #   GenAI pool for workers
│   │   ├── cache_service.py         #   Firestore caching (365+ days)
│   │   ├── queue_service.py         #   Firestore job queue
│   │   └── config_validator.py      #   Env validation
│   ├── worker/                # 🏭 Background processing
│   │   ├── worker_service.py  #   Main worker process
│   │   └── video_processor.py #   Video processing pipeline
│   └── models/                # 📋 Data structures
│       └── responses.py       #   Response JSON format
├── Makefile                   # 🛠️ Commands (dev, deploy, etc.)
├── requirements.txt           # 📦 Python dependencies
└── .env.example              # ⚙️ Environment variables template
```

## 🏗️ How It All Works

### Two Main Services
1. **API Service** (`main.py`) - Handles web requests, checks cache, queues jobs
2. **Worker Service** (`src/worker/`) - Processes videos in the background

### Key Components
- **Services** - Each handles one thing (scraping, AI, cache, queue)
- **Worker** - Runs separately, processes videos from queue
- **Models** - Defines what the response JSON looks like

## 🎯 Core Purpose

Creva Backend extracts creator content from TikTok and Instagram videos:
- **Transcripts** - Full text of what's said in the video
- **Hooks** - Attention-grabbing opening lines (first 30 seconds)
- **Metadata** - Title, description, creator, platform

## 🛠️ Development Workflow

### Starting Development
```bash
# Get everything running
make dev

# This starts:
# - API server (port 8080)
# - Worker service (port 8081)
```

### Working on the API
```bash
# Just run the API
make dev-api

# Edit main.py or src/services/*.py
# Server auto-reloads on changes
```

### Working on the Worker
```bash
# Just run the worker
make dev-worker

# Edit src/worker/*.py
# Worker auto-reloads on changes
```

### Testing Your Changes
```bash
# Health checks
curl http://localhost:8080/health
curl http://localhost:8081/health

# Test processing a video
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123"}'

# Check code quality
make lint
make test
```

## 🔧 Adding New Features

### Adding a New API Endpoint
1. Edit `main.py` or create new file in `src/api/`
2. Add your endpoint function
3. Test with curl

### Adding New Business Logic
1. Create or edit files in `src/services/`
2. Import in `main.py` or `worker_service.py`
3. Use dependency injection pattern

### Modifying Video Processing
1. Edit `src/worker/video_processor.py`
2. Worker will auto-reload
3. Test with a real video

### Changing Response Format
1. Edit `src/models/responses.py`
2. Update both API and Worker code
3. Test end-to-end

## 🚀 Deployment

### Local Testing
```bash
# Test Docker build
make docker-build
make docker-run
```

### Deploy to Production
```bash
# Deploy to creva-e6435
make deploy

# Preview (single region)
make deploy-preview
```

## 🔍 Debugging Tips

### Check Logs
```bash
# Local logs
make dev  # Shows logs from both services

# Production logs
make logs
```

### Common Issues
```bash
# Worker not processing?
curl http://localhost:8081/health

# Queue stuck?
curl http://localhost:8080/status

# Firestore issues?
make setup-firestore
```

## 📝 Code Patterns

### Services Pattern
```python
# Each service is a class with clear methods
class TikTokScraper:
    def __init__(self):
        # Setup
    
    async def scrape_video(self, url):
        # Do the work
```

### Async Everything
```python
# All I/O operations are async
async def process_video(url: str):
    result = await scraper.scrape_video(url)
    analysis = await ai_service.transcribe(result)
    await cache.store(url, analysis)
```

## 🎯 Best Practices

1. **Keep main.py thin** - Just routing, all logic in services
2. **One class per file** - Easy to find and test
3. **Async for I/O** - Network calls, file operations, database
4. **Error handling** - Catch specific exceptions, log with context
5. **Configuration** - Use environment variables, validate on startup
6. **Cache aggressively** - 365+ day cache for video content

## 💡 Quick Tips

- **New to the codebase?** Start with `main.py` and follow the imports
- **Adding features?** Look at existing services for patterns
- **Debugging?** Add logging with request IDs for tracing
- **Testing?** Use `make dev` and curl commands
- **Deploying?** `make deploy` handles everything

---

**Questions?** Check the logs, use health endpoints, or run `make help`
