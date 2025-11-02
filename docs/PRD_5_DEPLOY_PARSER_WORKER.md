# PRD-5: Deploy Dishly Parser Worker Service

**Team:** Backend Team
**Priority:** P0 - Critical (Blocking Recipe Imports)
**Estimated Effort:** 30 minutes (changes + deployment)
**Dependencies:** None - dishly-backend already configured
**Blocks:** All TikTok/Instagram recipe imports in Dishly app

---

## Executive Summary

The `dishly-parser-worker` Cloud Run service is either not deployed or was deployed with the incorrect name (`zest-parser-worker`). This causes all recipe import jobs to remain stuck in "pending" status indefinitely because no worker is processing the Firestore queue.

**Fix:** Update 3 configuration files to hardcode "dishly-parser-worker" (8 line changes total), then deploy using existing `make deploy` command.

**Risk:** ZERO risk to Zest infrastructure - dishly-backend is a completely separate repository.

---

## Problem Statement

### Issue: Recipe Imports Stuck in "Pending" Forever

**User Impact:**
- Users paste TikTok or Instagram URL into Dishly app
- App shows "Processing video..." loading indicator
- After 2 minutes, request times out with error
- No recipe is created

**Root Cause:**
Jobs are successfully queued in Firestore `processing_queue` collection but never processed because:
1. The worker service doesn't exist in Cloud Run, OR
2. The worker was deployed with name `zest-parser-worker` (Zest's naming) instead of `dishly-parser-worker`

**Evidence:**
```bash
# Check Cloud Run services
gcloud run services list --project=zest-45e51 --filter="metadata.name~dishly"

# Expected output:
SERVICE                REGION
dishly-parser          us-central1   # ✅ EXISTS (API service)
dishly-parser-worker   us-central1   # ❌ MISSING (Worker service)
```

**Firestore Queue State:**
```
processing_queue/{job_id}
{
  "status": "pending",
  "attempts": 0,
  "url": "https://tiktok.com/...",
  "created_at": "2025-11-01T10:00:00Z",
  // Never picked up by worker
}
```

---

## Proposed Minimal Solution

### Architecture Context

**Dishly Backend Infrastructure:**
- **Cloud Run Project:** `zest-45e51` (shared with Zest for compute/hosting)
- **Firebase Project:** `dishly-prod-fafd3` (separate Firestore database)
- **Services:**
  - `dishly-parser` (API service) - ✅ Already deployed
  - `dishly-parser-worker` (Worker service) - ❌ MISSING

**Zest Infrastructure (UNTOUCHABLE):**
- **Services:** `zest-parser`, `zest-parser-worker`
- **Firebase:** Separate project (not `dishly-prod-fafd3`)
- **Service Accounts:** `zest-parser@zest-45e51.iam.gserviceaccount.com`

**Isolation Strategy:**
- Different service names prevent collisions
- Different Firebase projects prevent data leakage
- Same GCP project for billing consolidation

### Fix: Hardcode Dishly Service Names (8 Line Changes)

**File 1: `cloudbuild.yaml`** (Used if deploying via Cloud Build)

**Line 204:**
```yaml
# BEFORE:
WORKER_SA="zest-parser-worker@${PROJECT_ID}.iam.gserviceaccount.com"

# AFTER:
WORKER_SA="dishly-parser@${PROJECT_ID}.iam.gserviceaccount.com"
```

**Line 207:**
```yaml
# BEFORE:
gcloud iam service-accounts create zest-parser-worker \

# AFTER:
gcloud iam service-accounts create dishly-parser \
```

**Line 208:**
```yaml
# BEFORE:
--display-name="Zest Parser Worker Service Account"

# AFTER:
--display-name="Dishly Parser Service Account"
```

**Line 234:**
```yaml
# BEFORE:
gcloud run deploy zest-parser-worker \

# AFTER:
gcloud run deploy dishly-parser-worker \
```

---

**File 2: `scripts/deployment/deploy.sh`** (Used by `make deploy-sequential`)

**Line 108:**
```bash
# BEFORE:
--service-account "${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \

# AFTER:
--service-account "${SERVICE_ACCOUNT}" \
```

**Line 137:**
```bash
# BEFORE (API secondary regions):
--service-account "${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \

# AFTER:
--service-account "${SERVICE_ACCOUNT}" \
```

**Line 159:**
```bash
# BEFORE (Worker secondary regions):
--service-account "${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \

# AFTER:
--service-account "${SERVICE_ACCOUNT}" \
```

---

**File 3: `scripts/fix_genai_permissions.sh`** (Utility script for IAM)

**Line 20:**
```bash
# BEFORE:
WORKER_SA="zest-parser-worker@${PROJECT_ID}.iam.gserviceaccount.com"

# AFTER:
WORKER_SA="dishly-parser@${PROJECT_ID}.iam.gserviceaccount.com"
```

---

### Why Hardcode Instead of Dynamic Variables?

**User's Requirement:** "This is only for Dishly, not Zest, so it doesn't matter"

**Benefits:**
- Simpler to understand (no variable substitution confusion)
- Explicitly clear this is Dishly infrastructure
- Reduces risk of accidental Zest name usage
- Easier to audit and verify

**Trade-off:**
- If you fork for another project, you'll need to manually update hardcoded names
- **Verdict:** Acceptable - Dishly is a standalone product, not a multi-tenant template

---

## Service Account Handling

### Does the Service Account Exist?

**Check:**
```bash
gcloud iam service-accounts describe dishly-parser@zest-45e51.iam.gserviceaccount.com \
  --project=zest-45e51
```

**Possible Outcomes:**

1. **If it exists:**
   - Output shows service account details
   - ✅ Ready to deploy worker service

2. **If it doesn't exist:**
   - Error: "Service account not found"
   - ⚠️ Need to create it manually (one-time)

### Service Account Creation (If Needed)

**One-Time Manual Creation:**
```bash
# Create service account
gcloud iam service-accounts create dishly-parser \
  --display-name="Dishly Parser Service Account" \
  --description="Service account for dishly-parser API and worker services" \
  --project=zest-45e51

# Grant permissions in zest-45e51 (Cloud Run project)
gcloud projects add-iam-policy-binding zest-45e51 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding zest-45e51 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/ml.developer"

gcloud projects add-iam-policy-binding zest-45e51 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/aiplatform.serviceAgent"

gcloud projects add-iam-policy-binding zest-45e51 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant permissions in dishly-prod-fafd3 (Firestore project)
gcloud projects add-iam-policy-binding dishly-prod-fafd3 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding dishly-prod-fafd3 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

**Note:** The deployment script in `cloudbuild.yaml` lines 65-108 will auto-create the service account if it doesn't exist, BUT since `make deploy` uses `deploy-parallel.sh` (which doesn't use cloudbuild.yaml), you may need manual creation.

**Recommendation:** Run manual creation commands ONCE before first deployment to ensure service account exists.

---

## Deployment Procedure

### Pre-Deployment Checklist

- [ ] Authenticated to GCP: `gcloud auth login`
- [ ] Project set: `gcloud config set project zest-45e51`
- [ ] Service account exists (check command above)
- [ ] All 3 file changes applied (8 lines total)
- [ ] No accidental "zest-parser-worker" references remain

### Deployment Command

**Option 1: Multi-Region Deployment (Recommended)**
```bash
cd /Users/baileygrady/Desktop/dishly-backend
make deploy
```

**What this does:**
1. Builds Docker image (once)
2. Deploys `dishly-parser` (API) to us-central1
3. Deploys `dishly-parser-worker` (Worker) to us-central1
4. Deploys both to 10 secondary regions in parallel
5. Time: 10-15 minutes

**Option 2: Single Region Only (Faster for Testing)**
```bash
make deploy-single-region
```

**What this does:**
1. Builds Docker image
2. Deploys both services to us-central1 only
3. Time: 5-7 minutes

### Expected Output

**Successful Deployment:**
```
✅ Building Docker image...
✅ Image pushed to Artifact Registry
✅ Deploying dishly-parser to us-central1...
✅ Deploying dishly-parser-worker to us-central1...
✅ API service: https://dishly-parser-g4zcestszq-uc.a.run.app
✅ Worker service: https://dishly-parser-worker-g4zcestszq-uc.a.run.app
```

**Failure Indicators:**
- ❌ "Service account not found" → Run manual service account creation
- ❌ "Permission denied" → Run `make fix-genai-permissions`
- ❌ "Image not found" → Check Artifact Registry permissions
- ❌ "Failed to start and listen on port" → Check worker code (unlikely)

---

## Verification Steps

### Step 1: Verify Services Exist in Cloud Run

```bash
gcloud run services list --project=zest-45e51 --filter="metadata.name~dishly"
```

**Expected:**
```
SERVICE                REGION        URL
dishly-parser          us-central1   https://dishly-parser-...
dishly-parser-worker   us-central1   https://dishly-parser-worker-...
```

### Step 2: Test Worker Health Endpoint

```bash
# Get worker URL
WORKER_URL=$(gcloud run services describe dishly-parser-worker \
  --region=us-central1 \
  --project=zest-45e51 \
  --format='value(status.url)')

# Test health
curl $WORKER_URL/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "worker_id": "worker-c-...",
  "timestamp": "2025-11-01T20:00:00",
  "genai_services": 3
}
```

### Step 3: Check Worker Logs

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=dishly-parser-worker" \
  --project=zest-45e51 \
  --limit=20 \
  --format=json
```

**Look for:**
- ✅ "Worker service starting..."
- ✅ "GenAI pool initialized with 3 services"
- ✅ "Worker polling for pending jobs..."
- ❌ Any ERROR level logs

### Step 4: Verify Zest Services Untouched

```bash
gcloud run services list --project=zest-45e51 --filter="metadata.name~zest-parser"
```

**Expected (unchanged):**
```
SERVICE              REGION        URL
zest-parser          us-central1   https://zest-parser-...
zest-parser-worker   us-central1   https://zest-parser-worker-...
```

**Critical:** Both Zest services should remain exactly as before. No changes to URLs, revisions, or traffic.

### Step 5: Test Recipe Import in Dishly App

1. Open Dishly Flutter app
2. Navigate to "Add Recipe"
3. Paste TikTok or Instagram URL
4. Observe:
   - ✅ "Processing video..." appears
   - ✅ After 5-60 seconds, recipe appears with parsed data
   - ✅ Recipe has title, description, image
   - ❌ If timeout after 2 minutes → Check logs for errors

---

## Technical Specifications

### Worker Service Configuration

**Cloud Run Settings:**
- **Service Name:** `dishly-parser-worker`
- **Regions:** 11 (us-central1 + 10 secondary)
- **Image:** `us-central1-docker.pkg.dev/zest-45e51/dishly-parser/dishly-parser:production`
- **Entry Point:** `uvicorn src.worker.worker_service:app --host 0.0.0.0 --port 8080`
- **Port:** 8080
- **Resources:**
  - Memory: 1.5Gi
  - CPU: 1
  - Timeout: 300s (5 minutes)
  - Concurrency: 1 (processes one job at a time)
- **Scaling:**
  - Min instances: 0 (scales to zero when idle)
  - Max instances: 10
- **Environment:**
  - `GOOGLE_CLOUD_PROJECT_ID=dishly-prod-fafd3`
  - `ENVIRONMENT=production`
  - `CLOUD_RUN_REGION=us-central1`
- **Secrets:**
  - `SCRAPECREATORS_API_KEY` (from Secret Manager)

### Service Account Permissions

**In zest-45e51 Project:**
- `roles/aiplatform.user` - Access Vertex AI (Gemini)
- `roles/ml.developer` - ML model predictions
- `roles/aiplatform.serviceAgent` - Vertex AI service agent
- `roles/secretmanager.secretAccessor` - Read ScrapeCreators API key

**In dishly-prod-fafd3 Project:**
- `roles/datastore.user` - Firestore read/write
- `roles/storage.objectAdmin` - Upload/download images

### Worker Processing Flow

```
1. Worker starts → FastAPI app listens on port 8080
2. Background task polls Firestore queue every 1-30 seconds (exponential backoff)
3. Finds pending job → Atomically claims it (status: "processing")
4. Downloads video from TikTok/Instagram using ScrapeCreators API
5. Analyzes video with Gemini AI (extracts recipe)
6. Stores result in Firestore `processing_results` collection
7. Marks job as "completed"
8. API service reads result and returns to Flutter app
```

**Atomic Job Claiming (Prevents Race Conditions):**
```python
@firestore.transactional
def claim_job_transaction(transaction, job_ref):
    job = job_ref.get(transaction=transaction)
    if job.get("status") != "pending":
        return None  # Already claimed by another worker

    transaction.update(job_ref, {
        "status": "processing",
        "worker_id": worker_id,
        "started_at": datetime.now(timezone.utc)
    })
    return job
```

---

## Dependencies

### External Services

**Required (Already Set Up):**
- ✅ GCP Project `zest-45e51` (Cloud Run hosting)
- ✅ Firebase Project `dishly-prod-fafd3` (Firestore database)
- ✅ Artifact Registry (Docker image storage)
- ✅ Secret Manager (ScrapeCreators API key)
- ✅ Vertex AI (Gemini 1.5 Flash)
- ✅ ScrapeCreators API (video downloading)

**No New Dependencies Required**

### Internal Dependencies

**Blocks:**
- ❌ All recipe imports in Dishly app (P0 blocker)

**Blocked By:**
- None - can deploy immediately

**Related Components:**
- `dishly-parser` (API service) - Already working
- Dishly Flutter app - Waiting for working backend

---

## File Checklist

### Files to Modify

- [ ] `cloudbuild.yaml` - Lines 204, 207, 208, 234 (4 changes)
- [ ] `scripts/deployment/deploy.sh` - Lines 108, 137, 159 (3 changes)
- [ ] `scripts/fix_genai_permissions.sh` - Line 20 (1 change)

**Total: 8 line changes across 3 files**

### Files NOT to Touch

- ❌ Any files in `/Users/baileygrady/Desktop/Zest` (Zest codebase)
- ❌ Worker service code in `src/worker/` (already correct)
- ❌ Makefile (already uses correct service account variable)
- ❌ `deploy-parallel.sh` (already correct!)

---

## Risk Assessment

### Risk to Dishly Infrastructure

**Risk Level:** LOW

**Mitigation:**
- Only deploying missing service (not modifying existing API)
- Cloud Run keeps revision history (instant rollback if needed)
- Can delete worker service if issues arise

### Risk to Zest Infrastructure

**Risk Level:** ZERO

**Reasoning:**
1. dishly-backend is a completely separate Git repository
2. Different service names (`dishly-parser-worker` vs `zest-parser-worker`)
3. Different Firebase projects (`dishly-prod-fafd3` vs Zest's Firebase)
4. No shared code, no shared deployments
5. Zest has no dependency on dishly-backend repository

**Verification:**
- Check Zest services before deployment
- Check Zest services after deployment
- Confirm no changes to Zest service URLs or revisions

### Edge Cases

**Scenario 1: Service account doesn't exist**
- **Impact:** Deployment fails with "service account not found"
- **Mitigation:** Run manual service account creation (see section above)
- **Recovery Time:** 2 minutes

**Scenario 2: Worker fails to start**
- **Impact:** Worker shows "Unhealthy" status in Cloud Run
- **Mitigation:** Check logs for error, fix code, redeploy
- **Recovery Time:** 5-10 minutes

**Scenario 3: Worker can't connect to Firestore**
- **Impact:** "Permission denied" errors in logs
- **Mitigation:** Run `make fix-genai-permissions`
- **Recovery Time:** 3 minutes

**Scenario 4: Worker processes jobs but results don't appear**
- **Impact:** Jobs complete but Flutter app shows timeout
- **Mitigation:** Check `GOOGLE_CLOUD_PROJECT_ID` environment variable points to `dishly-prod-fafd3`
- **Recovery Time:** 5 minutes (update env var, redeploy)

---

## Acceptance Criteria

### Functional Requirements

- [ ] `dishly-parser-worker` service exists in Cloud Run (us-central1)
- [ ] Worker health endpoint returns `{"status": "healthy"}`
- [ ] Worker logs show "Worker polling for pending jobs..."
- [ ] Pasting TikTok URL in Dishly app creates recipe within 60 seconds
- [ ] Pasting Instagram URL in Dishly app creates recipe within 60 seconds
- [ ] Recipe has title, description, and image extracted from video
- [ ] No changes to Zest services (`zest-parser`, `zest-parser-worker`)

### Performance Requirements

- [ ] Worker picks up pending jobs within 1 minute
- [ ] Video processing completes in 5-60 seconds (depends on video length)
- [ ] Worker scales to zero when no jobs (cost optimization)
- [ ] Worker auto-scales up to 10 instances under load

### Security Requirements

- [ ] Service account `dishly-parser@zest-45e51.iam.gserviceaccount.com` has correct permissions
- [ ] Worker only accesses Dishly Firebase project (`dishly-prod-fafd3`)
- [ ] ScrapeCreators API key stored in Secret Manager (not environment variable)
- [ ] No credentials in cloudbuild.yaml or deployment scripts

### Quality Requirements

- [ ] No "zest-parser-worker" references remain in code
- [ ] All service names hardcoded to "dishly-parser" or "dishly-parser-worker"
- [ ] Deployment completes without errors
- [ ] Cloud Run console shows both services as "READY"

---

## Testing Strategy

### Pre-Deployment Testing

**Local Development (Optional):**
```bash
# Start worker locally
make dev
```

**Expected:**
```
Worker service starting on port 8081...
GenAI pool initialized with 3 services
Worker polling for pending jobs...
```

### Post-Deployment Testing

**Test 1: Worker Health Check**
```bash
curl https://dishly-parser-worker-g4zcestszq-uc.a.run.app/health
```

**Test 2: Worker Stats**
```bash
curl https://dishly-parser-worker-g4zcestszq-uc.a.run.app/worker/stats
```

**Test 3: Queue Health**
```bash
curl https://dishly-parser-worker-g4zcestszq-uc.a.run.app/worker/queue-health
```

**Test 4: End-to-End Recipe Import**
1. Open Dishly app
2. Add TikTok URL: `https://www.tiktok.com/@gordonramsayofficial/video/7123456789`
3. Observe loading indicator
4. Recipe appears with:
   - Title: Extracted from video
   - Description: Extracted from video
   - Image: Thumbnail from TikTok
   - Source: TikTok icon

**Test 5: Zest Verification (Negative Test)**
1. Open Zest app (if available)
2. Verify bucket list feature still works
3. No changes to Zest backend behavior

---

## Rollback Plan

**If deployment fails or causes issues:**

### Option 1: Delete Worker Service
```bash
gcloud run services delete dishly-parser-worker \
  --region=us-central1 \
  --project=zest-45e51 \
  --quiet
```

**Impact:** Returns to current state (no worker, imports broken)

### Option 2: Rollback to Previous Revision
```bash
# List revisions
gcloud run revisions list \
  --service=dishly-parser-worker \
  --region=us-central1 \
  --project=zest-45e51

# Rollback to previous revision
gcloud run services update-traffic dishly-parser-worker \
  --region=us-central1 \
  --project=zest-45e51 \
  --to-revisions=REVISION_NAME=100
```

**Impact:** Reverts worker to previous code (if exists)

### Option 3: Fix and Redeploy
```bash
# Fix issue in code
# ...

# Redeploy
make deploy-single-region
```

**Time:** 5-7 minutes

---

## Open Questions

### Q1: Should we deploy to all 11 regions or just primary region?

**Options:**
- **Option A:** Primary only (us-central1) - Faster deployment, lower cost, sufficient for MVP
- **Option B:** All 11 regions - Global redundancy, lower latency, higher cost

**Recommendation:** Start with primary only (`make deploy-single-region`), expand to multi-region if needed for performance.

**Decision:** User decides

---

### Q2: What should happen to existing stuck jobs?

**Current State:** Jobs in Firestore queue with `status: "pending"`, `attempts: 0`, created days ago

**Options:**
- **Option A:** Worker automatically picks them up (default behavior)
- **Option B:** Manually mark them as failed (clean slate)
- **Option C:** Delete them and ask users to retry

**Recommendation:** Option A - Worker will process them automatically. If they fail (e.g., video deleted), they'll move to dead letter queue.

**Decision:** User decides

---

### Q3: Should we set up Cloud Scheduler for periodic queue checks?

**Current:** Worker polls queue in background loop (exponential backoff: 1-30 seconds)

**Option:** Add Cloud Scheduler to trigger `/worker/process-queue` endpoint every minute

**Benefits:**
- Ensures worker is always checking queue
- Faster response for cold starts
- Better monitoring

**Trade-offs:**
- Small additional cost (~$0.10/month)
- Adds complexity

**Recommendation:** Not required for MVP - worker's background loop is sufficient. Add later if needed.

**Decision:** Skip for now

---

## Timeline

| Task | Effort | Dependencies |
|------|--------|--------------|
| Verify service account exists | 2 min | GCP access |
| Create service account (if needed) | 5 min | Previous step |
| Apply 8 line changes | 3 min | None |
| Deploy worker (single region) | 7 min | Changes applied |
| Verify deployment | 5 min | Deployment complete |
| Test end-to-end | 5 min | All above |
| **Total** | **27 minutes** | |

**Buffer:** Add 10 minutes for unexpected issues
**Total with buffer:** ~40 minutes

---

## Success Metrics

### Immediate Success (Day 1)

- ✅ Worker service deployed and healthy
- ✅ At least 1 recipe imported successfully via TikTok
- ✅ At least 1 recipe imported successfully via Instagram
- ✅ Zero errors in worker logs
- ✅ Zest services completely untouched

### Ongoing Success (Week 1)

- Recipe import success rate > 80%
- Average processing time < 30 seconds
- Worker scales to zero when no jobs (cost optimization)
- Zero crashes or errors requiring intervention

---

## Contact

**Questions or blockers?**
- GCP/Cloud Run issues: Check [Cloud Run docs](https://cloud.google.com/run/docs)
- Firestore issues: Check Firebase Console
- Worker code issues: Review `src/worker/worker_service.py`
- Deployment script issues: Review `scripts/deployment/deploy-parallel.sh`

---

## Handoff to Developer

See **"Developer Handoff Instructions"** section at end of document.

---

## Completion Checklist

**Before marking as done:**

- [ ] All 8 line changes applied and committed
- [ ] Service account exists in GCP
- [ ] Worker deployed to at least us-central1
- [ ] Worker health endpoint returns healthy
- [ ] Recipe imported successfully from TikTok
- [ ] Recipe imported successfully from Instagram
- [ ] Zest services verified unchanged
- [ ] Documentation updated with worker URL
- [ ] PRD moved to `docs/done/` folder

---

# Developer Handoff Instructions

## Overview

You're deploying the missing `dishly-parser-worker` Cloud Run service. This is a **30-minute task** with **ZERO risk to Zest** because dishly-backend is a completely separate codebase.

---

## What You're Fixing

**Problem:** Recipe imports in Dishly app timeout because no worker is processing the job queue.

**Solution:** Deploy the worker service that's been configured but never deployed.

**Changes:** 8 lines across 3 files (just updating "zest-parser-worker" → "dishly-parser-worker")

---

## Prerequisites

1. **GCP Access:**
   ```bash
   gcloud auth login
   gcloud config set project zest-45e51
   ```

2. **Repository:**
   ```bash
   cd /Users/baileygrady/Desktop/dishly-backend
   git status  # Ensure clean working directory
   ```

3. **Verify Zest is Untouched:**
   ```bash
   gcloud run services list --project=zest-45e51 --filter="metadata.name~zest-parser"
   # Should show: zest-parser, zest-parser-worker (both unchanged)
   ```

---

## Step 1: Check Service Account (5 min)

```bash
# Check if service account exists
gcloud iam service-accounts describe dishly-parser@zest-45e51.iam.gserviceaccount.com \
  --project=zest-45e51
```

**If it exists:**
- ✅ Proceed to Step 2

**If it doesn't exist:**
- Run these commands (one-time setup):

```bash
# Create service account
gcloud iam service-accounts create dishly-parser \
  --display-name="Dishly Parser Service Account" \
  --description="Service account for dishly-parser API and worker services" \
  --project=zest-45e51

# Grant permissions in zest-45e51
gcloud projects add-iam-policy-binding zest-45e51 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding zest-45e51 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/ml.developer"

gcloud projects add-iam-policy-binding zest-45e51 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/aiplatform.serviceAgent"

gcloud projects add-iam-policy-binding zest-45e51 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant permissions in dishly-prod-fafd3
gcloud projects add-iam-policy-binding dishly-prod-fafd3 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding dishly-prod-fafd3 \
  --member="serviceAccount:dishly-parser@zest-45e51.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

---

## Step 2: Apply Code Changes (5 min)

### File 1: `cloudbuild.yaml`

**Line 204:**
```yaml
WORKER_SA="dishly-parser@${PROJECT_ID}.iam.gserviceaccount.com"
```

**Line 207:**
```yaml
gcloud iam service-accounts create dishly-parser \
```

**Line 208:**
```yaml
--display-name="Dishly Parser Service Account"
```

**Line 234:**
```yaml
gcloud run deploy dishly-parser-worker \
```

### File 2: `scripts/deployment/deploy.sh`

**Line 108, 137, 159:** (All 3 instances)
```bash
--service-account "${SERVICE_ACCOUNT}" \
```

### File 3: `scripts/fix_genai_permissions.sh`

**Line 20:**
```bash
WORKER_SA="dishly-parser@${PROJECT_ID}.iam.gserviceaccount.com"
```

---

## Step 3: Deploy Worker (10 min)

**Option A: Single Region (Faster - Recommended for First Deploy)**
```bash
make deploy-single-region
```

**Option B: All 11 Regions (Production-Ready)**
```bash
make deploy
```

**Watch for:**
- ✅ "Building Docker image..."
- ✅ "Deploying dishly-parser to us-central1..."
- ✅ "Deploying dishly-parser-worker to us-central1..."
- ✅ Service URLs printed at end

**If errors occur:**
- "Service account not found" → Go back to Step 1
- "Permission denied" → Run `make fix-genai-permissions`
- Other errors → Check logs: `gcloud logging tail`

---

## Step 4: Verify Deployment (5 min)

**Check services exist:**
```bash
gcloud run services list --project=zest-45e51 --filter="metadata.name~dishly"
```

**Expected output:**
```
SERVICE                REGION        URL
dishly-parser          us-central1   https://dishly-parser-g4zcestszq-uc.a.run.app
dishly-parser-worker   us-central1   https://dishly-parser-worker-g4zcestszq-uc.a.run.app
```

**Test worker health:**
```bash
WORKER_URL=$(gcloud run services describe dishly-parser-worker \
  --region=us-central1 \
  --project=zest-45e51 \
  --format='value(status.url)')

curl $WORKER_URL/health
```

**Expected response:**
```json
{"status": "healthy", "worker_id": "worker-c-...", "timestamp": "..."}
```

**Check worker logs:**
```bash
gcloud logging read \
  "resource.labels.service_name=dishly-parser-worker AND severity>=INFO" \
  --limit=10 \
  --project=zest-45e51
```

**Look for:**
- ✅ "Worker service starting..."
- ✅ "GenAI pool initialized with 3 services"
- ✅ "Worker polling for pending jobs..."

---

## Step 5: Test End-to-End (5 min)

**Option A: Using Dishly App (Best)**
1. Open Dishly Flutter app
2. Navigate to "Add Recipe"
3. Paste TikTok URL: `https://www.tiktok.com/@gordonramsayofficial/video/...`
4. Wait 10-60 seconds
5. Recipe should appear with title, description, image

**Option B: Using API Directly**
```bash
curl -X POST https://dishly-parser-g4zcestszq-uc.a.run.app/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@gordonramsayofficial/video/7297193769521581313"}'
```

**Expected:** Returns `request_id` immediately, then check Firestore for result after 30 seconds.

---

## Step 6: Verify Zest Untouched (2 min)

**Critical verification:**
```bash
gcloud run services list --project=zest-45e51 --filter="metadata.name~zest-parser"
```

**Expected (NO CHANGES):**
```
SERVICE              REGION        URL
zest-parser          us-central1   https://zest-parser-...  (same as before)
zest-parser-worker   us-central1   https://zest-parser-worker-...  (same as before)
```

**If anything changed:**
- ❌ **STOP** - Something went wrong
- Check which files were modified
- Review git diff to ensure only dishly-backend was changed

---

## Step 7: Commit Changes (3 min)

```bash
git status
# Should show 3 modified files only

git diff
# Verify all changes are "zest-parser-worker" → "dishly-parser-worker"

git add cloudbuild.yaml scripts/deployment/deploy.sh scripts/fix_genai_permissions.sh

git commit -m "fix: Deploy dishly-parser-worker with correct service name

- Changed hardcoded 'zest-parser-worker' to 'dishly-parser-worker'
- Updated cloudbuild.yaml to use dishly service account
- Fixed deploy.sh to use SERVICE_ACCOUNT variable
- Fixed fix_genai_permissions.sh service account reference

This deploys the missing worker service that processes recipe import jobs
from the Firestore queue. Zero impact on Zest infrastructure.

Fixes: Recipe imports stuck in 'pending' status indefinitely"

git push origin main
```

---

## Troubleshooting

### Issue: "Service account not found"
**Solution:** Run Step 1 (service account creation)

### Issue: "Permission denied" accessing Vertex AI
**Solution:**
```bash
make fix-genai-permissions
```

### Issue: Worker unhealthy in Cloud Run
**Solution:**
```bash
gcloud logging read "resource.labels.service_name=dishly-parser-worker AND severity>=ERROR" --limit=20
```
Check logs for specific error

### Issue: Recipe imports still timing out
**Solution:**
1. Check worker is running: `curl $WORKER_URL/health`
2. Check Firestore queue has jobs: Firebase Console → `processing_queue`
3. Check worker logs for processing errors
4. Verify `GOOGLE_CLOUD_PROJECT_ID=dishly-prod-fafd3` in Cloud Run env vars

---

## Rollback

**If something goes wrong:**
```bash
# Delete worker service
gcloud run services delete dishly-parser-worker \
  --region=us-central1 \
  --project=zest-45e51 \
  --quiet

# Revert code changes
git reset --hard HEAD~1
git push origin main --force
```

---

## Success Criteria

**You're done when:**
- ✅ `dishly-parser-worker` appears in Cloud Run console
- ✅ Health endpoint returns `{"status": "healthy"}`
- ✅ Recipe import works in Dishly app (TikTok or Instagram URL)
- ✅ Zest services are completely unchanged
- ✅ Changes committed to git with proper commit message

---

## Questions?

**Stuck or unsure?**
1. Check worker logs: `gcloud logging read ...`
2. Review this PRD (all answers are here)
3. Check Cloud Run console for service status
4. Verify service account permissions

**Total Time:** 30-40 minutes (including buffer)

**Risk:** ZERO to Zest (separate codebase)

---

**Good luck! This is a straightforward deployment - you've got this!**

---

**End of PRD-5**
