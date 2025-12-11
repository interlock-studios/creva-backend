# Script Generation: Minimal Context Guide

## Overview

Script generation requires only **4 essential fields** to produce high-quality, personalized scripts. The AI intelligently infers everything else.

---

## Required Fields

### 1. `template` (from vault)

The madlib-style template with `[placeholders]` from the user's vault.

**Example:**
```
"Stop doing [MISTAKE] if you want [GOAL]. Here's what actually works: [SOLUTION]."
```

**Source:** Pre-populated from the vault item the user selected.

---

### 2. `topic`

What the script is about.

**Examples:**
- `"classroom management"`
- `"meal prep"`
- `"workout routines"`
- `"Instagram growth"`

**UI:** Simple text input: "What are you talking about?"

---

### 3. `creator_role`

Who is creating this content. This is the most important context field.

**Examples:**
- `"school teacher"`
- `"food chef"`
- `"fitness coach"`
- `"college student"`
- `"entrepreneur"`
- `"parent"`
- `"nurse"`

**Why it matters:**
- Determines voice and terminology
- Sets expertise level
- Infers the appropriate niche
- Prevents topic drift (a teacher won't get marketing advice)

**UI:** Simple text input: "Who are you?" or "What's your role?"

**Future enhancement:** Save to user profile, allow multiple personas.

---

### 4. `main_message`

A single text describing what the creator wants to communicate. The AI uses this to fill template placeholders intelligently.

**Example for a teacher:**
```
"Stop trying to control every student behavior. Focus on building relationships and setting clear expectations from day one."
```

**Example for a chef:**
```
"Stop prepping everything on Monday morning. Prep on Sunday evening when you have more time and energy."
```

**How the AI uses it:**
- Parses the template for placeholders like `[MISTAKE]`, `[GOAL]`, `[SECRET]`
- Maps parts of the main_message to these placeholders
- Fills generic placeholders like `[number]`, `[timeframe]` from context

**UI:** Textarea: "What's your main message?" or "What do you want viewers to know?"

---

## Optional Fields

### `niche`
- Default: AI infers from `creator_role` + `topic`
- Only provide if you want to override the inference
- Example: `"education"`, `"food"`, `"fitness"`

### `style`
- Default: `"conversational"`
- Options: `"conversational"`, `"professional"`, `"humorous"`

### `length`
- Default: `"short"` (30 seconds, ~75 words)
- Options: `"short"`, `"medium"`, `"long"`

---

## How Niche Inference Works

The AI automatically determines the niche from `creator_role` and `topic`:

| Creator Role | Topic | Inferred Niche |
|--------------|-------|----------------|
| school teacher | classroom management | education |
| food chef | meal prep | food |
| fitness coach | workout routines | fitness |
| entrepreneur | marketing strategy | business |
| college student | study tips | education |
| nurse | patient care | health |

**Key benefit:** The AI stays within this niche. A "school teacher" talking about "classroom management" will get education-focused content, not marketing tips.

---

## How Placeholder Mapping Works

Given:
- **Template:** `"Stop doing [MISTAKE] if you want [GOAL]. Here's what works: [SOLUTION]"`
- **Main Message:** `"Stop trying to control every student behavior. Focus on building relationships."`

The AI maps:
- `[MISTAKE]` → "trying to control every student behavior"
- `[GOAL]` → "effective classroom management" (inferred from topic)
- `[SOLUTION]` → "building relationships and setting clear expectations"

### Placeholder Types

**User-Intent Placeholders** (filled from main_message):
- `[MISTAKE]`, `[GOAL]`, `[SECRET]`, `[SOLUTION]`, `[CHALLENGE]`, `[TIP]`

**Generic Placeholders** (inferred from context):
- `[topic]` → from topic field
- `[number]` → common values like 3, 5, 10
- `[timeframe]` → appropriate for context
- `[location]` → inferred from niche

---

## Example Requests

### Teacher Example

```json
{
  "template": "Stop doing [MISTAKE] if you want [GOAL]. Here's what works: [SOLUTION].",
  "topic": "classroom management",
  "creator_role": "school teacher",
  "main_message": "Stop trying to control every student behavior. Focus on building relationships and setting clear expectations from day one."
}
```

**Result:** Script using teacher terminology, classroom examples, education context.

---

### Chef Example

```json
{
  "template": "I can't believe I'm sharing this [SECRET] about [TOPIC]",
  "topic": "meal prep",
  "creator_role": "food chef",
  "main_message": "The secret to meal prep is doing it on Sunday evening, not Monday morning. You have more time and energy."
}
```

**Result:** Script using cooking terminology, kitchen examples, food context.

---

### Fitness Coach Example

```json
{
  "template": "Here are [NUMBER] things you're doing wrong at the gym",
  "topic": "beginner workouts",
  "creator_role": "fitness coach",
  "main_message": "Beginners skip warm-ups, use too heavy weights, and don't focus on form."
}
```

**Result:** Script using fitness terminology, gym examples, exercise context.

---

### Student Example

```json
{
  "template": "What would happen if you [ACTION] for [TIMEFRAME]?",
  "topic": "study habits",
  "creator_role": "college student",
  "main_message": "Study for 25 minutes with 5 minute breaks instead of cramming for hours."
}
```

**Result:** Script using student language, study examples, relatable academic context.

---

## UI Implementation

### Minimal Form

```
┌─────────────────────────────────────────────────────┐
│ Generate Script                                      │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Template: (auto-filled from vault)                  │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Stop doing [MISTAKE] if you want [GOAL]...      │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ What are you talking about? *                       │
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
│ │ Focus on building relationships...              │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ [Generate Script]                                   │
└─────────────────────────────────────────────────────┘
```

### Field Labels

| Field | Label Option 1 | Label Option 2 |
|-------|----------------|----------------|
| topic | "What are you talking about?" | "Topic" |
| creator_role | "Who are you?" | "Your role" |
| main_message | "What's your main message?" | "What do you want to say?" |

---

## Future Enhancements

### Creator Profiles (Phase 2)

Allow users to save creator profiles:

```json
{
  "name": "Teacher Profile",
  "creator_role": "school teacher",
  "expertise": "high school math",
  "years_experience": 10
}
```

Then select profile before generating scripts.

### Placeholder Suggestions (Phase 2)

After parsing template, suggest common values based on creator_role.

---

## Summary

| Field | Required | Source |
|-------|----------|--------|
| template | Yes | Vault item |
| topic | Yes | User input (text) |
| creator_role | Yes | User input (text) |
| main_message | Yes | User input (textarea) |
| niche | No | AI infers |
| style | No | Default: conversational |
| length | No | Default: short |

**Key insight:** With just these 4 fields, the AI can:
- Infer the appropriate niche
- Fill all template placeholders
- Adapt voice and terminology
- Stay contextually relevant
- Generate authentic, role-specific content
