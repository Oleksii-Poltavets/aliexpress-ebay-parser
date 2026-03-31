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
from google_sheet_processor import GoogleSheetProcessor
from gemini_processor import GeminiDescriptionProcessor


class ProductScraper:
    """Main orchestrator for scraping AliExpress and eBay products"""
    
    def __init__(self):
        execution_folder_name = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        execution_folder = Path(Config.DOWNLOAD_FOLDER) / execution_folder_name

        self.aliexpress_api = AliExpressAPI()
        self.ebay_api = EbayAPI()
        self.downloader = ImageDownloader(base_folder=str(execution_folder))
        self.execution_folder = str(execution_folder)
        self.results = []
        self.gemini_processor = GeminiDescriptionProcessor(
            api_key=Config.GEMINI_API_KEY,
            model_name=Config.GEMINI_MODEL,
            prompt_file=Config.GEMINI_PROMPT_FILE,
        )

        print(f"Images for this run will be saved to: {self.execution_folder}")
        if self.gemini_processor.enabled:
            print(
                f"Gemini description rewrite is enabled "
                f"(model: {Config.GEMINI_MODEL}, prompt: {Config.GEMINI_PROMPT_FILE})"
            )
        else:
            print("Gemini description rewrite is disabled")
            if self.gemini_processor.error:
                print(f"Reason: {self.gemini_processor.error}")
    
    def process_single_link(self, url, row_index=None, folder_name=None, flat_image_output=False):
        """
        Process a single product link (AliExpress or eBay)
        
        Args:
            url: Product URL
            row_index: Optional row index from table (for folder naming)
            folder_name: Optional custom folder name (overrides row_number)
            flat_image_output: Save images directly to the base download folder
            
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
            'flat_image_output': flat_image_output,
            'marketplace': None,
            'product_id': None,
            'seller_name': None,
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
        seller_name = self.aliexpress_api.get_seller_name(product_id)
        description = self.aliexpress_api.get_product_description(product_id)
        price_info = self.aliexpress_api.get_product_price(product_id)
        
        result['title'] = title
        result['seller_name'] = seller_name
        result['description'] = description
        result['price'] = price_info.get('formatted', 'N/A')
        
        if title:
            print(f"Title: {title}")
        if seller_name:
            print(f"Seller: {seller_name}")
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
            filename_prefix = result.get('row_number') or product_id
            folder = result.get('folder_name') or result.get('row_number') or product_id
            download_result = self.downloader.download_product_images(
                product_id,
                image_urls,
                custom_folder_name=folder,
                filename_prefix=filename_prefix,
                flat_output=result.get('flat_image_output', False)
            )
            
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
        seller_name = self.ebay_api.get_seller_name(item_id)
        description = self.ebay_api.get_product_description(item_id)
        price_info = self.ebay_api.get_product_price(item_id)
        
        result['title'] = title
        result['seller_name'] = seller_name
        result['description'] = description
        result['price'] = price_info.get('formatted', 'N/A')
        
        if title:
            print(f"Title: {title}")
        if seller_name:
            print(f"Seller: {seller_name}")
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
            filename_prefix = result.get('row_number') or item_id
            folder = result.get('folder_name') or result.get('row_number') or item_id
            download_result = self.downloader.download_product_images(
                item_id,
                image_urls,
                custom_folder_name=folder,
                filename_prefix=filename_prefix,
                flat_output=result.get('flat_image_output', False)
            )
            
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
            result = self.process_single_link(link, row_index=idx, flat_image_output=True)
            self.results.append(result)
        
        # Add results to table and save
        processor.add_results_columns(self.results)
        processor.save_results()
        
        # Print summary
        self._print_summary()
        
        return self.results

    def process_google_sheet(self, sheet_url, link_column=None):
        """
        Process product links from Google Sheet and upload results back to same sheet.

        Args:
            sheet_url: Google Sheet URL
            link_column: Optional column name containing links

        Returns:
            List of processing results
        """
        print(f"\n{'='*60}")
        print("Processing Google Sheet")
        print(f"{sheet_url}")
        print(f"{'='*60}\n")

        processor = GoogleSheetProcessor(sheet_url, Config.GOOGLE_SERVICE_ACCOUNT_FILE)

        try:
            processor.connect()
            processor.load_sheet()
        except Exception as e:
            print(f"Failed to connect/load Google Sheet: {e}")
            return []

        if link_column:
            processor.set_link_column(link_column)
        else:
            processor.find_link_column()

        if processor.link_column is None:
            print("\nAvailable columns:")
            for col in processor.headers:
                print(f"  - {col}")

            col_name = input("\nEnter the column name containing product links: ").strip()
            if not processor.set_link_column(col_name):
                print("Invalid column name. Exiting.")
                return []

        links_with_rows = processor.get_product_links()
        print(f"\nFound {len(links_with_rows)} product links to process\n")

        if not links_with_rows:
            print("No links found in sheet")
            return []

        self.results = []
        for list_index, (sheet_row_idx, link) in enumerate(links_with_rows):
            result = self.process_single_link(link, row_index=list_index, flat_image_output=True)
            if result.get('description'):
                result['description'] = self.gemini_processor.rewrite_description(result['description'])
            result['sheet_row_index'] = sheet_row_idx
            self.results.append(result)

        try:
            processor.upload_results(self.results)
        except Exception as e:
            print(f"Error uploading results to Google Sheet: {e}")

        self._print_summary()

        return self.results

    def process_google_sheet_descriptions(self, sheet_url, source_column='description', target_column='description'):
        """
        Rewrite existing description values in a Google Sheet without scraping products.

        Args:
            sheet_url: Google Sheet URL
            source_column: Column to read original descriptions from
            target_column: Column to write rewritten descriptions to

        Returns:
            Dict summary with processed and updated counts
        """
        print(f"\n{'='*60}")
        print("Rewriting Google Sheet descriptions only")
        print(f"{sheet_url}")
        print(f"Source column: {source_column}")
        print(f"Target column: {target_column}")
        print(f"{'='*60}\n")

        processor = GoogleSheetProcessor(sheet_url, Config.GOOGLE_SERVICE_ACCOUNT_FILE)

        try:
            processor.connect()
            processor.load_sheet()
        except Exception as e:
            print(f"Failed to connect/load Google Sheet: {e}")
            return {'processed': 0, 'updated': 0}

        if not self.gemini_processor.enabled:
            print("Gemini is not enabled. No description rewrite will be performed.")
            if self.gemini_processor.error:
                print(f"Reason: {self.gemini_processor.error}")
            return {'processed': 0, 'updated': 0}

        try:
            source_values = processor.get_column_values(source_column)
        except ValueError as e:
            print(str(e))
            return {'processed': 0, 'updated': 0}

        non_empty_descriptions = [(row_idx, text) for row_idx, text in source_values if text]
        if not non_empty_descriptions:
            print(f"No non-empty descriptions found in column '{source_column}'")
            return {'processed': 0, 'updated': 0}

        updates = []
        unchanged = 0
        for row_idx, description_text in non_empty_descriptions:
            rewritten = self.gemini_processor.rewrite_description(description_text)

            # Skip unchanged text to avoid writing fallback/original values repeatedly.
            if rewritten == description_text:
                unchanged += 1
                continue

            updates.append((row_idx, rewritten))

        try:
            processor.update_column_values(target_column, updates)
        except Exception as e:
            print(f"Error updating descriptions in Google Sheet: {e}")
            return {'processed': len(non_empty_descriptions), 'updated': 0}

        print("\nDescription rewrite summary")
        print(f"Processed descriptions: {len(non_empty_descriptions)}")
        print(f"Updated rows: {len(updates)}")
        print(f"Unchanged rows skipped: {unchanged}")

        return {'processed': len(non_empty_descriptions), 'updated': len(updates)}
    
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

    # Check command line arguments
    if len(sys.argv) > 1:
        input_path = sys.argv[1]

        if input_path.lower() in ('sheet-desc', 'desc', 'desc-only'):
            try:
                Config.validate_google_sheets()
            except ValueError as e:
                print(f"\n❌ Google Sheets Configuration Error: {e}")
                return

            source_column = sys.argv[2] if len(sys.argv) > 2 else 'description'
            target_column = sys.argv[3] if len(sys.argv) > 3 else source_column

            scraper = ProductScraper()
            scraper.process_google_sheet_descriptions(
                Config.GOOGLE_SHEET_URL,
                source_column=source_column,
                target_column=target_column,
            )
            return

        # Validate marketplace scraping configuration for all other modes
        try:
            Config.validate()
        except ValueError as e:
            print(f"\n❌ Configuration Error: {e}")
            print("\nPlease check your .env file and ensure all credentials are set.")
            return

        scraper = ProductScraper()
        
        # Check if it's a file
        if Path(input_path).is_file():
            scraper.process_table(input_path)
        elif input_path.lower() == 'sheet':
            try:
                Config.validate_google_sheets()
            except ValueError as e:
                print(f"\n❌ Google Sheets Configuration Error: {e}")
                return
            scraper.process_google_sheet(Config.GOOGLE_SHEET_URL)
        # Or a single URL
        elif validate_aliexpress_url(input_path) or validate_ebay_url(input_path):
            scraper.process_single_link(input_path)
        else:
            print(f"Invalid input: {input_path}")
            print("Usage: python main.py <file.xlsx|file.csv|product_url|sheet|sheet-desc>")
            print("Description-only usage: python main.py sheet-desc [source_column] [target_column]")
    else:
        # Default mode: process configured Google Sheet
        try:
            Config.validate_google_sheets()
        except ValueError as e:
            print(f"\n❌ Google Sheets Configuration Error: {e}")
            print("\nSet GOOGLE_SERVICE_ACCOUNT_FILE in .env and place the JSON key file in the project.")
            return

        try:
            Config.validate()
        except ValueError as e:
            print(f"\n❌ Configuration Error: {e}")
            print("\nPlease check your .env file and ensure all credentials are set.")
            return

        scraper = ProductScraper()
        scraper.process_google_sheet(Config.GOOGLE_SHEET_URL)


if __name__ == '__main__':
    main()
