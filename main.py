from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv

from src.services.tiktok_scraper import TikTokScraper, ScrapingOptions, APIError, NetworkError, ValidationError
from src.services.vertex_ai_service import VertexAIService
from src.worker.video_processor import VideoProcessor

load_dotenv()

# Debug: Print API key status at startup
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_key = os.getenv("SCRAPECREATORS_API_KEY")
logger.info(f"API Key loaded: {'Yes' if api_key else 'No'}")
if api_key:
    logger.info(f"API Key starts with: {api_key[:10]}...")

app = FastAPI(title="TikTok Workout Parser")

scraper = TikTokScraper()
vertex_ai = VertexAIService()
video_processor = VideoProcessor()


class ProcessRequest(BaseModel):
    url: str


@app.post("/process")
async def process_video(request: ProcessRequest):
    """Process a TikTok video and return workout JSON"""
    try:
        # Configure scraping options - transcript is now included by default
        options = ScrapingOptions(
            get_transcript=True,  # Transcript is now included in main response
            trim_response=True,
            max_retries=3,
            timeout=30
        )
        
        # Scrape video with transcript in single request
        logger.info(f"Processing video: {request.url}")
        video_content, metadata, transcript = await scraper.scrape_tiktok_complete(request.url, options)
        
        if transcript:
            logger.info(f"Successfully got transcript: {len(transcript)} characters")
        else:
            logger.info("No transcript available for this video")
        
        # 3. Remove audio
        logger.info("Removing audio from video...")
        silent_video = await video_processor.remove_audio(video_content)
        
        # 4. Analyze with Gemini
        caption = metadata.description or metadata.caption
        
        # Handle case where transcript might be None
        if transcript is None:
            logger.warning(f"Processing video without transcript: {request.url}")
            # You can still proceed without transcript, or modify this based on your needs
        else:
            logger.info(f"Processing video with transcript ({len(transcript)} chars): {request.url}")
        
        logger.info("Analyzing video with Vertex AI...")
        workout_json = vertex_ai.analyze_video_with_transcript(silent_video, transcript, caption)
        
        if not workout_json:
            raise HTTPException(status_code=422, detail="Could not extract workout information")
        
        logger.info(f"Successfully processed video: {request.url}")
        return workout_json
        
    except ValidationError as e:
        logger.error(f"Validation error for {request.url}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid URL: {str(e)}")
    except APIError as e:
        logger.error(f"API error for {request.url}: {str(e)} (Status: {e.status_code})")
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="TikTok video not found or unavailable")
        elif e.status_code == 401:
            raise HTTPException(status_code=500, detail="API authentication failed - check your API key")
        elif e.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limit exceeded - please try again later")
        else:
            raise HTTPException(status_code=500, detail=f"API error: {str(e)}")
    except NetworkError as e:
        logger.error(f"Network error for {request.url}: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Network error: {str(e)}")
    except Exception as e:
        # Log the full error for debugging
        logger.exception(f"Unexpected error processing video {request.url}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/test-api")
async def test_api():
    """Test the ScrapeCreators API connection"""
    try:
        # Test with a simple video info fetch (no video download)
        test_url = "https://www.tiktok.com/@stoolpresidente/video/7463250363559218474"
        
        options = ScrapingOptions(
            get_transcript=False,  # Skip transcript for faster testing
            trim_response=True,
            max_retries=1,
            timeout=10
        )
        
        info = await scraper.get_video_info(test_url, options)
        
        return {
            "status": "success",
            "message": "API key is working correctly",
            "test_video": {
                "title": info['metadata']['title'][:100],
                "author": info['metadata']['author'],
                "duration": info['metadata']['duration_seconds']
            }
        }
        
    except ValidationError as e:
        return {"status": "error", "type": "validation", "message": str(e)}
    except APIError as e:
        if e.status_code == 401:
            return {"status": "error", "type": "auth", "message": "API key is invalid or missing"}
        else:
            return {"status": "error", "type": "api", "message": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"status": "error", "type": "unexpected", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)