# Sets AI Backend - Integration Product Requirements Document (PRD)

## Overview
This document outlines the integration strategy for Sets AI Backend dual-service architecture, enabling backward compatibility while supporting new feature development.

## Current Architecture

### Service Deployment Strategy
```
┌─────────────────────────────────────────────────────────────────┐
│                     Sets AI Backend Architecture                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Legacy Service (Current App)    │    V2 Service (Future App)   │
│  ─────────────────────────────    │    ─────────────────────    │
│                                   │                             │
│  zest-parser (legacy)             │    zest-parser (current)    │
│  ├─ API: concise responses        │    ├─ API: verbose responses│
│  ├─ Branch: pre-localization      │    ├─ Branch: main          │
│  ├─ URL: zest-parser.run.app      │    ├─ URL: zest-parser-g4z  │
│  └─ Worker: zest-parser-worker    │    └─ Worker: current-worker│
│                                   │                             │
└─────────────────────────────────────────────────────────────────┘
```

## Service Specifications

### Legacy Service (zest-parser-legacy)
**Purpose**: Maintain backward compatibility for current mobile app
- **Branch**: `pre-localization`
- **Service Name**: `zest-parser-legacy`
- **API URL**: `https://zest-parser-g4zcestszq-uc.a.run.app`
- **Worker URL**: `https://zest-parser-worker-g4zcestszq-uc.a.run.app`
- **Response Format**: Concise (original format)
- **Rate Limiting**: Original settings (10 req/min)

### Current Service (zest-parser) ✅ DEPLOYED
**Purpose**: Support new features and enhanced functionality
- **Branch**: `main`
- **Service Name**: `zest-parser`
- **API URL**: `https://zest-parser-g4zcestszq-uc.a.run.app`
- **Worker URL**: `https://zest-parser-worker-g4zcestszq-uc.a.run.app`
- **Response Format**: Verbose (enhanced with metadata)
- **Rate Limiting**: Disabled (999,999 req/min)
- **Status**: 🟢 **LIVE AND TESTED**

#### V2 Service Test Endpoints
```bash
# Health Check
curl https://zest-parser-g4zcestszq-uc.a.run.app/health

# Process Video
curl -X POST https://zest-parser-g4zcestszq-uc.a.run.app/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/t/ZT6QvLBvy/"}'

# Check Status  
curl https://zest-parser-g4zcestszq-uc.a.run.app/status/{job_id}
```

## API Endpoints

### Common Endpoints (Both Services)
```
GET  /health                    # Service health check
POST /process                   # Process TikTok/Instagram video
GET  /status/{job_id}          # Check processing status
GET  /test-api                 # API validation
POST /cache/invalidate         # Cache management
```

## API Response Formats

### Key Differences Summary

| Aspect | Legacy Service (Pre-localization) | V2 Service (Main Branch) |
|--------|-----------------------------------|---------------------------|
| **Response Style** | Concise, minimal fields | Verbose, detailed metadata |
| **Completed Processing** | Wrapped in `result` object | Direct workout object |
| **Health Check** | Basic status + timestamp | Full service breakdown |
| **Error Format** | Simple error message | Structured error with codes |
| **Status Response** | Minimal job info | Detailed job tracking |
| **Rate Limiting** | 10 req/min (original) | 999,999 req/min (disabled) |
| **Timeout** | 5 min worker timeout | 15 min worker timeout |

### POST /process Endpoint

#### V2 Service - Completed Processing (Direct Response)
```json
{
  "title": "Deep Core Workout",
  "description": "Workout focusing on core strength using dumbbells",
  "workout_type": "full body",
  "duration_minutes": 15,
  "difficulty_level": 4,
  "exercises": [
    {
      "name": "Dumbbell Leg Lowers",
      "muscle_groups": ["abs", "core"],
      "equipment": "Dumbbells",
      "sets": [
        {
          "reps": 10,
          "weight_lbs": 5.0,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": 60
        }
      ],
      "instructions": null
    },
    {
      "name": "Dumbbell Russian Twists",
      "muscle_groups": ["abs", "obliques", "core"],
      "equipment": "Dumbbells",
      "sets": [
        {
          "reps": 10,
          "weight_lbs": 5.0,
          "duration_seconds": null,
          "distance_miles": null,
          "rest_seconds": 60
        }
      ],
      "instructions": null
    }
  ],
  "tags": ["fullbodyworkout", "dumbbellworkout", "shygirlworkout"],
  "creator": "fit with coco"
}
```

#### V2 Service - Queued Processing
```json
{
  "status": "queued",
  "job_id": "unknown_1755573460514",
  "message": "Video queued for processing. Check status with job_id.",
  "check_url": "/status/unknown_1755573460514"
}
```

#### Legacy Service - Expected Format (Pre-localization)
```json
{
  "status": "completed",
  "result": {
    "title": "Core Workout",
    "exercises": [
      {
        "name": "Leg Lowers",
        "sets": [{"reps": 10}]
      }
    ]
  }
}
```

### GET /status/{job_id} Endpoint

#### V2 Service - Processing Status
```json
{
  "status": "processing",
  "created_at": "2025-08-19T03:17:40.514482+00:00",
  "attempts": 1,
  "last_error": null
}
```

#### V2 Service - Completed Status
```json
{
  "status": "completed",
  "result": {
    "title": "Incline Walk with Lifting",
    "description": "Low intensity cardio with lifting to burn fat.",
    "workout_type": "full body",
    "duration_minutes": 30,
    "difficulty_level": 4,
    "exercises": [
      {
        "name": "Incline Walk",
        "muscle_groups": ["legs", "glutes", "calves"],
        "equipment": "Treadmill",
        "sets": [
          {
            "reps": null,
            "weight_lbs": null,
            "duration_seconds": 1800,
            "distance_miles": null,
            "rest_seconds": null
          }
        ],
        "instructions": null
      }
    ],
    "tags": ["FullBodyWorkout", "PilatesForWomen", "StrongGirls"],
    "creator": null
  },
  "completed_at": "2025-08-19T00:46:01.310126+00:00"
}
```

#### V2 Service - Failed Status
```json
{
  "status": "failed",
  "created_at": "2025-08-19T01:29:43.025465+00:00",
  "attempts": 3,
  "last_error": "TikTokAPIError: TIKTOK_API_ERROR: Failed to download TikTok video: No video download URL found"
}
```

#### Legacy Service - Expected Status Format
```json
{
  "status": "completed",
  "result": {
    "title": "Workout",
    "exercises": [...]
  }
}
```

### GET /health Endpoint

#### V2 Service - Health Response
```json
{
  "status": "healthy",
  "timestamp": "2025-08-19T03:17:53.014269",
  "environment": "production",
  "project_id": "sets-ai",
  "version": "1.0.0",
  "services": {
    "cache": "healthy",
    "queue": "active",
    "tiktok_scraper": "healthy",
    "app_check": "healthy"
  }
}
```

#### Legacy Service - Expected Health Format
```json
{
  "status": "healthy",
  "timestamp": "2025-08-19T03:17:53.014269"
}
```

### Error Response Format

#### V2 Service - Error Response
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Failed to process video: 403 Missing or insufficient permissions.",
    "status_code": 500
  },
  "request_id": "1755572227.0300229-140224122077456",
  "timestamp": "2025-08-19T02:57:10.595122Z",
  "path": "/process"
}
```

#### Legacy Service - Expected Error Format
```json
{
  "error": "Failed to process video",
  "status": "error"
}
```

## Integration Timeline

### Phase 1: Dual Service Deployment ✅ COMPLETE
- [x] Deploy V2 service with new name (`zest-parser`)
- [x] Configure separate Artifact Registry repository
- [x] Set up independent service accounts and permissions
- [x] Disable rate limiting on V2 service
- [x] Increase worker timeout to 15 minutes

### Phase 2: Legacy Service Deployment 🔄 PENDING
- [ ] Deploy legacy service from `pre-localization` branch
- [ ] Maintain legacy service name (`zest-parser-legacy`)
- [ ] Preserve original response format
- [ ] Ensure zero downtime for current app users

### Phase 3: App Migration Strategy 📋 PLANNED
- [ ] Current app continues using legacy service
- [ ] New app versions point to V2 service
- [ ] Gradual migration based on app update adoption
- [ ] Monitor usage patterns across both services

## Technical Specifications

### Resource Configuration

#### Legacy Service
```yaml
API Service:
  memory: 2Gi
  cpu: 2
  timeout: 900s (15 min)
  concurrency: 100
  min_instances: 1
  max_instances: 10

Worker Service:
  memory: 4Gi
  cpu: 4
  timeout: 300s (5 min)  # Original timeout
  concurrency: 10
  min_instances: 3
  max_instances: 50
```

#### V2 Service
```yaml
API Service:
  memory: 2Gi
  cpu: 2
  timeout: 900s (15 min)
  concurrency: 100
  min_instances: 1
  max_instances: 10

Worker Service:
  memory: 4Gi
  cpu: 4
  timeout: 900s (15 min)  # Extended timeout
  concurrency: 10
  min_instances: 3
  max_instances: 50
```

### Environment Variables

#### Shared Configuration
```bash
GOOGLE_CLOUD_PROJECT_ID=sets-ai
ENVIRONMENT=production
SCRAPECREATORS_API_KEY=[secret]
```

#### V2 Specific
```bash
RATE_LIMIT_REQUESTS=999999      # Disabled
RATE_LIMIT_WINDOW=60
WORKER_BATCH_SIZE=10
WORKER_POLLING_INTERVAL=1
```

## Google Cloud Services Used

### Vertex AI (Gemini 2.0 Flash Lite)
- **Endpoint**: `us-central1-aiplatform.googleapis.com`
- **Model**: `gemini-2.0-flash-lite:generateContent`
- **Purpose**: Video analysis and workout extraction
- **Quotas**: High (thousands of requests/minute)

### Cloud Firestore
- **Collections**:
  - `bucket_list_cache` - Processed video cache
  - `processing_queue` - Job queue management
  - `processing_results` - Completed job results
- **Indexes**: Composite indexes for queue queries

### Additional Services
- **Cloud Run**: Hosting API and worker services
- **Artifact Registry**: Docker image storage
- **Secret Manager**: API key storage
- **Cloud Monitoring**: Performance metrics
- **Firebase Admin SDK**: Authentication and Firestore access

## Monitoring & Observability

### Health Check Endpoints
```bash
# Legacy Service
curl https://zest-parser-g4zcestszq-uc.a.run.app/health

# V2 Service  
curl https://zest-parser-g4zcestszq-uc.a.run.app/health
```

### Log Analysis
```bash
# Legacy API Logs
gcloud logging read "resource.labels.service_name=zest-parser"

# V2 API Logs
gcloud logging read "resource.labels.service_name=zest-parser"

# Legacy Worker Logs
gcloud logging read "resource.labels.service_name=zest-parser-worker"

# V2 Worker Logs
gcloud logging read "resource.labels.service_name=zest-parser-worker"
```

### Key Metrics to Monitor
- **Processing Times**: Video analysis duration
- **Success Rates**: Successful vs failed processing
- **Cache Hit Rates**: Efficiency of caching layer
- **Queue Depth**: Pending jobs in processing queue
- **Error Rates**: API and worker error frequencies

## Deployment Commands

### Deploy V2 Service (Current Branch)
```bash
# From main branch
make deploy
```

### Deploy Legacy Service (Pre-localization Branch)
```bash
# Switch to legacy branch
git checkout pre-localization

# Deploy with original service name
make deploy
```

## Migration Strategy

### For Mobile App Teams

#### Current App (Legacy)
```typescript
const API_BASE_URL = 'https://zest-parser-g4zcestszq-uc.a.run.app';

// Existing integration remains unchanged
const response = await fetch(`${API_BASE_URL}/process`, {
  method: 'POST',
  body: JSON.stringify({ url: tiktokUrl })
});
```

#### Future App Versions (V2)
```typescript
const API_BASE_URL = 'https://zest-parser-g4zcestszq-uc.a.run.app';

// Enhanced integration with verbose responses
const response = await fetch(`${API_BASE_URL}/process`, {
  method: 'POST', 
  body: JSON.stringify({ url: tiktokUrl, localization: 'en' })
});

// Access additional metadata
const { title, description, difficulty_level, tags, creator } = response;
```

## Testing Strategy

### Regression Testing
- [ ] Verify legacy service maintains exact response format
- [ ] Test all existing app integrations with legacy service
- [ ] Validate V2 service provides enhanced data structure

### Performance Testing
- [ ] Load test both services independently
- [ ] Verify cache sharing between services
- [ ] Monitor resource utilization patterns

### Integration Testing
- [ ] Test video processing pipeline on both services
- [ ] Verify Firestore data consistency
- [ ] Validate error handling and retry logic

## Risk Mitigation

### Rollback Strategy
- **Legacy Service**: Can be rolled back to any previous revision
- **V2 Service**: Independent rollback without affecting legacy users
- **Database**: Shared Firestore collections remain compatible

### Monitoring Alerts
- **Service Health**: Alert on degraded status
- **Processing Failures**: Alert on high error rates
- **Resource Usage**: Alert on high CPU/memory usage
- **Queue Depth**: Alert on processing backlog

## Success Criteria

### Technical Metrics
- ✅ **Zero Downtime**: Legacy service maintains 99.9% uptime
- ✅ **Performance**: V2 service handles increased load
- ✅ **Compatibility**: Legacy responses match original format exactly
- ✅ **Enhanced Features**: V2 provides additional metadata and functionality

### Business Metrics
- **User Experience**: No degradation for current app users
- **Development Velocity**: Faster feature development on V2
- **Scalability**: Independent scaling based on usage patterns
- **Cost Efficiency**: Optimized resource allocation per service

## Future Considerations

### Service Evolution
- **Legacy Service**: Maintenance mode, security updates only
- **V2 Service**: Active development, new features
- **Migration Timeline**: Gradual user migration over 6-12 months
- **Deprecation**: Legacy service retirement after full migration

### Feature Roadmap
- **Localization Support**: Enhanced in V2 service
- **Advanced Analytics**: V2-specific features
- **Real-time Processing**: V2 optimizations
- **Multi-platform Support**: Extended platform coverage

---

**Document Version**: 1.0  
**Last Updated**: 2025-08-18  
**Next Review**: 2025-09-18
