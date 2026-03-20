"""
Debug script to test specific AliExpress products
"""
import requests
import json
from config import Config

def test_product(product_id):
    """Test a single product with all endpoints"""
    print(f"\n{'='*70}")
    print(f"Testing Product ID: {product_id}")
    print('='*70)
    
    endpoints = ['item_detail_3', 'item_detail_2', 'item_detail_6']
    
    headers = {
        'X-RapidAPI-Key': Config.RAPIDAPI_KEY,
        'X-RapidAPI-Host': Config.RAPIDAPI_HOST
    }
    
    for endpoint in endpoints:
        print(f"\nEndpoint: {endpoint}")
        print("-" * 60)
        
        url = f"https://{Config.RAPIDAPI_HOST}/{endpoint}"
        
        try:
            response = requests.get(
                url,
                headers=headers,
                params={'itemId': str(product_id)},
                timeout=10
            )
            
            print(f"HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', {})
                status = result.get('status', {})
                
                print(f"API Status Code: {status.get('code')}")
                print(f"API Status Data: {status.get('data')}")
                
                if status.get('data') == 'success':
                    item = result.get('item', {})
                    print(f"\n✓ SUCCESS!")
                    print(f"  Title: {item.get('title', 'N/A')[:80]}")
                    print(f"  Available: {item.get('available', 'N/A')}")
                    
                    # Check stock
                    sku = item.get('sku', {})
                    sku_def = sku.get('def', {})
                    stock = sku_def.get('quantity', 'N/A')
                    print(f"  Stock: {stock}")
                    
                    # Save successful response
                    with open(f'debug_{product_id}_{endpoint}.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"  Response saved to: debug_{product_id}_{endpoint}.json")
                    return True
                else:
                    print(f"✗ Error: {status.get('msg', 'Unknown')}")
            else:
                print(f"✗ HTTP Error: {response.status_code}")
                
        except Exception as e:
            print(f"✗ Exception: {e}")
    
    return False

if __name__ == '__main__':
    # Test the two products the user says are available
    products = [
        "1005007066678832",
        "1005009811042362"
    ]
    
    print("="*70)
    print("Testing User's AliExpress Products")
    print("="*70)
    
    for product_id in products:
        success = test_product(product_id)
        if not success:
            print(f"\n⚠️ Product {product_id} could not be fetched from any endpoint")
