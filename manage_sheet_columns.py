#!/usr/bin/env python3
"""
Sheet Column Management Tool

Automatically syncs your Google Sheet columns with the config.py SHEET_COLUMNS definition.
Handles adding missing columns, detecting extra columns, and validating column order.

Usage:
    python manage_sheet_columns.py --check        # Check for differences
    python manage_sheet_columns.py --sync         # Add missing columns
    python manage_sheet_columns.py --sync --force # Add missing AND reorder columns
"""

import argparse
import sys
from typing import List, Dict, Tuple

import config
from utils.google_sheets import GoogleSheetsClient


class SheetColumnManager:
    """Manages Google Sheet column structure"""
    
    def __init__(self):
        self.client = GoogleSheetsClient()
        self.sheet = self.client.spreadsheet.worksheet(self.client.MAIN_SHEET_NAME)
        
    def get_expected_columns(self) -> List[str]:
        """Get the expected column order from config"""
        # This is the canonical order defined in _initialize_main_sheet
        return [
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
    
    def get_current_columns(self) -> List[str]:
        """Get current column headers from sheet"""
        return self.sheet.row_values(1)
    
    def analyze_differences(self) -> Dict[str, List[str]]:
        """
        Analyze differences between expected and current columns
        
        Returns:
            Dict with 'missing', 'extra', and 'misplaced' keys
        """
        expected = self.get_expected_columns()
        current = self.get_current_columns()
        
        missing = [col for col in expected if col not in current]
        extra = [col for col in current if col not in expected]
        
        # Check if columns are in wrong order (only for columns that exist in both)
        misplaced = []
        for i, expected_col in enumerate(expected):
            if expected_col in current:
                current_idx = current.index(expected_col)
                # Count how many expected columns before this one exist in current
                expected_before = [c for c in expected[:i] if c in current]
                if len(expected_before) != current_idx:
                    misplaced.append(expected_col)
        
        return {
            'missing': missing,
            'extra': extra,
            'misplaced': misplaced
        }
    
    def print_analysis(self, differences: Dict[str, List[str]]) -> bool:
        """
        Print analysis results
        
        Returns:
            True if there are differences, False if sheet is in sync
        """
        has_differences = False
        
        print("\n" + "="*70)
        print("SHEET COLUMN ANALYSIS")
        print("="*70)
        
        expected = self.get_expected_columns()
        current = self.get_current_columns()
        
        print(f"\nExpected columns: {len(expected)}")
        print(f"Current columns:  {len(current)}")
        
        if differences['missing']:
            has_differences = True
            print(f"\n❌ MISSING COLUMNS ({len(differences['missing'])}):")
            for col in differences['missing']:
                expected_idx = expected.index(col)
                after_col = expected[expected_idx - 1] if expected_idx > 0 else "START"
                print(f"   • {col}")
                print(f"     Should be after: {after_col}")
        
        if differences['extra']:
            has_differences = True
            print(f"\n⚠️  EXTRA COLUMNS ({len(differences['extra'])}):")
            print("   These columns exist in the sheet but not in config:")
            for col in differences['extra']:
                current_idx = current.index(col)
                print(f"   • {col} (position {current_idx + 1})")
        
        if differences['misplaced']:
            has_differences = True
            print(f"\n⚠️  MISPLACED COLUMNS ({len(differences['misplaced'])}):")
            print("   These columns exist but are in the wrong position:")
            for col in differences['misplaced']:
                expected_idx = expected.index(col)
                current_idx = current.index(col)
                print(f"   • {col}")
                print(f"     Expected position: {expected_idx + 1}, Current position: {current_idx + 1}")
        
        if not has_differences:
            print("\n✅ Sheet is in sync with config!")
            print("   All columns are present and in the correct order.")
        
        print("\n" + "="*70)
        
        return has_differences
    
    def add_missing_columns(self, missing: List[str], dry_run: bool = False) -> None:
        """
        Add missing columns to the sheet
        
        Args:
            missing: List of column names to add
            dry_run: If True, only print what would be done
        """
        if not missing:
            print("\n✅ No missing columns to add.")
            return
        
        expected = self.get_expected_columns()
        current = self.get_current_columns()
        
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Adding {len(missing)} missing column(s)...")
        
        for col_name in missing:
            # Find where this column should be inserted
            expected_idx = expected.index(col_name)
            
            # Find the insertion point in current sheet
            # Insert after the last column that should come before this one
            insert_after_idx = 0
            for i in range(expected_idx - 1, -1, -1):
                prev_col = expected[i]
                if prev_col in current:
                    insert_after_idx = current.index(prev_col) + 1
                    break
            
            col_letter = self._col_index_to_letter(insert_after_idx)
            
            print(f"\n  Adding: {col_name}")
            print(f"    Position: {insert_after_idx + 1} (column {col_letter})")
            
            if not dry_run:
                # Insert column
                self.sheet.spreadsheet.batch_update({
                    'requests': [{
                        'insertDimension': {
                            'range': {
                                'sheetId': self.sheet.id,
                                'dimension': 'COLUMNS',
                                'startIndex': insert_after_idx,
                                'endIndex': insert_after_idx + 1
                            }
                        }
                    }]
                })
                
                # Set header
                self.sheet.update(f'{col_letter}1', [[col_name]])
                
                # Format header
                self.sheet.format(f'{col_letter}1', {
                    'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8},
                    'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                    'horizontalAlignment': 'CENTER'
                })
                
                # Set default values only for rows with addresses (primary key)
                if self.sheet.row_count > 1:
                    # Get the Address column to check which rows have data
                    address_col_name = config.SHEET_COLUMNS.get("address", "Address")
                    current_headers = self.get_current_columns()
                    
                    if address_col_name in current_headers:
                        address_col_idx = current_headers.index(address_col_name)
                        address_col_letter = self._col_index_to_letter(address_col_idx)
                        
                        # Get all addresses - col_values() returns values up to last non-empty cell
                        all_addresses = self.sheet.col_values(address_col_idx + 1)
                        
                        # Build list of updates only for rows with addresses
                        default_value = 0 if 'cost' in col_name.lower() or 'score' in col_name.lower() else ''
                        updates = []
                        
                        # Start from index 1 (skip header at index 0)
                        for idx, address in enumerate(all_addresses[1:], start=2):
                            if address and address.strip():  # Only if address exists and is not empty
                                updates.append({
                                    'range': f'{col_letter}{idx}',
                                    'values': [[default_value]]
                                })
                        
                        # Batch update all rows with addresses
                        if updates:
                            self.sheet.batch_update(updates)
                            print(f"    ✓ Set default values for {len(updates)} row(s) with addresses")
                        else:
                            print(f"    ℹ️  No rows with addresses found, skipping default values")
                    else:
                        # If no Address column found, don't set any defaults
                        print(f"    ⚠️  Warning: Address column not found, skipping default values")
                
                # Update current list for next iteration
                current.insert(insert_after_idx, col_name)
                
                print(f"    ✓ Added successfully")
        
        if not dry_run:
            print(f"\n✅ Successfully added {len(missing)} column(s)!")
    
    def reorder_columns(self, dry_run: bool = False) -> None:
        """
        Reorder columns to match expected order
        
        Args:
            dry_run: If True, only print what would be done
        """
        expected = self.get_expected_columns()
        current = self.get_current_columns()
        
        # Only reorder columns that exist in both
        common_cols = [col for col in expected if col in current]
        
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Reordering columns to match config...")
        print(f"  Columns to reorder: {len(common_cols)}")
        
        if dry_run:
            print("\n  Expected order:")
            for i, col in enumerate(common_cols):
                current_idx = current.index(col)
                status = "✓" if i == current_idx else "→"
                print(f"    {status} {col} (current pos: {current_idx + 1}, target pos: {i + 1})")
        else:
            print("\n  ⚠️  WARNING: Reordering columns is a complex operation.")
            print("     It's safer to manually reorder in Google Sheets if needed.")
            print("     This feature is not yet implemented for safety reasons.")
    
    @staticmethod
    def _col_index_to_letter(col_index: int) -> str:
        """Convert column index to letter (0=A, 25=Z, 26=AA, etc.)"""
        result = ""
        while col_index >= 0:
            result = chr(65 + (col_index % 26)) + result
            col_index = col_index // 26 - 1
        return result


def main():
    parser = argparse.ArgumentParser(
        description='Manage Google Sheet columns to match config.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python manage_sheet_columns.py --check              # Check for differences
  python manage_sheet_columns.py --sync               # Add missing columns
  python manage_sheet_columns.py --sync --dry-run     # Preview changes
  python manage_sheet_columns.py --sync --force       # Add and reorder columns
        """
    )
    
    parser.add_argument('--check', action='store_true',
                       help='Check for differences between sheet and config')
    parser.add_argument('--sync', action='store_true',
                       help='Sync sheet with config (add missing columns)')
    parser.add_argument('--force', action='store_true',
                       help='Force full sync including reordering (use with --sync)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    # Default to check if no action specified
    if not (args.check or args.sync):
        args.check = True
    
    try:
        manager = SheetColumnManager()
        differences = manager.analyze_differences()
        
        # Always print analysis
        has_differences = manager.print_analysis(differences)
        
        if args.sync:
            if not has_differences:
                print("\n✅ Nothing to sync - sheet is already up to date!")
                return 0
            
            if args.dry_run:
                print("\n" + "="*70)
                print("DRY RUN MODE - No changes will be made")
                print("="*70)
            
            # Add missing columns
            manager.add_missing_columns(differences['missing'], dry_run=args.dry_run)
            
            # Reorder if --force is specified
            if args.force and differences['misplaced']:
                manager.reorder_columns(dry_run=args.dry_run)
            
            if not args.dry_run:
                print("\n✅ Sync complete!")
                print("   Run with --check to verify changes.")
        
        elif has_differences:
            print("\n💡 TIP: Run with --sync to add missing columns")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

