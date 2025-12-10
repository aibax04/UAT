#!/usr/bin/env python3
"""
Simple test script to verify CRAWL AI works
"""

import requests
import time
import json

def test_local_website():
    """Test with a local website or simple public site"""
    
    # Test URL - using a simple public site
    test_url = "https://httpbin.org/html"  # Simple static site
    
    print(f"Testing URL: {test_url}")
    
    # Start test
    response = requests.post(
        "http://localhost:5000/api/start-test",
        json={"url": test_url},
        timeout=10
    )
    
    if response.status_code != 200:
        print(f"Error starting test: {response.text}")
        return False
    
    data = response.json()
    run_id = data['run_id']
    print(f"Test started with ID: {run_id}")
    
    # Poll for status
    max_attempts = 30  # 30 * 2 seconds = 1 minute max
    for i in range(max_attempts):
        time.sleep(2)
        
        status_response = requests.get(
            f"http://localhost:5000/api/test-status/{run_id}",
            timeout=10
        )
        
        if status_response.status_code != 200:
            print(f"Error getting status: {status_response.text}")
            continue
        
        status_data = status_response.json()
        print(f"Progress: {status_data.get('progress', 'Unknown')}")
        
        if status_data['status'] in ['completed', 'failed']:
            break
    
    # Get final report
    report_response = requests.get(
        f"http://localhost:5000/api/test-report/{run_id}",
        timeout=10
    )
    
    if report_response.status_code == 200:
        report_data = report_response.json()
        print("\n" + "="*60)
        print(f"Test {report_data['status'].upper()}")
        print(f"URL: {report_data['url']}")
        print(f"Pages: {report_data['total_pages']}")
        print(f"Interactions: {report_data['total_clicks']}")
        
        if report_data['status'] == 'completed':
            print(f"Screenshots: {len(report_data['screenshots'])}")
            print("\nReport preview:")
            print(report_data['report'][:500] + "...")
        else:
            print(f"Error: {report_data.get('error', 'Unknown error')}")
        
        print("="*60)
        return True
    else:
        print(f"Error getting report: {report_response.text}")
        return False

if __name__ == "__main__":
    print("Testing CRAWL AI system...")
    
    # First check if server is running
    try:
        health_response = requests.get("http://localhost:5000/api/health", timeout=5)
        print(f"Server health: {health_response.json()}")
    except requests.ConnectionError:
        print("Server not running. Please start it first with: python app.py")
        exit(1)
    
    # Run test
    success = test_local_website()
    
    if success:
        print("\n✅ Test completed successfully!")
        print("\nNow you can:")
        print("1. Open index.html in your browser")
        print("2. Enter a URL to analyze")
        print("3. View the results")
    else:
        print("\n❌ Test failed. Check server logs for details.")