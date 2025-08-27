#!/usr/bin/env python3
"""
Test script to verify dashboard data is populating correctly
"""

import requests
import time
import json
from datetime import datetime

# Configuration
API_URL = "https://workout-parser-v2-ty6tkvdynq-uc.a.run.app"
PROJECT_ID = "sets-ai"

def test_health_endpoint():
    """Test health endpoint with both GET and HEAD methods"""
    print("🔍 Testing health endpoint...")
    
    # Test GET
    try:
        response = requests.get(f"{API_URL}/health", timeout=10)
        print(f"✅ GET /health: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Services: {list(data.get('services', {}).keys())}")
    except Exception as e:
        print(f"❌ GET /health failed: {e}")
    
    # Test HEAD
    try:
        response = requests.head(f"{API_URL}/health", timeout=10)
        print(f"✅ HEAD /health: {response.status_code}")
    except Exception as e:
        print(f"❌ HEAD /health failed: {e}")

def generate_app_check_events():
    """Generate various App Check events for dashboard testing"""
    print("\n🔄 Generating App Check events...")
    
    events = [
        {"name": "Unverified requests", "headers": {}, "count": 5},
        {"name": "Invalid token requests", "headers": {"X-Firebase-AppCheck": "invalid-token-123"}, "count": 3},
        {"name": "Malformed token requests", "headers": {"X-Firebase-AppCheck": "malformed"}, "count": 2},
    ]
    
    for event in events:
        print(f"   Generating {event['count']} {event['name']}...")
        for i in range(event['count']):
            try:
                headers = {"Content-Type": "application/json"}
                headers.update(event['headers'])
                
                response = requests.post(
                    f"{API_URL}/process",
                    headers=headers,
                    json={"url": f"https://www.tiktok.com/@test/video/{int(time.time())}{i}"},
                    timeout=10
                )
                print(f"      Request {i+1}: {response.status_code}")
                time.sleep(0.5)  # Small delay between requests
            except Exception as e:
                print(f"      Request {i+1} failed: {e}")

def test_rate_limiting():
    """Test rate limiting functionality"""
    print("\n⚡ Testing rate limiting...")
    
    success_count = 0
    rate_limited_count = 0
    
    for i in range(12):  # Try to exceed the 15 req/min limit
        try:
            response = requests.post(
                f"{API_URL}/process",
                headers={"Content-Type": "application/json"},
                json={"url": f"https://www.tiktok.com/@ratetest/video/{i}"},
                timeout=5
            )
            
            if response.status_code == 200:
                success_count += 1
                print(f"   Request {i+1}: ✅ Success")
            elif response.status_code == 429:
                rate_limited_count += 1
                print(f"   Request {i+1}: 🚫 Rate limited")
            else:
                print(f"   Request {i+1}: ❓ Status {response.status_code}")
                
        except Exception as e:
            print(f"   Request {i+1}: ❌ Error: {e}")
        
        time.sleep(0.2)
    
    print(f"   Summary: {success_count} successful, {rate_limited_count} rate limited")
    
    if rate_limited_count > 0:
        print("   ✅ Rate limiting is working!")
    else:
        print("   ⚠️  Rate limiting may not be active or limits are high")

def check_logs():
    """Check if logs are being generated properly"""
    print("\n📋 Checking recent logs...")
    
    import subprocess
    
    try:
        # Check App Check events
        result = subprocess.run([
            "gcloud", "logging", "read",
            'resource.type="cloud_run_revision" AND jsonPayload.event_type="appcheck_metric"',
            "--limit=5", "--project=sets-ai",
            "--format=value(jsonPayload.metric,timestamp)"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            print("   ✅ App Check events found in logs:")
            for line in result.stdout.strip().split('\n')[:3]:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        print(f"      {parts[0]}: {parts[1]}")
        else:
            print("   ⚠️  No recent App Check events found in logs")
            
    except Exception as e:
        print(f"   ❌ Error checking logs: {e}")

def main():
    """Run all tests"""
    print("🛡️ Dashboard Data Verification Test")
    print("=" * 50)
    print(f"🎯 Target API: {API_URL}")
    print(f"📋 Project: {PROJECT_ID}")
    print(f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run tests
    test_health_endpoint()
    generate_app_check_events()
    test_rate_limiting()
    check_logs()
    
    print("\n" + "=" * 50)
    print("📊 Dashboard Check Instructions:")
    print("1. Wait 2-5 minutes for metrics to populate")
    print("2. Visit your dashboard:")
    print("   https://console.cloud.google.com/monitoring/dashboards/custom/4fc2c0fa-8141-4031-a04d-09f512e2f6ae?project=sets-ai")
    print("3. Look for:")
    print("   • App Check Readiness chart showing unverified requests")
    print("   • Unverified/Hour counter increasing")
    print("   • Security Events & App Check Logs showing recent activity")
    print("4. If data is still not showing:")
    print("   • Check that custom metrics are configured for both services")
    print("   • Verify log filters in dashboard match your service names")
    print("   • Wait up to 10 minutes for initial metric population")
    
    print("\n🎉 Test completed! Check your dashboard in a few minutes.")

if __name__ == "__main__":
    main()
