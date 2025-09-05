# Refactoring Plan: Sets (Workout) → Zest (Relationship Content)

## Overview
Transform the backend from parsing workout videos to extracting relationship/lifestyle content from Instagram and TikTok posts.

## Current State (Sets - Workout Parser)
- **Purpose**: Extract structured workout data from videos
- **Output**: Exercise lists, sets, reps, muscle groups
- **Focus**: Fitness and workout content

## Target State (Zest - Relationship Content Parser)
- **Purpose**: Extract relationship/lifestyle content from social media posts
- **Output**: Title, description, image, location
- **Focus**: Relationship advice, date ideas, lifestyle content

## Data Model Changes

### Current WorkoutData Structure
```json
{
  "title": "Full Body HIIT Workout",
  "description": "Intense 15-minute workout",
  "workout_type": "hiit",
  "duration_minutes": 15,
  "difficulty_level": 8,
  "exercises": [...],
  "tags": ["hiit", "cardio"],
  "creator": "@fitnessuser"
}
```

### New RelationshipContent Structure
```json
{
  "title": "Romantic Date Night Ideas",
  "description": "Creative and fun date ideas for couples",
  "image": "https://...",  // Main image from post/video
  "location": "New York, NY",  // Location if available
  "content_type": "date_idea",  // Type of relationship content
  "mood": "romantic",  // Mood/vibe of content
  "occasion": "date_night",  // Relevant occasion
  "tips": ["tip1", "tip2"],  // Extracted tips/advice
  "tags": ["datenight", "romance"],
  "creator": "@relationshipcoach"
}
```

## Key Files to Modify

### 1. Data Models (`src/models/`)
- **responses.py**: Replace WorkoutData with RelationshipContent
- **parser_result.py**: Keep VideoMetadata, update for relationship context

### 2. AI Service (`src/services/genai_service.py`)
- Update prompts from fitness to relationship content
- Change extraction logic for title, description, image, location
- Remove exercise-specific analysis

### 3. API Endpoints (`src/api/process.py`)
- Keep same structure but update response types
- Update documentation strings

### 4. Cache Service (`src/services/cache_service.py`)
- Update cache keys if needed
- Ensure compatibility with new data structure

### 5. Documentation
- **README.md**: Complete rewrite for Zest
- **main.py**: Update FastAPI metadata and descriptions
- **API docs**: Update all endpoint descriptions

### 6. Branding Updates
- Service name: workout-parser → relationship-parser
- API title: "Social Media Workout Parser" → "Zest - Relationship Content Parser"
- All references to "workout" → "content" or "relationship content"

## Implementation Steps

### Phase 1: Data Models
1. Create new RelationshipContent model
2. Update response models
3. Remove workout-specific models

### Phase 2: Core Logic
1. Update GenAI prompts for relationship content
2. Modify video processor to extract main image
3. Update location extraction logic

### Phase 3: API & Services
1. Update API endpoints
2. Modify cache service
3. Update queue service messages

### Phase 4: Documentation & Branding
1. Rewrite README for Zest
2. Update all code comments
3. Update environment variables and configs

### Phase 5: Testing
1. Test with relationship-focused TikTok/Instagram URLs
2. Verify image extraction
3. Validate location parsing

## Backwards Compatibility
- This is a complete refactor, no backwards compatibility maintained
- New API structure for relationship content
- Cache will be incompatible with old workout data

## Environment Variables
No changes needed to:
- GOOGLE_CLOUD_PROJECT_ID
- SCRAPECREATORS_API_KEY
- Other infrastructure variables

## Deployment Considerations
- Service name change in Cloud Run
- Update monitoring dashboards
- Clear existing cache data