"""
Table processor for handling Excel/CSV files with AliExpress product links
"""
import pandas as pd
from pathlib import Path


class TableProcessor:
    """Process Excel/CSV files containing AliExpress product links"""

    RESULT_COLUMNS = [
        'LotNum',
        'Link',
        'Status',
        'ImagesDownloaded',
        'DownloadFolder',
        'title',
        'description',
        'price',
        'shipping_price',
        'seller_nick',
        'rewritten_title',
        'rewritten_description',
    ]

    @staticmethod
    def _availability_display(value):
        """Normalize availability to a user-friendly string for sheet/table columns."""
        if value is True:
            return 'Available'
        if value is False:
            return 'Unavailable'
        return None
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = None
        self.link_column = None
    
    def load_table(self, sheet_name=0):
        """
        Load table from file
        
        Args:
            sheet_name: For Excel files, which sheet to load (default: first sheet)
            
        Returns:
            True if successful, False otherwise
        """
        file_ext = Path(self.file_path).suffix.lower()
        
        try:
            if file_ext in ['.xlsx', '.xls']:
                self.df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            elif file_ext == '.csv':
                # Read CSV with proper quote handling for complex URLs
                self.df = pd.read_csv(
                    self.file_path,
                    quotechar='"',
                    escapechar='\\',
                    encoding='utf-8'
                )
            else:
                print(f"Unsupported file format: {file_ext}")
                return False
            
            print(f"Loaded table with {len(self.df)} rows and {len(self.df.columns)} columns")
            print(f"Columns: {', '.join(self.df.columns)}")
            return True
            
        except Exception as e:
            print(f"Error loading table: {e}")
            return False
    
    def find_link_column(self, keywords=None):
        """
        Automatically find the column containing AliExpress links
        
        Args:
            keywords: List of keywords to search for in column names
            
        Returns:
            Column name if found, None otherwise
        """
        if self.df is None:
            return None
        
        if keywords is None:
            keywords = ['link', 'url', 'aliexpress']
        
        # First, try to find by column name - prioritize more specific matches
        for col in self.df.columns:
            col_lower = str(col).lower()
            # Check for exact or prioritized matches first
            if 'link' in col_lower or 'url' in col_lower:
                self.link_column = col
                print(f"Found link column: {col}")
                return col
        
        # Fallback to any keyword match
        for col in self.df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in keywords):
                self.link_column = col
                print(f"Found link column: {col}")
                return col
        
        # If not found, check content of first few rows
        for col in self.df.columns:
            sample = self.df[col].dropna().head(5)
            if any('aliexpress.com' in str(val).lower() for val in sample):
                self.link_column = col
                print(f"Found link column by content: {col}")
                return col
        
        print("Could not automatically find link column")
        return None
    
    def set_link_column(self, column_name):
        """
        Manually set the column containing links
        
        Args:
            column_name: Name of the column
        """
        if column_name in self.df.columns:
            self.link_column = column_name
            print(f"Link column set to: {column_name}")
            return True
        else:
            print(f"Column '{column_name}' not found in table")
            return False
    
    def get_product_links(self):
        """
        Get all product links from the table
        
        Returns:
            List of product links (non-empty strings)
        """
        if self.df is None or self.link_column is None:
            return []
        
        # Get non-null links
        links = self.df[self.link_column].dropna()
        
        # Convert to string and filter out empty strings
        links = [str(link).strip() for link in links if str(link).strip()]
        
        return links
    
    def get_folder_names(self, column_name='num'):
        """
        Get folder names from a specific column
        
        Args:
            column_name: Column name containing folder identifiers
            
        Returns:
            List of folder names corresponding to product links
        """
        if self.df is None:
            return []
        
        if column_name not in self.df.columns:
            print(f"Warning: Column '{column_name}' not found. Available columns: {', '.join(self.df.columns)}")
            return [None] * len(self.df)
        
        # Get folder names, convert to string
        folder_names = [str(val) if pd.notna(val) else None for val in self.df[column_name]]
        
        return folder_names
    
    def add_results_columns(self, results):
        """
        Add processing results back to the dataframe
        
        Args:
            results: List of dictionaries with processing results
                     Each dict should have 'row_index' to match with dataframe
        """
        if self.df is None:
            return
        
        for column_name in self.RESULT_COLUMNS:
            if column_name not in self.df.columns:
                self.df[column_name] = None
        
        # Update rows with results
        for result in results:
            idx = result.get('row_index')
            if idx is not None and idx < len(self.df):
                self.df.at[idx, 'LotNum'] = result.get('row_number')
                self.df.at[idx, 'Link'] = result.get('url')
                self.df.at[idx, 'Status'] = result.get('status')
                if result.get('images_downloaded') is not None:
                    self.df.at[idx, 'ImagesDownloaded'] = result.get('images_downloaded')
                if result.get('folder') is not None:
                    self.df.at[idx, 'DownloadFolder'] = result.get('folder')
                self.df.at[idx, 'title'] = result.get('title')
                self.df.at[idx, 'description'] = result.get('description')
                self.df.at[idx, 'price'] = result.get('price')
                self.df.at[idx, 'shipping_price'] = result.get('shipping_price')
                self.df.at[idx, 'seller_nick'] = result.get('seller_name')
                self.df.at[idx, 'rewritten_title'] = result.get('rewritten_title')
                self.df.at[idx, 'rewritten_description'] = result.get('rewritten_description')

                availability_value = self._availability_display(result.get('available'))
                if 'availability' in self.df.columns and availability_value is not None:
                    self.df.at[idx, 'availability'] = availability_value
                if 'Avalibility' in self.df.columns and availability_value is not None:
                    self.df.at[idx, 'Avalibility'] = availability_value
    
    def save_results(self, output_path=None):
        """
        Save the updated table with results
        
        Args:
            output_path: Path to save the file (default: add _results suffix)
        """
        if self.df is None:
            return False
        
        if output_path is None:
            # Generate output path
            input_path = Path(self.file_path)
            output_path = input_path.parent / f"{input_path.stem}_results{input_path.suffix}"
        
        try:
            file_ext = Path(output_path).suffix.lower()
            
            if file_ext in ['.xlsx', '.xls']:
                self.df.to_excel(output_path, index=False)
            elif file_ext == '.csv':
                self.df.to_csv(output_path, index=False)
            
            print(f"Results saved to: {output_path}")
            return True
            
        except Exception as e:
            print(f"Error saving results: {e}")
            return False

