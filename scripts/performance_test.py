#!/usr/bin/env python3
"""
Performance Testing Script for Sets AI Backend
Tests the optimized API performance and measures improvements
"""

import asyncio
import aiohttp
import time
import json
import statistics
import argparse
from typing import List, Dict, Any
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

class PerformanceTester:
    def __init__(self, base_url: str, concurrent_requests: int = 10):
        self.base_url = base_url.rstrip('/')
        self.concurrent_requests = concurrent_requests
        self.results = {
            'health_checks': [],
            'metrics_checks': [],
            'regional_health_checks': [],
            'processing_checks': [],
        }
    
    async def test_endpoint(self, session: aiohttp.ClientSession, endpoint: str, timeout: int = 10) -> Dict[str, Any]:
        """Test a single endpoint and measure performance"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                end_time = time.time()
                response_time = end_time - start_time
                
                if response.status == 200:
                    try:
                        data = await response.json()
                        return {
                            'success': True,
                            'response_time': response_time,
                            'status_code': response.status,
                            'data': data,
                            'url': url,
                        }
                    except json.JSONDecodeError:
                        return {
                            'success': False,
                            'response_time': response_time,
                            'status_code': response.status,
                            'error': 'Invalid JSON response',
                            'url': url,
                        }
                else:
                    return {
                        'success': False,
                        'response_time': response_time,
                        'status_code': response.status,
                        'error': f'HTTP {response.status}',
                        'url': url,
                    }
        except asyncio.TimeoutError:
            return {
                'success': False,
                'response_time': timeout,
                'status_code': 0,
                'error': 'Timeout',
                'url': url,
            }
        except Exception as e:
            end_time = time.time()
            return {
                'success': False,
                'response_time': end_time - start_time,
                'status_code': 0,
                'error': str(e),
                'url': url,
            }
    
    async def run_concurrent_tests(self, endpoint: str, test_name: str, count: int = None) -> List[Dict[str, Any]]:
        """Run concurrent tests on an endpoint"""
        if count is None:
            count = self.concurrent_requests
        
        print(f"🧪 Testing {test_name} with {count} concurrent requests...")
        
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [self.test_endpoint(session, endpoint) for _ in range(count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            valid_results = []
            for result in results:
                if isinstance(result, dict):
                    valid_results.append(result)
                else:
                    valid_results.append({
                        'success': False,
                        'response_time': 30.0,
                        'status_code': 0,
                        'error': str(result),
                        'url': f"{self.base_url}{endpoint}",
                    })
            
            return valid_results
    
    def analyze_results(self, results: List[Dict[str, Any]], test_name: str) -> Dict[str, Any]:
        """Analyze test results and calculate statistics"""
        if not results:
            return {'error': 'No results to analyze'}
        
        successful_results = [r for r in results if r['success']]
        failed_results = [r for r in results if not r['success']]
        
        response_times = [r['response_time'] for r in successful_results]
        
        if response_times:
            stats = {
                'test_name': test_name,
                'total_requests': len(results),
                'successful_requests': len(successful_results),
                'failed_requests': len(failed_results),
                'success_rate': len(successful_results) / len(results) * 100,
                'avg_response_time': statistics.mean(response_times),
                'min_response_time': min(response_times),
                'max_response_time': max(response_times),
                'median_response_time': statistics.median(response_times),
                'p95_response_time': self.percentile(response_times, 95),
                'p99_response_time': self.percentile(response_times, 99),
                'requests_per_second': len(successful_results) / max(response_times) if response_times else 0,
            }
        else:
            stats = {
                'test_name': test_name,
                'total_requests': len(results),
                'successful_requests': 0,
                'failed_requests': len(failed_results),
                'success_rate': 0,
                'error': 'All requests failed',
            }
        
        return stats
    
    @staticmethod
    def percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile of a dataset"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def print_results(self, stats: Dict[str, Any]):
        """Print formatted test results"""
        print(f"\n📊 {stats['test_name']} Results:")
        print(f"   Total Requests: {stats['total_requests']}")
        print(f"   Successful: {stats['successful_requests']}")
        print(f"   Failed: {stats['failed_requests']}")
        print(f"   Success Rate: {stats['success_rate']:.1f}%")
        
        if 'avg_response_time' in stats:
            print(f"   Average Response Time: {stats['avg_response_time']:.3f}s")
            print(f"   Min Response Time: {stats['min_response_time']:.3f}s")
            print(f"   Max Response Time: {stats['max_response_time']:.3f}s")
            print(f"   Median Response Time: {stats['median_response_time']:.3f}s")
            print(f"   95th Percentile: {stats['p95_response_time']:.3f}s")
            print(f"   99th Percentile: {stats['p99_response_time']:.3f}s")
            print(f"   Requests/Second: {stats['requests_per_second']:.1f}")
        
        if stats['success_rate'] < 95:
            print("   ⚠️  Success rate below 95%")
        elif stats['success_rate'] == 100:
            print("   ✅ Perfect success rate!")
        
        if 'avg_response_time' in stats and stats['avg_response_time'] < 0.5:
            print("   ⚡ Excellent response time!")
        elif 'avg_response_time' in stats and stats['avg_response_time'] > 2.0:
            print("   🐌 Response time could be improved")
    
    async def run_comprehensive_test(self):
        """Run comprehensive performance tests"""
        print(f"🚀 Starting comprehensive performance test for {self.base_url}")
        print(f"📈 Concurrent requests: {self.concurrent_requests}")
        print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Test 1: Health endpoint
        health_results = await self.run_concurrent_tests('/health', 'Health Endpoint')
        health_stats = self.analyze_results(health_results, 'Health Endpoint')
        self.print_results(health_stats)
        
        # Test 2: Regional health endpoint
        regional_results = await self.run_concurrent_tests('/health/regions', 'Regional Health')
        regional_stats = self.analyze_results(regional_results, 'Regional Health')
        self.print_results(regional_stats)
        
        # Test 3: Performance metrics endpoint
        metrics_results = await self.run_concurrent_tests('/metrics/performance', 'Performance Metrics')
        metrics_stats = self.analyze_results(metrics_results, 'Performance Metrics')
        self.print_results(metrics_stats)
        
        # Test 4: Processing health endpoint
        processing_results = await self.run_concurrent_tests('/health/processing', 'Processing Health')
        processing_stats = self.analyze_results(processing_results, 'Processing Health')
        self.print_results(processing_stats)
        
        # Overall summary
        print(f"\n🎯 Overall Performance Summary:")
        print(f"   Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        all_stats = [health_stats, regional_stats, metrics_stats, processing_stats]
        valid_stats = [s for s in all_stats if 'avg_response_time' in s]
        
        if valid_stats:
            overall_avg = statistics.mean([s['avg_response_time'] for s in valid_stats])
            overall_success = statistics.mean([s['success_rate'] for s in valid_stats])
            
            print(f"   Overall Average Response Time: {overall_avg:.3f}s")
            print(f"   Overall Success Rate: {overall_success:.1f}%")
            
            # Performance assessment
            if overall_avg < 0.5 and overall_success >= 99:
                print("   🏆 EXCELLENT: API performance is outstanding!")
            elif overall_avg < 1.0 and overall_success >= 95:
                print("   ✅ GOOD: API performance is solid")
            elif overall_avg < 2.0 and overall_success >= 90:
                print("   ⚠️  FAIR: API performance could be improved")
            else:
                print("   ❌ POOR: API performance needs attention")
        
        return {
            'health': health_stats,
            'regional_health': regional_stats,
            'metrics': metrics_stats,
            'processing_health': processing_stats,
        }

async def main():
    parser = argparse.ArgumentParser(description='Performance test the Sets AI Backend API')
    parser.add_argument('--url', required=True, help='Base URL of the API to test')
    parser.add_argument('--concurrent', type=int, default=10, help='Number of concurrent requests (default: 10)')
    parser.add_argument('--output', help='Output file for results (JSON format)')
    
    args = parser.parse_args()
    
    tester = PerformanceTester(args.url, args.concurrent)
    results = await tester.run_comprehensive_test()
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Results saved to {args.output}")

if __name__ == '__main__':
    asyncio.run(main())
