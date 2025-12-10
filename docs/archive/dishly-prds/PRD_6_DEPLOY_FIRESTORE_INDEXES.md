# PRD-6: Deploy Firestore Composite Indexes for Queue Processing

**Team:** Backend Team
**Priority:** P0 - Critical (Blocking Recipe Imports)
**Estimated Effort:** 15 minutes (deploy + verification)
**Dependencies:** Firebase CLI must be installed and authenticated
**Blocks:** All TikTok/Instagram recipe imports in Dishly app

---

## Executive Summary

The `dishly-parser-worker` Cloud Run service is deployed and healthy, but cannot process jobs from the Firestore queue because **composite indexes are missing** in the `dishly-prod-fafd3` Firebase project.

**Fix:** Deploy existing index definitions using `make setup-firestore` command. Index definitions already exist in `scripts/firestore_indexes.json` - they just need to be deployed to Firebase.

**Code Changes Required:** ZERO - indexes are already defined
**Risk:** ZERO risk to Zest - Dishly uses separate Firebase project

---

## Problem Statement

### Issue: Recipe Imports Stuck in "Pending" Forever

**User Impact:**
- Users paste TikTok or Instagram URL into Dishly app
- App shows "Processing video..." loading indicator
- After 2 minutes (60 polling attempts), request times out with error
- No recipe is created
- Jobs remain stuck in Firestore with `status: "pending"`, `attempts: 0`

**Root Cause:**
Jobs are successfully queued in Firestore `processing_queue` collection, but the worker cannot query them because Firestore requires a composite index for the query.

**Evidence from Worker Logs:**
```
Error getting next job: 400 The query requires an index.
You can create it here: https://console.firebase.google.com/v1/r/project/dishly-prod-fafd3/firestore/indexes?create_composite=...
```

**Worker Query (from `src/services/queue_service.py:189-192`):**
```python
query = (
    self.queue_collection.where(filter=FieldFilter("status", "==", "pending"))
    .order_by("priority_value")  # High priority first
    .order_by("created_at")      # Then oldest first
    .limit(10)
)
```

This query requires a composite index on:
1. `status` (ascending)
2. `priority_value` (ascending)
3. `created_at` (ascending)

**Firestore Queue State:**
```
processing_queue/{job_id}
{
  "job_id": "unknown_1762045151381",
  "status": "pending",
  "attempts": 0,
  "url": "https://www.tiktok.com/@aussiefitness/video/7564750012312309013",
  "created_at": "2025-11-02T00:59:11.381957+00:00",
  "priority": "normal",
  "priority_value": 2,
  // Worker cannot query this due to missing index
}
```

---

## Architecture Context

### Why Composite Indexes Are Required

**Firestore Query Limitations:**
- Single `where` clause: No index needed (uses built-in indexes)
- Multiple `where` clauses OR `where` + `order_by`: Composite index required
- Firestore does NOT auto-create composite indexes (security measure)

**Our Query:**
- 1 `where` clause: `status == "pending"`
- 2 `order_by` clauses: `priority_value`, `created_at`
- **Result:** Requires composite index on all 3 fields

### Dishly vs Zest Infrastructure

**Dishly Backend:**
- **Cloud Run Project:** `zest-45e51` (shared hosting)
- **Firebase Project:** `dishly-prod-fafd3` (separate Firestore) ← INDEX DEPLOYMENT TARGET
- **Services:** `dishly-parser`, `dishly-parser-worker` ✅ Deployed

**Zest Backend:**
- **Cloud Run Project:** `zest-45e51` (same hosting)
- **Firebase Project:** Different from Dishly (separate Firestore)
- **Services:** `zest-parser`, `zest-parser-worker` ← DO NOT TOUCH

**Isolation:**
- Different Firebase projects = Different Firestore databases
- Deploying indexes to `dishly-prod-fafd3` has ZERO impact on Zest
- Zest's indexes are in their separate Firebase project

---

## Proposed Minimal Solution

### Step 1: Verify Firebase CLI is Installed and Authenticated

**Check if Firebase CLI exists:**
```bash
which firebase
# Expected: /usr/local/bin/firebase or similar
# If not found: npm install -g firebase-tools
```

**Check authentication:**
```bash
firebase projects:list
# Should show: dishly-prod-fafd3 in the list
```

**If not authenticated:**
```bash
firebase login
# Follow browser authentication flow
```

---

### Step 2: Deploy Firestore Indexes (ONE COMMAND)

**Command:**
```bash
cd /Users/baileygrady/Desktop/dishly-backend
make setup-firestore
```

**What this does:**
1. Runs `scripts/deploy_indexes.sh`
2. Deploys indexes from `scripts/firestore_indexes.json` to `dishly-prod-fafd3`
3. Firebase begins building indexes (takes 5-10 minutes for production data)

**Expected Output:**
```
Deploying Firestore indexes to dishly-prod-fafd3...

✅ Indexes deployed successfully!

Index build status:
- processing_queue (status, priority_value, created_at): BUILDING (5-10 min)

Check build progress:
https://console.firebase.google.com/project/dishly-prod-fafd3/firestore/indexes
```

---

### Step 3: Wait for Index Build Completion

**Time Required:** 5-10 minutes (Firestore builds indexes asynchronously)

**Monitor Progress:**

**Option A: Firebase Console (Visual)**
1. Open: https://console.firebase.google.com/project/dishly-prod-fafd3/firestore/indexes
2. Look for index on `processing_queue` collection
3. Wait for status: `BUILDING` → `ENABLED` (green checkmark)

**Option B: Firebase CLI (Terminal)**
```bash
firebase firestore:indexes --project=dishly-prod-fafd3
```

**Expected Output (While Building):**
```
[ processing_queue ]
┌───────────┬──────────────────┬──────────┬────────────┐
│  Field    │  Order           │  Mode    │  Status    │
├───────────┼──────────────────┼──────────┼────────────┤
│  status   │  ASCENDING       │  -       │  BUILDING  │
│  priority │  ASCENDING       │  -       │  BUILDING  │
│  created  │  ASCENDING       │  -       │  BUILDING  │
└───────────┴──────────────────┴──────────┴────────────┘
```

**Expected Output (When Complete):**
```
[ processing_queue ]
┌───────────┬──────────────────┬──────────┬────────────┐
│  Field    │  Order           │  Mode    │  Status    │
├───────────┼──────────────────┼──────────┼────────────┤
│  status   │  ASCENDING       │  -       │  ENABLED   │
│  priority │  ASCENDING       │  -       │  ENABLED   │
│  created  │  ASCENDING       │  -       │  ENABLED   │
└───────────┴──────────────────┴──────────┴────────────┘
```

---

### Step 4: Verify Worker Can Query Queue

**Test Worker Immediately After Index Deployment:**

**Option A: Check Worker Logs**
```bash
gcloud logging read \
  "resource.labels.service_name=dishly-parser-worker AND severity>=INFO" \
  --limit=20 \
  --project=zest-45e51
```

**Look for:**
- ✅ **Before index:** `Error getting next job: 400 The query requires an index`
- ✅ **After index:** `Processing job {job_id} from queue`
- ✅ **After index:** `Job {job_id} completed successfully`

**Option B: Check Queue Health Endpoint**
```bash
curl https://dishly-parser-worker-g4zcestszq-uc.a.run.app/worker/queue-health
```

**Expected Response (After Index):**
```json
{
  "status": "healthy",
  "pending_jobs": 5,
  "processing_jobs": 1,
  "failed_jobs": 0,
  "can_query_queue": true,  // ← Should be true now
  "timestamp": "2025-11-02T01:30:00Z"
}
```

---

## Index Definitions (Already Exist in Codebase)

**File:** `scripts/firestore_indexes.json`

**Index 1: Queue Processing (Required)**
```json
{
  "collectionGroup": "processing_queue",
  "queryScope": "COLLECTION",
  "fields": [
    {
      "fieldPath": "status",
      "order": "ASCENDING"
    },
    {
      "fieldPath": "priority_value",
      "order": "ASCENDING"
    },
    {
      "fieldPath": "created_at",
      "order": "ASCENDING"
    }
  ]
}
```

**Purpose:** Enables worker to query pending jobs sorted by priority and age

---

**Index 2: Job History Queries (Optional, but included)**
```json
{
  "collectionGroup": "processing_results",
  "queryScope": "COLLECTION",
  "fields": [
    {
      "fieldPath": "status",
      "order": "ASCENDING"
    },
    {
      "fieldPath": "completed_at",
      "order": "DESCENDING"
    }
  ]
}
```

**Purpose:** Enables querying completed jobs by status and completion time (for debugging/analytics)

---

## Why the Index Wasn't Deployed

### Root Cause: Missing Deployment Step

**What happened:**
1. ✅ Indexes were defined in `firestore_indexes.json` (correct)
2. ✅ Worker code was written to use these queries (correct)
3. ✅ Deployment scripts exist (`make setup-firestore`) (correct)
4. ❌ Indexes were never deployed to `dishly-prod-fafd3` Firebase project (MISSING STEP)

**Why it was missed:**
- Firestore indexes are separate from Cloud Run deployments
- `make deploy` (Cloud Run) does NOT automatically deploy Firestore indexes
- Firestore index deployment requires separate `firebase deploy` command
- This is the first time Dishly backend has been used, so initial setup was incomplete

**Comparison with Zest:**
- Zest likely deployed indexes months ago during initial setup
- Zest's indexes exist in their Firebase project
- Dishly is a new Firebase project starting from scratch

---

## Deployment Script Details

### `scripts/deploy_indexes.sh` (Existing Script)

```bash
#!/bin/bash
set -e

PROJECT_ID="dishly-prod-fafd3"

echo "Deploying Firestore indexes to ${PROJECT_ID}..."

# Deploy indexes
firebase deploy --only firestore:indexes --project="${PROJECT_ID}"

echo "✅ Indexes deployed successfully!"
echo ""
echo "Index build status:"
firebase firestore:indexes --project="${PROJECT_ID}"

echo ""
echo "Check build progress:"
echo "https://console.firebase.google.com/project/${PROJECT_ID}/firestore/indexes"
```

**What it does:**
1. Reads `firestore.indexes.json` in project root
2. Deploys index definitions to Firebase project
3. Firebase starts building indexes asynchronously
4. Returns immediately (doesn't wait for build completion)

**Note:** The script looks for `firestore.indexes.json` in the repository root. If it doesn't exist, we need to create a symlink or copy from `scripts/firestore_indexes.json`.

---

### `Makefile` Target (Existing)

```makefile
setup-firestore: ## Setup Firestore database and indexes
	@chmod +x scripts/deploy_indexes.sh
	@./scripts/deploy_indexes.sh
```

**Usage:**
```bash
make setup-firestore
```

**Dependencies:**
- Firebase CLI installed (`npm install -g firebase-tools`)
- Authenticated to Firebase (`firebase login`)
- `scripts/deploy_indexes.sh` exists and is executable

---

## Pre-Deployment Checklist

### Prerequisites

- [ ] **Firebase CLI Installed:**
  ```bash
  which firebase
  # If not found: npm install -g firebase-tools
  ```

- [ ] **Firebase CLI Authenticated:**
  ```bash
  firebase login
  firebase projects:list | grep dishly-prod-fafd3
  ```

- [ ] **Correct Working Directory:**
  ```bash
  cd /Users/baileygrady/Desktop/dishly-backend
  pwd  # Should show dishly-backend
  ```

- [ ] **Index Definition File Exists:**
  ```bash
  ls scripts/firestore_indexes.json
  # Should show: scripts/firestore_indexes.json
  ```

- [ ] **Deployment Script Exists:**
  ```bash
  ls scripts/deploy_indexes.sh
  # Should show: scripts/deploy_indexes.sh
  ```

---

## Deployment Procedure

### Step-by-Step Instructions

**1. Navigate to Repository:**
```bash
cd /Users/baileygrady/Desktop/dishly-backend
```

**2. Verify Firebase CLI:**
```bash
firebase --version
# Expected: 12.x.x or higher
```

**3. Check Index Configuration File Location:**

The deployment script expects `firestore.indexes.json` in the repository root. Check if it exists:
```bash
ls firestore.indexes.json
```

**If it doesn't exist:**
```bash
# Create symlink to the correct file
ln -s scripts/firestore_indexes.json firestore.indexes.json
```

OR

```bash
# Copy file to root
cp scripts/firestore_indexes.json firestore.indexes.json
```

**4. Deploy Indexes:**
```bash
make setup-firestore
```

**5. Wait for Index Build (5-10 minutes):**

Monitor progress:
```bash
# Check every 2 minutes
firebase firestore:indexes --project=dishly-prod-fafd3
```

**6. Verify Index is Enabled:**

Look for `ENABLED` status in output:
```
processing_queue
  status, priority_value, created_at: ENABLED ✅
```

---

## Verification Steps

### Step 1: Verify Indexes Exist in Firebase Console

**URL:** https://console.firebase.google.com/project/dishly-prod-fafd3/firestore/indexes

**Expected:**
- `processing_queue` index with 3 fields: status, priority_value, created_at
- Status: `ENABLED` (green checkmark)

---

### Step 2: Check Worker Can Query Queue

**Test worker logs:**
```bash
gcloud logging read \
  "resource.labels.service_name=dishly-parser-worker" \
  --limit=10 \
  --project=zest-45e51 \
  --format=json
```

**Look for:**
- ✅ No "index required" errors
- ✅ "Processing job {job_id}" messages
- ✅ "Job {job_id} completed successfully" messages

---

### Step 3: Test Recipe Import End-to-End

**Using Dishly Flutter App:**

1. Open Dishly app
2. Navigate to "Add Recipe"
3. Paste TikTok URL: `https://www.tiktok.com/@aussiefitness/video/7564750012312309013`
4. Observe:
   - ✅ "Processing video..." appears
   - ✅ After 10-60 seconds, recipe appears
   - ✅ Recipe has title, description, image
   - ❌ If timeout → Check logs for new errors

**Using API Directly:**
```bash
curl -X POST https://dishly-parser-g4zcestszq-uc.a.run.app/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@aussiefitness/video/7564750012312309013"}'
```

**Expected Response:**
```json
{
  "status": "queued",
  "job_id": "unique_job_id",
  "message": "Video queued for processing"
}
```

**Check job status after 30 seconds:**
```bash
curl https://dishly-parser-g4zcestszq-uc.a.run.app/status/{job_id}
```

**Expected Response:**
```json
{
  "status": "completed",
  "result": {
    "title": "Easy Healthy Meal Prep",
    "description": "...",
    "image": "https://..."
  }
}
```

---

### Step 4: Verify Stuck Jobs Are Processed

**Check Firestore Console:**

URL: https://console.firebase.google.com/project/dishly-prod-fafd3/firestore/data/processing_queue

**Before Index:**
```
Job: unknown_1762045151381
status: "pending"
attempts: 0
created_at: 2025-11-02T00:59:11Z
// Stuck for hours
```

**After Index (within 1 minute):**
```
Job: unknown_1762045151381
status: "completed"  OR  status: "failed"
attempts: 1
started_at: 2025-11-02T01:35:00Z
completed_at: 2025-11-02T01:35:45Z
// Processed successfully
```

**Note:** Some old jobs may fail if:
- TikTok video was deleted
- Instagram video is private
- URL is invalid
- This is expected behavior - worker will mark them as "failed"

---

## Dependencies

### External Services

**Required (Already Set Up):**
- ✅ Firebase project `dishly-prod-fafd3` exists
- ✅ Firestore database created in `dishly-prod-fafd3`
- ✅ Service account `dishly-parser@zest-45e51.iam.gserviceaccount.com` has `datastore.user` role

**Required for Deployment:**
- 🔍 Firebase CLI installed locally (`npm install -g firebase-tools`)
- 🔍 Firebase CLI authenticated (`firebase login`)

**No New Dependencies Required**

---

### Internal Dependencies

**Blocks:**
- ❌ All recipe imports in Dishly app (P0 blocker)
- ❌ Worker is deployed but cannot function

**Blocked By:**
- None - can deploy immediately after installing Firebase CLI

**Related Components:**
- `dishly-parser-worker` (Cloud Run service) - Already deployed, waiting for indexes
- `src/services/queue_service.py` - Contains query that requires index
- `scripts/firestore_indexes.json` - Index definitions (already correct)

---

## Technical Specifications

### Index Build Time

**Factors Affecting Build Time:**
- Number of existing documents in collection (currently: ~5-10 pending jobs)
- Firestore region (us-central1)
- Number of fields in index (3 fields)

**Expected Build Time:**
- Empty collection: 1-2 minutes
- < 100 documents: 5-10 minutes
- 100-1000 documents: 10-20 minutes
- > 1000 documents: 20-60 minutes

**Dishly Current State:**
- Estimated documents: < 20 (few test imports)
- Expected build time: **5-10 minutes**

---

### Index Storage Overhead

**Storage Impact:**
- Composite index creates additional index entries
- Overhead: ~20-30% of document size per index
- For 100 documents @ 2KB each: ~40-60KB additional storage
- **Impact:** Negligible (well within free tier limits)

---

### Query Performance

**Before Index (Not Possible):**
- Query fails with 400 error
- Worker cannot process queue

**After Index:**
- Query latency: < 100ms (typical)
- Can query up to 10,000 documents efficiently
- Scales linearly with collection size

---

## Risk Assessment

### Risk to Dishly Infrastructure

**Risk Level:** ZERO

**Reasoning:**
- Only adding indexes (not modifying data)
- Firestore automatically manages index creation
- No downtime during index build
- Worker will continue trying to query (exponential backoff)
- Once index is ready, queries will succeed automatically

**Rollback:**
- Can delete index via Firebase Console if needed
- No code changes to revert

---

### Risk to Zest Infrastructure

**Risk Level:** ZERO

**Reasoning:**
1. Dishly uses separate Firebase project (`dishly-prod-fafd3`)
2. Zest uses different Firebase project (different Firestore database)
3. Firestore projects are completely isolated
4. Deploying indexes to Dishly Firebase has NO access to Zest Firebase
5. No shared resources, no shared data

**Verification:**
- Firebase Console shows separate projects
- Service accounts have scoped permissions to specific projects

---

### Edge Cases

**Scenario 1: Firebase CLI not installed**
- **Impact:** `make setup-firestore` fails with "command not found"
- **Mitigation:** Install Firebase CLI: `npm install -g firebase-tools`
- **Recovery Time:** 2 minutes

**Scenario 2: Not authenticated to Firebase**
- **Impact:** Deployment fails with "authentication error"
- **Mitigation:** Run `firebase login` and follow browser auth
- **Recovery Time:** 1 minute

**Scenario 3: Index build fails**
- **Impact:** Index stuck in "ERROR" state
- **Mitigation:** Delete index via console, redeploy
- **Recovery Time:** 10 minutes
- **Likelihood:** Very low (index definition is simple and correct)

**Scenario 4: Index takes longer than expected to build**
- **Impact:** Worker still cannot query for 10-20 minutes
- **Mitigation:** Just wait - Firestore will complete eventually
- **User Impact:** Recipe imports still timeout, but only temporarily
- **Likelihood:** Low (small number of documents)

**Scenario 5: Worker still fails after index is ready**
- **Impact:** Different error appears in logs
- **Root Cause:** Possible different issue (permissions, code bug)
- **Mitigation:** Check logs for new error, debug separately
- **Likelihood:** Very low (index is the only known blocker)

---

## Acceptance Criteria

### Functional Requirements

- [ ] Firestore index deployed to `dishly-prod-fafd3` project
- [ ] Index status shows `ENABLED` in Firebase Console
- [ ] Worker logs show no "index required" errors
- [ ] Worker logs show "Processing job {job_id}" messages
- [ ] Recipe import works end-to-end in Dishly app
- [ ] TikTok URL creates recipe within 60 seconds
- [ ] Instagram URL creates recipe within 60 seconds
- [ ] Old stuck jobs are processed or marked as failed

---

### Performance Requirements

- [ ] Index build completes within 10 minutes
- [ ] Query latency < 100ms after index is ready
- [ ] Worker picks up jobs within 1 minute of queueing
- [ ] No degradation in Firestore read/write performance

---

### Quality Requirements

- [ ] Index definition matches worker query requirements
- [ ] No errors during index deployment
- [ ] Firebase Console shows index with correct fields and order
- [ ] Zero impact on Zest Firebase project (verification check)

---

## Rollback Plan

**If deployment fails or causes issues:**

### Option 1: Delete Index via Firebase Console

1. Open: https://console.firebase.google.com/project/dishly-prod-fafd3/firestore/indexes
2. Find index on `processing_queue` collection
3. Click three dots menu → "Delete"
4. Confirm deletion

**Impact:** Returns to current state (worker still cannot query)

---

### Option 2: Delete Index via Firebase CLI

```bash
firebase firestore:indexes:delete \
  --collection-group=processing_queue \
  --project=dishly-prod-fafd3
```

**Impact:** Returns to current state

---

### Option 3: Redeploy with Corrected Index

```bash
# Edit scripts/firestore_indexes.json
# Fix index definition
# Redeploy
make setup-firestore
```

**Time:** 5-10 minutes

---

## Open Questions

### Q1: Is Firebase CLI already installed?

**Check:**
```bash
which firebase
```

**If not installed:**
```bash
npm install -g firebase-tools
```

**Time:** 2 minutes

**Decision:** Check before proceeding

---

### Q2: Should we manually create index via Firebase Console instead of CLI?

**Option A: Firebase CLI (Recommended)**
- ✅ Faster (one command)
- ✅ Reproducible (uses committed JSON file)
- ✅ Can be automated in CI/CD later
- ❌ Requires Firebase CLI installation

**Option B: Firebase Console (Manual)**
- ✅ No CLI required
- ✅ Visual confirmation
- ❌ Manual process (error-prone)
- ❌ Not reproducible
- ❌ Harder to document

**Recommendation:** Use Firebase CLI (`make setup-firestore`)

**Fallback:** If CLI issues occur, provide manual console instructions

**Decision:** User decides (default to CLI)

---

### Q3: What happens to jobs queued during index build?

**Behavior:**
- Jobs continue to be queued by API service ✅
- Worker continues to attempt queries (every 1-30 seconds)
- Worker gets "index required" error until index is ENABLED
- Once index is ENABLED, worker immediately picks up jobs
- No jobs are lost, no data is corrupted

**User Impact:**
- Recipe imports will timeout during index build (5-10 minutes)
- After index is ready, imports work normally
- Old stuck jobs will be processed automatically

**Recommendation:** Inform users (if any) that imports may be delayed 10 minutes during maintenance

**Decision:** Acceptable temporary downtime

---

### Q4: Should we deploy indexes for other collections now?

**Current Index Deployment:**
- `processing_queue` (required for worker) ✅
- `processing_results` (optional, for debugging) ✅

**Future Indexes (Not Yet Defined):**
- None currently needed

**Recommendation:** Deploy all indexes in `firestore_indexes.json` now (includes both)

**Decision:** Deploy all defined indexes (no harm, future-proof)

---

## Timeline

| Task | Effort | Dependencies |
|------|--------|--------------|
| Verify Firebase CLI installed | 1 min | None |
| Install Firebase CLI (if needed) | 2 min | npm |
| Authenticate to Firebase | 1 min | Firebase CLI |
| Deploy indexes | 1 min | Authentication |
| Wait for index build | 10 min | Deployment |
| Verify index enabled | 2 min | Index build complete |
| Test recipe import | 3 min | Index enabled |
| **Total** | **20 minutes** | |

**Buffer:** Add 5 minutes for unexpected issues
**Total with buffer:** ~25 minutes

---

## Success Metrics

### Immediate Success (Within 30 Minutes)

- ✅ Firestore index deployed to `dishly-prod-fafd3`
- ✅ Index status: `ENABLED` in Firebase Console
- ✅ Worker logs show no "index required" errors
- ✅ At least 1 recipe imported successfully via TikTok
- ✅ At least 1 recipe imported successfully via Instagram
- ✅ Old stuck jobs processed or failed (not stuck)

---

### Ongoing Success (Week 1)

- Recipe import success rate > 80%
- Average queue pickup time < 1 minute
- No "index required" errors in logs
- Worker continues to scale normally

---

## Comparison with Zest Setup

### How Zest Has It Set Up

**Investigation Needed:**

To compare with Zest, we would need to:
1. Check if Zest backend repository has `firestore_indexes.json`
2. Verify Zest's Firebase project has indexes deployed
3. Compare index definitions

**Likely Scenario:**
- Zest deployed Firestore indexes months ago during initial setup
- Zest's indexes are in their separate Firebase project
- Dishly forked backend code (including index definitions) but never deployed them

**Key Insight:**
- Index definitions are correct (copied from Zest)
- We just need to deploy them to Dishly's Firebase project

---

## Completion Checklist

**Before marking as done:**

- [ ] Firebase CLI installed and authenticated
- [ ] Indexes deployed via `make setup-firestore`
- [ ] Index build completed (status: ENABLED)
- [ ] Worker logs show no "index required" errors
- [ ] Recipe imported successfully from TikTok
- [ ] Recipe imported successfully from Instagram
- [ ] Old stuck jobs processed or marked as failed
- [ ] Firebase Console screenshot taken (proof of deployment)
- [ ] PRD moved to `docs/done/` folder

---

# Developer Handoff Instructions

## Overview

You're deploying Firestore composite indexes that the worker needs to query the job queue. This is a **15-minute task** with **ZERO risk to Zest** because Dishly uses a separate Firebase project.

---

## What You're Fixing

**Problem:** Worker deployed and healthy, but cannot query Firestore due to missing indexes.

**Solution:** Deploy existing index definitions using Firebase CLI.

**Code Changes:** ZERO - indexes are already defined in `scripts/firestore_indexes.json`

---

## Prerequisites

**1. Firebase CLI:**
```bash
# Check if installed
which firebase

# If not installed
npm install -g firebase-tools
```

**2. Authenticate:**
```bash
firebase login
# Follow browser authentication

# Verify access
firebase projects:list | grep dishly-prod-fafd3
# Should show: dishly-prod-fafd3
```

**3. Repository:**
```bash
cd /Users/baileygrady/Desktop/dishly-backend
```

---

## Step 1: Check Index Configuration File (2 min)

**Verify index definitions exist:**
```bash
cat scripts/firestore_indexes.json
# Should show index definitions for processing_queue
```

**Check if `firestore.indexes.json` exists in root:**
```bash
ls firestore.indexes.json
```

**If it doesn't exist (expected):**
```bash
# Create symlink (recommended)
ln -s scripts/firestore_indexes.json firestore.indexes.json

# OR copy file
cp scripts/firestore_indexes.json firestore.indexes.json
```

---

## Step 2: Deploy Indexes (1 min)

```bash
make setup-firestore
```

**Expected output:**
```
Deploying Firestore indexes to dishly-prod-fafd3...
✅ Indexes deployed successfully!

Index build status:
processing_queue: BUILDING

Check progress:
https://console.firebase.google.com/project/dishly-prod-fafd3/firestore/indexes
```

---

## Step 3: Wait for Index Build (10 min)

**Monitor progress:**
```bash
# Check every 2 minutes
firebase firestore:indexes --project=dishly-prod-fafd3
```

**Look for:**
- Status: `BUILDING` → `ENABLED`
- When you see `ENABLED`, proceed to verification

**Alternative: Visual monitoring**
- Open: https://console.firebase.google.com/project/dishly-prod-fafd3/firestore/indexes
- Refresh page until status shows green checkmark

---

## Step 4: Verify Worker Can Query (2 min)

**Check worker logs:**
```bash
gcloud logging read \
  "resource.labels.service_name=dishly-parser-worker AND severity>=INFO" \
  --limit=10 \
  --project=zest-45e51
```

**Look for:**
- ✅ "Processing job {job_id}" (worker is working!)
- ✅ No "index required" errors
- ✅ "Job {job_id} completed successfully"

**Test queue health:**
```bash
curl https://dishly-parser-worker-g4zcestszq-uc.a.run.app/worker/queue-health
```

---

## Step 5: Test Recipe Import (3 min)

**Using Dishly app:**
1. Open Dishly Flutter app
2. Navigate to "Add Recipe"
3. Paste: `https://www.tiktok.com/@aussiefitness/video/7564750012312309013`
4. Wait 10-60 seconds
5. Recipe should appear with title, description, image

**Using API directly:**
```bash
curl -X POST https://dishly-parser-g4zcestszq-uc.a.run.app/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@aussiefitness/video/7564750012312309013"}'
```

---

## Troubleshooting

### Issue: "Firebase CLI not found"
**Solution:**
```bash
npm install -g firebase-tools
```

### Issue: "Permission denied" during deployment
**Solution:**
```bash
firebase login --reauth
```

### Issue: Index stuck in "BUILDING" for > 15 minutes
**Solution:**
- This is normal for large collections
- Check Firebase Console for actual status
- If status shows "ERROR", delete and redeploy

### Issue: Worker still shows "index required" after index is ENABLED
**Solution:**
- Wait 1-2 minutes (Firestore propagation delay)
- Check worker logs for different error
- Restart worker if needed (Cloud Run auto-restarts)

---

## Success Criteria

**You're done when:**
- ✅ Index shows `ENABLED` in Firebase Console
- ✅ Worker logs show "Processing job {job_id}"
- ✅ Recipe import works in Dishly app
- ✅ No "index required" errors in logs

---

## Rollback

**If something goes wrong:**

**Delete index:**
```bash
# Via Firebase Console
# https://console.firebase.google.com/project/dishly-prod-fafd3/firestore/indexes
# Click three dots → Delete

# OR via CLI
firebase firestore:indexes:delete \
  --collection-group=processing_queue \
  --project=dishly-prod-fafd3
```

---

## Time Estimate

**Total Time:** 15-20 minutes
- Setup: 3 min
- Deployment: 1 min
- Index build: 5-10 min
- Verification: 2 min
- Testing: 3 min

**Risk:** ZERO to Zest (separate Firebase project)

---

**This is the final step to make recipe imports work! Let's get it done!**

---

**End of PRD-6**
