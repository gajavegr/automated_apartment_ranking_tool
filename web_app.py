#!/usr/bin/env python3
"""
Web interface for manual apartment data entry

Provides a user-friendly web form with Google Maps integration
for adding apartments to the analysis sheet.
"""

import os
import sys
import json
import signal
import webbrowser
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from threading import Timer

import config
from utils.google_sheets import GoogleSheetsClient
from analyzers.location_analyzer import LocationAnalyzer

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_requested
    if not shutdown_requested:
        shutdown_requested = True
        print("\n\n⚠️  Shutdown requested! Finishing current apartment, then stopping...")
        print("⚠️  Press Ctrl+C again to force quit (may corrupt data)")
    else:
        print("\n\n❌ Force quit requested. Exiting immediately.")
        sys.exit(1)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Register preference routes
try:
    from preferences.web_routes import register_preference_routes
    register_preference_routes(app)
    print("  ✓ Preference routes registered")
except ImportError as e:
    print(f"  ⚠️  Preference routes not available: {e}")

# Initialize clients
sheets_client = None
location_analyzer = None

def init_clients():
    """Initialize Google Sheets and Location Analyzer clients"""
    global sheets_client, location_analyzer
    try:
        print("  Initializing Google Sheets client...")
        sheets_client = GoogleSheetsClient()
        print("  ✓ Google Sheets client ready")
        
        print("  Initializing Location Analyzer...")
        location_analyzer = LocationAnalyzer()
        print("  ✓ Location Analyzer ready")
        
        return True
    except Exception as e:
        print(f"Error initializing clients: {e}")
        import traceback
        traceback.print_exc()
        return False


def col_index_to_letter(col_idx):
    """
    Convert column index (0-based) to Excel-style column letter(s)
    
    Examples:
        0 -> A
        25 -> Z
        26 -> AA
        27 -> AB
    """
    result = ""
    col_idx += 1  # Make it 1-based
    while col_idx > 0:
        col_idx -= 1
        result = chr(65 + (col_idx % 26)) + result
        col_idx //= 26
    return result


COMPONENT_LABELS = {
    "commute": "Commute",
    "safety": "Safety",
    "wfh_quality": "WFH Quality",
    "happening": "Happening",
    "parking": "Parking",
    "laundry": "Laundry",
    "gym_nearby": "Gym",
    "space_luxury": "Space & Luxury",
    "rent_control": "Rent Control",
}


def _safe_float(value, default=0.0):
    """Convert sheet value to float, handling currency and commas."""
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace(",", "")
            if cleaned == "":
                return default
            return float(cleaned)
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value, default=0):
    """Convert sheet value to int."""
    try:
        return int(round(_safe_float(value, default)))
    except (TypeError, ValueError):
        return default


def _sheet_bool(value, default=False):
    """Convert Google Sheets truthy strings to boolean."""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "checked", "✓", "☑"}:
            return True
        if normalized in {"false", "no", "n", "0", "unchecked", "✗", "x", ""}:
            return False
    return default


def _get_value_from_row(row, column_name, fallback_keys=None, default=None):
    """Fetch value from sheet row using primary column and optional fallbacks."""
    keys_to_try = []
    if column_name:
        keys_to_try.append(column_name)
    if fallback_keys:
        keys_to_try.extend(fallback_keys)
    for key in keys_to_try:
        if key is None:
            continue
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _sheet_value(row, sheet_key, fallback_keys=None, default=None):
    """Helper to fetch value using config sheet column mapping."""
    column_name = config.SHEET_COLUMNS.get(sheet_key)
    return _get_value_from_row(row, column_name, fallback_keys, default)

def _parse_commute_details(value):
    """Return commute details dict regardless of storage format."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return {}
        try:
            return json.loads(trimmed)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _normalize_sheet_row_for_scoring(row):
    """Normalize a sheet row into the structure expected by the scoring engine."""
    data = {}
    
    data['address'] = (_sheet_value(row, "address", default="") or "").strip()
    data['price'] = _safe_float(_sheet_value(row, "price"), 0.0)
    data['bedrooms'] = _safe_float(_sheet_value(row, "bedrooms"), 0.0)
    data['bathrooms'] = _safe_float(_sheet_value(row, "bathrooms"), 0.0)
    data['sqft'] = _safe_float(_sheet_value(row, "sqft"), 0.0)
    data['manual_safety_rating'] = _safe_float(_sheet_value(row, "manual_safety", ["manual_safety_rating"]), 5.0)
    data['commute_duration'] = _safe_float(_sheet_value(row, "commute_time_you", ["commute_duration"]), 999)
    data['commute_route'] = _sheet_value(row, "commute_route", ["commute_route"], "")
    data['commute_duration_partner'] = _safe_float(_sheet_value(row, "commute_time_partner", ["commute_duration_partner"]), 999)
    data['route_annoyingness'] = _safe_float(_sheet_value(row, "route_annoyingness"), 10.0)
    data['safety_score_opendata'] = _safe_float(_sheet_value(row, "safety_score_opendata"), 5.0)
    combined_safety = _safe_float(_sheet_value(row, "combined_safety"), None)
    if combined_safety is None:
        combined_safety = (data['manual_safety_rating'] + data['safety_score_opendata']) / 2.0
    data['combined_safety'] = combined_safety
    
    data['natural_light'] = _safe_float(_sheet_value(row, "natural_light"), None)
    data['desk_space_quality'] = _safe_float(_sheet_value(row, "desk_space_quality"), None)
    data['kitchen_quality'] = _safe_float(_sheet_value(row, "kitchen_quality"), None)
    data['double_pane_windows'] = _sheet_bool(_sheet_value(row, "double_pane_windows"), None)
    data['study_door_type'] = (_sheet_value(row, "study_door_type", default=None) or None)
    data['street_noise_level'] = _safe_float(_get_value_from_row(row, "Street Noise Level", default=None), None)
    data['floor_level'] = (_sheet_value(row, "floor_level", default=None) or None)
    
    data['restaurants_nearby'] = _safe_int(_sheet_value(row, "restaurants_nearby"), 0)
    data['cafes_nearby'] = _safe_int(_sheet_value(row, "cafes_nearby"), 0)
    data['parks_nearby'] = _safe_int(_sheet_value(row, "parks_nearby"), 0)
    data['avg_walk_to_poi_mins'] = _safe_float(_sheet_value(row, "avg_walk_to_poi_mins"), None)
    data['nearest_poi_count'] = _safe_int(_sheet_value(row, "nearest_poi_count"), 0)
    data['pois_within_1_mile'] = _safe_int(_sheet_value(row, "pois_within_1_mile"), 0)
    
    data['parking_type'] = _sheet_value(row, "parking_type", default="none") or "none"
    data['parking_enclosure'] = _sheet_value(row, "parking_enclosure", default="") or ""
    data['parking_distance'] = _sheet_value(row, "parking_distance", default="onsite") or "onsite"
    
    street_ease_value = _sheet_value(row, "street_parking_ease")
    data['street_parking_ease'] = None if street_ease_value in (None, "") else str(street_ease_value)
    visitor_ease = _sheet_value(row, "visitor_parking_ease")
    data['visitor_parking_ease'] = None if visitor_ease in (None, "") else str(visitor_ease)
    
    data['apartment_elevation'] = _safe_float(_sheet_value(row, "apartment_elevation"), None)
    data['elevation_to_gym'] = _safe_float(_sheet_value(row, "elevation_to_gym"), None)
    data['gym_within_10min'] = _sheet_bool(_sheet_value(row, "gym_within_10min"), False)
    data['gym_walk_time_mins'] = _safe_float(_sheet_value(row, "gym_walk_time_mins"), None)
    data['gym_bike_time_mins'] = _safe_float(_sheet_value(row, "gym_bike_time_mins"), None)
    data['gym_transport_mode'] = _sheet_value(row, "gym_transport_mode", default=None)
    data['gym_effective_time_mins'] = _safe_float(_sheet_value(row, "gym_effective_time_mins"), None)
    data['gym_quality'] = _safe_float(_sheet_value(row, "gym_quality"), 0.0)
    data['office_gym_only'] = _sheet_bool(_sheet_value(row, "office_gym_only"), False)
    data['rent_control'] = _sheet_bool(_sheet_value(row, "rent_control"), False)
    data['laundry_type'] = _sheet_value(row, "laundry_type", default="none") or "none"
    data['parking_cost'] = _safe_float(_sheet_value(row, "parking_cost"), 0.0)
    data['selected_gyms'] = _sheet_value(row, "selected_gyms", default="")
    
    # Derived/default fields
    data['street_parking_ease'] = data['street_parking_ease'] or None
    data['visitor_parking_ease'] = data['visitor_parking_ease'] or None
    data['on_steep_hill_from_work'] = _sheet_bool(row.get("On Steep Hill From Work"), False)
    
    return data


@app.route('/')
def index():
    """Show the entry form"""
    return render_template('entry_form.html', 
                         google_maps_api_key=config.GOOGLE_MAPS_API_KEY,
                         sf_neighborhoods=config.SF_NEIGHBORHOODS)


@app.route('/get_apartments', methods=['GET'])
def get_apartments():
    """Get list of all apartments for dropdown"""
    try:
        records = sheets_client.read_main_sheet()
        apartments = [{
            'row': i + 2,  # +2 for header and 1-indexing
            'address': record.get(config.SHEET_COLUMNS['address'], 'Unknown'),
            'price': record.get(config.SHEET_COLUMNS['price'], '')
        } for i, record in enumerate(records)]
        return jsonify({'apartments': apartments, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/get_apartment/<int:row_number>', methods=['GET'])
def get_apartment(row_number):
    """Get data for a specific apartment"""
    try:
        records = sheets_client.read_main_sheet()
        if 0 <= row_number - 2 < len(records):
            apartment = records[row_number - 2]
            apartment['row_number'] = row_number
            commute_details_raw = _sheet_value(apartment, "commute_details", default="")
            apartment['commute_details'] = _parse_commute_details(commute_details_raw)
            commute_details_raw = _sheet_value(apartment, "commute_details", default="")
            apartment['commute_details'] = _parse_commute_details(commute_details_raw)
            apartment['route_annoyingness'] = _safe_float(_sheet_value(apartment, "route_annoyingness"), None)
            commute_details_raw = _sheet_value(apartment, "commute_details", default="")
            try:
                apartment['commute_details'] = json.loads(commute_details_raw) if commute_details_raw else {}
            except (json.JSONDecodeError, TypeError):
                apartment['commute_details'] = {}
            apartment['route_annoyingness'] = _safe_float(_sheet_value(apartment, "route_annoyingness"), None)
            
            # Extract Zillow URL from Address column HYPERLINK formula
            sheet = sheets_client.spreadsheet.worksheet(sheets_client.MAIN_SHEET_NAME)
            headers = sheet.row_values(1)
            address_col_name = config.SHEET_COLUMNS['address']
            
            if address_col_name in headers:
                col_idx = headers.index(address_col_name)
                col_letter = chr(65 + col_idx)  # A=65
                cell_range = f'{col_letter}{row_number}'
                
                # Get the formula from the cell
                cell_data = sheet.get(cell_range, value_render_option='FORMULA')
                if cell_data and len(cell_data) > 0 and len(cell_data[0]) > 0:
                    formula = cell_data[0][0]
                    # Extract URL from HYPERLINK formula: =HYPERLINK("url", "text")
                    if formula.startswith('=HYPERLINK('):
                        import re
                        match = re.search(r'=HYPERLINK\("([^"]+)"', formula)
                        if match:
                            apartment['Zillow URL'] = match.group(1)
            
            return jsonify(apartment)
        return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_apartment_detailed/<int:row_number>', methods=['GET'])
def get_apartment_detailed(row_number):
    """Get detailed data for a specific apartment including component scores"""
    print(f"\n{'='*80}")
    print(f"DEBUG: get_apartment_detailed called for row {row_number}")
    print(f"{'='*80}")
    
    try:
        print(f"[1/8] Importing modules...")
        from main import ApartmentAnalyzer
        from analyzers.scoring_engine import build_scorecard
        print(f"  ✓ Imports successful")
        
        print(f"[2/8] Reading main sheet...")
        records = sheets_client.read_main_sheet()
        print(f"  ✓ Found {len(records)} records")
        
        if 0 <= row_number - 2 < len(records):
            print(f"[3/8] Loading apartment at index {row_number - 2}...")
            apartment = records[row_number - 2]
            apartment['row_number'] = row_number
            print(f"  ✓ Apartment address: {apartment.get(config.SHEET_COLUMNS.get('address', 'Address'), 'Unknown')}")
            
            # Extract Zillow URL from Address column HYPERLINK formula
            print(f"[4/8] Extracting Zillow URL...")
            try:
                sheet = sheets_client.spreadsheet.worksheet(sheets_client.MAIN_SHEET_NAME)
                headers = sheet.row_values(1)
                address_col_name = config.SHEET_COLUMNS['address']
                
                if address_col_name in headers:
                    col_idx = headers.index(address_col_name)
                    # Handle columns beyond Z
                    def col_index_to_letter(col_index):
                        result = ""
                        while col_index >= 0:
                            result = chr(65 + (col_index % 26)) + result
                            col_index = col_index // 26 - 1
                        return result
                    
                    col_letter = col_index_to_letter(col_idx)
                    cell_range = f'{col_letter}{row_number}'
                    
                    # Get the formula from the cell
                    cell_data = sheet.get(cell_range, value_render_option='FORMULA')
                    if cell_data and len(cell_data) > 0 and len(cell_data[0]) > 0:
                        formula = cell_data[0][0]
                        # Extract URL from HYPERLINK formula: =HYPERLINK("url", "text")
                        if formula.startswith('=HYPERLINK('):
                            import re
                            match = re.search(r'=HYPERLINK\("([^"]+)"', formula)
                            if match:
                                apartment['Zillow URL'] = match.group(1)
                                print(f"  ✓ Extracted Zillow URL")
                print(f"  ✓ Zillow URL extraction complete")
            except Exception as e:
                print(f"  ⚠️  Warning: Could not extract Zillow URL: {e}")
            
            # Calculate component scores and contributions
            print(f"[5/8] Normalizing apartment data for scoring...")
            component_scores = {}
            component_contributions = []
            total_recomputed_score = None
            try:
                normalized_input = _normalize_sheet_row_for_scoring(apartment)
                print(f"  ✓ Normalized data keys: {list(normalized_input.keys())}")
                
                # Debug gym-related fields
                gym_fields = {k: v for k, v in normalized_input.items() if 'gym' in k.lower()}
                print(f"  ✓ Gym fields in normalized data: {gym_fields}")
                
                print(f"[6/8] Building scorecard...")
                scorecard = build_scorecard(normalized_input)
                print(f"  ✓ Scorecard built with components: {list(scorecard.components.keys())}")
                
                print(f"[7/8] Calculating scores...")
                total_recomputed_score = round(scorecard.calculate_total(), 2)
                print(f"  ✓ Total score: {total_recomputed_score}")
                
                for component_name, component in scorecard.components.items():
                    weight = scorecard.config_components.get(component_name, {}).get('weight', 0.0)
                    raw_score = round(component.raw_value, 2)
                    weighted_contribution = round(component.raw_value * weight * 10.0, 2)
                    adjusted_raw_score = raw_score
                    adjusted_weighted = weighted_contribution
                    if component_name == 'wfh_quality' and not (component.details or {}).get('inputs_available', True):
                        adjusted_raw_score = None
                        adjusted_weighted = 0.0
                    component_scores[component_name] = {
                        'raw_score': adjusted_raw_score,
                        'weight': weight,
                        'weighted_contribution': adjusted_weighted,
                        'label': COMPONENT_LABELS.get(component_name, component_name.replace('_', ' ').title()),
                        'details': getattr(component, 'details', {}),
                    }
                    
                    if weight > 0:
                        component_contributions.append({
                            'name': component_name,
                            'label': component_scores[component_name]['label'],
                            'raw_score': adjusted_raw_score,
                            'weight': weight,
                            'weighted_contribution': max(0.0, adjusted_weighted),
                            'max_contribution': round(10.0 * weight * 10.0, 2),
                        })
                print(f"  ✓ Component scores calculated: {len(component_scores)} components")
            except Exception as e:
                print(f"  ❌ ERROR calculating component scores: {e}")
                import traceback
                traceback.print_exc()
                # Re-raise to see full error
                raise
            
            component_contributions.sort(key=lambda c: c['weighted_contribution'], reverse=True)
            
            apartment['component_scores'] = component_scores
            apartment['component_contributions'] = component_contributions
            if total_recomputed_score is not None:
                apartment['calculated_weighted_score'] = total_recomputed_score
            
            # Add current weights from config
            apartment['scoring_weights'] = {
                'commute': config.SCORE_COMPONENTS.get('commute', {}).get('weight', 0),
                'safety': config.SCORE_COMPONENTS.get('safety', {}).get('weight', 0),
                'wfh_quality': config.SCORE_COMPONENTS.get('wfh_quality', {}).get('weight', 0),
                'happening': config.SCORE_COMPONENTS.get('happening', {}).get('weight', 0),
                'parking': config.SCORE_COMPONENTS.get('parking', {}).get('weight', 0),
                'gym': config.SCORE_COMPONENTS.get('gym_nearby', {}).get('weight', 0),
                'laundry': config.SCORE_COMPONENTS.get('laundry', {}).get('weight', 0),
                'quietness': config.SCORE_COMPONENTS.get('quietness', {}).get('weight', 0)
            }
            
            print(f"[8/8] Parsing commute and place list details...")
            # Parse commute metadata for frontend (uses snake_case keys)
            commute_details_raw = _sheet_value(apartment, "commute_details", default="")
            apartment['commute_details'] = _parse_commute_details(commute_details_raw)
            apartment['route_annoyingness'] = _safe_float(_sheet_value(apartment, "route_annoyingness"), None)
            print(f"  ✓ Commute details parsed")
            
            # Parse place lists for happening score display
            print(f"  📍 Parsing place lists (restaurants, cafes, parks, POIs)...")
            try:
                restaurants_json = _sheet_value(apartment, "restaurants_list", default="[]")
                cafes_json = _sheet_value(apartment, "cafes_list", default="[]")
                parks_json = _sheet_value(apartment, "parks_list", default="[]")
                pois_json = _sheet_value(apartment, "pois_list", default="[]")
                
                print(f"     Raw restaurants_json length: {len(restaurants_json) if restaurants_json else 0}")
                print(f"     Raw cafes_json length: {len(cafes_json) if cafes_json else 0}")
                print(f"     Raw parks_json length: {len(parks_json) if parks_json else 0}")
                print(f"     Raw pois_json length: {len(pois_json) if pois_json else 0}")
                
                # Parse JSON strings
                apartment['restaurants_list'] = json.loads(restaurants_json) if restaurants_json and restaurants_json != "[]" else []
                apartment['cafes_list'] = json.loads(cafes_json) if cafes_json and cafes_json != "[]" else []
                apartment['parks_list'] = json.loads(parks_json) if parks_json and parks_json != "[]" else []
                apartment['pois_list'] = json.loads(pois_json) if pois_json and pois_json != "[]" else []
                
                print(f"     ✓ Parsed {len(apartment['restaurants_list'])} restaurants")
                print(f"     ✓ Parsed {len(apartment['cafes_list'])} cafes")
                print(f"     ✓ Parsed {len(apartment['parks_list'])} parks")
                print(f"     ✓ Parsed {len(apartment['pois_list'])} POIs")
                
            except (json.JSONDecodeError, TypeError) as e:
                print(f"     ⚠️  Error parsing place lists: {e}")
                apartment['restaurants_list'] = []
                apartment['cafes_list'] = []
                apartment['parks_list'] = []
                apartment['pois_list'] = []
            
            print(f"{'='*80}")
            print(f"✅ SUCCESS: Returning apartment details for row {row_number}")
            print(f"{'='*80}\n")
            return jsonify(apartment)
        
        print(f"❌ ERROR: Row {row_number} out of range (records: {len(records)})")
        return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ FATAL ERROR in get_apartment_detailed for row {row_number}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"{'='*80}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        return jsonify({'error': str(e)}), 500


@app.route('/geocode', methods=['POST'])
def geocode():
    """Geocode an address to get lat/lng"""
    try:
        address = request.json.get('address')
        if not address:
            return jsonify({'error': 'No address provided'}), 400
        
        coords = location_analyzer.geocode_address(address)
        if coords:
            return jsonify({
                'lat': coords[0],
                'lng': coords[1],
                'success': True
            })
        else:
            return jsonify({'error': 'Could not geocode address'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_neighborhoods', methods=['POST'])
def get_neighborhoods():
    """Get neighborhoods for an address"""
    try:
        address = request.json.get('address')
        
        if not address:
            return jsonify({'error': 'Address required'}), 400
        
        # Get neighborhoods
        neighborhoods = location_analyzer.get_neighborhoods(address)
        
        return jsonify({
            'neighborhoods': neighborhoods,
            'success': True
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_gyms', methods=['POST'])
def get_gyms():
    """Get nearby gyms for apartment address"""
    try:
        data = request.get_json()
        address = data.get('address')
        radius_miles = data.get('radius_miles')  # Optional custom radius
        clear_cache = data.get('clear_cache', False)  # Optional cache clear
        
        if not address:
            return jsonify({'error': 'Address required'}), 400
        
        # Geocode address
        coords = location_analyzer.geocode_address(address)
        
        if not coords:
            return jsonify({'error': 'Could not geocode address'}), 400
        
        # Clear cache if requested
        if clear_cache:
            print(f"  Clearing gym cache for {address}")
            cleared_count = location_analyzer.cache.clear_all()
            print(f"  Cleared {cleared_count} cache entries")
        
        # Get nearby gyms with optional custom radius
        gyms = location_analyzer.get_nearby_gyms_detailed(
            coords[0], coords[1], limit=20, radius_miles=radius_miles
        )
        
        print(f"  API returned {len(gyms)} gyms for display")
        
        # Get detailed info (reviews) for each gym
        for gym in gyms:
            details = location_analyzer.get_gym_details(gym['place_id'])
            if details:
                gym.update(details)
        
        # Get approved gyms to pre-select
        approved_gyms = sheets_client.get_approved_gyms()
        approved_place_ids = [g.get('Google Place ID') for g in approved_gyms]
        
        # Mark pre-selected gyms
        for gym in gyms:
            gym['is_approved'] = gym['place_id'] in approved_place_ids
        
        return jsonify({
            'gyms': gyms,
            'radius_used': radius_miles,  # Return the radius used
            'total_found': len(gyms),  # How many gyms were found
            'success': True
        })
    
    except Exception as e:
        print(f"Error in get_gyms: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/get_hilliness', methods=['POST'])
def get_hilliness():
    """Get auto-detected hilliness for an address"""
    try:
        data = request.get_json()
        address = data.get('address')
        
        if not address:
            return jsonify({'error': 'Address required'}), 400
        
        # Get coordinates
        coords = location_analyzer.geocode_address(address)
        
        if not coords:
            return jsonify({'error': 'Could not geocode address'}), 400
        
        # Get elevation
        elevation = location_analyzer.get_elevation(coords[0], coords[1])
        
        if elevation is None:
            return jsonify({
                'hilliness': None,
                'elevation': None,
                'success': False
            })
        
        # Calculate hilliness score (0-10 scale)
        # Based on elevation thresholds
        if elevation > 100:
            hilliness = 10
        elif elevation > 80:
            hilliness = 9
        elif elevation > 60:
            hilliness = 8
        elif elevation > 50:
            hilliness = 7
        elif elevation > 40:
            hilliness = 6
        elif elevation > 30:
            hilliness = 5
        elif elevation > 20:
            hilliness = 4
        elif elevation > 15:
            hilliness = 3
        elif elevation > 10:
            hilliness = 2
        elif elevation > 5:
            hilliness = 1
        else:
            hilliness = 0
        
        return jsonify({
            'hilliness': hilliness,
            'elevation': round(elevation, 1),
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_parking_ease', methods=['POST'])
def get_parking_ease():
    """Get estimated visitor parking ease for an address (includes SFMTA garages)"""
    try:
        data = request.get_json()
        address = data.get('address')
        parking_type = data.get('type', 'visitor')  # 'visitor' or 'street'
        
        if not address:
            return jsonify({'error': 'Address required'}), 400
        
        # Geocode address
        coords = location_analyzer.geocode_address(address)
        
        if not coords:
            return jsonify({'error': 'Could not geocode address'}), 400
        
        # Estimate parking ease based on type
        if parking_type == 'street':
            parking_info = location_analyzer.estimate_street_parking_ease(coords[0], coords[1], address)
        else:
            parking_info = location_analyzer.estimate_visitor_parking_ease(coords[0], coords[1], address)
        
        return jsonify({
            'parking_ease': parking_info.get('parking_ease', 5),
            'reasoning': parking_info.get('reasoning', ''),
            'public_garages': parking_info.get('public_garages', []),
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_laundromats', methods=['POST'])
def get_laundromats():
    """Get nearby laundromats for an address"""
    try:
        data = request.get_json()
        address = data.get('address')
        
        if not address:
            return jsonify({'error': 'Address required'}), 400
        
        # Geocode address
        coords = location_analyzer.geocode_address(address)
        
        if not coords:
            return jsonify({'error': 'Could not geocode address'}), 400
        
        # Get nearby laundromats
        laundromats = location_analyzer.get_nearby_laundromats(coords[0], coords[1], radius_miles=0.5)
        
        # Calculate estimated monthly cost
        cost_per_load = config.SCORE_COMPONENTS['laundry']['laundromat_penalty']['cost_per_load']
        loads_per_week = config.SCORE_COMPONENTS['laundry']['laundromat_penalty']['loads_per_week']
        monthly_cost = cost_per_load * loads_per_week * 4.33  # Average weeks per month
        
        return jsonify({
            'laundromats': laundromats[:5],  # Return top 5 closest
            'estimated_monthly_cost': round(monthly_cost, 2),
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_building_year', methods=['POST'])
def get_building_year():
    """Attempt to automatically detect building year"""
    try:
        data = request.get_json()
        address = data.get('address')
        
        if not address:
            return jsonify({'error': 'Address required'}), 400
        
        # Try to find building year
        year = location_analyzer.get_building_year(address)
        
        if year:
            return jsonify({
                'year': year,
                'success': True
            })
        else:
            return jsonify({
                'year': None,
                'success': False,
                'message': 'Could not automatically determine building year'
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/add', methods=['POST'])
def add_apartment():
    """Process form submission and add to Google Sheets"""
    try:
        # Extract multi-select fields as lists
        parking_types = request.form.getlist('parking_type')
        parking_enclosures = request.form.getlist('parking_enclosure')
        laundry_types = request.form.getlist('laundry_type')
        neighborhoods = request.form.getlist('neighborhoods')
        study_door_types = request.form.getlist('study_door_type')
        
        # Build tour questions list
        tour_questions = []
        if request.form.get('parking_type_tour_question'):
            tour_questions.append('Parking type')
        if request.form.get('parking_enclosure_tour_question'):
            tour_questions.append('Parking enclosure')
        if request.form.get('laundry_type_tour_question'):
            tour_questions.append('Laundry type')
        if request.form.get('wfh_tour_question'):
            tour_questions.append('WFH details')
        
        # Extract form data
        data = {
            'zillow_url': request.form.get('zillow_url', '').strip(),
            'address': request.form.get('address', '').strip(),
            'availability_status': request.form.get('availability_status', 'Available').strip(),
            'manual_safety_rating': float(request.form.get('manual_safety_rating', 5.0)),
            # Store multi-select values as newline-separated for better readability
            'parking_type': '\n'.join(parking_types) if parking_types else 'none',
            'parking_enclosure': '\n'.join(parking_enclosures) if parking_enclosures else '',
            'laundry_type': '\n'.join(laundry_types) if laundry_types else 'none',
            'neighborhoods': '\n'.join(neighborhoods) if neighborhoods else '',
            'tour_questions': '\n'.join(tour_questions) if tour_questions else '',
            'floor_level': request.form.get('floor_level', ''),
            'street_parking_ease': request.form.get('street_parking_ease', ''),
            'visitor_parking_ease': request.form.get('visitor_parking_ease', ''),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # WFH fields
        try:
            natural_light = request.form.get('natural_light', '').strip()
            if natural_light:
                data['natural_light'] = float(natural_light)
        except ValueError:
            pass
        
        try:
            desk_space = request.form.get('desk_space_quality', '').strip()
            if desk_space:
                data['desk_space_quality'] = float(desk_space)
        except ValueError:
            pass
        
        try:
            quietness = request.form.get('work_area_quietness', '').strip()
            if quietness:
                data['work_area_quietness'] = float(quietness)
        except ValueError:
            pass
        
        try:
            kitchen = request.form.get('kitchen_quality', '').strip()
            if kitchen:
                data['kitchen_quality'] = float(kitchen)
        except ValueError:
            pass
        
        # Double pane windows checkbox
        data['double_pane_windows'] = request.form.get('double_pane_windows') == 'true'
        
        # Study door type multi-select
        if study_door_types:
            data['study_door_type'] = '\n'.join(study_door_types)
        
        # Parking cost
        try:
            parking_cost = request.form.get('parking_cost', '').strip()
            if parking_cost:
                data['parking_cost'] = int(parking_cost)
            else:
                data['parking_cost'] = 0
        except ValueError:
            data['parking_cost'] = 0
        
        # Parse numeric fields
        try:
            data['price'] = int(request.form.get('price', 0))
        except ValueError:
            data['price'] = 0
        
        try:
            data['bedrooms'] = int(request.form.get('bedrooms', 0))
        except ValueError:
            data['bedrooms'] = 0
        
        try:
            data['bathrooms'] = float(request.form.get('bathrooms', 0))
        except ValueError:
            data['bathrooms'] = 0
        
        try:
            data['sqft'] = int(request.form.get('sqft', 0))
        except ValueError:
            data['sqft'] = 0
        
        # Square feet range (for uncertain estimates)
        try:
            sqft_min = request.form.get('sqft_min', '').strip()
            if sqft_min:
                data['sqft_min'] = int(sqft_min)
        except ValueError:
            pass
        
        try:
            sqft_max = request.form.get('sqft_max', '').strip()
            if sqft_max:
                data['sqft_max'] = int(sqft_max)
        except ValueError:
            pass
        
        # Luxury amenities checkboxes
        data['has_double_vanity'] = request.form.get('has_double_vanity') == 'true'
        data['high_end_appliances'] = request.form.get('high_end_appliances') == 'true'
        data['walk_in_closet'] = request.form.get('walk_in_closet') == 'true'
        data['has_balcony_patio'] = request.form.get('has_balcony_patio') == 'true'
        data['has_fireplace'] = request.form.get('has_fireplace') == 'true'
        
        # Year built and rent control
        year_built = request.form.get('year_built', '').strip()
        if year_built:
            try:
                year = int(year_built)
                data['year_built'] = year
                data['rent_control'] = year < config.SF_RENT_CONTROL_CUTOFF_YEAR
            except ValueError:
                pass
        
        # Hilliness override (only if checkbox is enabled)
        hilliness_enabled = request.form.get('hilliness_override_enabled')
        if hilliness_enabled:
            hilliness = request.form.get('hilliness_override', '5').strip()
            if hilliness:
                try:
                    hilliness_val = int(hilliness)
                    data['hilliness_manual_override'] = hilliness_val
                except ValueError:
                    pass
        
        # Handle selected gyms
        selected_gym_ids = request.form.getlist('selected_gyms[]')
        office_gym_only = request.form.get('office_gym_only') == 'on'  # Checkbox field
        
        if selected_gym_ids:
            # Get gym details from hidden fields and add to approved gyms
            for gym_id in selected_gym_ids:
                gym_name = request.form.get(f'gym_name_{gym_id}')
                gym_address = request.form.get(f'gym_address_{gym_id}')
                gym_rating = request.form.get(f'gym_rating_{gym_id}')
                gym_lat = request.form.get(f'gym_lat_{gym_id}')
                gym_lng = request.form.get(f'gym_lng_{gym_id}')
                gym_types = request.form.get(f'gym_types_{gym_id}')
                
                gym_data = {
                    'place_id': gym_id,
                    'name': gym_name,
                    'address': gym_address,
                    'rating': gym_rating,
                    'lat': gym_lat,
                    'lng': gym_lng,
                    'types': gym_types.split(',') if gym_types else []
                }
                
                sheets_client.add_approved_gym(gym_data)
            
            # Store selected gym names in apartment data
            gym_names = [request.form.get(f'gym_name_{gid}') for gid in selected_gym_ids]
            data['selected_gyms'] = ', '.join(gym_names)
        
        # Store office gym only flag
        data['office_gym_only'] = office_gym_only
        
        # Validate required fields
        if not data['address']:
            flash('Address is required', 'error')
            return redirect(url_for('index'))
        
        # Check if this is an update or new apartment
        row_number_str = request.form.get('row_number', '').strip()
        is_update = bool(row_number_str)
        
        # Add to or update Google Sheet
        sheet = sheets_client.spreadsheet.worksheet(sheets_client.MAIN_SHEET_NAME)
        records = sheets_client.read_main_sheet()
        
        if is_update:
            row_number = int(row_number_str)
        else:
            row_number = len(records) + 2
        
        headers = sheet.row_values(1)
        
        # Build row data
        updates = []
        
        # Column A: Manual Safety Rating (zillow_url column was removed)
        manual_safety_col_name = config.SHEET_COLUMNS['manual_safety']
        if manual_safety_col_name in headers:
            col_idx = headers.index(manual_safety_col_name)
            col_letter = col_index_to_letter(col_idx)
            updates.append({
                'range': f'{col_letter}{row_number}',
                'values': [[data.get('manual_safety_rating', 5.0)]]
            })
        
        # Column B: Address as hyperlink (if Zillow URL provided)
        # We'll handle this separately with a formula
        address_col_name = config.SHEET_COLUMNS['address']
        if address_col_name in headers:
            col_idx = headers.index(address_col_name)
            col_letter = col_index_to_letter(col_idx)
            
            # If zillow_url exists, create hyperlink formula, otherwise just address
            if data.get('zillow_url'):
                # Use HYPERLINK formula: =HYPERLINK("url", "text")
                formula = f'=HYPERLINK("{data["zillow_url"]}", "{data["address"]}")'
                updates.append({
                    'range': f'{col_letter}{row_number}',
                    'values': [[formula]]
                })
            else:
                updates.append({
                    'range': f'{col_letter}{row_number}',
                    'values': [[data['address']]]
                })
        
        # Other columns (skip address since we handled it above)
        column_mapping = {
            'availability_status': config.SHEET_COLUMNS['availability_status'],
            'price': config.SHEET_COLUMNS['price'],
            'bedrooms': config.SHEET_COLUMNS['bedrooms'],
            'bathrooms': config.SHEET_COLUMNS['bathrooms'],
            'sqft': config.SHEET_COLUMNS['sqft'],
            'parking_type': config.SHEET_COLUMNS['parking_type'],
            'parking_enclosure': config.SHEET_COLUMNS['parking_enclosure'],
            'parking_cost': config.SHEET_COLUMNS['parking_cost'],
            'floor_level': config.SHEET_COLUMNS['floor_level'],
            'street_parking_ease': config.SHEET_COLUMNS['street_parking_ease'],
            'visitor_parking_ease': config.SHEET_COLUMNS['visitor_parking_ease'],
            'laundry_type': config.SHEET_COLUMNS['laundry_type'],
            'neighborhoods': config.SHEET_COLUMNS['neighborhoods'],
            'neighborhood': config.SHEET_COLUMNS['neighborhood'],
            'rent_control': config.SHEET_COLUMNS['rent_control'],
            'tour_questions': config.SHEET_COLUMNS['tour_questions'],
            'hilliness_manual_override': config.SHEET_COLUMNS['hilliness_manual_override'],
            'selected_gyms': config.SHEET_COLUMNS['selected_gyms'],
            'office_gym_only': config.SHEET_COLUMNS['office_gym_only'],
            'year_built': config.SHEET_COLUMNS.get('year_built', 'Year Built'),
            'last_updated': config.SHEET_COLUMNS['last_updated'],
            # WFH fields
            'natural_light': config.SHEET_COLUMNS.get('natural_light', 'Natural Light'),
            'desk_space_quality': config.SHEET_COLUMNS.get('desk_space_quality', 'Desk Space Quality'),
            'work_area_quietness': config.SHEET_COLUMNS.get('quietness_score', 'Quietness Score'),
            'kitchen_quality': config.SHEET_COLUMNS.get('kitchen_quality', 'Kitchen Quality'),
            'double_pane_windows': config.SHEET_COLUMNS.get('double_pane_windows', 'Double Pane Windows'),
            'study_door_type': config.SHEET_COLUMNS.get('study_door_type', 'Study Door Type'),
            # Luxury amenities
            'has_double_vanity': config.SHEET_COLUMNS.get('has_double_vanity', 'Has Double Vanity'),
            'high_end_appliances': config.SHEET_COLUMNS.get('high_end_appliances', 'High-End Appliances'),
            'walk_in_closet': config.SHEET_COLUMNS.get('walk_in_closet', 'Walk-In Closet'),
            'has_balcony_patio': config.SHEET_COLUMNS.get('has_balcony_patio', 'Has Balcony/Patio'),
            'has_fireplace': config.SHEET_COLUMNS.get('has_fireplace', 'Has Fireplace'),
        }
        
        for data_key, column_name in column_mapping.items():
            if data_key in data and column_name in headers:
                col_idx = headers.index(column_name)
                col_letter = col_index_to_letter(col_idx)
                updates.append({
                    'range': f'{col_letter}{row_number}',
                    'values': [[data[data_key]]]
                })
        
        # Batch update
        # Use valueInputOption='USER_ENTERED' to allow formulas to be evaluated
        sheet.batch_update(updates, value_input_option='USER_ENTERED')
        
        # Format the row: auto-resize first, then apply text wrapping
        try:
            # Multi-select columns that need auto-width adjustment
            multi_select_column_names = [
                config.SHEET_COLUMNS["parking_type"],
                config.SHEET_COLUMNS["parking_enclosure"],
                config.SHEET_COLUMNS["laundry_type"],
                config.SHEET_COLUMNS["neighborhoods"],
                config.SHEET_COLUMNS["tour_questions"]
            ]
            
            # Build batch update request for sizing
            resize_requests = []
            
            # Set minimum widths for multi-select columns to prevent text cutoff
            # Use fixed widths that are wide enough for the longest expected values
            min_widths = {
                config.SHEET_COLUMNS["parking_type"]: 280,  # Wide enough for "dedicated_spot_car_and_motorcycle"
                config.SHEET_COLUMNS["parking_enclosure"]: 120,
                config.SHEET_COLUMNS["laundry_type"]: 150,
                config.SHEET_COLUMNS["neighborhoods"]: 200,
                config.SHEET_COLUMNS["tour_questions"]: 180
            }
            
            for col_name, min_width in min_widths.items():
                if col_name in headers:
                    col_idx = headers.index(col_name)
                    resize_requests.append({
                        'updateDimensionProperties': {
                            'range': {
                                'sheetId': sheet.id,
                                'dimension': 'COLUMNS',
                                'startIndex': col_idx,
                                'endIndex': col_idx + 1
                            },
                            'properties': {
                                'pixelSize': min_width
                            },
                            'fields': 'pixelSize'
                        }
                    })
            
            # Execute column width updates first
            if resize_requests:
                sheets_client.spreadsheet.batch_update({'requests': resize_requests})
            
            # Apply text wrapping to the entire row
            sheet.format(f'A{row_number}:{col_index_to_letter(len(headers)-1)}{row_number}', {
                'wrapStrategy': 'WRAP',
                'verticalAlignment': 'TOP'
            })
            
            # Auto-resize row height to fit wrapped content (do this AFTER wrapping)
            sheets_client.spreadsheet.batch_update({
                'requests': [{
                    'autoResizeDimensions': {
                        'dimensions': {
                            'sheetId': sheet.id,
                            'dimension': 'ROWS',
                            'startIndex': row_number - 1,  # 0-indexed
                            'endIndex': row_number
                        }
                    }
                }]
            })
        except Exception as format_error:
            print(f"Warning: Could not format row {row_number}: {format_error}")
        
        action = 'Updated' if is_update else 'Added'
        flash(f'✓ {action} apartment: {data["address"]} (Row {row_number})', 'success')
        return redirect(url_for('index'))
    
    except Exception as e:
        flash(f'Error adding apartment: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/delete/<int:row_number>', methods=['POST'])
def delete_apartment(row_number):
    """Delete an apartment from the sheet"""
    try:
        sheet = sheets_client.spreadsheet.worksheet(sheets_client.MAIN_SHEET_NAME)
        sheet.delete_rows(row_number)
        flash(f'✓ Deleted apartment from row {row_number}', 'success')
        return jsonify({'success': True})
    except Exception as e:
        flash(f'Error deleting apartment: {str(e)}', 'error')
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/save_apartment_edits/<int:row_number>', methods=['POST'])
def save_apartment_edits(row_number):
    """Save manual edits to apartment scores and recalculate weighted score"""
    try:
        from main import ApartmentAnalyzer
        from analyzers.scoring_engine import build_scorecard
        from datetime import datetime
        
        edits = request.get_json()
        
        # Get current apartment data
        records = sheets_client.read_main_sheet()
        if not (0 <= row_number - 2 < len(records)):
            return jsonify({'error': 'Apartment not found'}), 404
        
        apartment = records[row_number - 2]
        original_score = apartment.get(config.SHEET_COLUMNS['weighted_score'], 0)
        
        # Track what changed for logging
        changes = []
        
        # Map of edit field names to sheet column names
        edit_field_mapping = {
            'commute_you': 'commute_duration',
            'commute_partner': 'commute_duration_partner',
            'safety_opendata': 'safety_score_opendata',
            'natural_light': 'natural_light',
            'desk_space': 'desk_space_quality',
            'quietness': 'quietness_score',
            'kitchen': 'kitchen_quality',
            'double_pane_windows': 'double_pane_windows',
            'study_door_type': 'study_door_type',
            'restaurants': 'restaurants_nearby',
            'cafes': 'cafes_nearby',
            'parks': 'parks_nearby',
            'street_ease': 'street_parking_ease',
            'visitor_ease': 'visitor_parking_ease',
            'gym_quality': 'gym_quality'
        }
        
        # Apply edits to apartment data
        for edit_key, new_value in edits.items():
            if edit_key in edit_field_mapping:
                data_key = edit_field_mapping[edit_key]
                sheet_column = config.SHEET_COLUMNS.get(data_key, data_key)
                old_value = apartment.get(sheet_column)
                
                if old_value != new_value:
                    # Update with sheet column name (for display)
                    apartment[sheet_column] = new_value
                    # Also update with data key (for write_apartment_data)
                    apartment[data_key] = new_value
                    changes.append({
                        'field': data_key,
                        'old_value': old_value,
                        'new_value': new_value
                    })
        
        # Convert apartment data to format expected by build_scorecard
        # build_scorecard expects lowercase underscore keys, but apartment has sheet column names
        apartment_for_scoring = {}
        for data_key, sheet_column in config.SHEET_COLUMNS.items():
            if sheet_column in apartment:
                apartment_for_scoring[data_key] = apartment[sheet_column]
        
        # Add the edited values using their data keys
        for edit_key, new_value in edits.items():
            if edit_key in edit_field_mapping:
                data_key = edit_field_mapping[edit_key]
                apartment_for_scoring[data_key] = new_value
        
        # Recalculate weighted score with edited values
        try:
            scorecard = build_scorecard(apartment_for_scoring)
            new_score = scorecard.calculate_total()
            apartment[config.SHEET_COLUMNS['weighted_score']] = round(new_score, 2)
            apartment_for_scoring['weighted_score'] = round(new_score, 2)
            apartment[config.SHEET_COLUMNS['last_updated']] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            apartment_for_scoring['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"Error recalculating score: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error recalculating score: {str(e)}'}), 500
        
        # Write updated data back to sheet using the properly formatted data
        try:
            sheets_client.write_apartment_data(row_number, apartment_for_scoring)
        except Exception as e:
            print(f"Error writing to sheet: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error writing to sheet: {str(e)}'}), 500
        
        # Log the edits
        if changes:
            try:
                sheets_client.log_user_edit(
                    apartment_address=apartment.get(config.SHEET_COLUMNS['address'], 'Unknown'),
                    changes=changes,
                    original_score=original_score,
                    new_score=new_score
                )
            except Exception as e:
                print(f"Warning: Could not log edit: {e}")
        
        print(f"Saved edits successfully. Old score: {original_score}, New score: {new_score}")
        
        return jsonify({
            'success': True,
            'new_score': round(new_score, 2),
            'changes_count': len(changes)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/update_gym_transport_mode/<int:row_number>', methods=['POST'])
def update_gym_transport_mode(row_number):
    """Update the gym transport mode preference for an apartment"""
    try:
        from main import ApartmentAnalyzer
        from analyzers.scoring_engine import build_scorecard
        from datetime import datetime
        
        data = request.get_json()
        transport_mode = data.get('transport_mode', 'walk')
        effective_time = data.get('effective_time')
        
        # Get current apartment data
        records = sheets_client.read_main_sheet()
        if not (0 <= row_number - 2 < len(records)):
            return jsonify({'error': 'Apartment not found'}), 404
        
        apartment = records[row_number - 2]
        
        # Update transport mode in apartment data
        apartment_for_scoring = _normalize_sheet_row_for_scoring(apartment)
        apartment_for_scoring['gym_transport_mode'] = transport_mode
        apartment_for_scoring['gym_effective_time_mins'] = effective_time
        
        # Recalculate score with new transport mode
        scorecard = build_scorecard(apartment_for_scoring)
        new_score = scorecard.calculate_total()
        apartment_for_scoring['weighted_score'] = round(new_score, 2)
        apartment_for_scoring['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Write updated data back to sheet
        sheets_client.write_apartment_data(row_number, apartment_for_scoring)
        
        print(f"✓ Updated gym transport mode to '{transport_mode}' for row {row_number}, new score: {new_score:.2f}")
        
        return jsonify({
            'success': True,
            'new_score': round(new_score, 2),
            'transport_mode': transport_mode
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/run_analysis', methods=['POST'])
def run_analysis():
    """Run analysis on all apartments"""
    try:
        import sys
        from main import ApartmentAnalyzer
        
        # Flush stdout to ensure prints appear in Flask logs
        sys.stdout.flush()
        
        print("\n" + "="*70)
        print("RUNNING ANALYSIS")
        print("="*70)
        sys.stdout.flush()
        
        analyzer = ApartmentAnalyzer()
        
        # Use the centralized method that checks for missing score ranges
        apartments_to_analyze = sheets_client.get_apartments_needing_analysis()
        
        sys.stdout.flush()
        
        print(f"\nFound {len(apartments_to_analyze)} apartments to analyze")
        for apt in apartments_to_analyze:
            reason = apt.get('_analysis_reason', 'unknown')
            address = apt.get(config.SHEET_COLUMNS['address'], 'Unknown')
            print(f"  {apt['_row_number']}. {address[:50]} - {reason}")
        
        sys.stdout.flush()
        
        results = []
        for apartment in apartments_to_analyze:
            try:
                result = analyzer.analyze_apartment(apartment)
                if result and 'error' not in result:
                    # Write each result back to the sheet
                    row_number = apartment.get('_row_number')
                    if row_number:
                        print(f"Writing analysis results to row {row_number}")
                        
                        # Rate limiting: Sleep between writes to avoid hitting API limits
                        import time
                        time.sleep(1.2)
                        
                        # Retry logic with exponential backoff
                        max_retries = 3
                        retry_delay = 5
                        for attempt in range(max_retries):
                            try:
                                sheets_client.write_apartment_data(row_number, result)
                                break  # Success
                            except Exception as write_error:
                                error_str = str(write_error)
                                if 'RATE_LIMIT_EXCEEDED' in error_str or '429' in error_str:
                                    if attempt < max_retries - 1:
                                        wait_time = retry_delay * (2 ** attempt)
                                        print(f"  ⏳ Rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                                        time.sleep(wait_time)
                                    else:
                                        print(f"  ❌ Failed to write after {max_retries} attempts")
                                        raise
                                else:
                                    raise
                    else:
                        print(f"⚠️  Warning: No row number found for apartment: {apartment.get('address')}")
                    results.append(result)
            except Exception as e:
                print(f"Error analyzing apartment: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Update visualizations
        if results:
            sheets_client.update_scatter_plot_data()
            
            # Build criteria results for matrix
            criteria_results = []
            for result in results:
                if result.get('scorecard'):
                    criteria_result = {
                        'address': result.get('address', ''),
                        'components': result['scorecard'].get('components', {}),
                        'weighted_score': result.get('weighted_score', 0)
                    }
                    criteria_results.append(criteria_result)
            
            if criteria_results:
                sheets_client.update_criteria_matrix(criteria_results)
        
        # Small delay to allow Google Sheets API to propagate writes
        # This ensures data is available when switching to Analysis tab
        import time
        time.sleep(1.5)
        
        message = f"Successfully analyzed {len(results)} apartment(s)"
        return jsonify({
            'success': True, 
            'analyzed': len(results),
            'message': message
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/reanalyze/<int:row_number>', methods=['POST'])
def reanalyze_apartment(row_number):
    """Force reanalysis of a specific apartment"""
    try:
        import sys
        from main import ApartmentAnalyzer
        
        sys.stdout.flush()
        
        print("\n" + "="*70)
        print(f"REANALYZING APARTMENT AT ROW {row_number}")
        print("="*70)
        sys.stdout.flush()
        
        # Get the apartment data
        all_records = sheets_client.read_main_sheet()
        if row_number - 2 >= len(all_records):
            return jsonify({'error': 'Invalid row number', 'success': False}), 400
        
        apartment = all_records[row_number - 2]  # -2 for header and 1-indexing
        apartment['_row_number'] = row_number
        
        # Skip apartments that are no longer available
        availability_status = apartment.get(config.SHEET_COLUMNS.get("availability_status", ""), "").lower()
        if availability_status in ['rented', 'removed', 'unavailable', 'off market', 'off-market']:
            return jsonify({
                'error': f'This apartment is no longer available (Status: {availability_status})',
                'success': False
            }), 400
        
        address = apartment.get(config.SHEET_COLUMNS['address'], 'Unknown')
        print(f"Analyzing: {address}")
        sys.stdout.flush()
        
        # Run analysis
        analyzer = ApartmentAnalyzer()
        result = analyzer.analyze_apartment(apartment, force_refresh=True)
        
        if result and 'error' not in result:
            print(f"Writing analysis results to row {row_number}")
            sheets_client.write_apartment_data(row_number, result)
            
            # Update visualizations
            sheets_client.update_scatter_plot_data()
            
            # Update criteria matrix for this apartment
            if result.get('scorecard'):
                criteria_result = {
                    'address': result.get('address', ''),
                    'components': result['scorecard'].get('components', {}),
                    'weighted_score': result.get('weighted_score', 0)
                }
                # Note: We'd need to rebuild the entire matrix, so let's just update scatter for now
            
            print(f"✓ Reanalysis complete for {address}")
            sys.stdout.flush()
            
            import time
            time.sleep(1.0)
            
            return jsonify({
                'success': True,
                'address': address,
                'weighted_score': result.get('weighted_score', 0)
            })
        else:
            error_msg = result.get('error', 'Unknown error') if result else 'Analysis failed'
            return jsonify({'error': error_msg, 'success': False}), 500
            
    except Exception as e:
        print(f"Error reanalyzing apartment: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/analyze_edits', methods=['GET'])
def analyze_edits():
    """Analyze user edits and return weight adjustment suggestions"""
    try:
        from analyzers.weight_adjuster import WeightAdjuster
        
        # Get edit history from User Edits Log
        edit_history = sheets_client.get_user_edits()
        
        if not edit_history:
            return jsonify({
                'success': True,
                'suggestions': {},
                'message': 'No edit history found. Make some manual edits first to get weight suggestions.'
            })
        
        # Create weight adjuster and analyze
        adjuster = WeightAdjuster(edit_history)
        suggestions = adjuster.suggest_weight_adjustments()
        
        # Get summary text
        summary = adjuster.get_adjustment_summary()
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'summary': summary,
            'edit_count': len(edit_history)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/apply_weight_adjustments', methods=['POST'])
def apply_weight_adjustments():
    """Apply suggested weight adjustments (saves to a Scoring Weights sheet)"""
    try:
        from analyzers.weight_adjuster import WeightAdjuster
        
        # Get the suggestions from request
        data = request.get_json()
        suggestions = data.get('suggestions', {})
        
        if not suggestions:
            return jsonify({'error': 'No suggestions provided', 'success': False}), 400
        
        # Get edit history to create adjuster
        edit_history = sheets_client.get_user_edits()
        adjuster = WeightAdjuster(edit_history)
        
        # Apply adjustments
        new_weights = adjuster.apply_weight_adjustments(suggestions)
        
        # Save to Scoring Weights sheet (for now, just return them)
        # TODO: Implement persistent weight storage in Google Sheets
        # For now, we'll just return the new weights for manual update
        
        return jsonify({
            'success': True,
            'new_weights': new_weights,
            'message': 'Weight adjustments calculated. To apply permanently, update config.py SCORING_WEIGHTS with these values.'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/get_analysis_data', methods=['GET'])
def get_analysis_data():
    """Get all analysis data for visualization"""
    try:
        print("\n[DEBUG] get_analysis_data: Starting...")
        records = sheets_client.read_main_sheet()
        print(f"[DEBUG] get_analysis_data: Read {len(records)} records from sheet")
        
        scatter_data = []
        unanalyzed_data = []
        
        # Get availability column name
        availability_col = config.SHEET_COLUMNS.get("availability_status")
        
        for i, r in enumerate(records):
            address = r.get(config.SHEET_COLUMNS['address'], 'Unknown')
            
            # Skip if no address
            if not address or not address.strip():
                continue
            
            # Skip unavailable apartments
            if availability_col:
                status = r.get(availability_col, "").strip().lower()
                if status and status != "available":
                    print(f"[DEBUG] Skipping unavailable apartment: {address} (status: {status})")
                    continue
            
            weighted_score = r.get(config.SHEET_COLUMNS['weighted_score'])
            
            if weighted_score:
                try:
                    # Check data completeness
                    # Core required fields for accurate scoring
                    required_fields = [
                        'parking_type',
                        'parking_enclosure',
                        'laundry_type',
                        'manual_safety',
                        'visitor_parking_ease',
                        'street_parking_ease',
                        # WFH Quality fields
                        'natural_light',
                        'desk_space_quality',
                        'work_area_quietness',
                        'kitchen_quality',
                        'double_pane_windows',
                        'study_door_type',
                    ]
                    
                    missing_fields = []
                    for field in required_fields:
                        col_name = config.SHEET_COLUMNS.get(field)
                        if col_name:
                            value = r.get(col_name)
                            # Check if value is empty, None, or just whitespace
                            if not value or (isinstance(value, str) and not value.strip()):
                                missing_fields.append(field.replace('_', ' ').title())
                    
                    # Check if multiple options are selected (uncertainty)
                    has_uncertainty = False
                    score_min = r.get(config.SHEET_COLUMNS['score_min'])
                    score_max = r.get(config.SHEET_COLUMNS['score_max'])
                    if score_min and score_max:
                        try:
                            if abs(float(score_max) - float(score_min)) > 0.5:  # Significant range
                                has_uncertainty = True
                        except:
                            pass
                    
                    # Determine data quality
                    is_complete = len(missing_fields) == 0
                    
                    # Calculate effective price (rent + parking cost)
                    base_price = float(r.get(config.SHEET_COLUMNS['price'], 0) or 0)
                    parking_cost = float(r.get(config.SHEET_COLUMNS['parking_cost'], 0) or 0)
                    effective_price = base_price + parking_cost
                    
                    scatter_data.append({
                        'address': address,
                        'price': effective_price,  # Use effective price for plotting
                        'base_price': base_price,  # Keep base price for reference
                        'parking_cost': parking_cost,
                        'score': float(weighted_score),
                        'score_min': float(r.get(config.SHEET_COLUMNS['score_min'], weighted_score) or weighted_score),
                        'score_max': float(r.get(config.SHEET_COLUMNS['score_max'], weighted_score) or weighted_score),
                        'tour_questions': r.get(config.SHEET_COLUMNS['tour_questions'], ''),
                        'is_complete': is_complete,
                        'has_uncertainty': has_uncertainty,
                        'missing_fields': missing_fields,
                        'row': i + 2,
                        'needs_analysis': False
                    })
                except (ValueError, TypeError):
                    continue
            else:
                # Apartment has no score - needs analysis
                # Calculate effective price (rent + parking cost)
                base_price = float(r.get(config.SHEET_COLUMNS['price'], 0) or 0)
                parking_cost = float(r.get(config.SHEET_COLUMNS['parking_cost'], 0) or 0)
                effective_price = base_price + parking_cost
                
                unanalyzed_data.append({
                    'address': address,
                    'price': effective_price,  # Use effective price for plotting
                    'base_price': base_price,  # Keep base price for reference
                    'parking_cost': parking_cost,
                    'score': None,
                    'score_min': None,
                    'score_max': None,
                    'tour_questions': r.get(config.SHEET_COLUMNS['tour_questions'], ''),
                    'is_complete': False,
                    'has_uncertainty': False,
                    'missing_fields': ['Analysis not run'],
                    'row': i + 2,
                    'needs_analysis': True
                })
        
        # Sort analyzed apartments by score descending
        ranked_analyzed = sorted(scatter_data, key=lambda x: x['score'], reverse=True)
        
        # Append unanalyzed apartments at the bottom
        ranked = ranked_analyzed + unanalyzed_data
        
        # Build comparison matrix with key attributes for each apartment
        comparison_data = []
        for apt_data in ranked:
            # Get the full record for this apartment
            record_idx = apt_data['row'] - 2
            if record_idx < len(records):
                r = records[record_idx]
                
                comparison_data.append({
                    'address': apt_data['address'],
                    'row': apt_data['row'],
                    'price': apt_data['price'],  # This is effective price (rent + parking)
                    'base_price': apt_data.get('base_price', apt_data['price']),  # Base rent without parking
                    'parking_cost': apt_data.get('parking_cost', 0),
                    'score': apt_data['score'],
                    'score_min': apt_data['score_min'],
                    'score_max': apt_data['score_max'],
                    'value_ratio': round(apt_data['score'] / (apt_data['price'] / 1000), 2) if apt_data.get('score') and apt_data['price'] > 0 else 0,  # Score per $1000 of effective price
                    'is_complete': apt_data['is_complete'],
                    
                    # Component scores
                    'commute_score': r.get(config.SHEET_COLUMNS.get('commute_score')),
                    'safety_score': r.get(config.SHEET_COLUMNS.get('combined_safety')),
                    'wfh_score': r.get(config.SHEET_COLUMNS.get('wfh_quality_score')),
                    'happening_score': r.get(config.SHEET_COLUMNS.get('happening_score')),
                    'parking_score': r.get(config.SHEET_COLUMNS.get('parking_score')),
                    'gym_score': r.get(config.SHEET_COLUMNS.get('gym_score')),
                    'laundry_score': r.get(config.SHEET_COLUMNS.get('laundry_score')),
                    'space_luxury_score': r.get(config.SHEET_COLUMNS.get('space_luxury_score')),
                    
                    # Key attributes
                    'bedrooms': r.get(config.SHEET_COLUMNS.get('bedrooms')),
                    'bathrooms': r.get(config.SHEET_COLUMNS.get('bathrooms')),
                    'sqft': r.get(config.SHEET_COLUMNS.get('sqft')),
                    'commute_you': r.get(config.SHEET_COLUMNS.get('commute_time_you')),
                    'commute_partner': r.get(config.SHEET_COLUMNS.get('commute_time_partner')),
                    'natural_light': r.get(config.SHEET_COLUMNS.get('natural_light')),
                    'desk_space': r.get(config.SHEET_COLUMNS.get('desk_space_quality')),
                    'kitchen_quality': r.get(config.SHEET_COLUMNS.get('kitchen_quality')),
                    'parking_type': r.get(config.SHEET_COLUMNS.get('parking_type')),
                    'laundry_type': r.get(config.SHEET_COLUMNS.get('laundry_type')),
                    'rent_control': r.get(config.SHEET_COLUMNS.get('rent_control')),
                })
        
        print(f"[DEBUG] get_analysis_data: Processed {len(scatter_data)} analyzed, {len(unanalyzed_data)} unanalyzed")
        
        return jsonify({
            'scatter': scatter_data,
            'ranked': ranked,
            'comparison': comparison_data,
            'success': True
        })
    except Exception as e:
        print(f"[ERROR] get_analysis_data failed: {e}")
        import traceback
        traceback.print_exc()
        
        error_str = str(e)
        
        # Check if this is a rate limit error (429)
        if 'RATE_LIMIT_EXCEEDED' in error_str or '429' in error_str or 'Quota exceeded' in error_str:
            import datetime
            now = datetime.datetime.now()
            next_minute = (now + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)
            wait_seconds = int((next_minute - now).total_seconds()) + 1
            
            wait_display = f"{wait_seconds} seconds" if wait_seconds < 60 else f"{wait_seconds // 60} minute(s)"
            
            return jsonify({
                'error': f'Google Sheets API rate limit exceeded. Please try again in {wait_display}.',
                'error_type': 'rate_limit',
                'wait_seconds': wait_seconds,
                'success': False
            }), 429
        
        # Check if this is a service unavailable error (503)
        if '503' in error_str or 'UNAVAILABLE' in error_str or 'service is currently unavailable' in error_str:
            return jsonify({
                'error': 'Google Sheets API is temporarily unavailable. Retrying automatically...',
                'error_type': 'service_unavailable',
                'wait_seconds': 3,  # Short retry for transient errors
                'success': False
            }), 503
        
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/stats')
def stats():
    """Show current statistics"""
    try:
        records = sheets_client.read_main_sheet()
        return jsonify({
            'total_apartments': len(records),
            'analyzed': len([r for r in records if r.get(config.SHEET_COLUMNS['weighted_score'])]),
            'pending': len([r for r in records if not r.get(config.SHEET_COLUMNS['weighted_score'])])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/check_schema', methods=['GET'])
def admin_check_schema():
    """Check schema differences between config and sheet"""
    try:
        from manage_sheet_columns import SheetColumnManager
        
        manager = SheetColumnManager()
        expected = manager.get_expected_columns()
        current = manager.get_current_columns()
        differences = manager.analyze_differences()
        
        return jsonify({
            'success': True,
            'expected_count': len(expected),
            'current_count': len(current),
            'expected': expected,
            'current': current,
            'missing': [{'name': col, 'after': expected[expected.index(col) - 1] if expected.index(col) > 0 else None} 
                       for col in differences['missing']],
            'extra': differences['extra'],
            'misplaced': differences['misplaced'],
            'in_sync': not (differences['missing'] or differences['extra'] or differences['misplaced'])
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/admin/sync_schema', methods=['POST'])
def admin_sync_schema():
    """Sync schema by adding missing columns"""
    try:
        from manage_sheet_columns import SheetColumnManager
        
        manager = SheetColumnManager()
        differences = manager.analyze_differences()
        
        if not differences['missing']:
            return jsonify({
                'success': True,
                'added': [],
                'message': 'Sheet is already up to date'
            })
        
        # Add missing columns
        expected = manager.get_expected_columns()
        current = manager.get_current_columns()
        added = []
        
        for col_name in differences['missing']:
            # Find where this column should be inserted
            expected_idx = expected.index(col_name)
            
            # Find the insertion point in current sheet
            insert_after_idx = 0
            for i in range(expected_idx - 1, -1, -1):
                prev_col = expected[i]
                if prev_col in current:
                    insert_after_idx = current.index(prev_col) + 1
                    break
            
            col_letter = manager._col_index_to_letter(insert_after_idx)
            
            # Insert column
            manager.sheet.spreadsheet.batch_update({
                'requests': [{
                    'insertDimension': {
                        'range': {
                            'sheetId': manager.sheet.id,
                            'dimension': 'COLUMNS',
                            'startIndex': insert_after_idx,
                            'endIndex': insert_after_idx + 1
                        }
                    }
                }]
            })
            
            # Set header
            print(f"  Adding column: {col_name} at position {insert_after_idx + 1} (column {col_letter})")
            manager.sheet.update(f'{col_letter}1', [[col_name]])
            
            # Format header
            manager.sheet.format(f'{col_letter}1', {
                'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                'horizontalAlignment': 'CENTER'
            })
            print(f"  ✓ Header formatted")
            
            # Set default values only for rows with addresses (primary key)
            if manager.sheet.row_count > 1:
                # Get the Address column to check which rows have data
                address_col_name = config.SHEET_COLUMNS.get("address", "Address")
                current_headers = manager.get_current_columns()
                
                if address_col_name in current_headers:
                    address_col_idx = current_headers.index(address_col_name)
                    
                    # Get all addresses
                    all_addresses = manager.sheet.col_values(address_col_idx + 1)
                    
                    # Build list of updates only for rows with addresses
                    default_value = 0 if ('cost' in col_name.lower() or 'score' in col_name.lower()) else ''
                    updates = []
                    
                    # Start from index 1 (skip header at index 0)
                    for idx, address in enumerate(all_addresses[1:], start=2):
                        if address and address.strip():  # Only if address exists
                            updates.append({
                                'range': f'{col_letter}{idx}',
                                'values': [[default_value]]
                            })
                    
                    # Batch update all rows with addresses
                    if updates:
                        manager.sheet.batch_update(updates)
                        print(f"    ✓ Set default values for {len(updates)} row(s) with addresses")
                    else:
                        print(f"    ℹ️  No rows with addresses found, skipping default values")
                else:
                    print(f"    ⚠️  Warning: Address column not found, skipping default values")
            
            # Update current list for next iteration
            current.insert(insert_after_idx, col_name)
            
            added.append({
                'name': col_name,
                'position': insert_after_idx + 1
            })
        
        return jsonify({
            'success': True,
            'added': added,
            'message': f'Successfully added {len(added)} column(s)'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/clear_wfh/<int:row_number>', methods=['POST'])
def clear_wfh(row_number):
    """Clear WFH-related fields for a specific apartment row."""
    try:
        sheets_client.clear_wfh_fields(row_number)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/request_shutdown', methods=['POST'])
def admin_request_shutdown():
    """Request graceful shutdown of current analysis"""
    global shutdown_requested
    shutdown_requested = True
    return jsonify({
        'success': True,
        'message': 'Shutdown requested. Finishing current apartment...'
    })


@app.route('/admin/force_recalculate', methods=['POST'])
def admin_force_recalculate():
    """
    Force recalculation of specific score components by clearing them in the sheet.
    Also clears the cache to ensure fresh API calls (e.g., for updated Claude prompts).
    
    Request body:
    {
        "components": ["gym", "laundry", "parking", "happening", "all"],  // Array of components to recalculate
        "addresses": ["addr1", "addr2"] or "all"
    }
    
    Available components:
    - "gym": Clear gym scores and travel time data (walk/bike)
    - "laundry": Clear laundry scores
    - "parking": Clear parking scores
    - "happening": Clear happening scores (restaurants, cafes, parks)
    - "safety": Clear safety scores
    - "commute": Clear commute data
    - "wfh": Clear WFH quality scores
    - "all": Clear all scores and force full recalculation
    """
    try:
        data = request.json
        components = data.get('components', ['all'])
        addresses = data.get('addresses', 'all')
        
        # Ensure components is a list
        if isinstance(components, str):
            components = [components]
        
        # Clear cache to ensure fresh API calls (especially for Claude prompt changes)
        print("\n🗑️  Clearing cache for fresh analysis...")
        if location_analyzer and hasattr(location_analyzer, 'cache'):
            cleared_entries = location_analyzer.cache.clear_all()
            print(f"  ✓ Cleared {cleared_entries} cache entries")
        
        # Get all apartments
        records = sheets_client.read_main_sheet()
        
        # Filter by addresses if specified
        if addresses != 'all':
            records = [r for r in records if r.get(config.SHEET_COLUMNS["address"]) in addresses]
        
        # Determine which columns to clear based on components
        columns_to_clear = []
        component_descriptions = []
        
        if 'all' in components:
            # Clear everything for full recalculation
            columns_to_clear.extend([
                config.SHEET_COLUMNS["gym_score"],
                config.SHEET_COLUMNS["gym_walk_time_mins"],
                config.SHEET_COLUMNS["gym_bike_time_mins"],
                config.SHEET_COLUMNS["gym_transport_mode"],
                config.SHEET_COLUMNS["gym_effective_time_mins"],
                config.SHEET_COLUMNS["laundry_score"],
                config.SHEET_COLUMNS["parking_score"],
                config.SHEET_COLUMNS["happening_score"],
                config.SHEET_COLUMNS["safety_score_opendata"],
                config.SHEET_COLUMNS["combined_safety"],
                config.SHEET_COLUMNS["wfh_quality_score"],
                config.SHEET_COLUMNS["commute_time_you"],
                config.SHEET_COLUMNS["commute_route"],
                config.SHEET_COLUMNS["score_min"],
                config.SHEET_COLUMNS["score_max"],
                config.SHEET_COLUMNS["weighted_score"]
            ])
            component_descriptions.append("all components")
        else:
            # Clear specific components
            if 'gym' in components:
                columns_to_clear.extend([
                    config.SHEET_COLUMNS["gym_score"],
                    config.SHEET_COLUMNS["gym_walk_time_mins"],
                    config.SHEET_COLUMNS["gym_bike_time_mins"],
                    config.SHEET_COLUMNS["gym_transport_mode"],
                    config.SHEET_COLUMNS["gym_effective_time_mins"],
                ])
                component_descriptions.append("gym (walk/bike times)")
            
            if 'laundry' in components:
                columns_to_clear.append(config.SHEET_COLUMNS["laundry_score"])
                component_descriptions.append("laundry")
            
            if 'parking' in components:
                columns_to_clear.append(config.SHEET_COLUMNS["parking_score"])
                component_descriptions.append("parking")
            
            if 'happening' in components:
                columns_to_clear.extend([
                    config.SHEET_COLUMNS["happening_score"],
                    config.SHEET_COLUMNS["restaurants_nearby"],
                    config.SHEET_COLUMNS["cafes_nearby"],
                    config.SHEET_COLUMNS["parks_nearby"],
                ])
                component_descriptions.append("happening")
            
            if 'safety' in components:
                columns_to_clear.extend([
                    config.SHEET_COLUMNS["safety_score_opendata"],
                    config.SHEET_COLUMNS["combined_safety"],
                ])
                component_descriptions.append("safety")
            
            if 'commute' in components:
                columns_to_clear.extend([
                    config.SHEET_COLUMNS["commute_time_you"],
                    config.SHEET_COLUMNS["commute_route"],
                    config.SHEET_COLUMNS["commute_time_partner"],
                ])
                component_descriptions.append("commute")
            
            if 'wfh' in components:
                columns_to_clear.append(config.SHEET_COLUMNS["wfh_quality_score"])
                component_descriptions.append("WFH quality")
            
            # Only clear aggregate scores if recalculating ALL components
            # For partial recalc, we'll re-score using existing components
            if len(components) >= 6:  # If most/all components selected
                columns_to_clear.extend([
                    config.SHEET_COLUMNS["score_min"],
                    config.SHEET_COLUMNS["score_max"],
                    config.SHEET_COLUMNS["weighted_score"]
                ])
        
        # Get worksheet
        sheet = sheets_client.spreadsheet.worksheet(sheets_client.MAIN_SHEET_NAME)
        header_row = sheet.row_values(1)
        
        col_indices = {}
        for col_name in columns_to_clear:
            if col_name in header_row:
                col_indices[col_name] = header_row.index(col_name) + 1  # 1-indexed
        
        # Get address column for finding rows
        address_col_idx = header_row.index(config.SHEET_COLUMNS["address"]) + 1
        address_col = sheet.col_values(address_col_idx)
        
        # Build batch update list (to avoid rate limiting)
        batch_updates = []
        cleared_count = 0
        
        for record in records:
            address = record.get(config.SHEET_COLUMNS["address"])
            if not address:
                continue
            
            # Find row number (skip header row)
            row_num = None
            for i, row_address in enumerate(address_col[1:], start=2):
                if row_address == address:
                    row_num = i
                    break
            
            if row_num:
                # Add updates for each column for this row
                for col_name, col_idx in col_indices.items():
                    col_letter = sheets_client._col_index_to_letter(col_idx - 1)
                    batch_updates.append({
                        'range': f'{col_letter}{row_num}',
                        'values': [['']]
                    })
                    print(f"  Will clear {col_name} for row {row_num} ({address[:50]})")
                
                cleared_count += 1
        
        # Execute batch update (1 API call instead of N)
        if batch_updates:
            print(f"\n📝 Executing batch update with {len(batch_updates)} cell updates...")
            # Apply rate limiting before batch update
            from utils.rate_limiter import get_rate_limiter
            rate_limiter = get_rate_limiter()
            rate_limiter.wait_if_needed('google_sheets_write')
            
            # Use batch_update to clear all values at once
            sheet.batch_update(batch_updates, value_input_option='USER_ENTERED')
            print(f"  ✓ Batch update complete!")
        
        # For partial recalc, re-analyze only the specified components
        is_partial_recalc = 'all' not in components and len(components) < 6
        if is_partial_recalc:
            print(f"\n🔄 Starting partial recalculation for: {', '.join(components)}")
            print(f"⏱️  Rate limiting enabled: 1.2s delay between writes to avoid API quota (50 writes/min)")
            import sys
            from main import ApartmentAnalyzer
            sys.stdout.flush()
            
            analyzer = ApartmentAnalyzer()
            
            # Re-analyze only cleared apartments
            analyzed_count = 0
            for record in records:
                # Check if shutdown was requested
                global shutdown_requested
                if shutdown_requested:
                    print(f"\n⚠️  Shutdown requested. Stopping after {analyzed_count} apartments.")
                    message = f'⚠️ Interrupted: Recalculated {", ".join(component_descriptions)} for {analyzed_count}/{len(records)} apartment(s).'
                    break
                
                address = record.get(config.SHEET_COLUMNS["address"])
                if not address:
                    continue
                
                # Skip apartments that are no longer available
                availability_status = record.get(config.SHEET_COLUMNS.get("availability_status", ""), "").lower()
                if availability_status in ['rented', 'removed', 'unavailable', 'off market', 'off-market']:
                    print(f"  ⏭️  Skipping {address[:50]} (Status: {availability_status})")
                    continue
                
                # Find row number
                row_num = None
                for i, row_address in enumerate(address_col[1:], start=2):
                    if row_address == address:
                        row_num = i
                        break
                
                if row_num:
                    print(f"\n📍 Re-analyzing row {row_num}: {address[:50]} ({analyzed_count + 1}/{len(records)})")
                    try:
                        # Reload fresh data after clearing
                        fresh_records = sheets_client.read_main_sheet()
                        fresh_record = fresh_records[row_num - 2]
                        
                        # Analyze (will only recalculate specified components)
                        result = analyzer.analyze_apartment(fresh_record, force_refresh=False, 
                                                           components_to_recalc=components)
                        
                        if result and 'error' not in result:
                            # Rate limiting: Google Sheets API allows 60 write requests per minute
                            # Sleep for 1.2 seconds between writes to stay safely under the limit (50 writes/min)
                            import time
                            time.sleep(1.2)
                            
                            # Retry logic with exponential backoff for rate limit errors
                            max_retries = 3
                            retry_delay = 5
                            for attempt in range(max_retries):
                                try:
                                    sheets_client.write_apartment_data(row_num, result)
                                    analyzed_count += 1
                                    print(f"  ✓ Updated row {row_num}")
                                    break  # Success, exit retry loop
                                except Exception as write_error:
                                    error_str = str(write_error)
                                    if 'RATE_LIMIT_EXCEEDED' in error_str or '429' in error_str:
                                        if attempt < max_retries - 1:
                                            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                                            print(f"  ⏳ Rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                                            time.sleep(wait_time)
                                        else:
                                            print(f"  ❌ Failed to write after {max_retries} attempts due to rate limiting")
                                            raise
                                    else:
                                        # Non-rate-limit error, don't retry
                                        raise
                        else:
                            print(f"  ⚠️  Analysis failed for row {row_num}: {result.get('error', 'Unknown error')}")
                    except Exception as e:
                        print(f"  ❌ Error analyzing row {row_num}: {e}")
                        import traceback
                        traceback.print_exc()
            
            message = f'Recalculated {", ".join(component_descriptions)} for {analyzed_count} apartment(s).'
            
            # Reset shutdown flag after completion
            shutdown_requested = False
        else:
            message = f'Cleared {", ".join(component_descriptions)} for {cleared_count} apartment(s). Run analysis to recalculate.'
        
        return jsonify({
            'success': True,
            'cleared_count': cleared_count,
            'components': component_descriptions,
            'columns': list(col_indices.keys()),
            'cache_cleared': True,
            'message': message
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def open_browser():
    """Open browser after a short delay"""
    webbrowser.open('http://127.0.0.1:5001')


@app.route('/exclude_place', methods=['POST'])
def exclude_place():
    """
    Add or remove a place from the exclusion list
    
    Request body:
    {
        "action": "add" | "remove",
        "place_id": "ChIJ...",
        "place_name": "Place Name",
        "place_type": "restaurant" | "cafe" | "park",
        "reason": "Optional reason for exclusion"
    }
    """
    print("\n" + "="*80)
    print("🚫 /exclude_place endpoint called")
    print("="*80)
    
    try:
        data = request.json
        print(f"📋 Request data: {data}")
        
        action = data.get('action')
        place_id = data.get('place_id')
        
        print(f"  Action: {action}")
        print(f"  Place ID: {place_id}")
        
        if not action or not place_id:
            print(f"  ❌ Missing required fields!")
            return jsonify({'error': 'Missing required fields: action, place_id'}), 400
        
        if action == 'add':
            place_name = data.get('place_name', 'Unknown')
            place_type = data.get('place_type', 'unknown')
            reason = data.get('reason', '')
            
            print(f"  Place Name: {place_name}")
            print(f"  Place Type: {place_type}")
            print(f"  Reason: {reason}")
            print(f"  📝 Calling sheets_client.add_excluded_place()...")
            
            sheets_client.add_excluded_place(place_id, place_name, place_type, reason)
            
            print(f"  ✅ Successfully added to exclusion list!")
            print("="*80 + "\n")
            return jsonify({'success': True, 'message': f'Added {place_name} to exclusion list'})
        
        elif action == 'remove':
            print(f"  📝 Calling sheets_client.remove_excluded_place()...")
            sheets_client.remove_excluded_place(place_id)
            print(f"  ✅ Successfully removed from exclusion list!")
            print("="*80 + "\n")
            return jsonify({'success': True, 'message': 'Removed place from exclusion list'})
        
        else:
            print(f"  ❌ Invalid action: {action}")
            print("="*80 + "\n")
            return jsonify({'error': 'Invalid action. Must be "add" or "remove"'}), 400
    
    except Exception as e:
        print(f"❌ Exception in exclude_place endpoint:")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*80 + "\n")
        return jsonify({'error': str(e)}), 500


@app.route('/get_weights', methods=['GET'])
def get_weights():
    """Get current weight configuration from Settings sheet or config"""
    try:
        # Try to read from Settings sheet first
        try:
            settings_weights = sheets_client.get_weight_settings()
            if settings_weights:
                return jsonify({
                    'success': True,
                    'weights': settings_weights,
                    'source': 'google_sheets'
                })
        except Exception as e:
            print(f"Could not read from Settings sheet: {e}")
        
        # Fallback to config.SCORE_COMPONENTS
        default_weights = {}
        for component, settings in config.SCORE_COMPONENTS.items():
            weight = settings.get('weight', 0.0)
            if weight > 0:  # Only include components with non-zero weights
                default_weights[component] = weight
        
        return jsonify({
            'success': True,
            'weights': default_weights,
            'source': 'config'
        })
    except Exception as e:
        print(f"Error getting weights: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/save_weights', methods=['POST'])
def save_weights():
    """Save custom weight configuration"""
    try:
        data = request.get_json()
        weights = data.get('weights', {})
        update_config_file = data.get('update_config', False)
        
        if not weights:
            return jsonify({'error': 'No weights provided', 'success': False}), 400
        
        # Validate weights sum to 1.0 (allow small rounding errors)
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            return jsonify({
                'error': f'Weights must sum to 100% (currently {weight_sum * 100:.1f}%)',
                'success': False
            }), 400
        
        # Save to Google Sheets Settings sheet
        sheets_client.save_weight_settings(weights)
        
        # Optionally update config.py file
        if update_config_file:
            try:
                update_config_weights(weights)
            except Exception as e:
                print(f"Warning: Could not update config.py: {e}")
                # Don't fail the request if config update fails
        
        return jsonify({
            'success': True,
            'message': 'Weights saved successfully',
            'updated_config': update_config_file
        })
    except Exception as e:
        print(f"Error saving weights: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/save_commute_settings', methods=['POST'])
def save_commute_settings():
    """Save commute time settings"""
    try:
        data = request.get_json()
        am_departure = data.get('am_departure')
        pm_departure = data.get('pm_departure')
        partner_address = data.get('partner_address', '')
        partner_mode = data.get('partner_mode', 'driving')
        
        if not am_departure or not pm_departure:
            return jsonify({'error': 'AM and PM departure times are required', 'success': False}), 400
        
        # Validate time format (HH:MM)
        import re
        time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
        if not time_pattern.match(am_departure) or not time_pattern.match(pm_departure):
            return jsonify({'error': 'Invalid time format. Use HH:MM (24-hour)', 'success': False}), 400
        
        # Update config module (in-memory)
        config.AM_DEPARTURE_TIME = am_departure
        config.PM_DEPARTURE_TIME = pm_departure
        if partner_address:
            config.PARTNER_WORK_ADDRESS = partner_address
        config.PARTNER_COMMUTE_MODE = partner_mode
        
        # Optionally save to a settings file or Google Sheets
        # For now, we'll just update in-memory config
        # In the future, you could add persistence to Settings sheet
        
        # Note: Commute times would need to be recalculated for all apartments
        # For now, this just updates the settings for future calculations
        
        return jsonify({
            'success': True,
            'message': 'Commute settings saved successfully. Settings will be used for new commute calculations.',
            'settings': {
                'am_departure': am_departure,
                'pm_departure': pm_departure,
                'partner_address': partner_address,
                'partner_mode': partner_mode
            }
        })
    except Exception as e:
        print(f"Error saving commute settings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/get_commute_settings', methods=['GET'])
def get_commute_settings():
    """Get current commute settings"""
    try:
        return jsonify({
            'success': True,
            'settings': {
                'am_departure': config.AM_DEPARTURE_TIME,
                'pm_departure': config.PM_DEPARTURE_TIME,
                'partner_address': config.PARTNER_WORK_ADDRESS,
                'partner_mode': config.PARTNER_COMMUTE_MODE
            }
        })
    except Exception as e:
        print(f"Error getting commute settings: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


def update_config_weights(weights: dict):
    """Update weights in config.py file (optional feature)"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    
    # Read current config
    with open(config_path, 'r') as f:
        lines = f.readlines()
    
    # Find and update weight lines
    updated_lines = []
    current_component = None
    
    for i, line in enumerate(lines):
        # Detect which component we're in
        for component_name in weights.keys():
            if f'"{component_name}":' in line and '{' in line:
                current_component = component_name
                break
        
        # Update weight line for current component
        if current_component and '"weight":' in line:
            indent = len(line) - len(line.lstrip())
            new_weight = weights.get(current_component, 0.0)
            new_line = ' ' * indent + f'"weight": {new_weight},\n'
            updated_lines.append(new_line)
            current_component = None  # Reset after updating
        else:
            updated_lines.append(line)
    
    # Write back
    with open(config_path, 'w') as f:
        f.writelines(updated_lines)
    
    print(f"✓ Updated config.py with new weights")


if __name__ == '__main__':
    print("="*80)
    print("APARTMENT ENTRY WEB INTERFACE")
    print("="*80)
    print("\nInitializing...")
    
    if not init_clients():
        print("✗ Failed to initialize. Check your credentials and .env file.")
        exit(1)
    
    print("✓ Clients initialized")
    print("\nStarting web server...")
    print("URL: http://127.0.0.1:5001")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Open browser after 1 second
    Timer(1, open_browser).start()
    
    # Run Flask app on 127.0.0.1 explicitly (using port 5001 to avoid conflicts with Cursor IDE)
    app.run(debug=True, use_reloader=False, host='127.0.0.1', port=5001)

