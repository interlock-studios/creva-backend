#!/usr/bin/env python3
"""Test script for frame extraction functionality"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.worker.video_processor import VideoProcessor


async def test_frame_extraction():
    """Test the frame extraction with a sample video URL"""
    processor = VideoProcessor()
    
    # Test URL - you can replace with any TikTok/Instagram video URL
    test_url = "https://www.tiktok.com/@example/video/1234567890"  # Replace with actual URL
    
    print(f"Testing frame extraction with URL: {test_url}")
    print("-" * 50)
    
    try:
        # Download video
        print("1. Downloading video...")
        video_content, metadata = await processor.download_video(test_url)
        print(f"   ✓ Downloaded: {len(video_content)} bytes")
        print(f"   ✓ Platform: {metadata['platform']}")
        print(f"   ✓ Duration: {metadata['duration']}s")
        
        # Check if it's a slideshow or video
        if metadata.get('is_slideshow'):
            print("\n2. Content is a slideshow")
            print(f"   ✓ Image count: {metadata.get('image_count', 'Unknown')}")
            
            # For slideshows, the content would be a list of images
            # This is a simplified example - actual implementation may vary
            print("   Note: Slideshow frame extraction requires images list from scraper")
            
        else:
            print("\n2. Extracting first frame from video...")
            frame_bytes = await processor.extract_first_frame(video_content)
            print(f"   ✓ Extracted frame: {len(frame_bytes)} bytes")
            
            # Optionally save the frame for verification
            output_path = "test_frame.jpg"
            with open(output_path, "wb") as f:
                f.write(frame_bytes)
            print(f"   ✓ Saved frame to: {output_path}")
            
        print("\n✅ Frame extraction test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_slideshow_extraction():
    """Test the slideshow image extraction"""
    processor = VideoProcessor()
    
    # Create mock slideshow data
    mock_images = [
        b"fake_image_1_data_jpeg",  # In real scenario, these would be actual JPEG bytes
        b"fake_image_2_data_jpeg",
        b"fake_image_3_data_jpeg",
    ]
    
    print("\nTesting slideshow image extraction")
    print("-" * 50)
    
    try:
        # Test extracting first image (default)
        first_image = await processor.extract_image_from_slideshow(mock_images)
        print(f"✓ Extracted first image: {len(first_image)} bytes")
        
        # Test extracting specific image
        second_image = await processor.extract_image_from_slideshow(mock_images, index=1)
        print(f"✓ Extracted second image: {len(second_image)} bytes")
        
        # Test error handling
        try:
            await processor.extract_image_from_slideshow(mock_images, index=10)
        except IndexError as e:
            print(f"✓ Correctly caught out of bounds error: {e}")
            
        print("\n✅ Slideshow extraction test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")


if __name__ == "__main__":
    print("Frame Extraction Test Suite")
    print("=" * 50)
    
    # Get URL from command line or use default
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        print(f"Using provided URL: {test_url}")
    else:
        print("Usage: python test_frame_extraction.py <tiktok_or_instagram_url>")
        print("Running slideshow test only...\n")
        asyncio.run(test_slideshow_extraction())
        sys.exit(0)
    
    # Run tests
    asyncio.run(test_frame_extraction())