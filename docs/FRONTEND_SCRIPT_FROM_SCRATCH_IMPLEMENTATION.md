# Frontend Implementation Guide: Script Generation From Scratch

> **For Frontend Developer** - Ready to integrate! Both endpoints are live.

**Last Updated:** December 2024  
**Status:** ✅ Implemented and Ready  
**Base URL:** Same as existing API endpoints

---

## Quick Start

Two new endpoints are available:

| Endpoint | Purpose | Avg Response Time |
|----------|---------|-------------------|
| `POST /generate-scripts-from-scratch` | Generate 3 scripts without vault template | 5-10 seconds |
| `POST /refine-beat` | Refine a single beat with a specific action | 0.5-2 seconds |

---

## Endpoint 1: Generate Scripts From Scratch

### `POST /generate-scripts-from-scratch`

Generate 3 meaningfully different script options. No vault template needed.

### Request

```typescript
interface GenerateScriptsFromScratchRequest {
  // Required fields
  topic: string;              // max 120 chars
  hook_style: HookStyle;      // see enum below
  cta_type: CTAType;          // see enum below
  tone: Tone;                 // see enum below
  format: VideoFormat;        // see enum below
  length_seconds: 30 | 45 | 60;
  reading_speed: "normal" | "fast";
  
  // Optional fields
  audience?: string;          // max 80 chars
  proof?: string;             // max 500 chars - personal credentials/results
  cta_keyword?: string;       // max 20 chars - REQUIRED if cta_type is "comment_keyword"
}
```

### Response

```typescript
interface GenerateScriptsFromScratchResponse {
  success: true;
  options: ScriptOption[];    // Exactly 3 options
  meta?: {
    generation_time_ms: number;
    model: string;
  };
}

interface ScriptOption {
  option_id: "opt_1" | "opt_2" | "opt_3";
  beats: {
    hook: string;           // Opening hook (3-5 seconds)
    context: string;        // Problem setup (10-15 seconds)
    value: string;          // Main content (20-35 seconds)
    cta: string;            // Call-to-action (5-10 seconds)
  };
  full_text: string;        // All beats joined with "\n\n"
  estimated_seconds: number;
  word_count: number;
  tags: {
    hook_style: string;
    tone: string;
    format: string;
  };
}
```

### Example Request

```json
{
  "topic": "How to get more views with better hooks",
  "audience": "new creators on TikTok",
  "hook_style": "question",
  "proof": "I posted daily for 90 days and doubled my views",
  "cta_type": "save_this",
  "tone": "casual",
  "format": "talking_to_camera",
  "length_seconds": 60,
  "reading_speed": "normal"
}
```

### Example Response

```json
{
  "success": true,
  "options": [
    {
      "option_id": "opt_1",
      "beats": {
        "hook": "Wait. You're losing views every single day because of this one mistake.",
        "context": "I see creators making this error constantly. They spend hours on their content but completely ignore the first 3 seconds.",
        "value": "Here's the fix: Your hook needs to create a pattern interrupt. Something unexpected. A bold claim. A question that makes them curious. I tested this for 90 days and my views doubled.",
        "cta": "Save this so you don't forget. And follow for more creator tips."
      },
      "full_text": "Wait. You're losing views every single day because of this one mistake.\n\nI see creators making this error constantly. They spend hours on their content but completely ignore the first 3 seconds.\n\nHere's the fix: Your hook needs to create a pattern interrupt. Something unexpected. A bold claim. A question that makes them curious. I tested this for 90 days and my views doubled.\n\nSave this so you don't forget. And follow for more creator tips.",
      "estimated_seconds": 42,
      "word_count": 89,
      "tags": {
        "hook_style": "question",
        "tone": "casual",
        "format": "talking_to_camera"
      }
    },
    {
      "option_id": "opt_2",
      "beats": {
        "hook": "The algorithm isn't broken. Your hooks are.",
        "context": "I know that sounds harsh but hear me out. Most creators blame the platform when their videos flop.",
        "value": "The first 3 seconds stop the scroll. Not your editing. Not your lighting. Your opening line. After posting daily for 90 days, the videos with pattern-interrupt hooks got 2x more views.",
        "cta": "Save this. Try it on your next video. Then come back and tell me if it worked."
      },
      "full_text": "...",
      "estimated_seconds": 38,
      "word_count": 78,
      "tags": {
        "hook_style": "hot_take",
        "tone": "confident",
        "format": "talking_to_camera"
      }
    },
    {
      "option_id": "opt_3",
      "beats": {
        "hook": "Can I be honest with you for a second?",
        "context": "Your content is probably better than 90% of what goes viral. But nobody's watching past the first 3 seconds.",
        "value": "The hook is everything. Not the value. Not the edit. The hook. I learned this after 90 days of posting daily.",
        "cta": "Save this for your next video. And follow if you want more tips like this."
      },
      "full_text": "...",
      "estimated_seconds": 35,
      "word_count": 72,
      "tags": {
        "hook_style": "storytime",
        "tone": "casual",
        "format": "talking_to_camera"
      }
    }
  ],
  "meta": {
    "generation_time_ms": 4521,
    "model": "gpt-4o"
  }
}
```

---

## Endpoint 2: Refine Beat

### `POST /refine-beat`

Refine a single beat with a specific action.

### Request

```typescript
interface RefineBeatRequest {
  beat_type: "hook" | "context" | "value" | "cta";
  current_text: string;
  action: RefineAction;       // see enum below
  context?: {                 // Optional - helps maintain consistency
    topic?: string;
    audience?: string;
    tone?: string;
  };
}
```

### Response

```typescript
interface RefineBeatResponse {
  success: true;
  refined_text: string;
  estimated_seconds: number;
  word_count: number;
  action_applied: string;
}
```

### Example Request

```json
{
  "beat_type": "hook",
  "current_text": "Here are some tips to help you grow on TikTok",
  "action": "punchier",
  "context": {
    "topic": "TikTok growth",
    "tone": "confident"
  }
}
```

### Example Response

```json
{
  "success": true,
  "refined_text": "You're killing your TikTok growth and you don't even know it.",
  "estimated_seconds": 4,
  "word_count": 12,
  "action_applied": "punchier"
}
```

---

## Enums Reference

### `hook_style`

```typescript
type HookStyle = 
  | "question"    // Opens with an intriguing question
  | "hot_take"    // Bold, potentially controversial statement
  | "storytime"   // Personal anecdote opener
  | "ranking"     // "Top 3...", "The #1 reason..."
  | "tutorial"    // "Here's how to...", instructional
  | "myth_bust";  // "Everyone thinks X but actually..."
```

### `cta_type`

```typescript
type CTAType = 
  | "follow_for_more"   // "Follow for more tips like this"
  | "save_this"         // "Save this for later"
  | "comment_keyword"   // "Comment [keyword] below" (requires cta_keyword)
  | "try_this_today"    // "Try this on your next video"
  | "download_app"      // "Link in bio to download"
  | "dm_me";            // "DM me for more details"
```

### `tone`

```typescript
type Tone = 
  | "casual"       // Friendly, conversational, relatable
  | "confident"    // Authoritative, assertive, bold
  | "funny"        // Humorous, lighthearted, playful
  | "calm"         // Relaxed, soothing, measured
  | "direct"       // No fluff, straight to the point
  | "educational"; // Informative, teacher-like
```

### `format`

```typescript
type VideoFormat = 
  | "talking_to_camera"  // Standard talking head
  | "voiceover"          // Voice over B-roll
  | "faceless_text";     // Text on screen
```

### `reading_speed`

```typescript
type ReadingSpeed = "normal" | "fast";
// normal = 150 words per minute
// fast = 175 words per minute
```

### Refine Actions by Beat Type

```typescript
// Hook actions
type HookAction = "punchier" | "more_curiosity" | "shorter" | "new_hook";

// Context actions  
type ContextAction = "shorter" | "clearer" | "add_one_line";

// Value actions
type ValueAction = "add_example" | "make_simpler" | "cut_fluff" | "add_pattern_interrupt";

// CTA actions
type CTAAction = "swap_cta" | "add_keyword_prompt" | "less_salesy";

// All actions combined
type RefineAction = HookAction | ContextAction | ValueAction | CTAAction;
```

### Action Descriptions

| Action | Description |
|--------|-------------|
| `punchier` | Make it more impactful, bold, attention-grabbing |
| `more_curiosity` | Add mystery, open loop, make viewer desperate to keep watching |
| `shorter` | Reduce word count while keeping the essence |
| `new_hook` | Generate a completely different hook angle |
| `clearer` | Simplify language, remove jargon |
| `add_one_line` | Add one more sentence of context/setup |
| `add_example` | Include a specific, relatable example |
| `make_simpler` | Break down complex ideas into simpler terms |
| `cut_fluff` | Remove filler words and unnecessary phrases |
| `add_pattern_interrupt` | Add something unexpected to re-engage viewer |
| `swap_cta` | Generate a different style of call-to-action |
| `add_keyword_prompt` | Add "Comment [keyword] below" style prompt |
| `less_salesy` | Make CTA feel more natural and less pushy |

---

## Error Handling

### Error Response Format

```typescript
interface ErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    field?: string;  // Present for validation errors
  };
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `MISSING_KEYWORD` | 400 | `cta_keyword` required when `cta_type` is `comment_keyword` |
| `GENERATION_FAILED` | 500 | AI generation failed |
| `RATE_LIMITED` | 429 | Too many requests |

### Example Error Response

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "length_seconds must be 30, 45, or 60",
    "field": "length_seconds"
  }
}
```

---

## TypeScript Types (Copy-Paste Ready)

```typescript
// ============= ENUMS =============

type HookStyle = "question" | "hot_take" | "storytime" | "ranking" | "tutorial" | "myth_bust";
type CTAType = "follow_for_more" | "save_this" | "comment_keyword" | "try_this_today" | "download_app" | "dm_me";
type Tone = "casual" | "confident" | "funny" | "calm" | "direct" | "educational";
type VideoFormat = "talking_to_camera" | "voiceover" | "faceless_text";
type ReadingSpeed = "normal" | "fast";
type BeatType = "hook" | "context" | "value" | "cta";
type RefineAction = 
  | "punchier" | "more_curiosity" | "shorter" | "new_hook"
  | "clearer" | "add_one_line"
  | "add_example" | "make_simpler" | "cut_fluff" | "add_pattern_interrupt"
  | "swap_cta" | "add_keyword_prompt" | "less_salesy";

// ============= REQUEST TYPES =============

interface GenerateScriptsFromScratchRequest {
  topic: string;
  hook_style: HookStyle;
  cta_type: CTAType;
  tone: Tone;
  format: VideoFormat;
  length_seconds: 30 | 45 | 60;
  reading_speed: ReadingSpeed;
  audience?: string;
  proof?: string;
  cta_keyword?: string;
}

interface RefineBeatRequest {
  beat_type: BeatType;
  current_text: string;
  action: RefineAction;
  context?: {
    topic?: string;
    audience?: string;
    tone?: string;
  };
}

// ============= RESPONSE TYPES =============

interface ScriptBeats {
  hook: string;
  context: string;
  value: string;
  cta: string;
}

interface ScriptOption {
  option_id: string;
  beats: ScriptBeats;
  full_text: string;
  estimated_seconds: number;
  word_count: number;
  tags: {
    hook_style: string;
    tone: string;
    format: string;
  };
}

interface GenerateScriptsFromScratchResponse {
  success: true;
  options: ScriptOption[];
  meta?: {
    generation_time_ms: number;
    model: string;
  };
}

interface RefineBeatResponse {
  success: true;
  refined_text: string;
  estimated_seconds: number;
  word_count: number;
  action_applied: string;
}

interface ScriptErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    field?: string;
  };
}
```

---

## React Integration Example

```typescript
import { useState } from 'react';

// API client
async function generateScriptsFromScratch(
  request: GenerateScriptsFromScratchRequest,
  appCheckToken?: string
): Promise<GenerateScriptsFromScratchResponse | ScriptErrorResponse> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (appCheckToken) {
    headers["X-Firebase-AppCheck"] = appCheckToken;
  }

  const response = await fetch("/generate-scripts-from-scratch", {
    method: "POST",
    headers,
    body: JSON.stringify(request),
  });

  return response.json();
}

async function refineBeat(
  request: RefineBeatRequest,
  appCheckToken?: string
): Promise<RefineBeatResponse | ScriptErrorResponse> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (appCheckToken) {
    headers["X-Firebase-AppCheck"] = appCheckToken;
  }

  const response = await fetch("/refine-beat", {
    method: "POST",
    headers,
    body: JSON.stringify(request),
  });

  return response.json();
}

// React hook example
function useScriptGeneration() {
  const [loading, setLoading] = useState(false);
  const [scripts, setScripts] = useState<ScriptOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generate = async (request: GenerateScriptsFromScratchRequest) => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await generateScriptsFromScratch(request);
      
      if (result.success) {
        setScripts(result.options);
      } else {
        setError(result.error.message);
      }
    } catch (err) {
      setError("Failed to generate scripts");
    } finally {
      setLoading(false);
    }
  };

  return { loading, scripts, error, generate };
}
```

---

## Key Behavior Notes

1. **3 Meaningfully Different Scripts**: Each option uses different angles, not just synonym swaps

2. **No Fake Claims**: If `proof` is empty/null, the AI uses general credibility language like "I've seen this work..." instead of inventing statistics

3. **Time Estimation**: Based on word count ÷ WPM × 60
   - Normal speed: 150 WPM
   - Fast speed: 175 WPM

4. **4-Beat Structure**: Every script has hook → context → value → cta (different from template endpoint's hook → body → call_to_action)

5. **cta_keyword Validation**: If `cta_type` is `"comment_keyword"`, you MUST provide `cta_keyword`

6. **App Check**: Optional but recommended - include token in `X-Firebase-AppCheck` header

---

## Comparison with Existing Endpoint

| Feature | `/generate-script` | `/generate-scripts-from-scratch` |
|---------|-------------------|----------------------------------|
| Template Required | Yes (vault) | No |
| Output Count | 1 + variations | 3 distinct scripts |
| Beat Structure | hook, body, cta | hook, context, value, cta |
| Customization | Limited | Full (tone, format, hook style, etc.) |
| Use Case | Template-based | Fresh script creation |

---

## Questions?

Reach out to the backend team for clarification.

