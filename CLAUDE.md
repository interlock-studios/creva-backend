# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Social Media Workout Parser is a Python FastAPI backend service that transforms TikTok and Instagram workout videos into structured workout data. The system features:
- **Multi-Platform Support**: TikTok and Instagram video processing
- **Hybrid Processing**: Direct processing for low traffic, queue-based for high traffic
- **AI-Powered Analysis**: Google Gemini 2.0 Flash with multi-location service pooling
- **Video Processing**: Automated video scraping and audio removal
- **Queue System**: Firestore-based job queue with auto-scaling workers
- **Smart Caching**: Firestore cache with 1-week TTL for instant results
- **Cloud Deployment**: Google Cloud Run with integrated API and Worker services
- **Production Ready**: Comprehensive error handling, logging, and monitoring

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
make run                   # Run production mode locally
python main.py             # Direct execution (port 8080)

# Testing and validation
make test                  # Run test suite with pytest
make lint                  # Run all linters (black, flake8, mypy, bandit)
make format                # Format code with black
make security              # Run security checks (bandit, safety, pip-audit)
make validate              # Run all validation checks (lint + security + test)
```

### Docker Development
```bash
# Container operations
make docker-build          # Build Docker image locally
make docker-run            # Run containerized app locally
make docker-test           # Build and test Docker image
```

### Cloud Deployment
```bash
# Google Cloud setup
make setup-gcp             # Configure GCP project and enable APIs
make create-secrets        # Store API keys in Secret Manager
make update-secrets        # Update existing secrets

# Deployment
make deploy                # Deploy to production (Google Cloud Run)
make deploy-staging        # Deploy to staging environment

# Monitoring
make logs                  # View recent Cloud Run logs
make logs-tail             # Tail logs in real-time
make service-info          # Display Cloud Run service information
make test-api              # Test deployed API endpoints
```

### API Testing
```bash
# Local testing
curl http://localhost:8080/health
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"}'

# Production testing
curl https://workout-parser-ty6tkvdynq-uc.a.run.app/health
curl -X POST https://workout-parser-ty6tkvdynq-uc.a.run.app/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/1234567890"}'

# Instagram testing
curl -X POST https://workout-parser-ty6tkvdynq-uc.a.run.app/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/reel/CS7CshJjb15/"}'
```

## Architecture Overview

### FastAPI Application (main.py)
**Key Components:**
- **Middleware Stack**: CORS, Trusted Host, Request ID tracking, and timing
- **Error Handling**: Global exception handler with structured error responses
- **Logging**: Structured JSON logging with request correlation IDs
- **Health Monitoring**: Health check endpoint for container orchestration
- **Environment Management**: Development/staging/production configuration

**Core Endpoints:**
- `POST /process`: Main video processing endpoint (hybrid: direct or queued)
- `GET /status/{job_id}`: Check status of queued processing jobs
- `GET /status`: System status with queue statistics
- `GET /health`: Container health check
- `GET /test-api`: API connection validation

### Service Layer Architecture
**Key Services:**
- `src/services/genai_service.py`: Google Gemini AI integration
- `src/services/genai_service_pool.py`: Multi-location Gemini service pool for scaling
- `src/services/tiktok_scraper.py`: TikTok video scraping and API integration
- `src/services/instagram_scraper.py`: Instagram video scraping and API integration
- `src/services/url_router.py`: Platform detection and URL routing
- `src/services/queue_service.py`: Firestore-based job queue management
- `src/services/cache_service.py`: Firestore cache with TTL for instant results
- `src/services/config_validator.py`: Environment configuration and validation
- `src/worker/video_processor.py`: Video download and audio processing (handles both platforms)
- `src/worker/worker_service.py`: Background worker service for queue processing

**Data Models:**
- `src/models/parser_result.py`: Pydantic models for video metadata
- Structured workout JSON output with exercises, sets, and instructions

### Video Processing Pipeline (Hybrid Architecture)

**For Cached Videos (90% of popular workouts):**
1. **URL Validation**: Platform detection (TikTok/Instagram) and URL normalization
2. **Cache Check**: Instant return if video already processed

**For New Videos - Direct Processing (Low Traffic):**
1. **URL Validation**: Platform detection and URL normalization
2. **Capacity Check**: If under 5 concurrent videos
3. **Video Scraping**: Platform-specific scraper (TikTok/Instagram) with metadata extraction
4. **Audio Removal**: FFmpeg processing to create silent video
5. **AI Analysis**: Gemini 2.0 Flash processes video + transcript/caption
6. **Cache Storage**: Store result in Firestore cache
7. **Structured Output**: JSON workout data with exercises, sets, and metadata

**For New Videos - Queue Processing (High Traffic):**
1. **URL Validation**: Platform detection and URL normalization
2. **Queue Enqueue**: Add job to Firestore queue
3. **Job ID Return**: Return job_id for status tracking
4. **Worker Processing**: Background worker processes from queue
5. **Status Updates**: Job status updated in Firestore
6. **Result Storage**: Final result stored in cache and results collection

### External Services Integration
**ScrapeCreators API:**
- TikTok video downloading (no watermark)
- Instagram video downloading (posts and reels)
- Metadata extraction (title, author, statistics)
- Transcript extraction from TikTok videos
- Caption extraction from Instagram posts/reels
- Comprehensive error handling and retry logic

**Google Gen AI (Gemini with Service Pool):**
- Multi-location service pool (us-central1, us-east1, europe-west1)
- Video content analysis with transcript
- Structured JSON output generation
- Rate limiting and retry with exponential backoff
- Automatic failover between regions
- Custom prompts for fitness content extraction

**FFmpeg Processing:**
- Audio removal from downloaded videos
- Video codec copying for efficiency
- Temporary file management and cleanup

## Development Patterns

### Error Handling Strategy
- **Custom Exceptions**: `APIError`, `ValidationError`, `NetworkError`
- **Retry Logic**: Exponential backoff for rate limits and transient failures
- **User-Friendly Messages**: Clear error responses for different failure modes
- **Request Tracking**: Correlation IDs for debugging and monitoring

### Async Programming
- **Async/Await**: All I/O operations use async patterns
- **HTTP Clients**: httpx for async HTTP requests
- **Concurrent Processing**: Efficient handling of video download and processing

### Configuration Management
- **Environment Variables**: All secrets and config via environment
- **Secret Management**: Google Secret Manager for production secrets
- **Multi-Environment**: Development, staging, production configurations

### Production Best Practices
- **Health Checks**: Container orchestration compatibility
- **Structured Logging**: JSON logs with correlation IDs and timing
- **Request Middleware**: CORS, security headers, request tracking
- **Resource Management**: Proper cleanup of temporary files and connections

## API Structure

### Request/Response Patterns
```python
# Process Request (TikTok or Instagram)
{
    "url": "https://www.tiktok.com/@lastairbender222/video/7518493301046119710"
}
# or
{
    "url": "https://www.instagram.com/reel/CS7CshJjb15/"
}

# Direct/Cached Response (Immediate)
{
    "title": "Full Body HIIT Workout",
    "description": "Intense 15-minute full body workout",
    "workout_type": "hiit",
    "duration_minutes": 15,
    "difficulty_level": 8,
    "exercises": [
        {
            "name": "Burpees",
            "muscle_groups": ["full_body"],
            "equipment": "bodyweight",
            "sets": [{"reps": 15, "rest_seconds": 30}],
            "instructions": "Start standing, drop to plank, jump back up"
        }
    ],
    "tags": ["hiit", "cardio", "fullbody"],
    "creator": "@fitnessuser"
}

# Queued Response (When At Capacity)
{
    "status": "queued",
    "job_id": "req123_1234567890",
    "message": "Video queued for processing. Check status with job_id.",
    "check_url": "/status/req123_1234567890"
}

# Status Check Response (Processing)
{
    "status": "processing",
    "created_at": "2024-01-01T12:00:00",
    "attempts": 1
}

# Status Check Response (Completed)
{
    "status": "completed",
    "result": {
        "title": "Full Body HIIT Workout",
        "description": "Intense 15-minute full body workout",
        "exercises": [...]
    },
    "completed_at": "2024-01-01T12:01:30"
}
```

### Error Response Structure
```python
{
    "detail": "Error description",
    "request_id": "correlation-id",
    "timestamp": "2024-01-01T12:00:00Z"
}
```

## Environment Configuration

### Required Environment Variables
```bash
# Core Configuration
GOOGLE_CLOUD_PROJECT_ID=your-project-id
SCRAPECREATORS_API_KEY=your-api-key
ENVIRONMENT=development|staging|production

# Optional Configuration
PORT=8080                    # Override default port
LOG_LEVEL=INFO              # Logging level
```

### Development Setup
```bash
# 1. Copy environment template
cp .env.example .env

# 2. Set required variables
nano .env  # Edit with your API keys

# 3. Install dependencies
make setup

# 4. Run development server
make dev
```

## Deployment Architecture

### Google Cloud Run
**Key Features:**
- **Serverless**: Auto-scaling with pay-per-request
- **Container-based**: Docker deployment with Cloud Build
- **Secret Management**: Environment variables from Secret Manager
- **Load Balancing**: Automatic traffic distribution
- **Custom Domains**: HTTPS with managed certificates

### CI/CD Pipeline
**GitHub Actions Integration:**
- **Branch-based Deployment**: `main` → production, `staging` → staging
- **Automated Testing**: PR validation with test suite
- **Container Registry**: Google Artifact Registry
- **Workload Identity**: Secure GCP authentication

### Monitoring & Observability
- **Structured Logs**: JSON format with correlation IDs
- **Health Endpoints**: Container orchestration monitoring  
- **Performance Headers**: Request timing information
- **Error Tracking**: Comprehensive error logging and alerting

## Feature Development Process

### Quick Summary
```
1. User specifies feature → 2. Discuss & refine → 3. Create PRD
→ 4. Get PRD approval → 5. Search existing code → 6. Implement with error checking
→ 7. Fix errors (2 attempts max) → 8. Ask for help if needed
```

### Detailed Workflow

1. **Initial Discussion**
   - User states what they're working on
   - Clarify if changes affect API, processing, or deployment
   - Identify integration points and dependencies

2. **Requirements Gathering**
   - Define API changes and backward compatibility
   - Specify error handling requirements
   - Clarify performance and scalability needs
   - Validate assumptions about video processing or AI analysis

3. **PRD Creation**
   - Create PRD in `/PRDs/Backend/` folder
   - Name format: `YYYY-MM-DD-feature-name.md`
   - Include API specification, error handling, and deployment considerations
   - Finalize PRD based on discussion

4. **PRD Approval**
   - Present finalized PRD to user
   - Wait for explicit approval before implementation
   - Make any requested changes

5. **Implementation Phase**
   - **Pre-Implementation Checks**:
     - ALWAYS grep/search for existing services, models, and utilities
     - Read existing code patterns before creating anything new
     - Identify reusable components and error handling patterns
   
   - **During Implementation**:
     - Follow existing async patterns and error handling
     - Use established logging and monitoring practices
     - Ensure proper cleanup of resources (temp files, connections)
     - Test with real TikTok URLs and error scenarios
     - Run validation checks:
       - `make lint` for code quality
       - `make security` for security issues
       - `make test` for unit tests (when available)
       - `make docker-build` to verify containerization
   
   - **Error Handling Protocol**:
     - If build error occurs: Fix and retry
     - If error persists: **Use "ultrathink"** mode for deep analysis
     - If still failing after 2 attempts with ultrathink: Ask for human intervention
     - Document the issue clearly when asking for help

6. **Code Quality Standards**
   - Follow existing FastAPI patterns and async best practices
   - Maintain error handling consistency with existing services
   - Use structured logging with correlation IDs
   - Ensure proper resource cleanup and connection management

## Code Style Guidelines

### Search Before Creating
- **ALWAYS use grep to find existing patterns**:
  ```bash
  grep -r "class.*Service" src/        # Find service patterns
  grep -r "async def.*process" src/    # Find processing patterns
  grep -r "APIError\|ValidationError" src/  # Find error handling
  grep -r "logger\." src/              # Find logging patterns
  ```

### FastAPI Conventions
- **Async First**: All I/O operations should be async
- **Dependency Injection**: Use FastAPI's dependency system
- **Pydantic Models**: Type-safe request/response models
- **Error Handling**: Custom exceptions with proper HTTP status codes
- **Documentation**: Docstrings for all public methods

### Python Best Practices
- **Type Hints**: Use typing annotations for all function signatures
- **Error Handling**: Specific exception types with context
- **Resource Management**: Proper cleanup of files and connections
- **Logging**: Structured logging with appropriate levels
- **Security**: Input validation and sanitization

### Code Organization
```
src/
├── models/          # Pydantic data models
├── services/        # Business logic services
└── worker/          # Background processing tasks
```

### Testing Standards
- **Unit Tests**: Test individual components with pytest
- **Integration Tests**: Test API endpoints and external service integration
- **Mock External Services**: Use pytest-mock for external API calls
- **Error Scenario Testing**: Test various failure modes

## Debugging Process

### Quick Summary
1. Check application logs for errors and timing
2. Run `make lint` and `make security` for code issues  
3. Test API endpoints with curl or Python requests
4. Verify external service connectivity
5. Use structured logging to trace request flow

### Detailed Debugging Workflow

1. **Identify the Issue**
   - Check console logs for error messages and stack traces
   - Review request correlation IDs for tracing
   - Examine API response status codes and timing

2. **Local Development Debugging**
   ```bash
   # Run with verbose logging
   ENVIRONMENT=development LOG_LEVEL=DEBUG make dev
   
   # Test specific endpoints
   curl -v http://localhost:8080/health
   curl -v http://localhost:8080/test-api
   
   # Check code quality
   make validate
   ```

3. **External Service Issues**
   ```bash
   # Test ScrapeCreators API directly
   python example_usage.py
   
   # Verify Google Cloud authentication
   gcloud auth application-default print-access-token
   
   # Check API keys and environment variables
   echo $SCRAPECREATORS_API_KEY | cut -c1-10  # Show first 10 chars
   ```

4. **Production Debugging**
   ```bash
   # View recent logs
   make logs
   
   # Tail logs in real-time
   make logs-tail
   
   # Check service status
   make service-info
   
   # Test deployed API
   make test-api
   ```

### Debug Tools
- **Structured Logging**: Request IDs and timing information
- **Health Endpoints**: Service status and dependency checks
- **Error Responses**: Detailed error messages with context
- **Container Logs**: Cloud Run logging with structured JSON

### Common Issues and Solutions

#### "API key not found" error
```bash
# Check environment variables
env | grep SCRAPECREATORS_API_KEY
# Update secrets in production
make update-secrets
```

#### "Video processing failed" error
```bash
# Check FFmpeg availability
ffmpeg -version
# Test video download separately
python example_usage.py
```

#### "Rate limit exceeded" error
```bash
# Check retry logic and backoff settings
# Monitor Gemini API quotas in Google Cloud Console
```

## Security Best Practices

### API Security
- **Input Validation**: URL validation and sanitization
- **Rate Limiting**: Built-in retry logic with exponential backoff
- **Error Handling**: No sensitive information in error responses
- **CORS Configuration**: Proper origin restrictions for production

### Secret Management
- **Environment Variables**: No secrets in code or version control
- **Google Secret Manager**: Secure storage for production secrets
- **API Key Rotation**: Support for updating API keys without downtime

### Container Security
- **Base Image**: Official Python slim images
- **User Permissions**: Non-root container execution
- **Resource Limits**: Memory and CPU limits in production
- **Security Scanning**: Regular dependency vulnerability checks

### Data Privacy
- **No Data Storage**: Videos and personal data not persisted
- **Temporary Files**: Automatic cleanup of processed content
- **Request Logging**: No sensitive data in application logs
- **HTTPS Only**: Encrypted communication for all endpoints

## Performance Optimization

### Processing Pipeline
- **Async Operations**: Concurrent video download and processing
- **Memory Management**: Temporary file cleanup and resource disposal
- **Caching**: Structured response caching where appropriate
- **Timeout Management**: Configurable timeouts for external services

### Monitoring Metrics
- **Request Timing**: X-Process-Time headers
- **Memory Usage**: Container resource monitoring
- **Error Rates**: HTTP status code tracking
- **External Service Latency**: API call timing and retry metrics

## Production Considerations

### Scalability
- **Cloud Run Auto-scaling**: Handles traffic spikes automatically
- **Stateless Design**: No persistent state between requests
- **Resource Efficiency**: Optimized Docker images and dependency management

### Reliability
- **Health Checks**: Container orchestration compatibility
- **Graceful Degradation**: Fallback behavior for service failures
- **Circuit Breaker**: Retry limits and failure handling
- **Monitoring**: Comprehensive logging and alerting

### Cost Management
- **Pay-per-request**: Cloud Run pricing model
- **Resource Optimization**: Efficient video processing and memory usage
- **API Usage**: Monitored usage of external services
- **Development vs Production**: Environment-specific resource allocation

---

**Architecture Summary (Hybrid Processing):**

**Cached Videos (Instant):**
1. FastAPI receives TikTok/Instagram URL via POST request
2. Cache service checks Firestore for existing result
3. Return cached workout JSON immediately

**Direct Processing (Low Traffic):**
1. FastAPI receives TikTok/Instagram URL via POST request
2. URL Router detects platform (TikTok/Instagram)
3. Check processing capacity (< 5 concurrent)
4. Platform-specific scraper downloads video and extracts metadata/transcript/caption
5. FFmpeg removes audio from video for faster AI processing
6. Google Gemini (multi-region pool) analyzes silent video + transcript/caption
7. Store result in Firestore cache
8. Return structured workout JSON to client

**Queue Processing (High Traffic):**
1. FastAPI receives TikTok/Instagram URL via POST request
2. URL Router detects platform (TikTok/Instagram)
3. Check processing capacity (>= 5 concurrent)
4. Add job to Firestore queue
5. Return job_id for status tracking
6. Worker service processes jobs from queue in background
7. Worker updates job status in Firestore
8. Client polls status endpoint with job_id
9. Final result cached and returned when complete

**Components:**
- Main API Service (Cloud Run): Direct processing + queue management
- Worker Service (Cloud Run): Background queue processing
- Firestore Queue: Reliable job queue with status tracking
- Firestore Cache: 1-week TTL for instant results
- All operations logged with correlation IDs for monitoring