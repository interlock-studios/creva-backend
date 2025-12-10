"""
Search API endpoints for discovering videos in the global library.

Endpoints:
- GET /search - Search videos with filters
- GET /search/formats - Get available video formats
- GET /search/niches - Get available content niches
- GET /videos/{video_id} - Get video details
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
import logging

from src.services.search_service import SearchService
from src.services.video_service import VideoService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])

# Initialize services
search_service = SearchService()
video_service = VideoService()


@router.get("")
async def search_videos(
    q: Optional[str] = Query(None, description="Full-text search query"),
    format: Optional[str] = Query(None, description="Filter by video format (e.g., 'voiceover', 'talking_head')"),
    niche: Optional[str] = Query(None, description="Filter by content niche (e.g., 'fitness', 'business')"),
    platform: Optional[str] = Query(None, description="Filter by platform ('tiktok' or 'instagram')"),
    creator: Optional[str] = Query(None, description="Filter by creator username"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Search the global video library.
    
    Supports full-text search across titles, hooks, transcripts, and descriptions.
    Use filters to narrow results by format, niche, platform, or creator.
    
    Examples:
    - `/search?q=fitness+hooks` - Search for "fitness hooks"
    - `/search?format=voiceover&niche=fitness` - All voiceover fitness videos
    - `/search?creator=@creator` - All videos from a specific creator
    - `/search?platform=tiktok&limit=50` - 50 TikTok videos
    """
    try:
        result = await search_service.search(
            query=q,
            format=format,
            niche=niche,
            platform=platform,
            creator=creator,
            limit=limit,
            offset=offset,
        )
        
        return {
            "success": True,
            "data": {
                "videos": result.get("hits", []),
                "total": result.get("total", 0),
                "page": result.get("page", 0),
                "pages": result.get("pages", 0),
                "limit": limit,
                "offset": offset,
            },
            "meta": {
                "backend": result.get("backend"),
                "warning": result.get("warning"),
            },
        }
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/formats")
async def get_formats():
    """
    Get all available video formats for filtering.
    
    Returns the list of format types that can be used to filter search results.
    """
    formats = search_service.get_available_formats()
    
    # Add descriptions for each format
    format_descriptions = {
        "voiceover": "Voice narration over footage/B-roll",
        "talking_head": "Creator speaking directly to camera",
        "talking_back_forth": "Two perspectives/arguments presented",
        "reaction": "Reacting to other content",
        "setting_changes": "Multiple location/outfit changes",
        "whiteboard": "Text/drawing on screen explanations",
        "shot_angle_change": "Dynamic camera angle cuts",
        "multitasking": "Creator doing activity while talking",
        "visual": "Primarily visual, minimal talking",
        "green_screen": "Green screen background",
        "clone": "Same person appears multiple times",
        "slideshow": "Image carousel with text/voiceover",
        "tutorial": "Step-by-step how-to",
        "duet": "Side-by-side with another video",
        "stitch": "Response to another creator's clip",
        "pov": "Point-of-view storytelling",
        "before_after": "Transformation/comparison",
        "day_in_life": "Day in the life vlog",
        "interview": "Q&A or interview style",
        "list": "Listicle format",
        "other": "Other format",
    }
    
    return {
        "success": True,
        "data": {
            "formats": [
                {"id": f, "name": f.replace("_", " ").title(), "description": format_descriptions.get(f, "")}
                for f in formats
            ],
            "total": len(formats),
        },
    }


@router.get("/niches")
async def get_niches():
    """
    Get all available content niches for filtering.
    
    Returns the list of niche categories that can be used to filter search results.
    """
    niches = search_service.get_available_niches()
    
    # Add descriptions for each niche
    niche_descriptions = {
        "fitness": "Gym, workout, bodybuilding, yoga",
        "food": "Cooking, recipes, meal prep, restaurants",
        "business": "Entrepreneurship, startups, marketing",
        "finance": "Investing, budgeting, crypto, real estate",
        "tech": "Software, AI, gadgets, coding",
        "beauty": "Skincare, makeup, haircare",
        "fashion": "Outfits, styling, shopping",
        "lifestyle": "Daily routines, organization, productivity",
        "education": "Study tips, learning, academics",
        "entertainment": "Comedy, skits, memes, trends",
        "motivation": "Mindset, self-improvement, inspirational",
        "relationships": "Dating, marriage, family dynamics",
        "parenting": "Kids, pregnancy, family life",
        "health": "Wellness, mental health, nutrition",
        "travel": "Destinations, travel tips, adventure",
        "gaming": "Gameplay, reviews, esports",
        "music": "Covers, production, dance",
        "art": "Drawing, design, DIY, crafts",
        "pets": "Dogs, cats, animals",
        "sports": "Sports, athletics, training",
        "other": "Other topics",
    }
    
    return {
        "success": True,
        "data": {
            "niches": [
                {"id": n, "name": n.replace("_", " ").title(), "description": niche_descriptions.get(n, "")}
                for n in niches
            ],
            "total": len(niches),
        },
    }


@router.get("/status")
async def get_search_status():
    """
    Get search service status and capabilities.
    
    Returns information about the current search backend and available features.
    """
    status = search_service.get_status()
    
    return {
        "success": True,
        "data": status,
    }


# Video detail endpoint (separate from search)
video_router = APIRouter(prefix="/videos", tags=["videos"])


@video_router.get("/{video_id}")
async def get_video(video_id: str):
    """
    Get details for a specific video by ID.
    
    Returns the full video data including transcript, hook, format, niche, etc.
    """
    video = await video_service.get_video(video_id)
    
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
    
    return {
        "success": True,
        "data": video,
    }


@video_router.get("/stats")
async def get_video_stats():
    """
    Get statistics about the video library.
    
    Returns total video count, most saved videos, etc.
    """
    stats = video_service.get_video_stats()
    
    return {
        "success": True,
        "data": stats,
    }

