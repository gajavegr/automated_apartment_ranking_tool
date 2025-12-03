#!/usr/bin/env python3
"""
Geocode Missing Places of Interest
Specifically targets places without coordinates and tries multiple strategies
"""

import sys
import time
import requests
from utils.google_sheets import GoogleSheetsClient
import config

def geocode_address(address, api_key):
    """
    Use Geocoding API to convert address to coordinates
    
    Args:
        address: Address string
        api_key: Google Maps API key
        
    Returns:
        Dict with lat, lng, formatted_address or None
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    params = {
        'address': address,
        'key': api_key,
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        if data['status'] != 'OK':
            return None
        
        result = data['results'][0]
        location = result['geometry']['location']
        
        return {
            'lat': location['lat'],
            'lng': location['lng'],
            'address': result['formatted_address']
        }
    
    except Exception as e:
        print(f"  ❌ Geocoding error: {e}")
        return None

def search_place_flexible(place_name, api_key):
    """
    Search for a place using Google Places API with flexible queries
    
    Args:
        place_name: Name of the place
        api_key: Google Maps API key
        
    Returns:
        List of candidate places with name, address, lat, lng
    """
    # Try multiple query variations
    queries = [
        f"{place_name}, San Francisco, CA",
        f"{place_name}, SF Bay Area",
        f"{place_name}, California",
    ]
    
    for query in queries:
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        
        params = {
            'query': query,
            'key': api_key,
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            if data['status'] != 'OK':
                continue
            
            results = data.get('results', [])
            
            # Collect all candidates (expanded SF area)
            candidates = []
            for result in results[:10]:  # Top 10 results
                location = result['geometry']['location']
                lat = location['lat']
                lng = location['lng']
                
                # Expanded Bay Area bounding box
                if 37.0 <= lat <= 38.5 and -123.0 <= lng <= -121.5:
                    candidates.append({
                        'name': result.get('name'),
                        'address': result.get('formatted_address'),
                        'lat': lat,
                        'lng': lng,
                        'place_id': result.get('place_id'),
                        'types': result.get('types', []),
                        'rating': result.get('rating', 'N/A'),
                    })
            
            if candidates:
                return candidates
        
        except Exception as e:
            print(f"  ⚠️  Error with query '{query}': {e}")
            continue
    
    return []

def update_sheet_row(worksheet, row_num, address, lat, lng, address_idx, lat_idx, lng_idx):
    """Update a single row in the sheet with geocoded data"""
    def col_num_to_letter(n):
        result = ""
        while n >= 0:
            result = chr(65 + (n % 26)) + result
            n = n // 26 - 1
        return result
    
    address_col = col_num_to_letter(address_idx)
    lat_col = col_num_to_letter(lat_idx)
    lng_col = col_num_to_letter(lng_idx)
    
    # Batch update
    update_data = [
        {
            'range': f'{address_col}{row_num}',
            'values': [[address]]
        },
        {
            'range': f'{lat_col}{row_num}',
            'values': [[lat]]
        },
        {
            'range': f'{lng_col}{row_num}',
            'values': [[lng]]
        }
    ]
    
    worksheet.batch_update(update_data)

def main():
    print("="*80)
    print("GEOCODE MISSING PLACES OF INTEREST")
    print("="*80)
    
    # Initialize
    print("\nInitializing Google Sheets client...")
    sheets_client = GoogleSheetsClient()
    
    api_key = config.GOOGLE_MAPS_API_KEY
    if not api_key:
        print("❌ GOOGLE_MAPS_API_KEY not set in config")
        sys.exit(1)
    
    # Get the worksheet
    try:
        worksheet = sheets_client.spreadsheet.worksheet(sheets_client.PLACES_OF_INTEREST_SHEET_NAME)
    except:
        print(f"❌ Sheet '{sheets_client.PLACES_OF_INTEREST_SHEET_NAME}' not found")
        sys.exit(1)
    
    # Get all data
    all_data = worksheet.get_all_values()
    
    if len(all_data) < 2:
        print("❌ No data found in sheet")
        sys.exit(1)
    
    headers = all_data[0]
    rows = all_data[1:]
    
    # Find column indices
    try:
        name_idx = headers.index('Name')
        address_idx = headers.index('Address')
        lat_idx = headers.index('Latitude')
        lng_idx = headers.index('Longitude')
    except ValueError as e:
        print(f"❌ Required column not found: {e}")
        sys.exit(1)
    
    # Find rows missing coordinates
    missing_coords = []
    for i, row in enumerate(rows):
        row_num = i + 2  # +2 for 1-indexed and header
        
        # Ensure row has enough columns
        while len(row) < max(name_idx, address_idx, lat_idx, lng_idx) + 1:
            row.append('')
        
        place_name = row[name_idx].strip()
        current_address = row[address_idx].strip() if address_idx < len(row) else ''
        current_lat = row[lat_idx].strip() if lat_idx < len(row) else ''
        current_lng = row[lng_idx].strip() if lng_idx < len(row) else ''
        
        if not place_name:
            continue
        
        # Missing coordinates
        if not current_lat or not current_lng:
            missing_coords.append({
                'row_num': row_num,
                'name': place_name,
                'address': current_address,
            })
    
    total_missing = len(missing_coords)
    
    if total_missing == 0:
        print("\n✅ All places already have coordinates!")
        sys.exit(0)
    
    print(f"\nFound {total_missing} place(s) without coordinates\n")
    print("Strategy:")
    print("  1. If address exists → Use Geocoding API")
    print("  2. If no address → Search with Places API")
    print("  3. Auto-select first result in SF area")
    print("  4. Skip if no matches found\n")
    
    input("Press Enter to start geocoding... (Ctrl+C to cancel)")
    print()
    
    updated = 0
    skipped = 0
    
    for i, place_info in enumerate(missing_coords, 1):
        row_num = place_info['row_num']
        place_name = place_info['name']
        existing_address = place_info['address']
        
        print(f"[{i}/{total_missing}] 🔍 {place_name}")
        
        result = None
        
        # Strategy 1: Use existing address if available
        if existing_address:
            print(f"  ℹ️  Using existing address: {existing_address}")
            result = geocode_address(existing_address, api_key)
            
            if result:
                print(f"  ✓ Geocoded to: {result['lat']:.4f}, {result['lng']:.4f}")
            else:
                print(f"  ⚠️  Failed to geocode address, trying place search...")
        
        # Strategy 2: Search for place if no address or geocoding failed
        if not result:
            candidates = search_place_flexible(place_name, api_key)
            
            if not candidates:
                print(f"  ❌ No matches found - SKIPPING")
                skipped += 1
                time.sleep(0.5)
                continue
            
            # Auto-select first SF result
            sf_candidates = [c for c in candidates if 37.6 <= c['lat'] <= 37.9 and -122.6 <= c['lng'] <= -122.3]
            
            if sf_candidates:
                result = sf_candidates[0]
                print(f"  ✓ Auto-selected (SF): {result['name']}")
                print(f"     {result['address']}")
                print(f"     {result['lat']:.4f}, {result['lng']:.4f}")
            else:
                # Use first result from expanded area
                result = candidates[0]
                print(f"  ⚠️  Auto-selected (outside SF): {result['name']}")
                print(f"     {result['address']}")
                print(f"     {result['lat']:.4f}, {result['lng']:.4f}")
        
        # Update sheet
        if result:
            try:
                update_sheet_row(
                    worksheet, row_num,
                    result['address'], result['lat'], result['lng'],
                    address_idx, lat_idx, lng_idx
                )
                print(f"  ✅ Updated row {row_num}")
                updated += 1
            except Exception as e:
                print(f"  ❌ Error updating sheet: {e}")
                skipped += 1
        
        # Rate limit
        time.sleep(0.5)
        print()
    
    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total missing: {total_missing}")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print()
    
    if updated > 0:
        print(f"✅ Successfully geocoded {updated} place(s)!")
        print(f"\nNext: Run 'python main.py' to re-analyze apartments with complete POI data")
    else:
        print("ℹ️  No places were updated")

if __name__ == "__main__":
    main()

