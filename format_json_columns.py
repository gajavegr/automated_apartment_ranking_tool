#!/usr/bin/env python3
"""
Script to format JSON columns in existing Google Sheet to use CLIP instead of WRAP.
This prevents those columns from making rows extremely tall.

Run this if you already have data and want to fix the formatting.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.google_sheets import GoogleSheetsClient
import config


def format_json_columns():
    """Format JSON columns to use CLIP wrap strategy"""
    print("🔧 Formatting JSON Columns in Google Sheet")
    print("=" * 70)
    
    try:
        # Initialize client
        print("\n📊 Connecting to Google Sheets...")
        sheets_client = GoogleSheetsClient()
        
        print(f"✓ Connected to sheet: {sheets_client.MAIN_SHEET_NAME}")
        print(f"\n🎯 Formatting JSON columns to use CLIP (no wrap)...")
        
        # Use the built-in method
        sheets_client.ensure_json_columns_formatted()
        
        print(f"\n{'=' * 70}")
        print(f"✅ Success! JSON columns formatted")
        print(f"\n💡 The JSON columns will now clip text instead of wrapping.")
        print(f"   This keeps row heights manageable in the spreadsheet.")
        print(f"   You can still click on a cell to see the full JSON content.")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(format_json_columns())

