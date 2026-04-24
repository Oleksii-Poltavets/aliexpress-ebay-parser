"""
AliExpress API client for product information retrieval via RapidAPI
Using Aliexpress DataHub API
"""
import time
import requests
import json
import re
from html import unescape
from config import Config


class AliExpressAPI:
    """Client for interacting with AliExpress DataHub API via RapidAPI"""
    
    def __init__(self):
        self.api_key = Config.RAPIDAPI_KEY
        self.api_host = Config.RAPIDAPI_HOST
        self.base_url = f"https://{self.api_host}"
        self.last_request_time = 0
        self.request_delay = 1.0 / Config.MAX_REQUESTS_PER_SECOND
        self._item_desc_cache = {}
        self._product_page_cache = {}
        
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
        # Prefer endpoint 6 first because it most consistently includes description payloads.
        endpoints = ['item_detail_6', 'item_detail_2', 'item_detail_3']
        max_attempts = 3
        all_errors = []

        for attempt in range(1, max_attempts + 1):
            self._rate_limit()
            attempt_errors = []

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
                        print("⚠️ Rate limit exceeded! You've hit your API quota.")
                        print("   Please wait for your quota to reset or upgrade your plan.")
                        print("   Check: https://rapidapi.com/speedapi_com/api/aliexpress-datahub")
                        return None

                    response.raise_for_status()

                    data = response.json()

                    # Check for API errors or empty response
                    if not data or 'result' not in data:
                        attempt_errors.append(f"{endpoint}: No result in response")
                        continue

                    result = data.get('result', {})
                    status = result.get('status', {})

                    # Check if request was successful
                    if status.get('code') == 200 and status.get('data') == 'success':
                        print(f"✓ Using endpoint: {endpoint}")
                        return data

                    status_code = status.get('code', 'unknown')
                    status_data = status.get('data', 'unknown')
                    error_msg = status.get('msg', 'unknown error')
                    attempt_errors.append(
                        f"{endpoint}: code={status_code}, data={status_data}, msg={error_msg}"
                    )

                except requests.exceptions.RequestException as e:
                    attempt_errors.append(f"{endpoint}: Network error: {str(e)[:100]}")
                except json.JSONDecodeError as e:
                    attempt_errors.append(f"{endpoint}: JSON parse error: {str(e)[:100]}")

            all_errors.extend([f"attempt {attempt} - {err}" for err in attempt_errors])

            # Retry transient endpoint failures before giving up.
            if attempt < max_attempts:
                time.sleep(min(1.5 * attempt, 3.0))

        # All endpoints failed - log details for debugging
        print(f"All endpoints failed for product {product_id}")
        if all_errors:
            print("  API diagnostics:")
            for error in all_errors:
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
    
    def get_product_images(self, product_id, product_data=None, product_url=None):
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
            images = self._get_images_from_item_desc(product_id)
            if images:
                return images
            return self._get_images_from_product_page(product_id, product_url=product_url)
        
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

        if unique_images:
            return unique_images

        # Fallback when item_detail payload exists but carries no image list.
        images = self._get_images_from_item_desc(product_id)
        if images:
            return images
        return self._get_images_from_product_page(product_id, product_url=product_url)

    def _get_images_from_product_page(self, product_id, product_url=None):
        """Fallback: extract image URLs from public product page HTML."""
        image_urls = []
        seen = set()

        for page_html in self._get_product_page_html_candidates(product_url, product_id):
            # Preferred source when present in embedded data.
            list_match = re.search(r'"imagePathList"\s*:\s*\[(.*?)\]', page_html, re.IGNORECASE | re.DOTALL)
            if list_match:
                payload = list_match.group(1)
                for match in re.findall(r'"(https?:)?//([^"\\]+)"', payload):
                    prefix, path = match
                    url = f"{prefix or 'https:'}//{path}"
                    if url not in seen:
                        seen.add(url)
                        image_urls.append(url)

            # Generic fallback for direct image links in page source.
            for url in re.findall(r'(https?:)?//[^"\'\s>]+\.(?:jpg|jpeg|png|webp)', page_html, re.IGNORECASE):
                if isinstance(url, tuple):
                    # When regex returns groups, rebuild the full URL.
                    url = ''.join(url)
                if url.startswith('//'):
                    url = 'https:' + url
                elif not url.startswith('http'):
                    url = 'https://' + url.lstrip('/')
                if 'alicdn.com' not in url and 'aliexpress-media.com' not in url:
                    continue
                if url not in seen:
                    seen.add(url)
                    image_urls.append(url)

        return image_urls

    def _get_item_desc_item(self, product_id):
        """Fetch and cache item payload from item_desc endpoint."""
        cache_key = str(product_id)
        if cache_key in self._item_desc_cache:
            return self._item_desc_cache[cache_key]

        self._rate_limit()
        url = f"{self.base_url}/item_desc"
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params={'itemId': str(product_id)},
                timeout=Config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            result = data.get('result', {})
            status = result.get('status', {})
            if status.get('code') != 200 or status.get('data') != 'success':
                self._item_desc_cache[cache_key] = None
                return None

            item = result.get('item', {})
            self._item_desc_cache[cache_key] = item if isinstance(item, dict) else None
            return self._item_desc_cache[cache_key]
        except Exception:
            self._item_desc_cache[cache_key] = None
            return None

    def _get_images_from_item_desc(self, product_id):
        """Fallback: fetch image URLs from the dedicated item_desc endpoint."""
        item = self._get_item_desc_item(product_id)
        try:
            desc = (item or {}).get('description', {})
            images = desc.get('images') if isinstance(desc, dict) else []
            if not isinstance(images, list):
                return []

            unique_images = []
            seen = set()
            for img in images:
                if not img:
                    continue
                if isinstance(img, str) and img.startswith('//'):
                    img = 'https:' + img
                if img in seen:
                    continue
                seen.add(img)
                unique_images.append(img)
            return unique_images
        except Exception:
            return []
    
    def get_product_title(self, product_id, product_data=None, product_url=None):
        """
        Get product title
        
        Args:
            product_id: AliExpress product ID
            
        Returns:
            Product title string or None
        """
        if product_data is None:
            product_data = self.get_product_details(product_id)

        if product_data:
            result = product_data.get('result', {})
            item = result.get('item', {})
            title = item.get('title') or item.get('subject')
            if title:
                return title

        # Fallbacks when item_detail endpoints return empty.
        fallback_title = self._get_title_from_item_desc(product_id)
        if fallback_title:
            return fallback_title

        fallback_title = self._get_title_from_product_page(product_url, product_id)
        if fallback_title:
            return fallback_title

        return 'N/A'

    def _get_title_from_item_desc(self, product_id):
        """Fallback title from item_desc payload when available."""
        item = self._get_item_desc_item(product_id)
        if not item:
            return None

        for key in ('title', 'subject', 'name', 'itemTitle'):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _get_title_from_product_page(self, product_url, product_id):
        """Fallback title by parsing og:title/title from public product page."""
        for page_html in self._get_product_page_html_candidates(product_url, product_id):
            try:
                og_idx = page_html.lower().find('property="og:title"')
                if og_idx >= 0:
                    tag_end = page_html.find('>', og_idx)
                    if tag_end > og_idx:
                        og_tag = page_html[og_idx:tag_end + 1]
                        content_marker = 'content="'
                        marker_idx = og_tag.find(content_marker)
                        if marker_idx >= 0:
                            value_start = marker_idx + len(content_marker)
                            value_end = og_tag.rfind('"')
                            if value_end > value_start:
                                raw_title = unescape(og_tag[value_start:value_end]).strip()
                                clean_title = re.sub(r'\s*-\s*AliExpress.*$', '', raw_title, flags=re.IGNORECASE).strip()
                                if len(clean_title) > 5:
                                    return clean_title

                og_match = re.search(
                    r'<meta[^>]+property=["\']og:title["\'][^>]+content=(["\'])(.*?)\1',
                    page_html,
                    re.IGNORECASE | re.DOTALL,
                )
                if og_match:
                    title = unescape(og_match.group(2)).strip()
                    clean_title = re.sub(r'\s*-\s*AliExpress.*$', '', title, flags=re.IGNORECASE).strip()
                    if len(clean_title) > 5:
                        return clean_title

                title_match = re.search(r'<title>(.*?)</title>', page_html, re.IGNORECASE | re.DOTALL)
                if title_match:
                    raw_title = unescape(title_match.group(1))
                    clean_title = re.sub(r'\s+', ' ', raw_title).strip()
                    clean_title = re.sub(r'\s*\|\s*AliExpress.*$', '', clean_title, flags=re.IGNORECASE)
                    clean_title = re.sub(r'\s*-\s*AliExpress.*$', '', clean_title, flags=re.IGNORECASE)
                    if clean_title:
                        return clean_title
            except Exception:
                continue

        return None

    def _get_product_page_html_candidates(self, product_url, product_id):
        """Fetch candidate public product pages once and reuse them across fallbacks."""
        candidate_urls = []
        if product_url:
            candidate_urls.append(product_url)
        candidate_urls.append(f"https://www.aliexpress.com/item/{product_id}.html")
        candidate_urls.append(f"https://www.aliexpress.us/item/{product_id}.html")

        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            )
        }

        for url in candidate_urls:
            if not url or url in self._product_page_cache:
                cached_html = self._product_page_cache.get(url)
                if cached_html:
                    yield cached_html
                continue
            try:
                response = requests.get(url, headers=headers, timeout=Config.REQUEST_TIMEOUT)
                response.raise_for_status()
                page_html = response.text or ''
                self._product_page_cache[url] = page_html
                if page_html:
                    yield page_html
            except Exception:
                self._product_page_cache[url] = None
                continue

    def infer_availability_from_page(self, product_id, product_url=None):
        """Best-effort availability fallback from public page and item_desc presence."""
        if self._get_item_desc_item(product_id):
            return True

        unavailable_markers = [
            'sorry, this page is not available',
            'page not found',
            'this item is no longer available',
            'product is unavailable',
            'oops! looks like this page is unavailable',
            'item temporarily unavailable',
        ]
        for page_html in self._get_product_page_html_candidates(product_url, product_id):
            html_probe = page_html[:12000].lower()
            if any(marker in html_probe for marker in unavailable_markers):
                return False
            if self._get_title_from_product_page(product_url, product_id):
                return True

        return None

    def _get_shipping_price_from_description(self, product_id):
        """Best-effort shipping fallback parsed from item_desc text."""
        description = self._get_description_from_item_desc(product_id) or ''
        if not description:
            return ''

        description_lower = description.lower()
        if '$free' in description_lower or 'free shipping' in description_lower:
            return '0'

        patterns = [
            r'shipping[^:]{0,60}:\s*(?:us\s*\$|\$)\s*(\d+(?:\.\d+)?)',
            r'(?:shipping fee|shipping price|delivery fee)[^:]{0,40}:\s*(?:us\s*\$|\$)\s*(\d+(?:\.\d+)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if not match:
                continue
            fee = float(match.group(1))
            return str(int(fee)) if fee.is_integer() else str(fee)

        return ''

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
            return self._get_shipping_price_from_description(product_id)

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
            return self._get_shipping_price_from_description(product_id)

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

        description = None

        if product_data:
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

        # If still no description, fall back to dedicated item_desc endpoint
        if not description:
            description = self._get_description_from_item_desc(product_id)

        return description or 'N/A'

    def _get_description_from_item_desc(self, product_id):
        """
        Fallback: fetch description from the dedicated item_desc endpoint.
        Returns a plain-text string or None.
        """
        item = self._get_item_desc_item(product_id)
        try:
            desc = (item or {}).get('description', {})
            if not isinstance(desc, dict):
                return None
            text = desc.get('text')
            if isinstance(text, list):
                # Join list items into a single string
                text = ' '.join(str(t) for t in text if t).strip()
            elif isinstance(text, str):
                text = text.strip()
            else:
                text = None
            return text or None
        except Exception:
            return None
