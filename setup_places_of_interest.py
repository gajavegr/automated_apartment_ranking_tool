#!/usr/bin/env python3
"""
Setup script for "Places of Interest" sheet
This script helps you add your favorite places from Google Maps to the sheet
"""

import sys
from utils.google_sheets import GoogleSheetsClient
from analyzers.location_analyzer import LocationAnalyzer
import config

def create_sheet_if_needed(sheets_client):
    """Create 'Places of Interest' sheet with proper headers"""
    try:
        worksheet = sheets_client.spreadsheet.worksheet(sheets_client.PLACES_OF_INTEREST_SHEET_NAME)
        print(f"✓ '{sheets_client.PLACES_OF_INTEREST_SHEET_NAME}' sheet already exists")
        
        # Check if it has proper headers
        headers = worksheet.row_values(1)
        if not headers or headers[0] != "Name":
            print("  Setting up headers...")
            worksheet.insert_row(['Name', 'Address', 'Latitude', 'Longitude', 'Category', 'Notes'], 1)
            print("  ✓ Headers added")
        
        return worksheet
    except:
        print(f"Creating '{sheets_client.PLACES_OF_INTEREST_SHEET_NAME}' sheet...")
        worksheet = sheets_client.spreadsheet.add_worksheet(
            title=sheets_client.PLACES_OF_INTEREST_SHEET_NAME,
            rows=100,
            cols=6
        )
        worksheet.append_row(['Name', 'Address', 'Latitude', 'Longitude', 'Category', 'Notes'])
        print(f"✓ Created '{sheets_client.PLACES_OF_INTEREST_SHEET_NAME}' sheet with headers")
        return worksheet

def add_place_manually(sheets_client, location_analyzer):
    """Add a place manually by name or address"""
    print("\n" + "="*70)
    print("ADD A PLACE OF INTEREST")
    print("="*70)
    
    name = input("\nPlace name: ").strip()
    if not name:
        print("❌ Name is required")
        return
    
    address = input("Address (or press Enter to search by name): ").strip()
    
    if not address:
        # Try to geocode by name
        print(f"Searching for '{name}'...")
        coords = location_analyzer.geocode_address(name)
    else:
        # Geocode by address
        print(f"Geocoding '{address}'...")
        coords = location_analyzer.geocode_address(address)
    
    if not coords:
        print("❌ Could not find coordinates for this place")
        return
    
    lat, lng = coords
    
    # Check if it's in SF area
    if not (37.6 <= lat <= 37.9 and -122.6 <= lng <= -122.3):
        print(f"⚠️  Warning: This place is outside SF area (lat={lat:.4f}, lng={lng:.4f})")
        confirm = input("Add anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            return
    
    category = input("Category (e.g., Restaurant, Cafe, Store, Park): ").strip()
    notes = input("Notes (optional): ").strip()
    
    # Add to sheet
    worksheet = sheets_client.spreadsheet.worksheet(sheets_client.PLACES_OF_INTEREST_SHEET_NAME)
    worksheet.append_row([name, address or name, lat, lng, category, notes])
    
    print(f"✅ Added '{name}' to Places of Interest!")
    print(f"   Coordinates: {lat:.4f}, {lng:.4f}")

def import_from_google_maps_list(sheets_client):
    """Instructions for importing from Google Maps saved list"""
    print("\n" + "="*70)
    print("IMPORT FROM GOOGLE MAPS SAVED LIST")
    print("="*70)
    print("""
To import places from your Google Maps saved list:

1. Open your Google Maps list: https://maps.app.goo.gl/asoLnkefrso5xq5M9
2. For each place you want to add:
   a. Click on the place
   b. Copy the place name
   c. Copy the address
   d. Use the "Add Place Manually" option in this script

Unfortunately, Google Maps doesn't provide a direct export feature for saved lists.
You'll need to add places one by one, but they'll be saved permanently!

Alternatively, you can:
- Open your Google Sheet: https://docs.google.com/spreadsheets/d/{sheet_id}
- Go to "Places of Interest" tab
- Manually copy/paste:
  * Name
  * Address
  * Latitude (look up on Google Maps)
  * Longitude (look up on Google Maps)
  * Category (optional)
  * Notes (optional)
""")
    
    input("\nPress Enter to continue...")

def list_places(sheets_client):
    """List all places of interest"""
    places = sheets_client.get_places_of_interest()
    
    if not places:
        print("\n❌ No places of interest found (or none in SF area)")
        return
    
    print(f"\n{'='*70}")
    print(f"PLACES OF INTEREST IN SF ({len(places)} total)")
    print(f"{'='*70}")
    
    for i, place in enumerate(places, 1):
        name = place.get('Name', 'Unknown')
        address = place.get('Address', 'N/A')
        category = place.get('Category', 'N/A')
        lat = place.get('Latitude', 'N/A')
        lng = place.get('Longitude', 'N/A')
        
        print(f"\n{i}. {name}")
        print(f"   Address: {address}")
        print(f"   Category: {category}")
        print(f"   Coords: ({lat}, {lng})")

def main():
    print("="*70)
    print("PLACES OF INTEREST SETUP")
    print("="*70)
    
    # Initialize clients
    print("\nInitializing Google Sheets client...")
    sheets_client = GoogleSheetsClient()
    
    print("Initializing Location Analyzer...")
    location_analyzer = LocationAnalyzer()
    
    # Create sheet if needed
    create_sheet_if_needed(sheets_client)
    
    while True:
        print(f"\n{'='*70}")
        print("MENU")
        print(f"{'='*70}")
        print("1. Add a place manually")
        print("2. Import instructions (from Google Maps list)")
        print("3. List all places")
        print("4. Exit")
        
        choice = input("\nChoice (1-4): ").strip()
        
        if choice == '1':
            add_place_manually(sheets_client, location_analyzer)
        elif choice == '2':
            import_from_google_maps_list(sheets_client)
        elif choice == '3':
            list_places(sheets_client)
        elif choice == '4':
            print("\n✓ Done!")
            break
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    main()

