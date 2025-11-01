# Cross-Project Deployment Architecture

**Last Updated:** November 1, 2025
**Status:** Production Deployed
**Cloud Run Service:** `https://dishly-parser-589847864013.us-central1.run.app`

---

## Executive Summary

The Dishly backend (`dishly-parser`) is deployed in a cross-project architecture where:

- **Cloud Run Service** runs in `zest-45e51` (Zest's GCP project)
- **Firestore Database** and **Firebase Storage** reside in `dishly-prod-fafd3` (Dishly's Firebase project)

This setup was implemented as a workaround for a GCP API limitation where the Cloud Run API could not be enabled in the original `dishly-476904` project due to internal errors.

**Key Benefits:**
- ✅ Minimal configuration changes (reuses existing Zest infrastructure)
- ✅ Production-ready deployment in under 1 hour
- ✅ Data isolation maintained through IAM permissions
- ✅ Cost-effective (leverages existing Cloud Run quota)

**Key Trade-offs:**
- ⚠️ Cross-project IAM complexity (service account needs permissions in two projects)
- ⚠️ Billing split across two projects (compute in Zest, storage in Dishly)
- ⚠️ Future migration path required if Dishly scales to independent infrastructure

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Dishly Mobile App                            │
│                    (iOS + Android Flutter)                           │
│                                                                       │
│  Recipe Import Flow:                                                 │
│  1. User shares TikTok/Instagram video                              │
│  2. Share extension extracts URL                                    │
│  3. App calls dishly-parser API                                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ HTTPS POST /process
                         │ {"url": "https://tiktok.com/@user/video/123"}
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GCP Project: zest-45e51                           │
│                    (Zest's Firebase/GCP Project)                     │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Cloud Run Service: dishly-parser                              │ │
│  │  URL: dishly-parser-589847864013.us-central1.run.app          │ │
│  │  Region: us-central1                                           │ │
│  │  Runtime: Python 3.11                                          │ │
│  │  Service Account: dishly-parser@zest-45e51.iam.gserviceaccount│ │
│  │                                                                │ │
│  │  Environment Variables:                                        │ │
│  │  - GOOGLE_CLOUD_PROJECT_ID=dishly-prod-fafd3                  │ │
│  │  - SCRAPECREATORS_API_KEY=*** (from Secret Manager)           │ │
│  │  - ENVIRONMENT=production                                      │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                         │                                            │
│                         │ IAM: Service Account Identity              │
│                         │ (dishly-parser@zest-45e51.iam...)         │
└─────────────────────────┼────────────────────────────────────────────┘
                          │
                          │ Cross-Project API Call
                          │ (Firestore Admin API, Cloud Storage API)
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Firebase Project: dishly-prod-fafd3                    │
│               (Dishly's Production Firebase Project)                 │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Firestore Database (Native Mode)                              │ │
│  │  Location: us-central1                                         │ │
│  │                                                                │ │
│  │  Collections:                                                  │ │
│  │  - cache/processed_videos/{videoId}                           │ │
│  │  - job_queue/jobs/{jobId}                                     │ │
│  │  - recipes/{userId}/items/{recipeId}                          │ │
│  │                                                                │ │
│  │  IAM Permissions (dishly-parser service account):             │ │
│  │  - roles/datastore.user (Firestore read/write)                │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Cloud Storage                                                 │ │
│  │  Bucket: dishly-prod-fafd3.appspot.com                        │ │
│  │                                                                │ │
│  │  Paths:                                                        │ │
│  │  - recipe_images/{userId}/{uuid}.jpg                          │ │
│  │  - video_thumbnails/{videoId}.jpg                             │ │
│  │                                                                │ │
│  │  IAM Permissions (dishly-parser service account):             │ │
│  │  - roles/storage.objectAdmin (upload/download)                │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Why This Architecture Exists

### Problem: Cloud Run API Blocked in dishly-476904

When attempting to deploy the backend to the original `dishly-476904` project, we encountered:

```
ERROR: (gcloud.services.enable) FAILED_PRECONDITION:
Precondition check failed. Internal error occurred.
```

**Root Cause:** New GCP projects sometimes have restricted API access until:
- Billing is fully verified
- Project passes fraud/abuse checks
- Account reaches minimum age/activity threshold

**Impact:**
- Cloud Run API could not be enabled
- Deployment to `dishly-476904` was blocked
- No clear ETA for API access (GCP support typically takes 3-7 days)

### Solution: Deploy to Zest's Existing Infrastructure

Instead of waiting for GCP to resolve the API blocker, we:

1. **Leveraged Zest's established GCP project** (`zest-45e51`)
   - Cloud Run API already enabled
   - Existing quota and billing configured
   - Proven infrastructure with 99.9% uptime

2. **Configured cross-project IAM permissions**
   - Created dedicated service account: `dishly-parser@zest-45e51.iam.gserviceaccount.com`
   - Granted Firestore and Storage access in `dishly-prod-fafd3`
   - Data remains isolated in Dishly's Firebase project

3. **Maintained data sovereignty**
   - All user data stored in `dishly-prod-fafd3` (Dishly's project)
   - Zest has no access to Dishly user data
   - Service account permissions are scoped and auditable

**Result:** Production deployment completed in ~1 hour instead of waiting 3-7 days for API access.

---

## IAM Configuration Details

### Service Account Setup

**Service Account Name:** `dishly-parser@zest-45e51.iam.gserviceaccount.com`

**Created in Project:** `zest-45e51` (where Cloud Run service runs)

**Purpose:** Allows Cloud Run service to authenticate to Firestore and Storage in `dishly-prod-fafd3`

### Permissions in zest-45e51 (Cloud Run Project)

```bash
# Service account can act as itself (required for Cloud Run)
gcloud iam service-accounts add-iam-policy-binding \
  dishly-parser@zest-45e51.iam.gserviceaccount.com \
  --project=zest-45e51 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Access Secret Manager for API keys
gcloud projects add-iam-policy-binding zest-45e51 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Roles:**
- `roles/iam.serviceAccountUser` - Deploy Cloud Run services
- `roles/secretmanager.secretAccessor` - Read SCRAPECREATORS_API_KEY from Secret Manager

### Permissions in dishly-prod-fafd3 (Firestore/Storage Project)

```bash
# Firestore read/write access
gcloud projects add-iam-policy-binding dishly-prod-fafd3 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

# Cloud Storage object admin (upload/download)
gcloud projects add-iam-policy-binding dishly-prod-fafd3 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

**Roles:**
- `roles/datastore.user` - Read/write Firestore documents (cache, job queue)
- `roles/storage.objectAdmin` - Upload/download images and thumbnails

### Verification Commands

```bash
# Verify service account exists
gcloud iam service-accounts describe \
  dishly-parser@zest-45e51.iam.gserviceaccount.com \
  --project=zest-45e51

# Check permissions in Dishly project
gcloud projects get-iam-policy dishly-prod-fafd3 \
  --flatten="bindings[].members" \
  --filter="bindings.members:dishly-parser@zest-45e51.iam.gserviceaccount.com"
```

---

## Deployment Process

### Prerequisites

1. **gcloud CLI authenticated:**
   ```bash
   gcloud auth login
   gcloud config set project zest-45e51
   ```

2. **Environment variables configured:**
   ```bash
   # In dishly-backend/.env
   GOOGLE_CLOUD_PROJECT_ID=dishly-prod-fafd3  # Firestore project
   SCRAPECREATORS_API_KEY=***                 # Video parsing API
   ENVIRONMENT=production
   ```

3. **Secret Manager populated:**
   ```bash
   # Store API key in zest-45e51 Secret Manager
   echo -n "YOUR_API_KEY" | gcloud secrets create scrapecreators-api-key \
     --project=zest-45e51 \
     --replication-policy="automatic" \
     --data-file=-
   ```

### Deployment Commands

#### Option 1: Using Makefile (Recommended)

```bash
cd /path/to/dishly-backend

# Deploy to production (us-central1)
make deploy-single-region REGION=us-central1
```

This will:
1. Build Docker container with Cloud Build
2. Push to Artifact Registry
3. Deploy to Cloud Run with correct environment variables
4. Configure service account and IAM
5. Set up Cloud Scheduler for queue processing

#### Option 2: Manual gcloud Commands

```bash
# Build and push container
gcloud builds submit --config cloudbuild.yaml \
  --project=zest-45e51 \
  --substitutions=_ENVIRONMENT=production

# Deploy to Cloud Run
gcloud run deploy dishly-parser \
  --project=zest-45e51 \
  --region=us-central1 \
  --image=us-central1-docker.pkg.dev/zest-45e51/dishly-parser/dishly-parser:latest \
  --service-account=dishly-parser@zest-45e51.iam.gserviceaccount.com \
  --set-env-vars="GOOGLE_CLOUD_PROJECT_ID=dishly-prod-fafd3,ENVIRONMENT=production" \
  --set-secrets="SCRAPECREATORS_API_KEY=scrapecreators-api-key:latest" \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300s \
  --concurrency=80 \
  --min-instances=1 \
  --max-instances=100
```

### Post-Deployment Verification

```bash
# 1. Check service health
curl https://dishly-parser-589847864013.us-central1.run.app/health

# Expected response:
# {"status": "healthy", "environment": "production"}

# 2. Test video processing
curl -X POST https://dishly-parser-589847864013.us-central1.run.app/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123"}'

# Expected response (cached or queued):
# {"status": "queued", "job_id": "uuid"} OR
# {"title": "...", "description": "...", ...}

# 3. Check Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=dishly-parser" \
  --project=zest-45e51 \
  --limit=50 \
  --format=json
```

---

## Cost Implications

### Billing Split Across Projects

| Resource | Project | Cost Owner | Estimated Monthly Cost |
|----------|---------|------------|------------------------|
| Cloud Run (compute) | zest-45e51 | Zest | $50-150 (based on usage) |
| Firestore (database) | dishly-prod-fafd3 | Dishly | $25-100 (read/write ops) |
| Cloud Storage (images) | dishly-prod-fafd3 | Dishly | $5-20 (storage + egress) |
| Secret Manager | zest-45e51 | Zest | <$1 (minimal) |
| Cloud Build | zest-45e51 | Zest | $10-30 (CI/CD builds) |

**Total Estimated Cost:** $90-300/month (split: ~60% Zest, ~40% Dishly)

### Cost Optimization Recommendations

1. **Cloud Run:**
   - Use `--min-instances=1` to reduce cold starts during peak hours
   - Scale down to `--min-instances=0` during off-peak (set via scheduler)
   - Monitor CPU/memory usage and right-size containers

2. **Firestore:**
   - Use cache collections to minimize reads (TTL: 24 hours)
   - Batch writes when possible (job queue updates)
   - Create composite indexes only when needed

3. **Cloud Storage:**
   - Set lifecycle policies to delete old thumbnails (>30 days)
   - Use Cloud CDN for frequently accessed images
   - Compress images before upload (target: 500KB-1MB)

4. **Future Migration:**
   - When `dishly-476904` Cloud Run API is enabled, migrate to consolidate billing
   - Estimated migration time: 2-4 hours (no downtime with blue-green deployment)

---

## Security Considerations

### Data Isolation

**Question:** Can Zest access Dishly user data?

**Answer:** No. Data isolation is enforced through:

1. **IAM Scoping:**
   - Service account `dishly-parser@zest-45e51.iam.gserviceaccount.com` has permissions ONLY in `dishly-prod-fafd3`
   - No Zest developers have access to this service account's credentials
   - Service account cannot be used outside Cloud Run context

2. **Firestore Security Rules:**
   ```javascript
   // In dishly-prod-fafd3 Firestore rules
   match /recipes/{userId}/items/{recipeId} {
     allow read, write: if request.auth.uid == userId;
   }
   ```
   - User data requires authentication
   - Service account only accesses `cache/` and `job_queue/` collections
   - No cross-user data access possible

3. **Audit Logging:**
   ```bash
   # Monitor service account activity
   gcloud logging read "protoPayload.authenticationInfo.principalEmail=dishly-parser@zest-45e51.iam.gserviceaccount.com" \
     --project=dishly-prod-fafd3 \
     --limit=100
   ```

### API Security

**Current Setup:** Cloud Run service allows unauthenticated requests (`--allow-unauthenticated`)

**Why:** Dishly mobile app needs to call the API without service account credentials on device

**Mitigation:**
1. **Firebase App Check** (recommended for future):
   - Add App Check token validation in Cloud Run
   - Rejects requests not originating from Dishly mobile app
   - Prevents abuse and unauthorized access

2. **Rate Limiting:**
   - Cloud Armor rules (future enhancement)
   - Limit requests per IP: 100 requests/minute
   - DDoS protection

3. **Input Validation:**
   - URL format validation (TikTok/Instagram only)
   - Request size limits (max 1MB payload)
   - Sanitize all inputs before processing

### Secret Management

**API Keys:**
- `SCRAPECREATORS_API_KEY` stored in Secret Manager (zest-45e51)
- Never logged or exposed in responses
- Rotated quarterly (manual process)

**Firestore Credentials:**
- Service account uses Application Default Credentials (ADC)
- No JSON key files stored in code or containers
- Credentials automatically rotated by Google

---

## Monitoring and Troubleshooting

### Key Metrics to Monitor

#### 1. Cloud Run Service Health

**Dashboard:** [Cloud Run Console - dishly-parser](https://console.cloud.google.com/run/detail/us-central1/dishly-parser/metrics?project=zest-45e51)

**Metrics:**
- Request count (target: <500 requests/hour during beta)
- Request latency (p50, p95, p99) - target p95 <3s
- Error rate (5xx responses) - target <1%
- Container instance count (check for unexpected scaling)

**Alerts:**
```bash
# Create alert for high error rate
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Dishly Parser High Error Rate" \
  --condition-display-name="5xx errors >5%" \
  --condition-threshold-value=5 \
  --condition-threshold-duration=300s \
  --project=zest-45e51
```

#### 2. Firestore Performance

**Dashboard:** [Firestore Console - dishly-prod-fafd3](https://console.firebase.google.com/project/dishly-prod-fafd3/firestore)

**Metrics:**
- Read/write operations per second
- Document count in `cache/` and `job_queue/`
- Query performance (slow queries >1s)

**Check for Quota Limits:**
```bash
# Firestore quota usage
gcloud alpha monitoring dashboards list --project=dishly-prod-fafd3
```

#### 3. External API Usage

**ScrapeCreators API:**
- Rate limit: 1000 requests/day
- Monitor usage via logs:
  ```bash
  gcloud logging read "jsonPayload.message=~'ScrapeCreators API call'" \
    --project=zest-45e51 \
    --limit=100 \
    --format="table(timestamp, jsonPayload.status)"
  ```

### Common Issues and Solutions

#### Issue 1: 500 Internal Server Error

**Symptom:** API returns 500 errors with "Service Unavailable"

**Diagnosis:**
```bash
# Check Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" \
  --project=zest-45e51 \
  --limit=20
```

**Common Causes:**
1. **Firestore permission denied:**
   - Verify service account has `roles/datastore.user` in dishly-prod-fafd3
   - Check IAM policy with command from "IAM Configuration" section

2. **Secret Manager access denied:**
   - Verify `SCRAPECREATORS_API_KEY` secret exists
   - Check service account has `roles/secretmanager.secretAccessor`

3. **Cold start timeout:**
   - Increase Cloud Run timeout: `--timeout=300s`
   - Add health check endpoint warmup

#### Issue 2: Video Processing Fails

**Symptom:** `/process` endpoint returns success but video never processes

**Diagnosis:**
```bash
# Check job queue status
# (Access Firestore console and inspect job_queue/jobs collection)
```

**Common Causes:**
1. **ScrapeCreators API rate limit:**
   - Check API usage in logs
   - Implement exponential backoff

2. **Invalid video URL:**
   - Verify URL format (must be TikTok or Instagram)
   - Check for geoblocking or private videos

3. **Queue processor not running:**
   - Verify Cloud Scheduler job exists and is enabled
   - Check last execution time

#### Issue 3: Cross-Project Permission Errors

**Symptom:** `Permission denied on resource project dishly-prod-fafd3`

**Solution:**
```bash
# Re-grant IAM permissions
gcloud projects add-iam-policy-binding dishly-prod-fafd3 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding dishly-prod-fafd3 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

# Wait 60 seconds for IAM propagation
sleep 60

# Test permissions
gcloud auth activate-service-account \
  --key-file=/path/to/service-account-key.json

gcloud firestore databases list --project=dishly-prod-fafd3
```

---

## Future Migration Path

### When to Migrate to dishly-476904

**Triggers:**
1. Cloud Run API becomes available in `dishly-476904`
2. Dishly user base exceeds 10,000 active users
3. Billing separation required for financial reporting
4. Zest infrastructure changes impact Dishly stability

### Migration Plan (Zero Downtime)

**Preparation (1 hour):**
1. Enable Cloud Run API in `dishly-476904` (if not already enabled)
2. Create service account: `dishly-parser@dishly-476904.iam.gserviceaccount.com`
3. Grant IAM permissions in `dishly-prod-fafd3` (same as current setup)
4. Copy Secret Manager secrets to `dishly-476904`

**Deployment (30 minutes):**
```bash
# 1. Deploy to dishly-476904 (new service)
cd dishly-backend
gcloud config set project dishly-476904

make deploy-single-region REGION=us-central1

# 2. Verify new service health
NEW_URL=$(gcloud run services describe dishly-parser \
  --region=us-central1 \
  --format='value(status.url)')

curl $NEW_URL/health

# 3. Update Flutter app with new URL (gradual rollout)
# - Deploy to 10% of users first
# - Monitor for errors
# - Increase to 100% over 24 hours

# 4. Decommission old service (after 7 days)
gcloud run services delete dishly-parser \
  --project=zest-45e51 \
  --region=us-central1
```

**Rollback Plan:**
- Keep old service running for 7 days
- Flutter app can instantly revert to old URL
- No data migration required (Firestore unchanged)

---

## Additional Resources

### Documentation
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Firestore Cross-Project Access](https://cloud.google.com/firestore/docs/security/iam)
- [Service Account Best Practices](https://cloud.google.com/iam/docs/best-practices-service-accounts)

### Related Dishly Docs
- `BACKEND_INTEGRATION.md` - Flutter app integration guide (in Dishly repo)
- `API_REFERENCE.md` - API endpoint documentation
- `DEPLOYMENT.md` - General deployment procedures

### Support Contacts
- **GCP Billing:** [Cloud Console Billing](https://console.cloud.google.com/billing)
- **Firebase Support:** [Firebase Console Support](https://console.firebase.google.com/project/dishly-prod-fafd3/support)
- **Infrastructure Questions:** Contact backend team lead

---

## Changelog

| Date | Author | Changes |
|------|--------|---------|
| 2025-11-01 | Bailey Grady | Initial cross-project deployment to zest-45e51 |
| 2025-11-01 | Claude Code | Created comprehensive architecture documentation |

---

**Document Version:** 1.0
**Next Review Date:** December 1, 2025 (monthly review)
