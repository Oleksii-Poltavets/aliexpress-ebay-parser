"""Debug script to check AliExpress API response structure"""
import json
from aliexpress_api import AliExpressAPI

api = AliExpressAPI()
product_id = "1005004049949624"

print(f"Fetching data for product: {product_id}\n")
data = api.get_product_details(product_id)

if data:
    # Save the full response to a file for inspection
    with open('aliexpress_debug_response.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print("Full response saved to: aliexpress_debug_response.json\n")
    
    # Check the structure
    result = data.get('result', {})
    item = result.get('item', {})
    
    print("Available keys in 'item':")
    for key in sorted(item.keys()):
        print(f"  - {key}")
    
    print("\n" + "="*60)
    print("Checking description-related fields:")
    print("="*60)
    
    desc_fields = ['description', 'productDescription', 'detail', 'descriptionUrl', 
                   'itemDesc', 'desc', 'itemDescription', 'productDesc']
    
    for field in desc_fields:
        value = item.get(field)
        if value:
            print(f"\n{field}:")
            print(f"  Type: {type(value)}")
            if isinstance(value, str):
                print(f"  Value (first 200 chars): {value[:200]}")
            elif isinstance(value, dict):
                print(f"  Dict keys: {list(value.keys())}")
                print(f"  Dict preview: {str(value)[:200]}")
            else:
                print(f"  Value: {value}")
    
    # Try the description extraction method
    print("\n" + "="*60)
    print("Testing get_product_description() method:")
    print("="*60)
    description = api.get_product_description(product_id)
    print(f"Result: {description}")
else:
    print("Failed to fetch product data!")
