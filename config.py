"""
Configuration settings for AliExpress scraper
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for API credentials and settings"""
    
    # RapidAPI credentials (for AliExpress)
    RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
    RAPIDAPI_HOST = os.getenv('RAPIDAPI_HOST', 'aliexpress-datahub.p.rapidapi.com')
    
    # eBay API credentials
    EBAY_APP_ID = os.getenv('EBAY_APP_ID')
    EBAY_CERT_ID = os.getenv('EBAY_CERT_ID')
    EBAY_DEV_ID = os.getenv('EBAY_DEV_ID')
    EBAY_ENVIRONMENT = os.getenv('EBAY_ENVIRONMENT', 'PRODUCTION')  # PRODUCTION or SANDBOX
    
    # API endpoints
    API_BASE_URL = f'https://{RAPIDAPI_HOST}'
    
    # Rate limiting
    MAX_REQUESTS_PER_SECOND = int(os.getenv('MAX_REQUESTS_PER_SECOND', 1))
    
    # Download settings
    DOWNLOAD_FOLDER = 'downloads'
    IMAGE_QUALITY = 95

    # Google Sheets settings
    GOOGLE_SHEET_URL = os.getenv(
        'GOOGLE_SHEET_URL',
        'https://docs.google.com/spreadsheets/d/1CcEmBFjluUtm18JuIzBJTzrHAWoocA7gMsbr_fEjrp8/edit?gid=1636327865#gid=1636327865'
    )
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'service_account.json')

    # Gemini settings (optional, used for description rewriting)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
    GEMINI_PROMPT_FILE = os.getenv('GEMINI_PROMPT_FILE', 'title_prompt.txt')
    
    # Timeout settings
    REQUEST_TIMEOUT = 30
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present"""
        if not cls.RAPIDAPI_KEY:
            raise ValueError(
                "Missing AliExpress API credentials. Please set RAPIDAPI_KEY in your .env file.\n"
                "Get your key from https://rapidapi.com/"
            )
        
        if not cls.EBAY_APP_ID or not cls.EBAY_CERT_ID:
            raise ValueError(
                "Missing eBay API credentials. Please set EBAY_APP_ID and EBAY_CERT_ID in your .env file.\n"
                "Get your credentials from https://developer.ebay.com/"
            )
        
        return True

    @classmethod
    def validate_google_sheets(cls):
        """Validate that Google Sheets credentials configuration is present"""
        if not cls.GOOGLE_SHEET_URL:
            raise ValueError("Missing GOOGLE_SHEET_URL in .env file")

        if not os.path.exists(cls.GOOGLE_SERVICE_ACCOUNT_FILE):
            raise ValueError(
                "Google service account file not found. "
                "Set GOOGLE_SERVICE_ACCOUNT_FILE in .env and provide the JSON key file."
            )

        return True
