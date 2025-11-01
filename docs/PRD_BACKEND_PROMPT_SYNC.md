# PRD: Backend Recipe Extraction Prompt Synchronization

**Status:** Draft
**Priority:** P0 (Critical - Blocking Recipe Feature)
**Created:** 2025-11-01
**Owner:** Engineering
**Stakeholders:** Backend Team, Flutter App Team

---

## 1. Problem Statement

### Current Situation
The Dishly backend API at `localhost:8080/process` is returning responses in the **old Zest format** (relationship content) instead of the **new recipe format**, despite updating the AI prompts in `src/services/genai_service.py`.

**Expected Response:**
```json
{
  "title": "High Protein Pepperoni Pizza Chicken Rolls",
  "structuredIngredients": [
    {
      "name": "chicken breast",
      "amount": 2.0,
      "unit": "lbs",
      "emoji": "🍗",
      "preparation": "pounded flat"
    }
  ],
  "instructions": [
    {
      "stepNumber": 1,
      "text": "Pound chicken breast flat...",
      "durationMinutes": 5
    }
  ],
  "prepTimeMinutes": 10,
  "cookTimeMinutes": 25,
  "baseServings": 4
}
```

**Actual Response:**
```json
{
  "title": "High Protein Meal Prep Recipe",
  "description": "This video shows how to make...",
  "image": "data:image/jpeg;base64,..."
  // Missing: structuredIngredients, instructions, timing metadata
}
```

### Business Impact
- ❌ Flutter app cannot display recipe ingredients with amounts/emojis
- ❌ Cannot show step-by-step cooking instructions
- ❌ Cannot display prep/cook time or servings
- ❌ PRD-3 (Recipe UI Overhaul) is blocked
- ❌ App cannot launch without recipe extraction working

---

## 2. Root Cause Analysis

### Architecture Discovery
The backend uses a **dual-service architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│ /process API Endpoint (src/api/process.py)                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ├─► Direct Processing (< 30s videos)
                  │   └─► GenAIService (genai_service.py) ✅ NEW PROMPTS
                  │
                  └─► Queued Processing (> 30s videos)
                      └─► Worker Service (worker_service.py)
                          └─► GenAIServicePool (genai_service_pool.py) ❌ OLD PROMPTS
```

### Specific Issue
There are **TWO separate GenAI service implementations** with **different prompts**:

| File | Service | Prompts | Used By | Status |
|------|---------|---------|---------|--------|
| `src/services/genai_service.py` | `GenAIService` | Recipe extraction (NEW) | Direct processing | ✅ Updated |
| `src/services/genai_service_pool.py` | `GenAIServicePool` | Relationship content (OLD) | Worker service | ❌ Not updated |

### Why `make dev` Didn't Fix It
Running `make dev` restarts both services:
1. **API service** (port 8080) - Uses `GenAIService` ✅
2. **Worker service** (port 8081) - Uses `GenAIServicePool` ❌

The worker service was restarted, but it loaded the **old prompts** from `genai_service_pool.py`.

### Code Evidence

**genai_service.py (UPDATED):**
```python
# Line 194
prompt = "You are an expert culinary AI specializing in extracting structured recipe data..."
# Lines 214-343: New recipe JSON schema with structuredIngredients, instructions, etc.
```

**genai_service_pool.py (NOT UPDATED):**
```python
# Line 244
prompt = "You are an expert relationship coach and lifestyle content analyst..."
# Lines 262-297: Old JSON schema with content_type, mood, occasion, tips
```

---

## 3. Proposed Solutions

### Option A: Immediate Fix (Recommended for MVP)
**Update `genai_service_pool.py` with same prompts as `genai_service.py`**

**Changes Required:**
- Copy recipe extraction prompts from `genai_service.py` lines 194-343
- Paste into `genai_service_pool.py` lines 244-414 (both video and slideshow methods)
- Update emoji mapping constant to pool file
- Restart both services

**Pros:**
- ✅ Minimal change (one file update)
- ✅ Fastest to implement (~15 minutes)
- ✅ Zero risk to existing functionality
- ✅ Unblocks Flutter app development immediately

**Cons:**
- ❌ Prompt duplication (maintenance burden)
- ❌ Future updates require changing two files
- ❌ No long-term architectural improvement

**Estimated Effort:** 15 minutes
**Testing Time:** 10 minutes
**Total Time to Production:** 25 minutes

---

### Option B: Refactor to Shared Prompt Module (Long-term Fix)
**Create a shared prompt configuration module**

**Architecture:**
```
src/services/prompts/
├── __init__.py
├── recipe_prompts.py          # Centralized prompts
└── emoji_mapping.py            # Centralized emoji map

genai_service.py              → imports recipe_prompts
genai_service_pool.py         → imports recipe_prompts
```

**Changes Required:**
1. Create `src/services/prompts/recipe_prompts.py`
2. Extract prompt strings to shared module
3. Update both GenAI services to import prompts
4. Add tests to ensure prompt consistency

**Pros:**
- ✅ Single source of truth for prompts
- ✅ Future updates only require one file change
- ✅ Easier to test prompt variations
- ✅ Better architectural pattern

**Cons:**
- ❌ More complex refactor
- ❌ Requires testing both services
- ❌ Higher risk of breaking existing functionality
- ❌ Takes longer to implement

**Estimated Effort:** 1-2 hours
**Testing Time:** 30 minutes
**Total Time to Production:** 2.5 hours

---

## 4. Recommended Approach

### Phase 1: Immediate Fix (Option A)
**Timeline:** Complete today before bed

1. Update `genai_service_pool.py` with recipe prompts
2. Restart services with `make dev`
3. Test with sample TikTok URL
4. Verify response includes `structuredIngredients` and `instructions`
5. Commit and push to GitHub

**Acceptance Criteria:**
- ✅ API returns `structuredIngredients` array with amounts, units, emojis
- ✅ API returns `instructions` array with step numbers and timing
- ✅ API returns `prepTimeMinutes`, `cookTimeMinutes`, `baseServings`
- ✅ Both direct and queued processing return same format

### Phase 2: Refactor (Option B)
**Timeline:** Next sprint (after MVP launch)

1. Create shared prompt module
2. Migrate both services to use shared prompts
3. Add unit tests for prompt consistency
4. Update documentation

---

## 5. Implementation Details

### Files to Modify (Option A)

**Primary Change:**
- `/Users/baileygrady/Desktop/dishly-backend/src/services/genai_service_pool.py`
  - Lines 22-113: Add `INGREDIENT_EMOJI_MAP` constant
  - Lines 244-297: Update video analysis prompt
  - Lines 344-414: Update slideshow analysis prompt
  - Line 435 (new): Add `_apply_emoji_mapping()` helper method

**No Changes Needed:**
- `src/services/genai_service.py` - Already updated ✅
- `src/api/process.py` - Request routing works correctly
- `src/worker/worker_service.py` - Worker logic is fine
- `src/models/responses.py` - Response model accepts new fields

### Restart Procedure

**Stop Services:**
```bash
# In terminal running make dev
Ctrl+C  # Stop both API and worker
```

**Start Services:**
```bash
make dev  # Restart with new prompts loaded
```

**Verify Startup:**
- API should start on port 8080
- Worker should start on port 8081
- Check logs for "GenAI service initialized"

---

## 6. Testing Strategy

### Test Case 1: Simple Recipe (Direct Processing)
**Input:**
```bash
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@aussiefitness/video/7564750012312309013"}'
```

**Expected Output:**
```json
{
  "title": "High Protein Pepperoni Pizza Chicken Rolls",
  "structuredIngredients": [
    {"name": "chicken breast", "amount": 2.0, "unit": "lbs", "emoji": "🍗"}
  ],
  "instructions": [
    {"stepNumber": 1, "text": "Pound chicken...", "durationMinutes": 5}
  ],
  "prepTimeMinutes": 10,
  "cookTimeMinutes": 25
}
```

### Test Case 2: Complex Recipe (Queued Processing)
**Input:** Long Instagram recipe video (> 30s)

**Expected:** Same structured format with more ingredients/steps

### Test Case 3: Edge Cases
- Recipe with qualitative amounts ("drizzle", "pinch")
- Recipe without timing information
- Recipe with substitutions ("or tofu")

---

## 7. Dependencies & Impacts

### Systems Affected
- ✅ Backend API service (port 8080)
- ✅ Backend worker service (port 8081)
- ✅ Firestore (no changes needed)
- ✅ Google Gemini AI (no changes needed)

### Downstream Impacts
- **Flutter App:** Will receive new fields - already supports them (PRD-3)
- **Database:** Firestore already supports structured recipe fields
- **Cache:** May contain old-format responses - consider clearing

### Breaking Changes
- ❌ None - New fields are additive
- ❌ Old clients will ignore new fields (backward compatible)

---

## 8. Open Questions

### Q1: Cache Invalidation
**Question:** Should we clear Firestore cache of old-format recipes?

**Options:**
1. Clear all cache entries (force re-processing)
2. Keep old entries, new requests get new format
3. Add migration script to reprocess popular recipes

**Recommendation:** Option 2 (keep old entries) - simplest, no data loss

---

### Q2: Response Model Updates
**Question:** Should we update `src/models/responses.py` to enforce new fields?

**Current Model:**
```python
class RelationshipContent(BaseModel):
    title: str
    description: Optional[str]
    image: Optional[str]
    content_type: Optional[str]  # Old field
    mood: Optional[str]           # Old field
```

**Proposed Model:**
```python
class RecipeContent(BaseModel):
    title: str
    description: Optional[str]
    image: Optional[str]
    structuredIngredients: Optional[List[IngredientModel]]
    instructions: Optional[List[InstructionModel]]
    prepTimeMinutes: Optional[int]
    cookTimeMinutes: Optional[int]
    baseServings: Optional[int]
```

**Recommendation:** Yes, but in Phase 2 (after immediate fix works)

---

### Q3: Logging & Monitoring
**Question:** Should we add structured logging for new recipe fields?

**Options:**
1. Log ingredient count, step count, timing metadata
2. Track AI extraction success rate
3. Alert if new fields are missing

**Recommendation:** Add basic logging in Phase 2

---

## 9. Success Metrics

### Immediate (Phase 1)
- ✅ 100% of API responses include `structuredIngredients`
- ✅ 100% of API responses include `instructions`
- ✅ 95%+ of recipes have emoji-enhanced ingredients
- ✅ 80%+ of recipes have timing metadata

### Long-term (Phase 2)
- ✅ Prompt updates require changing only 1 file (not 2)
- ✅ Zero prompt drift between direct and queued processing
- ✅ Unit tests validate prompt consistency

---

## 10. Migration Plan

### Immediate (Tonight)
1. ✅ Update `genai_service_pool.py` with recipe prompts
2. ✅ Restart backend services
3. ✅ Test with 3 sample URLs (TikTok, Instagram, edge case)
4. ✅ Commit to GitHub
5. ✅ Document in PRD-4 implementation report

### Tomorrow
1. Test end-to-end with Flutter app
2. Verify recipe display in app UI
3. Test servings calculator with scaled amounts
4. Test cooking mode with highlighted ingredients

### Next Sprint
1. Refactor to shared prompt module (Option B)
2. Add unit tests for prompt consistency
3. Update response models with strict typing
4. Add structured logging

---

## 11. Rollback Plan

### If Fix Doesn't Work
**Symptoms:**
- API still returns old format
- Errors in worker logs
- Gemini API errors

**Rollback Steps:**
```bash
# Revert genai_service_pool.py changes
git checkout HEAD -- src/services/genai_service_pool.py

# Restart services
make dev
```

**Recovery Time:** < 5 minutes

---

## 12. Related Documents

- **PRD-3:** Recipe UI Overhaul (Flutter app requirements)
- **PRD-4:** Backend Fork Strategy (Zest → Dishly migration)
- **Implementation Report:** PRD_3_IMPLEMENTATION_REPORT.md
- **Architecture:** Backend uses FastAPI + Gemini 2.0 Flash Lite

---

## 13. Conclusion

### Problem Summary
The backend has duplicate GenAI service implementations with inconsistent prompts. The worker service uses the old prompts, causing API responses to return the wrong format.

### Recommended Solution
**Phase 1 (Immediate):** Update `genai_service_pool.py` with recipe extraction prompts - takes 25 minutes total.

**Phase 2 (Next Sprint):** Refactor to shared prompt module to prevent future drift.

### Risk Assessment
- **Risk Level:** Low
- **Blast Radius:** Single file change
- **Rollback Time:** < 5 minutes
- **Testing Required:** 10 minutes

### Approval Required
- [ ] Engineering Lead - Review implementation approach
- [ ] Backend Dev - Review code changes
- [ ] QA - Test with sample URLs

---

**Ready to proceed with Phase 1 implementation upon approval.**
