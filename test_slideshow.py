#!/usr/bin/env python3
"""
Test script for TikTok slideshow functionality
"""

import asyncio
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.services.tiktok_scraper import TikTokScraper, ScrapingOptions


async def test_slideshow_detection():
    """Test slideshow detection and metadata extraction"""
    
    # Test URLs - you'll need to replace these with actual slideshow TikTok URLs
    test_urls = [
        "https://www.tiktok.com/@user/video/123456789",  # Replace with actual slideshow URL
        # Add more slideshow URLs here for testing
    ]
    
    scraper = TikTokScraper()
    options = ScrapingOptions(get_transcript=True, trim_response=True)
    
    for url in test_urls:
        try:
            logger.info(f"Testing URL: {url}")
            
            # Get video info to check if it's a slideshow
            info = await scraper.get_video_info(url, options)
            metadata = info["metadata"]
            
            logger.info(f"Is slideshow: {metadata.get('is_slideshow', False)}")
            logger.info(f"Image count: {metadata.get('image_count', 'N/A')}")
            logger.info(f"Duration: {metadata.get('duration_seconds', 'N/A')} seconds")
            logger.info(f"Title: {metadata.get('title', 'N/A')[:100]}...")
            
            if metadata.get("is_slideshow"):
                logger.info("✅ Slideshow detected!")
                
                # Test slideshow-specific scraping
                slideshow_images, slideshow_metadata, transcript = await scraper.scrape_tiktok_slideshow(url, options)
                
                logger.info(f"Downloaded {len(slideshow_images)} images")
                logger.info(f"Image sizes: {[len(img) for img in slideshow_images]} bytes")
                logger.info(f"Has transcript: {transcript is not None}")
                
                # Test slideshow images extraction
                api_data = await scraper.fetch_tiktok_data(url, options)
                slideshow_image_objects = scraper.get_slideshow_images(api_data)
                
                logger.info(f"Slideshow image objects: {len(slideshow_image_objects)}")
                for i, img_obj in enumerate(slideshow_image_objects):
                    logger.info(f"  Image {i}: {img_obj.url[:50]}... ({img_obj.width}x{img_obj.height})")
                
            else:
                logger.info("ℹ️  Regular video detected")
                
        except Exception as e:
            logger.error(f"Error testing {url}: {e}")
            
        logger.info("-" * 80)


async def test_complete_slideshow_workflow():
    """Test the complete slideshow workflow including AI analysis"""
    
    # This would require a GenAI service setup
    logger.info("Testing complete slideshow workflow...")
    
    # You would test with the worker service here
    # This is just a placeholder for the workflow test
    
    logger.info("Complete workflow test - requires full environment setup")


async def main():
    """Main test function"""
    logger.info("Starting TikTok slideshow functionality tests...")
    
    # Check required environment variables
    required_vars = ["SCRAPECREATORS_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set up your .env file with ScrapeCreators API key")
        return
    
    logger.info("✅ Environment variables are set")
    
    # Test slideshow detection
    await test_slideshow_detection()
    
    # Test complete workflow (commented out for now)
    # await test_complete_slideshow_workflow()
    
    logger.info("Tests completed!")


if __name__ == "__main__":
    asyncio.run(main())