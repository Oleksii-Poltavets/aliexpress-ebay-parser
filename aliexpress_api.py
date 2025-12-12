"""
AliExpress API client for product information retrieval via RapidAPI
Using Aliexpress DataHub API
"""
import time
import requests
import json
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
