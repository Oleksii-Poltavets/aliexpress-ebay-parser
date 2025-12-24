"""More thorough debug of description extraction"""
from aliexpress_api import AliExpressAPI
import re

api = AliExpressAPI()
product_id = "1005004049949624"

print(f"Testing description extraction for product: {product_id}\n")
data = api.get_product_details(product_id)

if data:
    result = data.get('result', {})
    item = result.get('item', {})
    
    desc_dict = item.get('description')
    print(f"Description dict: {type(desc_dict)}")
    
    if isinstance(desc_dict, dict):
        html = desc_dict.get('html', '')
        print(f"\nHTML content (first 500 chars):")
        print(html[:500])
        
        # Strip HTML tags
        text = re.sub(r'<[^>]+>', '', html)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        print(f"\nAfter stripping HTML tags:")
        print(f"Length: {len(text)}")
        print(f"Content: '{text}'")
        
        print(f"\nIs empty after strip: {not text}")
        
        # Alternative: Keep a simplified version if only images
        if not text and html:
            # Count images in description
            img_count = html.count('<img')
            print(f"\nDescription contains {img_count} images but no text")
            print(f"Should we return '[Description contains {img_count} product images]' instead of N/A?")

print("\n" + "="*60)
description = api.get_product_description(product_id)
print(f"Final result from get_product_description(): {description}")
