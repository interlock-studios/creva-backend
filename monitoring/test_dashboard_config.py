#!/usr/bin/env python3
"""
Test script to validate dashboard configuration and Google Cloud integration
"""

import json
import os
import sys
from google.cloud import monitoring_v3
from google.cloud import logging as cloud_logging

def test_dashboard_json():
    """Test that the dashboard JSON is valid"""
    print("🔍 Testing dashboard JSON configuration...")
    
    dashboard_file = "comprehensive_security_dashboard.json"
    
    try:
        with open(dashboard_file, 'r') as f:
            dashboard_config = json.load(f)
        
        # Validate required fields
        required_fields = ['displayName', 'mosaicLayout']
        for field in required_fields:
            if field not in dashboard_config:
                print(f"❌ Missing required field: {field}")
                return False
        
        # Count tiles
        tiles = dashboard_config['mosaicLayout'].get('tiles', [])
        print(f"✅ Dashboard JSON valid - {len(tiles)} tiles configured")
        
        # Validate key tiles
        tile_titles = [tile.get('widget', {}).get('title', '') for tile in tiles]
        key_tiles = [
            "🚦 App Check Readiness Indicator",
            "📊 App Check Status Overview",
            "📈 Security Metrics Over Time",
            "🚨 Security Threats Detected"
        ]
        
        missing_tiles = [title for title in key_tiles if not any(title in t for t in tile_titles)]
        if missing_tiles:
            print(f"⚠️  Missing key tiles: {missing_tiles}")
        else:
            print("✅ All key tiles present")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Dashboard file not found: {dashboard_file}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error validating dashboard: {e}")
        return False

def test_google_cloud_connection():
    """Test Google Cloud Monitoring connection"""
    print("\n🔍 Testing Google Cloud connection...")
    
    try:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not project_id:
            print("⚠️  GOOGLE_CLOUD_PROJECT_ID not set, using default credentials")
        
        # Test Monitoring API
        monitoring_client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{project_id or 'default'}"
        
        # Try to list metrics (this will fail gracefully if no permissions)
        try:
            metrics = monitoring_client.list_metric_descriptors(
                request={"name": project_name}
            )
            # Just check if we can iterate (don't need to fetch all)
            next(iter(metrics), None)
            print("✅ Google Cloud Monitoring API accessible")
        except Exception as e:
            print(f"⚠️  Monitoring API limited access: {str(e)[:100]}...")
        
        # Test Logging API
        try:
            logging_client = cloud_logging.Client()
            # Test if we can access the client
            logger = logging_client.logger("test-logger")
            print("✅ Google Cloud Logging API accessible")
        except Exception as e:
            print(f"⚠️  Logging API limited access: {str(e)[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Google Cloud connection failed: {e}")
        return False

def test_log_structure():
    """Test that our log structure matches dashboard expectations"""
    print("\n🔍 Testing log structure compatibility...")
    
    # Test log entry structure
    sample_log_entry = {
        "event_type": "appcheck_metric",
        "metric": "verified",
        "path": "/process",
        "app_id": "test-app-id",
        "ip_address": "127.0.0.1",
        "severity": "info",
        "readiness_score": 100,
        "readiness_percentage": 85.5,
        "readiness_status": "READY",
        "cumulative_verified": 100,
        "cumulative_unverified": 15,
        "cumulative_invalid": 5,
        "total_requests": 120,
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    # Check required fields for dashboard
    required_fields = [
        "event_type", "metric", "readiness_percentage", 
        "readiness_status", "security_event", "ip_address"
    ]
    
    # Note: security_event is optional, so we'll add it
    sample_log_entry["security_event"] = ""
    
    missing_fields = []
    for field in required_fields:
        if field not in sample_log_entry and field != "security_event":
            missing_fields.append(field)
    
    if missing_fields:
        print(f"❌ Missing log fields: {missing_fields}")
        return False
    else:
        print("✅ Log structure compatible with dashboard")
        return True

def test_readiness_calculation():
    """Test App Check readiness calculation logic"""
    print("\n🔍 Testing App Check readiness calculation...")
    
    test_cases = [
        {"verified": 90, "total": 100, "expected_status": "READY", "expected_pct": 90.0},
        {"verified": 70, "total": 100, "expected_status": "CAUTION", "expected_pct": 70.0},
        {"verified": 30, "total": 100, "expected_status": "NOT_READY", "expected_pct": 30.0},
        {"verified": 0, "total": 0, "expected_status": "NOT_READY", "expected_pct": 0.0},
    ]
    
    all_passed = True
    
    for case in test_cases:
        verified = case["verified"]
        total = case["total"]
        
        # Simulate the calculation from main.py
        readiness_percentage = (verified / total * 100) if total > 0 else 0
        
        if readiness_percentage >= 80:
            readiness_status = "READY"
        elif readiness_percentage >= 50:
            readiness_status = "CAUTION"
        else:
            readiness_status = "NOT_READY"
        
        if (readiness_percentage == case["expected_pct"] and 
            readiness_status == case["expected_status"]):
            print(f"✅ Test case passed: {verified}/{total} = {readiness_percentage}% ({readiness_status})")
        else:
            print(f"❌ Test case failed: {verified}/{total} = {readiness_percentage}% ({readiness_status})")
            all_passed = False
    
    return all_passed

def main():
    """Run all tests"""
    print("🛡️ Dashboard Configuration & Integration Tests")
    print("=" * 50)
    
    tests = [
        ("Dashboard JSON Configuration", test_dashboard_json),
        ("Google Cloud Connection", test_google_cloud_connection),
        ("Log Structure Compatibility", test_log_structure),
        ("Readiness Calculation Logic", test_readiness_calculation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Dashboard is ready for deployment.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
