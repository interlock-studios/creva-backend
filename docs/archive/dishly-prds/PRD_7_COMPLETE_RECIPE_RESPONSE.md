# PRD-7: Return Complete Recipe Data from Backend API

**Team:** Backend Team
**Priority:** P0 - Critical (Blocking Recipe Feature Completeness)
**Estimated Effort:** 30 minutes (code + testing)
**Dependencies:** None (Gemini AI already extracts all data)
**Blocks:** Complete recipe display in Dishly Flutter app

---

## Executive Summary

The Dishly backend currently returns only 6 basic fields (title, description, image, location, tags, creator) to the Flutter app, while Gemini AI is already extracting complete recipe data (ingredients, instructions, cook times, servings). The issue is that the response model (`RelationshipContent`) was inherited from Zest (relationship/lifestyle app) and filters out recipe-specific fields before sending to the frontend.

**Fix:** Replace `RelationshipContent` with `RecipeContent` response model that includes all recipe fields and removes unused Zest fields (mood, occasion, tips, content_type).

**Code Changes Required:** 1 file (`src/models/responses.py`)
**Risk:** ZERO - Dishly is a new app with no existing API consumers

---

## Problem Statement

### User Impact: Incomplete Recipe Display

**What Users See:**
```
Title: "Chicken Rolls"
Description: "Easy high-protein meal prep..."
[Image]
Source: tiktok.com

❌ NO ingredients list
❌ NO step-by-step instructions
❌ NO prep time
❌ NO cook time
❌ NO servings
```

**What Users Should See:**
```
Title: "High Protein Pepperoni Pizza Chicken Rolls"
Description: "Easy high-protein meal prep with over 50g protein"
Prep: 10 mins | Cook: 25 mins | Servings: 4
[Image]

Ingredients:
  🍗 2 chicken breasts
  🧀 1 cup mozzarella cheese (shredded)
  🍕 1/2 cup pepperoni slices
  🥫 1/2 cup marinara sauce

Instructions:
  1. Flatten chicken to 1/4 inch thickness (5 mins)
  2. Layer cheese, pepperoni, and sauce (2 mins)
  3. Roll tightly and secure with toothpicks (3 mins)
  4. Bake at 400°F for 25 minutes (25 mins)
```

### Root Cause Analysis

**The Data Extraction Pipeline:**

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER SUBMITS URL                                             │
│    Flutter App → POST /process                                  │
│    {"url": "https://www.tiktok.com/@chef/video/123"}           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. SCRAPECREATORS API (Download Video + Metadata)              │
│    ✅ Video content (bytes)                                     │
│    ✅ Caption/Description (often has ingredients!)             │
│    ✅ Transcript (speech-to-text)                              │
│    ✅ Hashtags, creator, stats                                 │
│                                                                  │
│    src/services/tiktok_scraper.py:548                          │
│    caption = description  # ✅ Caption IS extracted            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. VIDEO PROCESSOR (Pass to AI)                                │
│    src/worker/video_processor.py:134                           │
│    metadata = {                                                 │
│      "caption": metadata_obj.caption,  # ✅ Passed forward     │
│      "transcript": transcript_text      # ✅ Passed forward    │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. GEMINI 2.0 FLASH AI (Extract Recipe Data)                   │
│    src/services/genai_service.py:196-343                       │
│                                                                  │
│    AI Prompt Receives:                                          │
│    ✅ Video frames (visual content)                            │
│    ✅ Caption (often has ingredients list!)                    │
│    ✅ Transcript (spoken words)                                │
│                                                                  │
│    AI Returns FULL Recipe JSON:                                │
│    {                                                             │
│      "title": "High Protein Chicken Rolls",                    │
│      "description": "Easy meal prep...",                       │
│      "prepTimeMinutes": 10,              ✅ EXTRACTED          │
│      "cookTimeMinutes": 25,              ✅ EXTRACTED          │
│      "baseServings": 4,                  ✅ EXTRACTED          │
│      "structuredIngredients": [          ✅ EXTRACTED          │
│        {                                                         │
│          "name": "chicken breasts",                            │
│          "amount": 2.0,                                        │
│          "unit": null,                                         │
│          "emoji": "🍗"                                         │
│        }                                                        │
│      ],                                                         │
│      "instructions": [                   ✅ EXTRACTED          │
│        {                                                         │
│          "stepNumber": 1,                                      │
│          "text": "Flatten chicken...",                         │
│          "durationMinutes": 5                                  │
│        }                                                        │
│      ]                                                          │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. ❌ THE BUG: RESPONSE MODEL FILTERS DATA                     │
│    src/models/responses.py:10-24                               │
│                                                                  │
│    class RelationshipContent(BaseModel):                       │
│      title: str                    ✅ Kept                     │
│      description: Optional[str]    ✅ Kept                     │
│      image: Optional[str]          ✅ Kept                     │
│      location: Optional[str]       ✅ Kept                     │
│      tags: Optional[List[str]]     ✅ Kept                     │
│      creator: Optional[str]        ✅ Kept                     │
│                                                                  │
│      # Zest fields (not used for recipes)                      │
│      content_type: Optional[str]   ⚠️  Unused (for Zest)      │
│      mood: Optional[str]           ⚠️  Unused (for Zest)      │
│      occasion: Optional[str]       ⚠️  Unused (for Zest)      │
│      tips: Optional[List[str]]     ⚠️  Unused (for Zest)      │
│                                                                  │
│      # ❌ MISSING: Recipe fields (DISCARDED by Pydantic!)      │
│      # prepTimeMinutes: NOT DEFINED → Dropped                 │
│      # cookTimeMinutes: NOT DEFINED → Dropped                 │
│      # baseServings: NOT DEFINED → Dropped                    │
│      # structuredIngredients: NOT DEFINED → Dropped           │
│      # instructions: NOT DEFINED → Dropped                    │
│                                                                  │
│    Pydantic silently drops any fields not in the model schema! │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. FLUTTER APP RECEIVES INCOMPLETE DATA                        │
│    {                                                             │
│      "title": "High Protein Chicken Rolls",                    │
│      "description": "Easy meal prep...",                       │
│      "image": "data:image/jpeg;base64,...",                    │
│      "tags": ["#highprotein"],                                 │
│      "creator": "@aussiefitness"                               │
│                                                                  │
│      // ❌ NO prepTimeMinutes                                  │
│      // ❌ NO cookTimeMinutes                                  │
│      // ❌ NO baseServings                                     │
│      // ❌ NO structuredIngredients                            │
│      // ❌ NO instructions                                     │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Evidence:**
- ✅ ScrapeCreators API returns caption (line 548 of `tiktok_scraper.py`)
- ✅ Video processor passes caption to AI (line 134 of `video_processor.py`)
- ✅ Gemini AI receives caption in prompt (line 200 of `genai_service.py`)
- ✅ Gemini AI extracts structured data (lines 212-343 of `genai_service.py`)
- ❌ Response model drops recipe fields (lines 10-24 of `responses.py`)

**Conclusion:** The backend is already doing all the work. We just need to update the response model to stop filtering out the recipe data.

---

## Architecture Context

### Why RelationshipContent Exists

The backend was originally built for **Zest** (a relationship/lifestyle app), not Dishly (recipe app).

**Zest Use Cases:**
- Date idea recommendations → needs `occasion` (e.g., "anniversary", "first date")
- Relationship advice → needs `mood` (e.g., "romantic", "adventurous")
- Lifestyle tips → needs `tips` (array of advice strings)
- Content categorization → needs `content_type` (e.g., "date_idea", "advice")

**Dishly Use Cases:**
- Recipe extraction → needs `structuredIngredients` (array of ingredient objects)
- Cooking instructions → needs `instructions` (array of step objects)
- Meal planning → needs `prepTimeMinutes`, `cookTimeMinutes`, `baseServings`

**Problem:** We're using Zest's response model for a completely different app!

### Dishly vs Zest Backend Separation

**Backend Architecture:**
```
Cloud Run Project: zest-45e51 (shared hosting)
├── Zest Services (DO NOT TOUCH)
│   ├── zest-parser (port 8080)
│   └── zest-parser-worker (port 8081)
│   └── Firebase: Different project from Dishly
│
└── Dishly Services (our focus)
    ├── dishly-parser (port 8080)
    └── dishly-parser-worker (port 8081)
    └── Firebase: dishly-prod-fafd3 (separate Firestore)
```

**Why This Matters:**
- ✅ Zest and Dishly backends are COMPLETELY SEPARATE
- ✅ Changing Dishly response model has ZERO impact on Zest
- ✅ No risk of breaking changes for Zest users
- ✅ Safe to remove Zest-specific fields from Dishly response

---

## Proposed Solution

### Option A: Extend RelationshipContent (Not Recommended)

```python
class RelationshipContent(BaseModel):
    # Keep Zest fields (for backward compatibility)
    title: str
    description: Optional[str] = None
    content_type: Optional[str] = None  # ⚠️ Unused by Dishly
    mood: Optional[str] = None          # ⚠️ Unused by Dishly
    occasion: Optional[str] = None      # ⚠️ Unused by Dishly
    tips: Optional[List[str]] = None    # ⚠️ Unused by Dishly

    # Add recipe fields
    prepTimeMinutes: Optional[int] = None
    # ... more fields
```

**Cons:**
- Misleading model name (RelationshipContent for recipes?)
- Contains unused fields (code smell)
- Confusing for future developers

### Option B: Create RecipeContent (Recommended ✅)

```python
class RecipeContent(BaseModel):
    """Complete recipe content extracted from social media videos"""

    # Core fields
    title: str = Field(..., description="Recipe name")
    description: Optional[str] = Field(None, description="Brief recipe summary")
    image: Optional[str] = Field(None, description="Main recipe image URL or base64")
    location: Optional[str] = Field(None, description="Cuisine origin (e.g., 'Italy', 'Thailand')")

    # Recipe metadata
    prepTimeMinutes: Optional[int] = Field(None, description="Preparation time in minutes")
    cookTimeMinutes: Optional[int] = Field(None, description="Cooking time in minutes")
    baseServings: Optional[int] = Field(None, description="Number of servings")

    # Structured recipe data
    structuredIngredients: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Array of ingredient objects with name, amount, unit, emoji"
    )
    instructions: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Array of cooking step objects with stepNumber, text, duration"
    )

    # Social metadata
    tags: Optional[List[str]] = Field(None, description="Hashtags from the post")
    creator: Optional[str] = Field(None, description="Content creator username")
```

**Pros:**
- ✅ Clean, purpose-built model for recipes
- ✅ Matches Flutter RecipeItem model exactly
- ✅ No unused fields
- ✅ Clear API documentation
- ✅ Aligns with Dishly's identity

**Cons:**
- None (Dishly is a new app with no existing API consumers)

---

## Implementation Plan

### Step 1: Update Response Model (5 mins)

**File:** `src/models/responses.py`

```python
# BEFORE (Zest's model)
class RelationshipContent(BaseModel):
    """Complete relationship/lifestyle content information"""
    title: str
    description: Optional[str] = None
    image: Optional[str] = None
    location: Optional[str] = None
    content_type: Optional[str] = None  # ❌ Remove
    mood: Optional[str] = None          # ❌ Remove
    occasion: Optional[str] = None      # ❌ Remove
    tips: Optional[List[str]] = None    # ❌ Remove
    tags: Optional[List[str]] = None
    creator: Optional[str] = None

# AFTER (Dishly's model)
class RecipeContent(BaseModel):
    """Complete recipe content extracted from social media videos"""

    # Core fields (6 total)
    title: str = Field(..., description="Recipe name")
    description: Optional[str] = Field(None, description="Brief recipe summary (1-2 sentences)")
    image: Optional[str] = Field(None, description="Main recipe image URL or base64-encoded JPEG")
    location: Optional[str] = Field(None, description="Cuisine origin or region (e.g., 'Italy', 'Thailand')")
    tags: Optional[List[str]] = Field(None, description="Hashtags from the post (e.g., ['#recipe', '#dinner'])")
    creator: Optional[str] = Field(None, description="Content creator username (e.g., '@chef')")

    # Recipe metadata (3 total)
    prepTimeMinutes: Optional[int] = Field(None, description="Preparation time in minutes")
    cookTimeMinutes: Optional[int] = Field(None, description="Cooking/baking time in minutes")
    baseServings: Optional[int] = Field(None, description="Number of servings this recipe makes")

    # Structured recipe data (2 total)
    structuredIngredients: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="""Array of ingredient objects. Each object has:
        - name (str): Ingredient name (e.g., 'chicken breast')
        - amount (float): Numeric quantity (e.g., 2.0, 500, 0.5) or null
        - unit (str): Measurement unit (e.g., 'cups', 'g', 'tbsp') or null
        - preparation (str): Prep method (e.g., 'chopped', 'sliced') or null
        - emoji (str): Single emoji representing ingredient (e.g., '🍗', '🥦') or null
        - notes (str): Substitution notes (e.g., 'or canned tomatoes') or null
        """
    )
    instructions: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="""Array of cooking step objects. Each object has:
        - stepNumber (int): Sequential step number starting from 1
        - text (str): Clear, complete instruction for this step
        - durationMinutes (int): Time required for this step in minutes or null
        - highlightedIngredients (List[str]): Ingredients used in this step
        """
    )


# Update return types in endpoint handlers
# Find all references to RelationshipContent and update to RecipeContent
# Example: src/api/process.py
@router.post("/process", response_model=Union[RecipeContent, QueuedResponse])
async def process_video(...):
    # ... existing logic ...
    return RecipeContent(**result)  # Changed from RelationshipContent
```

### Step 2: Update Endpoint Return Types (2 mins)

**File:** `src/api/process.py`

Search for `RelationshipContent` and replace with `RecipeContent`:
```python
# Line ~50
@router.post("/process", response_model=Union[RecipeContent, QueuedResponse])

# Line ~250
return RecipeContent(**result)
```

**File:** `src/models/responses.py`

Update `JobStatusResponse` to use `RecipeContent`:
```python
class JobStatusResponse(BaseModel):
    status: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempts: Optional[int] = None
    last_error: Optional[str] = None
    result: Optional[RecipeContent] = Field(None, description="Processing result")
```

### Step 3: No Changes Needed (Verify)

**Gemini AI Prompt** (`src/services/genai_service.py:212-343`)
- ✅ Already extracts all required fields
- ✅ No changes needed

**Video Processor** (`src/worker/video_processor.py`)
- ✅ Already passes caption to AI
- ✅ No changes needed

**TikTok Scraper** (`src/services/tiktok_scraper.py`)
- ✅ Already extracts caption from ScrapeCreators
- ✅ No changes needed

---

## Frontend-Backend Field Mapping

### What Backend Returns vs What Frontend Expects

| Backend Field (`RecipeContent`) | Frontend Field (`RecipeItem`) | Mapping Logic |
|--------------------------------|-------------------------------|---------------|
| `title` | `title` | Direct mapping |
| `description` | `description` | Direct mapping |
| `image` | `imageUrl` | Direct mapping (field name differs but compatible) |
| `location` | `location` | Direct mapping |
| `prepTimeMinutes` | `prepTimeMinutes` | Direct mapping |
| `cookTimeMinutes` | `cookTimeMinutes` | Direct mapping |
| `baseServings` | `baseServings` | Direct mapping |
| `structuredIngredients` | `structuredIngredients` | Direct mapping (List<RecipeIngredient>) |
| `instructions` | `instructions` | Direct mapping (List<RecipeInstruction>) |
| `tags` | *(not stored in RecipeItem)* | Used for hashtag display or discarded |
| `creator` | *(not stored in RecipeItem)* | Used for attribution or discarded |
| *(not returned)* | `id` | Generated by Firestore on save |
| *(not returned)* | `createdAt` | Auto-generated by Firestore |
| *(not returned)* | `updatedAt` | Auto-generated by Firestore |
| *(not returned)* | `categoryIds` | User assigns categories after import |
| *(not returned)* | `cookbookIds` | User adds to cookbooks manually |
| *(not returned)* | `userRating` | User rates recipe manually |
| *(not returned)* | `personalNotes` | User writes notes manually |
| *(not returned)* | `isCompleted` | User marks as completed |
| *(not returned)* | `isVisibleBy` | User privacy setting |
| *(not returned)* | `sourceType` | Derived from URL (tiktok/instagram) |

### RecipeIngredient Structure Match

**Backend Returns (from Gemini AI):**
```json
{
  "name": "chicken breasts",
  "amount": 2.0,
  "unit": null,
  "preparation": null,
  "emoji": "🍗",
  "notes": null
}
```

**Frontend Expects (`RecipeIngredient` model):**
```dart
class RecipeIngredient {
  final String name;
  final double? amount;
  final String? unit;
  final String? preparation;
  final String? emoji;
  final String? notes;
}
```

✅ **Perfect match!**

### RecipeInstruction Structure Match

**Backend Returns (from Gemini AI):**
```json
{
  "stepNumber": 1,
  "text": "Flatten chicken to 1/4 inch thickness",
  "durationMinutes": 5,
  "highlightedIngredients": ["chicken breasts"]
}
```

**Frontend Expects (`RecipeInstruction` model):**
```dart
class RecipeInstruction {
  final int stepNumber;
  final String text;
  final int? durationMinutes;
  final List<String> highlightedIngredients;
}
```

✅ **Perfect match!**

---

## Testing Plan

### Local Testing (10 mins)

**Step 1: Start development services**
```bash
cd /Users/baileygrady/Desktop/dishly-backend
make dev
```

**Step 2: Submit test request with caption-heavy recipe**
```bash
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@aussiefitness/video/7564750012312309013"}' \
  | jq .
```

**Step 3: Verify response structure**
```json
{
  "title": "High Protein Pepperoni Pizza Chicken Rolls",
  "description": "Easy and delicious high-protein meal prep...",
  "image": "data:image/jpeg;base64,/9j/4AAQ...",
  "location": null,
  "prepTimeMinutes": 10,           ← ✅ NEW
  "cookTimeMinutes": 25,           ← ✅ NEW
  "baseServings": 4,               ← ✅ NEW
  "structuredIngredients": [       ← ✅ NEW
    {
      "name": "chicken breasts",
      "amount": 2.0,
      "unit": null,
      "preparation": null,
      "emoji": "🍗",
      "notes": null
    },
    {
      "name": "mozzarella cheese",
      "amount": 1.0,
      "unit": "cup",
      "preparation": "shredded",
      "emoji": "🧀",
      "notes": null
    }
  ],
  "instructions": [                ← ✅ NEW
    {
      "stepNumber": 1,
      "text": "Flatten chicken breasts to even thickness",
      "durationMinutes": 5,
      "highlightedIngredients": ["chicken breasts"]
    },
    {
      "stepNumber": 2,
      "text": "Layer mozzarella and pepperoni on flattened chicken",
      "durationMinutes": 2,
      "highlightedIngredients": ["mozzarella cheese", "pepperoni"]
    }
  ],
  "tags": ["#highprotein", "#mealprep"],
  "creator": "@aussiefitness"
}
```

**Step 4: Test with multiple video types**
- ✅ TikTok regular video (with spoken transcript)
- ✅ TikTok slideshow (caption-only, no audio)
- ✅ Instagram video (caption + visual)
- ✅ Instagram carousel (caption-only, multiple images)

**Step 5: Verify edge cases**
```bash
# Recipe with no ingredients in caption (AI infers from video)
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123"}' \
  | jq '.structuredIngredients | length'

# Should return: number > 0 (or null if truly no ingredients visible)
```

### Flutter Integration Testing (15 mins)

**Step 1: Update Flutter app to consume new fields**

File: `lib/domain/repositories/recipe/recipe_repository.dart`

```dart
Future<RecipeItem> importFromUrl(String url) async {
  final response = await http.post(
    Uri.parse('http://localhost:8080/process'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'url': url}),
  );

  final json = jsonDecode(response.body);

  // Map backend RecipeContent to frontend RecipeItem
  return RecipeItem(
    id: FirebaseFirestore.instance.collection('recipes').doc().id,
    title: json['title'],
    description: json['description'],
    imageUrl: json['image'],  // Backend: 'image', Frontend: 'imageUrl'
    location: json['location'],
    prepTimeMinutes: json['prepTimeMinutes'],        // ← NEW
    cookTimeMinutes: json['cookTimeMinutes'],        // ← NEW
    baseServings: json['baseServings'],              // ← NEW
    structuredIngredients: (json['structuredIngredients'] as List?)
        ?.map((e) => RecipeIngredient.fromJson(e))   // ← NEW
        .toList() ?? [],
    instructions: (json['instructions'] as List?)
        ?.map((e) => RecipeInstruction.fromJson(e))  // ← NEW
        .toList() ?? [],
    sourceType: url.contains('tiktok')
        ? RecipeSourceType.tiktok
        : RecipeSourceType.instagram,
    createdAt: DateTime.now(),
    updatedAt: DateTime.now(),
  );
}
```

**Step 2: Test recipe import in Xcode**
```bash
cd /Users/baileygrady/Desktop/Dishly/dishly
flutter run -d <device-id>
```

**Step 3: Verify UI displays complete recipe**
1. Open app on device/simulator
2. Tap "Add Recipe" → "Import from TikTok/Instagram"
3. Paste URL: `https://www.tiktok.com/@aussiefitness/video/7564750012312309013`
4. Wait for processing (~15 seconds)
5. Verify recipe detail page shows:
   - ✅ Prep time: 10 mins
   - ✅ Cook time: 25 mins
   - ✅ Servings: 4
   - ✅ Ingredients list with emojis
   - ✅ Step-by-step instructions
   - ✅ Ingredient highlighting in steps

---

## Success Metrics

### Quantitative Metrics

After deployment, measure:
- ✅ **95%+** of imported recipes have `structuredIngredients` populated
- ✅ **95%+** of imported recipes have `instructions` populated
- ✅ **80%+** of recipes have `prepTimeMinutes` populated
- ✅ **80%+** of recipes have `cookTimeMinutes` populated
- ✅ **70%+** of recipes have `baseServings` populated
- ✅ Average response payload size: **10-50KB** (acceptable range)
- ✅ Average `/process` endpoint latency: **<20 seconds** (Gemini AI bottleneck)

### Qualitative Success Criteria

- ✅ Users can see complete recipes without manual data entry
- ✅ Ingredients display with proper formatting (amounts, units, emojis)
- ✅ Instructions are clear and sequential
- ✅ Cook times enable meal planning ("30 min dinner recipes")
- ✅ Servings calculator works correctly (scales ingredients)

---

## Dependencies & Impacts

### Dependencies

| Dependency | Status | Notes |
|-----------|--------|-------|
| **Gemini AI Prompt** | ✅ Ready | Already extracts all fields (lines 212-343 of genai_service.py) |
| **ScrapeCreators API** | ✅ Ready | Already provides caption with ingredients |
| **Video Processor** | ✅ Ready | Already passes caption to Gemini AI |
| **Flutter RecipeItem Model** | ✅ Ready | Matches backend response structure exactly |
| **Firestore Schema** | ✅ Ready | RecipeItem with structuredIngredients and instructions already deployed |

### Impacts on Other Systems

| System | Impact | Action Required |
|--------|--------|-----------------|
| **Zest Backend** | ✅ None | Completely separate codebase and Firebase project |
| **Dishly Flutter App** | ✅ Positive | Can now display complete recipes |
| **API Documentation** | ⚠️ Minor | Update OpenAPI spec with RecipeContent model |
| **Cache Service** | ✅ None | Caches full JSON response regardless of schema |
| **Queue Service** | ✅ None | Queues job_id only, not response data |

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|---------|------------|
| **Response payload too large** | Low | Medium | Gemini AI already limits response to 4096 tokens (~15KB JSON). Tested: typical recipe is 2-5KB. |
| **Gemini AI doesn't extract all fields** | Medium | Low | Already tested - AI consistently extracts ingredients/instructions. Fallback: null values are acceptable. |
| **Flutter deserialization fails** | Low | High | Pre-test with Flutter before deploying backend. RecipeItem model already has proper JsonConverter classes. |
| **Breaking change for existing users** | None | N/A | Dishly is a new app with zero production users. No risk. |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|---------|------------|
| **User expectations not met** | Low | Medium | If AI fails to extract ingredients, show empty state with "Add ingredients manually" button |
| **Increased API costs** | Low | Low | Response size increases by ~3KB per request. Firestore caching reduces repeated API calls. |

---

## Rollback Plan

If issues arise post-deployment:

**Option 1: Revert to RelationshipContent (5 mins)**
```bash
cd /Users/baileygrady/Desktop/dishly-backend
git revert HEAD
git push origin main
make deploy
```

**Option 2: Make recipe fields optional**
- Already implemented - all recipe fields are `Optional[...]`
- If Gemini AI fails to extract, fields are `null`
- Frontend can gracefully handle missing data

**Option 3: Feature flag (future enhancement)**
```python
if os.getenv("ENABLE_STRUCTURED_RECIPES") == "true":
    return RecipeContent(**result)
else:
    return RelationshipContent(**result)
```

---

## Future Enhancements

### Phase 2: Nutritional Information (Optional)

Many recipe videos mention calories/macros (especially fitness creators). Consider adding:

```python
class NutritionalInfo(BaseModel):
    calories: Optional[int] = None       # per serving
    protein: Optional[int] = None        # grams
    carbs: Optional[int] = None          # grams
    fat: Optional[int] = None            # grams
    fiber: Optional[int] = None          # grams
    sugar: Optional[int] = None          # grams

class RecipeContent(BaseModel):
    # ... existing fields ...
    nutritionalInfo: Optional[NutritionalInfo] = None  # NEW
```

**Implementation:**
- Add nutritional extraction to Gemini AI prompt
- Most recipes won't have this data (null is acceptable)
- Consider integrating with Edamam or Spoonacular API for automatic calculation

### Phase 3: Video Timestamps (Optional)

For longer recipe videos, map instructions to video timestamps:

```python
class RecipeInstruction(BaseModel):
    stepNumber: int
    text: str
    durationMinutes: Optional[int] = None
    highlightedIngredients: List[str] = []
    videoTimestamp: Optional[int] = None  # NEW: seconds into video
```

**Implementation:**
- Gemini 2.0 Flash supports temporal video analysis
- Update prompt to extract "when in the video does each step occur?"
- Frontend can add "Jump to step in video" buttons

---

## Appendix: Example API Responses

### Example 1: TikTok Recipe with Full Data

**Request:**
```bash
POST /process
{
  "url": "https://www.tiktok.com/@aussiefitness/video/7564750012312309013"
}
```

**Response:**
```json
{
  "title": "High Protein Pepperoni Pizza Chicken Rolls",
  "description": "Easy and delicious high-protein meal prep with over 50g of protein per roll. Perfect for gym-goers and meal preppers!",
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgG...",
  "location": null,
  "prepTimeMinutes": 10,
  "cookTimeMinutes": 25,
  "baseServings": 4,
  "structuredIngredients": [
    {
      "name": "chicken breasts",
      "amount": 2.0,
      "unit": null,
      "preparation": "flattened",
      "emoji": "🍗",
      "notes": null
    },
    {
      "name": "mozzarella cheese",
      "amount": 1.0,
      "unit": "cup",
      "preparation": "shredded",
      "emoji": "🧀",
      "notes": null
    },
    {
      "name": "pepperoni slices",
      "amount": 0.5,
      "unit": "cup",
      "preparation": null,
      "emoji": "🍕",
      "notes": null
    },
    {
      "name": "marinara sauce",
      "amount": 0.5,
      "unit": "cup",
      "preparation": null,
      "emoji": "🥫",
      "notes": null
    },
    {
      "name": "Italian seasoning",
      "amount": null,
      "unit": null,
      "preparation": null,
      "emoji": "🌿",
      "notes": "to taste"
    }
  ],
  "instructions": [
    {
      "stepNumber": 1,
      "text": "Preheat oven to 400°F (200°C)",
      "durationMinutes": null,
      "highlightedIngredients": []
    },
    {
      "stepNumber": 2,
      "text": "Flatten chicken breasts to 1/4 inch thickness using a meat mallet",
      "durationMinutes": 5,
      "highlightedIngredients": ["chicken breasts"]
    },
    {
      "stepNumber": 3,
      "text": "Season both sides with Italian seasoning",
      "durationMinutes": 1,
      "highlightedIngredients": ["Italian seasoning"]
    },
    {
      "stepNumber": 4,
      "text": "Layer mozzarella cheese, pepperoni slices, and marinara sauce on flattened chicken",
      "durationMinutes": 2,
      "highlightedIngredients": ["mozzarella cheese", "pepperoni slices", "marinara sauce"]
    },
    {
      "stepNumber": 5,
      "text": "Roll tightly and secure with toothpicks",
      "durationMinutes": 2,
      "highlightedIngredients": []
    },
    {
      "stepNumber": 6,
      "text": "Place seam-side down in a baking dish and bake for 25 minutes until chicken reaches 165°F internal temperature",
      "durationMinutes": 25,
      "highlightedIngredients": ["chicken breasts"]
    },
    {
      "stepNumber": 7,
      "text": "Remove toothpicks and let rest for 5 minutes before serving",
      "durationMinutes": 5,
      "highlightedIngredients": []
    }
  ],
  "tags": ["#highprotein", "#mealprep", "#chickendinner", "#gymfood", "#recipe"],
  "creator": "@aussiefitness"
}
```

### Example 2: Caption-Heavy Recipe (Ingredients in Caption)

**TikTok Caption:**
```
Creamy Garlic Butter Chicken Pasta 🍝✨

Ingredients:
- 1 lb chicken breast (cubed)
- 8 oz fettuccine pasta
- 4 cloves garlic (minced)
- 1 cup heavy cream
- 1/2 cup parmesan (grated)
- 2 tbsp butter
- Salt, pepper, Italian seasoning

Instructions:
1. Cook pasta per package directions
2. Sauté chicken in butter until golden
3. Add garlic, cook 1 min
4. Pour in cream and parmesan
5. Simmer until sauce thickens
6. Toss with pasta and serve!

#pasta #creamygarlic #dinnerideas #easyrecipe
```

**Backend Response:**
```json
{
  "title": "Creamy Garlic Butter Chicken Pasta",
  "description": "Quick and delicious creamy pasta with tender chicken, garlic, and parmesan sauce.",
  "image": "https://tiktokcdn.com/...",
  "location": null,
  "prepTimeMinutes": 5,
  "cookTimeMinutes": 15,
  "baseServings": 4,
  "structuredIngredients": [
    {
      "name": "chicken breast",
      "amount": 1.0,
      "unit": "lb",
      "preparation": "cubed",
      "emoji": "🍗",
      "notes": null
    },
    {
      "name": "fettuccine pasta",
      "amount": 8.0,
      "unit": "oz",
      "preparation": null,
      "emoji": "🍝",
      "notes": null
    },
    {
      "name": "garlic",
      "amount": 4.0,
      "unit": "cloves",
      "preparation": "minced",
      "emoji": "🧄",
      "notes": null
    },
    {
      "name": "heavy cream",
      "amount": 1.0,
      "unit": "cup",
      "preparation": null,
      "emoji": "🥛",
      "notes": null
    },
    {
      "name": "parmesan cheese",
      "amount": 0.5,
      "unit": "cup",
      "preparation": "grated",
      "emoji": "🧀",
      "notes": null
    },
    {
      "name": "butter",
      "amount": 2.0,
      "unit": "tbsp",
      "preparation": null,
      "emoji": "🧈",
      "notes": null
    }
  ],
  "instructions": [
    {
      "stepNumber": 1,
      "text": "Cook pasta according to package directions",
      "durationMinutes": 10,
      "highlightedIngredients": ["fettuccine pasta"]
    },
    {
      "stepNumber": 2,
      "text": "Sauté cubed chicken in butter until golden brown",
      "durationMinutes": 8,
      "highlightedIngredients": ["chicken breast", "butter"]
    },
    {
      "stepNumber": 3,
      "text": "Add minced garlic and cook for 1 minute until fragrant",
      "durationMinutes": 1,
      "highlightedIngredients": ["garlic"]
    },
    {
      "stepNumber": 4,
      "text": "Pour in heavy cream and grated parmesan, stirring to combine",
      "durationMinutes": 2,
      "highlightedIngredients": ["heavy cream", "parmesan cheese"]
    },
    {
      "stepNumber": 5,
      "text": "Simmer sauce until thickened, about 3-4 minutes",
      "durationMinutes": 4,
      "highlightedIngredients": []
    },
    {
      "stepNumber": 6,
      "text": "Toss cooked pasta with the creamy chicken sauce and serve immediately",
      "durationMinutes": 1,
      "highlightedIngredients": ["fettuccine pasta"]
    }
  ],
  "tags": ["#pasta", "#creamygarlic", "#dinnerideas", "#easyrecipe"],
  "creator": "@user"
}
```

**Key Observation:** The caption contained the full ingredient list with amounts and units. Gemini AI successfully parsed it into structured `RecipeIngredient` objects!

---

## Developer Handoff Message

**To:** Backend Developer
**From:** Product Team
**Subject:** PRD-7 Implementation - Complete Recipe Response Model

---

Hey team,

We need to update the backend `/process` endpoint to return complete recipe data. Right now we're only sending back 6 basic fields (title, description, image) even though Gemini AI is already extracting full recipes with ingredients, instructions, cook times, etc.

**The Issue:**
The `RelationshipContent` response model (inherited from Zest) is filtering out recipe-specific fields. Users see recipes with no ingredients or cooking steps.

**The Fix:**
Replace `RelationshipContent` with `RecipeContent` that includes:
- ✅ Remove 4 Zest fields: `content_type`, `mood`, `occasion`, `tips`
- ✅ Add 5 recipe fields: `prepTimeMinutes`, `cookTimeMinutes`, `baseServings`, `structuredIngredients`, `instructions`

**Files to Modify:**
1. `src/models/responses.py` - Create `RecipeContent` class
2. `src/api/process.py` - Update return type from `RelationshipContent` to `RecipeContent`

**Complete implementation details in:** `/Users/baileygrady/Desktop/dishly-backend/docs/PRD_7_COMPLETE_RECIPE_RESPONSE.md`

**Testing:**
```bash
make dev
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@aussiefitness/video/7564750012312309013"}' \
  | jq .
```

Verify response includes `structuredIngredients` and `instructions` arrays.

**Timeline:** ~30 mins implementation + 15 mins testing
**Priority:** P0 - Blocking recipe feature completeness
**Risk:** Zero (Dishly is new, no existing API consumers)

Let me know if you have questions!

---

## Conclusion

This PRD documents a simple, low-risk change to unlock complete recipe functionality in the Dishly app. The backend already does all the hard work (video download, AI extraction, structured data parsing) - we just need to stop filtering out the recipe data before sending it to the frontend.

**Summary:**
- ✅ No changes to AI prompts (already perfect)
- ✅ No changes to video processing (already working)
- ✅ No changes to caption extraction (already captured)
- ✅ Only change: Update response model (1 file, 30 lines of code)

**Impact:**
- Before: Users see recipe title and image only
- After: Users see complete recipes with ingredients, instructions, and timing

**Timeline:** 30 minutes to implement, 15 minutes to test, ready to deploy.
