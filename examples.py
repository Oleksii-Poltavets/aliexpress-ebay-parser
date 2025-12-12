"""
Example usage of the AliExpress scraper
"""
from main import AliExpressScraper
from config import Config

# Make sure to set up your .env file first!

def example_single_product():
    """Example: Process a single product"""
    print("Example 1: Single Product\n")
    
    scraper = AliExpressScraper()
    
    url = "https://www.aliexpress.com/item/1005001234567890.html"
    result = scraper.process_single_link(url)
    
    print(f"\nResult: {result}")


def example_multiple_products():
    """Example: Process multiple products"""
    print("Example 2: Multiple Products\n")
    
    scraper = AliExpressScraper()
    
    links = [
        "https://www.aliexpress.com/item/1005001234567890.html",
        "https://www.aliexpress.com/item/1005009876543210.html",
        "https://www.aliexpress.com/item/1005005555555555.html"
    ]
    
    results = scraper.process_links_list(links)
    
    print(f"\nProcessed {len(results)} products")


def example_table_processing():
    """Example: Process products from Excel file"""
    print("Example 3: Table Processing\n")
    
    scraper = AliExpressScraper()
    
    # Assuming you have a file named 'products.xlsx'
    results = scraper.process_table('products.xlsx')
    
    print(f"\nProcessed {len(results)} products from table")


def example_custom_download_folder():
    """Example: Use custom download folder"""
    print("Example 4: Custom Download Folder\n")
    
    from image_downloader import ImageDownloader
    from aliexpress_api import AliExpressAPI
    
    # Create downloader with custom folder
    downloader = ImageDownloader(base_folder='my_custom_folder')
    api = AliExpressAPI()
    
    product_id = "1005001234567890"
    
    # Get images
    image_urls = api.get_product_images(product_id)
    
    # Download to custom folder
    result = downloader.download_product_images(product_id, image_urls)
    
    print(f"\nImages saved to: {result['folder']}")


def example_url_parsing():
    """Example: Parse product URLs"""
    print("Example 5: URL Parsing\n")
    
    from url_parser import extract_product_id, validate_aliexpress_url, normalize_url
    
    urls = [
        "https://www.aliexpress.com/item/1005001234567890.html",
        "https://aliexpress.com/item/1234567890.html?spm=a2g0o.home.0.0",
        "https://www.aliexpress.ru/item/1005009999999999.html"
    ]
    
    for url in urls:
        print(f"URL: {url}")
        print(f"  Valid: {validate_aliexpress_url(url)}")
        print(f"  Product ID: {extract_product_id(url)}")
        print(f"  Normalized: {normalize_url(url)}")
        print()


if __name__ == '__main__':
    # Validate configuration first
    try:
        Config.validate()
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("Please set up your .env file with API credentials")
        exit(1)
    
    # Run examples (comment out the ones you don't want to run)
    
    # example_url_parsing()  # This one works without API credentials
    
    # These require API credentials:
    # example_single_product()
    # example_multiple_products()
    # example_table_processing()
    # example_custom_download_folder()
    
    print("\nTo run examples, uncomment the function calls in examples.py")
