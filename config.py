"""
Configuration settings for AliExpress scraper
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for API credentials and settings"""
    
    # RapidAPI credentials
    RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
    RAPIDAPI_HOST = os.getenv('RAPIDAPI_HOST', 'aliexpress-datahub.p.rapidapi.com')
    
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
                "Missing API credentials. Please set RAPIDAPI_KEY in your .env file.\n"
                "Get your key from https://rapidapi.com/"
            )
        return True
