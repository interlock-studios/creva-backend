# Project Structure

This document explains the organization of the TikTok Workout Parser codebase following industry-standard practices.

## Directory Layout

```
sets-ai-backend/
├── src/                          # Source code (all application code lives here)
│   ├── services/                 # Business logic and external integrations
│   │   ├── __init__.py
│   │   ├── cache_service.py      # Firestore cache management
│   │   ├── genai_service.py      # Single Gemini API client
│   │   ├── genai_service_pool.py # Multiple Gemini clients for scaling
│   │   ├── queue_service.py      # Firestore job queue management
│   │   └── tiktok_scraper.py     # TikTok video scraping
│   │
│   ├── worker/                   # Background job processing
│   │   ├── __init__.py
│   │   ├── video_processor.py    # Video manipulation (audio removal)
│   │   └── worker_service.py     # Main worker process for queue
│   │
│   └── models/                   # Data models
│       ├── __init__.py
│       └── parser_result.py      # Workout data structures
│
├── main.py                       # Main API server entry point
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container configuration
├── cloudbuild.yaml              # Main API deployment config
├── cloudbuild-worker.yaml       # Worker deployment config
├── deploy.sh                    # Main API deployment script
├── deploy-worker.sh             # Worker deployment script
│
├── docs/                        # Documentation
│   ├── README.md               # Main documentation
│   ├── FLUTTER_INTEGRATION.md  # Flutter client guide
│   └── PROJECT_STRUCTURE.md    # This file
│
├── tests/                       # Test files (if any)
│   └── ...
│
└── .env.example                 # Environment variables template
```

## Architecture Overview

The application follows a **microservices-inspired monorepo** structure with two deployable services:

### 1. API Service (main.py)
- **Purpose**: Handle HTTP requests, manage queue, serve cached results
- **Responsibilities**:
  - Accept video processing requests
  - Check cache for existing results
  - Queue new jobs for processing
  - Provide job status endpoints
- **Deployed as**: Cloud Run service

### 2. Worker Service (src/worker/worker_service.py)
- **Purpose**: Process videos from queue asynchronously
- **Responsibilities**:
  - Poll queue for new jobs
  - Download and process videos
  - Analyze with Gemini AI
  - Store results in cache
- **Deployed as**: Separate Cloud Run service

## Why This Structure?

### Industry Standards Applied

1. **Separation of Concerns**
   - `services/`: External integrations and business logic
   - `worker/`: Background processing
   - `models/`: Data structures

2. **Scalability**
   - API and Worker can scale independently
   - Multiple workers can process queue in parallel
   - Service pool pattern for rate limit distribution

3. **Maintainability**
   - Clear module boundaries
   - Each service has a single responsibility
   - Easy to test individual components

4. **Deployment Flexibility**
   - Services can be deployed separately
   - Different resource allocations per service
   - Independent scaling policies

## Service Descriptions

### services/cache_service.py
- Manages Firestore document cache
- 1-week TTL for processed videos
- Handles cache invalidation

### services/queue_service.py
- Firestore-based job queue
- Atomic job claiming for workers
- Retry logic for failed jobs
- Priority queue support

### services/genai_service_pool.py
- Manages multiple Gemini API clients
- Round-robin request distribution
- Supports multiple auth methods:
  - Service account files
  - Service account JSON
  - Multiple regions
  - Default credentials

### worker/worker_service.py
- Async job processing
- Health check endpoints
- Graceful shutdown
- Concurrent job handling

## Environment Variables

### Required for Both Services
```bash
GOOGLE_CLOUD_PROJECT_ID=your-project-id
SCRAPECREATORS_API_KEY=your-api-key
```

### Optional for Scaling
```bash
# Multiple service accounts (comma-separated)
GOOGLE_SERVICE_ACCOUNT_FILES=/keys/sa1.json,/keys/sa2.json

# Multiple regions (comma-separated)
GEMINI_LOCATIONS=us-central1,us-east1,europe-west1

# Worker configuration
WORKER_POLLING_INTERVAL=5
MAX_CONCURRENT_PROCESSING=50
```

## Deployment Architecture

```
                    ┌─────────────┐
                    │   Client    │
                    │  (Flutter)  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Cloud Load  │
                    │  Balancer   │
                    └──────┬──────┘
                           │
                ┌──────────┴──────────┐
                │                     │
         ┌──────▼──────┐      ┌──────▼──────┐
         │ API Service │      │ API Service │  (Auto-scaling)
         │ Instance 1  │      │ Instance N  │
         └──────┬──────┘      └──────┬──────┘
                │                     │
                └──────────┬──────────┘
                           │
                    ┌──────▼──────┐
                    │  Firestore  │
                    │   Database  │
                    │ ┌─────────┐ │
                    │ │  Cache  │ │
                    │ │  Queue  │ │
                    │ │ Results │ │
                    │ └─────────┘ │
                    └──────┬──────┘
                           │
                ┌──────────┴──────────┐
                │                     │
         ┌──────▼──────┐      ┌──────▼──────┐
         │Worker Service│     │Worker Service│  (Auto-scaling)
         │  Instance 1 │      │  Instance N │
         └──────┬──────┘      └──────┬──────┘
                │                     │
                └──────────┬──────────┘
                           │
                    ┌──────▼──────┐
                    │  Gemini AI  │
                    │   (Vertex)  │
                    └─────────────┘
```

## Development Workflow

### Local Development
```bash
# Run API locally
python main.py

# Run worker locally (separate terminal)
python -m src.worker.worker_service
```

### Testing
```bash
# Test API endpoints
curl http://localhost:8080/health

# Test worker health
curl http://localhost:8081/health
```

### Deployment
```bash
# Deploy API
./deploy.sh

# Deploy Worker
./deploy-worker.sh
```

## Best Practices

1. **Never put business logic in main.py**
   - Keep it as a thin entry point
   - All logic goes in services/

2. **Use dependency injection**
   - Services are instantiated at module level
   - Easy to mock for testing

3. **Handle errors gracefully**
   - Workers retry failed jobs
   - API returns appropriate status codes

4. **Monitor everything**
   - Health endpoints for both services
   - Queue statistics endpoint
   - Structured logging

5. **Scale horizontally**
   - Add more worker instances for throughput
   - Add more API instances for availability