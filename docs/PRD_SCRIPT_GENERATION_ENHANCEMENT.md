# PRD: Script Generation Enhancement - Multi-Step Workflow

## Executive Summary

**Date**: 2025-01-27  
**Author**: Backend Team  
**Status**: In Progress  
**Priority**: P1 (High)  
**Platform**: Backend API

### One-Line Description
Enhance script generation with support for detailed topic descriptions to improve script quality without adding extra steps.

### User Value
Creators can provide rich topic context (like competitor example) directly in script generation, resulting in better scripts without adding complexity or extra API calls.

### Success Metrics (Option A - Simple Enhancement)
- 40% of users provide detailed topic_description within first month
- 25% improvement in script quality scores (user feedback)
- No increase in API response time
- 20% reduction in script regeneration requests

### Success Metrics (Option B - Research Step - Future)
- 60% of users use research generation before script generation
- 30% improvement in script quality scores (user feedback)
- Average research generation time < 15 seconds
- Research step reduces script regeneration requests by 25%

---

## Quick Example: Option A (Simple Enhancement)

### Input (Enhanced - with topic_description)
```json
POST /generate-script
{
  "template": "Stop doing [MISTAKE] if you want [GOAL]. Here's what works: [SOLUTION].",
  "topic": "Google Nano Banana Image model",
  "topic_description": "Make a video about Google releasing Nano Banana Image model. Specifically, I want to highlight how it works, a few interesting examples, and most importantly, why it will change the game for designers. Last, let's end the video with a super bold prediction.",
  "creator_role": "designer",
  "main_message": "This will change how designers work by enabling on-device AI generation without cloud dependency."
}
```

### Output (Same format, better quality)
```json
{
  "success": true,
  "script": {
    "hook": "Google just released Nano Banana Image model, and it's going to change everything for designers. Here's why...",
    "body": "Most designers rely on cloud-based AI image generation, which means you need internet, you wait for responses, and you're limited by API costs. Nano Banana runs entirely on your device - your phone, your tablet, even your laptop. I tested it during a client meeting and generated logo concepts in real-time while they watched. No cloud dependency, no waiting, no limits. This is the future of design work.",
    "call_to_action": "Try Nano Banana and let me know how it changes your workflow!"
  },
  "full_script": "...",
  "variations": [...],
  "estimated_duration": "30 seconds"
}
```

**Key Difference**: The script uses the detailed context from `topic_description` (how it works, examples, impact on designers, bold prediction) to generate a more specific, higher-quality script.

### Input (Backward Compatible - simple topic)
```json
POST /generate-script
{
  "template": "Stop doing [MISTAKE] if you want [GOAL]...",
  "topic": "classroom management",
  "creator_role": "school teacher",
  "main_message": "Stop trying to control every student behavior. Focus on building relationships."
}
```

**Works exactly as before** - no changes needed to existing frontend.

---

## Problem Statement

### Current User Experience

**Current Flow:**
1. User selects template from vault
2. User enters simple topic (e.g., "classroom management")
3. User enters creator role (e.g., "school teacher")
4. User enters main message
5. System generates script immediately

**Current Data Collection:**
- `template` (string) - From vault, madlib-style with [placeholders]
- `topic` (string) - Simple topic/subject (e.g., "classroom management")
- `creator_role` (string) - Who is creating (e.g., "school teacher")
- `main_message` (string) - Single text describing main message/goal
- Optional: `niche`, `style`, `length`

**Current API Endpoint:**
- `POST /generate-script` - Single endpoint, generates script immediately

### Pain Points

1. **Limited Topic Context**: Users provide only a simple topic string (e.g., "classroom management") without details about what they want to highlight, examples they want to include, or specific angles. This limits script quality.

2. **No Research Step**: Competitors generate research reports before script generation, helping users refine their ideas and providing AI with richer context. We skip this step entirely.

3. **Single-Step Workflow**: Everything happens in one API call. Users can't review or refine intermediate outputs (like research) before generating scripts.

4. **No Hook Selection**: Competitors allow users to pick from multiple hook options before script generation. We generate hooks as part of the script but don't offer pre-selection.

5. **Topic vs. Topic Description Gap**: Current `topic` field is too simple. Competitor example shows a detailed prompt: "Make a video about Google releasing Nano Banana Image model. Specifically, I want to highlight how it works, a few interesting examples, and most importantly, why it will change the game for designers. Last, let's end the video with a super bold prediction."

### User Quotes

> "I wish I could see research on my topic before generating the script - it would help me refine my ideas."

> "The competitor lets me describe my topic in detail, not just a single word. That would help."

### Impact

- **User Satisfaction**: Users comparing to competitors notice the missing research step
- **Script Quality**: Limited topic context results in generic scripts that need regeneration
- **Workflow Efficiency**: Users can't refine ideas before script generation, leading to multiple regeneration attempts

---

## Solution Overview

### Two Implementation Options

**RECOMMENDATION: Option A (Simple Enhancement) - Implement Now**
- No extra steps, no new endpoints
- Just add optional `topic_description` field
- Use richer context directly in script generation
- Fully backward compatible

**Option B (Research Step) - Keep for Future**
- Separate research generation endpoint
- Multi-step workflow
- More complex but matches competitor exactly

---

### Option A: Simple Enhancement (Recommended)

**Minimal Enhancement Approach (KISS Principle):**

1. **Enhance Existing Script Generation**
   - Add optional `topic_description` field to `GenerateScriptRequest`
   - If `topic_description` provided, use it in prompt instead of simple `topic`
   - No new endpoint, no extra step - just better input handling
   - Fully backward compatible - existing `topic` field still works

2. **Keep Existing Flow Intact**
   - `/generate-script` endpoint enhanced (not replaced)
   - Same single API call, same workflow
   - Users can provide simple `topic` OR detailed `topic_description`
   - Backward compatible - existing frontend continues to work

### Option B: Research Step (Future Enhancement)

**Multi-Step Approach:**

1. **Add Optional Research Generation Endpoint**
   - New endpoint: `POST /generate-research`
   - Takes detailed topic description (enhanced topic field)
   - Generates research report with key points, examples, angles
   - Optional step - users can skip and go directly to script generation

2. **Enhance Topic Collection**
   - Support both simple `topic` (backward compatible) and detailed `topic_description`
   - If `topic_description` provided, use it; otherwise fall back to `topic`
   - Allows users to provide rich context like competitor example

3. **Keep Existing Flow Intact**
   - `/generate-script` endpoint remains unchanged
   - Research is optional - users can still generate scripts directly
   - Backward compatible - existing frontend continues to work

### User Flow

**Option A: Simple Enhancement (No Extra Steps)**
1. User enters topic (simple) OR topic_description (detailed) - same form field
2. User selects template from vault
3. User enters creator role and main message
4. System generates script using richer context if topic_description provided
   - **No extra step, no extra API call, just better input handling**

**Option B: Enhanced Flow (with research) - FUTURE**
1. User enters detailed topic description (or simple topic)
2. User optionally clicks "Generate Research"
3. System generates research report with key points, examples, angles
4. User reviews research, refines topic description if needed
5. User selects template from vault
6. User enters creator role and main message
7. System generates script using research context

**Option C: Direct Flow (without research) - CURRENT**
1. User enters topic (simple)
2. User selects template from vault
3. User enters creator role and main message
4. System generates script (existing flow)

### Key Features

**Option A: Simple Enhancement (Recommended)**

1. **Enhanced Topic Support in Existing Endpoint**
   - Add optional `topic_description` field to `GenerateScriptRequest`
   - If `topic_description` provided, use it in prompt instead of `topic`
   - Backward compatible - existing `topic` field still works
   - No new endpoint, no extra step - just better input handling

**Option B: Research Step (Future Enhancement)**

1. **Research Generation Endpoint** (`POST /generate-research`)
   - Input: `topic_description` (detailed) or `topic` (simple), `creator_role`
   - Output: Research report with key points, examples, angles, predictions
   - Optional step - doesn't break existing workflow

2. **Enhanced Topic Support**
   - Accept both `topic` (simple string) and `topic_description` (detailed text)
   - Backward compatible - existing `topic` field still works
   - If `topic_description` provided, use it for richer context

3. **Research-Enhanced Script Generation**
   - `/generate-script` can optionally accept `research_id` or `research_data`
   - AI uses research context to generate better scripts
   - Falls back to existing behavior if no research provided

### Out of Scope

- Hook selection step (future enhancement)
- Multi-step UI workflow enforcement (frontend decision)
- Research storage/persistence (future enhancement)
- Research editing/refinement (future enhancement)

---

## Technical Requirements

### Architecture

**Layer**: API Layer (Backend)  
**Components**:
- New endpoint: `src/api/research.py`
- New service method: `src/services/openai_service.py` → `generate_research()`
- Enhanced request model: `src/models/requests.py` → `GenerateResearchRequest`
- Enhanced response model: `src/models/responses.py` → `ResearchReport`
- Optional enhancement: `GenerateScriptRequest` accepts `research_data`

### Data Models

**Option A: Simple Enhancement (Recommended)**

**Enhanced Script Request:**
```python
class GenerateScriptRequest(BaseModel):
    # Existing required fields
    template: str = Field(..., description="Madlib template with [placeholders]")
    topic: str = Field(..., description="User's topic/subject")
    creator_role: str = Field(..., description="Creator's role/identity")
    main_message: str = Field(..., description="Single text describing main message/goal")
    
    # NEW: Optional detailed topic description
    topic_description: Optional[str] = Field(
        None, 
        description="Detailed topic description with context, examples, angles. If provided, used instead of topic for richer context."
    )
    
    # Existing optional fields
    niche: Optional[str] = Field(None, description="Content niche")
    style: Optional[str] = Field("conversational", description="Script style")
    length: Optional[str] = Field("short", description="Target length")
    
    @field_validator("topic_description")
    @classmethod
    def validate_topic_description(cls, v):
        if v and len(v.strip()) < 10:
            raise ValueError("topic_description must be at least 10 characters")
        return v.strip() if v else None
    
    # Note: topic is still required for backward compatibility
    # If topic_description provided, it will be used in prompt instead
```

**Option B: Research Step (Future Enhancement)**

**New Request Model:**
```python
class GenerateResearchRequest(BaseModel):
    """Request model for research generation"""
    
    # Accept both simple topic and detailed description
    topic: Optional[str] = Field(None, description="Simple topic (backward compatible)")
    topic_description: Optional[str] = Field(None, description="Detailed topic description with context, examples, angles")
    creator_role: str = Field(..., description="Creator's role/identity")
    
    @field_validator("topic_description")
    @classmethod
    def validate_topic_description(cls, v):
        if v and len(v.strip()) < 10:
            raise ValueError("topic_description must be at least 10 characters")
        return v.strip() if v else None
    
    @model_validator(mode='after')
    def validate_topic_or_description(self):
        if not self.topic and not self.topic_description:
            raise ValueError("Either topic or topic_description must be provided")
        return self
```

**New Response Model:**
```python
class ResearchReport(BaseModel):
    """Research report response"""
    
    success: bool
    topic: str  # Normalized topic from input
    key_points: List[str]  # 3-5 key points about the topic
    examples: List[str]  # Specific examples or use cases
    angles: List[str]  # Different angles/perspectives to cover
    predictions: Optional[str] = None  # Bold predictions or future implications
    summary: str  # 2-3 sentence summary
    generated_at: datetime
```

**Enhanced Script Request (with research):**
```python
class GenerateScriptRequest(BaseModel):
    # ... existing fields ...
    
    # New optional field
    research_data: Optional[Dict[str, Any]] = Field(
        None, 
        description="Research report data to enhance script generation"
    )
```

### API Endpoints

**Option A: Simple Enhancement (Recommended)**

**Enhanced Existing Endpoint:**
```
POST /generate-script
```

**Request (with detailed topic_description):**
```json
{
  "template": "Stop doing [MISTAKE] if you want [GOAL]. Here's what works: [SOLUTION].",
  "topic": "Google Nano Banana Image model",
  "topic_description": "Make a video about Google releasing Nano Banana Image model. Specifically, I want to highlight how it works, a few interesting examples, and most importantly, why it will change the game for designers. Last, let's end the video with a super bold prediction.",
  "creator_role": "designer",
  "main_message": "This will change how designers work by enabling on-device AI generation without cloud dependency."
}
```

**Request (simple topic - backward compatible):**
```json
{
  "template": "Stop doing [MISTAKE] if you want [GOAL]...",
  "topic": "classroom management",
  "creator_role": "school teacher",
  "main_message": "Stop trying to control every student behavior. Focus on building relationships."
}
```

**Response (unchanged):**
```json
{
  "success": true,
  "script": {
    "hook": "...",
    "body": "...",
    "call_to_action": "..."
  },
  "full_script": "...",
  "variations": [...],
  "estimated_duration": "30 seconds"
}
```

**Option B: Research Step (Future Enhancement)**

**New Endpoint:**
```
POST /generate-research
```

**Request:**
```json
{
  "topic_description": "Make a video about Google releasing Nano Banana Image model. Specifically, I want to highlight how it works, a few interesting examples, and most importantly, why it will change the game for designers. Last, let's end the video with a super bold prediction.",
  "creator_role": "designer"
}
```

**Response:**
```json
{
  "success": true,
  "topic": "Google Nano Banana Image model",
  "key_points": [
    "Nano Banana is a new image generation model optimized for speed",
    "Designed specifically for designers and creative professionals",
    "Runs efficiently on mobile devices and edge computing"
  ],
  "examples": [
    "Real-time logo generation during client meetings",
    "On-the-fly mockup creation without cloud dependency",
    "Instant style transfer for design iterations"
  ],
  "angles": [
    "Technical: How it works and why it's faster",
    "Practical: Real-world use cases for designers",
    "Impact: Why this changes the design industry"
  ],
  "predictions": "Within 2 years, every designer will have AI image generation running locally on their devices, eliminating cloud dependency and enabling true creative freedom.",
  "summary": "Google's Nano Banana Image model represents a breakthrough in on-device AI image generation, specifically designed for designers. It enables real-time creative workflows without cloud dependency, fundamentally changing how designers work.",
  "generated_at": "2025-01-27T10:30:00Z"
}
```

**Enhanced Script Endpoint (with research):**
```
POST /generate-script
```

**Request (with research):**
```json
{
  "template": "Stop doing [MISTAKE] if you want [GOAL]...",
  "topic": "Google Nano Banana Image model",
  "topic_description": "Make a video about Google releasing Nano Banana Image model...",
  "creator_role": "designer",
  "main_message": "This will change how designers work by enabling on-device AI generation.",
  "research_data": {
    "key_points": [...],
    "examples": [...],
    "angles": [...]
  }
}
```

### Service Implementation

**Option A: Simple Enhancement (Recommended)**

**Enhanced Script Generation Method:**
```python
async def generate_script(
    self,
    template: str,
    topic: str,
    creator_role: str,
    main_message: str,
    topic_description: Optional[str] = None,  # NEW: Optional detailed description
    niche: Optional[str] = None,
    style: str = "conversational",
    length: str = "short",
) -> Optional[Dict[str, Any]]:
    """
    Generate a script from a template using creator role and main message.
    
    If topic_description provided, use it instead of topic for richer context.
    """
    # Use topic_description if provided, otherwise use topic
    topic_context = topic_description if topic_description else topic
    
    # Build prompt using topic_context (richer if topic_description provided)
    prompt = f"""...
TOPIC: "{topic_context}"
...
"""
```

**Option B: Research Step (Future Enhancement)**

**New Service Method:**
```python
async def generate_research(
    self,
    topic: Optional[str] = None,
    topic_description: Optional[str] = None,
    creator_role: str,
) -> Optional[Dict[str, Any]]:
    """
    Generate research report from topic description.
    
    Uses topic_description if provided, otherwise topic.
    Generates key points, examples, angles, and predictions.
    """
```

**Enhanced Script Generation:**
- If `research_data` provided, include it in prompt context
- Use research key points and examples to enrich script
- Maintain backward compatibility if no research provided

### Performance Requirements

- Research generation: < 15 seconds (95th percentile)
- Script generation with research: < 20 seconds (95th percentile)
- API response time: < 2 seconds (excluding AI processing)
- No impact on existing `/generate-script` performance

### Backward Compatibility

**Critical Requirements:**
- Existing `/generate-script` endpoint must continue working unchanged
- Existing request format (with simple `topic`) must still work
- No breaking changes to existing response format
- Frontend can adopt new features incrementally

---

## Implementation Plan

### RECOMMENDED: Option A - Simple Enhancement (No Extra Steps)

**Phase 1: Enhanced Topic Description Support (3-4 days)**

**Day 1: Request Model Enhancement**
- [ ] Add optional `topic_description` field to `GenerateScriptRequest`
- [ ] Add validation for `topic_description` (min 10 characters)
- [ ] Ensure backward compatibility - `topic` still required

**Day 2: Service Enhancement**
- [ ] Update `OpenAIService.generate_script()` to accept `topic_description` parameter
- [ ] Modify prompt to use `topic_description` if provided, otherwise `topic`
- [ ] Test with both simple topic and detailed topic_description

**Day 3: API Endpoint Update**
- [ ] Update `src/api/script.py` to pass `topic_description` to service
- [ ] Ensure existing requests without `topic_description` still work
- [ ] Add logging for topic_description usage

**Day 4: Testing & Documentation**
- [ ] Unit tests for topic_description validation
- [ ] Integration tests with topic_description
- [ ] Test backward compatibility
- [ ] Update API documentation

### FUTURE: Option B - Research Step (Keep for Later)

**Phase 1: Research Generation Endpoint (Week 1)

**Day 1-2: Models and Service**
- [ ] Create `GenerateResearchRequest` model
- [ ] Create `ResearchReport` response model
- [ ] Add `generate_research()` method to `OpenAIService`
- [ ] Write prompt template for research generation

**Day 3-4: API Endpoint**
- [ ] Create `src/api/research.py` router
- [ ] Implement `POST /generate-research` endpoint
- [ ] Add error handling and validation
- [ ] Add logging and monitoring

**Day 5: Testing**
- [ ] Unit tests for request validation
- [ ] Integration tests for research generation
- [ ] Test backward compatibility
- [ ] Test with both `topic` and `topic_description`

### Phase 2: Enhanced Topic Support (Week 2)

**Day 1-2: Request Model Enhancement**
- [ ] Add `topic_description` field to `GenerateScriptRequest` (optional)
- [ ] Update validation logic to accept either `topic` or `topic_description`
- [ ] Update `OpenAIService.generate_script()` to use `topic_description` if provided

**Day 3-4: Script Generation Enhancement**
- [ ] Add `research_data` optional field to `GenerateScriptRequest`
- [ ] Update script generation prompt to include research context
- [ ] Test script generation with and without research

**Day 5: Testing & Documentation**
- [ ] Test all combinations (topic only, topic_description only, with research, without research)
- [ ] Update API documentation
- [ ] Update `FRONTEND_SCRIPT_GENERATION_API.md`

### Phase 3: Polish & Optimization (Week 3)

**Day 1-2: Performance**
- [ ] Optimize research generation prompt
- [ ] Add caching considerations (future enhancement)
- [ ] Monitor response times

**Day 3-4: Error Handling**
- [ ] Enhanced error messages
- [ ] Retry logic for research generation
- [ ] Graceful degradation if research fails

**Day 5: Documentation**
- [ ] Update PRD with learnings
- [ ] Create migration guide for frontend
- [ ] Document research prompt engineering

### File Changes

**New Files:**
- `src/api/research.py` - Research generation endpoint
- `tests/test_api/test_research.py` - Research endpoint tests

**Modified Files:**
- `src/models/requests.py` - Add `GenerateResearchRequest`, enhance `GenerateScriptRequest`
- `src/models/responses.py` - Add `ResearchReport` model
- `src/services/openai_service.py` - Add `generate_research()` method, enhance `generate_script()`
- `src/api/__init__.py` - Export research router
- `main.py` - Include research router
- `docs/FRONTEND_SCRIPT_GENERATION_API.md` - Document new endpoint

### Dependencies

- **OpenAI API**: Already integrated, no new dependencies
- **Frontend Changes**: Optional - frontend can adopt incrementally
- **Database**: None required (research not persisted initially)

### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Research generation slow (>20s) | Medium | High | Optimize prompt, add timeout, show progress indicator |
| Backward compatibility broken | Low | High | Comprehensive testing, feature flags |
| Research quality poor | Medium | Medium | Iterate on prompt, collect user feedback |
| Frontend adoption slow | Low | Low | Research is optional, existing flow unchanged |

---

## Dependencies & Impacts

### System Dependencies

**No Breaking Changes:**
- Existing `/generate-script` endpoint unchanged
- Existing request/response models unchanged
- No database changes required
- No authentication changes required

**New Dependencies:**
- None - uses existing OpenAI service
- No new external APIs
- No new infrastructure requirements

### Impact on Other Systems

**Frontend:**
- **Optional Enhancement**: Frontend can adopt research generation incrementally
- **Backward Compatible**: Existing script generation flow continues to work
- **New UI Opportunity**: Can add "Generate Research" button before script generation

**Backend:**
- **Minimal Impact**: New endpoint, no changes to existing endpoints
- **Service Layer**: Extends `OpenAIService`, doesn't modify existing methods
- **Monitoring**: Add metrics for research generation endpoint

**API Consumers:**
- **No Breaking Changes**: Existing API consumers continue to work
- **Progressive Enhancement**: Can adopt research feature when ready

---

## Open Questions & Missing Information

### Open Questions

1. **Research Persistence**: Should research reports be stored in database for future reference, or generated on-demand each time?
   - **Recommendation**: Start with on-demand, add persistence later if users request it

2. **Research Caching**: Should we cache research reports for similar topics to reduce API costs?
   - **Recommendation**: Not in initial implementation, add if cost becomes issue

3. **Research Editing**: Should users be able to edit research reports before using them for script generation?
   - **Recommendation**: Out of scope for initial implementation, future enhancement

4. **Hook Selection Step**: Should we add a hook selection step like the competitor (pick favorite hook before script generation)?
   - **Recommendation**: Future enhancement, not in scope for this PRD

5. **Topic Description Length**: What's the maximum length for `topic_description`?
   - **Recommendation**: 2000 characters (similar to main_message)

6. **Research Quality Metrics**: How do we measure research quality?
   - **Recommendation**: User feedback, script quality improvement, reduction in regeneration requests

### Missing Information

1. **User Research**: Do users actually want research generation, or is this feature parity only?
   - **Action**: Collect user feedback after implementation

2. **Competitor Analysis**: What exactly does competitor research report contain?
   - **Action**: Analyze competitor example more deeply, iterate on prompt

3. **Cost Analysis**: What's the additional OpenAI API cost for research generation?
   - **Action**: Monitor costs after implementation, optimize if needed

4. **Usage Patterns**: Will users always use research, or only for complex topics?
   - **Action**: Track usage patterns, optimize UX based on data

---

## Success Criteria

### Technical Success

- [ ] Research generation endpoint responds in < 15 seconds (95th percentile)
- [ ] Backward compatibility maintained - existing endpoints work unchanged
- [ ] No increase in error rates
- [ ] Research quality validated through testing

### Product Success

- [ ] 60% of users try research generation within first month
- [ ] 30% improvement in script quality scores (user feedback)
- [ ] 25% reduction in script regeneration requests
- [ ] Positive user feedback on research feature

### Implementation Success

- [ ] All tests passing
- [ ] Documentation updated
- [ ] No breaking changes
- [ ] Code review approved
- [ ] Deployed to production

---

## Future Enhancements

### Phase 2: Research Persistence
- Store research reports in database
- Allow users to view past research
- Reuse research for multiple scripts

### Phase 3: Hook Selection
- Generate multiple hook options
- Allow users to select favorite hook
- Use selected hook in script generation

### Phase 4: Research Editing
- Allow users to edit research reports
- Add/remove key points
- Refine examples and angles

### Phase 5: Research Templates
- Pre-defined research templates by niche
- Customizable research structure
- Research quality scoring

---

## Appendix

### Current API Flow

```
User → POST /generate-script
  ├─ template (from vault)
  ├─ topic (simple string)
  ├─ creator_role
  ├─ main_message
  └─ Optional: niche, style, length

Response → GeneratedScript
  ├─ script (hook, body, cta)
  ├─ full_script
  ├─ variations
  └─ estimated_duration
```

### Proposed Enhanced Flow

```
User → POST /generate-research (optional)
  ├─ topic_description (detailed) OR topic (simple)
  └─ creator_role

Response → ResearchReport
  ├─ key_points
  ├─ examples
  ├─ angles
  └─ predictions

User → POST /generate-script
  ├─ template (from vault)
  ├─ topic OR topic_description
  ├─ creator_role
  ├─ main_message
  └─ Optional: research_data

Response → GeneratedScript (enhanced with research context)
```

### Competitor Analysis

**Competitor Flow:**
1. "Describe your topic" - Detailed prompt with context, examples, angles
2. "Review the research" - AI-generated research report
3. "Pick your favorite hook" - Hook selection from options
4. Script generation (presumably)

**Key Differences:**
- Competitor collects detailed topic description upfront
- Competitor generates research as separate step
- Competitor allows hook selection before script generation
- Competitor uses multi-step workflow

**Our Approach:**
- Make research optional (KISS principle)
- Support both simple and detailed topics (backward compatible)
- Keep existing script generation flow intact
- Add research as enhancement, not requirement

---

**Last Updated**: 2025-01-27  
**Status**: In Progress  
**Next Steps**: Review with team, gather feedback, begin Option A implementation

---

## Summary & Recommendation

### Option A: Simple Enhancement (RECOMMENDED)

**What it does:**
- Adds optional `topic_description` field to existing `/generate-script` endpoint
- Uses richer context directly in script generation
- No new endpoints, no extra steps, no complexity

**Implementation:**
- 3-4 days of work
- Minimal code changes
- Fully backward compatible

**Benefits:**
- Better scripts without adding complexity
- Users can provide detailed context like competitor
- No workflow changes needed
- Can always add research step later if needed

### Option B: Research Step (FUTURE)

**What it does:**
- Adds new `/generate-research` endpoint
- Multi-step workflow (research → script)
- Matches competitor exactly

**Implementation:**
- 2-3 weeks of work
- New endpoint, new models, new UI flow
- More complex but more powerful

**Benefits:**
- Users can review research before script generation
- More control over script quality
- Matches competitor feature set

**Recommendation:** Start with Option A. It solves 80% of the problem with 20% of the complexity. Keep Option B in the backlog for future enhancement if users request it or if we want to match competitor exactly.

