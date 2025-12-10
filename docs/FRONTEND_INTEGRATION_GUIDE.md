# Creva API - Frontend Integration Guide

> **Complete handoff documentation for frontend developers integrating with the Creva video parsing API.**

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Project Configuration](#project-configuration)
3. [Authentication](#authentication)
4. [API Reference](#api-reference)
   - [Health Endpoints](#health-endpoints)
   - [Video Processing Endpoints](#video-processing-endpoints)
   - [Search Endpoints](#search-endpoints)
   - [Video Endpoints](#video-endpoints)
5. [Video Formats Reference](#video-formats-reference)
6. [Content Niches Reference](#content-niches-reference)
7. [TypeScript Interfaces](#typescript-interfaces)
8. [Firestore Data Structure](#firestore-data-structure)
9. [React/Next.js Integration Examples](#reactnextjs-integration-examples)
10. [Error Handling](#error-handling)
11. [Testing Guide](#testing-guide)

---

## Quick Start

### 1. Get the Production API URL

```bash
gcloud run services describe creva-parser --project=creva-e6435 --region=us-central1 --format="value(status.url)"
```

### 2. Test the API

```bash
# Health check
curl https://YOUR_API_URL/health

# Get available formats
curl https://YOUR_API_URL/search/formats

# Get available niches
curl https://YOUR_API_URL/search/niches

# Process a video
curl -X POST https://YOUR_API_URL/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@creator/video/123"}'
```

### 3. Install Required Dependencies (Frontend)

```bash
npm install firebase
# or
yarn add firebase
```

---

## Project Configuration

### API Endpoints

| Environment | Base URL |
|-------------|----------|
| **Production** | `https://creva-parser-<hash>.run.app` |
| **Local Dev** | `http://localhost:8080` |

> **GCP Project ID:** `creva-e6435`

### Environment Variables

Add these to your frontend `.env.local` or environment config:

```env
# API Configuration
NEXT_PUBLIC_API_URL=https://creva-parser-xxx.run.app

# Firebase Configuration
NEXT_PUBLIC_FIREBASE_PROJECT_ID=creva-e6435
NEXT_PUBLIC_FIREBASE_API_KEY=your-api-key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=creva-e6435.firebaseapp.com
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=creva-e6435.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
NEXT_PUBLIC_FIREBASE_APP_ID=your-app-id
```

### Firebase Configuration

```typescript
// lib/firebase.ts
import { initializeApp, getApps } from 'firebase/app';
import { getFirestore } from 'firebase/firestore';
import { getAuth } from 'firebase/auth';
import { initializeAppCheck, ReCaptchaV3Provider } from 'firebase/app-check';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

// Initialize Firebase (prevent re-initialization)
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];

export const db = getFirestore(app);
export const auth = getAuth(app);

// Initialize App Check (optional but recommended for production)
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'production') {
  initializeAppCheck(app, {
    provider: new ReCaptchaV3Provider(process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY!),
    isTokenAutoRefreshEnabled: true,
  });
}

export default app;
```

---

## Authentication

### App Check (Optional)

The API supports Firebase App Check for enhanced security. When enabled, include the token in your requests:

```typescript
import { getToken } from 'firebase/app-check';
import { appCheck } from './firebase';

async function getAppCheckToken(): Promise<string | null> {
  try {
    const result = await getToken(appCheck, /* forceRefresh */ false);
    return result.token;
  } catch (error) {
    console.warn('App Check token retrieval failed:', error);
    return null;
  }
}

// Usage in API calls
const appCheckToken = await getAppCheckToken();
const response = await fetch(`${API_URL}/process`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    ...(appCheckToken && { 'X-Firebase-AppCheck': appCheckToken }),
  },
  body: JSON.stringify({ url: videoUrl }),
});
```

### Endpoints That Skip App Check

These endpoints work without App Check tokens:
- `/health` - Health check
- `/search/formats` - Get video formats
- `/search/niches` - Get content niches
- `/search` - Search videos
- `/docs`, `/redoc`, `/openapi.json` - API documentation (dev only)

---

## API Reference

### Health Endpoints

#### `GET /health`

Check API health status and service availability.

**Request:**
```bash
curl https://YOUR_API_URL/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "environment": "production",
  "project_id": "creva-e6435",
  "version": "1.0.0",
  "services": {
    "cache": "healthy",
    "queue": "healthy",
    "tiktok_scraper": "healthy",
    "app_check": "healthy"
  }
}
```

**Status Values:**
- `healthy` - All services operational
- `degraded` - Some services have issues but API is functional

---

#### `GET /status`

Get detailed system status including processing capacity.

**Request:**
```bash
curl https://YOUR_API_URL/status
```

**Response:**
```json
{
  "status": "operational",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "hybrid_mode": {
    "enabled": true,
    "direct_processing": {
      "active": 3,
      "max": 20,
      "available": 17
    }
  },
  "rate_limiting": {
    "active_ips": 5,
    "limit_per_ip": 10,
    "window_seconds": 60
  },
  "processing_queue": {
    "available_slots": 40,
    "total_slots": 50,
    "utilization_percent": 20
  },
  "cache": {
    "hits": 150,
    "misses": 30,
    "hit_rate": 0.83
  },
  "queue": {
    "pending": 5,
    "processing": 2,
    "completed_today": 100
  },
  "app_check": {
    "required": false,
    "stats": {
      "verified": 450,
      "unverified": 50,
      "invalid": 2
    }
  },
  "cloud_run": {
    "max_instances": 50,
    "concurrency_per_instance": 80,
    "max_concurrent_requests": 4000
  }
}
```

---

### Video Processing Endpoints

#### `POST /process`

Process a TikTok or Instagram video URL to extract transcript, hook, format, and niche.

**Request:**
```bash
curl -X POST https://YOUR_API_URL/process \
  -H "Content-Type: application/json" \
  -H "X-Firebase-AppCheck: <optional-token>" \
  -d '{
    "url": "https://www.tiktok.com/@creator/video/7463250363559218474",
    "localization": "Spanish"
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | TikTok or Instagram video URL |
| `localization` | string | No | Language for translation (e.g., "Spanish", "zh", "Tamil") |

**Success Response (Direct Processing):**
```json
{
  "title": "5 Morning Habits for Success",
  "description": "Creator shares five powerful morning routines that successful entrepreneurs follow daily.",
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "transcript": "Hey everyone! Today I'm sharing 5 morning habits that changed my life. Number one - wake up at 5am. I know it sounds crazy but hear me out. The most successful CEOs start their day early when the world is quiet. Number two - exercise first thing. Get your blood flowing and your mind sharp. Even just 20 minutes makes a huge difference. Number three - no phone for the first hour. Protect your mental space from the chaos of notifications. Number four - journal your goals. Write down what you want to achieve that day. And number five - eat a healthy breakfast. Fuel your body for peak performance. Try these out and let me know how it goes in the comments!",
  "hook": "Hey everyone! Today I'm sharing 5 morning habits that changed my life.",
  "format": "talking_head",
  "niche": "lifestyle",
  "niche_detail": "morning routines and productivity habits for entrepreneurs",
  "secondary_niches": ["business", "motivation"],
  "creator": "@productivityguru",
  "platform": "tiktok",
  "tags": ["#morningroutine", "#productivity", "#successhabits", "#entrepreneur", "#fyp"],
  "cached": false
}
```

**Queued Response (High Load):**
```json
{
  "status": "queued",
  "job_id": "abc123-def456-ghi789",
  "message": "Video queued for processing. Check status with job_id.",
  "check_url": "/status/abc123-def456-ghi789"
}
```

**Response Fields Explained:**

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | AI-generated descriptive title for the video |
| `description` | string | Brief 1-2 sentence summary of the video content |
| `image` | string | Base64-encoded JPEG thumbnail (first frame or first slideshow image) |
| `transcript` | string | **FULL transcript** of everything spoken in the video (Priority #1) |
| `hook` | string | The attention-grabbing opening line (first 10-30 seconds) |
| `format` | string | Video production style - see [Video Formats Reference](#video-formats-reference) |
| `niche` | string | Primary content category - see [Content Niches Reference](#content-niches-reference) |
| `niche_detail` | string | Specific subcategory (e.g., "meal prep for bodybuilders") |
| `secondary_niches` | string[] | Additional categories if video spans multiple niches |
| `creator` | string | Creator username (e.g., "@username") |
| `platform` | string | Source platform: `"tiktok"` or `"instagram"` |
| `tags` | string[] | Original hashtags from the post |
| `cached` | boolean | `true` if result was served from cache |

---

#### `GET /status/{job_id}`

Check the processing status of a queued video job.

**Request:**
```bash
curl https://YOUR_API_URL/status/abc123-def456-ghi789
```

**Pending Response:**
```json
{
  "status": "pending",
  "job_id": "abc123-def456-ghi789",
  "created_at": "2024-01-15T10:30:00.000Z",
  "attempts": 0
}
```

**Processing Response:**
```json
{
  "status": "processing",
  "job_id": "abc123-def456-ghi789",
  "created_at": "2024-01-15T10:30:00.000Z",
  "attempts": 1
}
```

**Completed Response:**
```json
{
  "status": "completed",
  "job_id": "abc123-def456-ghi789",
  "created_at": "2024-01-15T10:30:00.000Z",
  "completed_at": "2024-01-15T10:30:45.000Z",
  "attempts": 1,
  "result": {
    "title": "5 Morning Habits for Success",
    "description": "...",
    "transcript": "...",
    "hook": "...",
    "format": "talking_head",
    "niche": "lifestyle",
    ...
  }
}
```

**Failed Response:**
```json
{
  "status": "failed",
  "job_id": "abc123-def456-ghi789",
  "created_at": "2024-01-15T10:30:00.000Z",
  "attempts": 3,
  "last_error": "Video unavailable or private"
}
```

**Status Values:**
- `pending` - Job is queued, waiting to be processed
- `processing` - Job is currently being processed
- `completed` - Job finished successfully, result available
- `failed` - Job failed after max retries
- `not_found` - Job ID doesn't exist

---

### Search Endpoints

#### `GET /search`

Search the global video library with full-text search and filters.

**Request:**
```bash
# Full-text search
curl "https://YOUR_API_URL/search?q=fitness+hooks"

# Filter by format and niche
curl "https://YOUR_API_URL/search?format=voiceover&niche=fitness&limit=20"

# Filter by creator
curl "https://YOUR_API_URL/search?creator=@productivityguru"

# Filter by platform with pagination
curl "https://YOUR_API_URL/search?platform=tiktok&limit=50&offset=100"

# Combined search
curl "https://YOUR_API_URL/search?q=morning+routine&niche=lifestyle&format=talking_head&limit=10"
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | - | Full-text search query (searches title, hook, transcript, description) |
| `format` | string | - | Filter by video format (see [formats](#video-formats-reference)) |
| `niche` | string | - | Filter by content niche (see [niches](#content-niches-reference)) |
| `platform` | string | - | Filter by platform: `"tiktok"` or `"instagram"` |
| `creator` | string | - | Filter by creator username |
| `limit` | int | 20 | Results per page (1-100) |
| `offset` | int | 0 | Pagination offset |

**Response:**
```json
{
  "success": true,
  "data": {
    "videos": [
      {
        "video_id": "a1b2c3d4e5f6g7h8",
        "title": "5 Gym Tips for Beginners",
        "description": "Essential tips for anyone starting their fitness journey",
        "hook": "Stop making these gym mistakes!",
        "format": "talking_head",
        "niche": "fitness",
        "niche_detail": "beginner workout tips and gym etiquette",
        "creator": "@fitnessguru",
        "platform": "tiktok",
        "save_count": 150,
        "image": "data:image/jpeg;base64,..."
      },
      {
        "video_id": "b2c3d4e5f6g7h8i9",
        "title": "High Protein Meal Prep",
        "description": "Easy meal prep for muscle building",
        "hook": "Here's what I eat in a day for gains",
        "format": "voiceover",
        "niche": "fitness",
        "niche_detail": "meal prep for bodybuilders",
        "secondary_niches": ["food"],
        "creator": "@mealprep101",
        "platform": "instagram",
        "save_count": 89,
        "image": "data:image/jpeg;base64,..."
      }
    ],
    "total": 245,
    "page": 0,
    "pages": 13,
    "limit": 20,
    "offset": 0
  },
  "meta": {
    "backend": "AlgoliaBackend",
    "warning": null
  }
}
```

**Search Backend Info:**

The `meta.backend` field tells you which search backend is being used:
- `AlgoliaBackend` - Full-text search with relevance ranking (optimal)
- `TypesenseBackend` - Self-hosted full-text search (optimal)
- `FirestoreBackend` - Limited search (filter-only, no full-text) - warning will be shown

---

#### `GET /search/formats`

Get all available video formats for filtering.

**Request:**
```bash
curl https://YOUR_API_URL/search/formats
```

**Response:**
```json
{
  "success": true,
  "data": {
    "formats": [
      {
        "id": "voiceover",
        "name": "Voiceover",
        "description": "Voice narration over footage/B-roll"
      },
      {
        "id": "talking_head",
        "name": "Talking Head",
        "description": "Creator speaking directly to camera"
      },
      {
        "id": "talking_back_forth",
        "name": "Talking Back Forth",
        "description": "Two perspectives/arguments presented"
      }
      // ... 18 more formats
    ],
    "total": 21
  }
}
```

---

#### `GET /search/niches`

Get all available content niches for filtering.

**Request:**
```bash
curl https://YOUR_API_URL/search/niches
```

**Response:**
```json
{
  "success": true,
  "data": {
    "niches": [
      {
        "id": "fitness",
        "name": "Fitness",
        "description": "Gym, workout, bodybuilding, yoga"
      },
      {
        "id": "food",
        "name": "Food",
        "description": "Cooking, recipes, meal prep, restaurants"
      },
      {
        "id": "business",
        "name": "Business",
        "description": "Entrepreneurship, startups, marketing"
      }
      // ... 18 more niches
    ],
    "total": 21
  }
}
```

---

#### `GET /search/status`

Get search service health and capabilities.

**Request:**
```bash
curl https://YOUR_API_URL/search/status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "backend": "AlgoliaBackend",
    "healthy": true,
    "features": {
      "full_text_search": true,
      "faceted_filtering": true,
      "relevance_ranking": true
    }
  }
}
```

---

### Video Endpoints

#### `GET /videos/{video_id}`

Get details for a specific video by ID.

**Request:**
```bash
curl https://YOUR_API_URL/videos/a1b2c3d4e5f6g7h8
```

**Response:**
```json
{
  "success": true,
  "data": {
    "video_id": "a1b2c3d4e5f6g7h8",
    "url": "https://www.tiktok.com/@creator/video/123",
    "normalized_url": "tiktok.com/@creator/video/123",
    "title": "5 Morning Habits for Success",
    "description": "Creator shares five powerful morning routines",
    "transcript": "Hey everyone! Today I'm sharing 5 morning habits...",
    "hook": "Hey everyone! Today I'm sharing 5 morning habits that changed my life.",
    "image": "data:image/jpeg;base64,...",
    "format": "talking_head",
    "niche": "lifestyle",
    "niche_detail": "morning routines and productivity habits",
    "secondary_niches": ["business", "motivation"],
    "creator": "@productivityguru",
    "platform": "tiktok",
    "hashtags": ["#morningroutine", "#productivity"],
    "created_at": "2024-01-15T10:30:00.000Z",
    "last_saved_at": "2024-01-16T14:20:00.000Z",
    "save_count": 45
  }
}
```

**Error Response (404):**
```json
{
  "detail": "Video not found: a1b2c3d4e5f6g7h8"
}
```

---

#### `GET /videos/stats`

Get statistics about the video library.

**Request:**
```bash
curl https://YOUR_API_URL/videos/stats
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "active",
    "total_videos": 1250,
    "top_videos": [
      {
        "video_id": "a1b2c3d4",
        "title": "This morning routine changed everything",
        "save_count": 523
      },
      {
        "video_id": "b2c3d4e5",
        "title": "Stop doing this at the gym",
        "save_count": 412
      },
      {
        "video_id": "c3d4e5f6",
        "title": "Easy meal prep for the week",
        "save_count": 398
      },
      {
        "video_id": "d4e5f6g7",
        "title": "How I made $10k last month",
        "save_count": 356
      },
      {
        "video_id": "e5f6g7h8",
        "title": "The best skincare routine",
        "save_count": 301
      }
    ]
  }
}
```

---

## Video Formats Reference

The API classifies videos into **21 production formats** based on how the content is presented. Use these format IDs for filtering with the `/search` endpoint.

| Format ID | Display Name | Description | Best For |
|-----------|--------------|-------------|----------|
| `voiceover` | Voiceover | Voice narration over footage/B-roll. Creator not visible on screen. | Educational content, documentaries, storytelling |
| `talking_head` | Talking Head | Creator speaking directly to camera, single angle. Most common format. | Tips, advice, personal stories, reviews |
| `talking_back_forth` | Talking Back & Forth | Two perspectives or arguments presented (like angel/devil on shoulders). | Debates, pros/cons, decision content |
| `reaction` | Reaction | Reacting to other content shown on screen. | Commentary, reviews, reactions to trends |
| `setting_changes` | Setting Changes | Multiple locations or outfit changes throughout the video. | Vlogs, fashion, travel montages |
| `whiteboard` | Whiteboard | Text, drawings, or explanations written/typed on screen. | Tutorials, explanations, lists |
| `shot_angle_change` | Shot Angle Change | Dynamic camera angles with multiple cuts. | High production content, music, action |
| `multitasking` | Multitasking | Creator doing an activity while talking (cooking, cleaning, working out). | GRWM, cooking, cleaning, workout vlogs |
| `visual` | Visual | Primarily visual content with minimal or no talking. | Aesthetic content, ASMR, art, satisfying videos |
| `green_screen` | Green Screen | Creator overlaid on a green screen background (news, images, videos). | News commentary, reactions, educational |
| `clone` | Clone | Same person appears multiple times in frame simultaneously. | Comedy sketches, arguments with self |
| `slideshow` | Slideshow | Image carousel with text overlay or voiceover. | Tips, lists, stories, photo dumps |
| `tutorial` | Tutorial | Step-by-step instructional content. | How-to guides, DIY, recipes, tech tutorials |
| `duet` | Duet | Side-by-side with another video (TikTok duet feature). | Reactions, collaborations, responses |
| `stitch` | Stitch | Response that starts with another creator's clip. | Responses, additions, corrections |
| `pov` | POV | Point-of-view storytelling format. | Roleplay, comedy, relatable content |
| `before_after` | Before & After | Transformation or comparison content. | Makeovers, renovations, progress |
| `day_in_life` | Day In Life | Day in the life vlog format (DITL). | Lifestyle, career, routine content |
| `interview` | Interview | Q&A or interview style with questions. | Expert interviews, Q&As, conversations |
| `list` | List | Listicle format (5 tips, 10 things, etc.). | Tips, recommendations, rankings |
| `other` | Other | Doesn't fit above categories. | Unique or hybrid formats |

### Format Selection in UI

```typescript
// Example: Building a format filter dropdown
const formatOptions = [
  { value: '', label: 'All Formats' },
  { value: 'talking_head', label: 'Talking Head' },
  { value: 'voiceover', label: 'Voiceover' },
  { value: 'tutorial', label: 'Tutorial' },
  { value: 'slideshow', label: 'Slideshow' },
  { value: 'reaction', label: 'Reaction' },
  { value: 'green_screen', label: 'Green Screen' },
  { value: 'pov', label: 'POV' },
  { value: 'list', label: 'Listicle' },
  { value: 'before_after', label: 'Before & After' },
  { value: 'day_in_life', label: 'Day In Life' },
  // ... etc
];
```

---

## Content Niches Reference

The API classifies videos into **21 content niches** based on the topic/subject matter. Use these niche IDs for filtering with the `/search` endpoint.

| Niche ID | Display Name | Description | Example Topics |
|----------|--------------|-------------|----------------|
| `fitness` | Fitness | Physical exercise and gym content | Gym workouts, bodybuilding, yoga, CrossFit, home workouts, exercise tips |
| `food` | Food | Cooking and food-related content | Recipes, meal prep, cooking tutorials, restaurant reviews, food reviews |
| `business` | Business | Entrepreneurship and professional growth | Startups, marketing, sales, side hustles, entrepreneurship, business tips |
| `finance` | Finance | Money and investment content | Investing, budgeting, crypto, real estate, saving money, passive income |
| `tech` | Tech | Technology and digital content | Software, AI, gadgets, coding tutorials, app reviews, tech news |
| `beauty` | Beauty | Cosmetics and skincare | Skincare routines, makeup tutorials, haircare, beauty tips, product reviews |
| `fashion` | Fashion | Clothing and style | Outfit ideas, styling tips, shopping hauls, fashion trends, thrift flips |
| `lifestyle` | Lifestyle | Daily life and organization | Daily routines, organization, productivity hacks, life tips, aesthetic living |
| `education` | Education | Learning and academics | Study tips, language learning, career advice, academic content, skills |
| `entertainment` | Entertainment | Comedy and pop culture | Comedy skits, memes, trends, pop culture, challenges, funny videos |
| `motivation` | Motivation | Mindset and self-improvement | Mindset, self-improvement, productivity, inspirational quotes, success |
| `relationships` | Relationships | Dating and social dynamics | Dating advice, marriage tips, friendship, social skills, family dynamics |
| `parenting` | Parenting | Kids and family life | Parenting tips, pregnancy, baby content, family vlogs, mom/dad life |
| `health` | Health | Wellness and medical | Mental health, wellness, nutrition, medical info, healthy living |
| `travel` | Travel | Destinations and adventures | Travel vlogs, destination guides, travel tips, adventure, hotels |
| `gaming` | Gaming | Video games and esports | Gameplay, game reviews, esports, gaming setup, game tips |
| `music` | Music | Musical content | Covers, music production, dance, instruments, song recommendations |
| `art` | Art | Creative and DIY content | Drawing, design, DIY projects, crafts, creative tutorials, art tips |
| `pets` | Pets | Animals and pet care | Dogs, cats, exotic pets, pet care tips, animal content, cute animals |
| `sports` | Sports | Athletic content | Specific sports, athletics, training, sports news, highlights |
| `other` | Other | Uncategorized content | Content that doesn't fit other categories |

### Niche Selection in UI

```typescript
// Example: Building a niche filter dropdown
const nicheOptions = [
  { value: '', label: 'All Niches' },
  { value: 'fitness', label: 'Fitness' },
  { value: 'food', label: 'Food & Cooking' },
  { value: 'business', label: 'Business' },
  { value: 'finance', label: 'Finance' },
  { value: 'tech', label: 'Tech' },
  { value: 'beauty', label: 'Beauty' },
  { value: 'fashion', label: 'Fashion' },
  { value: 'lifestyle', label: 'Lifestyle' },
  { value: 'education', label: 'Education' },
  { value: 'entertainment', label: 'Entertainment' },
  { value: 'motivation', label: 'Motivation' },
  { value: 'relationships', label: 'Relationships' },
  { value: 'parenting', label: 'Parenting' },
  { value: 'health', label: 'Health & Wellness' },
  { value: 'travel', label: 'Travel' },
  { value: 'gaming', label: 'Gaming' },
  { value: 'music', label: 'Music' },
  { value: 'art', label: 'Art & DIY' },
  { value: 'pets', label: 'Pets' },
  { value: 'sports', label: 'Sports' },
  { value: 'other', label: 'Other' },
];
```

---

## TypeScript Interfaces

Copy these interfaces to your frontend project for type-safe API integration:

```typescript
// types/api.ts

// ============================================
// Request Types
// ============================================

export interface ProcessRequest {
  url: string;
  localization?: string;
}

export interface SearchParams {
  q?: string;
  format?: VideoFormat;
  niche?: ContentNiche;
  platform?: 'tiktok' | 'instagram';
  creator?: string;
  limit?: number;
  offset?: number;
}

// ============================================
// Response Types
// ============================================

export interface CreatorContent {
  title: string;
  description: string | null;
  image: string | null;
  transcript: string | null;
  hook: string | null;
  format: VideoFormat | null;
  niche: ContentNiche | null;
  niche_detail: string | null;
  secondary_niches: string[] | null;
  creator: string | null;
  platform: 'tiktok' | 'instagram' | null;
  tags: string[] | null;
  cached: boolean | null;
}

export interface QueuedResponse {
  status: 'queued' | 'processing';
  job_id: string;
  message: string;
  check_url: string;
}

export interface JobStatusResponse {
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'not_found';
  job_id?: string;
  created_at?: string;
  completed_at?: string;
  attempts?: number;
  last_error?: string;
  result?: CreatorContent;
}

export interface SearchResponse {
  success: boolean;
  data: {
    videos: VideoSearchResult[];
    total: number;
    page: number;
    pages: number;
    limit: number;
    offset: number;
  };
  meta: {
    backend: string;
    warning: string | null;
  };
}

export interface VideoSearchResult {
  video_id: string;
  title: string;
  description: string | null;
  hook: string | null;
  format: VideoFormat | null;
  niche: ContentNiche | null;
  niche_detail: string | null;
  secondary_niches: string[] | null;
  creator: string | null;
  platform: 'tiktok' | 'instagram' | null;
  save_count: number;
  image: string | null;
}

export interface VideoDetails extends VideoSearchResult {
  url: string;
  normalized_url: string;
  transcript: string | null;
  hashtags: string[] | null;
  created_at: string;
  last_saved_at: string;
}

export interface FormatItem {
  id: VideoFormat;
  name: string;
  description: string;
}

export interface NicheItem {
  id: ContentNiche;
  name: string;
  description: string;
}

export interface FormatsResponse {
  success: boolean;
  data: {
    formats: FormatItem[];
    total: number;
  };
}

export interface NichesResponse {
  success: boolean;
  data: {
    niches: NicheItem[];
    total: number;
  };
}

export interface VideoStatsResponse {
  success: boolean;
  data: {
    status: string;
    total_videos: number;
    top_videos: {
      video_id: string;
      title: string;
      save_count: number;
    }[];
  };
}

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  timestamp: string;
  environment: string;
  project_id: string;
  version: string;
  services: Record<string, string>;
}

// ============================================
// Enums
// ============================================

export type VideoFormat =
  | 'voiceover'
  | 'talking_head'
  | 'talking_back_forth'
  | 'reaction'
  | 'setting_changes'
  | 'whiteboard'
  | 'shot_angle_change'
  | 'multitasking'
  | 'visual'
  | 'green_screen'
  | 'clone'
  | 'slideshow'
  | 'tutorial'
  | 'duet'
  | 'stitch'
  | 'pov'
  | 'before_after'
  | 'day_in_life'
  | 'interview'
  | 'list'
  | 'other';

export type ContentNiche =
  | 'fitness'
  | 'food'
  | 'business'
  | 'finance'
  | 'tech'
  | 'beauty'
  | 'fashion'
  | 'lifestyle'
  | 'education'
  | 'entertainment'
  | 'motivation'
  | 'relationships'
  | 'parenting'
  | 'health'
  | 'travel'
  | 'gaming'
  | 'music'
  | 'art'
  | 'pets'
  | 'sports'
  | 'other';

// ============================================
// Error Types
// ============================================

export interface APIError {
  error: {
    type: string;
    message: string;
    code: string;
    details?: Record<string, unknown>;
  };
  request_id: string;
  timestamp: string;
  path: string;
}
```

---

## Firestore Data Structure

The backend uses Firestore for caching and storing video data. You can also access Firestore directly from the frontend for user-specific operations.

### Collections Overview

| Collection | Purpose | Access |
|------------|---------|--------|
| `videos` | Global video library (searchable by all users) | Read-only from frontend |
| `users/{uid}/saved_videos` | Per-user saved videos with custom tags | Read/write per user |
| `parser_cache` | Processing cache | Backend only |

### `videos` Collection Schema

```typescript
// Document ID: SHA256 hash of normalized URL (first 16 chars)
interface VideoDocument {
  video_id: string;            // Same as document ID
  url: string;                 // Original video URL
  normalized_url: string;      // Normalized URL for deduplication
  
  // Core content from AI extraction
  title: string | null;
  description: string | null;
  transcript: string | null;
  hook: string | null;
  image: string | null;        // Base64-encoded JPEG
  
  // Classification (AI-detected)
  format: VideoFormat | null;
  niche: ContentNiche | null;
  niche_detail: string | null;
  secondary_niches: string[] | null;
  
  // Metadata
  creator: string | null;
  platform: 'tiktok' | 'instagram' | null;
  hashtags: string[] | null;
  
  // Timestamps and stats
  created_at: Timestamp;
  last_saved_at: Timestamp;
  save_count: number;          // How many users saved this video
}
```

### `users/{uid}/saved_videos` Collection Schema

```typescript
// Document ID: Same as video_id from videos collection
interface UserSavedVideoDocument {
  video_id: string;            // Reference to videos collection
  
  // User-specific data
  user_tags: string[];         // User's custom tags
  user_notes: string | null;   // User's notes
  collections: string[];       // User's folders/collections
  
  // Timestamps
  saved_at: Timestamp;
  updated_at: Timestamp;
}
```

### Firestore Access Examples

```typescript
// lib/firestore.ts
import { 
  collection, 
  doc, 
  getDoc, 
  getDocs, 
  query, 
  where, 
  orderBy, 
  limit,
  setDoc,
  updateDoc,
  deleteDoc,
  increment,
  serverTimestamp
} from 'firebase/firestore';
import { db } from './firebase';

// Get a video by ID
export async function getVideo(videoId: string) {
  const docRef = doc(db, 'videos', videoId);
  const docSnap = await getDoc(docRef);
  
  if (docSnap.exists()) {
    return { id: docSnap.id, ...docSnap.data() };
  }
  return null;
}

// Get user's saved videos
export async function getUserSavedVideos(userId: string, limitCount = 50) {
  const savedVideosRef = collection(db, 'users', userId, 'saved_videos');
  const q = query(
    savedVideosRef,
    orderBy('saved_at', 'desc'),
    limit(limitCount)
  );
  
  const snapshot = await getDocs(q);
  return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
}

// Save a video for user with custom tags
export async function saveVideoForUser(
  userId: string, 
  videoId: string, 
  tags: string[] = [],
  notes: string | null = null
) {
  const userVideoRef = doc(db, 'users', userId, 'saved_videos', videoId);
  
  await setDoc(userVideoRef, {
    video_id: videoId,
    user_tags: tags,
    user_notes: notes,
    collections: [],
    saved_at: serverTimestamp(),
    updated_at: serverTimestamp(),
  }, { merge: true });
  
  // Increment save count on global video
  const videoRef = doc(db, 'videos', videoId);
  await updateDoc(videoRef, {
    save_count: increment(1),
    last_saved_at: serverTimestamp(),
  });
}

// Update user tags for a saved video
export async function updateUserTags(
  userId: string,
  videoId: string,
  tags: string[]
) {
  const userVideoRef = doc(db, 'users', userId, 'saved_videos', videoId);
  await updateDoc(userVideoRef, {
    user_tags: tags,
    updated_at: serverTimestamp(),
  });
}

// Remove video from user's saved list
export async function unsaveVideo(userId: string, videoId: string) {
  const userVideoRef = doc(db, 'users', userId, 'saved_videos', videoId);
  await deleteDoc(userVideoRef);
  
  // Decrement save count on global video
  const videoRef = doc(db, 'videos', videoId);
  await updateDoc(videoRef, {
    save_count: increment(-1),
  });
}
```

### Recommended Firestore Security Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    
    // Global videos collection - read-only for authenticated users
    match /videos/{videoId} {
      allow read: if request.auth != null;
      allow write: if false; // Only backend can write
    }
    
    // User-specific saved videos
    match /users/{userId}/saved_videos/{videoId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    
    // User document
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    
    // Cache collection - backend only
    match /parser_cache/{docId} {
      allow read, write: if false;
    }
  }
}
```

---

## React/Next.js Integration Examples

### API Service Layer

```typescript
// services/api.ts
import { 
  ProcessRequest, 
  CreatorContent, 
  QueuedResponse, 
  SearchParams, 
  SearchResponse,
  JobStatusResponse,
  FormatsResponse,
  NichesResponse,
  VideoDetails,
  VideoStatsResponse
} from '@/types/api';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

class ApiService {
  private baseUrl: string;
  private appCheckToken: string | null = null;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  setAppCheckToken(token: string | null) {
    this.appCheckToken = token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.appCheckToken) {
      (headers as Record<string, string>)['X-Firebase-AppCheck'] = this.appCheckToken;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || error.message || 'API request failed');
    }

    return response.json();
  }

  // ============================================
  // Video Processing
  // ============================================

  async processVideo(
    request: ProcessRequest
  ): Promise<CreatorContent | QueuedResponse> {
    return this.request('/process', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getJobStatus(jobId: string): Promise<JobStatusResponse> {
    return this.request(`/status/${jobId}`);
  }

  async processVideoWithPolling(
    request: ProcessRequest,
    onProgress?: (status: string) => void
  ): Promise<CreatorContent> {
    const result = await this.processVideo(request);

    // If direct result, return immediately
    if ('title' in result) {
      return result as CreatorContent;
    }

    // Poll for result
    const queuedResult = result as QueuedResponse;
    const jobId = queuedResult.job_id;

    while (true) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const status = await this.getJobStatus(jobId);
      onProgress?.(status.status);

      if (status.status === 'completed' && status.result) {
        return status.result;
      }

      if (status.status === 'failed') {
        throw new Error(status.last_error || 'Processing failed');
      }

      if (status.status === 'not_found') {
        throw new Error('Job not found');
      }
    }
  }

  // ============================================
  // Search
  // ============================================

  async search(params: SearchParams): Promise<SearchResponse> {
    const searchParams = new URLSearchParams();
    
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.set(key, String(value));
      }
    });

    return this.request(`/search?${searchParams.toString()}`);
  }

  async getFormats(): Promise<FormatsResponse> {
    return this.request('/search/formats');
  }

  async getNiches(): Promise<NichesResponse> {
    return this.request('/search/niches');
  }

  // ============================================
  // Videos
  // ============================================

  async getVideo(videoId: string): Promise<{ success: boolean; data: VideoDetails }> {
    return this.request(`/videos/${videoId}`);
  }

  async getVideoStats(): Promise<VideoStatsResponse> {
    return this.request('/videos/stats');
  }

  // ============================================
  // Health
  // ============================================

  async getHealth() {
    return this.request('/health');
  }
}

export const api = new ApiService();
export default api;
```

### React Hooks

```typescript
// hooks/useVideoProcessor.ts
import { useState, useCallback } from 'react';
import { api } from '@/services/api';
import { CreatorContent, ProcessRequest } from '@/types/api';

interface UseVideoProcessorResult {
  processVideo: (url: string, localization?: string) => Promise<CreatorContent>;
  isLoading: boolean;
  error: string | null;
  progress: string | null;
}

export function useVideoProcessor(): UseVideoProcessorResult {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);

  const processVideo = useCallback(async (
    url: string, 
    localization?: string
  ): Promise<CreatorContent> => {
    setIsLoading(true);
    setError(null);
    setProgress('Starting...');

    try {
      const request: ProcessRequest = { url };
      if (localization) {
        request.localization = localization;
      }

      const result = await api.processVideoWithPolling(request, (status) => {
        setProgress(status === 'pending' ? 'Queued...' : 'Processing...');
      });

      setProgress(null);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Processing failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { processVideo, isLoading, error, progress };
}
```

```typescript
// hooks/useVideoSearch.ts
import { useState, useCallback, useEffect } from 'react';
import { api } from '@/services/api';
import { SearchParams, VideoSearchResult } from '@/types/api';

interface UseVideoSearchResult {
  videos: VideoSearchResult[];
  total: number;
  page: number;
  pages: number;
  isLoading: boolean;
  error: string | null;
  search: (params: SearchParams) => Promise<void>;
  loadMore: () => Promise<void>;
}

export function useVideoSearch(initialParams?: SearchParams): UseVideoSearchResult {
  const [videos, setVideos] = useState<VideoSearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pages, setPages] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentParams, setCurrentParams] = useState<SearchParams>(initialParams || {});

  const search = useCallback(async (params: SearchParams) => {
    setIsLoading(true);
    setError(null);
    setCurrentParams(params);

    try {
      const response = await api.search({ ...params, offset: 0 });
      setVideos(response.data.videos);
      setTotal(response.data.total);
      setPage(response.data.page);
      setPages(response.data.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadMore = useCallback(async () => {
    if (isLoading || page >= pages - 1) return;

    setIsLoading(true);
    const limit = currentParams.limit || 20;
    const newOffset = (page + 1) * limit;

    try {
      const response = await api.search({ ...currentParams, offset: newOffset });
      setVideos(prev => [...prev, ...response.data.videos]);
      setPage(response.data.page);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Load more failed');
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, page, pages, currentParams]);

  // Initial search
  useEffect(() => {
    if (initialParams) {
      search(initialParams);
    }
  }, []);

  return { videos, total, page, pages, isLoading, error, search, loadMore };
}
```

```typescript
// hooks/useFormatsAndNiches.ts
import { useState, useEffect } from 'react';
import { api } from '@/services/api';
import { FormatItem, NicheItem } from '@/types/api';

interface UseFormatsAndNichesResult {
  formats: FormatItem[];
  niches: NicheItem[];
  isLoading: boolean;
  error: string | null;
}

export function useFormatsAndNiches(): UseFormatsAndNichesResult {
  const [formats, setFormats] = useState<FormatItem[]>([]);
  const [niches, setNiches] = useState<NicheItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [formatsRes, nichesRes] = await Promise.all([
          api.getFormats(),
          api.getNiches(),
        ]);
        setFormats(formatsRes.data.formats);
        setNiches(nichesRes.data.niches);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load filters');
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, []);

  return { formats, niches, isLoading, error };
}
```

### Example Components

```tsx
// components/VideoProcessor.tsx
import { useState } from 'react';
import { useVideoProcessor } from '@/hooks/useVideoProcessor';
import { CreatorContent } from '@/types/api';

export function VideoProcessor() {
  const [url, setUrl] = useState('');
  const [result, setResult] = useState<CreatorContent | null>(null);
  const { processVideo, isLoading, error, progress } = useVideoProcessor();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const data = await processVideo(url);
      setResult(data);
    } catch {
      // Error is already in the hook state
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Paste TikTok or Instagram URL..."
          className="w-full p-3 border rounded-lg"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !url}
          className="w-full p-3 bg-blue-600 text-white rounded-lg disabled:opacity-50"
        >
          {isLoading ? progress || 'Processing...' : 'Process Video'}
        </button>
      </form>

      {error && (
        <div className="mt-4 p-4 bg-red-100 text-red-700 rounded-lg">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-4">
          <h2 className="text-xl font-bold">{result.title}</h2>
          
          {result.image && (
            <img 
              src={result.image} 
              alt={result.title}
              className="w-full rounded-lg"
            />
          )}
          
          <div className="flex gap-2">
            <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm">
              {result.format}
            </span>
            <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
              {result.niche}
            </span>
            <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
              {result.platform}
            </span>
          </div>

          <div>
            <h3 className="font-semibold">Hook:</h3>
            <p className="text-gray-700 italic">"{result.hook}"</p>
          </div>

          <div>
            <h3 className="font-semibold">Transcript:</h3>
            <p className="text-gray-600 whitespace-pre-wrap">{result.transcript}</p>
          </div>

          {result.tags && result.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {result.tags.map((tag, i) => (
                <span key={i} className="text-blue-600 text-sm">{tag}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

```tsx
// components/VideoSearch.tsx
import { useState } from 'react';
import { useVideoSearch } from '@/hooks/useVideoSearch';
import { useFormatsAndNiches } from '@/hooks/useFormatsAndNiches';

export function VideoSearch() {
  const [query, setQuery] = useState('');
  const [selectedFormat, setSelectedFormat] = useState('');
  const [selectedNiche, setSelectedNiche] = useState('');
  
  const { formats, niches, isLoading: filtersLoading } = useFormatsAndNiches();
  const { videos, total, isLoading, error, search, loadMore, pages, page } = useVideoSearch();

  const handleSearch = () => {
    search({
      q: query || undefined,
      format: selectedFormat || undefined,
      niche: selectedNiche || undefined,
      limit: 20,
    });
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Search Form */}
      <div className="space-y-4 mb-8">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search videos..."
          className="w-full p-3 border rounded-lg"
        />
        
        <div className="flex gap-4">
          <select
            value={selectedFormat}
            onChange={(e) => setSelectedFormat(e.target.value)}
            className="flex-1 p-3 border rounded-lg"
            disabled={filtersLoading}
          >
            <option value="">All Formats</option>
            {formats.map((format) => (
              <option key={format.id} value={format.id}>
                {format.name}
              </option>
            ))}
          </select>

          <select
            value={selectedNiche}
            onChange={(e) => setSelectedNiche(e.target.value)}
            className="flex-1 p-3 border rounded-lg"
            disabled={filtersLoading}
          >
            <option value="">All Niches</option>
            {niches.map((niche) => (
              <option key={niche.id} value={niche.id}>
                {niche.name}
              </option>
            ))}
          </select>

          <button
            onClick={handleSearch}
            disabled={isLoading}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg disabled:opacity-50"
          >
            Search
          </button>
        </div>
      </div>

      {/* Results */}
      {error && (
        <div className="p-4 bg-red-100 text-red-700 rounded-lg mb-4">
          {error}
        </div>
      )}

      {total > 0 && (
        <p className="text-gray-600 mb-4">Found {total} videos</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {videos.map((video) => (
          <div key={video.video_id} className="border rounded-lg overflow-hidden">
            {video.image && (
              <img 
                src={video.image} 
                alt={video.title}
                className="w-full h-48 object-cover"
              />
            )}
            <div className="p-4">
              <h3 className="font-semibold line-clamp-2">{video.title}</h3>
              <p className="text-sm text-gray-600 mt-1">{video.creator}</p>
              <div className="flex gap-2 mt-2">
                <span className="text-xs px-2 py-1 bg-purple-100 text-purple-700 rounded">
                  {video.format}
                </span>
                <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">
                  {video.niche}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Saved {video.save_count} times
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Load More */}
      {page < pages - 1 && (
        <div className="text-center mt-8">
          <button
            onClick={loadMore}
            disabled={isLoading}
            className="px-6 py-3 border border-blue-600 text-blue-600 rounded-lg disabled:opacity-50"
          >
            {isLoading ? 'Loading...' : 'Load More'}
          </button>
        </div>
      )}
    </div>
  );
}
```

---

## Error Handling

### Error Response Format

All API errors follow this structure:

```json
{
  "error": {
    "type": "ValidationError",
    "message": "Invalid URL format",
    "code": "VALIDATION_ERROR",
    "details": {
      "field": "url",
      "value": "not-a-url"
    }
  },
  "request_id": "abc123-def456",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "path": "/process"
}
```

### Common Error Codes

| HTTP Status | Error Type | Description |
|-------------|------------|-------------|
| 400 | `ValidationError` | Invalid request data (bad URL, invalid parameters) |
| 401 | `AuthenticationError` | Missing or invalid App Check token (when required) |
| 404 | `NotFoundError` | Resource not found (job, video) |
| 429 | `RateLimitError` | Too many requests |
| 500 | `ProcessingError` | Video processing failed |
| 503 | `ServiceUnavailable` | Backend service unavailable |

### Frontend Error Handling

```typescript
// utils/errorHandler.ts
import { APIError } from '@/types/api';

export function handleAPIError(error: unknown): string {
  if (error instanceof Response) {
    return `API Error: ${error.status} ${error.statusText}`;
  }

  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'object' && error !== null && 'error' in error) {
    const apiError = error as APIError;
    return apiError.error.message;
  }

  return 'An unexpected error occurred';
}

export function isRateLimitError(error: unknown): boolean {
  if (error instanceof Response) {
    return error.status === 429;
  }
  return false;
}

export function isAuthError(error: unknown): boolean {
  if (error instanceof Response) {
    return error.status === 401;
  }
  return false;
}
```

### Retry Logic

```typescript
// utils/retry.ts
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      
      // Don't retry on 4xx errors (except 429)
      if (error instanceof Response && error.status >= 400 && error.status < 500 && error.status !== 429) {
        throw error;
      }

      if (attempt < maxRetries - 1) {
        const delay = baseDelay * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError;
}
```

---

## Testing Guide

### Local Development

1. **Start the backend locally:**
   ```bash
   cd creva-backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8080
   ```

2. **Update your frontend `.env.local`:**
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8080
   ```

3. **Test endpoints with curl:**
   ```bash
   # Health check
   curl http://localhost:8080/health

   # Get formats
   curl http://localhost:8080/search/formats

   # Process a video
   curl -X POST http://localhost:8080/process \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.tiktok.com/@creator/video/123"}'
   ```

### API Documentation

When running locally, access interactive API docs at:
- **Swagger UI:** http://localhost:8080/docs
- **ReDoc:** http://localhost:8080/redoc

> Note: These are disabled in production.

### Testing with Jest/Vitest

```typescript
// __tests__/api.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '@/services/api';

describe('API Service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('should fetch formats', async () => {
    const mockResponse = {
      success: true,
      data: {
        formats: [
          { id: 'voiceover', name: 'Voiceover', description: 'Voice narration' },
        ],
        total: 1,
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await api.getFormats();
    
    expect(result.success).toBe(true);
    expect(result.data.formats).toHaveLength(1);
    expect(result.data.formats[0].id).toBe('voiceover');
  });

  it('should handle processing errors', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: () => Promise.resolve({
        detail: 'Invalid URL format',
      }),
    });

    await expect(api.processVideo({ url: 'invalid' })).rejects.toThrow('Invalid URL format');
  });
});
```

### Postman/Insomnia Collection

Import this collection for quick API testing:

```json
{
  "info": {
    "name": "Creva API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "baseUrl",
      "value": "http://localhost:8080"
    }
  ],
  "item": [
    {
      "name": "Health",
      "request": {
        "method": "GET",
        "url": "{{baseUrl}}/health"
      }
    },
    {
      "name": "Get Formats",
      "request": {
        "method": "GET",
        "url": "{{baseUrl}}/search/formats"
      }
    },
    {
      "name": "Get Niches",
      "request": {
        "method": "GET",
        "url": "{{baseUrl}}/search/niches"
      }
    },
    {
      "name": "Search Videos",
      "request": {
        "method": "GET",
        "url": {
          "raw": "{{baseUrl}}/search?niche=fitness&format=talking_head&limit=10",
          "query": [
            {"key": "niche", "value": "fitness"},
            {"key": "format", "value": "talking_head"},
            {"key": "limit", "value": "10"}
          ]
        }
      }
    },
    {
      "name": "Process Video",
      "request": {
        "method": "POST",
        "url": "{{baseUrl}}/process",
        "header": [
          {"key": "Content-Type", "value": "application/json"}
        ],
        "body": {
          "mode": "raw",
          "raw": "{\"url\": \"https://www.tiktok.com/@creator/video/123\"}"
        }
      }
    },
    {
      "name": "Check Job Status",
      "request": {
        "method": "GET",
        "url": "{{baseUrl}}/status/{{jobId}}"
      }
    }
  ]
}
```

---

## Quick Reference Card

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/status` | System status |
| POST | `/process` | Process video URL |
| GET | `/status/{job_id}` | Check job status |
| GET | `/search` | Search videos |
| GET | `/search/formats` | Get 21 video formats |
| GET | `/search/niches` | Get 21 content niches |
| GET | `/search/status` | Search service status |
| GET | `/videos/{video_id}` | Get video details |
| GET | `/videos/stats` | Library statistics |

### Key Response Fields

| Field | Description |
|-------|-------------|
| `transcript` | Full text of everything spoken (Priority #1) |
| `hook` | Opening attention-grabber (first 10-30 sec) |
| `format` | How the video is produced (21 options) |
| `niche` | What topic the video covers (21 options) |
| `niche_detail` | Specific subcategory |
| `image` | Base64 JPEG thumbnail |

### Environment Setup

```env
NEXT_PUBLIC_API_URL=https://creva-parser-xxx.run.app
NEXT_PUBLIC_FIREBASE_PROJECT_ID=creva-e6435
```

---

## Support

For questions or issues with the API:
1. Check the API health: `GET /health`
2. Review error responses for specific error codes
3. Check the Firestore console for data issues
4. Contact the backend team with the `request_id` from error responses

---

*Last updated: December 2024*
*API Version: 3.0.0*

