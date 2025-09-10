#!/usr/bin/env python3
"""
Test script for queue cleanup functionality
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.queue_service import QueueService
from datetime import datetime, timezone

async def test_queue_cleanup():
    """Test the queue cleanup functionality"""
    
    print("🧪 Testing Queue Cleanup Functionality")
    print("=" * 50)
    
    # Initialize queue service
    qs = QueueService()
    if not qs.db:
        print("❌ Firestore not connected")
        return
    
    # Get initial queue status
    all_docs = list(qs.queue_collection.stream())
    print(f"Initial queue size: {len(all_docs)} documents")
    
    # Count by status
    status_counts = {}
    for doc in all_docs:
        data = doc.to_dict()
        status = data.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("Status breakdown:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    
    # Test cleanup (dry run first)
    print(f"\n🧹 Testing cleanup of jobs older than 1 day...")
    
    try:
        deleted_count = await qs.cleanup_old_jobs(days=1, batch_size=10)
        print(f"✅ Cleanup completed: {deleted_count} jobs processed")
        
        # Check final status
        final_docs = list(qs.queue_collection.stream())
        print(f"Final queue size: {len(final_docs)} documents")
        
        if len(final_docs) < len(all_docs):
            print(f"🎉 Successfully cleaned up {len(all_docs) - len(final_docs)} documents")
        else:
            print("ℹ️ No old jobs found to clean up")
            
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_queue_cleanup())
