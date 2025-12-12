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
