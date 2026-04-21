"""
Google Sheets processor for loading product links and writing scraping results.
"""
from urllib.parse import urlparse, parse_qs

import gspread


class GoogleSheetProcessor:
    """Process Google Sheets containing product links and update result columns."""

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
        """Normalize availability to a user-friendly string for existing sheet columns."""
        if value is True:
            return 'Available'
        if value is False:
            return 'Unavailable'
        return None

    @staticmethod
    def _truncate_for_sheet(value, max_chars=49000):
        """
        Truncate cell values to fit within Google Sheets' 50,000 character limit.
        Uses 49,000 as a safer limit to account for any formatting.
        
        Args:
            value: The value to potentially truncate
            max_chars: Maximum characters allowed (default 49,000)
            
        Returns:
            Truncated string value, or empty string if value is None
        """
        if value is None:
            return ''
        
        str_value = str(value)
        if len(str_value) > max_chars:
            truncated = str_value[:max_chars-3] + '...'
            return truncated
        return str_value

    def __init__(self, sheet_url, service_account_file):
        self.sheet_url = sheet_url
        self.service_account_file = service_account_file
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        self.headers = []
        self.rows = []
        self.link_column = None

    @staticmethod
    def _column_letter(col_index_1_based):
        """Convert 1-based column index to A1 letter (1->A, 27->AA)."""
        result = ''
        num = col_index_1_based
        while num > 0:
            num, rem = divmod(num - 1, 26)
            result = chr(65 + rem) + result
        return result

    @staticmethod
    def _extract_gid(sheet_url):
        parsed = urlparse(sheet_url)
        query_params = parse_qs(parsed.query)
        if 'gid' in query_params and query_params['gid']:
            return query_params['gid'][0]

        if parsed.fragment and 'gid=' in parsed.fragment:
            parts = parse_qs(parsed.fragment)
            if 'gid' in parts and parts['gid']:
                return parts['gid'][0]

        return None

    def connect(self):
        """Connect to Google Sheets and select worksheet by gid from URL."""
        self.client = gspread.service_account(filename=self.service_account_file)
        self.spreadsheet = self.client.open_by_url(self.sheet_url)

        gid = self._extract_gid(self.sheet_url)
        if gid is not None:
            target_gid = int(gid)
            for ws in self.spreadsheet.worksheets():
                if ws.id == target_gid:
                    self.worksheet = ws
                    break

        if self.worksheet is None:
            self.worksheet = self.spreadsheet.get_worksheet(0)

        return True

    def load_sheet(self):
        """Load header and rows from worksheet."""
        all_values = self.worksheet.get_all_values()
        if not all_values:
            self.headers = []
            self.rows = []
            return True

        self.headers = all_values[0]
        self.rows = all_values[1:]
        print(f"Loaded Google Sheet '{self.worksheet.title}' with {len(self.rows)} rows")
        print(f"Columns: {', '.join(self.headers)}")
        return True

    def find_link_column(self, keywords=None):
        """Find link column by header name or sample row values."""
        if keywords is None:
            keywords = ['link', 'url', 'aliexpress', 'ebay']

        for col_name in self.headers:
            col_lower = str(col_name).lower()
            if 'link' in col_lower or 'url' in col_lower:
                self.link_column = col_name
                print(f"Found link column: {col_name}")
                return col_name

        for col_name in self.headers:
            col_lower = str(col_name).lower()
            if any(k in col_lower for k in keywords):
                self.link_column = col_name
                print(f"Found link column: {col_name}")
                return col_name

        # Fallback: inspect sample data
        for idx, col_name in enumerate(self.headers):
            sample_values = [row[idx] for row in self.rows[:5] if idx < len(row)]
            for value in sample_values:
                value_lower = str(value).lower()
                if 'aliexpress.com' in value_lower or 'ebay.com' in value_lower:
                    self.link_column = col_name
                    print(f"Found link column by content: {col_name}")
                    return col_name

        print("Could not automatically find link column")
        return None

    def set_link_column(self, column_name):
        """Set link column manually by header name."""
        if column_name in self.headers:
            self.link_column = column_name
            print(f"Link column set to: {column_name}")
            return True

        print(f"Column '{column_name}' not found in sheet")
        return False

    def get_product_links(self):
        """Return links and corresponding row indices in sheet rows (0-based data rows)."""
        if not self.link_column:
            return []

        link_idx = self.headers.index(self.link_column)
        links = []
        for row_idx, row in enumerate(self.rows):
            if link_idx < len(row):
                url = str(row[link_idx]).strip()
                if url:
                    links.append((row_idx, url))

        return links

    def ensure_result_columns(self):
        """Ensure result columns exist in the header row."""
        updated = False
        for col_name in self.RESULT_COLUMNS:
            if col_name not in self.headers:
                self.headers.append(col_name)
                updated = True

        if updated:
            total_cols = len(self.headers)
            end_letter = self._column_letter(total_cols)
            self.worksheet.update(f"A1:{end_letter}1", [self.headers])
            print("Added missing result columns to sheet")

    def ensure_column(self, column_name):
        """Ensure a single column exists in the header row."""
        if column_name in self.headers:
            return True

        self.headers.append(column_name)
        total_cols = len(self.headers)
        end_letter = self._column_letter(total_cols)
        self.worksheet.update(f"A1:{end_letter}1", [self.headers])
        print(f"Added missing column: {column_name}")
        return True

    def get_column_values(self, column_name):
        """Return (row_index, value) pairs for a given column from loaded rows."""
        if column_name not in self.headers:
            raise ValueError(f"Column '{column_name}' not found in sheet")

        col_idx = self.headers.index(column_name)
        values = []
        for row_idx, row in enumerate(self.rows):
            value = row[col_idx] if col_idx < len(row) else ''
            values.append((row_idx, str(value).strip()))
        return values

    def update_column_values(self, column_name, row_value_updates):
        """Update one column for multiple rows using batch update."""
        if not row_value_updates:
            print(f"No updates to write for column: {column_name}")
            return True

        self.ensure_column(column_name)
        col_idx = self.headers.index(column_name) + 1
        col_letter = self._column_letter(col_idx)

        batch_requests = []
        for row_idx, value in row_value_updates:
            target_row = row_idx + 2
            cell_range = f"{col_letter}{target_row}"
            batch_requests.append({'range': cell_range, 'values': [[value]]})

        self.worksheet.batch_update(batch_requests)
        print(f"Updated {len(row_value_updates)} rows in column '{column_name}'")
        return True

    def upload_results(self, results):
        """Upload result values to result columns only, preserving all other columns (e.g. photos)."""
        if not results:
            return True

        self.ensure_result_columns()

        for result in results:
            sheet_row_idx = result.get('sheet_row_index')
            if sheet_row_idx is None:
                continue

            # +2 because sheet row 1 is header and data starts at row 2.
            target_row = sheet_row_idx + 2
            updates = {
                'Link': result.get('url', ''),
                'Status': result.get('status', ''),
                'title': self._truncate_for_sheet(result.get('title', '')),
                'description': self._truncate_for_sheet(result.get('description', '')),
                'price': result.get('price', ''),
                'shipping_price': result.get('shipping_price', ''),
                'seller_nick': result.get('seller_name', ''),
                'rewritten_title': self._truncate_for_sheet(result.get('rewritten_title', '')),
                'rewritten_description': self._truncate_for_sheet(result.get('rewritten_description', '')),
            }

            explicit_lotnum = result.get('lotnum')
            if explicit_lotnum not in (None, ''):
                updates['LotNum'] = explicit_lotnum

            availability_value = self._availability_display(result.get('available'))
            if availability_value is not None:
                if 'availability' in self.headers:
                    updates['availability'] = availability_value
                if 'Avalibility' in self.headers:
                    updates['Avalibility'] = availability_value

            if result.get('images_downloaded') is not None:
                updates['ImagesDownloaded'] = result.get('images_downloaded', '')
            if result.get('folder') is not None:
                updates['DownloadFolder'] = result.get('folder', '')

            batch_requests = []
            for col_name, value in updates.items():
                col_idx = self.headers.index(col_name) + 1
                col_letter = self._column_letter(col_idx)
                cell_range = f"{col_letter}{target_row}"
                batch_requests.append({'range': cell_range, 'values': [[value]]})

            if batch_requests:
                self.worksheet.batch_update(batch_requests)

        print(f"Uploaded results for {len(results)} rows to Google Sheet")
        return True

