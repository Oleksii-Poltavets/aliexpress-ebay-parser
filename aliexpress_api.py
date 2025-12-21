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
        
        # Aliexpress DataHub endpoint - using item_detail_6 which has better data coverage
        url = f"https://aliexpress-datahub.p.rapidapi.com/item_detail_6"
        
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
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors or empty response
            # For item_detail_6, data is in result.item
            if not data or 'result' not in data:
                print(f"No data returned for product {product_id}")
                return None
            
            result = data.get('result', {})
            status = result.get('status', {})
            
            # Check if request was successful
            if status.get('code') != 200 or status.get('data') != 'success':
                print(f"API error for product {product_id}: {status}")
                return None
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed for product {product_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None
        except json.JSONDecodeError as e:
            print(f"Failed to parse response for product {product_id}: {e}")
            return None
    
    def check_availability(self, product_id):
        """
        Check if product is available for purchase
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            Dictionary with availability status and stock info
        """
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
            # Check stock availability
            if 'totalAvailableStock' in item:
                stock_quantity = item.get('totalAvailableStock', 0)
                if stock_quantity <= 0:
                    is_available = False
                    reason = 'Out of stock'
            
            # Alternative stock check
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
    
    def get_product_images(self, product_id):
        """
        Get list of product image URLs
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            List of image URLs
        """
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
    
    def get_product_title(self, product_id):
        """
        Get product title
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            Product title string or None
        """
        product_data = self.get_product_details(product_id)
        
        if not product_data:
            return None
        
        result = product_data.get('result', {})
        item = result.get('item', {})
        
        return item.get('title') or item.get('subject') or 'N/A'
    
    def get_product_price(self, product_id):
        """
        Get product price information
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            Dictionary with price information (currency, min_price, max_price, formatted)
        """
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
        
        # Get currency
        currency = item.get('currency') or item.get('targetCurrency') or 'USD'
        
        # Try to get price from salePrice or price object
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
        
        # Format price string
        if min_price is not None and max_price is not None:
            if min_price == max_price:
                formatted = f"{currency} {min_price}"
            else:
                formatted = f"{currency} {min_price} - {max_price}"
        elif min_price is not None:
            formatted = f"{currency} {min_price}"
        else:
            formatted = 'N/A'
        
        return {
            'currency': currency,
            'min_price': min_price,
            'max_price': max_price,
            'formatted': formatted
        }
    
    def get_product_description(self, product_id):
        """
        Get full product description from seller
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            Product description string or None
        """
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
        
        if description:
            # Strip HTML tags
            description = re.sub(r'<[^>]+>', '', description)
            # Clean up extra whitespace and newlines
            description = re.sub(r'\s+', ' ', description).strip()
        
        return description or 'N/A'
