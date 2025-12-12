"""
Main orchestrator for AliExpress product scraper
"""
import sys
from pathlib import Path
from datetime import datetime
from config import Config
from url_parser import extract_product_id, validate_aliexpress_url
from aliexpress_api import AliExpressAPI
from image_downloader import ImageDownloader
from table_processor import TableProcessor


class AliExpressScraper:
    """Main orchestrator for scraping AliExpress products"""
    
    def __init__(self):
        self.api = AliExpressAPI()
        self.downloader = ImageDownloader()
        self.results = []
    
    def process_single_link(self, url, row_index=None):
        """
        Process a single product link
        
        Args:
            url: AliExpress product URL
            row_index: Optional row index from table
            
        Returns:
            Dictionary with processing results
        """
        print(f"\n{'='*60}")
        print(f"Processing: {url}")
        print(f"{'='*60}")
        
        result = {
            'url': url,
            'row_index': row_index,
            'product_id': None,
            'available': False,
            'stock_quantity': None,
            'images_downloaded': 0,
            'folder': None,
            'error': None
        }
        
        # Validate URL
        if not validate_aliexpress_url(url):
            result['error'] = 'Invalid AliExpress URL'
            print(f"❌ {result['error']}")
            return result
        
        # Extract product ID
        product_id = extract_product_id(url)
        if not product_id:
            result['error'] = 'Could not extract product ID from URL'
            print(f"❌ {result['error']}")
            return result
        
        result['product_id'] = product_id
        print(f"Product ID: {product_id}")
        
        # Check availability
        print("\nChecking availability...")
        availability = self.api.check_availability(product_id)
        
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
        image_urls = self.api.get_product_images(product_id)
        
        if image_urls:
            print(f"Found {len(image_urls)} images")
            download_result = self.downloader.download_product_images(product_id, image_urls)
            
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
        
        # Process each link
        self.results = []
        for idx, link in enumerate(links):
            result = self.process_single_link(link, row_index=idx)
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
        
        print(f"Total products processed: {total}")
        print(f"Available: {available}")
        print(f"Unavailable: {unavailable}")
        print(f"Errors: {errors}")
        print(f"Total images downloaded: {total_images}")
        print(f"{'='*60}\n")


def main():
    """Main entry point"""
    print("AliExpress Product Scraper")
    print("=" * 60)
    
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nPlease follow these steps:")
        print("1. Copy .env.example to .env")
        print("2. Get your API credentials from https://portals.aliexpress.com/")
        print("3. Fill in your API credentials in the .env file")
        return
    
    scraper = AliExpressScraper()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        
        # Check if it's a file
        if Path(input_path).is_file():
            scraper.process_table(input_path)
        # Or a single URL
        elif validate_aliexpress_url(input_path):
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
            url = input("Enter AliExpress product URL: ").strip()
            scraper.process_single_link(url)
        
        else:
            print("Invalid choice")


if __name__ == '__main__':
    main()
