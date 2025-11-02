# Dishly - Recipe Parser

**Extract recipes, ingredients, and cooking instructions from TikTok and Instagram cooking videos with AI-powered analysis!**

Send a TikTok or Instagram recipe video URL → Get back structured recipe data with title, description, ingredients, instructions, and images.

---

## 🚨 CRITICAL INFRASTRUCTURE RULES

### **Dishly Backend is Separate from Zest - NEVER Touch Zest Services**

**Infrastructure Setup:**
- **GCP Project (Shared):** `zest-45e51` - Shared for Cloud Run compute/hosting only
- **Firebase Project (Dishly):** `dishly-prod-fafd3` - Completely separate Firestore database
- **Firebase Project (Zest):** Separate project - **DO NOT ACCESS**

**Deployed Services:**
```
✅ DISHLY (This Project):
- dishly-parser          → https://dishly-parser-g4zcestszq-uc.a.run.app
- dishly-parser-worker   → https://dishly-parser-worker-g4zcestszq-uc.a.run.app

❌ ZEST (DO NOT TOUCH):
- zest-parser            → DO NOT MODIFY
- zest-parser-worker     → DO NOT MODIFY
```

**Service Account:**
```
✅ Dishly: dishly-parser@zest-45e51.iam.gserviceaccount.com
   - Created in: zest-45e51 (Cloud Run project)
   - Has permissions in: zest-45e51 AND dishly-prod-fafd3
   - Used by: Both dishly-parser and dishly-parser-worker

❌ Zest: zest-parser@zest-45e51.iam.gserviceaccount.com
   - DO NOT USE OR MODIFY
```

**Why This Matters:**
- Different service names prevent collisions
- Different Firebase projects prevent data leakage
- Same GCP project for billing consolidation only
- **Zest is a separate production app - do not interfere with it**

**Before ANY deployment or change:**
1. ✅ Verify you're working with `dishly-parser` or `dishly-parser-worker`
2. ✅ Verify Firebase operations use `dishly-prod-fafd3`
3. ❌ NEVER run commands that affect `zest-parser*` services
4. ❌ NEVER modify Zest's Firebase project

---

## 🚀 Try It Now

**Preview API:** run `make deploy-preview` (prints the current preview URL)
**Production API:** Will be available after deployment

```bash
# TikTok Recipe Example
curl -X POST "http://localhost:8080/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@cookingwithlove/video/1234567890"}'

# Instagram Recipe Example
curl -X POST "http://localhost:8080/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/reel/ABC123XYZ/"}'

# With Localization (Spanish recipe)
curl -X POST "http://localhost:8080/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@recetasfaciles/video/9876543210", "localization": "Spanish"}'
```

## 🎯 How It Works

### Simple Flow
1. **Send TikTok/Instagram URL** → API receives your recipe video request
2. **Detect Platform** → Automatically routes to appropriate scraper
3. **Check Cache** → If we've seen this recipe before, instant result!
4. **Process Content** → Download video, extract captions, analyze with AI
5. **Return Data** → Get structured recipe JSON with ingredients and instructions

### Three Response Types

#### 1. Cached (Instant - 90% of popular content)
```json
{
  "title": "Easy Pasta Carbonara",
  "description": "Classic Italian pasta dish ready in 20 minutes",
  "image": "https://example.com/image.jpg",
  "ingredients": [
    "1 lb spaghetti",
    "4 large eggs",
    "1 cup grated parmesan cheese",
    "8 oz bacon or pancetta",
    "2 cloves garlic",
    "Salt and black pepper to taste"
  ],
  "instructions": [
    "Bring a large pot of salted water to boil",
    "Cook spaghetti according to package directions",
    "Fry bacon until crispy, then set aside",
    "Whisk eggs and parmesan together in a bowl",
    "Toss hot pasta with egg mixture",
    "Add bacon and serve with extra parmesan"
  ],
  "servings": "4 servings",
  "prep_time": "10 minutes",
  "cook_time": "15 minutes",
  "tags": ["pasta", "italian", "quick", "dinner"],
  "creator": "@cookingwithlove"
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
curl "http://localhost:8080/status/req123_1234567890"
```

## 🏗️ Technical Overview

### Architecture
- **FastAPI** - Main API service
- **Cloud Run** - Serverless hosting (auto-scales)
- **Firestore** - Queue system and caching
- **Worker Service** - Background recipe processing
- **Google Gemini AI** - Recipe content analysis and extraction

### Smart Processing
- **Cache First** - Popular content returns instantly
- **Direct Mode** - Process immediately when not busy
- **Queue Mode** - Background processing when at capacity
- **Auto-Scale** - Handles 1 user or 10,000 users
 - **Slideshow Aware** - TikTok PhotoMode slideshows supported (HEIC/WEBP auto-converted to JPEG)

## 🚀 Quick Setup (5 minutes)

### Prerequisites
- Python 3.11
- Google Cloud account (free tier works)
- ScrapeCreators API key ([get one here](https://scrapecreators.com))

### Install & Run
```bash
# 1. Navigate to dishly-backend (already forked)
cd dishly-backend
make setup

# 2. Your .env file is already configured with:
# GOOGLE_CLOUD_PROJECT_ID=dishly-476904
# SCRAPECREATORS_API_KEY=TqHKAnqkrYcEQDRFDf2mjyPawR43

# 3. Start everything
make dev
```

That's it! API runs on http://localhost:8080

### What `make dev` starts:
- **API Service** (port 8080) - Handles requests, checks cache
- **Worker Service** (port 8081) - Processes content in background

### Other helpful commands
```bash
make deploy             # Multi-region prod deploy (parallel)
make deploy-sequential  # Sequential deploy
make deploy-preview     # Single-region preview deploy
make setup-security     # Safe Cloud Armor policy
make setup-security-allowlist  # Strict allowlist policy
make test-endpoints     # Test global + primary endpoints
make security-logs      # View Cloud Armor logs
```

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
Process a TikTok or Instagram post/video

**Parameters:**
- `url` (required): TikTok or Instagram URL
- `localization` (optional): Language for response text (e.g., "Spanish", "French", "es", "fr")

```bash
# Basic usage
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/p/DH2NALdyt2s/?igsh=dGR6eWs1d2o0azFk"}'

curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/p/DPCGfg5jKx3/"}'

# With Spanish localization
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123", "localization": "Spanish"}'
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

## 🌍 Localization Support

The API supports **optional localization** to get content in different languages!

### How to Use Localization

Simply add the `localization` parameter to your request:

```json
{
  "url": "https://www.tiktok.com/@user/video/123",
  "localization": "Spanish"
}
```

### Supported Formats

- **Language names**: "Spanish", "French", "Portuguese", "Chinese", "German", "Italian", etc.
- **Language codes**: "es", "fr", "pt", "zh", "de", "it", etc.

### What Gets Localized

When you specify a localization, the following fields are translated:
- ✅ **title** - Content title
- ✅ **description** - Content description  
- ✅ **tips** - Extracted tips or advice
- ✅ **location** - Location information
- ❌ **JSON structure** - Stays the same
- ❌ **content_type** - Stays in English (for consistency)
- ❌ **mood/occasion** - Stays in English (for consistency)

### Example Responses

**English (default):**
```json
{
  "title": "5 Perfect Date Night Ideas",
  "description": "Creative date ideas for couples",
  "tips": [
    "Plan a romantic picnic",
    "Try a cooking class together"
  ]
}
```

**Spanish (`"localization": "Spanish"`):**
```json
{
  "title": "5 Ideas Perfectas para una Noche de Cita",
  "description": "Ideas creativas de citas para parejas",
  "tips": [
    "Planea un picnic romántico",
    "Prueben una clase de cocina juntos"
  ]
}
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

### Background Processing (for queued content):
1. **Worker picks up job** from Firestore queue
2. **Download content** using platform-specific scraper
3. **Extract metadata** - captions, descriptions, location tags
4. **Analyze with Gemini AI** - Extract relationship/lifestyle content
5. **Store result** in cache and results collection
6. **Update job status** to completed

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

Your API will be live at: `https://dishly-parser-g4zcestszq-uc.a.run.app`

## 📊 Monitoring & Analytics

### **🚀 Zest Analytics Dashboard**
Monitor your production deployment with our comprehensive analytics dashboard.

### What You Can Monitor:
- **🔥 Real-time API Performance** - Request rates, response times, error rates
- **📱 Platform Usage** - TikTok vs Instagram processing breakdown
- **🎯 Cache Hit Rates** - See how much traffic is served instantly from cache
- **🔄 Queue Metrics** - Background job processing status and throughput
- **⚡ GenAI Usage** - AI service performance and rate limiting
- **🌍 Geographic Distribution** - Where your users are coming from
- **📊 Business Metrics** - Daily/weekly/monthly usage trends
- **🚨 Alerts & Incidents** - Get notified of any issues immediately

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

**Content stuck in "pending" status**
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
- **Personal use** (< 1,000 recipes): $0-5
- **Small app** (10,000 recipes): $10-30
- **High volume** (100,000 recipes): $50-150

## 🏆 What Makes This Special

- **Smart Caching** - Popular recipes load instantly
- **Hybrid Processing** - Fast when quiet, scalable when busy
- **Production Ready** - Handles failures, retries, monitoring
- **Cost Efficient** - Only pay for what you use
- **AI-Powered** - Intelligent recipe extraction with Gemini 2.0
- **Ingredient Extraction** - Automatically parses ingredients with quantities
- **Step-by-Step Instructions** - Converts videos to clear cooking steps

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

# Test content processing (use real TikTok or Instagram URLs)
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'

curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/p/DN-69RUAD2F"}'

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
dishly-backend/
├── main.py                     # Main FastAPI application
├── src/
│   ├── services/              # Core business logic services
│   │   ├── tiktok_scraper.py      # TikTok recipe video downloading & metadata
│   │   ├── instagram_scraper.py   # Instagram recipe video downloading & metadata
│   │   ├── url_router.py          # Platform detection and URL validation
│   │   ├── genai_service.py       # Single GenAI service instance
│   │   ├── genai_service_pool.py  # Multiple GenAI services for workers
│   │   ├── cache_service.py       # Firestore-based result caching
│   │   ├── queue_service.py       # Firestore-based job queue
│   │   └── config_validator.py    # Environment validation
│   ├── worker/                # Background processing system
│   │   ├── worker_service.py      # Main worker process (Cloud Run service)
│   │   └── video_processor.py     # Video processing pipeline (both platforms)
│   └── models/                # Data structures
│       └── parser_result.py       # Result JSON schema
│       └── responses.py           # Response schemas
├── requirements.txt           # Python dependencies
├── requirements-dev.txt       # Development dependencies
├── Dockerfile                # Container configuration
├── cloudbuild.yaml           # Google Cloud Build configuration
├── Makefile                  # Development commands
└── README.md                 # This file
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

## 📖 Documentation

Comprehensive guides for operations, deployment, and architecture:

- **[Scripts Directory](scripts/README.md)** - All deployment and setup scripts
- **[Edge Security Setup](docs/operations/EDGE_SECURITY_SETUP.md)** - Cloud Armor and bot protection
- **[Performance Optimizations](docs/operations/PERFORMANCE_OPTIMIZATIONS.md)** - Speed improvements
- **[Deployment Guide](docs/operations/DEPLOYMENT_GUIDE.md)** - Production deployment steps
- **[Project Structure](PROJECT_STRUCTURE.md)** - Quick guide to the codebase
- **[Integration PRD](docs/architecture/INTEGRATION_PRD.md)** - Dual-service architecture

### Quick Commands Reference
```bash
# Deployment
make deploy                    # Multi-region deployment
make deploy-preview           # Single-region preview

# Infrastructure
make setup-security           # Edge security (Cloud Armor)
make update-lb-single-region  # Cost optimization (single region)

# Monitoring
make logs                     # View logs
make test-endpoints          # Test all endpoints
make security-logs           # View blocked requests
```

## 📚 Architecture Details

### Service Architecture
- **Main API** (`main.py`): FastAPI service handling HTTP requests
- **Worker Service** (`src/worker/worker_service.py`): Background video processing
- **GenAI Pool** (`src/services/genai_service_pool.py`): Multiple AI service instances
- **Queue System** (`src/services/queue_service.py`): Firestore-based job management
- **Cache System** (`src/services/cache_service.py`): Result caching with TTL

### Processing Flow
1. **Request comes in** → `main.py` receives TikTok/Instagram recipe URL
2. **Platform detection** → `url_router.py` determines TikTok vs Instagram
3. **Cache check** → `cache_service.py` looks for existing results
4. **Processing decision** → Direct processing or queue based on load
5. **Video download** → Platform-specific scraper downloads recipe video
6. **AI analysis** → `genai_service_pool.py` analyzes with Gemini to extract recipe
7. **Result storage** → Cache and return structured recipe data (ingredients, instructions, etc.)

### Scaling Strategy
- **Hybrid processing**: Direct for low load, queue for high load
- **Multiple GenAI services**: Distribute API calls across service accounts
- **Auto-scaling**: Cloud Run scales based on demand
- **Worker instances**: Dedicated background processing capacity

---

**Questions?** Open an issue or check the logs with `make logs`

---

**⚠️ Proprietary Software Notice**

This software is proprietary and confidential. All rights reserved. This codebase contains trade secrets and proprietary technology for AI-powered content analysis. Unauthorized copying, distribution, or reverse engineering is prohibited.
