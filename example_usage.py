#!/usr/bin/env python3
"""
Example usage of the enhanced TikTok Scraper

This script demonstrates how to use the TikTokScraper with proper error handling
and different configuration options.

Requirements:
    - Set SCRAPECREATORS_API_KEY environment variable
    - Install dependencies: pip install -r requirements.txt
"""

import asyncio
import logging
import os
from typing import Optional

from src.services.tiktok_scraper import (
    TikTokScraper, 
    ScrapingOptions, 
    APIError, 
    NetworkError, 
    ValidationError
)


# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def example_basic_usage():
    """Example of basic TikTok scraping"""
    print("\n=== Basic Usage Example ===")
    
    try:
        scraper = TikTokScraper()
        
        # Example TikTok URL - replace with actual URL
        test_url = "https://www.tiktok.com/@stoolpresidente/video/7463250363559218474"
        
        # Get video info only (lightweight operation)
        print(f"Fetching video info for: {test_url}")
        info = await scraper.get_video_info(test_url)
        
        print(f"✅ Video Title: {info['metadata']['title']}")
        print(f"✅ Author: {info['metadata']['author']}")
        print(f"✅ Duration: {info['metadata']['duration_seconds']} seconds")
        print(f"✅ View Count: {info['metadata']['view_count']:,}")
        print(f"✅ Transcript Available: {'Yes' if info['transcript'] else 'No'}")
        
        if info['transcript']:
            print(f"✅ Transcript Preview: {info['transcript'][:100]}...")
        
    except ValidationError as e:
        print(f"❌ Invalid URL: {e}")
    except APIError as e:
        print(f"❌ API Error: {e}")
        if e.status_code:
            print(f"   Status Code: {e.status_code}")
    except NetworkError as e:
        print(f"❌ Network Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")


async def example_advanced_usage():
    """Example with custom options and full video download"""
    print("\n=== Advanced Usage Example ===")
    
    try:
        scraper = TikTokScraper()
        
        # Custom options
        options = ScrapingOptions(
            get_transcript=True,      # Get transcript
            trim_response=True,       # Trim API response for efficiency
            max_retries=5,           # Retry up to 5 times
            timeout=60               # 60 second timeout
        )
        
        test_url = "https://www.tiktok.com/@stoolpresidente/video/7463250363559218474"
        
        print(f"Scraping complete video with custom options...")
        print(f"Options: transcript={options.get_transcript}, retries={options.max_retries}, timeout={options.timeout}s")
        
        # Complete scraping (this downloads the actual video content)
        video_content, metadata, transcript = await scraper.scrape_tiktok_complete(test_url, options)
        
        print(f"✅ Successfully downloaded video!")
        print(f"✅ Video size: {len(video_content):,} bytes ({len(video_content) / (1024*1024):.1f} MB)")
        print(f"✅ Metadata: {metadata.title}")
        print(f"✅ Author: {metadata.author} (@{metadata.author_id})")
        print(f"✅ Stats: {metadata.view_count:,} views, {metadata.like_count:,} likes")
        
        if transcript:
            print(f"✅ Transcript length: {len(transcript)} characters")
            print(f"✅ Transcript preview: {transcript[:200]}...")
        
        # Save video to file (optional)
        output_filename = f"tiktok_video_{metadata.author_id}.mp4"
        with open(output_filename, 'wb') as f:
            f.write(video_content)
        print(f"✅ Video saved as: {output_filename}")
        
    except ValidationError as e:
        print(f"❌ Invalid URL: {e}")
    except APIError as e:
        print(f"❌ API Error: {e}")
        if e.status_code:
            print(f"   Status Code: {e.status_code}")
        if e.response_text:
            print(f"   Response: {e.response_text[:200]}...")
    except NetworkError as e:
        print(f"❌ Network Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")


async def example_error_handling():
    """Example demonstrating different error scenarios"""
    print("\n=== Error Handling Examples ===")
    
    scraper = TikTokScraper()
    
    # Test cases for different error types
    test_cases = [
        ("Invalid URL", "not-a-url"),
        ("Non-TikTok URL", "https://www.youtube.com/watch?v=invalid"),
        ("Non-existent TikTok", "https://www.tiktok.com/@fake/video/999999999999999999"),
    ]
    
    for test_name, test_url in test_cases:
        print(f"\nTesting {test_name}: {test_url}")
        try:
            info = await scraper.get_video_info(test_url)
            print(f"✅ Unexpected success: {info['metadata']['title']}")
        except ValidationError as e:
            print(f"⚠️  Validation Error (expected): {e}")
        except APIError as e:
            print(f"⚠️  API Error (expected): {e}")
            if e.status_code:
                print(f"   Status Code: {e.status_code}")
        except NetworkError as e:
            print(f"❌ Network Error: {e}")
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")


async def example_transcript_only():
    """Example of fetching just transcript for a video"""
    print("\n=== Transcript Only Example ===")
    
    try:
        scraper = TikTokScraper()
        
        # Use full URL (video ID alone won't work with the video info endpoint)
        video_url = "https://www.tiktok.com/@stoolpresidente/video/7463250363559218474"
        
        print(f"Fetching transcript for video: {video_url}")
        
        # Use get_video_info to get transcript (no video download)
        options = ScrapingOptions(get_transcript=True, trim_response=True)
        result = await scraper.get_video_info(video_url, options)
        transcript = result.get('transcript')
        
        if transcript:
            print(f"✅ Transcript length: {len(transcript)} characters")
            print(f"✅ Transcript content: {transcript}")
        else:
            print("ℹ️  No transcript available for this video")
            
    except Exception as e:
        print(f"❌ Error fetching transcript: {e}")


async def main():
    """Run all examples"""
    print("🚀 TikTok Scraper Examples")
    print("=" * 50)
    
    # Check if API key is set
    if not os.getenv("SCRAPECREATORS_API_KEY"):
        print("❌ Error: SCRAPECREATORS_API_KEY environment variable not set!")
        print("   Please set your API key before running this example.")
        return
    
    # Run examples
    await example_basic_usage()
    await example_advanced_usage()
    await example_error_handling()
    await example_transcript_only()
    
    print("\n✅ All examples completed!")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())