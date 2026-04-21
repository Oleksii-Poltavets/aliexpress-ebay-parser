"""
AliExpress API client for product information retrieval via RapidAPI
Using Aliexpress DataHub API
"""
import time
import requests
import json
import re
from config import Config


class AliExpressAPI:
    """Client for interacting with AliExpress DataHub API via RapidAPI"""
    
    def __init__(self):
        self.api_key = Config.RAPIDAPI_KEY
        self.api_host = Config.RAPIDAPI_HOST
        self.base_url = f"https://{self.api_host}"
        self.last_request_time = 0
        self.request_delay = 1.0 / Config.MAX_REQUESTS_PER_SECOND
        
        # RapidAPI headers
        self.headers = {
            'X-RapidAPI-Key': self.api_key,
            'X-RapidAPI-Host': self.api_host
        }
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)
        self.last_request_time = time.time()
    
    def get_product_details(self, product_id):
        """
        Get detailed product information via Aliexpress DataHub API
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            Dictionary containing product details or None if error
        """
        self._rate_limit()
        
        # Prefer endpoint 6 first because it most consistently includes description payloads.
        endpoints = ['item_detail_6', 'item_detail_2', 'item_detail_3']
        
        errors = []
        
        for endpoint in endpoints:
            url = f"https://aliexpress-datahub.p.rapidapi.com/{endpoint}"
            
            querystring = {
                'itemId': str(product_id)
            }
            
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    params=querystring,
                    timeout=Config.REQUEST_TIMEOUT
                )
                
                # Check for rate limit error
                if response.status_code == 429:
                    print(f"⚠️ Rate limit exceeded! You've hit your API quota.")
                    print(f"   Please wait for your quota to reset or upgrade your plan.")
                    print(f"   Check: https://rapidapi.com/speedapi_com/api/aliexpress-datahub")
                    return None
                
                response.raise_for_status()
                
                data = response.json()
                
                # Check for API errors or empty response
                if not data or 'result' not in data:
                    errors.append(f"{endpoint}: No result in response")
                    continue
                
                result = data.get('result', {})
                status = result.get('status', {})
                
                # Check if request was successful
                if status.get('code') == 200 and status.get('data') == 'success':
                    print(f"✓ Using endpoint: {endpoint}")
                    return data
                else:
                    status_code = status.get('code', 'unknown')
                    status_data = status.get('data', 'unknown')
                    error_msg = status.get('msg', 'unknown error')
                    errors.append(f"{endpoint}: code={status_code}, data={status_data}, msg={error_msg}")
                    continue
                
            except requests.exceptions.RequestException as e:
                errors.append(f"{endpoint}: Network error: {str(e)[:100]}")
                continue
            except json.JSONDecodeError as e:
                errors.append(f"{endpoint}: JSON parse error: {str(e)[:100]}")
                continue
        
        # All endpoints failed - log details for debugging
        print(f"All endpoints failed for product {product_id}")
        if errors:
            print("  API diagnostics:")
            for error in errors:
                print(f"    - {error}")
        return None
    
    def check_availability(self, product_id, product_data=None):
        """
        Check if product is available for purchase
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            Dictionary with availability status and stock info
        """
        if product_data is None:
            product_data = self.get_product_details(product_id)
        
        if not product_data:
            return {
                'available': False,
                'reason': 'Failed to fetch product data',
                'product_id': product_id
            }
        
        # Extract product info from Aliexpress DataHub response
        result = product_data.get('result', {})
        item = result.get('item', {})
        
        # Check various availability indicators
        is_available = True
        reason = 'Available'
        stock_quantity = None
        
        # Check if product exists
        if not item:
            is_available = False
            reason = 'Product not found'
        else:
            # First check the direct 'available' field from the API
            if 'available' in item:
                is_available = item.get('available', False)
                if not is_available:
                    reason = 'Product not available'
            
            # Check stock availability - try sku.def.quantity first
            sku = item.get('sku', {})
            sku_def = sku.get('def', {})
            
            if 'quantity' in sku_def:
                stock_quantity = sku_def.get('quantity', 0)
                if stock_quantity <= 0:
                    is_available = False
                    reason = 'Out of stock'
            elif 'totalAvailableStock' in item:
                stock_quantity = item.get('totalAvailableStock', 0)
                if stock_quantity <= 0:
                    is_available = False
                    reason = 'Out of stock'
            elif 'stock' in item:
                stock_quantity = item.get('stock', 0)
                if stock_quantity <= 0:
                    is_available = False
                    reason = 'Out of stock'
            
            # Check if item is offline/removed
            if item.get('itemStatus') == 'offline' or item.get('offline', False):
                is_available = False
                reason = 'Product is offline'
        
        return {
            'available': is_available,
            'reason': reason,
            'product_id': product_id,
            'stock_quantity': stock_quantity,
            'product_title': item.get('title', 'N/A') if item else 'N/A'
        }
    
    def get_product_images(self, product_id, product_data=None):
        """
        Get list of product image URLs
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            List of image URLs
        """
        if product_data is None:
            product_data = self.get_product_details(product_id)
        
        if not product_data:
            return []
        
        result = product_data.get('result', {})
        item = result.get('item', {})
        images = []
        
        # Get main image
        main_image = item.get('mainImageUrl') or item.get('imageUrl') or item.get('image')
        if main_image:
            images.append(main_image)
        
        # Get additional images from various possible fields
        image_list = (
            item.get('imageUrls') or 
            item.get('images') or 
            item.get('productImages') or
            item.get('imagePathList') or
            []
        )
        
        if isinstance(image_list, list):
            images.extend(image_list)
        elif isinstance(image_list, str):
            # Some APIs return semicolon or comma separated strings
            for separator in [';', ',', '|']:
                if separator in image_list:
                    additional_images = [url.strip() for url in image_list.split(separator) if url.strip()]
                    images.extend(additional_images)
                    break
            else:
                if image_list.strip():
                    images.append(image_list.strip())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_images = []
        for img in images:
            if img and img not in seen:
                # Fix protocol-relative URLs
                if img.startswith('//'):
                    img = 'https:' + img
                seen.add(img)
                unique_images.append(img)
        
        return unique_images
    
    def get_product_title(self, product_id, product_data=None):
        """
        Get product title
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            Product title string or None
        """
        if product_data is None:
            product_data = self.get_product_details(product_id)
        
        if not product_data:
            return None
        
        result = product_data.get('result', {})
        item = result.get('item', {})
        
        return item.get('title') or item.get('subject') or 'N/A'

    def get_seller_name(self, product_id, product_data=None):
        """
        Get seller/store name

        Args:
            product_id: AliExpress product ID

        Returns:
            Seller name string or None
        """
        if product_data is None:
            product_data = self.get_product_details(product_id)

        if not product_data:
            return None

        result = product_data.get('result', {})
        seller = result.get('seller', {})
        item = result.get('item', {})

        return (
            seller.get('storeTitle') or
            seller.get('storeName') or
            seller.get('companyName') or
            item.get('storeName') or
            item.get('sellerName') or
            'N/A'
        )
    
    def get_product_price(self, product_id, product_data=None):
        """
        Get product price information
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            Dictionary with price information (currency, min_price, max_price, formatted)
        """
        if product_data is None:
            product_data = self.get_product_details(product_id)
        
        if not product_data:
            return {
                'currency': 'N/A',
                'min_price': None,
                'max_price': None,
                'formatted': 'N/A'
            }
        
        result = product_data.get('result', {})
        item = result.get('item', {})
        
        # Try to get price from various possible fields
        price_info = {}
        
        # Get currency from settings or item
        settings = result.get('settings', {})
        currency = settings.get('currency') or item.get('currency') or item.get('targetCurrency') or 'USD'
        
        # Try to get price from sku.def first (most reliable)
        sku = item.get('sku', {})
        sku_def = sku.get('def', {})
        
        min_price = None
        max_price = None
        
        if sku_def:
            # Use promotion price if available, otherwise regular price
            promo_price = sku_def.get('promotionPrice')
            regular_price = sku_def.get('price')
            
            # Helper to extract price from string that might contain ranges like "3.26 - 4.61"
            def parse_price(price_val):
                if price_val is None:
                    return None
                if isinstance(price_val, (int, float)):
                    return float(price_val)
                if isinstance(price_val, str):
                    # Handle price ranges like "3.26 - 4.61"
                    if ' - ' in price_val:
                        parts = price_val.split(' - ')
                        try:
                            return float(parts[0].strip())  # Return minimum price
                        except (ValueError, IndexError):
                            pass
                    try:
                        return float(price_val)
                    except ValueError:
                        return None
                return None
            
            if promo_price:
                min_price = parse_price(promo_price)
            elif regular_price:
                min_price = parse_price(regular_price)
        
        # Fallback to other price fields if sku.def doesn't have price
        if min_price is None:
            sale_price = item.get('salePrice', {})
            if isinstance(sale_price, dict):
                min_price = sale_price.get('min') or sale_price.get('minPrice')
                max_price = sale_price.get('max') or sale_price.get('maxPrice')
            else:
                # Try other fields
                min_price = (
                    item.get('minPrice') or 
                    item.get('price') or 
                    item.get('targetMinPrice') or
                    item.get('sku_min_price')
                )
                max_price = (
                    item.get('maxPrice') or 
                    item.get('targetMaxPrice') or
                    item.get('sku_max_price')
                )
        
        # Format price string without currency symbols/codes
        if min_price is not None and max_price is not None:
            if min_price == max_price:
                formatted = str(min_price)
            else:
                formatted = f"{min_price} - {max_price}"
        elif min_price is not None:
            formatted = str(min_price)
        else:
            formatted = 'N/A'
        
        return {
            'currency': currency,
            'min_price': min_price,
            'max_price': max_price,
            'formatted': formatted
        }

    def get_shipping_price(self, product_id, product_data=None):
        """Get the cheapest available shipping fee for a product."""
        if product_data is None:
            product_data = self.get_product_details(product_id)

        if not product_data:
            return ''

        result = product_data.get('result', {})
        delivery = result.get('delivery', {})
        shipping_list = delivery.get('shippingList') or []

        fees = []
        for option in shipping_list:
            for key in ('shippingFee', 'shippingPrice', 'cost', 'fee'):
                fee = option.get(key)
                if fee in (None, ''):
                    continue
                try:
                    fees.append(float(fee))
                except (TypeError, ValueError):
                    continue

        # Fallbacks for responses where shipping options are summarized differently.
        for key in ('shippingFee', 'shippingPrice', 'minShippingFee'):
            fee = delivery.get(key)
            if fee in (None, ''):
                continue
            try:
                fees.append(float(fee))
            except (TypeError, ValueError):
                continue

        if not fees:
            return ''

        cheapest_fee = min(fees)
        return str(int(cheapest_fee)) if cheapest_fee.is_integer() else str(cheapest_fee)
    
    def get_product_description(self, product_id, product_data=None):
        """
        Get full product description from seller
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            Product description string or None
        """
        if product_data is None:
            product_data = self.get_product_details(product_id)
        
        if not product_data:
            return None
        
        result = product_data.get('result', {})
        item = result.get('item', {})
        
        # Try various description fields - prioritize full description
        description = (
            item.get('description') or 
            item.get('productDescription') or
            item.get('detail') or
            item.get('descriptionUrl')  # Sometimes only URL is provided
        )

        raw_html_description = None
        
        # Handle if description is a dictionary
        if isinstance(description, dict):
            # Try to get HTML description first, then other common fields
            raw_html_description = description.get('html')
            description = (
                description.get('html') or
                description.get('text') or 
                description.get('en') or 
                description.get('english') or 
                next(iter(description.values()), None) if description else None
            )
        
        if description and isinstance(description, str):
            original_description = description
            # Strip HTML tags
            description = re.sub(r'<[^>]+>', '', description)
            # Clean up extra whitespace and newlines
            description = re.sub(r'\s+', ' ', description).strip()

            # Some products provide description only as rich HTML/images with no plain text.
            if not description:
                if raw_html_description and isinstance(raw_html_description, str):
                    return raw_html_description.strip() or 'N/A'
                if '<' in original_description and '>' in original_description:
                    return original_description.strip() or 'N/A'
        
        return description or 'N/A'
