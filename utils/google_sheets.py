"""
Google Sheets integration for reading/writing apartment data

Handles multi-tab operations for:
- Main data sheet
- Scatter plot data
- Criteria matrix
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound, SpreadsheetNotFound

import config
from utils.rate_limiter import get_rate_limiter


class GoogleSheetsClient:
    """Client for interacting with Google Sheets"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # Sheet names
    MAIN_SHEET_NAME = "Apartment Data"
    SCATTER_PLOT_SHEET_NAME = "Price vs Score"
    CRITERIA_MATRIX_SHEET_NAME = "Criteria Matrix"
    APPROVED_GYMS_SHEET_NAME = "Approved Gyms"
    USER_EDITS_LOG_SHEET_NAME = "User Edits Log"
    
    def __init__(self, credentials_path: str = None, sheet_id: str = None):
        """
        Initialize Google Sheets client
        
        Args:
            credentials_path: Path to service account JSON credentials
            sheet_id: Google Sheet ID
        """
        self.credentials_path = credentials_path or config.GOOGLE_SHEETS_CREDENTIALS_PATH
        self.sheet_id = sheet_id or config.GOOGLE_SHEET_ID
        
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                f"Google Sheets credentials not found at {self.credentials_path}. "
                "Please follow setup instructions in README."
            )
        
        if not self.sheet_id:
            raise ValueError(
                "GOOGLE_SHEET_ID not set. Please set it in .env file."
            )
        
        # Authenticate
        creds = Credentials.from_service_account_file(
            self.credentials_path,
            scopes=self.SCOPES
        )
        self.client = gspread.authorize(creds)
        
        # Open spreadsheet with retry logic
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.spreadsheet = self.client.open_by_key(self.sheet_id)
                break  # Success!
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  Google Sheets connection attempt {attempt + 1} failed, retrying in {retry_delay}s...")
                    import time
                    time.sleep(retry_delay)
                else:
                    # Final attempt failed
                    raise ConnectionError(
                        f"Failed to connect to Google Sheets API after {max_retries} attempts. "
                        "Please check your internet connection and try again. "
                        f"Error: {str(e)}"
                    ) from e
    
    def _get_or_create_worksheet(self, name: str, rows: int = 1000, cols: int = 50) -> gspread.Worksheet:
        """Get worksheet by name or create if doesn't exist"""
        try:
            return self.spreadsheet.worksheet(name)
        except WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)
    
    def initialize_sheets(self) -> None:
        """Initialize all required sheets with headers"""
        # Main data sheet
        main_sheet = self._get_or_create_worksheet(self.MAIN_SHEET_NAME)
        self._initialize_main_sheet(main_sheet)
        
        # Scatter plot sheet
        scatter_sheet = self._get_or_create_worksheet(self.SCATTER_PLOT_SHEET_NAME)
        self._initialize_scatter_plot_sheet(scatter_sheet)
        
        # Criteria matrix sheet
        criteria_sheet = self._get_or_create_worksheet(self.CRITERIA_MATRIX_SHEET_NAME)
        self._initialize_criteria_matrix_sheet(criteria_sheet)
    
    def _initialize_main_sheet(self, sheet: gspread.Worksheet) -> None:
        """Initialize main data sheet with headers"""
        # Check if already initialized
        if sheet.row_count > 0 and sheet.col_count > 0:
            first_row = sheet.row_values(1)
            if first_row and first_row[0] == config.SHEET_COLUMNS["zillow_url"]:
                return  # Already initialized
        
        # Create headers
        # Note: zillow_url is stored but not displayed as a column (it's in the address hyperlink)
        headers = [
            config.SHEET_COLUMNS["manual_safety"],
            config.SHEET_COLUMNS["address"],
            config.SHEET_COLUMNS["price"],
            config.SHEET_COLUMNS["bedrooms"],
            config.SHEET_COLUMNS["bathrooms"],
            config.SHEET_COLUMNS["sqft"],
            config.SHEET_COLUMNS["commute_time_you"],
            config.SHEET_COLUMNS["commute_route"],
            config.SHEET_COLUMNS["commute_time_partner"],
            config.SHEET_COLUMNS["route_annoyingness"],
            config.SHEET_COLUMNS["commute_details"],
            config.SHEET_COLUMNS["safety_score_opendata"],
            config.SHEET_COLUMNS["combined_safety"],
            config.SHEET_COLUMNS["wfh_quality_score"],
            config.SHEET_COLUMNS["natural_light"],
            config.SHEET_COLUMNS["desk_space_quality"],
            config.SHEET_COLUMNS["quietness_score"],
            config.SHEET_COLUMNS["double_pane_windows"],
            config.SHEET_COLUMNS["study_door_type"],
            config.SHEET_COLUMNS["kitchen_quality"],
            config.SHEET_COLUMNS["location_vibe_score"],
            config.SHEET_COLUMNS["restaurants_nearby"],
            config.SHEET_COLUMNS["cafes_nearby"],
            config.SHEET_COLUMNS["parks_nearby"],
            config.SHEET_COLUMNS["parking_type"],
            config.SHEET_COLUMNS["parking_enclosure"],
            config.SHEET_COLUMNS["parking_distance"],
            config.SHEET_COLUMNS["parking_cost"],
            config.SHEET_COLUMNS["street_parking_ease"],
            config.SHEET_COLUMNS["visitor_parking_ease"],
            config.SHEET_COLUMNS["parking_score"],
            config.SHEET_COLUMNS["laundry_type"],
            config.SHEET_COLUMNS["floor_level"],
            config.SHEET_COLUMNS["view_quality"],
            config.SHEET_COLUMNS["gym_within_10min"],
            config.SHEET_COLUMNS["gym_quality"],
            config.SHEET_COLUMNS["rent_control"],
            config.SHEET_COLUMNS["year_built"],
            config.SHEET_COLUMNS["neighborhood"],
            config.SHEET_COLUMNS["neighborhoods"],
            config.SHEET_COLUMNS["tour_questions"],
            config.SHEET_COLUMNS["weighted_score"],
            config.SHEET_COLUMNS["value_ratio"],
            config.SHEET_COLUMNS["last_updated"],
            config.SHEET_COLUMNS["last_analyzed"],
        ]
        
        sheet.update('A1:AQ1', [headers])
        
        # Apply formatting
        sheet.format('A1:AQ1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8}
        })
        
        # Freeze header row
        sheet.freeze(rows=1)
    
    def _col_index_to_letter(self, col_idx: int) -> str:
        """Converts a 0-indexed column number to an Excel-style column letter."""
        letter = ''
        while col_idx >= 0:
            letter = chr(col_idx % 26 + ord('A')) + letter
            col_idx = col_idx // 26 - 1
        return letter
    
    def _initialize_scatter_plot_sheet(self, sheet: gspread.Worksheet) -> None:
        """Initialize scatter plot data sheet"""
        if sheet.row_count > 0 and sheet.col_count > 0:
            first_row = sheet.row_values(1)
            if first_row and first_row[0] == "Address":
                return  # Already initialized
        
        headers = ["Address", "Price", "Weighted Score"]
        sheet.update('A1:C1', [headers])
        sheet.format('A1:C1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8}
        })
        sheet.freeze(rows=1)
    
    def _initialize_criteria_matrix_sheet(self, sheet: gspread.Worksheet) -> None:
        """Initialize criteria matrix sheet"""
        if sheet.row_count > 0 and sheet.col_count > 0:
            first_row = sheet.row_values(1)
            if first_row and first_row[0] == "Address":
                return  # Already initialized
        
        headers = ["Address"]
        # Add criteria names
        for criterion_name, criterion_data in config.IDEAL_CRITERIA.items():
            # Convert snake_case to Title Case
            display_name = criterion_name.replace("_", " ").title()
            headers.append(display_name)
        headers.append("Total Criteria Met")
        
        sheet.update(f'A1:{chr(65 + len(headers) - 1)}1', [headers])
        sheet.format(f'A1:{chr(65 + len(headers) - 1)}1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8}
        })
        sheet.freeze(rows=1)
    
    def read_main_sheet(self) -> List[Dict[str, Any]]:
        """
        Read all data from main sheet
        
        Returns:
            List of apartment records as dictionaries
        """
        # Rate limit: Google Sheets read
        rate_limiter = get_rate_limiter()
        rate_limiter.wait_if_needed('google_sheets_read')
        
        sheet = self._get_or_create_worksheet(self.MAIN_SHEET_NAME)
        records = sheet.get_all_records()
        return records

    @staticmethod
    def needs_commute_metadata_refresh(record: Dict[str, Any]) -> bool:
        """
        Check whether a record is missing enriched metadata (commute or crime details).
        Returns True if any of these are missing:
        - Route annoyingness or commute details
        - Commute details without AM/PM structure
        - Crime details
        """
        def _is_blank(value: Any, treat_empty_structs: bool = False) -> bool:
            if value is None:
                return True
            if isinstance(value, (int, float)):
                return False
            if isinstance(value, str):
                trimmed = value.strip()
                if trimmed == "":
                    return True
                if treat_empty_structs and trimmed in {"{}", "[]"}:
                    return True
            return False

        # Check commute metadata
        route_annoy_col = config.SHEET_COLUMNS.get("route_annoyingness")
        commute_details_col = config.SHEET_COLUMNS.get("commute_details")
        route_annoy_value = record.get(route_annoy_col) if route_annoy_col else None
        commute_details_value = record.get(commute_details_col) if commute_details_col else None

        missing_annoy = _is_blank(route_annoy_value)
        missing_details = _is_blank(commute_details_value, treat_empty_structs=True)
        
        # Check if commute_details has the new AM/PM structure
        if not missing_details and commute_details_value:
            try:
                import json
                details = json.loads(commute_details_value) if isinstance(commute_details_value, str) else commute_details_value
                driver = details.get('driver', {})
                # If it's missing AM/PM fields, we need to refresh
                if 'duration_am_mins' not in driver or 'duration_pm_mins' not in driver:
                    return True
            except:
                pass
        
        # Check crime details
        crime_details_col = config.SHEET_COLUMNS.get("crime_details")
        crime_details_value = record.get(crime_details_col) if crime_details_col else None
        missing_crime = _is_blank(crime_details_value, treat_empty_structs=True)
        
        return missing_annoy or missing_details or missing_crime
    
    def get_apartments_needing_analysis(self) -> List[Dict[str, Any]]:
        """
        Get apartments that need analysis (have URL but no weighted score)
        
        Returns:
            List of apartment records that need analysis
        """
        records = self.read_main_sheet()
        needing_analysis = []
        
        for i, record in enumerate(records):
            zillow_url = record.get(config.SHEET_COLUMNS["zillow_url"], "").strip()
            weighted_score = record.get(config.SHEET_COLUMNS["weighted_score"], "")
            address = record.get(config.SHEET_COLUMNS["address"], "Unknown address")
            
            needs_analysis = False
            reason = None
            
            if zillow_url and not weighted_score:
                needs_analysis = True
                reason = "no score"
            elif zillow_url and self.needs_commute_metadata_refresh(record):
                needs_analysis = True
                # Determine specific reason
                route_annoy_col = config.SHEET_COLUMNS.get("route_annoyingness")
                commute_details_col = config.SHEET_COLUMNS.get("commute_details")
                crime_details_col = config.SHEET_COLUMNS.get("crime_details")
                
                missing_parts = []
                if not record.get(route_annoy_col):
                    missing_parts.append("route annoyingness")
                if not record.get(commute_details_col):
                    missing_parts.append("commute details")
                if not record.get(crime_details_col):
                    missing_parts.append("crime details")
                
                if missing_parts:
                    reason = f"missing {', '.join(missing_parts)}"
                else:
                    reason = "missing commute metadata"
            
            if needs_analysis:
                record['_row_number'] = i + 2  # +2 for 1-indexed and header row
                record['_analysis_reason'] = reason
                needing_analysis.append(record)
        
        return needing_analysis
    
    def write_apartment_data(self, row_number: int, data: Dict[str, Any]) -> None:
        """
        Write apartment analysis data to a specific row
        
        Args:
            row_number: Row number (1-indexed, where 1 is header)
            data: Dictionary with analysis results
        """
        # Rate limit: Google Sheets write
        rate_limiter = get_rate_limiter()
        rate_limiter.wait_if_needed('google_sheets_write')
        
        sheet = self._get_or_create_worksheet(self.MAIN_SHEET_NAME)
        
        # Build row data in correct column order
        row_data = []
        column_mapping = {
            "price": config.SHEET_COLUMNS["price"],
            "bedrooms": config.SHEET_COLUMNS["bedrooms"],
            "bathrooms": config.SHEET_COLUMNS["bathrooms"],
            "sqft": config.SHEET_COLUMNS["sqft"],
            "commute_duration": config.SHEET_COLUMNS["commute_time_you"],  # Map commute_duration -> commute_time_you
            "commute_route": config.SHEET_COLUMNS["commute_route"],
            "commute_duration_partner": config.SHEET_COLUMNS["commute_time_partner"],  # Map commute_duration_partner -> commute_time_partner
            "route_annoyingness": config.SHEET_COLUMNS["route_annoyingness"],
            "commute_details_json": config.SHEET_COLUMNS["commute_details"],
            "safety_score_opendata": config.SHEET_COLUMNS["safety_score_opendata"],
            "combined_safety": config.SHEET_COLUMNS["combined_safety"],
            "crime_details_json": config.SHEET_COLUMNS["crime_details"],
            "wfh_quality_score": config.SHEET_COLUMNS["wfh_quality_score"],
            "natural_light": config.SHEET_COLUMNS["natural_light"],
            "desk_space_quality": config.SHEET_COLUMNS["desk_space_quality"],
            "quietness_score": config.SHEET_COLUMNS["quietness_score"],
            "double_pane_windows": config.SHEET_COLUMNS["double_pane_windows"],
            "study_door_type": config.SHEET_COLUMNS["study_door_type"],
            "kitchen_quality": config.SHEET_COLUMNS["kitchen_quality"],
            "location_vibe_score": config.SHEET_COLUMNS["location_vibe_score"],
            "restaurants_nearby": config.SHEET_COLUMNS["restaurants_nearby"],
            "cafes_nearby": config.SHEET_COLUMNS["cafes_nearby"],
            "parks_nearby": config.SHEET_COLUMNS["parks_nearby"],
            "parking_type": config.SHEET_COLUMNS["parking_type"],
            "parking_enclosure": config.SHEET_COLUMNS["parking_enclosure"],
            "parking_distance": config.SHEET_COLUMNS["parking_distance"],
            "parking_cost": config.SHEET_COLUMNS["parking_cost"],
            "street_parking_ease": config.SHEET_COLUMNS["street_parking_ease"],
            "visitor_parking_ease": config.SHEET_COLUMNS["visitor_parking_ease"],
            "parking_score": config.SHEET_COLUMNS["parking_score"],
            "laundry_type": config.SHEET_COLUMNS["laundry_type"],
            "floor_level": config.SHEET_COLUMNS["floor_level"],
            "view_quality": config.SHEET_COLUMNS["view_quality"],
            "gym_within_10min": config.SHEET_COLUMNS["gym_within_10min"],
            "gym_quality": config.SHEET_COLUMNS["gym_quality"],
            "rent_control": config.SHEET_COLUMNS["rent_control"],
            "year_built": config.SHEET_COLUMNS["year_built"],
            "neighborhood": config.SHEET_COLUMNS["neighborhood"],
            "neighborhoods": config.SHEET_COLUMNS["neighborhoods"],
            "tour_questions": config.SHEET_COLUMNS["tour_questions"],
            "weighted_score": config.SHEET_COLUMNS["weighted_score"],
            "value_ratio": config.SHEET_COLUMNS["value_ratio"],
            "last_updated": config.SHEET_COLUMNS["last_updated"],
            "last_analyzed": config.SHEET_COLUMNS["last_analyzed"],
        }
        
        # Get header row to determine column positions
        headers = sheet.row_values(1)
        
        # Helper function to convert column index to letter (0=A, 25=Z, 26=AA, etc.)
        def col_index_to_letter(col_index):
            result = ""
            while col_index >= 0:
                result = chr(65 + (col_index % 26)) + result
                col_index = col_index // 26 - 1
            return result
        
        # Create update dict mapping column letter to value
        updates = {}
        for data_key, column_name in column_mapping.items():
            if data_key in data:
                try:
                    col_index = headers.index(column_name)
                    col_letter = col_index_to_letter(col_index)
                    value = data[data_key]
                    
                    if value is None:
                        value = ""
                    # Serialize JSON fields
                    if data_key in ['commute_details_json', 'crime_details_json'] and isinstance(value, dict):
                        import json
                        value = json.dumps(value)
                    
                    updates[f"{col_letter}{row_number}"] = value
                    if data_key == 'crime_details_json':
                        preview = value[:200] if isinstance(value, str) else str(value)
                        print(f"  -> Writing crime details to {column_name} (row {row_number}): {preview}...")
                except ValueError:
                    print(f"Warning: Column {column_name} not found in sheet")
        
        # Batch update
        if updates:
            update_list = [{'range': cell, 'values': [[value]]} for cell, value in updates.items()]
            sheet.batch_update(update_list)
    
    def clear_wfh_fields(self, row_number: int) -> None:
        """
        Clear WFH-related columns (so blanks show until photo analyzer/manual entry fills them).
        """
        sheet = self._get_or_create_worksheet(self.MAIN_SHEET_NAME)
        headers = sheet.row_values(1)
        
        wfh_columns = [
            config.SHEET_COLUMNS.get("natural_light"),
            config.SHEET_COLUMNS.get("desk_space_quality"),
            config.SHEET_COLUMNS.get("kitchen_quality"),
            config.SHEET_COLUMNS.get("view_quality"),
            config.SHEET_COLUMNS.get("floor_level"),
            config.SHEET_COLUMNS.get("double_pane_windows"),
            config.SHEET_COLUMNS.get("study_door_type"),
            config.SHEET_COLUMNS.get("street_noise_level"),
            config.SHEET_COLUMNS.get("quietness_score"),
            config.SHEET_COLUMNS.get("wfh_quality_score"),
        ]
        
        def col_index_to_letter(col_index):
            result = ""
            while col_index >= 0:
                result = chr(65 + (col_index % 26)) + result
                col_index = col_index // 26 - 1
            return result
        
        updates = []
        for column_name in wfh_columns:
            if not column_name:
                continue
            try:
                col_index = headers.index(column_name)
            except ValueError:
                print(f"Warning: Column {column_name} not found when clearing WFH fields")
                continue
            col_letter = col_index_to_letter(col_index)
            updates.append({'range': f'{col_letter}{row_number}', 'values': [[""]]})
        
        if updates:
            sheet.batch_update(updates)
    
    def update_scatter_plot_data(self) -> None:
        """Update scatter plot sheet with latest data from main sheet"""
        main_data = self.read_main_sheet()
        scatter_sheet = self._get_or_create_worksheet(self.SCATTER_PLOT_SHEET_NAME)
        
        # Build scatter plot data
        plot_data = []
        for record in main_data:
            address = record.get(config.SHEET_COLUMNS["address"], "")
            price = record.get(config.SHEET_COLUMNS["price"], "")
            score = record.get(config.SHEET_COLUMNS["weighted_score"], "")
            
            if address and price and score:
                plot_data.append([address, price, score])
        
        if plot_data:
            # Clear existing data (except headers)
            if scatter_sheet.row_count > 1:
                # Delete all rows except header
                try:
                    # Only delete if there are actually rows to delete (row_count must be > 1)
                    num_rows_to_delete = scatter_sheet.row_count - 1
                    if num_rows_to_delete > 0:
                        scatter_sheet.delete_rows(2, num_rows_to_delete)
                except Exception as e:
                    # If we can't delete, try clearing the range instead
                    print(f"  Note: Could not delete rows, clearing range instead (error: {e})")
                    try:
                        scatter_sheet.batch_clear(['A2:Z1000'])
                    except:
                        pass  # If clearing fails, we'll just append
            
            # Add new data
            scatter_sheet.append_rows(plot_data)
        # If no data, just leave the headers
    
    def update_criteria_matrix(self, criteria_results: List[Dict[str, Any]]) -> None:
        """
        Update criteria matrix sheet
        
        Args:
            criteria_results: List of dicts with 'address' and criteria flags
        """
        criteria_sheet = self._get_or_create_worksheet(self.CRITERIA_MATRIX_SHEET_NAME)
        
        # Get criteria order from headers
        headers = criteria_sheet.row_values(1)
        criterion_columns = headers[1:-1]  # Skip "Address" and "Total"
        
        # Build matrix data
        matrix_data = []
        for result in criteria_results:
            row = [result.get('address', '')]
            
            # Add checkmarks for each criterion
            for col_name in criterion_columns:
                # Convert column name back to snake_case key
                key = col_name.lower().replace(" ", "_")
                has_criterion = result.get(key, False)
                row.append("✓" if has_criterion else "")
            
            # Add total count
            total = result.get('total_criteria_met', 0)
            row.append(total)
            
            matrix_data.append(row)
        
        # Sort by total criteria met (descending)
        matrix_data.sort(key=lambda x: x[-1], reverse=True)
        
        if matrix_data:
            # Clear existing data (except headers)
            if criteria_sheet.row_count > 1:
                # Delete all rows except header
                try:
                    criteria_sheet.delete_rows(2, criteria_sheet.row_count)
                except Exception as e:
                    # If we can't delete (e.g., only header row exists), just clear any data
                    print(f"  Note: Clearing criteria matrix data (error: {e})")
                    # Clear range from row 2 onwards if it exists
                    try:
                        criteria_sheet.batch_clear(['A2:Z1000'])
                    except:
                        pass  # If clearing fails, we'll just append
            
            # Add new data
            criteria_sheet.append_rows(matrix_data)
            
            # Apply conditional formatting based on total
            # Green scale based on number of criteria met
            self._apply_criteria_conditional_formatting(criteria_sheet, len(matrix_data))
    
    def _apply_criteria_conditional_formatting(self, sheet: gspread.Worksheet, num_rows: int) -> None:
        """Apply conditional formatting to criteria matrix"""
        if num_rows == 0:
            return
        
        # Apply color scale to "Total Criteria Met" column
        last_col_letter = chr(65 + len(sheet.row_values(1)) - 1)
        range_notation = f"{last_col_letter}2:{last_col_letter}{num_rows + 1}"
        
        # Color scale: red (0) to yellow (4) to green (8)
        sheet.format(range_notation, {
            'backgroundColor': {'red': 0.85, 'green': 0.92, 'blue': 0.83}
        })
    
    def init_approved_gyms_sheet(self) -> None:
        """Initialize Approved Gyms sheet if it doesn't exist"""
        try:
            worksheet = self.spreadsheet.worksheet(self.APPROVED_GYMS_SHEET_NAME)
            # Check if already initialized
            if worksheet.row_count > 0:
                first_row = worksheet.row_values(1)
                if first_row and first_row[0] == "Gym Name":
                    return  # Already initialized
        except WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=self.APPROVED_GYMS_SHEET_NAME,
                rows=100,
                cols=10
            )
        
        headers = [
            "Gym Name",
            "Google Place ID",
            "Address",
            "Rating",
            "Types",
            "First Approved",
            "Times Used",
            "Latitude",
            "Longitude"
        ]
        worksheet.update(range_name='A1:I1', values=[headers])
        
        # Apply formatting
        worksheet.format('A1:I1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8}
        })
        worksheet.freeze(rows=1)
    
    def get_approved_gyms(self) -> List[Dict]:
        """Get all approved gyms from sheet"""
        try:
            worksheet = self.spreadsheet.worksheet(self.APPROVED_GYMS_SHEET_NAME)
            records = worksheet.get_all_records()
            return records
        except Exception as e:
            print(f"Error reading approved gyms: {e}")
            return []
    
    def add_approved_gym(self, gym_data: Dict) -> None:
        """Add a gym to approved list or increment usage count"""
        try:
            worksheet = self.spreadsheet.worksheet(self.APPROVED_GYMS_SHEET_NAME)
        except WorksheetNotFound:
            # Initialize if doesn't exist
            self.init_approved_gyms_sheet()
            worksheet = self.spreadsheet.worksheet(self.APPROVED_GYMS_SHEET_NAME)
        
        approved = self.get_approved_gyms()
        
        # Check if gym already exists (by place_id)
        existing_idx = None
        for idx, gym in enumerate(approved):
            if gym.get('Google Place ID') == gym_data.get('place_id'):
                existing_idx = idx
                break
        
        if existing_idx is not None:
            # Increment usage count
            row_num = existing_idx + 2  # +1 for header, +1 for 0-index
            current_count = approved[existing_idx].get('Times Used', 0)
            worksheet.update(range_name=f'G{row_num}', values=[[current_count + 1]])
        else:
            # Add new gym
            new_row = [
                gym_data.get('name'),
                gym_data.get('place_id'),
                gym_data.get('address'),
                gym_data.get('rating'),
                ', '.join(gym_data.get('types', [])),
                datetime.now().strftime('%Y-%m-%d'),
                1,  # Times Used
                gym_data.get('lat'),
                gym_data.get('lng')
            ]
            worksheet.append_row(new_row)
    
    def _initialize_user_edits_log_sheet(self) -> None:
        """Initialize User Edits Log sheet with headers"""
        try:
            worksheet = self.spreadsheet.worksheet(self.USER_EDITS_LOG_SHEET_NAME)
        except WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=self.USER_EDITS_LOG_SHEET_NAME,
                rows=1000,
                cols=7
            )
        
        # Set headers
        headers = [
            'Timestamp',
            'Apartment Address',
            'Field Changed',
            'Original Value',
            'New Value',
            'Original Weighted Score',
            'New Weighted Score'
        ]
        worksheet.update('A1:G1', [headers])
        
        # Format header row
        worksheet.format('A1:G1', {
            'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8},
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            'horizontalAlignment': 'CENTER'
        })
    
    def log_user_edit(self, apartment_address: str, changes: List[Dict[str, Any]], 
                     original_score: float, new_score: float) -> None:
        """
        Log user edits to tracking sheet
        
        Args:
            apartment_address: Address of the apartment
            changes: List of dicts with 'field', 'old_value', 'new_value'
            original_score: Weighted score before edits
            new_score: Weighted score after edits
        """
        try:
            # Get or create worksheet
            try:
                worksheet = self.spreadsheet.worksheet(self.USER_EDITS_LOG_SHEET_NAME)
            except WorksheetNotFound:
                self._initialize_user_edits_log_sheet()
                worksheet = self.spreadsheet.worksheet(self.USER_EDITS_LOG_SHEET_NAME)
            
            # Add a row for each changed field
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            rows_to_add = []
            
            for change in changes:
                row = [
                    timestamp,
                    apartment_address,
                    change.get('field', ''),
                    str(change.get('old_value', '')),
                    str(change.get('new_value', '')),
                    round(original_score, 2) if original_score else '',
                    round(new_score, 2) if new_score else ''
                ]
                rows_to_add.append(row)
            
            if rows_to_add:
                worksheet.append_rows(rows_to_add)
                print(f"Logged {len(rows_to_add)} edit(s) for {apartment_address}")
        
        except Exception as e:
            print(f"Error logging user edit: {e}")
            import traceback
            traceback.print_exc()
    
    def get_user_edits(self, apartment_address: str = None) -> List[Dict[str, Any]]:
        """
        Get user edit history
        
        Args:
            apartment_address: Optional filter by apartment address
            
        Returns:
            List of edit records
        """
        try:
            worksheet = self.spreadsheet.worksheet(self.USER_EDITS_LOG_SHEET_NAME)
            records = worksheet.get_all_records()
            
            if apartment_address:
                records = [r for r in records if r.get('Apartment Address') == apartment_address]
            
            return records
        except WorksheetNotFound:
            return []
        except Exception as e:
            print(f"Error reading user edits: {e}")
            return []

