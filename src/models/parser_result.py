from typing import Optional, List
from pydantic import BaseModel


class VideoMetadata(BaseModel):
    """Metadata from TikTok video"""
    title: Optional[str] = None
    description: Optional[str] = None
    caption: Optional[str] = None
    author: Optional[str] = None
    author_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None
    upload_date: Optional[str] = None
    hashtags: Optional[List[str]] = None
    sound_title: Optional[str] = None
    sound_author: Optional[str] = None
    file_size_bytes: Optional[int] = None