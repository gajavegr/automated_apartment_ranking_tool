"""
Google Sheets integration for reading/writing apartment data

Handles multi-tab operations for:
- Main data sheet
- Scatter plot data
- Criteria matrix
"""

import os
import contextvars
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound, SpreadsheetNotFound

import config
from utils.rate_limiter import get_rate_limiter


# ---------------------------------------------------------------------------
# Per-user context
#
# The multi-user deployment stores each user's data in their own set of
# worksheet tabs, namespaced as "<username> - <Base Tab Name>". The active
# username is tracked per request/thread via a context variable so the single
# shared GoogleSheetsClient instance resolves worksheet lookups to the right
# user's tabs. When no user is set (e.g. CLI scripts, single-user usage), the
# base tab names are used unchanged for backwards compatibility.
# ---------------------------------------------------------------------------
_current_user_var: "contextvars.ContextVar[Optional[str]]" = contextvars.ContextVar(
    "current_sheets_user", default=None
)


def set_current_user(username: Optional[str]) -> None:
    """Set the active username for worksheet scoping (per request/thread)."""
    _current_user_var.set(username.strip() if username else None)


def get_current_user() -> Optional[str]:
    """Get the active username used for worksheet scoping, or None."""
    return _current_user_var.get()


class GoogleSheetsClient:
    """Client for interacting with Google Sheets"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # ------------------------------------------------------------------
    # Worksheet (tab) names
    #
    # Per-user tabs are namespaced as "<username> - <base name>" and resolved
    # dynamically via the properties below based on the active user context
    # (see set_current_user / get_current_user). Global tabs are shared across
    # all users and are NOT namespaced.
    # ------------------------------------------------------------------

    # Base names for per-user tabs
    _BASE_MAIN_SHEET_NAME = "Apartment Data"
    _BASE_SCATTER_PLOT_SHEET_NAME = "Price vs Score"
    _BASE_CRITERIA_MATRIX_SHEET_NAME = "Criteria Matrix"
    _BASE_PLACES_OF_INTEREST_SHEET_NAME = "Places of Interest"
    _BASE_EXCLUDED_PLACES_SHEET_NAME = "Excluded Places"
    _BASE_USER_EDITS_LOG_SHEET_NAME = "User Edits Log"
    _BASE_SETTINGS_SHEET_NAME = "Settings"

    # Global (shared) tabs — not namespaced per user.
    # "Approved Gyms" is a shared reference cache of gym metadata (place_id,
    # coordinates, rating) so expensive gym lookups aren't duplicated per user.
    APPROVED_GYMS_SHEET_NAME = "Approved Gyms"
    # "Users" is the registry of usernames used for the uniqueness check.
    USERS_SHEET_NAME = "Users"
    # Column in the Users tab that records when a user finished/dismissed the
    # first-run onboarding walkthrough (blank = not yet onboarded).
    _ONBOARDED_AT_HEADER = "Onboarded At"

    def _scoped_name(self, base_name: str) -> str:
        """Return the current user's namespaced tab name for a base name.

        Falls back to the base name when no user context is set.
        """
        user = get_current_user()
        if user:
            return f"{user} - {base_name}"
        return base_name

    @property
    def MAIN_SHEET_NAME(self) -> str:
        return self._scoped_name(self._BASE_MAIN_SHEET_NAME)

    @property
    def SCATTER_PLOT_SHEET_NAME(self) -> str:
        return self._scoped_name(self._BASE_SCATTER_PLOT_SHEET_NAME)

    @property
    def CRITERIA_MATRIX_SHEET_NAME(self) -> str:
        return self._scoped_name(self._BASE_CRITERIA_MATRIX_SHEET_NAME)

    @property
    def PLACES_OF_INTEREST_SHEET_NAME(self) -> str:
        return self._scoped_name(self._BASE_PLACES_OF_INTEREST_SHEET_NAME)

    @property
    def EXCLUDED_PLACES_SHEET_NAME(self) -> str:
        return self._scoped_name(self._BASE_EXCLUDED_PLACES_SHEET_NAME)

    @property
    def USER_EDITS_LOG_SHEET_NAME(self) -> str:
        return self._scoped_name(self._BASE_USER_EDITS_LOG_SHEET_NAME)

    @property
    def SETTINGS_SHEET_NAME(self) -> str:
        return self._scoped_name(self._BASE_SETTINGS_SHEET_NAME)

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
        self._format_json_columns(main_sheet)
        
        # Scatter plot sheet
        scatter_sheet = self._get_or_create_worksheet(self.SCATTER_PLOT_SHEET_NAME)
        self._initialize_scatter_plot_sheet(scatter_sheet)
        
        # Criteria matrix sheet
        criteria_sheet = self._get_or_create_worksheet(self.CRITERIA_MATRIX_SHEET_NAME)
        self._initialize_criteria_matrix_sheet(criteria_sheet)
    
    def _format_json_columns(self, sheet: gspread.Worksheet) -> None:
        """
        Format JSON columns to use CLIP instead of WRAP to prevent row height issues.
        This can be called multiple times safely to ensure formatting is preserved.
        """
        try:
            # Get header row to find JSON column indices
            headers = sheet.row_values(1)
            
            json_columns = [
                config.SHEET_COLUMNS.get("commute_details"),
                config.SHEET_COLUMNS.get("crime_details"),
                config.SHEET_COLUMNS.get("restaurants_list"),
                config.SHEET_COLUMNS.get("cafes_list"),
                config.SHEET_COLUMNS.get("parks_list"),
                config.SHEET_COLUMNS.get("pois_list")
            ]
            
            formatted_any = False
            for col_name in json_columns:
                if col_name and col_name in headers:
                    col_idx = headers.index(col_name)
                    col_letter = self._col_index_to_letter(col_idx)
                    
                    # Format entire column to use CLIP wrap strategy
                    # Use update_acell with formatOnly to preserve existing values
                    sheet.format(f'{col_letter}:{col_letter}', {
                        'wrapStrategy': 'CLIP',
                        'verticalAlignment': 'TOP'
                    })
                    formatted_any = True
                    print(f"  ✓ Formatted {col_name} column ({col_letter}) to use CLIP wrap strategy")
            
            if not formatted_any:
                print(f"  ℹ️  No JSON columns found to format")
                    
        except Exception as e:
            print(f"  ⚠️  Warning: Could not format JSON columns: {e}")
    
    def ensure_json_columns_formatted(self) -> None:
        """
        Public method to ensure JSON columns are formatted with CLIP.
        Can be called after any operation that might reset formatting.
        """
        try:
            sheet = self.spreadsheet.worksheet(self.MAIN_SHEET_NAME)
            self._format_json_columns(sheet)
        except Exception as e:
            print(f"  ⚠️  Warning: Could not format JSON columns: {e}")
    
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
            config.SHEET_COLUMNS["availability_status"],
            config.SHEET_COLUMNS["price"],
            config.SHEET_COLUMNS["bedrooms"],
            config.SHEET_COLUMNS["bathrooms"],
            config.SHEET_COLUMNS["sqft"],
            config.SHEET_COLUMNS["commute_time_you"],
            config.SHEET_COLUMNS["commute_route"],
            config.SHEET_COLUMNS["commute_time_partner"],
            config.SHEET_COLUMNS["route_annoyingness"],
            config.SHEET_COLUMNS["commute_details"],
            config.SHEET_COLUMNS["commute_score"],
            config.SHEET_COLUMNS["safety_score_opendata"],
            config.SHEET_COLUMNS["combined_safety"],
            config.SHEET_COLUMNS["crime_details"],
            config.SHEET_COLUMNS["wfh_quality_score"],
            config.SHEET_COLUMNS["natural_light"],
            config.SHEET_COLUMNS["desk_space_quality"],
            config.SHEET_COLUMNS["quietness_score"],
            config.SHEET_COLUMNS["double_pane_windows"],
            config.SHEET_COLUMNS["study_door_type"],
            config.SHEET_COLUMNS["kitchen_quality"],
            config.SHEET_COLUMNS["happening_score"],
            config.SHEET_COLUMNS["restaurants_nearby"],
            config.SHEET_COLUMNS["restaurants_list"],
            config.SHEET_COLUMNS["cafes_nearby"],
            config.SHEET_COLUMNS["cafes_list"],
            config.SHEET_COLUMNS["parks_nearby"],
            config.SHEET_COLUMNS["parks_list"],
            config.SHEET_COLUMNS["pois_list"],
            config.SHEET_COLUMNS["avg_walk_to_poi_mins"],
            config.SHEET_COLUMNS["nearest_poi_count"],
            config.SHEET_COLUMNS["pois_within_1_mile"],
            config.SHEET_COLUMNS["parking_type"],
            config.SHEET_COLUMNS["parking_enclosure"],
            config.SHEET_COLUMNS["parking_distance"],
            config.SHEET_COLUMNS["parking_cost"],
            config.SHEET_COLUMNS["street_parking_ease"],
            config.SHEET_COLUMNS["visitor_parking_ease"],
            config.SHEET_COLUMNS["parking_score"],
            config.SHEET_COLUMNS["laundry_type"],
            config.SHEET_COLUMNS["laundry_score"],
            config.SHEET_COLUMNS["gym_score"],
            config.SHEET_COLUMNS["space_luxury_score"],
            config.SHEET_COLUMNS["floor_level"],
            config.SHEET_COLUMNS["view_quality"],
            config.SHEET_COLUMNS["gym_within_10min"],
            config.SHEET_COLUMNS["gym_walk_time_mins"],
            config.SHEET_COLUMNS["gym_bike_time_mins"],
            config.SHEET_COLUMNS["gym_transport_mode"],
            config.SHEET_COLUMNS["gym_effective_time_mins"],
            config.SHEET_COLUMNS["gym_quality"],
            config.SHEET_COLUMNS["selected_gyms"],
            config.SHEET_COLUMNS["office_gym_only"],
            config.SHEET_COLUMNS["rent_control"],
            config.SHEET_COLUMNS["year_built"],
            config.SHEET_COLUMNS["neighborhood"],
            config.SHEET_COLUMNS["neighborhoods"],
            config.SHEET_COLUMNS["tour_questions"],
            config.SHEET_COLUMNS["weighted_score"],
            config.SHEET_COLUMNS["score_min"],
            config.SHEET_COLUMNS["score_max"],
            config.SHEET_COLUMNS["score_certainty"],
            config.SHEET_COLUMNS["score_vs_max"],
            config.SHEET_COLUMNS["value_ratio"],
            config.SHEET_COLUMNS["last_updated"],
            config.SHEET_COLUMNS["last_analyzed"],
        ]
        
        # Ensure the sheet is wide enough for every header before writing.
        # New tabs are created with a fixed default column count (see
        # _get_or_create_worksheet) that can be narrower than this header row —
        # the schema has grown over time — and writing past the sheet's width
        # otherwise fails with a Google Sheets 400 (INVALID_ARGUMENT), which
        # aborts new-user tab creation partway. Grow the sheet as needed, then
        # write to a range sized to the headers rather than a hardcoded one.
        if sheet.col_count < len(headers):
            sheet.add_cols(len(headers) - sheet.col_count)

        end_col = self._col_index_to_letter(len(headers) - 1)
        sheet.update(f'A1:{end_col}1', [headers])

        # Apply formatting across the full header range.
        sheet.format(f'A1:{end_col}1', {
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
        Get apartments that need analysis (have address but missing data)
        
        Returns:
            List of apartment records that need analysis
        """
        records = self.read_main_sheet()
        needing_analysis = []
        
        print(f"\n🔍 Checking {len(records)} records for analysis needs...")
        
        for i, record in enumerate(records):
            address = record.get(config.SHEET_COLUMNS["address"], "").strip()
            
            # Skip rows without addresses
            if not address:
                continue
            
            print(f"\n  📍 Row {i+2}: {address[:50]}...")
            
            zillow_url = record.get(config.SHEET_COLUMNS["zillow_url"], "").strip()
            weighted_score = record.get(config.SHEET_COLUMNS["weighted_score"], "")
            score_min_raw = record.get(config.SHEET_COLUMNS["score_min"], "")
            score_max_raw = record.get(config.SHEET_COLUMNS["score_max"], "")
            gym_score_raw = record.get(config.SHEET_COLUMNS["gym_score"], "")
            
            print(f"     Weighted Score: {weighted_score}")
            print(f"     Score Min (raw): {repr(score_min_raw)}")
            print(f"     Score Max (raw): {repr(score_max_raw)}")
            print(f"     Gym Score (raw): {repr(gym_score_raw)}")
            
            needs_analysis = False
            reason = None
            
            # Convert score_min/max to float for comparison
            try:
                score_min = float(score_min_raw) if score_min_raw not in ("", None) else None
                score_max = float(score_max_raw) if score_max_raw not in ("", None) else None
                gym_score = float(gym_score_raw) if gym_score_raw not in ("", None) else None
                print(f"     Score Min (parsed): {score_min}")
                print(f"     Score Max (parsed): {score_max}")
                print(f"     Gym Score (parsed): {gym_score}")
            except (ValueError, TypeError) as e:
                score_min = None
                score_max = None
                gym_score = None
                print(f"     ⚠️  Error parsing scores: {e}")
            
            # Check if missing score entirely
            if not weighted_score:
                needs_analysis = True
                reason = "no score"
                print(f"     ❌ No weighted score")
            # Check if gym score is missing
            elif gym_score is None:
                needs_analysis = True
                reason = "missing gym score"
                print(f"     ❌ Missing gym score")
            # Check if score range data is missing, zero, or invalid
            # Score of 0 doesn't make sense - apartments should have positive scores
            elif score_min is None or score_max is None or score_min == 0 or score_max == 0:
                needs_analysis = True
                reason = "missing or invalid score range data"
                print(f"     ❌ Invalid score range (min={score_min}, max={score_max})")
            # Check if missing metadata
            elif self.needs_commute_metadata_refresh(record):
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
                print(f"     ❌ Missing metadata: {reason}")
            else:
                print(f"     ✅ All data present, skipping")
            
            if needs_analysis:
                record['_row_number'] = i + 2  # +2 for 1-indexed and header row
                record['_analysis_reason'] = reason
                needing_analysis.append(record)
                print(f"     ➡️  WILL ANALYZE: {reason}")
        
        print(f"\n📊 Summary: {len(needing_analysis)} apartments need analysis\n")
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
            "availability_status": config.SHEET_COLUMNS["availability_status"],
            "price": config.SHEET_COLUMNS["price"],
            "bedrooms": config.SHEET_COLUMNS["bedrooms"],
            "bathrooms": config.SHEET_COLUMNS["bathrooms"],
            "sqft": config.SHEET_COLUMNS["sqft"],
            "commute_duration": config.SHEET_COLUMNS["commute_time_you"],  # Map commute_duration -> commute_time_you
            "commute_route": config.SHEET_COLUMNS["commute_route"],
            "commute_duration_partner": config.SHEET_COLUMNS["commute_time_partner"],  # Map commute_duration_partner -> commute_time_partner
            "route_annoyingness": config.SHEET_COLUMNS["route_annoyingness"],
            "commute_details_json": config.SHEET_COLUMNS["commute_details"],
            "commute_score": config.SHEET_COLUMNS["commute_score"],
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
            "happening_score": config.SHEET_COLUMNS["happening_score"],
            "restaurants_nearby": config.SHEET_COLUMNS["restaurants_nearby"],
            "restaurants_list": config.SHEET_COLUMNS["restaurants_list"],
            "cafes_nearby": config.SHEET_COLUMNS["cafes_nearby"],
            "cafes_list": config.SHEET_COLUMNS["cafes_list"],
            "parks_nearby": config.SHEET_COLUMNS["parks_nearby"],
            "parks_list": config.SHEET_COLUMNS["parks_list"],
            "pois_list": config.SHEET_COLUMNS["pois_list"],
            "avg_walk_to_poi_mins": config.SHEET_COLUMNS["avg_walk_to_poi_mins"],
            "nearest_poi_count": config.SHEET_COLUMNS["nearest_poi_count"],
            "pois_within_1_mile": config.SHEET_COLUMNS["pois_within_1_mile"],
            "parking_type": config.SHEET_COLUMNS["parking_type"],
            "parking_enclosure": config.SHEET_COLUMNS["parking_enclosure"],
            "parking_distance": config.SHEET_COLUMNS["parking_distance"],
            "parking_cost": config.SHEET_COLUMNS["parking_cost"],
            "street_parking_ease": config.SHEET_COLUMNS["street_parking_ease"],
            "visitor_parking_ease": config.SHEET_COLUMNS["visitor_parking_ease"],
            "parking_score": config.SHEET_COLUMNS["parking_score"],
            "laundry_type": config.SHEET_COLUMNS["laundry_type"],
            "laundry_score": config.SHEET_COLUMNS["laundry_score"],
            "gym_score": config.SHEET_COLUMNS["gym_score"],
            "space_luxury_score": config.SHEET_COLUMNS["space_luxury_score"],
            "floor_level": config.SHEET_COLUMNS["floor_level"],
            "view_quality": config.SHEET_COLUMNS["view_quality"],
            "gym_within_10min": config.SHEET_COLUMNS["gym_within_10min"],
            "gym_walk_time_mins": config.SHEET_COLUMNS["gym_walk_time_mins"],
            "gym_bike_time_mins": config.SHEET_COLUMNS["gym_bike_time_mins"],
            "gym_transport_mode": config.SHEET_COLUMNS["gym_transport_mode"],
            "gym_effective_time_mins": config.SHEET_COLUMNS["gym_effective_time_mins"],
            "gym_quality": config.SHEET_COLUMNS["gym_quality"],
            "selected_gyms": config.SHEET_COLUMNS["selected_gyms"],
            "office_gym_only": config.SHEET_COLUMNS["office_gym_only"],
            "rent_control": config.SHEET_COLUMNS["rent_control"],
            "year_built": config.SHEET_COLUMNS["year_built"],
            "neighborhood": config.SHEET_COLUMNS["neighborhood"],
            "neighborhoods": config.SHEET_COLUMNS["neighborhoods"],
            "tour_questions": config.SHEET_COLUMNS["tour_questions"],
            "weighted_score": config.SHEET_COLUMNS["weighted_score"],
            "score_min": config.SHEET_COLUMNS["score_min"],
            "score_max": config.SHEET_COLUMNS["score_max"],
            "score_certainty": config.SHEET_COLUMNS["score_certainty"],
            "score_vs_max": config.SHEET_COLUMNS["score_vs_max"],
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
        json_column_letters = []  # Track JSON columns to format
        
        for data_key, column_name in column_mapping.items():
            if data_key in data:
                try:
                    col_index = headers.index(column_name)
                    col_letter = col_index_to_letter(col_index)
                    value = data[data_key]
                    
                    if value is None:
                        value = ""
                    # Serialize JSON fields (they're already strings from main.py, but check dict types from other sources)
                    json_data_keys = ['commute_details_json', 'crime_details_json', 'restaurants_list', 'cafes_list', 'parks_list', 'pois_list']
                    if data_key in json_data_keys:
                        if isinstance(value, dict) or isinstance(value, list):
                            import json
                            value = json.dumps(value)
                        # Track this cell for CLIP formatting
                        json_column_letters.append(f"{col_letter}{row_number}")
                    
                    updates[f"{col_letter}{row_number}"] = value
                    if data_key == 'crime_details_json':
                        preview = value[:200] if isinstance(value, str) else str(value)
                        print(f"  -> Writing crime details to {column_name} (row {row_number}): {preview}...")
                except ValueError:
                    print(f"Warning: Column {column_name} not found in sheet")
        
        # Batch update values
        if updates:
            update_list = [{'range': cell, 'values': [[value]]} for cell, value in updates.items()]
            sheet.batch_update(update_list, value_input_option='USER_ENTERED')
            
            # Apply CLIP formatting to JSON cells to prevent wrapping
            if json_column_letters:
                for cell_range in json_column_letters:
                    try:
                        sheet.format(cell_range, {
                            'wrapStrategy': 'CLIP',
                            'verticalAlignment': 'TOP'
                        })
                    except Exception as e:
                        # Don't fail the whole operation if formatting fails
                        print(f"  ⚠️  Warning: Could not format {cell_range} as CLIP: {e}")
    
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
    
    def get_places_of_interest(self) -> List[Dict]:
        """Get list of user's places of interest in SF"""
        try:
            worksheet = self.spreadsheet.worksheet(self.PLACES_OF_INTEREST_SHEET_NAME)
            records = worksheet.get_all_records()
            # Filter to SF area (lat between 37.6 and 37.9, lng between -122.6 and -122.3)
            sf_places = []
            for place in records:
                lat = place.get('Latitude')
                lng = place.get('Longitude')
                if lat and lng:
                    try:
                        lat_float = float(lat)
                        lng_float = float(lng)
                        # SF bounding box
                        if 37.6 <= lat_float <= 37.9 and -122.6 <= lng_float <= -122.3:
                            sf_places.append(place)
                    except (ValueError, TypeError):
                        continue
            return sf_places
        except WorksheetNotFound:
            print(f"⚠️  '{self.PLACES_OF_INTEREST_SHEET_NAME}' sheet not found. Please create it.")
            return []
        except Exception as e:
            print(f"Error reading places of interest: {e}")
            return []
    
    def get_excluded_places(self) -> List[str]:
        """
        Get list of place_ids that have been excluded from happening score calculations
        
        Returns:
            List of place_ids to exclude
        """
        try:
            worksheet = self.spreadsheet.worksheet(self.EXCLUDED_PLACES_SHEET_NAME)
            records = worksheet.get_all_records()
            return [record.get('Place ID') for record in records if record.get('Place ID')]
        except WorksheetNotFound:
            # Create the sheet if it doesn't exist
            self._initialize_excluded_places_sheet()
            return []
        except Exception as e:
            print(f"Error reading excluded places: {e}")
            return []
    
    def add_excluded_place(self, place_id: str, place_name: str, place_type: str, reason: str = "") -> None:
        """
        Add a place to the exclusion list
        
        Args:
            place_id: Google Place ID
            place_name: Name of the place
            place_type: Type ('restaurant', 'cafe', 'park')
            reason: Optional reason for exclusion
        """
        print(f"\n  📝 add_excluded_place() called in GoogleSheetsClient")
        print(f"    Place ID: {place_id}")
        print(f"    Place Name: {place_name}")
        print(f"    Place Type: {place_type}")
        print(f"    Reason: {reason}")
        
        try:
            # Get or create the worksheet
            print(f"    🔍 Getting or creating '{self.EXCLUDED_PLACES_SHEET_NAME}' worksheet...")
            try:
                worksheet = self.spreadsheet.worksheet(self.EXCLUDED_PLACES_SHEET_NAME)
                print(f"    ✓ Found existing worksheet")
            except WorksheetNotFound:
                print(f"    ⚠️  Worksheet not found, creating new one...")
                self._initialize_excluded_places_sheet()
                worksheet = self.spreadsheet.worksheet(self.EXCLUDED_PLACES_SHEET_NAME)
                print(f"    ✓ Created and initialized worksheet")
            
            # Check if already excluded
            print(f"    🔍 Checking if place is already excluded...")
            excluded = self.get_excluded_places()
            print(f"    Current exclusion list: {excluded}")
            
            if place_id in excluded:
                print(f"    ℹ️  {place_name} is already in exclusion list")
                return
            
            print(f"    ✓ Place not in exclusion list, adding...")
            new_row = [
                place_id,
                place_name,
                place_type,
                reason,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            print(f"    📋 New row data: {new_row}")
            
            print(f"    📤 Appending row to worksheet...")
            worksheet.append_row(new_row)
            print(f"    ✅ Successfully added {place_name} to exclusion list!")
            
        except Exception as e:
            print(f"    ❌ Error adding excluded place: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def remove_excluded_place(self, place_id: str) -> None:
        """
        Remove a place from the exclusion list
        
        Args:
            place_id: Google Place ID to remove
        """
        try:
            worksheet = self.spreadsheet.worksheet(self.EXCLUDED_PLACES_SHEET_NAME)
            records = worksheet.get_all_records()
            
            # Find the row with this place_id
            for idx, record in enumerate(records):
                if record.get('Place ID') == place_id:
                    row_num = idx + 2  # +1 for header, +1 for 0-index
                    worksheet.delete_rows(row_num)
                    print(f"  ✓ Removed {record.get('Place Name')} from exclusion list")
                    return
            
            print(f"  ℹ️  Place ID {place_id} not found in exclusion list")
        except Exception as e:
            print(f"Error removing excluded place: {e}")
    
    def _initialize_excluded_places_sheet(self) -> None:
        """Initialize Excluded Places sheet with headers"""
        try:
            worksheet = self.spreadsheet.worksheet(self.EXCLUDED_PLACES_SHEET_NAME)
        except WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=self.EXCLUDED_PLACES_SHEET_NAME,
                rows=100,
                cols=5
            )
        
        # Set headers
        headers = ["Place ID", "Place Name", "Type", "Reason", "Date Added"]
        worksheet.update('A1:E1', [headers])
        
        # Format header row
        worksheet.format('A1:E1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
        })
    
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

    def get_weight_settings(self) -> Dict[str, float]:
        """
        Get custom weight settings from Settings sheet
        
        Returns:
            Dictionary of component weights, or empty dict if not found
        """
        try:
            worksheet = self.spreadsheet.worksheet(self.SETTINGS_SHEET_NAME)
            records = worksheet.get_all_records()
            
            weights = {}
            for record in records:
                component = record.get('Component')
                weight = record.get('Weight')
                if component and weight is not None:
                    try:
                        weights[component] = float(weight)
                    except (ValueError, TypeError):
                        continue
            
            return weights
        except WorksheetNotFound:
            return {}
        except Exception as e:
            print(f"Error reading weight settings: {e}")
            return {}
    
    def save_weight_settings(self, weights: Dict[str, float]):
        """
        Save custom weight settings to Settings sheet
        
        Args:
            weights: Dictionary of component weights
        """
        try:
            # Get or create Settings sheet
            try:
                worksheet = self.spreadsheet.worksheet(self.SETTINGS_SHEET_NAME)
            except WorksheetNotFound:
                worksheet = self.spreadsheet.add_worksheet(
                    title=self.SETTINGS_SHEET_NAME,
                    rows=20,
                    cols=4
                )
                self._initialize_settings_sheet(worksheet)
            
            # Clear existing data (keep headers)
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
            
            # Add weight data
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            rows = []
            for component, weight in weights.items():
                rows.append([component, weight, timestamp, "Web App"])
            
            if rows:
                worksheet.append_rows(rows)
            
            print(f"✓ Saved {len(weights)} weight settings to Google Sheets")
        except Exception as e:
            print(f"Error saving weight settings: {e}")
            raise
    
    def _initialize_settings_sheet(self, sheet: gspread.Worksheet) -> None:
        """Initialize Settings sheet with headers"""
        headers = ["Component", "Weight", "Last Updated", "Updated By"]
        sheet.update('A1:D1', [headers])
        sheet.format('A1:D1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8}
        })
        sheet.freeze(rows=1)

    # ------------------------------------------------------------------
    # User registry (multi-user support)
    #
    # A single global "Users" tab holds the set of usernames. It is used for
    # the uniqueness check on registration and to resolve the canonical
    # (stored) casing of a username at login so worksheet tab names match.
    # ------------------------------------------------------------------

    def _get_users_worksheet(self) -> gspread.Worksheet:
        """Get (or create + initialize) the global Users registry worksheet."""
        try:
            return self.spreadsheet.worksheet(self.USERS_SHEET_NAME)
        except WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=self.USERS_SHEET_NAME,
                rows=1000,
                cols=3
            )
            headers = ["Username", "Created At", self._ONBOARDED_AT_HEADER]
            worksheet.update('A1:C1', [headers])
            worksheet.format('A1:C1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8}
            })
            worksheet.freeze(rows=1)
            return worksheet

    def list_users(self) -> List[str]:
        """Return all registered usernames (as stored)."""
        worksheet = self._get_users_worksheet()
        records = worksheet.get_all_records()
        users = []
        for record in records:
            username = str(record.get('Username', '')).strip()
            if username:
                users.append(username)
        return users

    def get_canonical_username(self, username: str) -> Optional[str]:
        """Return the stored form of a username matching case-insensitively.

        Returns None if the username is not registered.
        """
        if not username:
            return None
        target = username.strip().lower()
        for stored in self.list_users():
            if stored.lower() == target:
                return stored
        return None

    def user_exists(self, username: str) -> bool:
        """Return True if a username is already registered (case-insensitive)."""
        return self.get_canonical_username(username) is not None

    def create_user(self, username: str) -> bool:
        """Register a new username and initialize their worksheet tabs.

        Returns True if created, False if the username already exists
        (case-insensitive collision).
        """
        username = (username or "").strip()
        if not username:
            raise ValueError("Username cannot be empty")

        if self.user_exists(username):
            return False

        worksheet = self._get_users_worksheet()
        worksheet.append_row([
            username,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        ])

        # Initialize this user's core worksheet tabs so the app has headers
        # to read/write against immediately after registration.
        previous_user = get_current_user()
        try:
            set_current_user(username)
            self.initialize_sheets()
        except Exception as e:
            print(f"⚠️  Warning: could not initialize sheets for '{username}': {e}")
        finally:
            set_current_user(previous_user)

        return True

    def delete_user(self, username: str) -> Dict[str, Any]:
        """Delete a user and all of their per-user data. Inverse of create_user.

        Removes the user's row from the global Users registry and deletes every
        worksheet tab namespaced to that user ("<username> - *"). Global tabs
        (Users, Approved Gyms) and other users' tabs are never touched.

        Matching is case-insensitive (like get_canonical_username) so the caller
        can pass whatever casing they have; the canonical stored form is used to
        build the tab prefix.

        Returns a result dict:
            {
                'existed': bool,            # was the user in the registry?
                'deleted': bool,            # did we remove anything?
                'username': str,            # canonical username (or the input
                                            #   if it wasn't registered)
                'tabs_deleted': List[str],  # titles of per-user tabs removed
                'registry_row_removed': bool,
            }

        Deleting a non-existent user is not an error: it returns
        existed=False / deleted=False so callers can respond with a clear,
        non-500 message.
        """
        requested = (username or "").strip()
        canonical = self.get_canonical_username(requested) if requested else None

        if not canonical:
            return {
                'existed': False,
                'deleted': False,
                'username': requested,
                'tabs_deleted': [],
                'registry_row_removed': False,
            }

        # Safety guard: only ever delete tabs that carry this exact user's
        # "<username> - " prefix. The " - " separator (not just "<username>")
        # keeps us from matching another user whose name shares this prefix
        # (e.g. "bob" must not match "bobby - Apartment Data"). Global tabs have
        # no prefix and are additionally excluded by name below.
        prefix = f"{canonical} - ".lower()
        global_tabs = {self.USERS_SHEET_NAME.lower(), self.APPROVED_GYMS_SHEET_NAME.lower()}

        tabs_deleted: List[str] = []
        for worksheet in self.spreadsheet.worksheets():
            title = worksheet.title
            if title.lower() in global_tabs:
                continue
            if title.lower().startswith(prefix):
                try:
                    self.spreadsheet.del_worksheet(worksheet)
                    tabs_deleted.append(title)
                except Exception as e:
                    print(f"⚠️  Warning: could not delete tab '{title}': {e}")

        # Remove the user's row from the global Users registry (case-insensitive
        # match on the canonical name). Row 1 is the header.
        registry_row_removed = False
        try:
            users_ws = self._get_users_worksheet()
            usernames = users_ws.col_values(1)
            target = canonical.lower()
            for i, stored in enumerate(usernames[1:], start=2):
                if str(stored).strip().lower() == target:
                    users_ws.delete_rows(i)
                    registry_row_removed = True
                    break
        except Exception as e:
            print(f"⚠️  Warning: could not remove '{canonical}' from Users registry: {e}")

        return {
            'existed': True,
            'deleted': registry_row_removed or bool(tabs_deleted),
            'username': canonical,
            'tabs_deleted': tabs_deleted,
            'registry_row_removed': registry_row_removed,
        }

    # ------------------------------------------------------------------
    # Onboarding state (multi-user support)
    #
    # Whether a user has finished/dismissed the first-run walkthrough is
    # tracked in the global Users tab (an "Onboarded At" timestamp column)
    # rather than a per-user tab, so it's a single lookup keyed by username.
    # ------------------------------------------------------------------

    def has_completed_onboarding(self, username: str) -> bool:
        """Return True if the user has finished or dismissed onboarding.

        Robust to an older Users tab that predates the "Onboarded At" column:
        the header is simply absent from the records, so this returns False.
        """
        if not username:
            return False
        target = username.strip().lower()
        try:
            worksheet = self._get_users_worksheet()
            for record in worksheet.get_all_records():
                stored = str(record.get('Username', '')).strip()
                if stored.lower() == target:
                    return bool(str(record.get(self._ONBOARDED_AT_HEADER, '')).strip())
        except Exception as e:
            print(f"Error reading onboarding state for '{username}': {e}")
        return False

    def mark_onboarding_complete(self, username: str) -> bool:
        """Record that the user has finished/dismissed onboarding.

        Adds the "Onboarded At" column to the Users tab on the fly if it does
        not exist yet (older registries created with only two columns), then
        stamps the current time in the matching user's row. Returns True on a
        successful write, False if the user could not be found.
        """
        if not username:
            return False
        target = username.strip().lower()
        try:
            worksheet = self._get_users_worksheet()
            header_row = worksheet.row_values(1)

            # Locate (or append) the "Onboarded At" column.
            try:
                col_idx = header_row.index(self._ONBOARDED_AT_HEADER) + 1
            except ValueError:
                col_idx = len(header_row) + 1
                worksheet.update_cell(1, col_idx, self._ONBOARDED_AT_HEADER)

            # Find the user's row (row 1 is the header).
            usernames = worksheet.col_values(1)
            row_idx = None
            for i, stored in enumerate(usernames[1:], start=2):
                if str(stored).strip().lower() == target:
                    row_idx = i
                    break
            if row_idx is None:
                return False

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            worksheet.update_cell(row_idx, col_idx, timestamp)
            return True
        except Exception as e:
            print(f"Error marking onboarding complete for '{username}': {e}")
            return False

