#!/usr/bin/env python3
"""
Manual data entry helper for apartments

Since Zillow actively blocks automated scraping (403 errors), this tool
helps you quickly input data manually from the Zillow page you have open.
"""

import sys
from datetime import datetime
from utils.google_sheets import GoogleSheetsClient
import config


def manual_entry():
    """Interactively collect apartment data"""
    print("\n" + "="*80)
    print("MANUAL APARTMENT DATA ENTRY")
    print("="*80)
    print("\nOpen the Zillow listing in your browser and enter the info below.")
    print("Press Ctrl+C at any time to cancel.\n")
    
    data = {}
    
    # Required fields
    print("--- BASIC INFO ---")
    data['zillow_url'] = input("Zillow URL: ").strip()
    data['address'] = input("Address: ").strip()
    
    try:
        data['price'] = int(input("Monthly rent ($): ").strip())
    except ValueError:
        data['price'] = 0
    
    try:
        data['bedrooms'] = int(input("Bedrooms: ").strip())
    except ValueError:
        data['bedrooms'] = 0
    
    try:
        data['bathrooms'] = float(input("Bathrooms: ").strip())
    except ValueError:
        data['bathrooms'] = 0
    
    try:
        data['sqft'] = int(input("Square feet: ").strip())
    except ValueError:
        data['sqft'] = 0
    
    print("\n--- PARKING ---")
    print("Options: single_garage, dedicated_spot_car_and_motorcycle, dedicated_spot_car_only, street_parking, none")
    data['parking_type'] = input("Parking type: ").strip() or "none"
    
    if data['parking_type'] != 'none' and data['parking_type'] != 'street_parking':
        print("\nParking enclosure options: enclosed, covered, open")
        data['parking_enclosure'] = input("Parking enclosure (optional): ").strip()
    
    print("\n--- LAUNDRY ---")
    print("Options: in_unit, shared_good, shared_poor, none")
    data['laundry_type'] = input("Laundry type: ").strip() or "none"
    
    print("\n--- SAFETY (your assessment) ---")
    try:
        data['manual_safety_rating'] = float(input("Safety rating (0-10): ").strip())
    except ValueError:
        data['manual_safety_rating'] = 5.0
    
    print("\n--- OPTIONAL ---")
    data['neighborhood'] = input("Neighborhood (optional): ").strip()
    
    year_built = input("Year built (optional, for rent control): ").strip()
    if year_built:
        try:
            year = int(year_built)
            data['year_built'] = year
            data['rent_control'] = year < config.SF_RENT_CONTROL_CUTOFF_YEAR
        except ValueError:
            pass
    
    # Timestamp
    data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return data


def add_to_sheet(data: dict):
    """Add manually entered data to Google Sheet"""
    print("\n" + "="*80)
    print("ADDING TO GOOGLE SHEET")
    print("="*80)
    
    try:
        sheets_client = GoogleSheetsClient()
        sheet = sheets_client.spreadsheet.worksheet(sheets_client.MAIN_SHEET_NAME)
        
        # Find the first empty row
        records = sheets_client.read_main_sheet()
        row_number = len(records) + 2  # +2 for header and 1-indexing
        
        print(f"\nAdding to row {row_number}...")
        
        # Write the Zillow URL first (column A) - using named parameters
        sheet.update(
            values=[[data.get('zillow_url', '')]],
            range_name=f'A{row_number}'
        )
        
        # Write manual safety rating (column B)
        sheet.update(
            values=[[data.get('manual_safety_rating', 5.0)]],
            range_name=f'B{row_number}'
        )
        
        # Write address as hyperlink in column C (if Zillow URL provided)
        headers = sheet.row_values(1)
        address_col_name = config.SHEET_COLUMNS['address']
        if address_col_name in headers:
            col_idx = headers.index(address_col_name) + 1
            col_letter = chr(64 + col_idx)
            
            if data.get('zillow_url'):
                # Create HYPERLINK formula
                formula = f'=HYPERLINK("{data["zillow_url"]}", "{data["address"]}")'
                sheet.update(
                    values=[[formula]],
                    range_name=f'{col_letter}{row_number}'
                )
            else:
                sheet.update(
                    values=[[data.get('address', '')]],
                    range_name=f'{col_letter}{row_number}'
                )
        
        # Write other basic data to columns (price, beds, baths, sqft)
        sheet.update(
            values=[[
                data.get('price', ''),
                data.get('bedrooms', ''),
                data.get('bathrooms', ''),
                data.get('sqft', ''),
            ]],
            range_name=f'D{row_number}:G{row_number}'
        )
        
        # Write parking type (find column for parking_type)
        # For now, write to a few key columns we know
        
        # Find and update parking type column
        if config.SHEET_COLUMNS["parking_type"] in headers:
            col_idx = headers.index(config.SHEET_COLUMNS["parking_type"]) + 1
            col_letter = chr(64 + col_idx)
            sheet.update(
                values=[[data.get('parking_type', '')]],
                range_name=f'{col_letter}{row_number}'
            )
        
        # Find and update parking enclosure column
        if config.SHEET_COLUMNS["parking_enclosure"] in headers:
            col_idx = headers.index(config.SHEET_COLUMNS["parking_enclosure"]) + 1
            col_letter = chr(64 + col_idx)
            sheet.update(
                values=[[data.get('parking_enclosure', '')]],
                range_name=f'{col_letter}{row_number}'
            )
        
        # Find and update laundry column
        if config.SHEET_COLUMNS["laundry_type"] in headers:
            col_idx = headers.index(config.SHEET_COLUMNS["laundry_type"]) + 1
            col_letter = chr(64 + col_idx)
            sheet.update(
                values=[[data.get('laundry_type', '')]],
                range_name=f'{col_letter}{row_number}'
            )
        
        # Find and update neighborhood column
        if config.SHEET_COLUMNS["neighborhood"] in headers:
            col_idx = headers.index(config.SHEET_COLUMNS["neighborhood"]) + 1
            col_letter = chr(64 + col_idx)
            sheet.update(
                values=[[data.get('neighborhood', '')]],
                range_name=f'{col_letter}{row_number}'
            )
        
        # Find and update rent control column
        if config.SHEET_COLUMNS["rent_control"] in headers:
            col_idx = headers.index(config.SHEET_COLUMNS["rent_control"]) + 1
            col_letter = chr(64 + col_idx)
            sheet.update(
                values=[[data.get('rent_control', False)]],
                range_name=f'{col_letter}{row_number}'
            )
        
        # Update timestamp
        if config.SHEET_COLUMNS["last_updated"] in headers:
            col_idx = headers.index(config.SHEET_COLUMNS["last_updated"]) + 1
            col_letter = chr(64 + col_idx)
            sheet.update(
                values=[[data.get('last_updated', '')]],
                range_name=f'{col_letter}{row_number}'
            )
        
        print("✓ Data added successfully!")
        print(f"\nRow {row_number}: {data.get('address', 'Unknown')}")
        print("\nNow run: python main.py --analyze-new")
        print("This will fill in location data, safety scores, and calculate the final score.")
        
    except Exception as e:
        print(f"\n✗ Error adding to sheet: {e}")
        print("\nYou can manually add this row to your sheet:")
        print(f"  URL: {data.get('zillow_url')}")
        print(f"  Manual Safety: {data.get('manual_safety_rating')}")
        print(f"  Address: {data.get('address')}")
        print(f"  Price: {data.get('price')}")
        print(f"  Beds/Baths/Sqft: {data.get('bedrooms')}/{data.get('bathrooms')}/{data.get('sqft')}")
        print(f"  Parking: {data.get('parking_type')}")
        print(f"  Laundry: {data.get('laundry_type')}")


def main():
    """Main entry point"""
    print("\n🏠 MANUAL APARTMENT DATA ENTRY")
    print("\nZillow blocks automated scraping (HTTP 403 errors).")
    print("Use this tool to quickly add apartments manually while we fix scraping.\n")
    
    try:
        while True:
            data = manual_entry()
            
            print("\n" + "-"*80)
            print("REVIEW YOUR ENTRY:")
            print("-"*80)
            print(f"Address: {data.get('address')}")
            print(f"Price: ${data.get('price')}/mo")
            print(f"Beds/Baths: {data.get('bedrooms')}/{data.get('bathrooms')}")
            print(f"Sqft: {data.get('sqft')}")
            print(f"Parking: {data.get('parking_type')}")
            print(f"Laundry: {data.get('laundry_type')}")
            print(f"Safety: {data.get('manual_safety_rating')}/10")
            
            confirm = input("\nAdd this to the sheet? (y/n): ").strip().lower()
            
            if confirm == 'y':
                add_to_sheet(data)
            else:
                print("Skipped.")
            
            another = input("\nAdd another apartment? (y/n): ").strip().lower()
            if another != 'y':
                break
        
        print("\n✓ Done! Run 'python main.py --analyze-new' to analyze with location data.\n")
    
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(0)
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

