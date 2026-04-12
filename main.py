"""
Main orchestrator for AliExpress and eBay product scraper
"""
import sys
from pathlib import Path
from datetime import datetime
import requests
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
    
    def __init__(self, description_prompt_file=None, title_prompt_file='title_prompt.txt'):
        execution_folder_name = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        execution_folder = Path(Config.DOWNLOAD_FOLDER) / execution_folder_name
        selected_description_prompt_file = description_prompt_file or Config.GEMINI_PROMPT_FILE
        selected_title_prompt_file = title_prompt_file

        self.aliexpress_api = AliExpressAPI()
        self.ebay_api = EbayAPI()
        self.downloader = ImageDownloader(base_folder=str(execution_folder))
        self.execution_folder = str(execution_folder)
        self.results = []
        self.gemini_processor = GeminiDescriptionProcessor(
            api_key=Config.GEMINI_API_KEY,
            model_name=Config.GEMINI_MODEL,
            prompt_file=selected_description_prompt_file,
        )
        self.gemini_title_processor = GeminiDescriptionProcessor(
            api_key=Config.GEMINI_API_KEY,
            model_name=Config.GEMINI_MODEL,
            prompt_file=selected_title_prompt_file,
        )

        print(f"Images for this run will be saved to: {self.execution_folder}")
        if self.gemini_processor.enabled:
            print(
                f"Gemini description rewrite is enabled "
                f"(model: {Config.GEMINI_MODEL}, prompt: {selected_description_prompt_file})"
            )
        else:
            print("Gemini description rewrite is disabled")
            if self.gemini_processor.error:
                print(f"Reason: {self.gemini_processor.error}")

        if self.gemini_title_processor.enabled:
            print(
                f"Gemini title rewrite is enabled "
                f"(model: {Config.GEMINI_MODEL}, prompt: {selected_title_prompt_file})"
            )
        else:
            print("Gemini title rewrite is disabled")
            if self.gemini_title_processor.error:
                print(f"Reason: {self.gemini_title_processor.error}")
    
    def process_single_link(
        self,
        url,
        row_index=None,
        folder_name=None,
        flat_image_output=False,
        images_only=False,
        skip_images=False,
        skip_text_fields=False,
        skip_rewrite=False,
    ):
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
            'shipping_price': None,
            'rewritten_title': None,
            'rewritten_description': None,
            'price': None,
            'available': None,
            'stock_quantity': None,
            'images_downloaded': 0,
            'folder': None,
            'status': None,
            'error': None
        }
        try:
            # Detect marketplace
            marketplace = detect_marketplace(url)
            result['marketplace'] = marketplace

            if marketplace == 'unknown':
                result['error'] = 'Invalid URL - not from AliExpress or eBay'
                print(f"âŒ {result['error']}")
                return self._finalize_result(result)

            unavailable_reason = self._get_unavailable_url_reason(url, marketplace)
            if unavailable_reason:
                result['error'] = unavailable_reason
                print(f"âŒ {result['error']}")
                return self._finalize_result(result)

            # Process based on marketplace
            if marketplace == 'aliexpress':
                if images_only:
                    result = self._process_aliexpress_images_only(url, result)
                else:
                    result = self._process_aliexpress(
                        url,
                        result,
                        skip_images=skip_images,
                        skip_text_fields=skip_text_fields,
                    )
            elif marketplace == 'ebay':
                if images_only:
                    result = self._process_ebay_images_only(url, result)
                else:
                    result = self._process_ebay(
                        url,
                        result,
                        skip_images=skip_images,
                        skip_text_fields=skip_text_fields,
                    )

            if not images_only and not skip_text_fields and not skip_rewrite:
                original_description = result.get('description')
                if original_description:
                    rewritten_description = self.gemini_processor.rewrite_description(original_description)
                    if rewritten_description != original_description:
                        rewritten_description = self._ensure_trailing_br(rewritten_description)
                    result['rewritten_description'] = rewritten_description

                original_title = result.get('title')
                if original_title:
                    result['rewritten_title'] = self.gemini_title_processor.rewrite_description(original_title)
        except Exception as exc:
            result['error'] = str(exc) or exc.__class__.__name__
            print(f"âŒ Error processing product: {result['error']}")
            print("Skipping to next product...")

        return self._finalize_result(result)

    def _finalize_result(self, result):
        """Ensure derived result fields are always populated before returning."""
        if not result.get('status'):
            result['status'] = self._build_status(result)
        return result

    @staticmethod
    def _get_unavailable_url_reason(url, marketplace):
        """Return a reason string when URL is unavailable, otherwise None."""
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            )
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=min(Config.REQUEST_TIMEOUT, 10),
                allow_redirects=True,
            )

            if response.status_code == 404:
                return 'Product URL returned 404'

            final_url = response.url or ''
            if marketplace == 'aliexpress' and not validate_aliexpress_url(final_url):
                return 'Product URL redirected to a non-product page'
            if marketplace == 'ebay' and not validate_ebay_url(final_url):
                return 'Product URL redirected to a non-product page'

            if marketplace == 'aliexpress':
                original_id = extract_product_id(url)
                final_id = extract_product_id(final_url)
                if original_id and final_id and original_id != final_id:
                    return 'Product URL redirected to a different product'
            if marketplace == 'ebay':
                original_id = extract_ebay_item_id(url)
                final_id = extract_ebay_item_id(final_url)
                if original_id and final_id and original_id != final_id:
                    return 'Product URL redirected to a different product'

            html_probe = (response.text or '')[:6000].lower()
            unavailable_markers = [
                'sorry, this page is not available',
                'page not found',
                'this item is no longer available',
                'product is unavailable',
                'oops! looks like this page is unavailable',
            ]
            if any(marker in html_probe for marker in unavailable_markers):
                return 'Product page appears unavailable'

            return None
        except requests.RequestException:
            # Do not block scraping due to transient network problems.
            return None
    
    def _process_aliexpress(self, url, result, skip_images=False, skip_text_fields=False):
        """Process AliExpress product"""
        # Extract product ID
        product_id = extract_product_id(url)
        if not product_id:
            result['error'] = 'Could not extract product ID from URL'
            print(f"âŒ {result['error']}")
            return result
        
        result['product_id'] = product_id
        print(f"Product ID: {product_id}")

        product_data = self.aliexpress_api.get_product_details(product_id)
        if not product_data:
            result['error'] = 'Failed to fetch product data from AliExpress API'
            print(f"❌ {result['error']}")
            return result
        
        # Get product details (title, description, price)
        print("\nFetching product details...")
        seller_name = self.aliexpress_api.get_seller_name(product_id, product_data=product_data)
        price_info = self.aliexpress_api.get_product_price(product_id, product_data=product_data)

        title = None
        description = None
        if not skip_text_fields:
            title = self.aliexpress_api.get_product_title(product_id, product_data=product_data)
            description = self.aliexpress_api.get_product_description(product_id, product_data=product_data)
        
        result['title'] = title
        result['seller_name'] = seller_name
        result['description'] = description
        result['price'] = price_info.get('formatted', 'N/A')
        result['shipping_price'] = self.aliexpress_api.get_shipping_price(product_id, product_data=product_data)
        
        if title:
            print(f"Title: {title}")
        if seller_name:
            print(f"Seller: {seller_name}")
        if price_info.get('formatted'):
            print(f"Price: {price_info['formatted']}")
        
        # Check availability
        print("\nChecking availability...")
        availability = self.aliexpress_api.check_availability(product_id, product_data=product_data)
        
        result['available'] = availability['available']
        result['stock_quantity'] = availability.get('stock_quantity')
        
        if availability['available']:
            print(f"âœ“ Product available")
            if availability.get('stock_quantity'):
                print(f"  Stock: {availability['stock_quantity']} units")
        else:
            print(f"âœ— Not available: {availability['reason']}")
        
        if skip_images:
            print("\nSkipping image download")
            result['images_downloaded'] = None
            result['status'] = 'ok'
            return result

        # Get and download images
        print("\nFetching product images...")
        image_urls = self.aliexpress_api.get_product_images(product_id, product_data=product_data)

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

    def _process_aliexpress_images_only(self, url, result):
        """Download AliExpress product images without fetching other product data."""
        product_id = extract_product_id(url)
        if not product_id:
            result['error'] = 'Could not extract product ID from URL'
            print(f"âŒ {result['error']}")
            return result

        result['product_id'] = product_id
        print(f"Product ID: {product_id}")

        product_data = self.aliexpress_api.get_product_details(product_id)
        if not product_data:
            result['error'] = 'Failed to fetch product data from AliExpress API'
            print(f"❌ {result['error']}")
            return result

        print("\nFetching product images only...")
        image_urls = self.aliexpress_api.get_product_images(product_id, product_data=product_data)

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
            result['status'] = 'Images downloaded'
        else:
            print("No images found")
            result['status'] = 'No images found'

        return result
    
    def _process_ebay(self, url, result, skip_images=False, skip_text_fields=False):
        """Process eBay product"""
        # Extract item ID
        item_id = extract_ebay_item_id(url)
        if not item_id:
            result['error'] = 'Could not extract item ID from URL'
            print(f"âŒ {result['error']}")
            return result
        
        result['product_id'] = item_id
        print(f"Item ID: {item_id}")
        
        # Get product details (title, description, price)
        print("\nFetching product details...")
        seller_name = self.ebay_api.get_seller_name(item_id)
        price_info = self.ebay_api.get_product_price(item_id)

        title = None
        description = None
        if not skip_text_fields:
            title = self.ebay_api.get_product_title(item_id)
            description = self.ebay_api.get_product_description(item_id)
        
        result['title'] = title
        result['seller_name'] = seller_name
        result['description'] = description
        result['price'] = price_info.get('formatted', 'N/A')
        result['shipping_price'] = self.ebay_api.get_shipping_price(item_id)
        
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
            print(f"âœ“ Product available")
            if quantity:
                print(f"  Stock: {quantity} units")
        else:
            print(f"âœ— Not available: {reason}")
        
        if skip_images:
            print("\nSkipping image download")
            result['images_downloaded'] = None
            result['status'] = 'ok'
            return result

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

    def _process_ebay_images_only(self, url, result):
        """Download eBay product images without fetching other product data."""
        item_id = extract_ebay_item_id(url)
        if not item_id:
            result['error'] = 'Could not extract item ID from URL'
            print(f"âŒ {result['error']}")
            return result

        result['product_id'] = item_id
        print(f"Item ID: {item_id}")

        print("\nFetching product images only...")
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
            result['status'] = 'Images downloaded'
        else:
            print("No images found")
            result['status'] = 'No images found'

        return result
    
    def process_table(self, file_path, link_column=None, images_only=False, skip_images=False, skip_text_fields=False, skip_rewrite=False):
        """
        Process all links from a table file
        
        Args:
            file_path: Path to Excel or CSV file
            link_column: Optional column name containing links
            
        Returns:
            List of processing results
        """
        print(f"\n{'='*60}")
        if images_only:
            mode_label = f"Downloading images from table: {file_path}"
        elif skip_images and skip_rewrite:
            mode_label = f"Scraping table without rewrite or image download: {file_path}"
        elif skip_images and skip_text_fields:
            mode_label = f"Scraping table without title, description, or image download: {file_path}"
        elif skip_images:
            mode_label = f"Scraping table without image download: {file_path}"
        else:
            mode_label = f"Processing table: {file_path}"
        print(mode_label)
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
            result = self.process_single_link(
                link,
                row_index=idx,
                flat_image_output=True,
                images_only=images_only,
                skip_images=skip_images,
                skip_text_fields=skip_text_fields,
                skip_rewrite=skip_rewrite,
            )
            self.results.append(result)
        
        # Add results to table and save
        processor.add_results_columns(self.results)
        processor.save_results()
        
        # Print summary
        self._print_summary()
        
        return self.results

    def process_google_sheet(self, sheet_url, link_column=None, images_only=False, skip_images=False, skip_text_fields=False, skip_rewrite=False):
        """
        Process product links from Google Sheet and upload results back to same sheet.

        Args:
            sheet_url: Google Sheet URL
            link_column: Optional column name containing links

        Returns:
            List of processing results
        """
        print(f"\n{'='*60}")
        if images_only:
            print("Downloading images from Google Sheet")
        elif skip_images and skip_rewrite:
            print("Scraping Google Sheet without rewrite or image download")
        elif skip_images and skip_text_fields:
            print("Scraping Google Sheet without title, description, or image download")
        elif skip_images:
            print("Scraping Google Sheet without image download")
        else:
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
            result = self.process_single_link(
                link,
                row_index=list_index,
                flat_image_output=True,
                images_only=images_only,
                skip_images=skip_images,
                skip_text_fields=skip_text_fields,
                skip_rewrite=skip_rewrite,
            )
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

            rewritten = self._ensure_trailing_br(rewritten)
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

    def process_google_sheet_titles(self, sheet_url, source_column='title', target_column='title'):
        """
        Rewrite existing title values in a Google Sheet without scraping products.

        Args:
            sheet_url: Google Sheet URL
            source_column: Column to read original titles from
            target_column: Column to write rewritten titles to

        Returns:
            Dict summary with processed and updated counts
        """
        print(f"\n{'='*60}")
        print("Rewriting Google Sheet titles only")
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

        if not self.gemini_title_processor.enabled:
            print("Gemini is not enabled. No title rewrite will be performed.")
            if self.gemini_title_processor.error:
                print(f"Reason: {self.gemini_title_processor.error}")
            return {'processed': 0, 'updated': 0}

        try:
            source_values = processor.get_column_values(source_column)
        except ValueError as e:
            print(str(e))
            return {'processed': 0, 'updated': 0}

        non_empty_titles = [(row_idx, text) for row_idx, text in source_values if text]
        if not non_empty_titles:
            print(f"No non-empty titles found in column '{source_column}'")
            return {'processed': 0, 'updated': 0}

        updates = []
        unchanged = 0
        for row_idx, title_text in non_empty_titles:
            rewritten = self.gemini_title_processor.rewrite_description(title_text)

            if rewritten == title_text:
                unchanged += 1
                continue

            updates.append((row_idx, rewritten))

        try:
            processor.update_column_values(target_column, updates)
        except Exception as e:
            print(f"Error updating titles in Google Sheet: {e}")
            return {'processed': len(non_empty_titles), 'updated': 0}

        print("\nTitle rewrite summary")
        print(f"Processed titles: {len(non_empty_titles)}")
        print(f"Updated rows: {len(updates)}")
        print(f"Unchanged rows skipped: {unchanged}")

        return {'processed': len(non_empty_titles), 'updated': len(updates)}

    def process_google_sheet_titles_and_descriptions(
        self,
        sheet_url,
        title_source_column='title',
        title_target_column='rewritten_title',
        description_source_column='description',
        description_target_column='rewritten_description',
    ):
        """Rewrite both title and description columns in a Google Sheet."""
        print(f"\n{'='*60}")
        print("Rewriting Google Sheet titles and descriptions")
        print(f"{sheet_url}")
        print(f"Title: {title_source_column} -> {title_target_column}")
        print(f"Description: {description_source_column} -> {description_target_column}")
        print(f"{'='*60}\n")

        title_summary = self.process_google_sheet_titles(
            sheet_url,
            source_column=title_source_column,
            target_column=title_target_column,
        )
        desc_summary = self.process_google_sheet_descriptions(
            sheet_url,
            source_column=description_source_column,
            target_column=description_target_column,
        )

        print("\nCombined rewrite summary")
        print(f"Title updated: {title_summary.get('updated', 0)}")
        print(f"Description updated: {desc_summary.get('updated', 0)}")

        return {'title': title_summary, 'description': desc_summary}

    @staticmethod
    def _normalize_url_for_match(url):
        """Normalize URL for lightweight matching against sheet values."""
        if not url:
            return ''
        return str(url).strip().rstrip('/')

    @staticmethod
    def _urls_refer_to_same_product(url_a, url_b):
        """Return True when two URLs are equivalent or point to the same product ID."""
        norm_a = ProductScraper._normalize_url_for_match(url_a)
        norm_b = ProductScraper._normalize_url_for_match(url_b)

        if not norm_a or not norm_b:
            return False

        if norm_a == norm_b:
            return True

        marketplace_a = detect_marketplace(norm_a)
        marketplace_b = detect_marketplace(norm_b)
        if marketplace_a != marketplace_b:
            return False

        if marketplace_a == 'aliexpress':
            return extract_product_id(norm_a) and extract_product_id(norm_a) == extract_product_id(norm_b)
        if marketplace_a == 'ebay':
            return extract_ebay_item_id(norm_a) and extract_ebay_item_id(norm_a) == extract_ebay_item_id(norm_b)

        return False

    def upload_single_result_to_google_sheet(self, source_url, result):
        """Best-effort upload of one processed URL result back to configured Google Sheet."""
        try:
            Config.validate_google_sheets()
        except ValueError:
            # Single URL mode can still run without Google Sheets credentials.
            return False

        processor = GoogleSheetProcessor(Config.GOOGLE_SHEET_URL, Config.GOOGLE_SERVICE_ACCOUNT_FILE)

        try:
            processor.connect()
            processor.load_sheet()
            processor.find_link_column()
        except Exception as exc:
            print(f"Skipping Google Sheet update for single URL: {exc}")
            return False

        if processor.link_column is None:
            print("Skipping Google Sheet update for single URL: link column not found")
            return False

        matched_row_idx = None
        for row_idx, sheet_url in processor.get_product_links():
            if self._urls_refer_to_same_product(source_url, sheet_url):
                matched_row_idx = row_idx
                break

        if matched_row_idx is None:
            print("Single URL was not found in Google Sheet; no sheet row was updated")
            return False

        result_for_sheet = dict(result)
        result_for_sheet['sheet_row_index'] = matched_row_idx

        try:
            processor.upload_results([result_for_sheet])
        except Exception as exc:
            print(f"Failed to upload single URL result to Google Sheet: {exc}")
            return False

        print(f"Updated Google Sheet row {matched_row_idx + 2} for the processed URL")
        return True

    @staticmethod
    def _ensure_trailing_br(text):
        """Ensure rewritten description ends with a single trailing <br>."""
        if not text:
            return text

        stripped = text.rstrip()
        if stripped.endswith('<br>'):
            return stripped
        return f"{stripped}<br>"

    @staticmethod
    def _build_status(result):
        """Build a user-facing status value for result sheet outputs."""
        if result.get('error'):
            return 'fail'
        return 'ok'
    
    def process_links_list(self, links, images_only=False, skip_images=False, skip_text_fields=False, skip_rewrite=False):
        """
        Process a list of product links
        
        Args:
            links: List of AliExpress product URLs
            
        Returns:
            List of processing results
        """
        if images_only:
            print(f"\nDownloading images for {len(links)} product links\n")
        elif skip_images and skip_rewrite:
            print(f"\nScraping {len(links)} product links without rewrite or image download\n")
        elif skip_images and skip_text_fields:
            print(f"\nScraping {len(links)} product links without title, description, or image download\n")
        elif skip_images:
            print(f"\nScraping {len(links)} product links without image download\n")
        else:
            print(f"\nProcessing {len(links)} product links\n")
        
        self.results = []
        for idx, link in enumerate(links):
            result = self.process_single_link(
                link,
                row_index=idx,
                images_only=images_only,
                skip_images=skip_images,
                skip_text_fields=skip_text_fields,
                skip_rewrite=skip_rewrite,
            )
            self.results.append(result)
        
        self._print_summary()
        
        return self.results
    
    def _print_summary(self):
        """Print processing summary"""
        print(f"\n{'='*60}")
        print("PROCESSING SUMMARY")
        print(f"{'='*60}")
        
        total = len(self.results)
        available = sum(1 for r in self.results if r.get('available') is True)
        unavailable = sum(1 for r in self.results if r.get('available') is False)
        unknown = sum(1 for r in self.results if r.get('available') is None)
        errors = sum(1 for r in self.results if r.get('error'))
        total_images = sum(
            value if isinstance(value, (int, float)) else 0
            for value in (r.get('images_downloaded') for r in self.results)
        )
        
        # Count by marketplace
        aliexpress_count = sum(1 for r in self.results if r.get('marketplace') == 'aliexpress')
        ebay_count = sum(1 for r in self.results if r.get('marketplace') == 'ebay')
        
        print(f"Total products processed: {total}")
        print(f"  - AliExpress: {aliexpress_count}")
        print(f"  - eBay: {ebay_count}")
        print(f"Available: {available}")
        print(f"Unavailable: {unavailable}")
        print(f"Availability not checked: {unknown}")
        print(f"Errors: {errors}")
        print(f"Total images downloaded: {total_images}")
        print(f"{'='*60}")
        print(f"{'='*60}\n")


def main():
    """Main entry point"""
    print("AliExpress & eBay Product Scraper")
    print("=" * 60)
    default_description_prompt_file = 'description_prompt.txt'
    default_title_prompt_file = 'title_prompt.txt'

    # Check command line arguments
    if len(sys.argv) > 1:
        input_path = sys.argv[1]

        if input_path.lower() in ('sheet-desc', 'desc', 'desc-only'):
            try:
                Config.validate_google_sheets()
            except ValueError as e:
                print(f"\nâŒ Google Sheets Configuration Error: {e}")
                return

            source_column = sys.argv[2] if len(sys.argv) > 2 else 'description'
            target_column = sys.argv[3] if len(sys.argv) > 3 else source_column
            scraper = ProductScraper(
                description_prompt_file=default_description_prompt_file,
                title_prompt_file=default_title_prompt_file,
            )
            scraper.process_google_sheet_descriptions(
                Config.GOOGLE_SHEET_URL,
                source_column=source_column,
                target_column=target_column,
            )
            return

        if input_path.lower() in ('sheet-title', 'title', 'title-only'):
            try:
                Config.validate_google_sheets()
            except ValueError as e:
                print(f"\nâŒ Google Sheets Configuration Error: {e}")
                return

            source_column = sys.argv[2] if len(sys.argv) > 2 else 'title'
            target_column = sys.argv[3] if len(sys.argv) > 3 else 'rewritten_title'
            scraper = ProductScraper(
                description_prompt_file=default_description_prompt_file,
                title_prompt_file=default_title_prompt_file,
            )
            scraper.process_google_sheet_titles(
                Config.GOOGLE_SHEET_URL,
                source_column=source_column,
                target_column=target_column,
            )
            return

        if input_path.lower() in ('sheet-title-desc', 'sheet-both', 'both'):
            try:
                Config.validate_google_sheets()
            except ValueError as e:
                print(f"\nâŒ Google Sheets Configuration Error: {e}")
                return

            title_source = sys.argv[2] if len(sys.argv) > 2 else 'title'
            title_target = sys.argv[3] if len(sys.argv) > 3 else 'rewritten_title'
            desc_source = sys.argv[4] if len(sys.argv) > 4 else 'description'
            desc_target = sys.argv[5] if len(sys.argv) > 5 else 'rewritten_description'
            scraper = ProductScraper(
                description_prompt_file=default_description_prompt_file,
                title_prompt_file=default_title_prompt_file,
            )
            scraper.process_google_sheet_titles_and_descriptions(
                Config.GOOGLE_SHEET_URL,
                title_source_column=title_source,
                title_target_column=title_target,
                description_source_column=desc_source,
                description_target_column=desc_target,
            )
            return

        if input_path.lower() in ('images-only', 'images', 'img-only', 'img'):
            image_input = sys.argv[2] if len(sys.argv) > 2 else 'sheet'

            try:
                Config.validate()
            except ValueError as e:
                print(f"\nâŒ Configuration Error: {e}")
                print("\nPlease check your .env file and ensure all credentials are set.")
                return

            scraper = ProductScraper(
                description_prompt_file=default_description_prompt_file,
                title_prompt_file=default_title_prompt_file,
            )

            if Path(image_input).is_file():
                scraper.process_table(image_input, images_only=True)
            elif image_input.lower() == 'sheet':
                try:
                    Config.validate_google_sheets()
                except ValueError as e:
                    print(f"\nâŒ Google Sheets Configuration Error: {e}")
                    return
                scraper.process_google_sheet(Config.GOOGLE_SHEET_URL, images_only=True)
            elif validate_aliexpress_url(image_input) or validate_ebay_url(image_input):
                result = scraper.process_single_link(image_input, images_only=True)
                scraper.upload_single_result_to_google_sheet(image_input, result)
            else:
                print(f"Invalid input for images-only mode: {image_input}")
                print("Images-only usage: python main.py images-only [sheet|file.xlsx|file.csv|product_url]")
            return

        if input_path.lower() in ('scrape-only', 'no-images', 'scrape-no-images'):
            scrape_input = sys.argv[2] if len(sys.argv) > 2 else 'sheet'

            try:
                Config.validate()
            except ValueError as e:
                print(f"\nâŒ Configuration Error: {e}")
                print("\nPlease check your .env file and ensure all credentials are set.")
                return

            scraper = ProductScraper(
                description_prompt_file=default_description_prompt_file,
                title_prompt_file=default_title_prompt_file,
            )

            if Path(scrape_input).is_file():
                scraper.process_table(scrape_input, skip_images=True)
            elif scrape_input.lower() == 'sheet':
                try:
                    Config.validate_google_sheets()
                except ValueError as e:
                    print(f"\nâŒ Google Sheets Configuration Error: {e}")
                    return
                scraper.process_google_sheet(Config.GOOGLE_SHEET_URL, skip_images=True)
            elif validate_aliexpress_url(scrape_input) or validate_ebay_url(scrape_input):
                result = scraper.process_single_link(scrape_input, skip_images=True)
                scraper.upload_single_result_to_google_sheet(scrape_input, result)
            else:
                print(f"Invalid input for scrape-only mode: {scrape_input}")
                print("Scrape-only usage: python main.py scrape-only [sheet|file.xlsx|file.csv|product_url]")
            return

        if input_path.lower() in ('meta-only', 'fields-only', 'scrape-no-text'):
            meta_input = sys.argv[2] if len(sys.argv) > 2 else 'sheet'

            try:
                Config.validate()
            except ValueError as e:
                print(f"\nâŒ Configuration Error: {e}")
                print("\nPlease check your .env file and ensure all credentials are set.")
                return

            scraper = ProductScraper(
                description_prompt_file=default_description_prompt_file,
                title_prompt_file=default_title_prompt_file,
            )

            if Path(meta_input).is_file():
                scraper.process_table(meta_input, skip_images=True, skip_rewrite=True)
            elif meta_input.lower() == 'sheet':
                try:
                    Config.validate_google_sheets()
                except ValueError as e:
                    print(f"\nâŒ Google Sheets Configuration Error: {e}")
                    return
                scraper.process_google_sheet(
                    Config.GOOGLE_SHEET_URL,
                    skip_images=True,
                    skip_rewrite=True,
                )
            elif validate_aliexpress_url(meta_input) or validate_ebay_url(meta_input):
                result = scraper.process_single_link(meta_input, skip_images=True, skip_rewrite=True)
                scraper.upload_single_result_to_google_sheet(meta_input, result)
            else:
                print(f"Invalid input for meta-only mode: {meta_input}")
                print("Meta-only usage: python main.py meta-only [sheet|file.xlsx|file.csv|product_url]")
            return

        # Validate marketplace scraping configuration for all other modes
        try:
            Config.validate()
        except ValueError as e:
            print(f"\nâŒ Configuration Error: {e}")
            print("\nPlease check your .env file and ensure all credentials are set.")
            return

        scraper = ProductScraper(
            description_prompt_file=default_description_prompt_file,
            title_prompt_file=default_title_prompt_file,
        )
        
        # Check if it's a file
        if Path(input_path).is_file():
            scraper.process_table(input_path)
        elif input_path.lower() == 'sheet':
            try:
                Config.validate_google_sheets()
            except ValueError as e:
                print(f"\nâŒ Google Sheets Configuration Error: {e}")
                return
            scraper.process_google_sheet(Config.GOOGLE_SHEET_URL)
        # Or a single URL
        elif validate_aliexpress_url(input_path) or validate_ebay_url(input_path):
            result = scraper.process_single_link(input_path)
            scraper.upload_single_result_to_google_sheet(input_path, result)
        else:
            print(f"Invalid input: {input_path}")
            print("Usage: python main.py <file.xlsx|file.csv|product_url|sheet|sheet-desc|sheet-title|sheet-title-desc|images-only|scrape-only|meta-only>")
            print("Description-only usage: python main.py sheet-desc [source_column] [target_column]")
            print("Title-only usage: python main.py sheet-title [source_column] [target_column]")
            print("Title+description usage: python main.py sheet-title-desc [title_source] [title_target] [description_source] [description_target]")
            print("Images-only usage: python main.py images-only [sheet|file.xlsx|file.csv|product_url]")
            print("Scrape-only usage: python main.py scrape-only [sheet|file.xlsx|file.csv|product_url]")
            print("Meta-only usage: python main.py meta-only [sheet|file.xlsx|file.csv|product_url]")
    else:
        # Default mode: process configured Google Sheet
        try:
            Config.validate_google_sheets()
        except ValueError as e:
            print(f"\nâŒ Google Sheets Configuration Error: {e}")
            print("\nSet GOOGLE_SERVICE_ACCOUNT_FILE in .env and place the JSON key file in the project.")
            return

        try:
            Config.validate()
        except ValueError as e:
            print(f"\nâŒ Configuration Error: {e}")
            print("\nPlease check your .env file and ensure all credentials are set.")
            return

        scraper = ProductScraper(
            description_prompt_file=default_description_prompt_file,
            title_prompt_file=default_title_prompt_file,
        )
        scraper.process_google_sheet(Config.GOOGLE_SHEET_URL)


if __name__ == '__main__':
    main()

