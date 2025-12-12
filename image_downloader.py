"""
Image downloader for AliExpress products
"""
import os
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO
from config import Config


class ImageDownloader:
    """Download and save product images organized by product ID"""
    
    def __init__(self, base_folder=None):
        self.base_folder = base_folder or Config.DOWNLOAD_FOLDER
        self._ensure_base_folder()
    
    def _ensure_base_folder(self):
        """Create base download folder if it doesn't exist"""
        Path(self.base_folder).mkdir(parents=True, exist_ok=True)
    
    def _sanitize_filename(self, filename):
        """Remove invalid characters from filename"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename
    
    def create_product_folder(self, product_id):
        """
        Create a folder for the product
        
        Args:
            product_id: Product ID to use as folder name
            
        Returns:
            Path to the created folder
        """
        folder_path = Path(self.base_folder) / str(product_id)
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path
    
    def download_image(self, url, save_path, timeout=30):
        """
        Download a single image from URL
        
        Args:
            url: Image URL
            save_path: Path where to save the image
            timeout: Request timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Load image to validate it's a valid image file
            img = Image.open(BytesIO(response.content))
            
            # Convert to RGB if necessary (handles RGBA, etc.)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Save the image
            img.save(save_path, 'JPEG', quality=Config.IMAGE_QUALITY, optimize=True)
            
            print(f"Downloaded: {save_path.name}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {url}: {e}")
            return False
        except Exception as e:
            print(f"Error processing image {url}: {e}")
            return False
    
    def download_product_images(self, product_id, image_urls):
        """
        Download all images for a product
        
        Args:
            product_id: Product ID
            image_urls: List of image URLs
            
        Returns:
            Dictionary with download statistics
        """
        if not image_urls:
            print(f"No images to download for product {product_id}")
            return {
                'product_id': product_id,
                'total': 0,
                'downloaded': 0,
                'failed': 0,
                'folder': None
            }
        
        # Create product folder
        product_folder = self.create_product_folder(product_id)
        
        downloaded = 0
        failed = 0
        
        for idx, url in enumerate(image_urls, start=1):
            # Generate filename
            filename = f"{product_id}_image_{idx}.jpg"
            save_path = product_folder / filename
            
            # Skip if already exists
            if save_path.exists():
                print(f"Skipping existing file: {filename}")
                downloaded += 1
                continue
            
            # Download the image
            if self.download_image(url, save_path):
                downloaded += 1
            else:
                failed += 1
        
        print(f"\nProduct {product_id}: Downloaded {downloaded}/{len(image_urls)} images")
        
        return {
            'product_id': product_id,
            'total': len(image_urls),
            'downloaded': downloaded,
            'failed': failed,
            'folder': str(product_folder)
        }
    
    def get_existing_images(self, product_id):
        """
        Get list of already downloaded images for a product
        
        Args:
            product_id: Product ID
            
        Returns:
            List of image file paths
        """
        product_folder = Path(self.base_folder) / str(product_id)
        
        if not product_folder.exists():
            return []
        
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        images = []
        
        for ext in image_extensions:
            images.extend(product_folder.glob(f'*{ext}'))
        
        return sorted(images)
