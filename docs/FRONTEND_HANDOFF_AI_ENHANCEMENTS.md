# Frontend Integration Handoff: AI Enhancements

**Date**: December 11, 2024  
**Status**: ✅ Deployed to Production  
**Backend Version**: 3.0.0

---

## 🎉 What's New

Two major AI enhancements have been deployed:

1. **Enhanced `/process` endpoint** - Now includes "Why This Works" hook analysis
2. **New `/generate-script` endpoint** - Generate scripts from vault templates

---

## 📍 API Endpoints

### Base URL
- **Production**: `https://creva-parser-1079242014740.us-central1.run.app`
- **Global Load Balancer** (if configured): `https://api.creva.app`

---

## 1. Enhanced `/process` Endpoint

### Endpoint
```
POST /process
```

### What Changed
The `/process` endpoint now automatically includes hook analysis for **newly processed videos**. Cached videos will return `analysis: null`.

### Request (Unchanged)
```json
{
  "url": "https://www.tiktok.com/@creator/video/123",
  "localization": "en" // optional
}
```

### Response (New Field Added)
```json
{
  "success": true,
  "title": "Video Title",
  "description": "...",
  "image": "base64 or URL",
  "transcript": "Full transcript...",
  "hook": "What would happen if you drilled through the ice in Antarctica?",
  "format": "talking_head",
  "niche": "adventure",
  "niche_detail": "extreme sports",
  "secondary_niches": ["travel"],
  "creator": "@username",
  "platform": "tiktok",
  "tags": ["#adventure", "#explore"],
  "cached": false,
  
  // 🆕 NEW: Analysis object (null for cached videos)
  "analysis": {
    "hook_formula": "curiosity_gap",
    "hook_formula_name": "Curiosity Gap",
    "explanation": "This hook uses the 'What would happen if...' curiosity formula. It creates an immediate knowledge gap that viewers MUST fill. The combination of extreme action (drilling through ice) + unusual location (Antarctica) creates irresistible curiosity.",
    "why_it_works": [
      "Creates immediate curiosity gap",
      "Combines extreme action with unusual context",
      "Implies danger which triggers survival instinct",
      "Simple question format is easy to process"
    ],
    "replicable_pattern": "What would happen if you [extreme action] in [unusual location]?"
  }
}
```

### Analysis Field Details

| Field | Type | Description |
|-------|------|-------------|
| `hook_formula` | `string` | Machine-readable formula type (see below) |
| `hook_formula_name` | `string` | Human-readable formula name |
| `explanation` | `string` | 2-3 sentence explanation of psychological triggers |
| `why_it_works` | `string[]` | Array of bullet points explaining triggers |
| `replicable_pattern` | `string` | Template with `[placeholders]` for vault |

### Hook Formula Types

| Formula | Example Hook |
|---------|--------------|
| `curiosity_gap` | "What would happen if..." |
| `controversy` | "Stop doing X immediately..." |
| `transformation` | "I went from X to Y in Z days..." |
| `list` | "3 things that changed my life..." |
| `story` | "I was walking to work when..." |
| `question` | "Have you ever wondered why..." |
| `challenge` | "I tried X for 30 days..." |
| `secret` | "The thing nobody tells you about..." |
| `comparison` | "X vs Y - which is actually better?" |
| `myth_busting` | "Everything you know about X is wrong..." |

### When Analysis is Null

- **Cached videos**: Analysis is only generated for newly processed videos
- **Missing hook**: If no hook was extracted, `analysis` will be `null`
- **Processing error**: If analysis fails, `analysis` will be `null` (non-blocking)

### Flutter Integration

Update your `VideoItem` model:

```dart
@freezed
class VideoItem with _$VideoItem {
  const factory VideoItem({
    required String title,
    required String? description,
    required String? image,
    required String? transcript,
    required String? hook,
    required String? format,
    required String? niche,
    required String? nicheDetail,
    required List<String>? secondaryNiches,
    required String? creator,
    required String? platform,
    required List<String>? tags,
    required bool? cached,
    
    // 🆕 NEW: Add analysis field
    required VideoAnalysis? analysis,
  }) = _VideoItem;

  factory VideoItem.fromJson(Map<String, dynamic> json) =>
      _$VideoItemFromJson(json);
}

// 🆕 NEW: Analysis model
@freezed
class VideoAnalysis with _$VideoAnalysis {
  const factory VideoAnalysis({
    @JsonKey(name: 'hook_formula') required String hookFormula,
    @JsonKey(name: 'hook_formula_name') required String hookFormulaName,
    required String explanation,
    @JsonKey(name: 'why_it_works') required List<String> whyItWorks,
    @JsonKey(name: 'replicable_pattern') required String replicablePattern,
  }) = _VideoAnalysis;

  factory VideoAnalysis.fromJson(Map<String, dynamic> json) =>
      _$VideoAnalysisFromJson(json);
}
```

### Display Logic

```dart
// Show analysis section if available
if (video.analysis != null) {
  VideoWhyItWorksSection(analysis: video.analysis!)
} else if (video.cached == true) {
  // Show "Analysis not available for cached videos" message
  Text("Analysis not available for older videos")
}
```

---

## 2. New `/generate-script` Endpoint

### Endpoint
```
POST /generate-script
```

### Purpose
Generate complete scripts from vault templates + user topics. This is user-initiated (not automatic).

### Request
```json
{
  "template": "What would happen if you [extreme action] in [unusual location]?",
  "topic": "morning routine for busy parents",
  "niche": "productivity",  // optional, default: "general"
  "style": "conversational",  // optional: "conversational", "professional", "humorous", default: "conversational"
  "length": "short"  // optional: "short" (30s), "medium" (60s), "long" (90s+), default: "short"
}
```

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `template` | `string` | ✅ Yes | Madlib template with `[placeholders]` |
| `topic` | `string` | ✅ Yes | User's topic/subject |
| `niche` | `string` | ❌ No | Content niche (default: "general") |
| `style` | `string` | ❌ No | "conversational", "professional", "humorous" (default: "conversational") |
| `length` | `string` | ❌ No | "short", "medium", "long" (default: "short") |

### Response
```json
{
  "success": true,
  "script": {
    "hook": "What would happen if you woke up 30 minutes earlier as a busy parent?",
    "body": "I tried it for 30 days and here's what happened. First, I actually had time to drink my coffee while it was hot. Revolutionary, I know. Second, I got 15 minutes of quiet time before the chaos started. And third - this is the big one - I stopped feeling like I was already behind before the day even started.",
    "call_to_action": "Try it for one week and tell me if it changed your mornings."
  },
  "full_script": "What would happen if you woke up 30 minutes earlier as a busy parent?\n\nI tried it for 30 days...",
  "variations": [
    {
      "hook": "The one morning habit that changed everything for me as a busy parent",
      "body": "...",
      "call_to_action": "..."
    }
  ],
  "estimated_duration": "45 seconds"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | `boolean` | Always `true` on success |
| `script` | `object` | Primary generated script |
| `script.hook` | `string` | Opening hook (first 3 seconds) |
| `script.body` | `string` | Main content body |
| `script.call_to_action` | `string` | Ending CTA |
| `full_script` | `string` | Complete script as one string |
| `variations` | `array` | 1-2 alternative script variations |
| `estimated_duration` | `string` | Estimated video duration |

### Error Responses

```json
// Missing template
{
  "detail": [
    {
      "loc": ["body", "template"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}

// Missing topic
{
  "detail": [
    {
      "loc": ["body", "topic"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}

// Generation failed
{
  "detail": "Failed to generate script. Please try again."
}
```

### Rate Limiting

- **5 requests/minute** per authenticated user
- **10 requests/minute** per IP (authenticated)
- **5 requests/minute** per IP (unauthenticated)
- Returns `429` status code when exceeded

### Flutter Integration

Add to your AI repository:

```dart
// lib/domain/repositories/ai/ai_repository.dart

Future<GeneratedScript> generateScript({
  required String template,
  required String topic,
  String? niche,
  String? style,
  String? length,
}) async {
  final response = await _client.post(
    Uri.parse('$baseUrl/generate-script'),
    headers: {
      'Content-Type': 'application/json',
      if (appCheckToken != null) 'X-Firebase-AppCheck': appCheckToken!,
    },
    body: jsonEncode({
      'template': template,
      'topic': topic,
      if (niche != null) 'niche': niche,
      if (style != null) 'style': style,
      if (length != null) 'length': length,
    }),
  );

  if (response.statusCode == 200) {
    return GeneratedScript.fromJson(jsonDecode(response.body));
  } else if (response.statusCode == 429) {
    throw RateLimitException('Too many script generation requests');
  } else {
    throw ScriptGenerationException('Failed to generate script');
  }
}
```

### Models

```dart
@freezed
class GeneratedScript with _$GeneratedScript {
  const factory GeneratedScript({
    required bool success,
    required ScriptParts script,
    @JsonKey(name: 'full_script') required String fullScript,
    required List<ScriptParts> variations,
    @JsonKey(name: 'estimated_duration') required String estimatedDuration,
  }) = _GeneratedScript;

  factory GeneratedScript.fromJson(Map<String, dynamic> json) =>
      _$GeneratedScriptFromJson(json);
}

@freezed
class ScriptParts with _$ScriptParts {
  const factory ScriptParts({
    required String hook,
    required String body,
    @JsonKey(name: 'call_to_action') required String callToAction,
  }) = _ScriptParts;

  factory ScriptParts.fromJson(Map<String, dynamic> json) =>
      _$ScriptPartsFromJson(json);
}
```

---

## 🔑 Important Notes

### Field Naming Convention
- **Backend uses snake_case**: `hook_formula`, `why_it_works`, `call_to_action`
- **Flutter uses camelCase**: `hookFormula`, `whyItWorks`, `callToAction`
- Use `@JsonKey(name: 'snake_case')` for conversion

### Cached Videos
- Analysis is **only generated for newly processed videos**
- Cached videos return `analysis: null`
- This keeps cache hits fast (no 2+ second AI delay)

### Performance
- Hook analysis adds ~1-2 seconds to `/process` for new videos
- Script generation takes ~2-3 seconds
- Both use existing Gemini 2.0 Flash infrastructure

### Error Handling
- Analysis failures are **non-blocking** - video processing still succeeds
- Script generation failures return proper error responses
- Rate limit errors return `429` with `Retry-After` header

---

## 🧪 Testing

### Test `/process` with Analysis

```bash
curl -X POST https://creva-parser-1079242014740.us-central1.run.app/process \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.tiktok.com/@creator/video/123"
  }'

# Verify response includes "analysis" object
```

### Test `/generate-script`

```bash
# Basic test
curl -X POST https://creva-parser-1079242014740.us-central1.run.app/generate-script \
  -H "Content-Type: application/json" \
  -d '{
    "template": "What would happen if you [action] for [time]?",
    "topic": "cold showers"
  }'

# With all options
curl -X POST https://creva-parser-1079242014740.us-central1.run.app/generate-script \
  -H "Content-Type: application/json" \
  -d '{
    "template": "[Number] things that [outcome]",
    "topic": "improved my sleep",
    "niche": "health",
    "style": "conversational",
    "length": "medium"
  }'
```

---

## 📊 Deployment Status

### Successfully Deployed Regions
- ✅ **us-central1** (Primary) - `https://creva-parser-1079242014740.us-central1.run.app`
- ✅ **us-east1** - `https://creva-parser-1079242014740.us-east1.run.app`
- ✅ **us-west1** - `https://creva-parser-1079242014740.us-west1.run.app`
- ✅ **europe-west1** - `https://creva-parser-1079242014740.europe-west1.run.app`
- ✅ **europe-west4** - `https://creva-parser-1079242014740.europe-west4.run.app`

### Quota-Limited Regions (Not Critical)
- ⚠️ europe-north1
- ⚠️ asia-southeast1
- ⚠️ asia-northeast1
- ⚠️ asia-south1
- ⚠️ australia-southeast1
- ⚠️ southamerica-east1

*Note: These regions can be deployed later if needed. Primary regions are sufficient for now.*

---

## 🚀 Next Steps for Frontend

1. **Update `VideoItem` model** - Add `analysis` field with `VideoAnalysis` model
2. **Update `/process` response handling** - Handle `analysis: null` for cached videos
3. **Create `VideoWhyItWorksSection` widget** - Display analysis data (you mentioned this is already built)
4. **Add script generation repository method** - Implement `generateScript()` method
5. **Create script generation UI** - Form to collect template, topic, niche, style, length
6. **Handle rate limiting** - Show user-friendly messages for 429 errors

---

## 📞 Support

If you encounter any issues:
1. Check the API response structure matches this document
2. Verify field names use snake_case in API responses
3. Test with a fresh video URL (not cached) to see analysis
4. Check rate limits if script generation fails

---

## ✅ Checklist

- [x] Backend deployed to production
- [x] `/process` endpoint enhanced with analysis
- [x] `/generate-script` endpoint created
- [x] Rate limiting configured
- [x] Error handling implemented
- [ ] Frontend models updated
- [ ] Frontend UI updated
- [ ] Testing completed

---

**Ready for integration!** 🎉

