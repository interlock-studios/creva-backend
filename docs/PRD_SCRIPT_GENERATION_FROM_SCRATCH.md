# PRD: AI Script Generation From Scratch

## Executive Summary

**Date**: 2024-12-23  
**Author**: Backend Team  
**Status**: Draft  
**Priority**: P1 (High)  
**Platform**: Backend API

### One-Line Description

Two new API endpoints enabling AI-powered script generation without requiring vault templates, plus beat-level refinement.

### User Value

Creators can generate complete scripts from scratch by describing their topic, audience, and style preferences - no template required. They can then refine individual beats (hook, context, value, CTA) with specific actions like "make it punchier" or "add more curiosity."

### Success Metrics

- 70% of users who try script-from-scratch generate at least one usable script
- Average generation time < 10 seconds for 3 script options
- Beat refinement response time < 2 seconds
- 50% reduction in script regeneration requests vs template-based flow

---

## Problem Statement

### Current User Experience

The existing `/generate-script` endpoint requires a vault template as input:

```
User selects template from vault → Fills in topic/role/message → Gets script
```

This works well for users who have saved templates, but creates friction for:
1. New users with empty vaults
2. Users who want to explore ideas without committing to a template structure
3. Users who want more control over individual script sections

### Pain Points

1. **Template Dependency**: Cannot generate scripts without first having a saved template
2. **No Beat-Level Control**: Users must regenerate entire scripts when only one section needs adjustment
3. **Limited Customization**: Current endpoint doesn't expose hook style, CTA type, or tone as explicit choices

### Impact

- Frontend team blocked from building "generate from scratch" feature
- Users comparing to competitors notice missing functionality
- Increased support requests for "how to generate without a template"

---

## Solution Overview

### Proposed Solution

Add two new endpoints that work independently from the existing template-based flow:

| Endpoint | Purpose | Response Time |
|----------|---------|---------------|
| `POST /generate-scripts-from-scratch` | Generate 3 complete scripts from user inputs | 5-10 seconds |
| `POST /refine-beat` | Refine a single beat with a specific action | 0.5-2 seconds |

### Key Principles

1. **4-Beat Structure**: Scripts follow Hook → Context → Value → CTA format
2. **Time-Aware Generation**: All scripts fit target duration (30/45/60 seconds)
3. **No Fake Claims**: If user provides no proof, use general credibility language
4. **Spoken Language Style**: Short punchy sentences, conversational tone

### User Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Generate Scripts From Scratch                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User fills form:                                            │
│     - Topic: "How to get more views with better hooks"          │
│     - Audience: "new creators on TikTok"                        │
│     - Hook Style: [Question ▼]                                  │
│     - Tone: [Casual ▼]                                          │
│     - Length: [60 seconds ▼]                                    │
│     - Proof (optional): "I posted daily for 90 days..."         │
│                                                                 │
│  2. User clicks "Generate Scripts"                              │
│                                                                 │
│  3. System returns 3 meaningfully different options             │
│                                                                 │
│  4. User selects one, can refine individual beats:              │
│     [Hook: Make Punchier] [Context: Shorter] [CTA: Less Salesy] │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Out of Scope

- Modifying existing `/generate-script` endpoint (remains unchanged)
- Script persistence/storage (frontend handles)
- Per-endpoint rate limiting (use existing global limits for v1)
- Response caching (low cache hit rate expected due to personalization)

---

## Technical Requirements

### Architecture

**Layer**: API Layer  
**Pattern**: New router + extended models + service methods

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                               │
│                    (include new router)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              src/api/script_from_scratch.py                  │
│                      (NEW - ~150 lines)                      │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │ /generate-scripts-  │  │ /refine-beat                │   │
│  │ from-scratch        │  │                             │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              src/services/openai_service.py                  │
│                    (EXTEND - +150 lines)                     │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │ generate_scripts_   │  │ refine_beat()               │   │
│  │ from_scratch()      │  │                             │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Data Models

#### New Request Models (add to `src/models/requests.py`)

```python
from enum import Enum

class HookStyle(str, Enum):
    QUESTION = "question"
    HOT_TAKE = "hot_take"
    STORYTIME = "storytime"
    RANKING = "ranking"
    TUTORIAL = "tutorial"
    MYTH_BUST = "myth_bust"

class CTAType(str, Enum):
    FOLLOW_FOR_MORE = "follow_for_more"
    SAVE_THIS = "save_this"
    COMMENT_KEYWORD = "comment_keyword"
    TRY_THIS_TODAY = "try_this_today"
    DOWNLOAD_APP = "download_app"
    DM_ME = "dm_me"

class Tone(str, Enum):
    CASUAL = "casual"
    CONFIDENT = "confident"
    FUNNY = "funny"
    CALM = "calm"
    DIRECT = "direct"
    EDUCATIONAL = "educational"

class VideoFormat(str, Enum):
    TALKING_TO_CAMERA = "talking_to_camera"
    VOICEOVER = "voiceover"
    FACELESS_TEXT = "faceless_text"

class ReadingSpeed(str, Enum):
    NORMAL = "normal"  # 150 wpm
    FAST = "fast"      # 175 wpm

class BeatType(str, Enum):
    HOOK = "hook"
    CONTEXT = "context"
    VALUE = "value"
    CTA = "cta"

class RefineAction(str, Enum):
    # Hook actions
    PUNCHIER = "punchier"
    MORE_CURIOSITY = "more_curiosity"
    SHORTER = "shorter"
    NEW_HOOK = "new_hook"
    # Context actions
    CLEARER = "clearer"
    ADD_ONE_LINE = "add_one_line"
    # Value actions
    ADD_EXAMPLE = "add_example"
    MAKE_SIMPLER = "make_simpler"
    CUT_FLUFF = "cut_fluff"
    ADD_PATTERN_INTERRUPT = "add_pattern_interrupt"
    # CTA actions
    SWAP_CTA = "swap_cta"
    ADD_KEYWORD_PROMPT = "add_keyword_prompt"
    LESS_SALESY = "less_salesy"


class GenerateScriptsFromScratchRequest(BaseModel):
    """Request for generating scripts from scratch (no template)"""
    
    topic: str = Field(..., max_length=120, description="Main topic/subject")
    audience: Optional[str] = Field(None, max_length=80, description="Target audience")
    hook_style: HookStyle = Field(..., description="Style of opening hook")
    proof: Optional[str] = Field(None, max_length=500, description="Personal proof/credentials")
    cta_type: CTAType = Field(..., description="Type of call-to-action")
    cta_keyword: Optional[str] = Field(None, max_length=20, description="Keyword for comment_keyword CTA")
    tone: Tone = Field(..., description="Voice/tone of script")
    format: VideoFormat = Field(..., description="Video production format")
    length_seconds: int = Field(..., description="Target length: 30, 45, or 60")
    reading_speed: ReadingSpeed = Field(..., description="Reading pace")

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v):
        if not v or not v.strip():
            raise ValueError("topic must be non-empty")
        return v.strip()

    @field_validator("length_seconds")
    @classmethod
    def validate_length(cls, v):
        if v not in [30, 45, 60]:
            raise ValueError("length_seconds must be 30, 45, or 60")
        return v

    @model_validator(mode='after')
    def validate_cta_keyword(self):
        if self.cta_type == CTAType.COMMENT_KEYWORD and not self.cta_keyword:
            raise ValueError("cta_keyword required when cta_type is comment_keyword")
        return self


class RefineBeatRequest(BaseModel):
    """Request for refining a single beat"""
    
    beat_type: BeatType = Field(..., description="Which beat to refine")
    current_text: str = Field(..., description="Current text of the beat")
    action: RefineAction = Field(..., description="Refinement action to apply")
    context: Optional[Dict[str, str]] = Field(None, description="Optional context")

    @field_validator("current_text")
    @classmethod
    def validate_current_text(cls, v):
        if not v or not v.strip():
            raise ValueError("current_text must be non-empty")
        return v.strip()
```

#### New Response Models (add to `src/models/responses.py`)

```python
class ScriptBeats(BaseModel):
    """4-beat script structure"""
    hook: str = Field(..., description="Opening hook (3-5 seconds)")
    context: str = Field(..., description="Problem setup (10-15 seconds)")
    value: str = Field(..., description="Main content (20-35 seconds)")
    cta: str = Field(..., description="Call-to-action (5-10 seconds)")


class ScriptOption(BaseModel):
    """Single script option with metadata"""
    option_id: str = Field(..., description="Unique identifier (opt_1, opt_2, opt_3)")
    beats: ScriptBeats = Field(..., description="The 4 beats")
    full_text: str = Field(..., description="Complete script joined with newlines")
    estimated_seconds: int = Field(..., description="Estimated speaking time")
    word_count: int = Field(..., description="Total word count")
    tags: Dict[str, str] = Field(..., description="Style metadata")


class GenerateScriptsFromScratchResponse(BaseModel):
    """Response with 3 script options"""
    success: bool = Field(True)
    options: List[ScriptOption] = Field(..., min_length=3, max_length=3)
    meta: Optional[Dict[str, Any]] = Field(None, description="Generation metadata")


class RefineBeatResponse(BaseModel):
    """Response for beat refinement"""
    success: bool = Field(True)
    refined_text: str = Field(..., description="Refined beat text")
    estimated_seconds: int = Field(..., description="Estimated speaking time")
    word_count: int = Field(..., description="Word count")
    action_applied: str = Field(..., description="Action that was applied")
```

### API Endpoints

#### `POST /generate-scripts-from-scratch`

**Request:**
```json
{
  "topic": "How to get more views with better hooks",
  "audience": "new creators on TikTok",
  "hook_style": "question",
  "proof": "I posted daily for 90 days and doubled my views",
  "cta_type": "save_this",
  "cta_keyword": null,
  "tone": "casual",
  "format": "talking_to_camera",
  "length_seconds": 60,
  "reading_speed": "normal"
}
```

**Response:**
```json
{
  "success": true,
  "options": [
    {
      "option_id": "opt_1",
      "beats": {
        "hook": "Wait. You're losing views every single day because of this one mistake.",
        "context": "I see creators making this error constantly...",
        "value": "Here's the fix: Your hook needs to create a pattern interrupt...",
        "cta": "Save this so you don't forget. And follow for more creator tips."
      },
      "full_text": "Wait. You're losing views...",
      "estimated_seconds": 42,
      "word_count": 89,
      "tags": {"hook_style": "question", "tone": "casual", "format": "talking_to_camera"}
    },
    // ... 2 more options
  ],
  "meta": {"generation_time_ms": 4521, "model": "gpt-4o"}
}
```

#### `POST /refine-beat`

**Request:**
```json
{
  "beat_type": "hook",
  "current_text": "Stop scrolling if you want more views",
  "action": "punchier",
  "context": {"topic": "TikTok growth", "tone": "confident"}
}
```

**Response:**
```json
{
  "success": true,
  "refined_text": "You're killing your TikTok growth and you don't even know it.",
  "estimated_seconds": 4,
  "word_count": 12,
  "action_applied": "punchier"
}
```

### Time Estimation Formula

```python
def estimate_seconds(word_count: int, reading_speed: str) -> int:
    """Calculate speaking time based on word count and reading speed."""
    wpm = 175 if reading_speed == "fast" else 150  # words per minute
    return round(word_count / wpm * 60)
```

### Error Handling

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `MISSING_KEYWORD` | 400 | `cta_keyword` required when `cta_type` is `comment_keyword` |
| `GENERATION_FAILED` | 500 | AI generation failed |
| `RATE_LIMITED` | 429 | Too many requests |

**Error Response Format:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Topic is required and cannot be empty",
    "field": "topic"
  }
}
```

---

## Implementation Plan

### Phase 1: Models & Enums (Day 1)

- [ ] Add enums to `src/models/requests.py` (HookStyle, CTAType, Tone, etc.)
- [ ] Add `GenerateScriptsFromScratchRequest` model with validation
- [ ] Add `RefineBeatRequest` model with validation
- [ ] Add response models to `src/models/responses.py`

### Phase 2: Service Methods (Day 2)

- [ ] Add `generate_scripts_from_scratch()` method to `OpenAIService`
- [ ] Add `refine_beat()` method to `OpenAIService`
- [ ] Add time estimation helper function
- [ ] Write prompts for both generation types

### Phase 3: API Endpoints (Day 3)

- [ ] Create `src/api/script_from_scratch.py` router
- [ ] Implement `POST /generate-scripts-from-scratch` endpoint
- [ ] Implement `POST /refine-beat` endpoint
- [ ] Add error handling
- [ ] Export router in `src/api/__init__.py`
- [ ] Include router in `main.py`

### Phase 4: Testing (Day 4)

- [ ] Unit tests for request validation
- [ ] Unit tests for time estimation
- [ ] Integration tests for both endpoints
- [ ] Test error scenarios
- [ ] Test with various topic/style combinations

### Phase 5: Documentation (Day 5)

- [ ] Update `FRONTEND_SCRIPT_GENERATION_API.md` with new endpoints
- [ ] Add endpoint examples
- [ ] Document enum values

### File Changes Summary

| File | Change | Est. Lines |
|------|--------|------------|
| `src/models/requests.py` | Add enums + 2 request models | +80 |
| `src/models/responses.py` | Add 4 response models | +50 |
| `src/services/openai_service.py` | Add 2 methods + helper | +150 |
| `src/api/script_from_scratch.py` | New router file | ~150 |
| `src/api/__init__.py` | Export new router | +2 |
| `main.py` | Include new router | +2 |
| `tests/test_api/test_script_from_scratch.py` | New test file | ~200 |

**All files remain under 500 lines per project rules.**

---

## Dependencies & Impacts

### System Dependencies

**No Breaking Changes:**
- Existing `/generate-script` endpoint unchanged
- Existing request/response models unchanged
- No database changes required
- No authentication changes required

**Uses Existing Infrastructure:**
- OpenAI service (already integrated)
- App Check middleware (optional token support)
- Global rate limiting (via SecurityMiddleware)
- Structured logging (with endpoint tags)

### Impact on Other Systems

**Frontend:**
- Unblocks "generate from scratch" feature development
- New endpoints integrate with existing App Check token flow
- Same error response format as existing endpoints

**Backend:**
- New router added alongside existing script router
- OpenAI service extended with 2 new methods
- No changes to existing endpoints

---

## Testing Strategy

### Unit Tests

- [ ] Enum validation (all valid values accepted, invalid rejected)
- [ ] Request validation (required fields, conditional cta_keyword)
- [ ] Time estimation calculation (normal vs fast speed)
- [ ] Response model serialization

### Integration Tests

- [ ] Generate scripts with all hook styles
- [ ] Generate scripts with all CTA types
- [ ] Refine beats with all action types
- [ ] Test without proof (general credibility language)
- [ ] Test with comment_keyword CTA (requires cta_keyword)

### Manual Testing Checklist

- [ ] Generate 3 meaningfully different scripts (not just synonym swaps)
- [ ] Verify estimated_seconds matches word count / WPM formula
- [ ] Verify no fake claims when proof is empty
- [ ] Test beat refinement preserves overall meaning
- [ ] Verify rate limiting works under load

---

## Decisions Made

1. **Rate Limiting**: Use existing global rate limiting for v1 (simpler)
2. **Caching**: Skip caching for v1 (low cache hit rate expected)
3. **Metrics**: Reuse existing logging with endpoint-specific tags

---

## Future Enhancements

### Phase 2 (If Needed)
- Per-endpoint rate limits matching frontend spec
- Response caching for common combinations
- Separate metrics dashboard for from-scratch generation

### Phase 3 (Backlog)
- A/B testing different prompt strategies
- User feedback integration for quality scoring
- Batch generation for multiple topics

---

**Last Updated**: 2024-12-23  
**Status**: Draft  
**Next Steps**: Review with team, begin Phase 1 implementation

