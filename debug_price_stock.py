"""Debug script to check AliExpress price and stock extraction"""
import json
from aliexpress_api import AliExpressAPI

api = AliExpressAPI()
product_id = "1005004049949624"

print(f"Testing price and stock for product: {product_id}\n")

# Get full data
data = api.get_product_details(product_id)

if data:
    result = data.get('result', {})
    item = result.get('item', {})
    
    print("="*60)
    print("SKU DATA:")
    print("="*60)
    sku_data = item.get('sku', {})
    print(json.dumps(sku_data, indent=2))
    
    print("\n" + "="*60)
    print("PRICE EXTRACTION TEST:")
    print("="*60)
    price_info = api.get_product_price(product_id)
    print(f"Result: {price_info}")
    
    print("\n" + "="*60)
    print("AVAILABILITY/STOCK TEST:")
    print("="*60)
    availability = api.check_availability(product_id)
    print(f"Result: {availability}")
    
    print("\n" + "="*60)
    print("CHECKING OTHER POSSIBLE FIELDS:")
    print("="*60)
    
    # Check for price in other locations
    if 'price' in item:
        print(f"item.price: {item.get('price')}")
    if 'salePrice' in item:
        print(f"item.salePrice: {item.get('salePrice')}")
    if 'totalAvailableStock' in item:
        print(f"item.totalAvailableStock: {item.get('totalAvailableStock')}")
    if 'stock' in item:
        print(f"item.stock: {item.get('stock')}")
