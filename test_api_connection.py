"""
Test script to diagnose AliExpress API connection issues
"""
import requests
import json
from config import Config

def test_api_endpoints():
    """Test different API endpoints to see which works"""
    
    test_product_ids = [
        "1005006292239327",  # User's fresh product
        "1005004049949624",  # Product from debug file 
        "4000058597733",     # Simple old format ID
    ]
    
    # Different endpoints to try
    endpoints = [
        "item_detail_6",
        "item_detail",
        "item_search",
    ]
    
    headers = {
        'X-RapidAPI-Key': Config.RAPIDAPI_KEY,
        'X-RapidAPI-Host': Config.RAPIDAPI_HOST
    }
    
    print("="*70)
    print("AliExpress API Connection Test")
    print("="*70)
    print(f"API Host: {Config.RAPIDAPI_HOST}")
    print(f"API Key: {Config.RAPIDAPI_KEY[:10]}...")
    print("="*70)
    
    for endpoint in endpoints:
        print(f"\n\n{'='*70}")
        print(f"Testing endpoint: {endpoint}")
        print('='*70)
        
        for product_id in test_product_ids:
            print(f"\n  Testing Product ID: {product_id}")
            print("  " + "-"*60)
            
            url = f"https://{Config.RAPIDAPI_HOST}/{endpoint}"
            
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    params={'itemId': product_id},
                    timeout=10
                )
                
                print(f"  Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if we got data
                    result = data.get('result', {})
                    status = result.get('status', {})
                    
                    print(f"  Status Code (API): {status.get('code')}")
                    print(f"  Status Data: {status.get('data')}")
                    
                    if status.get('data') == 'success':
                        print(f"  ✓ SUCCESS! This endpoint works for product {product_id}")
                        item = result.get('item', {})
                        if item:
                            print(f"  Product Title: {item.get('title', 'N/A')[:100]}")
                            print(f"  Available: {item.get('available', 'N/A')}")
                    else:
                        print(f"  ✗ API Error: {status.get('msg', 'Unknown error')}")
                else:
                    print(f"  ✗ HTTP Error: {response.text[:200]}")
                    
            except Exception as e:
                print(f"  ✗ Exception: {e}")

    print("\n\n" + "="*70)
    print("Testing API subscription info")
    print("="*70)
    
    # Try to get API subscription details
    try:
        # Some RapidAPI endpoints have a status or info endpoint
        url = f"https://{Config.RAPIDAPI_HOST}/status"
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status endpoint response: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
    except:
        print("No status endpoint available")

if __name__ == '__main__':
    test_api_endpoints()
