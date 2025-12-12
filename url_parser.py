"""
Utility functions for parsing AliExpress and eBay product links
"""
import re
from urllib.parse import urlparse, parse_qs


def extract_product_id(url):
    """
    Extract product ID from AliExpress URL
    
    Args:
        url: AliExpress product URL
        
    Returns:
        Product ID as string, or None if not found
        
    Examples:
        https://www.aliexpress.com/item/1005001234567890.html -> 1005001234567890
        https://aliexpress.com/item/1234567890.html?param=value -> 1234567890
    """
    # Pattern 1: /item/{product_id}.html
    pattern1 = r'/item/(\d+)\.html'
    match = re.search(pattern1, url)
    if match:
        return match.group(1)
    
    # Pattern 2: /item/{product_id} (without .html)
    pattern2 = r'/item/(\d+)'
    match = re.search(pattern2, url)
    if match:
        return match.group(1)
    
    # Pattern 3: Query parameter productId or product_id
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    
    if 'productId' in params:
        return params['productId'][0]
    if 'product_id' in params:
        return params['product_id'][0]
    
    return None


def validate_aliexpress_url(url):
    """
    Validate if URL is from AliExpress
    
    Args:
        url: URL string to validate
        
    Returns:
        Boolean indicating if URL is valid AliExpress URL
    """
    if not url:
        return False
    
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Support both .com, .us, and .ru domains
    return any(d in domain for d in ['aliexpress.com', 'aliexpress.us', 'aliexpress.ru'])


def normalize_url(url):
    """
    Normalize AliExpress URL by removing unnecessary parameters
    
    Args:
        url: Raw product URL
        
    Returns:
        Normalized URL string
    """
    product_id = extract_product_id(url)
    if not product_id:
        return url
    
    return f"https://www.aliexpress.com/item/{product_id}.html"


# eBay URL parsing functions

def extract_ebay_item_id(url):
    """
    Extract item ID from eBay URL
    
    Args:
        url: eBay product URL
        
    Returns:
        Item ID as string, or None if not found
        
    Examples:
        https://www.ebay.com/itm/123456789012 -> 123456789012
        https://ebay.com/itm/123456789012?param=value -> 123456789012
    """
    # Pattern 1: /itm/{item_id}
    pattern1 = r'/itm/(\d+)'
    match = re.search(pattern1, url)
    if match:
        return match.group(1)
    
    # Pattern 2: Query parameter item or itemId
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    
    if 'item' in params:
        return params['item'][0]
    if 'itemId' in params:
        return params['itemId'][0]
    
    return None


def validate_ebay_url(url):
    """
    Validate if URL is from eBay
    
    Args:
        url: URL string to validate
        
    Returns:
        Boolean indicating if URL is valid eBay URL
    """
    if not url:
        return False
    
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    return 'ebay.com' in domain


def detect_marketplace(url):
    """
    Detect which marketplace a URL belongs to
    
    Args:
        url: Product URL
        
    Returns:
        String: 'aliexpress', 'ebay', or 'unknown'
    """
    if validate_aliexpress_url(url):
        return 'aliexpress'
    elif validate_ebay_url(url):
        return 'ebay'
    else:
        return 'unknown'

