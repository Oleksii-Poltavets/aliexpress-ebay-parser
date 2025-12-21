"""
Main orchestrator for AliExpress and eBay product scraper
"""
import sys
from pathlib import Path
from datetime import datetime
from config import Config
from url_parser import (
    extract_product_id, validate_aliexpress_url,
    extract_ebay_item_id, validate_ebay_url, detect_marketplace
)
from aliexpress_api import AliExpressAPI
from ebay_api import EbayAPI
from image_downloader import ImageDownloader
from table_processor import TableProcessor


class ProductScraper:
    """Main orchestrator for scraping AliExpress and eBay products"""
    
    def __init__(self):
        self.aliexpress_api = AliExpressAPI()
        self.ebay_api = EbayAPI()
        self.downloader = ImageDownloader()
        self.results = []
    
    def process_single_link(self, url, row_index=None, folder_name=None):
        """
        Process a single product link (AliExpress or eBay)
        
        Args:
            url: Product URL
            row_index: Optional row index from table (for folder naming)
            folder_name: Optional custom folder name (overrides row_number)
            
        Returns:
            Dictionary with processing results
        """
        print(f"\n{'='*60}")
        print(f"Processing: {url}")
        print(f"{'='*60}")
        
        result = {
            'url': url,
            'row_index': row_index,
            'row_number': row_index + 1 if row_index is not None else None,
            'folder_name': folder_name,
            'marketplace': None,
            'product_id': None,
            'title': None,
            'description': None,
            'price': None,
            'available': False,
            'stock_quantity': None,
            'images_downloaded': 0,
            'folder': None,
            'error': None
        }
        
        # Detect marketplace
        marketplace = detect_marketplace(url)
        result['marketplace'] = marketplace
        
        if marketplace == 'unknown':
            result['error'] = 'Invalid URL - not from AliExpress or eBay'
            print(f"❌ {result['error']}")
            return result
        
        # Process based on marketplace
        if marketplace == 'aliexpress':
            return self._process_aliexpress(url, result)
        elif marketplace == 'ebay':
            return self._process_ebay(url, result)
        
        return result
    
    def _process_aliexpress(self, url, result):
        """Process AliExpress product"""
        # Extract product ID
        product_id = extract_product_id(url)
        if not product_id:
            result['error'] = 'Could not extract product ID from URL'
            print(f"❌ {result['error']}")
            return result
        
        result['product_id'] = product_id
        print(f"Product ID: {product_id}")
        
        # Get product details (title, description, price)
        print("\nFetching product details...")
        title = self.aliexpress_api.get_product_title(product_id)
        description = self.aliexpress_api.get_product_description(product_id)
        price_info = self.aliexpress_api.get_product_price(product_id)
        
        result['title'] = title
        result['description'] = description
        result['price'] = price_info.get('formatted', 'N/A')
        
        if title:
            print(f"Title: {title}")
        if price_info.get('formatted'):
            print(f"Price: {price_info['formatted']}")
        
        # Check availability
        print("\nChecking availability...")
        availability = self.aliexpress_api.check_availability(product_id)
        
        result['available'] = availability['available']
        result['stock_quantity'] = availability.get('stock_quantity')
        
        if availability['available']:
            print(f"✓ Product available")
            if availability.get('stock_quantity'):
                print(f"  Stock: {availability['stock_quantity']} units")
        else:
            print(f"✗ Not available: {availability['reason']}")
        
        # Get and download images
        print("\nFetching product images...")
        image_urls = self.aliexpress_api.get_product_images(product_id)
        
        if image_urls:
            print(f"Found {len(image_urls)} images")
            # Use custom folder_name if provided, otherwise use row_number, fallback to product_id
            folder = result.get('folder_name') or result.get('row_number') or product_id
            download_result = self.downloader.download_product_images(product_id, image_urls, custom_folder_name=folder)
            
            result['images_downloaded'] = download_result['downloaded']
            result['folder'] = download_result['folder']
        else:
            print("No images found")
        
        return result
    
    def _process_ebay(self, url, result):
        """Process eBay product"""
        # Extract item ID
        item_id = extract_ebay_item_id(url)
        if not item_id:
            result['error'] = 'Could not extract item ID from URL'
            print(f"❌ {result['error']}")
            return result
        
        result['product_id'] = item_id
        print(f"Item ID: {item_id}")
        
        # Get product details (title, description, price)
        print("\nFetching product details...")
        title = self.ebay_api.get_product_title(item_id)
        description = self.ebay_api.get_product_description(item_id)
        price_info = self.ebay_api.get_product_price(item_id)
        
        result['title'] = title
        result['description'] = description
        result['price'] = price_info.get('formatted', 'N/A')
        
        if title:
            print(f"Title: {title}")
        if price_info.get('formatted'):
            print(f"Price: {price_info['formatted']}")
        
        # Check availability
        print("\nChecking availability...")
        is_available, quantity, reason = self.ebay_api.check_availability(item_id)
        
        result['available'] = is_available
        result['stock_quantity'] = quantity
        
        if is_available:
            print(f"✓ Product available")
            if quantity:
                print(f"  Stock: {quantity} units")
        else:
            print(f"✗ Not available: {reason}")
        
        # Get and download images
        print("\nFetching product images...")
        image_urls = self.ebay_api.get_product_images(item_id)
        
        if image_urls:
            print(f"Found {len(image_urls)} images")
            # Use custom folder_name if provided, otherwise use row_number, fallback to item_id
            folder = result.get('folder_name') or result.get('row_number') or item_id
            download_result = self.downloader.download_product_images(item_id, image_urls, custom_folder_name=folder)
            
            result['images_downloaded'] = download_result['downloaded']
            result['folder'] = download_result['folder']
        else:
            print("No images found")
        
        return result
    
    def process_table(self, file_path, link_column=None):
        """
        Process all links from a table file
        
        Args:
            file_path: Path to Excel or CSV file
            link_column: Optional column name containing links
            
        Returns:
            List of processing results
        """
        print(f"\n{'='*60}")
        print(f"Processing table: {file_path}")
        print(f"{'='*60}\n")
        
        # Load table
        processor = TableProcessor(file_path)
        if not processor.load_table():
            print("Failed to load table")
            return []
        
        # Find or set link column
        if link_column:
            processor.set_link_column(link_column)
        else:
            processor.find_link_column()
        
        if processor.link_column is None:
            print("\nAvailable columns:")
            for col in processor.df.columns:
                print(f"  - {col}")
            
            # Ask user to specify column
            col_name = input("\nEnter the column name containing product links: ").strip()
            if not processor.set_link_column(col_name):
                print("Invalid column name. Exiting.")
                return []
        
        # Get all links
        links = processor.get_product_links()
        print(f"\nFound {len(links)} product links to process\n")
        
        if not links:
            print("No links found in table")
            return []
        
        # Get folder names from 'num' column if it exists
        folder_names = processor.get_folder_names('num')
        
        # Process each link
        self.results = []
        for idx, link in enumerate(links):
            # Get corresponding folder name for this row
            folder_name = folder_names[idx] if idx < len(folder_names) else None
            result = self.process_single_link(link, row_index=idx, folder_name=folder_name)
            self.results.append(result)
        
        # Add results to table and save
        processor.add_results_columns(self.results)
        processor.save_results()
        
        # Print summary
        self._print_summary()
        
        return self.results
    
    def process_links_list(self, links):
        """
        Process a list of product links
        
        Args:
            links: List of AliExpress product URLs
            
        Returns:
            List of processing results
        """
        print(f"\nProcessing {len(links)} product links\n")
        
        self.results = []
        for idx, link in enumerate(links):
            result = self.process_single_link(link, row_index=idx)
            self.results.append(result)
        
        self._print_summary()
        
        return self.results
    
    def _print_summary(self):
        """Print processing summary"""
        print(f"\n{'='*60}")
        print("PROCESSING SUMMARY")
        print(f"{'='*60}")
        
        total = len(self.results)
        available = sum(1 for r in self.results if r['available'])
        unavailable = sum(1 for r in self.results if not r['available'])
        errors = sum(1 for r in self.results if r['error'])
        total_images = sum(r['images_downloaded'] for r in self.results)
        
        # Count by marketplace
        aliexpress_count = sum(1 for r in self.results if r.get('marketplace') == 'aliexpress')
        ebay_count = sum(1 for r in self.results if r.get('marketplace') == 'ebay')
        
        print(f"Total products processed: {total}")
        print(f"  - AliExpress: {aliexpress_count}")
        print(f"  - eBay: {ebay_count}")
        print(f"Available: {available}")
        print(f"Unavailable: {unavailable}")
        print(f"Errors: {errors}")
        print(f"Total images downloaded: {total_images}")
        print(f"{'='*60}")
        print(f"{'='*60}\n")


def main():
    """Main entry point"""
    print("AliExpress & eBay Product Scraper")
    print("=" * 60)
    
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nPlease check your .env file and ensure all credentials are set.")
        return
    
    scraper = ProductScraper()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        
        # Check if it's a file
        if Path(input_path).is_file():
            scraper.process_table(input_path)
        # Or a single URL
        elif validate_aliexpress_url(input_path) or validate_ebay_url(input_path):
            scraper.process_single_link(input_path)
        else:
            print(f"Invalid input: {input_path}")
            print("Usage: python main.py <file.xlsx|file.csv|product_url>")
    else:
        # Interactive mode
        print("\nSelect mode:")
        print("1. Process table file (Excel/CSV)")
        print("2. Process single product URL")
        
        choice = input("\nEnter choice (1 or 2): ").strip()
        
        if choice == '1':
            file_path = input("Enter path to table file: ").strip()
            if Path(file_path).is_file():
                scraper.process_table(file_path)
            else:
                print(f"File not found: {file_path}")
        
        elif choice == '2':
            url = input("Enter product URL (AliExpress or eBay): ").strip()
            scraper.process_single_link(url)
        
        else:
            print("Invalid choice")


if __name__ == '__main__':
    main()
