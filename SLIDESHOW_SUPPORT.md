# TikTok Slideshow Support

This document describes the comprehensive slideshow support added to the TikTok Workout Parser backend.

## Overview

TikTok slideshows are multi-image posts that display a series of images instead of a traditional video. These are commonly used for:
- Step-by-step workout tutorials
- Before/after fitness transformations
- Exercise form demonstrations
- Workout routine breakdowns

## Implementation Details

### 1. Enhanced Data Models

**`SlideshowImage`** - Represents individual images in a slideshow:
```python
class SlideshowImage(BaseModel):
    url: str                    # Direct image URL
    width: Optional[int]        # Image width in pixels
    height: Optional[int]       # Image height in pixels  
    index: int                  # Position in slideshow (0-based)
```

**`VideoMetadata`** - Extended to support slideshow metadata:
```python
# New slideshow-specific fields:
is_slideshow: bool = False                              # Whether content is slideshow
slideshow_images: Optional[List[SlideshowImage]] = None # Image metadata
slideshow_duration: Optional[float] = None             # Total duration if timed
image_count: Optional[int] = None                       # Number of images
```

### 2. ScrapeCreators API Integration

The implementation leverages ScrapeCreators' TikTok API which provides:
- **Slideshow Detection**: Via `image_post_info` field in API response
- **High-Quality Images**: Multiple resolution options per image
- **Metadata Extraction**: Image dimensions, order, and URLs
- **Transcript Support**: Speech-to-text for slideshow narration

### 3. Enhanced TikTok Scraper

**Automatic Detection**:
```python
# The scraper automatically detects slideshow vs video content
api_data = await scraper.fetch_tiktok_data(url)
metadata = scraper.extract_metadata(api_data)

if metadata.is_slideshow:
    print(f"Found slideshow with {metadata.image_count} images")
else:
    print("Regular video content")
```

**Slideshow-Specific Methods**:
```python
# Download all slideshow images
slideshow_images, metadata, transcript = await scraper.scrape_tiktok_slideshow(url)

# Get slideshow image metadata only
image_objects = scraper.get_slideshow_images(api_data)

# Download image data as bytes
image_contents = await scraper.download_slideshow_images(api_data)
```

**Unified Interface**:
```python
# Works for both videos and slideshows
content, metadata, transcript = await scraper.scrape_tiktok_complete(url)

# For slideshows, content will be the first image
# All images are available in metadata.slideshow_images
```

### 4. AI Analysis Enhancement

**Multi-Image Analysis**:
- Gemini 2.0 Flash analyzes ALL slideshow images together
- Understands exercise sequences across multiple images
- Extracts comprehensive workout information from visual content

**GenAI Service Pool Integration**:
```python
# Analyze slideshow with multiple images
workout_json = await genai_pool.analyze_slideshow(
    slideshow_images=image_bytes_list,
    transcript=transcript_text,
    caption=caption_text
)
```

**Enhanced Prompting**:
- Specialized prompts for slideshow analysis
- Instructions to analyze image sequences
- Better extraction of step-by-step exercises

### 5. Worker Service Integration

**Automatic Content Type Handling**:
```python
# Worker automatically detects and processes slideshow content
if metadata_dict.get("is_slideshow", False):
    # Download all images and analyze with AI
    slideshow_images, _, transcript = await scraper.scrape_tiktok_slideshow(url)
    workout_json = await genai_pool.analyze_slideshow(slideshow_images, transcript, caption)
else:
    # Process as regular video
    silent_video = await processor.remove_audio(video_content)
    workout_json = await genai_pool.analyze_video(silent_video, transcript, caption)
```

## Usage Examples

### Basic Slideshow Detection

```python
from src.services.tiktok_scraper import TikTokScraper

scraper = TikTokScraper()

# Check if URL contains a slideshow
info = await scraper.get_video_info("https://www.tiktok.com/@user/video/123")
metadata = info["metadata"]

if metadata["is_slideshow"]:
    print(f"Slideshow with {metadata['image_count']} images")
    print(f"Duration: {metadata['slideshow_duration']} seconds")
```

### Complete Slideshow Processing

```python
# Download and process slideshow
slideshow_images, metadata, transcript = await scraper.scrape_tiktok_slideshow(url)

print(f"Downloaded {len(slideshow_images)} images")
print(f"Transcript: {transcript}")

# Each slideshow_images[i] contains image bytes
# metadata.slideshow_images contains SlideshowImage objects with URLs and dimensions
```

### Worker Integration

The worker service automatically handles slideshows without any code changes needed. Simply submit a slideshow TikTok URL to the queue and it will:

1. Detect slideshow content automatically
2. Download all images at high resolution
3. Analyze with Gemini 2.0 Flash using all images
4. Extract workout information considering the full sequence
5. Cache and return structured workout data

## API Response Format

### Slideshow Detection Response

```json
{
  "metadata": {
    "title": "5 Minute Morning Routine",
    "is_slideshow": true,
    "image_count": 6,
    "slideshow_duration": 15.0,
    "slideshow_images": [
      {
        "url": "https://p16-sign.tiktokcdn.com/...",
        "width": 720,
        "height": 1280,
        "index": 0
      }
    ],
    "author": "fitness_coach",
    "view_count": 125000,
    "like_count": 8500
  },
  "transcript": "Here's my quick morning routine..."
}
```

### Workout Analysis Response

Slideshow analysis produces the same structured workout JSON as videos:

```json
{
  "title": "Morning Mobility Routine",
  "workout_type": "mobility",
  "exercises": [
    {
      "name": "Neck Rolls",
      "muscle_groups": ["neck"],
      "equipment": "None",
      "sets": [{"reps": 10, "rest_seconds": 5}],
      "instructions": "Slowly roll your head in circles as shown in image 1-2"
    }
  ],
  "difficulty_level": 3,
  "tags": ["morning", "mobility", "quick"]
}
```

## Error Handling

### Common Scenarios

1. **Invalid Slideshow URL**: Returns clear error message
2. **Image Download Failures**: Continues with available images, logs warnings
3. **Mixed Content**: Automatically detects and handles appropriately
4. **API Rate Limits**: Handled by existing retry mechanisms

### Fallback Behavior

```python
try:
    slideshow_images, metadata, transcript = await scraper.scrape_tiktok_slideshow(url)
except Exception as e:
    if "not a slideshow" in str(e):
        # Fall back to regular video processing
        content, metadata, transcript = await scraper.scrape_tiktok_complete(url)
```

## Performance Considerations

### Optimizations Implemented

1. **Parallel Image Downloads**: All slideshow images downloaded concurrently
2. **Smart Content Detection**: Minimal API calls to detect content type
3. **Efficient Caching**: Slideshow metadata cached like regular videos
4. **Resource Management**: Proper cleanup of image data after processing

### Resource Usage

- **Memory**: Higher usage due to multiple images in memory
- **Network**: More bandwidth for downloading multiple high-res images
- **Processing**: Gemini 2.0 Flash handles multiple images efficiently
- **Storage**: Slideshow results cached same as videos

## Testing

Use the provided test script:

```bash
python test_slideshow.py
```

The test script will:
1. Validate environment setup
2. Test slideshow detection
3. Verify image download functionality
4. Check metadata extraction
5. Validate AI analysis (if configured)

## Configuration

No additional configuration required. Slideshow support works with existing:
- `SCRAPECREATORS_API_KEY` for data access
- `GOOGLE_CLOUD_PROJECT_ID` for AI analysis
- Standard worker and queue configurations

## Limitations

1. **Platform Support**: Currently TikTok only (Instagram slideshows planned)
2. **Image Formats**: Supports JPEG/WebP from TikTok's CDN
3. **Count Limits**: Up to 35 images per slideshow (TikTok's limit)
4. **Analysis Time**: Longer processing due to multiple image analysis

## Future Enhancements

1. **Instagram Slideshow Support**: Extend to Instagram carousel posts
2. **Image Caching**: Cache individual images for faster re-processing
3. **Selective Download**: Option to download specific image resolutions
4. **Video Generation**: Create videos from slideshow images for standard processing

## Troubleshooting

### Common Issues

**"This is not a slideshow" Error**:
- Verify URL contains a slideshow (multiple images, not video)
- Check ScrapeCreators API key validity
- Ensure URL is accessible and public

**Empty Image Downloads**:
- Check network connectivity
- Verify ScrapeCreators API quota
- Review logs for specific image URLs failing

**AI Analysis Failures**:
- Ensure Gemini 2.0 Flash is configured correctly
- Check if images contain recognizable workout content
- Verify Google Cloud credentials and quotas

For additional support, check the main application logs and ensure all environment variables are properly configured.