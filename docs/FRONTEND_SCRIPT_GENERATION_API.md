# Frontend Integration Guide: Script Generation & Hook Analysis

## Overview

This document provides complete API documentation for the new script generation endpoint and hook analysis feature. These features allow users to:
1. **Analyze hooks** from processed videos to understand why they work
2. **Generate scripts** from templates and topics for creating new content

---

## Table of Contents

1. [Hook Analysis](#hook-analysis)
2. [Script Generation Endpoint](#script-generation-endpoint)
3. [Request/Response Models](#requestresponse-models)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [Integration Examples](#integration-examples)

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
    topic: "your topic here",
    niche: content.niche || "general",
    style: "conversational",
    length: "short",
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
  template: string;              // Required: Madlib template with [placeholders]
  topic: string;                 // Required: User's topic/subject
  niche?: string;                // Optional: Content niche (default: "general")
  style?: string;                // Optional: Script style (default: "conversational")
  length?: string;               // Optional: Target length (default: "short")
}
```

### Field Validation

#### `template` (Required)
- Must be a non-empty string
- Should contain `[placeholders]` in square brackets
- Example: `"I can't believe I'm sharing this [SECRET] about [TOPIC]"`

#### `topic` (Required)
- Must be a non-empty string
- User's specific topic/subject for the script
- Example: `"growing a TikTok following"`

#### `niche` (Optional)
- Default: `"general"`
- Content category/niche
- Common values: `"fitness"`, `"business"`, `"food"`, `"tech"`, `"beauty"`, etc.

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
  "template": "I can't believe I'm sharing this [SECRET] about [TOPIC]",
  "topic": "growing a TikTok following",
  "niche": "business",
  "style": "conversational",
  "length": "short"
}
```

### Example Response

```json
{
  "success": true,
  "script": {
    "hook": "I can't believe I'm sharing this secret about growing a TikTok following.",
    "body": "Most creators think you need thousands of followers to go viral. But here's the thing - I went from 0 to 100k in 3 months using one simple strategy. Post at the same time every day. The algorithm loves consistency. Engage with every comment in the first hour. And use trending sounds - but add your own twist. The key? Be authentic. People can tell when you're being fake.",
    "call_to_action": "Try this strategy and let me know how it works for you!"
  },
  "full_script": "I can't believe I'm sharing this secret about growing a TikTok following. Most creators think you need thousands of followers to go viral. But here's the thing - I went from 0 to 100k in 3 months using one simple strategy. Post at the same time every day. The algorithm loves consistency. Engage with every comment in the first hour. And use trending sounds - but add your own twist. The key? Be authentic. People can tell when you're being fake. Try this strategy and let me know how it works for you!",
  "variations": [
    {
      "hook": "Stop doing this if you want to grow your TikTok.",
      "body": "I see so many creators making the same mistake. They post randomly, ignore comments, and copy trends exactly. Here's what actually works: consistency beats everything. Pick a time slot and stick to it. Your audience will learn when to expect you. Next, engage authentically. Don't just reply with emojis - have real conversations. And finally, put your spin on trends. Don't copy - remix. That's how you stand out.",
      "call_to_action": "What's your biggest TikTok growth challenge? Drop it below!"
    }
  ],
  "estimated_duration": "30 seconds"
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
  "detail": "template must be a non-empty string"
}
```

**Possible causes:**
- Empty `template` or `topic` fields
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

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);

    try {
      const appCheckToken = await getAppCheckToken(); // Your Firebase App Check token getter
      
      const result = await generateScript({
        template: "I can't believe I'm sharing this [SECRET] about [TOPIC]",
        topic: "growing a TikTok following",
        niche: "business",
        style: "conversational",
        length: "short",
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
  template: "I can't believe I'm sharing this [SECRET] about [TOPIC]",
  topic: "growing a TikTok following",
  niche: "business",
  style: "conversational",
  length: "short",
})
  .then((script) => {
    console.log("Generated script:", script);
    console.log("Hook:", script.script.hook);
    console.log("Full script:", script.full_script);
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

## Field Name Handling

The API handles both `snake_case` and `camelCase` field names from the GenAI service. The response will always be in `snake_case` format for consistency.

**Frontend should expect:**
- `call_to_action` (not `callToAction`)
- `full_script` (not `fullScript`)
- `estimated_duration` (not `estimatedDuration`)

---

## Testing

### Test Cases

1. **Valid Request**
   - All required fields provided
   - Valid optional field values
   - Should return 200 with script

2. **Missing Required Fields**
   - Missing `template` → 400 error
   - Missing `topic` → 400 error

3. **Invalid Field Values**
   - Invalid `style` → 400 error
   - Invalid `length` → 400 error

4. **Rate Limiting**
   - Send 6 requests in 1 minute → 429 error on 6th request

5. **Empty Template/Topic**
   - Empty string → 400 error

---

## Summary

### Key Points

1. **Hook Analysis**: Automatically included in `/process` endpoint responses for new videos
2. **Script Generation**: New `/generate-script` endpoint for generating scripts from templates
3. **Rate Limits**: 5 requests/minute per user, 10 per IP (auth), 5 per IP (unauth)
4. **Error Handling**: Proper validation and error responses
5. **Field Names**: All responses use `snake_case` format

### Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/process` | POST | Process video (includes hook analysis) |
| `/generate-script` | POST | Generate script from template |

### Support

For questions or issues, contact the backend team or refer to the main API documentation.

