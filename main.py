#!/usr/bin/env python3
"""
Apartment Value Analyzer - Main Orchestrator

Analyzes apartment listings from a Google Sheet using web scraping,
computer vision, and location APIs.
"""

import sys
import argparse
import json
from typing import List, Dict, Any
from datetime import datetime
import traceback

from tqdm import tqdm

import config
from utils.google_sheets import GoogleSheetsClient
from utils.cache import get_cache
from analyzers.vision_analyzer import VisionAnalyzer
from analyzers.location_analyzer import LocationAnalyzer
from analyzers.scoring_engine import build_scorecard


class ApartmentAnalyzer:
    """Main orchestrator for apartment analysis"""
    
    def __init__(self):
        """Initialize all components"""
        print("Initializing Apartment Analyzer...")
        
        try:
            self.sheets_client = GoogleSheetsClient()
            self.vision_analyzer = VisionAnalyzer()
            self.location_analyzer = LocationAnalyzer(sheets_client=self.sheets_client)
            self.cache = get_cache()
            
            print("✓ All components initialized successfully")
        except Exception as e:
            print(f"✗ Error initializing components: {e}")
            print("\nPlease check:")
            print("1. Google Sheets credentials are in place")
            print("2. API keys are set in .env file")
            print("3. All dependencies are installed")
            raise
    
    def analyze_apartment(self, row_data: Dict[str, Any], force_refresh: bool = False, 
                         components_to_recalc: List[str] = None) -> Dict[str, Any]:
        """
        Analyze a single apartment
        
        Args:
            row_data: Row data from Google Sheets (must include basic info)
            force_refresh: Force re-analysis even if cached
            components_to_recalc: List of components to recalculate (None = all)
                                 Options: 'gym', 'commute', 'safety', 'happening', 'wfh'
            
        Returns:
            Dictionary with all analysis results
        """
        address = row_data.get(config.SHEET_COLUMNS["address"], "").strip()
        manual_safety = row_data.get(config.SHEET_COLUMNS["manual_safety"], 5.0)
        
        if not address:
            return {'error': 'No address provided'}
        
        # Determine what to analyze
        recalc_all = components_to_recalc is None or 'all' in (components_to_recalc or [])
        recalc_commute = recalc_all or 'commute' in components_to_recalc
        recalc_safety = recalc_all or 'safety' in components_to_recalc
        recalc_happening = recalc_all or 'happening' in components_to_recalc
        recalc_gym = recalc_all or 'gym' in components_to_recalc
        recalc_wfh = recalc_all or 'wfh' in components_to_recalc
        recalc_space_luxury = recalc_all or 'space_luxury' in components_to_recalc
        recalc_sheet_only = 'sheet_only' in (components_to_recalc or [])
        
        # Sheet-only: recompute scores from the latest sheet data without any external API calls
        if recalc_sheet_only:
            recalc_commute = False
            recalc_safety = False
            recalc_happening = False
            recalc_gym = False
            recalc_wfh = False
            recalc_space_luxury = True  # Safe to recompute based on sheet values
        
        # Note: space_luxury doesn't need special handling - it's always calculated from existing data
        
        # Debug logging
        print(f"\n  Recalc flags:")
        print(f"    recalc_all: {recalc_all}")
        print(f"    recalc_commute: {recalc_commute}")
        print(f"    recalc_safety: {recalc_safety}")
        print(f"    recalc_happening: {recalc_happening}")
        print(f"    recalc_gym: {recalc_gym}")
        print(f"    recalc_wfh: {recalc_wfh}")
        print(f"    recalc_space_luxury: {recalc_space_luxury}")
        print(f"    recalc_sheet_only: {recalc_sheet_only}")
        
        if components_to_recalc:
            print(f"\n{'='*80}")
            print(f"Analyzing: {address}")
            print(f"Components to recalculate: {', '.join(components_to_recalc)}")
            print(f"{'='*80}")
        else:
            print(f"\n{'='*80}")
            print(f"Analyzing: {address}")
            print(f"{'='*80}")
        
        result = {}
        
        try:
            # Get basic info from sheet (manually entered via web interface)
            result['address'] = address
            result['price'] = row_data.get(config.SHEET_COLUMNS["price"], 0)
            result['bedrooms'] = row_data.get(config.SHEET_COLUMNS["bedrooms"], 0)
            result['bathrooms'] = row_data.get(config.SHEET_COLUMNS["bathrooms"], 0)
            result['sqft'] = row_data.get(config.SHEET_COLUMNS["sqft"], 0)
            result['parking_type'] = row_data.get(config.SHEET_COLUMNS["parking_type"], 'none')
            result['parking_enclosure'] = row_data.get(config.SHEET_COLUMNS["parking_enclosure"], '')
            result['laundry_type'] = row_data.get(config.SHEET_COLUMNS["laundry_type"], 'none')
            result['rent_control'] = row_data.get(config.SHEET_COLUMNS["rent_control"], False)
            result['neighborhood'] = row_data.get(config.SHEET_COLUMNS["neighborhood"], '')
            result['selected_gyms'] = row_data.get(config.SHEET_COLUMNS["selected_gyms"], '')
            
            print(f"\n[1/3] Basic Info (from manual entry):")
            print(f"  Address: {result['address']}")
            print(f"  Price: ${result['price']}/mo | {result['bedrooms']}bd/{result['bathrooms']}ba | {result['sqft']} sqft")
            parking_info = result['parking_type']
            if result.get('parking_enclosure'):
                parking_info += f" ({result['parking_enclosure']})"
            print(f"  Parking: {parking_info}")
            print(f"  Laundry: {result['laundry_type']}")
            
            # Note: We skip photo analysis for manually entered apartments
            # If photos are needed, they can be manually uploaded and analyzed separately
            print(f"\n[2/3] Skipping photo analysis (manual entry mode)")
            
            # Preserve manually entered WFH/visual fields - DO NOT overwrite with None!
            # Only set to None if they don't already exist in the row data
            result['natural_light'] = row_data.get(config.SHEET_COLUMNS.get("natural_light"))
            result['desk_space_quality'] = row_data.get(config.SHEET_COLUMNS.get("desk_space_quality"))
            result['kitchen_quality'] = row_data.get(config.SHEET_COLUMNS.get("kitchen_quality"))
            result['view_quality'] = row_data.get(config.SHEET_COLUMNS.get("view_quality"))
            result['floor_level'] = row_data.get(config.SHEET_COLUMNS.get("floor_level"))
            result['double_pane_windows'] = row_data.get(config.SHEET_COLUMNS.get("double_pane_windows"))
            result['study_door_type'] = row_data.get(config.SHEET_COLUMNS.get("study_door_type"))
            result['street_noise_level'] = row_data.get(config.SHEET_COLUMNS.get("street_noise_level"))
            
            # Also preserve parking ease fields - these are manually entered
            if config.SHEET_COLUMNS.get("visitor_parking_ease") in row_data:
                result['visitor_parking_ease'] = row_data.get(config.SHEET_COLUMNS.get("visitor_parking_ease"))
            if config.SHEET_COLUMNS.get("street_parking_ease") in row_data:
                result['street_parking_ease'] = row_data.get(config.SHEET_COLUMNS.get("street_parking_ease"))
            
            # Analyze location
            if recalc_sheet_only:
                print(f"\n[3/3] Skipping external API calls (sheet-only recalc)")
                result['latitude'] = row_data.get(config.SHEET_COLUMNS.get("latitude"))
                result['longitude'] = row_data.get(config.SHEET_COLUMNS.get("longitude"))
                result['apartment_elevation'] = row_data.get(config.SHEET_COLUMNS.get("apartment_elevation"))
                result['commute_duration'] = row_data.get(config.SHEET_COLUMNS.get("commute_time_you"))
                result['commute_route'] = row_data.get(config.SHEET_COLUMNS.get("commute_route"))
                result['commute_duration_partner'] = row_data.get(config.SHEET_COLUMNS.get("commute_time_partner"))
                result['commute_details'] = row_data.get(config.SHEET_COLUMNS.get("commute_details"))
                result['commute_details_json'] = row_data.get(config.SHEET_COLUMNS.get("commute_details_json"))
                result['safety_score_opendata'] = row_data.get(config.SHEET_COLUMNS.get("safety_score_opendata"))
                result['incident_count'] = row_data.get(config.SHEET_COLUMNS.get("incident_count"))
                result['avg_severity'] = row_data.get(config.SHEET_COLUMNS.get("avg_severity"))
                result['count_score'] = row_data.get(config.SHEET_COLUMNS.get("count_score"))
                result['severity_score'] = row_data.get(config.SHEET_COLUMNS.get("severity_score"))
                result['crime_details'] = row_data.get(config.SHEET_COLUMNS.get("crime_details"))
                result['restaurants_nearby'] = row_data.get(config.SHEET_COLUMNS.get("restaurants_nearby"))
                result['cafes_nearby'] = row_data.get(config.SHEET_COLUMNS.get("cafes_nearby"))
                result['parks_nearby'] = row_data.get(config.SHEET_COLUMNS.get("parks_nearby"))
                result['restaurants_list'] = row_data.get(config.SHEET_COLUMNS.get("restaurants_list"), "[]")
                result['cafes_list'] = row_data.get(config.SHEET_COLUMNS.get("cafes_list"), "[]")
                result['parks_list'] = row_data.get(config.SHEET_COLUMNS.get("parks_list"), "[]")
                result['avg_walk_to_poi_mins'] = row_data.get(config.SHEET_COLUMNS.get("avg_walk_to_poi_mins"))
                result['nearest_poi_count'] = row_data.get(config.SHEET_COLUMNS.get("nearest_poi_count"))
                result['pois_within_1_mile'] = row_data.get(config.SHEET_COLUMNS.get("pois_within_1_mile"))
                result['pois_list'] = row_data.get(config.SHEET_COLUMNS.get("pois_list"))
                result['gym_within_10min'] = row_data.get(config.SHEET_COLUMNS.get("gym_within_10min"))
                result['gym_quality'] = row_data.get(config.SHEET_COLUMNS.get("gym_quality"))
                result['nearest_gym_name'] = row_data.get(config.SHEET_COLUMNS.get("nearest_gym_name"))
                result['nearest_gym_distance'] = row_data.get(config.SHEET_COLUMNS.get("nearest_gym_distance"))
                result['elevation_to_gym'] = row_data.get(config.SHEET_COLUMNS.get("elevation_to_gym"))
            else:
                print(f"\n[3/3] Analyzing location...")
                if result['address']:
                    # Only run full location analysis if we need commute or safety data
                    if recalc_commute or recalc_safety:
                        location_data = self.location_analyzer.analyze_location(
                            result['address'],
                            analyze_commute=recalc_commute,
                            analyze_safety=recalc_safety,
                            analyze_amenities=False  # We handle amenities separately in the happening block
                        )
                        
                        if recalc_commute:
                            result['commute_duration'] = location_data.get('commute_duration', 999)
                            result['commute_route'] = location_data.get('commute_route', '')
                            result['commute_duration_partner'] = location_data.get('commute_duration_partner', 999)
                            result['route_annoyingness'] = location_data.get('route_annoyingness', 10.0)
                            commute_details = location_data.get('commute_details', {})
                            result['commute_details'] = commute_details
                            result['commute_details_json'] = json.dumps(commute_details) if commute_details else ""
                        else:
                            # Preserve existing commute data
                            result['commute_duration'] = row_data.get(config.SHEET_COLUMNS["commute_time_you"])
                            result['commute_route'] = row_data.get(config.SHEET_COLUMNS["commute_route"], '')
                            result['commute_duration_partner'] = row_data.get(config.SHEET_COLUMNS["commute_time_partner"])
                            result['commute_details'] = row_data.get(config.SHEET_COLUMNS.get("commute_details"))
                            result['commute_details_json'] = row_data.get(config.SHEET_COLUMNS.get("commute_details_json"), "")
                        
                        if recalc_safety:
                            result['safety_score_opendata'] = location_data.get('safety_score_opendata', 5.0)
                            result['incident_count'] = location_data.get('incident_count', 0)
                            result['avg_severity'] = location_data.get('avg_severity')
                            result['count_score'] = location_data.get('count_score')
                            result['severity_score'] = location_data.get('severity_score')
                            crime_details = location_data.get('crime_details')
                            if crime_details:
                                result['crime_details'] = crime_details
                        else:
                            # Preserve existing safety data
                            result['safety_score_opendata'] = row_data.get(config.SHEET_COLUMNS["safety_score_opendata"])
                            result['incident_count'] = row_data.get(config.SHEET_COLUMNS.get("incident_count"))
                            result['avg_severity'] = row_data.get(config.SHEET_COLUMNS.get("avg_severity"))
                            result['count_score'] = row_data.get(config.SHEET_COLUMNS.get("count_score"))
                            result['severity_score'] = row_data.get(config.SHEET_COLUMNS.get("severity_score"))
                            result['crime_details'] = row_data.get(config.SHEET_COLUMNS.get("crime_details"))
                        
                        # Get latitude/longitude for other calculations
                        result['latitude'] = location_data.get('latitude')
                        result['longitude'] = location_data.get('longitude')
                        result['apartment_elevation'] = location_data.get('apartment_elevation')
                    else:
                        # Just get coordinates without full analysis
                        coords = self.location_analyzer.geocode_address(result['address'])
                        if coords:
                            result['latitude'] = coords[0]
                            result['longitude'] = coords[1]
                            result['apartment_elevation'] = self.location_analyzer.get_elevation(coords[0], coords[1])
                        
                        # Preserve existing data
                        result['commute_duration'] = row_data.get(config.SHEET_COLUMNS["commute_time_you"])
                        result['commute_route'] = row_data.get(config.SHEET_COLUMNS["commute_route"], '')
                        result['commute_duration_partner'] = row_data.get(config.SHEET_COLUMNS["commute_time_partner"])
                        result['commute_details'] = row_data.get(config.SHEET_COLUMNS.get("commute_details"))
                        result['commute_details_json'] = row_data.get(config.SHEET_COLUMNS.get("commute_details_json"))
                        result['safety_score_opendata'] = row_data.get(config.SHEET_COLUMNS["safety_score_opendata"])
                        result['incident_count'] = row_data.get(config.SHEET_COLUMNS.get("incident_count"))
                        result['avg_severity'] = row_data.get(config.SHEET_COLUMNS.get("avg_severity"))
                        result['count_score'] = row_data.get(config.SHEET_COLUMNS.get("count_score"))
                        result['severity_score'] = row_data.get(config.SHEET_COLUMNS.get("severity_score"))
                        result['crime_details'] = row_data.get(config.SHEET_COLUMNS.get("crime_details"))
                
                # Happening score - restaurants, cafes, parks
                if recalc_happening:
                    # Get Places of Interest first (to pass names to amenities search)
                    print("📍 Calculating distance to personal places of interest...")
                    places_of_interest = self.sheets_client.get_places_of_interest()
                    poi_names = [place.get('Name', '') for place in places_of_interest] if places_of_interest else []
                    
                    # Get detailed amenity lists (for UI display and exclusion)
                    # Pass POI names to skip Claude verification for places already in your curated list
                    amenities_detailed = self.location_analyzer.get_nearby_amenities(
                        result['latitude'], 
                        result['longitude'],
                        return_details=True,
                        poi_names=poi_names
                    )
                    
                    result['restaurants_nearby'] = len(amenities_detailed.get('restaurants', []))
                    result['cafes_nearby'] = len(amenities_detailed.get('cafes', []))
                    result['parks_nearby'] = len(amenities_detailed.get('parks', []))
                    
                    # Store detailed lists as JSON
                    result['restaurants_list'] = json.dumps(amenities_detailed.get('restaurants', []))
                    result['cafes_list'] = json.dumps(amenities_detailed.get('cafes', []))
                    result['parks_list'] = json.dumps(amenities_detailed.get('parks', []))
                else:
                    # Preserve existing happening data
                    result['restaurants_nearby'] = row_data.get(config.SHEET_COLUMNS.get("restaurants_nearby"))
                    result['cafes_nearby'] = row_data.get(config.SHEET_COLUMNS.get("cafes_nearby"))
                    result['parks_nearby'] = row_data.get(config.SHEET_COLUMNS.get("parks_nearby"))
                    result['restaurants_list'] = row_data.get(config.SHEET_COLUMNS.get("restaurants_list"), "[]")
                    result['cafes_list'] = row_data.get(config.SHEET_COLUMNS.get("cafes_list"), "[]")
                    result['parks_list'] = row_data.get(config.SHEET_COLUMNS.get("parks_list"), "[]")
                
                # Calculate average walking time to places of interest
                # (Only if recalculating happening score)
                if recalc_happening:
                    places_of_interest = self.sheets_client.get_places_of_interest()
                    if places_of_interest:
                        apartment_coords = self.location_analyzer.geocode_address(result.get('address'))
                        if apartment_coords:
                            poi_data = self.location_analyzer.get_avg_walk_time_to_places_of_interest(
                                apartment_coords[0], apartment_coords[1], places_of_interest
                            )
                            result['avg_walk_to_poi_mins'] = poi_data['avg_walk_time_mins']
                            result['nearest_poi_count'] = poi_data['count']
                            
                            # Count POIs within 1 mile
                            pois_within_mile = 0
                            for place in places_of_interest:
                                try:
                                    place_lat = float(place.get('Latitude'))
                                    place_lng = float(place.get('Longitude'))
                                    distance_miles = self.location_analyzer._calculate_distance(
                                        apartment_coords[0], apartment_coords[1],
                                        place_lat, place_lng
                                    )
                                    if distance_miles <= 1.0:
                                        pois_within_mile += 1
                                except (ValueError, TypeError):
                                    continue
                            result['pois_within_1_mile'] = pois_within_mile
                            
                            # Store POI list as JSON for UI display
                            result['pois_list'] = json.dumps(poi_data['nearest_places'])
                            
                            if poi_data['nearest_places']:
                                print(f"  ✓ Top {poi_data['count']} nearest places (avg: {poi_data['avg_walk_time_mins']:.1f} min):")
                                for place in poi_data['nearest_places']:
                                    print(f"    • {place['name']}: {place['walk_time_mins']:.1f} min")
                                print(f"  ✓ POIs within 1 mile: {pois_within_mile}")
                            else:
                                print(f"  ⚠️  No walking times calculated for places of interest")
                        else:
                            print(f"  ⚠️  Could not geocode apartment for POI calculation")
                            result['avg_walk_to_poi_mins'] = None
                            result['nearest_poi_count'] = 0
                            result['pois_within_1_mile'] = 0
                            result['pois_list'] = json.dumps([])
                    else:
                        print(f"  ℹ️  No places of interest configured")
                        result['avg_walk_to_poi_mins'] = None
                        result['nearest_poi_count'] = 0
                        result['pois_within_1_mile'] = 0
                        result['pois_list'] = json.dumps([])
                else:
                    # Preserve existing POI data
                    result['avg_walk_to_poi_mins'] = row_data.get(config.SHEET_COLUMNS.get("avg_walk_to_poi_mins"))
                    result['nearest_poi_count'] = row_data.get(config.SHEET_COLUMNS.get("nearest_poi_count"))
                    result['pois_within_1_mile'] = row_data.get(config.SHEET_COLUMNS.get("pois_within_1_mile"))
                    result['pois_list'] = row_data.get(config.SHEET_COLUMNS.get("pois_list"), "[]")
                
                # Gym calculation - only if recalculating gym score
                if recalc_gym:
                    # Check if user has pre-selected gyms
                    selected_gyms_str = result.get('selected_gyms', '').strip()
                    print(f"  Selected gyms from sheet: '{selected_gyms_str}'")
                    
                    if selected_gyms_str:
                        # User has pre-selected gyms - calculate score based on nearest one
                        print(f"  → Processing {len(selected_gyms_str.split(','))} selected gym(s)")
                        selected_gym_names = [name.strip() for name in selected_gyms_str.split(',')]
                        
                        # Get approved gyms sheet to find coordinates
                        approved_gyms = self.sheets_client.get_approved_gyms()
                        print(f"  Found {len(approved_gyms)} approved gyms in sheet")
                        
                        # Get apartment coordinates
                        apartment_address = result.get('address')
                        apartment_coords = self.location_analyzer.geocode_address(apartment_address)
                        
                        if not apartment_coords:
                            print(f"  ⚠️  Could not geocode apartment address: {apartment_address}")
                            result['gym_within_10min'] = False
                            result['gym_walk_time_mins'] = None
                            result['gym_bike_time_mins'] = None
                            result['gym_transport_mode'] = None
                            result['gym_effective_time_mins'] = None
                        else:
                            apartment_lat, apartment_lng = apartment_coords
                            
                            # Build list of selected gyms with their coordinates
                            selected_gyms_data = []
                            for gym in approved_gyms:
                                gym_name = gym.get('Gym Name', '').strip()
                                if gym_name in selected_gym_names:
                                    # Try to get coords from sheet (Latitude/Longitude columns)
                                    gym_lat = gym.get('Latitude')
                                    gym_lng = gym.get('Longitude')
                                    
                                    # If not in sheet, geocode the address
                                    if not gym_lat or not gym_lng:
                                        gym_address = gym.get('Address')
                                        if gym_address:
                                            gym_coords = self.location_analyzer.geocode_address(gym_address)
                                            if gym_coords:
                                                gym_lat, gym_lng = gym_coords
                                    
                                    if gym_lat and gym_lng:
                                        try:
                                            # Convert to float if stored as string
                                            gym_lat = float(gym_lat)
                                            gym_lng = float(gym_lng)
                                            selected_gyms_data.append({
                                                'name': gym_name,
                                                'lat': gym_lat,
                                                'lng': gym_lng,
                                                'rating': gym.get('Rating', 'N/A')
                                            })
                                        except (ValueError, TypeError):
                                            print(f"    ⚠️  Invalid coordinates for {gym_name}: lat={gym_lat}, lng={gym_lng}")
                                    else:
                                        print(f"    ⚠️  No coordinates found for {gym_name}")
                            
                            if not selected_gyms_data:
                                print(f"  ⚠️  Could not find coordinates for any selected gyms")
                                result['gym_within_10min'] = False
                                result['gym_walk_time_mins'] = None
                                result['gym_bike_time_mins'] = None
                                result['gym_transport_mode'] = None
                                result['gym_effective_time_mins'] = None
                            else:
                                # Calculate walking times to all selected gyms
                                gym_coords_list = [(gym['lat'], gym['lng']) for gym in selected_gyms_data]
                                walking_times = self.location_analyzer._get_walking_times(
                                    apartment_lat, 
                                    apartment_lng, 
                                    gym_coords_list
                                )
                                
                                # Find nearest gym by walk time
                                min_walk_time = float('inf')
                                nearest_gym = None
                                nearest_gym_idx = None
                                
                                for i, gym_data in enumerate(selected_gyms_data):
                                    walk_time_data = walking_times[i]
                                    walk_time = walk_time_data.get('duration_mins')
                                    
                                    if walk_time is not None:
                                        print(f"    {gym_data['name']}: {walk_time} min walk")
                                        if walk_time < min_walk_time:
                                            min_walk_time = walk_time
                                            nearest_gym = gym_data
                                            nearest_gym_idx = i
                                    else:
                                        print(f"    ⚠️  {gym_data['name']}: Could not calculate walk time")
                                
                                if nearest_gym and min_walk_time != float('inf'):
                                    # Check if walking time is >15 min - if so, also calculate biking time
                                    bike_time = None
                                    transport_mode = 'walk'
                                    effective_time = min_walk_time
                                    
                                    if min_walk_time > 15.0:
                                        print(f"  → Gym is >{config.GYM_BIKE_THRESHOLD_MINS} min walk, calculating biking time...")
                                        biking_times = self.location_analyzer._get_biking_times(
                                            apartment_lat,
                                            apartment_lng,
                                            [gym_coords_list[nearest_gym_idx]]
                                        )
                                        
                                        if biking_times and biking_times[0].get('duration_mins') is not None:
                                            bike_time = biking_times[0]['duration_mins']
                                            print(f"    {nearest_gym['name']}: {bike_time} min bike")
                                            
                                            # Use biking time for scoring if it's better
                                            if bike_time < min_walk_time:
                                                effective_time = bike_time
                                                transport_mode = 'bike'
                                                print(f"  → Using biking time for scoring ({bike_time:.1f} min)")
                                            else:
                                                print(f"  → Walking is still faster, using walk time ({min_walk_time:.1f} min)")
                                    
                                    result['gym_within_10min'] = effective_time <= 20  # 20 min threshold
                                    result['gym_walk_time_mins'] = min_walk_time  # Always store walk time
                                    result['gym_bike_time_mins'] = bike_time  # Store bike time if calculated
                                    result['gym_transport_mode'] = transport_mode  # Store which mode is used for scoring
                                    result['gym_effective_time_mins'] = effective_time  # Store the time used for scoring
                                    
                                    if transport_mode == 'bike':
                                        print(f"  ✓ Nearest selected gym: {nearest_gym['name']} ({min_walk_time:.1f} min walk, {bike_time:.1f} min bike, using bike for scoring)")
                                    else:
                                        print(f"  ✓ Nearest selected gym: {nearest_gym['name']} ({min_walk_time:.1f} min walk, within 20min: {result['gym_within_10min']})")
                                else:
                                    print(f"  ⚠️  Could not calculate walk times to any selected gyms")
                                    result['gym_within_10min'] = False
                                    result['gym_walk_time_mins'] = None
                                    result['gym_bike_time_mins'] = None
                                    result['gym_transport_mode'] = None
                                    result['gym_effective_time_mins'] = None
                    else:
                        # No gyms selected - cannot calculate walk time
                        print(f"  ⚠️  No gyms selected for this apartment")
                        print(f"     Please select gyms in the entry form to enable distance-based scoring")
                        result['gym_within_10min'] = False
                        result['gym_walk_time_mins'] = None
                        result['gym_bike_time_mins'] = None
                        result['gym_transport_mode'] = None
                        result['gym_effective_time_mins'] = None
                else:
                    # Not recalculating gym - preserve existing data
                    result['gym_within_10min'] = row_data.get(config.SHEET_COLUMNS.get("gym_within_10min"))
                    result['gym_walk_time_mins'] = row_data.get(config.SHEET_COLUMNS.get("gym_walk_time_mins"))
                    result['gym_bike_time_mins'] = row_data.get(config.SHEET_COLUMNS.get("gym_bike_time_mins"))
                    result['gym_transport_mode'] = row_data.get(config.SHEET_COLUMNS.get("gym_transport_mode"))
                    result['gym_effective_time_mins'] = row_data.get(config.SHEET_COLUMNS.get("gym_effective_time_mins"))
                
                print(f"✓ Location analysis complete")
                if recalc_commute:
                    print(f"  Your commute: {result['commute_duration']} min via {result['commute_route']}")
                    print(f"  Partner commute: {result['commute_duration_partner']} min")
                    if result.get('route_annoyingness') is not None:
                        print(f"  Route annoyingness: {result['route_annoyingness']:.1f}/10")
                if recalc_safety:
                    print(f"  Safety score: {result['safety_score_opendata']:.1f}/10")
                if recalc_happening:
                    print(f"  Amenities: {result['restaurants_nearby']} restaurants, {result['cafes_nearby']} cafes")
                else:
                    print("⚠ No address available, skipping location analysis")
            
            # Add manual safety rating
            result['manual_safety_rating'] = manual_safety
            
            # Defaults for missing fields
            result.setdefault('parking_distance', 'onsite')
            result.setdefault('street_parking_ease', None)
            result.setdefault('visitor_parking_ease', None)
            
            # Calculate scores
            print(f"\n✓ Calculating scores...")
            print(f"  Debug - Parking type: {result.get('parking_type')}")
            print(f"  Debug - Laundry type: {result.get('laundry_type')}")
            print(f"  Debug - Gym data for scoring:")
            print(f"    gym_within_10min: {result.get('gym_within_10min')}")
            print(f"    gym_walk_time_mins: {result.get('gym_walk_time_mins')} (PRIMARY scoring factor)")
            print(f"    office_gym_only: {result.get('office_gym_only')}")
            scorecard = build_scorecard(result)
            
            # Calculate total score
            total_score = scorecard.calculate_total()
            result['weighted_score'] = round(total_score, 2)
            
            # Calculate score range (for uncertain data)
            score_min, score_max = scorecard.calculate_total_range()
            result['score_min'] = round(score_min, 2)
            result['score_max'] = round(score_max, 2)
            result['score_certainty'] = round(scorecard.get_certainty_percentage(), 1)
            print(f"  Debug - Score range: {score_min:.2f} - {score_max:.2f}")
            
            # Check if parking or laundry components have ranges
            parking_component = scorecard.components.get('parking')
            if parking_component and hasattr(parking_component, 'raw_value_min') and parking_component.raw_value_min is not None:
                print(f"  Debug - Parking score range: {parking_component.raw_value_min:.2f} - {parking_component.raw_value_max:.2f}")
            
            laundry_component = scorecard.components.get('laundry')
            if laundry_component and hasattr(laundry_component, 'raw_value_min') and laundry_component.raw_value_min is not None:
                print(f"  Debug - Laundry score range: {laundry_component.raw_value_min:.2f} - {laundry_component.raw_value_max:.2f}")
            
            # Calculate score vs theoretical max
            actual_score, theoretical_max, score_vs_max = scorecard.calculate_score_vs_theoretical_max()
            result['score_vs_max'] = round(score_vs_max, 1)
            
            # Calculate value ratio
            if result['price'] > 0:
                result['value_ratio'] = round(total_score / (result['price'] / 1000), 2)
            else:
                result['value_ratio'] = 0.0
            
            # Extract component scores for sheet
            result['combined_safety'] = (result['manual_safety_rating'] + result.get('safety_score_opendata', 5.0)) / 2.0
            wfh_component = scorecard.components['wfh_quality']
            quietness_component = scorecard.components['quietness']
            result['wfh_quality_score'] = wfh_component.raw_value
            result['quietness_score'] = quietness_component.raw_value
            if not (wfh_component.details or {}).get('inputs_available', True):
                result['wfh_quality_score'] = None
            if not (quietness_component.details or {}).get('inputs_available', True):
                result['quietness_score'] = None
            result['happening_score'] = scorecard.components['happening'].raw_value
            result['parking_score'] = scorecard.components['parking'].raw_value
            result['laundry_score'] = scorecard.components['laundry'].raw_value
            result['gym_score'] = scorecard.components['gym_nearby'].raw_value
            result['commute_score'] = scorecard.components['commute'].raw_value
            result['space_luxury_score'] = scorecard.components['space_luxury'].raw_value
            
            # Prepare JSON fields for sheet storage (already serialized at line 126, don't overwrite!)
            # commute_details_json was already set at line 126
            # crime_details needs to be serialized to JSON
            if 'crime_details' in result:
                result['crime_details_json'] = json.dumps(result['crime_details']) if result['crime_details'] else ""
                # Only log if this was actually recalculated (not preserved data)
                if recalc_safety:
                    try:
                        print(f"  -> Crime details recalculated ({result['address']}): {json.dumps(result['crime_details'])[:200]}...")
                    except Exception as json_err:
                        print(f"  ⚠ Failed to serialize crime details for {result['address']}: {json_err}")
            
            # Evaluate ideal criteria
            criteria_met = scorecard.evaluate_ideal_criteria()
            result['criteria_met'] = criteria_met
            result['total_criteria_met'] = scorecard.count_criteria_met()
            
            # Timestamps
            result['last_analyzed'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # Don't update last_updated here - that's for manual edits
            
            print(f"\n✓ Analysis complete!")
            print(f"  Weighted Score: {result['weighted_score']:.1f}/100")
            if score_min != score_max:
                print(f"  Score Range: {score_min:.1f} - {score_max:.1f} (certainty: {result['score_certainty']:.0f}%)")
            print(f"  Performance: {score_vs_max:.1f}% of theoretical max")
            print(f"  Value Ratio: {result['value_ratio']:.2f}")
            print(f"  Criteria Met: {result['total_criteria_met']}/{len(config.IDEAL_CRITERIA)}")
            
            return result
        
        except Exception as e:
            print(f"\n✗ Error analyzing apartment: {e}")
            traceback.print_exc()
            return {'error': str(e)}
    
    def analyze_all(self, force_refresh: bool = False, fail_fast: bool = False):
        """
        Analyze all apartments in the sheet
        
        Args:
            force_refresh: Force re-scraping even if cached
            fail_fast: Stop on first error (useful for debugging)
        """
        print("\n" + "="*80)
        print("ANALYZING ALL APARTMENTS")
        print("="*80)
        
        # Get apartments needing analysis
        apartments = self.sheets_client.get_apartments_needing_analysis()
        
        if not apartments:
            print("\n✓ No apartments need analysis. All done!")
            return
        
        print(f"\nFound {len(apartments)} apartments to analyze")
        for apt in apartments:
            address = apt.get(config.SHEET_COLUMNS["address"], "Unknown")
            reason = apt.get('_analysis_reason', 'needs analysis')
            print(f"  - {address}: {reason}")
        
        if fail_fast:
            print("⚠️  FAIL-FAST MODE: Will stop on first error\n")
        
        # Analyze each apartment
        error_count = 0
        for apartment in tqdm(apartments, desc="Analyzing apartments"):
            try:
                result = self.analyze_apartment(apartment, force_refresh=force_refresh)
                
                if 'error' not in result:
                    # Write to sheet
                    row_number = apartment['_row_number']
                    self.sheets_client.write_apartment_data(row_number, result)
                else:
                    error_count += 1
                    print(f"\n⚠ Skipped apartment due to error: {result['error']}")
                    
                    if fail_fast:
                        print("\n❌ STOPPING: Fail-fast mode enabled")
                        print("\nTroubleshooting:")
                        print("1. Zillow is blocking (HTTP 403): Use 'python manual_entry.py' to add data manually")
                        print("2. Test single URL: 'python test_scraper.py <url>'")
                        print("3. Check README for setup instructions")
                        raise Exception(f"Failed to scrape apartment: {result['error']}")
            
            except Exception as e:
                error_count += 1
                print(f"\n✗ Error processing apartment: {e}")
                if fail_fast:
                    raise
        
        # Update visualizations
        print("\nUpdating visualizations...")
        self.update_visualizations()
        
        if error_count > 0:
            print(f"\n⚠️  Completed with {error_count} errors")
        else:
            print("\n✓ All apartments analyzed successfully!")
    
    def analyze_new(self, fail_fast: bool = False):
        """Analyze only new apartments (those without scores)"""
        self.analyze_all(force_refresh=False, fail_fast=fail_fast)
    
    def reanalyze_row(self, row_number: int):
        """Re-analyze a specific row"""
        print(f"\nRe-analyzing row {row_number}...")
        
        records = self.sheets_client.read_main_sheet()
        if row_number - 2 < len(records):
            apartment = records[row_number - 2]
            apartment['_row_number'] = row_number
            
            result = self.analyze_apartment(apartment, force_refresh=True)
            
            if 'error' not in result:
                self.sheets_client.write_apartment_data(row_number, result)
                self.update_visualizations()
                print(f"\n✓ Row {row_number} re-analyzed successfully")
            else:
                print(f"\n✗ Error: {result['error']}")
        else:
            print(f"✗ Row {row_number} not found")
    
    def update_visualizations(self):
        """Update scatter plot and criteria matrix"""
        try:
            print("Updating scatter plot...")
            self.sheets_client.update_scatter_plot_data()
            
            print("Updating criteria matrix...")
            records = self.sheets_client.read_main_sheet()
            
            # Build criteria results
            criteria_results = []
            for record in records:
                address = record.get(config.SHEET_COLUMNS["address"], "")
                if not address:
                    continue
                
                # Build score dict for criteria evaluation
                score_dict = {
                    'combined_safety': record.get(config.SHEET_COLUMNS["combined_safety"], 0),
                    'commute_duration': record.get(config.SHEET_COLUMNS["commute_time_you"], 999),
                    'commute_route': record.get(config.SHEET_COLUMNS["commute_route"], ""),
                    'parking_score': record.get(config.SHEET_COLUMNS["parking_score"], 0),
                    'wfh_quality': record.get(config.SHEET_COLUMNS["wfh_quality_score"], 0),
                    'laundry_type': record.get(config.SHEET_COLUMNS["laundry_type"], ""),
                    'gym_within_10min': record.get(config.SHEET_COLUMNS["gym_within_10min"], False),
                    'gym_quality': record.get(config.SHEET_COLUMNS["gym_quality"], 0),
                    'rent_control': record.get(config.SHEET_COLUMNS["rent_control"], False),
                    'price': record.get(config.SHEET_COLUMNS["price"], 999999),
                }
                
                # Evaluate criteria
                criteria_result = {'address': address}
                total = 0
                for criterion_name, criterion_config in config.IDEAL_CRITERIA.items():
                    try:
                        met = criterion_config["condition"](score_dict)
                        criteria_result[criterion_name] = met
                        if met:
                            total += 1
                    except:
                        criteria_result[criterion_name] = False
                
                criteria_result['total_criteria_met'] = total
                criteria_results.append(criteria_result)
            
            self.sheets_client.update_criteria_matrix(criteria_results)
            print("✓ Visualizations updated")
        
        except Exception as e:
            print(f"✗ Error updating visualizations: {e}")
    
    def clear_cache(self):
        """Clear all cached data"""
        print("Clearing cache...")
        cleared = self.cache.clear_all()
        print(f"✓ Cleared {cleared} cache entries")
    
    def cache_stats(self):
        """Show cache statistics"""
        stats = self.cache.get_stats()
        print("\nCache Statistics:")
        print(f"  Total entries: {stats['total']}")
        print(f"  Valid entries: {stats['valid']}")
        print(f"  Expired entries: {stats['expired']}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Apartment Value Analyzer - Analyze apartment listings from Google Sheets"
    )
    
    parser.add_argument(
        '--analyze-all',
        action='store_true',
        help='Analyze all apartments in the sheet'
    )
    
    parser.add_argument(
        '--analyze-new',
        action='store_true',
        help='Analyze only new apartments (no existing scores)'
    )
    
    parser.add_argument(
        '--fail-fast',
        action='store_true',
        help='Stop on first error (useful for debugging)'
    )
    
    parser.add_argument(
        '--reanalyze-row',
        type=int,
        metavar='ROW',
        help='Re-analyze a specific row number'
    )
    
    parser.add_argument(
        '--update-scores',
        action='store_true',
        help='Recalculate scores for all apartments (no re-scraping)'
    )
    
    parser.add_argument(
        '--update-visualizations',
        action='store_true',
        help='Update scatter plot and criteria matrix'
    )
    
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Clear all cached data'
    )
    
    parser.add_argument(
        '--cache-stats',
        action='store_true',
        help='Show cache statistics'
    )
    
    parser.add_argument(
        '--init-sheets',
        action='store_true',
        help='Initialize Google Sheets with proper structure'
    )
    
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force refresh (ignore cache)'
    )
    
    args = parser.parse_args()
    
    try:
        analyzer = ApartmentAnalyzer()
        
        if args.init_sheets:
            print("Initializing Google Sheets...")
            analyzer.sheets_client.initialize_sheets()
            analyzer.sheets_client.init_approved_gyms_sheet()
            print("✓ Sheets initialized (including Approved Gyms)")
        elif args.analyze_all:
            analyzer.analyze_all(force_refresh=args.force_refresh, fail_fast=args.fail_fast)
        
        elif args.analyze_new:
            analyzer.analyze_new(fail_fast=args.fail_fast)
        
        elif args.reanalyze_row:
            analyzer.reanalyze_row(args.reanalyze_row)
        
        elif args.update_visualizations:
            analyzer.update_visualizations()
        
        elif args.clear_cache:
            analyzer.clear_cache()
        
        elif args.cache_stats:
            analyzer.cache_stats()
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

