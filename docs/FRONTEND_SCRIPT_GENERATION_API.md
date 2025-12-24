# Frontend Integration Guide: Script Generation & Hook Analysis

## Overview

This document provides complete API documentation for the new script generation endpoint and hook analysis feature. These features allow users to:
1. **Analyze hooks** from processed videos to understand why they work
2. **Generate scripts** from templates and topics for creating new content

---

## Table of Contents

1. [Hook Analysis](#hook-analysis)
2. [Script Generation Endpoint](#script-generation-endpoint) (template-based)
3. [Script Generation From Scratch](#script-generation-from-scratch) (NEW)
4. [Refine Beat Endpoint](#refine-beat-endpoint) (NEW)
5. [Request/Response Models](#requestresponse-models)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Integration Examples](#integration-examples)

---

## Hook Analysis

### Overview

When a video is processed via the `/process` endpoint, if a hook is detected, the response now includes an optional `analysis` field that explains why the hook works psychologically.

### Response Structure

The `CreatorContent` response model now includes:

```typescript
interface CreatorContent {
  // ... existing fields ...
  analysis: HookAnalysis | null;
}
```

### HookAnalysis Model

```typescript
interface HookAnalysis {
  hook_formula: string;           // Machine-readable formula type
  hook_formula_name: string;      // Human-readable formula name
  explanation: string;             // 2-3 sentence explanation
  why_it_works: string[];         // Array of psychological trigger bullet points
  replicable_pattern: string;      // Template with [placeholders] for reuse
}
```

### Hook Formula Types

The `hook_formula` field will be one of:
- `curiosity_gap`
- `controversy`
- `transformation`
- `list`
- `story`
- `question`
- `challenge`
- `secret`
- `comparison`
- `myth_busting`

### Important Notes

#### When Analysis is Available

- **New Videos Only**: Analysis is only generated for newly processed videos. If a video was previously processed and cached, `analysis` will be `null`.
- **Requires Hook**: Analysis is only generated if the video has a detected hook. If `hook` is `null` or empty, `analysis` will be `null`.
- **Automatic Inclusion**: Analysis is automatically included in the `/process` endpoint response - no additional API call needed.

#### When Analysis is `null`

The `analysis` field will be `null` in these scenarios:

1. **Cached Results**: Video was previously processed and served from cache
   ```json
   {
     "hook": "Some hook text",
     "analysis": null,
     "cached": true
   }
   ```

2. **No Hook Detected**: Video doesn't have a hook
   ```json
   {
     "hook": null,
     "analysis": null,
     "cached": false
   }
   ```

3. **Analysis Failed**: Hook exists but analysis generation failed (silently fails, no error thrown)
   ```json
   {
     "hook": "Some hook text",
     "analysis": null,
     "cached": false
   }
   ```

#### Getting Analysis for Cached Videos

If you need analysis for a cached video:
1. Invalidate the cache using `/admin/invalidate-cache` endpoint (if available)
2. Reprocess the video via `/process` endpoint
3. Analysis will be generated on the new processing

#### Frontend Handling

**Always check for `analysis` before displaying:**
```typescript
if (content.analysis) {
  // Display hook analysis UI
  showHookAnalysis(content.analysis);
} else {
  // Show message or hide analysis section
  if (content.cached) {
    showMessage("Analysis not available for cached videos");
  } else if (!content.hook) {
    showMessage("No hook detected in this video");
  } else {
    showMessage("Analysis unavailable");
  }
}
```

**The `analysis` field is always optional/nullable** - never assume it will be present, even for newly processed videos.

#### Using Analysis with Script Generation

The `replicable_pattern` field from hook analysis is designed to be used as a `template` in the script generation endpoint:

```typescript
// 1. Process video and get analysis
const content = await processVideo(videoUrl);

if (content.analysis?.replicable_pattern) {
  // 2. Use the replicable pattern as a template
  const script = await generateScript({
    template: content.analysis.replicable_pattern,
    topic: "classroom management",
    creator_role: "school teacher",
    main_message: "Focus on building relationships, not controlling behavior",
  });
  
  // 3. Use the generated script
  console.log(script.full_script);
}
```

This creates a workflow where users can:
1. Analyze successful hooks from other creators
2. Extract the replicable pattern
3. Generate new scripts using that proven pattern

### Example Response

```json
{
  "title": "5 Ways to Grow Your TikTok",
  "description": "Creator shares proven strategies...",
  "transcript": "Hey everyone! Today I'm going to share...",
  "hook": "Hey everyone! Today I'm going to share 5 ways to grow your TikTok account.",
  "format": "talking_head",
  "niche": "business",
  "analysis": {
    "hook_formula": "list",
    "hook_formula_name": "List Hook",
    "explanation": "This hook works because it promises specific, actionable value (5 ways) which creates a curiosity gap. Viewers want to know what those 5 ways are, and the number creates an expectation of quick, digestible content.",
    "why_it_works": [
      "Creates curiosity gap - what are the 5 ways?",
      "Promises specific value - actionable tips",
      "Number creates expectation of quick, digestible content",
      "Direct address ('Hey everyone') creates personal connection"
    ],
    "replicable_pattern": "Hey everyone! Today I'm going to share [NUMBER] ways to [ACHIEVE GOAL]."
  },
  "cached": false
}
```

---

## Script Generation Endpoint

### Endpoint

```
POST /generate-script
```

### Authentication

- **App Check Token**: Optional but recommended
- **Headers**: Include Firebase App Check token if available

### Request Body

```typescript
interface GenerateScriptRequest {
  // Required fields
  template: string;       // Vault template with [placeholders]
  topic: string;          // User's specific topic/subject
  creator_role: string;   // Who is creating this content (e.g., "food chef", "school teacher")
  main_message: string;   // Single text describing the creator's goal/message for this script
  
  // Optional fields
  niche?: string;         // Content niche (AI infers from creator_role + topic if not provided)
  style?: string;         // Script style: "conversational" | "professional" | "humorous"
  length?: string;        // Target length: "short" | "medium" | "long"
}
```

### Field Validation

#### `template` (Required)
- Must be a non-empty string
- Should contain `[placeholders]` in square brackets
- Example: `"Stop doing [MISTAKE] if you want [GOAL]. Here's what works: [SOLUTION]"`

#### `topic` (Required)
- Must be a non-empty string
- User's specific topic/subject for the script
- Example: `"classroom management"`, `"meal prep"`, `"workout routines"`

#### `creator_role` (Required)
- Must be a non-empty string
- Describes who is creating this content
- Examples: `"school teacher"`, `"food chef"`, `"fitness coach"`, `"college student"`, `"entrepreneur"`
- **This is critical** - it determines voice, terminology, and expertise level

#### `main_message` (Required)
- Must be a non-empty string
- Single text describing what the creator wants to communicate
- The AI uses this to fill user-intent placeholders like `[MISTAKE]`, `[GOAL]`, `[SECRET]`
- Example: `"Stop trying to control every student behavior. Focus on building relationships and clear expectations."`

#### `niche` (Optional)
- Default: AI infers from `creator_role` + `topic`
- If you want to override the inferred niche, provide explicitly
- Common values: `"fitness"`, `"business"`, `"food"`, `"education"`, `"tech"`, `"beauty"`, etc.

#### `style` (Optional)
- Default: `"conversational"`
- Must be one of:
  - `"conversational"` - Casual, first-person style
  - `"professional"` - Formal, authoritative tone
  - `"humorous"` - Funny, entertaining style

#### `length` (Optional)
- Default: `"short"`
- Must be one of:
  - `"short"` - ~30 seconds, ~75 words
  - `"medium"` - ~60 seconds, ~150 words
  - `"long"` - ~90+ seconds, ~225 words

### Response Model

```typescript
interface GeneratedScript {
  success: boolean;              // Always true on success
  script: ScriptParts;           // Primary generated script
  full_script: string;           // Complete script as one readable string
  variations: ScriptParts[];     // Alternative script variations (1-2 variations)
  estimated_duration: string;    // Estimated video duration (e.g., "30 seconds")
  inferred_niche?: string;       // The niche AI inferred from creator_role + topic
}

interface ScriptParts {
  hook: string;                  // Opening hook (first 3 seconds)
  body: string;                  // Main content body
  call_to_action: string;        // Ending call to action
}
```

### Example Request

```json
{
  "template": "Stop doing [MISTAKE] if you want [GOAL]. Here's what actually works: [SOLUTION].",
  "topic": "classroom management",
  "creator_role": "school teacher",
  "main_message": "Stop trying to control every student behavior. Focus on building relationships and setting clear expectations from day one."
}
```

### Example Response

```json
{
  "success": true,
  "script": {
    "hook": "Stop trying to control every student behavior if you want effective classroom management.",
    "body": "I spent my first year as a teacher constantly policing every little thing. It was exhausting and it didn't work. Here's what actually works: building genuine relationships with your students. When kids feel respected and connected, they want to behave. Set clear expectations on day one, be consistent, and focus on the positive. I went from dreading every class to actually enjoying my job.",
    "call_to_action": "What classroom management tip works for you? Drop it in the comments!"
  },
  "full_script": "Stop trying to control every student behavior if you want effective classroom management. I spent my first year as a teacher constantly policing every little thing. It was exhausting and it didn't work. Here's what actually works: building genuine relationships with your students. When kids feel respected and connected, they want to behave. Set clear expectations on day one, be consistent, and focus on the positive. I went from dreading every class to actually enjoying my job. What classroom management tip works for you? Drop it in the comments!",
  "variations": [
    {
      "hook": "The biggest mistake new teachers make? Trying to control everything.",
      "body": "I know because I made it too. My first year, I was the behavior police. Every whisper, every movement - I was on it. And guess what? It made everything worse. What changed everything was focusing on relationships first. Get to know your students. Respect them. Set clear expectations together. When students feel seen and valued, classroom management becomes natural. Trust me, it's a game-changer.",
      "call_to_action": "Tag a new teacher who needs to hear this!"
    }
  ],
  "estimated_duration": "30 seconds",
  "inferred_niche": "education"
}
```

### How the AI Processes Your Request

1. **Infers Niche**: From `creator_role` ("school teacher") + `topic` ("classroom management") → "education"
2. **Maps Main Message to Placeholders**:
   - `[MISTAKE]` → "trying to control every student behavior"
   - `[GOAL]` → "effective classroom management"
   - `[SOLUTION]` → "building relationships and setting clear expectations"
3. **Adapts Voice**: Uses teacher terminology, classroom examples, education context
4. **Maintains Niche Consistency**: All content stays relevant to education (no marketing, business, etc.)

---

## Script Generation From Scratch

> **NEW ENDPOINT** - Generate scripts without requiring a vault template

### Endpoint

```
POST /generate-scripts-from-scratch
```

### Overview

Generate 3 meaningfully different script options based on user inputs. No template required - the AI creates complete scripts from scratch with a 4-beat structure: Hook → Context → Value → CTA.

### Request Body

```typescript
interface GenerateScriptsFromScratchRequest {
  topic: string;              // Required, max 120 chars
  audience?: string;          // Optional, max 80 chars
  hook_style: HookStyle;      // Required enum
  proof?: string;             // Optional, max 500 chars
  cta_type: CTAType;          // Required enum
  cta_keyword?: string;       // Required if cta_type is "comment_keyword"
  tone: Tone;                 // Required enum
  format: VideoFormat;        // Required enum
  length_seconds: number;     // Required: 30, 45, or 60
  reading_speed: ReadingSpeed; // Required enum
}
```

### Enums

#### `hook_style`
| Value | Description |
|-------|-------------|
| `question` | Opens with an intriguing question |
| `hot_take` | Bold, potentially controversial statement |
| `storytime` | Personal anecdote opener |
| `ranking` | "Top 3...", "The #1 reason..." |
| `tutorial` | "Here's how to...", instructional |
| `myth_bust` | "Everyone thinks X but actually..." |

#### `cta_type`
| Value | Description |
|-------|-------------|
| `follow_for_more` | "Follow for more tips like this" |
| `save_this` | "Save this for later" |
| `comment_keyword` | "Comment [keyword] below" (requires `cta_keyword`) |
| `try_this_today` | "Try this on your next video" |
| `download_app` | "Link in bio to download" |
| `dm_me` | "DM me for more details" |

#### `tone`
| Value | Description |
|-------|-------------|
| `casual` | Friendly, conversational, relatable |
| `confident` | Authoritative, assertive, bold |
| `funny` | Humorous, lighthearted, playful |
| `calm` | Relaxed, soothing, measured |
| `direct` | No fluff, straight to the point |
| `educational` | Informative, teacher-like |

#### `format`
| Value | Description |
|-------|-------------|
| `talking_to_camera` | Standard talking head format |
| `voiceover` | Voice narration over B-roll |
| `faceless_text` | Text on screen with background |

#### `reading_speed`
| Value | Words Per Minute |
|-------|------------------|
| `normal` | 150 wpm |
| `fast` | 175 wpm |

### Example Request

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

### Response

```typescript
interface GenerateScriptsFromScratchResponse {
  success: boolean;
  options: ScriptOption[];  // Exactly 3 options
  meta?: {
    generation_time_ms: number;
    model: string;
  };
}

interface ScriptOption {
  option_id: string;        // "opt_1", "opt_2", "opt_3"
  beats: {
    hook: string;           // Opening hook (3-5 seconds)
    context: string;        // Problem setup (10-15 seconds)
    value: string;          // Main content (20-35 seconds)
    cta: string;            // Call-to-action (5-10 seconds)
  };
  full_text: string;        // Complete script joined with newlines
  estimated_seconds: number;
  word_count: number;
  tags: {
    hook_style: string;
    tone: string;
    format: string;
  };
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
      "full_text": "Wait. You're losing views every single day...",
      "estimated_seconds": 42,
      "word_count": 89,
      "tags": {
        "hook_style": "question",
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

### Key Differences from `/generate-script`

| Feature | `/generate-script` | `/generate-scripts-from-scratch` |
|---------|-------------------|----------------------------------|
| Template | Required (vault) | Not needed |
| Output | 1 script + variations | 3 distinct scripts |
| Structure | hook, body, cta | hook, context, value, cta |
| Use Case | Template-based generation | Fresh script creation |

---

## Refine Beat Endpoint

> **NEW ENDPOINT** - Refine individual beats with specific actions

### Endpoint

```
POST /refine-beat
```

### Overview

Refine a single beat of a script with a specific action like "make it punchier" or "add more curiosity". Useful for iterating on individual sections without regenerating the entire script.

### Request Body

```typescript
interface RefineBeatRequest {
  beat_type: BeatType;        // Which beat to refine
  current_text: string;       // Current text of the beat
  action: RefineAction;       // Action to apply
  context?: {                 // Optional context for consistency
    topic?: string;
    audience?: string;
    tone?: string;
  };
}
```

### Beat Types and Available Actions

| Beat Type | Available Actions |
|-----------|-------------------|
| `hook` | `punchier`, `more_curiosity`, `shorter`, `new_hook` |
| `context` | `shorter`, `clearer`, `add_one_line` |
| `value` | `add_example`, `make_simpler`, `cut_fluff`, `add_pattern_interrupt` |
| `cta` | `swap_cta`, `add_keyword_prompt`, `less_salesy` |

### Action Descriptions

| Action | Description |
|--------|-------------|
| `punchier` | Make it more impactful, bold, attention-grabbing |
| `more_curiosity` | Add mystery, open loop, make viewer want to keep watching |
| `shorter` | Reduce word count while keeping the essence |
| `new_hook` | Generate a completely different hook angle |
| `clearer` | Simplify language, remove jargon |
| `add_one_line` | Add one more sentence of context/setup |
| `add_example` | Include a specific example or case study |
| `make_simpler` | Break down complex ideas into simpler terms |
| `cut_fluff` | Remove filler words and unnecessary phrases |
| `add_pattern_interrupt` | Add something unexpected to re-engage viewer |
| `swap_cta` | Generate a different style of call-to-action |
| `add_keyword_prompt` | Add "Comment [keyword] below" style prompt |
| `less_salesy` | Make CTA feel more natural and less pushy |

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

### Response

```typescript
interface RefineBeatResponse {
  success: boolean;
  refined_text: string;
  estimated_seconds: number;
  word_count: number;
  action_applied: string;
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

## Error Handling

### HTTP Status Codes

- **200 OK**: Success
- **400 Bad Request**: Invalid request body (validation errors)
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error or GenAI service failure

### Error Response Format

```typescript
interface ErrorResponse {
  detail: string;  // Error message
}
```

### Common Error Scenarios

#### 1. Validation Error (400)

```json
{
  "detail": "creator_role must be a non-empty string"
}
```

**Possible causes:**
- Empty `template`, `topic`, `creator_role`, or `main_message` fields
- Invalid `style` value (not one of: conversational, professional, humorous)
- Invalid `length` value (not one of: short, medium, long)

#### 2. Rate Limit Exceeded (429)

```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

**Rate limits:**
- **Authenticated users**: 5 requests per minute per user
- **IP-based (authenticated)**: 10 requests per minute per IP
- **IP-based (unauthenticated)**: 5 requests per minute per IP

#### 3. Service Error (500)

```json
{
  "detail": "Failed to generate script. Please try again."
}
```

**Possible causes:**
- GenAI service unavailable
- Timeout
- Internal processing error

### Error Handling Best Practices

1. **Validate client-side** before sending requests
2. **Handle rate limits** with exponential backoff
3. **Show user-friendly messages** for validation errors
4. **Retry logic** for 500 errors (with backoff)
5. **Log errors** for debugging

---

## Rate Limiting

### Script Generation Endpoint Limits

| User Type | Limit | Window |
|-----------|-------|--------|
| Authenticated User | 5 requests | 1 minute |
| IP (Authenticated) | 10 requests | 1 minute |
| IP (Unauthenticated) | 5 requests | 1 minute |

### Rate Limit Headers

The API may include rate limit headers in responses:

```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1640995200
```

### Handling Rate Limits

1. **Track request counts** client-side
2. **Implement exponential backoff** when hitting limits
3. **Show user feedback** when rate limited
4. **Queue requests** if needed

---

## Integration Examples

### TypeScript/React Example

```typescript
// Types
interface GenerateScriptRequest {
  template: string;
  topic: string;
  creator_role: string;
  main_message: string;
  niche?: string;
  style?: "conversational" | "professional" | "humorous";
  length?: "short" | "medium" | "long";
}

interface GeneratedScript {
  success: boolean;
  script: {
    hook: string;
    body: string;
    call_to_action: string;
  };
  full_script: string;
  variations: Array<{
    hook: string;
    body: string;
    call_to_action: string;
  }>;
  estimated_duration: string;
  inferred_niche?: string;
}

// API Client
async function generateScript(
  request: GenerateScriptRequest,
  appCheckToken?: string
): Promise<GeneratedScript> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  
  if (appCheckToken) {
    headers["X-Firebase-AppCheck"] = appCheckToken;
  }

  const response = await fetch("/generate-script", {
    method: "POST",
    headers,
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    if (response.status === 429) {
      throw new Error("Rate limit exceeded. Please try again later.");
    }
    const error = await response.json();
    throw new Error(error.detail || "Failed to generate script");
  }

  return response.json();
}

// React Component Example
function ScriptGenerator() {
  const [loading, setLoading] = useState(false);
  const [script, setScript] = useState<GeneratedScript | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [template, setTemplate] = useState("");
  const [topic, setTopic] = useState("");
  const [creatorRole, setCreatorRole] = useState("");
  const [mainMessage, setMainMessage] = useState("");

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);

    try {
      const appCheckToken = await getAppCheckToken();
      
      const result = await generateScript({
        template,
        topic,
        creator_role: creatorRole,
        main_message: mainMessage,
      }, appCheckToken);

      setScript(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate script");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <input 
        placeholder="Template (from vault)"
        value={template}
        onChange={(e) => setTemplate(e.target.value)}
      />
      <input 
        placeholder="Topic (e.g., classroom management)"
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
      />
      <input 
        placeholder="Who are you? (e.g., school teacher)"
        value={creatorRole}
        onChange={(e) => setCreatorRole(e.target.value)}
      />
      <textarea 
        placeholder="What's your main message?"
        value={mainMessage}
        onChange={(e) => setMainMessage(e.target.value)}
      />
      
      <button onClick={handleGenerate} disabled={loading}>
        {loading ? "Generating..." : "Generate Script"}
      </button>
      
      {error && <div className="error">{error}</div>}
      
      {script && (
        <div>
          <h3>Script</h3>
          <p><strong>Hook:</strong> {script.script.hook}</p>
          <p><strong>Body:</strong> {script.script.body}</p>
          <p><strong>CTA:</strong> {script.script.call_to_action}</p>
          
          <h4>Variations</h4>
          {script.variations.map((variation, idx) => (
            <div key={idx}>
              <p><strong>Hook:</strong> {variation.hook}</p>
              <p><strong>Body:</strong> {variation.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### JavaScript Example

```javascript
async function generateScript(request) {
  const response = await fetch("/generate-script", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to generate script");
  }

  return response.json();
}

// Usage
generateScript({
  template: "Stop doing [MISTAKE] if you want [GOAL]. Here's what works: [SOLUTION].",
  topic: "meal prep",
  creator_role: "food chef",
  main_message: "Stop prepping everything on Monday morning. Prep on Sunday evening when you have more time and energy."
})
  .then((script) => {
    console.log("Generated script:", script);
    console.log("Hook:", script.script.hook);
    console.log("Full script:", script.full_script);
    console.log("Inferred niche:", script.inferred_niche);
  })
  .catch((error) => {
    console.error("Error:", error.message);
  });
```

### Hook Analysis Usage

```typescript
// The hook analysis is automatically included in the /process endpoint response
async function processVideo(url: string) {
  const response = await fetch("/process", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url }),
  });

  const content = await response.json();
  
  // Check if analysis is available
  if (content.analysis) {
    console.log("Hook Formula:", content.analysis.hook_formula_name);
    console.log("Why it works:", content.analysis.why_it_works);
    console.log("Replicable Pattern:", content.analysis.replicable_pattern);
  } else {
    console.log("No analysis available (cached result or no hook)");
  }
  
  return content;
}
```

---

## UI Form Recommendations

### Minimal Form Fields

```
┌─────────────────────────────────────────────────────┐
│ Generate Script                                      │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Template (from vault):                              │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Stop doing [MISTAKE] if you want [GOAL]...      │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ Topic: *                                            │
│ ┌─────────────────────────────────────────────────┐ │
│ │ classroom management                            │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ Who are you? *                                      │
│ ┌─────────────────────────────────────────────────┐ │
│ │ school teacher                                  │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ What's your main message? *                         │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Stop trying to control every student behavior.  │ │
│ │ Focus on building relationships and setting     │ │
│ │ clear expectations from day one.                │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ [Optional: Advanced Settings]                       │
│   Style: [Conversational ▼]                         │
│   Length: [Short (30s) ▼]                           │
│                                                     │
│ [Generate Script]                                   │
└─────────────────────────────────────────────────────┘
```

### Field Labels

- **Template**: Auto-populated from vault item
- **Topic**: "What are you talking about?"
- **Creator Role**: "Who are you?" or "What's your role?"
- **Main Message**: "What's your main point?" or "What do you want viewers to know?"

---

## Field Name Handling

The API handles both `snake_case` and `camelCase` field names from the GenAI service. The response will always be in `snake_case` format for consistency.

**Frontend should expect:**
- `call_to_action` (not `callToAction`)
- `full_script` (not `fullScript`)
- `estimated_duration` (not `estimatedDuration`)
- `inferred_niche` (not `inferredNiche`)

---

## Testing

### Test Cases

1. **Valid Request**
   - All required fields provided (`template`, `topic`, `creator_role`, `main_message`)
   - Should return 200 with script

2. **Missing Required Fields**
   - Missing `template` → 400 error
   - Missing `topic` → 400 error
   - Missing `creator_role` → 400 error
   - Missing `main_message` → 400 error

3. **Invalid Field Values**
   - Invalid `style` → 400 error
   - Invalid `length` → 400 error

4. **Rate Limiting**
   - Send 6 requests in 1 minute → 429 error on 6th request

5. **Empty Fields**
   - Empty string for required field → 400 error

6. **Niche Inference**
   - Send without `niche`, verify `inferred_niche` in response matches creator_role + topic

---

## Summary

### Key Points

1. **Four Required Fields**: `template`, `topic`, `creator_role`, `main_message`
2. **Smart Niche Inference**: AI infers niche from creator_role + topic (no need to ask user)
3. **Single Message Input**: One `main_message` field replaces complex placeholder mapping
4. **Voice Adaptation**: `creator_role` determines terminology, examples, and expertise level
5. **Hook Analysis**: Automatically included in `/process` endpoint responses for new videos

### Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/process` | POST | Process video (includes hook analysis) |
| `/generate-script` | POST | Generate script from template |

### Required Fields Summary

| Field | Type | Description |
|-------|------|-------------|
| `template` | string | Vault template with [placeholders] |
| `topic` | string | What the script is about |
| `creator_role` | string | Who is creating (affects voice) |
| `main_message` | string | Core message to communicate |

### Support

For questions or issues, contact the backend team or refer to the main API documentation.
