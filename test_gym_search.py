"""
Test script to debug gym search for a specific location
Tests why "Live Fit Gym - Mission" at 780 Valencia St isn't showing up
"""

import os
import sys
import requests
from math import radians, sin, cos, sqrt, atan2

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config

def haversine_distance(lat1, lng1, lat2, lng2):
    """Calculate distance in miles between two coordinates"""
    R = 3959  # Earth radius in miles
    
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def test_gym_search(test_address, target_gym_name, target_gym_address):
    """
    Test gym search from a specific address
    
    Args:
        test_address: Address to search from (e.g., apartment location)
        target_gym_name: Name of gym we're looking for
        target_gym_address: Address of gym we're looking for
    """
    print(f"\n{'='*80}")
    print(f"TESTING GYM SEARCH")
    print(f"{'='*80}")
    print(f"Search from: {test_address}")
    print(f"Looking for: {target_gym_name}")
    print(f"Located at: {target_gym_address}")
    print(f"{'='*80}\n")
    
    # Step 1: Geocode the test address
    print("Step 1: Geocoding test address...")
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    geocode_params = {
        'address': test_address,
        'key': config.GOOGLE_MAPS_API_KEY
    }
    
    response = requests.get(geocode_url, params=geocode_params)
    geocode_data = response.json()
    
    if geocode_data['status'] != 'OK':
        print(f"  ❌ Geocoding failed: {geocode_data['status']}")
        return
    
    location = geocode_data['results'][0]['geometry']['location']
    test_lat, test_lng = location['lat'], location['lng']
    print(f"  ✓ Test location: {test_lat}, {test_lng}")
    
    # Step 2: Geocode the target gym address
    print(f"\nStep 2: Geocoding target gym address...")
    geocode_params['address'] = target_gym_address
    response = requests.get(geocode_url, params=geocode_params)
    gym_geocode_data = response.json()
    
    if gym_geocode_data['status'] != 'OK':
        print(f"  ❌ Gym geocoding failed: {gym_geocode_data['status']}")
        gym_lat, gym_lng = None, None
    else:
        gym_location = gym_geocode_data['results'][0]['geometry']['location']
        gym_lat, gym_lng = gym_location['lat'], gym_location['lng']
        distance = haversine_distance(test_lat, test_lng, gym_lat, gym_lng)
        print(f"  ✓ Target gym location: {gym_lat}, {gym_lng}")
        print(f"  ✓ Distance from test address: {distance:.2f} miles")
    
    # Step 3: Test different search strategies
    print(f"\n{'='*80}")
    print("STRATEGY 1: Nearby Search by Type")
    print(f"{'='*80}")
    
    search_radii = [2, 3, 4, 5]  # miles
    for radius_miles in search_radii:
        radius_meters = int(radius_miles * 1609.34)
        print(f"\n--- Testing radius: {radius_miles} miles ({radius_meters} meters) ---")
        
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{test_lat},{test_lng}",
            'radius': radius_meters,
            'type': 'gym',
            'key': config.GOOGLE_MAPS_API_KEY,
        }
        
        found_in_type_search = False
        page = 1
        all_gyms_this_radius = []
        
        while page <= 3:  # Max 3 pages
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] != 'OK':
                print(f"  Page {page} status: {data['status']}")
                break
            
            gyms = data.get('results', [])
            print(f"  Page {page}: Found {len(gyms)} gyms")
            
            for gym in gyms:
                gym_name = gym.get('name')
                gym_place_id = gym.get('place_id')
                gym_lat_result = gym['geometry']['location']['lat']
                gym_lng_result = gym['geometry']['location']['lng']
                distance = haversine_distance(test_lat, test_lng, gym_lat_result, gym_lng_result)
                
                all_gyms_this_radius.append({
                    'name': gym_name,
                    'distance': distance,
                    'place_id': gym_place_id
                })
                
                # Check if this is our target gym
                if target_gym_name.lower() in gym_name.lower():
                    found_in_type_search = True
                    print(f"  ✓✓✓ FOUND TARGET: {gym_name} at {distance:.2f} mi (place_id: {gym_place_id})")
            
            # Check for next page
            next_page_token = data.get('next_page_token')
            if next_page_token:
                import time
                time.sleep(2)
                params = {'pagetoken': next_page_token, 'key': config.GOOGLE_MAPS_API_KEY}
                page += 1
            else:
                break
        
        # Sort and show closest 10
        all_gyms_this_radius.sort(key=lambda g: g['distance'])
        print(f"\n  Closest 10 gyms in this radius:")
        for i, gym in enumerate(all_gyms_this_radius[:10], 1):
            print(f"    {i}. {gym['name']} - {gym['distance']:.2f} mi")
        print(f"  Total unique gyms found: {len(all_gyms_this_radius)}")
        
        if found_in_type_search:
            print(f"  ✅ TARGET FOUND in type search at {radius_miles} mi radius")
            break
    
    # Strategy 2: Text/Keyword Search
    print(f"\n{'='*80}")
    print("STRATEGY 2: Text/Keyword Search")
    print(f"{'='*80}")
    
    for search_term in ['Live Fit Gym', 'gym', 'fitness center']:
        print(f"\n--- Searching for: '{search_term}' ---")
        
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{test_lat},{test_lng}",
            'radius': int(5 * 1609.34),  # 5 miles
            'keyword': search_term,
            'key': config.GOOGLE_MAPS_API_KEY,
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data['status'] == 'OK':
            gyms = data.get('results', [])
            print(f"  Found {len(gyms)} results")
            
            for gym in gyms[:10]:  # Show first 10
                gym_name = gym.get('name')
                gym_lat_result = gym['geometry']['location']['lat']
                gym_lng_result = gym['geometry']['location']['lng']
                distance = haversine_distance(test_lat, test_lng, gym_lat_result, gym_lng_result)
                
                if target_gym_name.lower() in gym_name.lower():
                    print(f"  ✓✓✓ FOUND TARGET: {gym_name} at {distance:.2f} mi")
                else:
                    print(f"    - {gym_name} - {distance:.2f} mi")
        else:
            print(f"  Status: {data['status']}")
    
    # Strategy 3: Text Search (different API)
    print(f"\n{'='*80}")
    print("STRATEGY 3: Text Search API (finds places by name)")
    print(f"{'='*80}")
    
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        'query': f"{target_gym_name} near {target_gym_address}",
        'key': config.GOOGLE_MAPS_API_KEY,
    }
    
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    
    if data['status'] == 'OK':
        results = data.get('results', [])
        print(f"  Found {len(results)} results for exact gym name")
        
        for result in results:
            name = result.get('name')
            address = result.get('formatted_address')
            place_id = result.get('place_id')
            result_lat = result['geometry']['location']['lat']
            result_lng = result['geometry']['location']['lng']
            distance = haversine_distance(test_lat, test_lng, result_lat, result_lng)
            
            print(f"\n  Result: {name}")
            print(f"    Address: {address}")
            print(f"    Place ID: {place_id}")
            print(f"    Location: {result_lat}, {result_lng}")
            print(f"    Distance from test: {distance:.2f} miles")
            
            if gym_lat and gym_lng:
                distance_from_expected = haversine_distance(gym_lat, gym_lng, result_lat, result_lng)
                print(f"    Distance from expected location: {distance_from_expected:.3f} miles")
    else:
        print(f"  Status: {data['status']}")
    
    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    # Test with the specific gym that's not showing up
    test_gym_search(
        test_address="1617 Noe St, San Francisco, CA 94131",  # Example address in Noe Valley
        target_gym_name="Live Fit Gym - Mission",
        target_gym_address="780 Valencia St, San Francisco, CA 94110"
    )
    
    # You can also test from other addresses
    print("\n\nTesting from Mission District address (closer to gym):")
    test_gym_search(
        test_address="3000 16th St, San Francisco, CA 94103",  # Mission District
        target_gym_name="Live Fit Gym - Mission",
        target_gym_address="780 Valencia St, San Francisco, CA 94110"
    )

