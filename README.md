# AliExpress Product Scraper

A Python tool to automate the process of checking AliExpress product availability and downloading product images. This tool uses the AliExpress Open Platform API to avoid CAPTCHA issues and handles bulk processing from Excel/CSV files.

## Features

- ✅ Extract product IDs from AliExpress URLs
- ✅ Check product availability and stock status via API
- ✅ Download product images organized by product ID
- ✅ Process bulk product links from Excel/CSV files
- ✅ Rate limiting to respect API quotas
- ✅ Automatic retry and error handling
- ✅ Export results back to Excel/CSV with availability status

## Prerequisites

1. **AliExpress API Credentials**
   - Register at [AliExpress Open Platform](https://portals.aliexpress.com/)
   - Create an application to get your API credentials
   - You'll need: `APP_KEY`, `APP_SECRET`, and optionally `SESSION_KEY`

2. **Python 3.7+**

## Installation

1. **Clone or download this project**

2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Set up configuration:**
   - Copy `.env.example` to `.env`:
     ```powershell
     Copy-Item .env.example .env
     ```
   - Edit `.env` and add your AliExpress API credentials:
     ```
     ALIEXPRESS_APP_KEY=your_app_key_here
     ALIEXPRESS_APP_SECRET=your_app_secret_here
     ALIEXPRESS_SESSION_KEY=your_session_key_here
     ```

## Usage

### Option 1: Process a Table File (Excel/CSV)

Your table should have a column containing AliExpress product URLs. The program will automatically detect the column or ask you to specify it.

**Run the program:**
```powershell
python main.py products.xlsx
```

Or in interactive mode:
```powershell
python main.py
# Select option 1 and enter the file path
```

**Example table structure:**
| Product Name | AliExpress Link | Price |
|--------------|----------------|-------|
| Widget A | https://www.aliexpress.com/item/1005001234567890.html | $10.99 |
| Widget B | https://www.aliexpress.com/item/1005009876543210.html | $15.50 |

**Output:**
- Original table with added columns: `product_id`, `availability`, `stock_quantity`, `images_downloaded`, `download_folder`
- Saved as `products_results.xlsx`
- Images downloaded to `downloads/<product_id>/` folders

### Option 2: Process a Single Product

```powershell
python main.py "https://www.aliexpress.com/item/1005001234567890.html"
```

Or in interactive mode:
```powershell
python main.py
# Select option 2 and enter the URL
```

### Option 3: Use as a Python Module

```python
from main import AliExpressScraper

scraper = AliExpressScraper()

# Process a single link
result = scraper.process_single_link(
    "https://www.aliexpress.com/item/1005001234567890.html"
)

# Process multiple links
links = [
    "https://www.aliexpress.com/item/1005001234567890.html",
    "https://www.aliexpress.com/item/1005009876543210.html"
]
results = scraper.process_links_list(links)

# Process a table file
results = scraper.process_table("products.xlsx")
```

## Project Structure

```
proj-final/
├── main.py                 # Main entry point
├── config.py               # Configuration management
├── aliexpress_api.py       # API client for AliExpress
├── url_parser.py           # URL parsing utilities
├── image_downloader.py     # Image download handler
├── table_processor.py      # Excel/CSV processing
├── logger.py               # Logging configuration
├── requirements.txt        # Python dependencies
├── .env.example           # Example environment variables
├── .gitignore             # Git ignore rules
├── README.md              # This file
├── downloads/             # Downloaded images (created automatically)
│   └── <product_id>/      # Organized by product ID
└── logs/                  # Application logs (created automatically)
```

## Configuration Options

Edit `config.py` or `.env` file to customize:

- `MAX_REQUESTS_PER_SECOND`: API rate limit (default: 2)
- `DOWNLOAD_FOLDER`: Base folder for downloads (default: 'downloads')
- `IMAGE_QUALITY`: JPEG quality 1-100 (default: 95)
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 30)

## API Information

This tool uses the AliExpress Dropshipping API methods:
- `aliexpress.ds.product.get` - Get product details, availability, and images

**API Limits:**
- Check your API plan for rate limits
- The tool implements automatic rate limiting
- Failed requests are logged for review

## Troubleshooting

### "Missing API credentials" error
- Make sure you've created a `.env` file (not `.env.example`)
- Verify your API credentials are correct
- Check that there are no extra spaces in the `.env` file

### "Could not extract product ID" error
- Verify the URL is a valid AliExpress product link
- Some shortened URLs may not work - use the full product URL

### Images not downloading
- Check if the product has images available
- Verify internet connectivity
- Check API quotas haven't been exceeded

### "Product not found" or "Product offline"
- The product may have been removed or is no longer available
- Check the URL in a browser to verify

## Notes

- Images are saved as JPEG files for consistency
- Duplicate images are automatically filtered
- Already downloaded images are skipped on re-run
- Processing logs are saved in the `logs/` folder
- Results table includes availability and stock information

## Support

For AliExpress API documentation and support:
- [AliExpress Open Platform](https://portals.aliexpress.com/)
- [API Documentation](https://developers.aliexpress.com/)

## License

This tool is for educational and personal use. Make sure to comply with AliExpress Terms of Service and API usage policies.
