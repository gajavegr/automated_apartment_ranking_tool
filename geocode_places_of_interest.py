#!/usr/bin/env python3
"""
Geocode Places of Interest
Reads place names from the sheet and fills in addresses/coordinates using Google Places API
"""

import sys
import time
import requests
from utils.google_sheets import GoogleSheetsClient
import config

def search_place(place_name, api_key):
    """
    Search for a place using Google Places API Text Search
    
    Args:
        place_name: Name of the place
        api_key: Google Maps API key
        
    Returns:
        List of candidate places with name, address, lat, lng
    """
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    
    # Add "San Francisco" to narrow down results
    query = f"{place_name}, San Francisco, CA"
    
    params = {
        'query': query,
        'key': api_key,
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        if data['status'] != 'OK':
            print(f"  ⚠️  API returned status: {data['status']}")
            return []
        
        results = data.get('results', [])
        
        # Filter to SF area only
        candidates = []
        for result in results:
            location = result['geometry']['location']
            lat = location['lat']
            lng = location['lng']
            
            # SF bounding box
            if 37.6 <= lat <= 37.9 and -122.6 <= lng <= -122.3:
                candidates.append({
                    'name': result.get('name'),
                    'address': result.get('formatted_address'),
                    'lat': lat,
                    'lng': lng,
                    'place_id': result.get('place_id'),
                    'types': result.get('types', []),
                    'rating': result.get('rating', 'N/A'),
                })
        
        return candidates
    
    except Exception as e:
        print(f"  ❌ Error searching for place: {e}")
        return []

def select_from_candidates(place_name, candidates):
    """
    Show user a menu to select the correct place(s) from candidates
    
    Args:
        place_name: Original place name
        candidates: List of candidate places
        
    Returns:
        List of selected candidate dicts (can be empty, one, or multiple)
    """
    if not candidates:
        return []
    
    if len(candidates) == 1:
        # Only one result, use it automatically
        print(f"  ✓ Found exactly 1 match: {candidates[0]['address']}")
        return [candidates[0]]
    
    # Multiple results - ask user to choose
    print(f"\n  Found {len(candidates)} matches for '{place_name}':")
    print(f"  {'='*70}")
    
    for i, candidate in enumerate(candidates, 1):
        print(f"\n  {i}. {candidate['name']}")
        print(f"     Address: {candidate['address']}")
        print(f"     Rating: {candidate['rating']}")
        print(f"     Types: {', '.join(candidate['types'][:3])}")
    
    print(f"\n  0. Skip (none of these match)")
    print(f"  {'='*70}")
    print(f"  💡 TIP: You can select multiple by typing space-delimited numbers (e.g., '1 3 5')")
    
    while True:
        try:
            choice = input(f"\n  Select match(es) (0 or 1-{len(candidates)}): ").strip()
            
            if choice == '0':
                print(f"  ⏭️  Skipped")
                return []
            
            # Parse space-delimited choices
            choice_nums = [int(c) for c in choice.split()]
            
            # Validate all choices
            invalid = [c for c in choice_nums if c < 1 or c > len(candidates)]
            if invalid:
                print(f"  ❌ Invalid choice(s): {invalid}. Enter numbers 1-{len(candidates)}")
                continue
            
            # Get selected candidates
            selected = [candidates[c - 1] for c in choice_nums]
            
            if len(selected) == 1:
                print(f"  ✓ Selected: {selected[0]['address']}")
            else:
                print(f"  ✓ Selected {len(selected)} locations:")
                for sel in selected:
                    print(f"    • {sel['address']}")
            
            return selected
            
        except ValueError:
            print(f"  ❌ Invalid input. Enter number(s) between 0 and {len(candidates)}")
        except KeyboardInterrupt:
            print("\n\n  ⚠️  Interrupted by user")
            sys.exit(0)

def main():
    print("="*70)
    print("GEOCODE PLACES OF INTEREST")
    print("="*70)
    
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
        print("   Run setup_places_of_interest.py first to create it")
        sys.exit(1)
    
    # Get all data
    all_data = worksheet.get_all_values()
    
    if len(all_data) < 2:
        print("❌ No data found in sheet (only headers or empty)")
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
        print(f"   Expected columns: Name, Address, Latitude, Longitude")
        sys.exit(1)
    
    # Process each row
    total_rows = len(rows)
    processed = 0
    skipped = 0
    updated = 0
    
    print(f"\nProcessing {total_rows} place(s)...\n")
    
    for i, row in enumerate(rows):
        row_num = i + 2  # +2 for 1-indexed and header row
        
        # Ensure row has enough columns
        while len(row) < max(name_idx, address_idx, lat_idx, lng_idx) + 1:
            row.append('')
        
        place_name = row[name_idx].strip()
        current_lat = row[lat_idx].strip() if lat_idx < len(row) else ''
        current_lng = row[lng_idx].strip() if lng_idx < len(row) else ''
        
        if not place_name:
            skipped += 1
            continue
        
        # Skip if already has coordinates
        if current_lat and current_lng:
            processed += 1
            print(f"[{processed}/{total_rows}] ✓ {place_name} - Already has coordinates")
            continue
        
        processed += 1
        print(f"[{processed}/{total_rows}] 🔍 Searching for: {place_name}")
        
        # Search for the place
        candidates = search_place(place_name, api_key)
        
        if not candidates:
            print(f"  ❌ No matches found in SF area")
            skipped += 1
            continue
        
        # Let user select (can be multiple)
        selected_list = select_from_candidates(place_name, candidates)
        
        if not selected_list:
            skipped += 1
            continue
        
        # Update the sheet for each selected location
        for idx, selected in enumerate(selected_list):
            try:
                # For the first selection, update the current row
                # For additional selections, insert new rows
                if idx == 0:
                    # Update existing row
                    target_row_num = row_num
                else:
                    # Insert new row after current row
                    worksheet.insert_row([''] * len(headers), row_num + idx)
                    target_row_num = row_num + idx
                    # Copy the place name to the new row
                    name_col = col_num_to_letter(name_idx)
                    worksheet.update(f'{name_col}{target_row_num}', [[place_name]])
                
                # Convert column indices to letters
                def col_num_to_letter(n):
                    result = ""
                    while n >= 0:
                        result = chr(65 + (n % 26)) + result
                        n = n // 26 - 1
                    return result
                
                address_col = col_num_to_letter(address_idx)
                lat_col = col_num_to_letter(lat_idx)
                lng_col = col_num_to_letter(lng_idx)
                
                # Batch update for efficiency
                update_data = [
                    {
                        'range': f'{address_col}{target_row_num}',
                        'values': [[selected['address']]]
                    },
                    {
                        'range': f'{lat_col}{target_row_num}',
                        'values': [[selected['lat']]]
                    },
                    {
                        'range': f'{lng_col}{target_row_num}',
                        'values': [[selected['lng']]]
                    }
                ]
                
                worksheet.batch_update(update_data)
                updated += 1
                
                if idx == 0:
                    print(f"  ✅ Updated row {target_row_num} with: {selected['lat']:.4f}, {selected['lng']:.4f}")
                else:
                    print(f"  ✅ Added new row {target_row_num} for branch #{idx+1}: {selected['lat']:.4f}, {selected['lng']:.4f}")
                
            except Exception as e:
                print(f"  ❌ Error updating sheet: {e}")
                skipped += 1
        
        # Rate limit
        time.sleep(0.5)
        print()
    
    # Summary
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total places: {total_rows}")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Already had coordinates: {total_rows - processed}")
    print()
    
    if updated > 0:
        print(f"✅ Successfully geocoded {updated} place(s)!")
        print(f"\nNext steps:")
        print(f"1. Open your Google Sheet to verify the data")
        print(f"2. Run 'python main.py' to analyze apartments with POI data")
    else:
        print("ℹ️  No places were updated")

if __name__ == "__main__":
    main()

