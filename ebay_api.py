"""
eBay API client for product information retrieval
Uses OAuth 2.0 Client Credentials flow for authentication
"""
import requests
import base64
import time
import re
from config import Config
from logger import get_logger

logger = get_logger(__name__)


class EbayAPI:
    """Client for eBay Browse API"""
    
    def __init__(self):
        self.app_id = Config.EBAY_APP_ID
        self.cert_id = Config.EBAY_CERT_ID
        self.environment = Config.EBAY_ENVIRONMENT
        
        # Set base URLs based on environment
        if self.environment == 'PRODUCTION':
            self.api_base_url = 'https://api.ebay.com'
            self.auth_url = 'https://api.ebay.com/identity/v1/oauth2/token'
        else:  # SANDBOX
            self.api_base_url = 'https://api.sandbox.ebay.com'
            self.auth_url = 'https://api.sandbox.ebay.com/identity/v1/oauth2/token'
        
        self.access_token = None
        self.token_expiry = 0
        
        logger.info(f"Initialized eBay API client ({self.environment} environment)")
    
    def _get_access_token(self):
        """
        Get OAuth 2.0 access token using client credentials flow
        
        Returns:
            Access token string
        """
        # Check if we have a valid token
        if self.access_token and time.time() < self.token_expiry:
            return self.access_token
        
        logger.info("Requesting new eBay OAuth token...")
        
        # Create authorization header (Base64 encoded "AppID:CertID")
        credentials = f"{self.app_id}:{self.cert_id}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {b64_credentials}'
        }
        
        data = {
            'grant_type': 'client_credentials',
            'scope': 'https://api.ebay.com/oauth/api_scope'
        }
        
        try:
            response = requests.post(
                self.auth_url,
                headers=headers,
                data=data,
                timeout=Config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            # Set expiry to 5 minutes before actual expiry for safety
            self.token_expiry = time.time() + token_data['expires_in'] - 300
            
            logger.info("Successfully obtained eBay OAuth token")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get eBay access token: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise
    
    def get_product_details(self, item_id):
        """
        Get product details using eBay Browse API
        
        Args:
            item_id: eBay item ID (legacy item ID or new v1|itemId|0 format)
            
        Returns:
            Dictionary with product details or None on error
        """
        token = self._get_access_token()
        
        # Try to get item using legacy ID first (more common from URLs)
        url = f"{self.api_base_url}/buy/browse/v1/item/get_item_by_legacy_id"
        
        headers = {
            'Authorization': f'Bearer {token}',
            'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US'  # Can be made configurable
        }
        
        params = {
            'legacy_item_id': item_id
        }
        
        try:
            logger.info(f"Fetching eBay product details for item {item_id}")
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=Config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Successfully fetched details for eBay item {item_id}")
            return data
            
        except requests.exceptions.HTTPError as e:
            # Check if this is an item group (error 11006)
            if e.response.status_code == 400:
                try:
                    error_data = e.response.json()
                    if error_data.get('errors', [{}])[0].get('errorId') == 11006:
                        # This is an item group, try getting group details
                        logger.info(f"Item {item_id} is an item group, fetching group details")
                        return self._get_item_group_details(item_id)
                except:
                    pass
            
            logger.error(f"Request failed for product {item_id}: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for product {item_id}: {e}")
            return None
    
    def _get_item_group_details(self, item_group_id):
        """
        Get item group details (for listings with variations)
        
        Args:
            item_group_id: eBay item group ID
            
        Returns:
            Dictionary with aggregated item group details or None on error
        """
        token = self._get_access_token()
        
        url = f"{self.api_base_url}/buy/browse/v1/item/get_items_by_item_group"
        
        headers = {
            'Authorization': f'Bearer {token}',
            'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US'
        }
        
        params = {
            'item_group_id': item_group_id
        }
        
        try:
            logger.info(f"Fetching eBay item group details for {item_group_id}")
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=Config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                logger.warning(f"No items found in group {item_group_id}")
                return None
            
            # Return the first item from the group as representative
            # but mark it as an item group
            first_item = items[0]
            first_item['_is_item_group'] = True
            first_item['_item_group_size'] = len(items)
            
            # Aggregate availability from all items in the group
            total_quantity = 0
            for item in items:
                qty = item.get('estimatedAvailabilities', [{}])[0].get('estimatedAvailableQuantity', 0)
                total_quantity += qty
            
            # Update the quantity to reflect total across all variations
            if first_item.get('estimatedAvailabilities'):
                first_item['estimatedAvailabilities'][0]['estimatedAvailableQuantity'] = total_quantity
            
            logger.info(f"Successfully fetched item group {item_group_id} with {len(items)} variations")
            return first_item
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Request failed for item group {item_group_id}: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for item group {item_group_id}: {e}")
            return None
    
    def check_availability(self, item_id):
        """
        Check if a product is available for purchase
        
        Args:
            item_id: eBay item ID
            
        Returns:
            Tuple of (is_available: bool, quantity: int, reason: str)
        """
        product_data = self.get_product_details(item_id)
        
        if not product_data:
            return False, 0, "Failed to fetch product data"
        
        # Check if listing has ended
        item_end_date = product_data.get('itemEndDate')
        if item_end_date:
            from datetime import datetime
            try:
                end_date = datetime.fromisoformat(item_end_date.replace('Z', '+00:00'))
                if end_date < datetime.now(end_date.tzinfo):
                    return False, 0, "Listing has ended"
            except:
                pass  # If date parsing fails, continue with other checks
        
        # Check if item is available for purchase
        available_quantity = product_data.get('estimatedAvailabilities', [{}])[0].get('estimatedAvailableQuantity', 0)
        
        # Check item condition (buyingOptions)
        buying_options = product_data.get('buyingOptions', [])
        
        # Check if item is active (itemWebUrl exists and no error messages)
        is_active = bool(product_data.get('itemWebUrl'))
        
        if not is_active:
            return False, 0, "Item is not active"
        
        if available_quantity > 0:
            return True, available_quantity, "Available"
        else:
            return False, 0, "Out of stock"
    
    def get_product_images(self, item_id):
        """
        Get product image URLs
        
        Args:
            item_id: eBay item ID
            
        Returns:
            List of image URLs
        """
        product_data = self.get_product_details(item_id)
        
        if not product_data:
            logger.warning(f"No product data found for {item_id}")
            return []
        
        images = []
        
        # Get main image
        if 'image' in product_data:
            image_url = product_data['image'].get('imageUrl')
            if image_url:
                images.append(image_url)
        
        # Get additional images
        if 'additionalImages' in product_data:
            for img in product_data['additionalImages']:
                image_url = img.get('imageUrl')
                if image_url:
                    images.append(image_url)
        
        logger.info(f"Found {len(images)} images for eBay product {item_id}")
        return images
    
    def get_product_title(self, item_id):
        """
        Get product title
        
        Args:
            item_id: eBay item ID
            
        Returns:
            Product title string or None
        """
        product_data = self.get_product_details(item_id)
        
        if not product_data:
            return None
        
        return product_data.get('title', 'Unknown Product')
    
    def get_product_price(self, item_id):
        """
        Get product price information
        
        Args:
            item_id: eBay item ID
            
        Returns:
            Dictionary with price information (currency, value, formatted)
        """
        product_data = self.get_product_details(item_id)
        
        if not product_data:
            return {
                'currency': 'N/A',
                'value': None,
                'formatted': 'N/A'
            }
        
        # Get price from product data
        price_obj = product_data.get('price', {})
        
        if isinstance(price_obj, dict):
            currency = price_obj.get('currency', 'USD')
            value = price_obj.get('value')
            
            if value is not None:
                formatted = f"{currency} {value}"
            else:
                formatted = 'N/A'
        else:
            currency = 'N/A'
            value = None
            formatted = 'N/A'
        
        return {
            'currency': currency,
            'value': value,
            'formatted': formatted
        }
    
    def get_product_description(self, item_id):
        """
        Get full product description from seller
        
        Args:
            item_id: eBay item ID
            
        Returns:
            Product description string or None
        """
        product_data = self.get_product_details(item_id)
        
        if not product_data:
            return None
        
        # Get full description from seller
        # eBay Browse API provides description in the 'description' field
        # which contains the full HTML description from the seller
        description = product_data.get('description')
        
        if not description:
            # Fallback to shortDescription if description is not available
            description = product_data.get('shortDescription')
        
        if description:
            # Strip HTML tags
            description = re.sub(r'<[^>]+>', '', description)
            # Clean up extra whitespace and newlines
            description = re.sub(r'\s+', ' ', description).strip()
        
        return description or 'N/A'
