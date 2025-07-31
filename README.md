# TikTok Workout Parser

**Turn any TikTok workout video into structured JSON data in seconds!**

Send a TikTok URL → Get back structured workout data with exercises, sets, reps, and instructions.

## 🚀 Try It Now

**Live API:** https://tiktok-workout-parser-ty6tkvdynq-uc.a.run.app

```bash
curl -X POST "https://tiktok-workout-parser-ty6tkvdynq-uc.a.run.app/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'
```

## 🎯 How It Works

### Simple Flow
1. **Send TikTok URL** → API receives your request
2. **Check Cache** → If we've seen this video before, instant result!
3. **Process Video** → Download video, extract transcript, analyze with AI
4. **Return Data** → Get structured workout JSON

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
Process a TikTok video
```bash
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123"}'
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

### When you send a TikTok URL:

1. **URL Validation** - Check if it's a valid TikTok URL
2. **Cache Check** - Look in Firestore cache (1-week TTL)
3. **If Cached** → Return result instantly
4. **If Not Cached** → Check system capacity
5. **If Low Traffic** → Process directly (10-15 seconds)
6. **If High Traffic** → Add to queue, return job_id

### Background Processing (for queued videos):
1. **Worker picks up job** from Firestore queue
2. **Download video** using ScrapeCreators API
3. **Extract transcript** from video metadata
4. **Remove audio** with ffmpeg (faster AI processing)
5. **Analyze with Gemini AI** (video + transcript)
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

## 🤝 Contributing

1. Fork the repo
2. Make your changes
3. Run `make validate` to check code quality
4. Submit a pull request

## 📚 Project Structure

```
sets-ai-backend/
├── main.py                     # Main API service
├── src/
│   ├── services/
│   │   ├── genai_service.py    # AI video analysis
│   │   ├── tiktok_scraper.py   # Video downloading
│   │   ├── queue_service.py    # Job queue management
│   │   └── cache_service.py    # Result caching
│   └── worker/
│       ├── worker_service.py   # Background processing
│       └── video_processor.py  # Video processing logic
├── Makefile                    # Development commands
└── requirements.txt            # Dependencies
```

---

**Questions?** Open an issue or check the logs with `make logs`