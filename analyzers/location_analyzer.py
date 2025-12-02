"""
Location analyzer for apartments

Analyzes:
- Commute times and routes
- Neighborhood safety (SF OpenData crime statistics)
- Nearby amenities (gyms, restaurants, cafes, parks)
"""

import os
import requests
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import time

import config
from utils.cache import get_cache


class LocationAnalyzer:
    """Analyzer for apartment location and surroundings"""
    
    def __init__(self, google_maps_api_key: str = None):
        """
        Initialize location analyzer
        
        Args:
            google_maps_api_key: Google Maps API key
        """
        self.api_key = google_maps_api_key or config.GOOGLE_MAPS_API_KEY
        if not self.api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY not set. Please set it in .env file.")
        
        self.cache = get_cache()
    
    def analyze_location(self, address: str) -> Dict[str, Any]:
        """
        Complete location analysis for an apartment
        
        Args:
            address: Apartment address
            
        Returns:
            Dictionary with all location analysis results
        """
        result = {}
        
        # Get coordinates
        coords = self.geocode_address(address)
        if coords:
            result['latitude'] = coords[0]
            result['longitude'] = coords[1]
            
            # Get apartment elevation
            result['apartment_elevation'] = self.get_elevation(coords[0], coords[1])
        else:
            print(f"Warning: Could not geocode address: {address}")
            return result
        
        # Commute analysis
        print(f"\n📍 Analyzing commutes from: {address}")
        print(f"  Your work: {config.YOUR_WORK_ADDRESS}")
        print(f"  Partner work: {config.PARTNER_WORK_ADDRESS}")
        
        commute_details = {}
        
        if not config.YOUR_WORK_ADDRESS or config.YOUR_WORK_ADDRESS == "":
            print("  ⚠️  YOUR_WORK_ADDRESS not configured in .env file")
            result['commute_duration'] = 999
            result['commute_route'] = 'not_configured'
        else:
            commute_your_work = self.get_commute(
                address,
                config.YOUR_WORK_ADDRESS,
                mode=config.GOOGLE_MAPS_TRAVEL_MODE,
                allow_alternatives=True
            )
            result['commute_duration'] = commute_your_work.get('duration_mins', 999)
            result['commute_route'] = commute_your_work.get('route', '')
            result['route_annoyingness'] = commute_your_work.get('annoyingness', {}).get('score', None)
            commute_details['driver'] = commute_your_work
            if 'error' in commute_your_work:
                result['commute_error'] = commute_your_work['error']
        
        if not config.PARTNER_WORK_ADDRESS or config.PARTNER_WORK_ADDRESS == "":
            print("  ⚠️  PARTNER_WORK_ADDRESS not configured in .env file")
            result['commute_duration_partner'] = 999
        else:
            commute_partner_work = self.get_commute(
                address,
                config.PARTNER_WORK_ADDRESS,
                mode=config.PARTNER_COMMUTE_MODE,
                allow_alternatives=False,
                fallback_modes=[config.PARTNER_COMMUTE_FALLBACK_MODE] if config.PARTNER_COMMUTE_FALLBACK_MODE else None
            )
            result['commute_duration_partner'] = commute_partner_work.get('duration_mins', 999)
            commute_details['partner'] = commute_partner_work
            if 'error' in commute_partner_work:
                result['commute_partner_error'] = commute_partner_work['error']
        
        result['commute_details'] = commute_details
        
        # Calculate elevation gain to work (for hill access penalty)
        work_coords = self.geocode_address(config.YOUR_WORK_ADDRESS)
        if work_coords and result.get('apartment_elevation') is not None:
            work_elev_data = self.calculate_elevation_gain(coords, work_coords)
            result['elevation_to_work'] = work_elev_data['elevation_gain']
            result['on_steep_hill_from_work'] = work_elev_data['is_steep_hill']
        
        # Safety analysis
        safety_data = self.get_safety_score(coords[0], coords[1])
        result['safety_score_opendata'] = safety_data.get('safety_score', 5.0)
        result['crime_incidents'] = safety_data.get('incident_count', 0)
        
        # Store detailed crime data as JSON for the sheet
        crime_details = {
            'incident_count': safety_data.get('incident_count', 0),
            'avg_severity': safety_data.get('avg_severity', 0),
            'count_score': safety_data.get('count_score'),
            'severity_score': safety_data.get('severity_score'),
            'incident_categories': safety_data.get('incident_categories', {}),
            'search_radius_miles': 0.25,
            'baseline_incidents': 500
        }
        result['crime_details'] = crime_details
        
        # Nearby amenities
        amenities = self.get_nearby_amenities(coords[0], coords[1])
        result['restaurants_nearby'] = amenities.get('restaurants', 0)
        result['cafes_nearby'] = amenities.get('cafes', 0)
        result['parks_nearby'] = amenities.get('parks', 0)
        
        # Gym analysis
        gym_data = self.find_nearby_gyms(coords[0], coords[1])
        result['gym_within_10min'] = gym_data.get('has_nearby', False)
        result['gym_quality'] = gym_data.get('best_rating', 0.0)
        result['nearest_gym_name'] = gym_data.get('nearest_gym_name', '')
        result['nearest_gym_distance'] = gym_data.get('nearest_gym_distance', 0.0)
        
        # Calculate elevation gain to nearest gym if one exists
        if gym_data.get('nearest_gym_coords'):
            gym_coords = gym_data['nearest_gym_coords']
            gym_elev_data = self.calculate_elevation_gain(coords, gym_coords)
            result['elevation_to_gym'] = gym_elev_data['elevation_gain']
        elif result.get('apartment_elevation') is not None:
            # Fallback: estimate based on apartment elevation
            result['elevation_to_gym'] = self._estimate_gym_elevation_gain(result['apartment_elevation'])
        
        return result
    
    def geocode_address(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Geocode an address to lat/lng
        
        Args:
            address: Address string
            
        Returns:
            Tuple of (latitude, longitude) or None
        """
        cache_key = f"geocode_{address}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'address': address,
                'key': self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK' and len(data['results']) > 0:
                location = data['results'][0]['geometry']['location']
                coords = (location['lat'], location['lng'])
                self.cache.set(cache_key, coords)
                return coords
        
        except Exception as e:
            print(f"Error geocoding address {address}: {e}")
        
        return None
    
    def get_neighborhoods(self, address: str) -> List[str]:
        """
        Extract neighborhood names from address using Google Places API
        
        Args:
            address: Address string
            
        Returns:
            List of neighborhood names
        """
        cache_key = f"neighborhoods_{address}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'address': address,
                'key': self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK' and len(data['results']) > 0:
                neighborhoods = []
                for component in data['results'][0]['address_components']:
                    if 'neighborhood' in component['types'] or \
                       'sublocality' in component['types'] or \
                       'sublocality_level_1' in component['types']:
                        neighborhoods.append(component['long_name'])
                
                self.cache.set(cache_key, neighborhoods)
                return neighborhoods
        except Exception as e:
            print(f"Error getting neighborhoods: {e}")
        
        return []
    
    def get_commute(
        self,
        origin: str,
        destination: str,
        mode: str = None,
        allow_alternatives: bool = False,
        fallback_modes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get commute time and route information
        
        Args:
            origin: Origin address
            destination: Destination address
            mode: Preferred travel mode (driving, transit, walking, bicycling)
            allow_alternatives: Whether to request alternate routes (driving only)
            fallback_modes: Optional list of modes to try if the preferred mode fails
            
        Returns:
            Dictionary with commute information
        """
        travel_mode = (mode or config.GOOGLE_MAPS_TRAVEL_MODE).lower()
        modes_to_try = [travel_mode]
        if fallback_modes:
            for fallback in fallback_modes:
                if not fallback:
                    continue
                fallback_mode = fallback.lower()
                if fallback_mode not in modes_to_try:
                    modes_to_try.append(fallback_mode)
        
        cache_key = f"commute_v2_{origin}_{destination}_{'_'.join(modes_to_try)}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        last_result: Dict[str, Any] = {
            'success': False,
            'duration_mins': 999,
            'route': 'not_found',
            'error': 'No route calculated'
        }
        
        for current_mode in modes_to_try:
            try:
                print(f"\n🚗 Calculating commute ({current_mode}): {origin} → {destination}")
                
                # For driving mode, calculate both AM and PM peak times
                if current_mode == 'driving':
                    morning_ts, evening_ts = self._get_peak_departure_times()
                    print(f"  📅 Using peak times: 8:30 AM and 6:00 PM")
                    
                    # Get AM commute
                    directions_am = self._request_directions(
                        origin,
                        destination,
                        current_mode,
                        allow_alternatives and current_mode == 'driving',
                        departure_time=str(morning_ts)
                    )
                    
                    if not directions_am['success']:
                        last_result = directions_am
                        continue
                    
                    # Get PM commute
                    directions_pm = self._request_directions(
                        origin,
                        destination,
                        current_mode,
                        allow_alternatives and current_mode == 'driving',
                        departure_time=str(evening_ts)
                    )
                    
                    if not directions_pm['success']:
                        last_result = directions_pm
                        continue
                    
                    # Combine AM and PM data for each route
                    summaries_am = self._summarize_routes(directions_am['routes'], current_mode)
                    summaries_pm = self._summarize_routes(directions_pm['routes'], current_mode)
                    
                    # Combine primary route
                    combined_primary = self._combine_am_pm_routes(
                        summaries_am['primary'],
                        summaries_pm['primary']
                    )
                    
                    # Combine alternatives (match routes by key)
                    combined_alternatives = {}
                    all_route_keys = set(summaries_am['alternatives'].keys()) | set(summaries_pm['alternatives'].keys())
                    for route_key in all_route_keys:
                        am_route = summaries_am['alternatives'].get(route_key)
                        pm_route = summaries_pm['alternatives'].get(route_key)
                        if am_route and pm_route:
                            combined_alternatives[route_key] = self._combine_am_pm_routes(am_route, pm_route)
                        elif am_route:
                            # Only have AM data, duplicate it for PM
                            combined_alternatives[route_key] = self._combine_am_pm_routes(am_route, am_route)
                        else:
                            # Only have PM data, duplicate it for AM
                            combined_alternatives[route_key] = self._combine_am_pm_routes(pm_route, pm_route)
                    
                    result = {
                        'success': True,
                        'mode_used': current_mode,
                        **combined_primary,
                        'alternatives': combined_alternatives,
                    }
                else:
                    # For non-driving modes, use current time
                    directions = self._request_directions(
                        origin,
                        destination,
                        current_mode,
                        allow_alternatives and current_mode == 'driving'
                    )
                    
                    if not directions['success']:
                        last_result = directions
                        continue
                    
                    summaries = self._summarize_routes(directions['routes'], current_mode)
                    result = {
                        'success': True,
                        'mode_used': current_mode,
                        **summaries['primary'],
                        'alternatives': summaries['alternatives'],
                    }
                
                self.cache.set(cache_key, result)
                return result
            except Exception as e:
                print(f"  ❌ Exception fetching commute ({current_mode}): {e}")
                last_result = {
                    'success': False,
                    'duration_mins': 999,
                    'route': 'error',
                    'error': str(e),
                    'mode_used': current_mode
                }
        
        return last_result
    
    @staticmethod
    def _get_peak_departure_times() -> Tuple[int, int]:
        """
        Get Unix timestamps for typical peak commute times.
        Returns (morning_8:30am_tomorrow, evening_6pm_today).
        Uses next weekday to ensure we're not calculating for weekend.
        """
        now = datetime.now()
        # Find next weekday (Monday-Friday)
        target_date = now
        while target_date.weekday() >= 5:  # Saturday=5, Sunday=6
            target_date += timedelta(days=1)
        
        # Morning commute: 8:30 AM
        morning = target_date.replace(hour=8, minute=30, second=0, microsecond=0)
        if morning < now:
            morning += timedelta(days=1)
            # Make sure it's still a weekday
            while morning.weekday() >= 5:
                morning += timedelta(days=1)
        
        # Evening commute: 6:00 PM (same day as morning for consistency)
        evening = morning.replace(hour=18, minute=0, second=0, microsecond=0)
        
        morning_timestamp = int(morning.timestamp())
        evening_timestamp = int(evening.timestamp())
        
        return (morning_timestamp, evening_timestamp)
    
    @staticmethod
    def _combine_am_pm_routes(am_route: Dict[str, Any], pm_route: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine AM and PM route data, storing both durations separately plus total.
        Uses AM route for all non-duration fields (polyline, route label, etc).
        """
        combined = am_route.copy()
        
        # Store individual AM/PM durations
        combined['duration_am_mins'] = am_route['duration_mins']
        combined['duration_am_secs'] = am_route['duration_secs']
        combined['duration_pm_mins'] = pm_route['duration_mins']
        combined['duration_pm_secs'] = pm_route['duration_secs']
        
        # Calculate total daily commute (round-trip)
        combined['duration_daily_mins'] = am_route['duration_mins'] + pm_route['duration_mins']
        combined['duration_daily_secs'] = am_route['duration_secs'] + pm_route['duration_secs']
        
        # For backwards compatibility, set duration_mins to AM duration (morning commute)
        # This is what scoring engine expects for the "commute time" metric
        combined['duration_mins'] = am_route['duration_mins']
        combined['duration_secs'] = am_route['duration_secs']
        
        return combined
    
    def _request_directions(
        self,
        origin: str,
        destination: str,
        mode: str,
        allow_alternatives: bool,
        departure_time: str = 'now'
    ) -> Dict[str, Any]:
        """Call the Google Directions API for a specific mode."""
        params = {
            'origin': origin,
            'destination': destination,
            'mode': mode,
            'departure_time': departure_time,
            'key': self.api_key,
        }
        
        if mode == 'driving':
            params['traffic_model'] = config.GOOGLE_MAPS_TRAFFIC_MODEL
            if allow_alternatives:
                params['alternatives'] = 'true'
        elif mode == 'transit':
            params['transit_routing_preference'] = 'less_walking'
        
        url = "https://maps.googleapis.com/maps/api/directions/json"
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        status = data.get('status')
        print(f"  API Status ({mode}): {status}")
        
        if status == 'OK' and data.get('routes'):
            return {'success': True, 'routes': data['routes']}
        
        error_msg = data.get('error_message', status)
        print(f"  ⚠️  Directions ({mode}) failed: {error_msg}")
        return {
            'success': False,
            'error': error_msg or 'Directions API error',
            'status': status
        }
    
    def _summarize_routes(self, routes: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
        """Build summaries for the primary route plus best alternates (101/280)."""
        primary_summary = None
        alternatives: Dict[str, Dict[str, Any]] = {}
        
        for idx, route in enumerate(routes):
            summary = self._build_route_summary(route, mode)
            if idx == 0:
                primary_summary = summary
            route_key = summary['route']
            existing = alternatives.get(route_key)
            if not existing or summary['duration_mins'] < existing['duration_mins']:
                alternatives[route_key] = summary
        
        if not primary_summary:
            primary_summary = {
                'duration_mins': 999,
                'distance_miles': 0,
                'route': 'no_route',
                'route_label': 'No route',
                'polyline': None,
                'annoyingness': {},
            }
        
        return {
            'primary': primary_summary,
            'alternatives': alternatives
        }
    
    def _build_route_summary(self, route: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Extract standardized information from a Directions API route."""
        leg = route['legs'][0]
        duration_in_traffic = leg.get('duration_in_traffic', leg['duration'])
        duration_seconds = duration_in_traffic['value']
        baseline_seconds = leg['duration']['value']
        distance_meters = leg['distance']['value']
        
        summary_label = route.get('summary') or leg['steps'][0].get('html_instructions', 'Route')
        route_key = self._categorize_route(summary_label)
        polyline = route.get('overview_polyline', {}).get('points')
        
        result = {
            'duration_mins': int(round(duration_seconds / 60)),
            'duration_secs': duration_seconds,
            'distance_miles': round(distance_meters / 1609.34, 2),
            'route': route_key,
            'route_label': summary_label,
            'polyline': polyline,
            'summary_html': summary_label,
            'distance_text': leg['distance']['text'],
            'duration_text': duration_in_traffic['text'],
            'baseline_duration_secs': baseline_seconds,
        }
        
        if mode == 'driving':
            result['annoyingness'] = self._calculate_annoyingness(route, leg)
        elif mode == 'transit':
            result['transit_details'] = self._extract_transit_details(leg)
        else:
            result['annoyingness'] = {}
        
        return result
    
    def _categorize_route(self, summary: str) -> str:
        """Identify whether a route primarily uses 101, 280, or neither."""
        text = (summary or "").upper()
        if '280' in text:
            return '280'
        if '101' in text:
            return '101'
        return 'other'
    
    def _calculate_annoyingness(self, route: Dict[str, Any], leg: Dict[str, Any]) -> Dict[str, Any]:
        """Approximate how frustrating a route feels based on maneuvers and traffic."""
        steps = leg.get('steps', [])
        total_distance_miles = max(leg['distance']['value'] / 1609.34, 0.01)
        left_turns_before_highway = 0
        low_speed_segments = 0
        highway_distance = 0.0
        local_distance = 0.0
        hit_highway = False
        
        for step in steps:
            maneuver = (step.get('maneuver') or "").lower()
            html = (step.get('html_instructions') or "").lower()
            distance_miles = step.get('distance', {}).get('value', 0) / 1609.34
            duration_secs = step.get('duration', {}).get('value', 0)
            
            is_highway = any(token in html for token in ['i-', 'us-', 'hwy', 'highway', 'freeway']) or 'merge' in maneuver or 'ramp' in maneuver
            if is_highway:
                hit_highway = True
                highway_distance += distance_miles
            else:
                local_distance += distance_miles
            
            if not hit_highway and maneuver.startswith('turn-left'):
                left_turns_before_highway += 1
            
            if duration_secs > 0:
                speed_mph = (distance_miles / duration_secs) * 3600 if distance_miles > 0 else 0
                if speed_mph and speed_mph < 15 and distance_miles >= 0.2:
                    low_speed_segments += 1
        
        traffic_delay = max(0, leg.get('duration_in_traffic', leg['duration'])['value'] - leg['duration']['value'])
        baseline = max(leg['duration']['value'], 1)
        congestion_ratio = traffic_delay / baseline
        
        left_penalty = min(3.0, left_turns_before_highway * 0.6)
        congestion_penalty = min(2.5, congestion_ratio * 10)
        low_speed_penalty = min(2.0, low_speed_segments * 0.7)
        lane_split_ratio = highway_distance / total_distance_miles
        lane_penalty = min(2.5, (1 - lane_split_ratio) * 2.5)
        
        total_penalty = left_penalty + congestion_penalty + low_speed_penalty + lane_penalty
        score = max(0.0, 10.0 - total_penalty)
        
        return {
            'score': round(score, 2),
            'left_turns_before_highway': left_turns_before_highway,
            'low_speed_segments': low_speed_segments,
            'lane_split_ratio': round(lane_split_ratio, 2),
            'congestion_ratio': round(congestion_ratio, 2),
            'penalties': {
                'left_turns': round(left_penalty, 2),
                'congestion': round(congestion_penalty, 2),
                'low_speed': round(low_speed_penalty, 2),
                'lane_choices': round(lane_penalty, 2),
            }
        }
    
    def _extract_transit_details(self, leg: Dict[str, Any]) -> Dict[str, Any]:
        """Capture key transit lines / walking segments for partner commute display."""
        steps = leg.get('steps', [])
        transit_segments = []
        walking_minutes = 0
        
        for step in steps:
            mode = step.get('travel_mode')
            duration_secs = step.get('duration', {}).get('value', 0)
            if mode == 'TRANSIT':
                transit_info = step.get('transit_details', {})
                line = transit_info.get('line', {})
                vehicle = line.get('vehicle', {})
                transit_segments.append({
                    'line_name': line.get('short_name') or line.get('name'),
                    'vehicle_type': vehicle.get('type'),
                    'agency': line.get('agencies', [{}])[0].get('name') if line.get('agencies') else None,
                    'num_stops': transit_info.get('num_stops'),
                })
            elif mode == 'WALKING':
                walking_minutes += int(round(duration_secs / 60))
        
        return {
            'transit_segments': transit_segments,
            'walking_minutes': walking_minutes
        }
    
    def get_safety_score(self, lat: float, lng: float) -> Dict[str, Any]:
        """
        Get safety score based on SF crime data
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            Dictionary with safety information
        """
        print(f"\n🔒 Calculating safety score for coordinates: ({lat:.6f}, {lng:.6f})")
        
        cache_key = f"safety_v2_{lat}_{lng}"
        cached = self.cache.get(cache_key)
        if cached:
            score = cached.get('safety_score', 0)
            count = cached.get('incident_count', 0)
            severity = cached.get('avg_severity', 0)
            print(f"  ✓ Using cached safety data: {score:.1f}/10 ({count} incidents, avg severity: {severity:.2f}/10)")
            return cached
        
        result = {}
        
        try:
            # Query SF OpenData for crime incidents
            # Using Socrata API
            url = config.SF_OPENDATA_API_ENDPOINT
            print(f"  API endpoint: {url}")
            
            # Calculate date range (last 12 months)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            print(f"  Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            # Calculate bounding box (approximate)
            # 0.25 mile = ~0.004 degrees
            radius_deg = config.CRIME_RADIUS_MILES * 0.016
            print(f"  Search radius: {config.CRIME_RADIUS_MILES} miles (~{radius_deg:.4f}°)")
            
            # SoQL query
            params = {
                '$where': f"incident_date >= '{start_date.strftime('%Y-%m-%d')}' AND "
                         f"latitude > {lat - radius_deg} AND latitude < {lat + radius_deg} AND "
                         f"longitude > {lng - radius_deg} AND longitude < {lng + radius_deg}",
                '$limit': 10000,
            }
            
            # Add App Token authentication if available (helps avoid throttling)
            headers = {}
            if config.SF_OPENDATA_APP_TOKEN:
                headers['X-App-Token'] = config.SF_OPENDATA_APP_TOKEN
                print(f"  ✓ Using authenticated API request with App Token")
            else:
                print(f"  ⚠️  No App Token found - may be subject to throttling")
                print(f"     Get one at: https://data.sfgov.org/profile/edit/developer_settings")
            
            print(f"  Querying SF OpenData API...")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            print(f"  API Status: {response.status_code}")
            
            if response.status_code == 200:
                incidents = response.json()
                incident_count = len(incidents)
                print(f"  Found {incident_count} crime incidents in the area")
                
                # Calculate weighted severity score
                severity_scores = []
                incident_categories = {}
                
                for incident in incidents:
                    category = incident.get('incident_category', 'Miscellaneous')
                    
                    # Get severity weight (default to 3.0 for unknown categories)
                    severity_weight = config.CRIME_SEVERITY_WEIGHTS.get(category, 3.0)
                    
                    # Track incident types with count and severity
                    if category not in incident_categories:
                        incident_categories[category] = {'count': 0, 'severity': severity_weight}
                    incident_categories[category]['count'] += 1
                    
                    severity_scores.append(severity_weight)
                
                # Calculate average severity
                avg_severity = sum(severity_scores) / len(severity_scores) if severity_scores else 0
                weighted_incident_score = sum(severity_scores)
                
                # Show breakdown of top incident types
                if incident_categories:
                    sorted_categories = sorted(incident_categories.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
                    print(f"  Top incident types:")
                    for category, info in sorted_categories:
                        print(f"    - {category}: {info['count']} (severity: {info['severity']:.1f}/10)")
                
                # Calculate safety score based on:
                # 1. Incident count relative to SF baseline (50% weight)
                # 2. Weighted severity of incidents (50% weight)
                
                # Score from incident count (compare to baseline)
                baseline = config.SF_CRIME_BASELINE
                count_ratio = incident_count / baseline if baseline > 0 else 0
                count_score = max(0, min(10, 10 - (count_ratio * 10)))
                
                # Score from severity (normalize to 0-10 scale, inverted)
                # Average severity ranges from 0.5 to 10, lower is better
                severity_score = max(0, min(10, 10 - avg_severity))
                
                # Combined score (50/50 weight)
                safety_score = (count_score * 0.5) + (severity_score * 0.5)
                
                result['incident_count'] = incident_count
                result['avg_severity'] = round(avg_severity, 2)
                result['weighted_incident_score'] = round(weighted_incident_score, 2)
                result['safety_score'] = round(safety_score, 2)
                result['count_score'] = round(count_score, 2)
                result['severity_score'] = round(severity_score, 2)
                result['incident_categories'] = incident_categories
                
                print(f"  Average severity: {avg_severity:.2f}/10")
                print(f"  Incident count vs baseline: {incident_count} vs {baseline} ({count_ratio:.1%})")
                print(f"  Count-based score: {count_score:.1f}/10")
                print(f"  Severity-based score: {severity_score:.1f}/10")
                print(f"  ✓ Combined safety score: {safety_score:.1f}/10")
                
                self.cache.set(cache_key, result)
            else:
                print(f"  ❌ SF OpenData API returned status {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                result['incident_count'] = 0
                result['safety_score'] = 5.0  # Neutral default
        
        except Exception as e:
            print(f"  ❌ Error getting safety data: {e}")
            import traceback
            traceback.print_exc()
            result['incident_count'] = 0
            result['safety_score'] = 5.0  # Neutral default
        
        return result
    
    def get_nearby_amenities(self, lat: float, lng: float) -> Dict[str, int]:
        """
        Get count of nearby amenities
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            Dictionary with amenity counts
        """
        cache_key = f"amenities_{lat}_{lng}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        result = {
            'restaurants': 0,
            'cafes': 0,
            'parks': 0,
        }
        
        try:
            # Search for restaurants
            result['restaurants'] = self._search_places(
                lat, lng, 'restaurant', config.PLACES_SEARCH_RADIUS
            )
            
            time.sleep(0.1)  # Rate limiting
            
            # Search for cafes
            result['cafes'] = self._search_places(
                lat, lng, 'cafe', config.PLACES_SEARCH_RADIUS
            )
            
            time.sleep(0.1)
            
            # Search for parks
            result['parks'] = self._search_places(
                lat, lng, 'park', config.PLACES_SEARCH_RADIUS
            )
            
            self.cache.set(cache_key, result)
        
        except Exception as e:
            print(f"Error getting nearby amenities: {e}")
        
        return result
    
    def find_nearby_gyms(self, lat: float, lng: float) -> Dict[str, Any]:
        """
        Find nearby gyms with quality ratings
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            Dictionary with gym information
        """
        cache_key = f"gyms_{lat}_{lng}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        result = {
            'has_nearby': False,
            'best_rating': 0.0,
            'nearest_gym_name': '',
            'nearest_gym_distance': 999.0,
            'nearest_gym_coords': None,
        }
        
        try:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': config.GYM_SEARCH_RADIUS,
                'type': 'gym',
                'key': self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK':
                gyms = data.get('results', [])
                
                if gyms:
                    result['has_nearby'] = True
                    
                    # Find best-rated gym
                    best_gym = max(gyms, key=lambda g: g.get('rating', 0))
                    result['best_rating'] = best_gym.get('rating', 0) * 2  # Scale to 0-10
                    
                    # Find nearest gym
                    nearest_gym = min(gyms, key=lambda g: self._haversine_distance(
                        lat, lng,
                        g['geometry']['location']['lat'],
                        g['geometry']['location']['lng']
                    ))
                    result['nearest_gym_name'] = nearest_gym.get('name', '')
                    result['nearest_gym_distance'] = self._haversine_distance(
                        lat, lng,
                        nearest_gym['geometry']['location']['lat'],
                        nearest_gym['geometry']['location']['lng']
                    )
                    # Store nearest gym coordinates for elevation calculation
                    result['nearest_gym_coords'] = (
                        nearest_gym['geometry']['location']['lat'],
                        nearest_gym['geometry']['location']['lng']
                    )
                
                self.cache.set(cache_key, result)
        
        except Exception as e:
            print(f"Error finding nearby gyms: {e}")
        
        return result
    
    def _search_places(self, lat: float, lng: float, place_type: str, radius: int) -> int:
        """Search for places and return count"""
        try:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': radius,
                'type': place_type,
                'key': self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK':
                return len(data.get('results', []))
        
        except Exception as e:
            print(f"Error searching for {place_type}: {e}")
        
        return 0
    
    def _haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance in miles between two coordinates"""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 3959  # Earth radius in miles
        
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def get_elevation(self, lat: float, lng: float) -> Optional[float]:
        """
        Get elevation in meters for a coordinate
        
        Uses Google Maps Elevation API with caching
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            Elevation in meters or None if error
        """
        cache_key = f"elevation_{lat}_{lng}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            url = "https://maps.googleapis.com/maps/api/elevation/json"
            params = {
                'locations': f'{lat},{lng}',
                'key': self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK' and len(data['results']) > 0:
                elevation = data['results'][0]['elevation']
                self.cache.set(cache_key, elevation)
                return elevation
            else:
                print(f"Elevation API error: {data.get('status')} - {data.get('error_message', 'No error message')}")
        except Exception as e:
            print(f"Error getting elevation: {e}")
        
        return None
    
    def calculate_elevation_gain(self, from_coords: Tuple[float, float], 
                                 to_coords: Tuple[float, float]) -> Dict[str, Any]:
        """
        Calculate elevation gain between two points
        
        Args:
            from_coords: (latitude, longitude) of starting point
            to_coords: (latitude, longitude) of ending point
        
        Returns:
            Dictionary with:
                - from_elevation: float
                - to_elevation: float
                - elevation_gain: float (positive = uphill to destination)
                - is_moderate_hill: bool (>20m gain)
                - is_steep_hill: bool (>40m gain)
        """
        from_elev = self.get_elevation(from_coords[0], from_coords[1])
        to_elev = self.get_elevation(to_coords[0], to_coords[1])
        
        if from_elev is None or to_elev is None:
            return {
                'from_elevation': None,
                'to_elevation': None,
                'elevation_gain': 0,
                'is_moderate_hill': False,
                'is_steep_hill': False
            }
        
        gain = to_elev - from_elev
        
        return {
            'from_elevation': from_elev,
            'to_elevation': to_elev,
            'elevation_gain': gain,
            'is_moderate_hill': abs(gain) > 20,
            'is_steep_hill': abs(gain) > 40
        }
    
    def get_building_year(self, address: str) -> Optional[int]:
        """
        Attempt to find the year a building was built
        
        Uses multiple strategies:
        1. Google Places API (sometimes has this data)
        2. Street View metadata (earliest available image)
        
        Args:
            address: Full address string
            
        Returns:
            Year as integer, or None if not found
        """
        cache_key = f"building_year_{address}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        result = None
        
        try:
            # First try: Google Places API
            coords = self.geocode_address(address)
            if coords:
                lat, lng = coords
                
                # Search for the place
                url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                params = {
                    'location': f"{lat},{lng}",
                    'radius': 50,  # Very small radius to get the exact building
                    'key': self.api_key,
                }
                
                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                
                if data['status'] == 'OK' and data.get('results'):
                    place = data['results'][0]
                    place_id = place.get('place_id')
                    
                    # Get place details
                    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                    details_params = {
                        'place_id': place_id,
                        'fields': 'opening_date,editorial_summary,reviews',
                        'key': self.api_key,
                    }
                    
                    details_response = requests.get(details_url, params=details_params, timeout=10)
                    details_data = details_response.json()
                    
                    if details_data['status'] == 'OK':
                        place_details = details_data.get('result', {})
                        
                        # Check for opening_date (sometimes available for buildings)
                        opening_date = place_details.get('opening_date')
                        if opening_date and 'year' in opening_date:
                            result = int(opening_date['year'])
            
            # Second try: Street View metadata (earliest image date as proxy)
            if not result and coords:
                metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
                metadata_params = {
                    'location': f"{lat},{lng}",
                    'key': self.api_key,
                }
                
                metadata_response = requests.get(metadata_url, params=metadata_params, timeout=10)
                metadata = metadata_response.json()
                
                if metadata.get('status') == 'OK' and metadata.get('date'):
                    # Date format is like "2023-09"
                    date_str = metadata['date']
                    if '-' in date_str:
                        year = int(date_str.split('-')[0])
                        # Street view date gives us an upper bound
                        # Building must be older than the street view image
                        # Don't return this as definitive, just cache it
                        print(f"  Note: Earliest street view from {year} (building likely older)")
            
            if result:
                self.cache.set(cache_key, result)
                print(f"  Found building year: {result}")
            else:
                print(f"  Could not determine building year automatically")
            
            return result
        
        except Exception as e:
            print(f"  Error finding building year: {e}")
            return None
        
    
    def _estimate_gym_elevation_gain(self, apartment_elevation: float) -> float:
        """
        Estimate elevation gain to gym based on apartment elevation
        
        Simplified heuristic: Gyms are typically on main streets (lower elevation)
        
        Args:
            apartment_elevation: Apartment elevation in meters
            
        Returns:
            Estimated elevation gain in meters
        """
        if apartment_elevation is None:
            return 0.0
        
        # Heuristic: Main streets/commercial areas typically 20-40m lower than hill residences
        # Apartment on steep hill (>50m) = significant climb from gym
        if apartment_elevation > 50:
            return 40.0  # Steep hill case (like 39 Seward St)
        elif apartment_elevation > 30:
            return 25.0  # Moderate hill case
        
        return 0.0  # Flat area
    
    def get_nearby_gyms_detailed(self, lat: float, lng: float, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get detailed information about nearby gyms for user selection
        
        Args:
            lat: Latitude
            lng: Longitude
            limit: Maximum number of gyms to return
        
        Returns:
            List of gym dictionaries with full details for user selection
        """
        cache_key = f"gyms_detailed_{lat}_{lng}_{limit}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        result = []
        
        try:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': config.GYM_SEARCH_RADIUS,
                'type': 'gym',
                'key': self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK':
                gyms = data.get('results', [])
                
                # Process ALL gyms from the API response, not just the first 'limit'
                all_gyms = []
                for gym in gyms:
                    gym_lat = gym['geometry']['location']['lat']
                    gym_lng = gym['geometry']['location']['lng']
                    distance = self._haversine_distance(lat, lng, gym_lat, gym_lng)
                    
                    gym_info = {
                        'name': gym.get('name'),
                        'place_id': gym.get('place_id'),
                        'address': gym.get('vicinity'),
                        'rating': gym.get('rating', 0),
                        'user_ratings_total': gym.get('user_ratings_total', 0),
                        'types': gym.get('types', []),
                        'distance_miles': round(distance, 2),
                        'lat': gym_lat,
                        'lng': gym_lng,
                    }
                    
                    all_gyms.append(gym_info)
                
                # Sort by distance FIRST, then take the top N closest
                all_gyms.sort(key=lambda g: g['distance_miles'])
                result = all_gyms[:limit]
                
                print(f"  Found {len(all_gyms)} gyms total, showing {len(result)} closest")
                
                self.cache.set(cache_key, result)
        
        except Exception as e:
            print(f"Error getting detailed gym info: {e}")
        
        return result
    
    def get_gym_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific gym including reviews
        
        Uses Google Places Details API
        
        Args:
            place_id: Google Place ID for the gym
            
        Returns:
            Dictionary with detailed gym information including reviews
        """
        cache_key = f"gym_details_{place_id}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            url = "https://maps.googleapis.com/maps/api/place/details/json"
            params = {
                'place_id': place_id,
                'fields': 'reviews,opening_hours,website,formatted_phone_number',
                'key': self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK':
                result = data.get('result', {})
                
                # Extract first review snippet if available
                reviews = result.get('reviews', [])
                review_snippet = reviews[0].get('text', '') if reviews else ''
                
                details = {
                    'review_snippet': review_snippet[:150] + '...' if len(review_snippet) > 150 else review_snippet,
                    'opening_hours': result.get('opening_hours', {}).get('weekday_text', []),
                    'website': result.get('website'),
                    'phone': result.get('formatted_phone_number'),
                }
                
                self.cache.set(cache_key, details)
                return details
        
        except Exception as e:
            print(f"Error getting gym details: {e}")
        
        return None
    
    def estimate_parking_ease(self, lat: float, lng: float, address: str = "") -> Dict[str, Any]:
        """
        Estimate visitor parking ease based on area characteristics
        
        Uses heuristics based on:
        - Nearby parking facilities
        - Area type (residential vs commercial)
        - Street characteristics from geocoding data
        
        Args:
            lat: Latitude
            lng: Longitude
            address: Optional address for additional context
            
        Returns:
            Dictionary with parking_ease (1-5) and reasoning
        """
        cache_key = f"parking_ease_{lat}_{lng}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Search for parking-related places nearby
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': 500,  # 500m radius
                'key': self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] != 'OK':
                error_msg = data.get('error_message', data['status'])
                print(f"Places API error: {data['status']} - {error_msg}")
                if data['status'] == 'REQUEST_DENIED':
                    print("⚠️  Places API access denied. Please enable 'Places API' in Google Cloud Console and ensure billing is enabled.")
                return {'parking_ease': 3, 'reasoning': f'Unable to determine ({data["status"]}), defaulting to moderate'}
            
            # Analyze the area
            places = data.get('results', [])
            
            # Count different types of places
            parking_lots = 0
            commercial_count = 0
            residential_count = 0
            
            for place in places:
                types = place.get('types', [])
                if 'parking' in types:
                    parking_lots += 1
                if any(t in types for t in ['store', 'restaurant', 'bar', 'shopping_mall', 'cafe']):
                    commercial_count += 1
                if 'residential' in ' '.join(types):
                    residential_count += 1
            
            # Heuristic scoring
            # More parking lots = easier parking
            # More commercial = harder parking (busy area)
            # More residential = easier parking (quieter area)
            
            score = 3  # Start with moderate
            reasoning_parts = []
            
            # Parking facilities boost score
            if parking_lots >= 3:
                score += 1.5
                reasoning_parts.append(f"{parking_lots} parking facilities nearby")
            elif parking_lots >= 1:
                score += 0.5
                reasoning_parts.append(f"{parking_lots} parking facility nearby")
            
            # Commercial activity reduces score
            if commercial_count > 15:
                score -= 1.5
                reasoning_parts.append("busy commercial area")
            elif commercial_count > 8:
                score -= 0.5
                reasoning_parts.append("moderate commercial activity")
            else:
                reasoning_parts.append("quiet area")
            
            # Residential areas are generally easier
            if residential_count > commercial_count:
                score += 0.5
                reasoning_parts.append("primarily residential")
            
            # Clamp to 1-5 range
            score = max(1, min(5, round(score)))
            
            result = {
                'parking_ease': int(score),
                'reasoning': ', '.join(reasoning_parts) if reasoning_parts else 'Based on area characteristics',
                'parking_facilities_count': parking_lots,
                'commercial_density': commercial_count,
            }
            
            self.cache.set(cache_key, result)
            return result
        
        except Exception as e:
            print(f"Error estimating parking ease: {e}")
            return {
                'parking_ease': 3,
                'reasoning': 'Error determining parking ease, defaulting to moderate'
            }
    
    def get_nearby_laundromats(self, lat: float, lng: float, radius_miles: float = 0.5) -> List[Dict[str, Any]]:
        """
        Find nearby laundromats with walking time
        
        Args:
            lat: Latitude
            lng: Longitude
            radius_miles: Search radius in miles (default 0.5)
            
        Returns:
            List of laundromat dictionaries with details including walking time
        """
        cache_key = f"laundromats_{lat}_{lng}_{radius_miles}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Convert miles to meters
            radius_meters = radius_miles * 1609.34
            
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': int(radius_meters),
                'type': 'laundry',
                'key': self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] != 'OK':
                print(f"Laundromat search error: {data['status']}")
                return []
            
            laundromats = []
            for place in data.get('results', []):
                # Calculate crow-flies distance
                place_lat = place['geometry']['location']['lat']
                place_lng = place['geometry']['location']['lng']
                distance_miles = self._calculate_distance(lat, lng, place_lat, place_lng)
                
                laundromat = {
                    'name': place.get('name', 'Unknown'),
                    'address': place.get('vicinity', ''),
                    'rating': place.get('rating', 0),
                    'user_ratings_total': place.get('user_ratings_total', 0),
                    'distance_miles': round(distance_miles, 2),
                    'place_id': place.get('place_id', ''),
                    'lat': place_lat,
                    'lng': place_lng,
                }
                laundromats.append(laundromat)
            
            # Sort by distance first
            laundromats.sort(key=lambda x: x['distance_miles'])
            
            # Get walking times for the closest ones (limit to 10 to avoid too many API calls)
            closest_laundromats = laundromats[:10]
            
            if closest_laundromats:
                # Use Distance Matrix API to get walking times
                walking_times = self._get_walking_times(
                    lat, lng, 
                    [(l['lat'], l['lng']) for l in closest_laundromats]
                )
                
                # Add walking times to laundromats
                for i, laundromat in enumerate(closest_laundromats):
                    if i < len(walking_times):
                        laundromat['walking_time_mins'] = walking_times[i]['duration_mins']
                        laundromat['walking_distance_miles'] = walking_times[i]['distance_miles']
                
                # Re-sort by walking time
                closest_laundromats.sort(key=lambda x: x.get('walking_time_mins', 999))
            
            self.cache.set(cache_key, closest_laundromats)
            return closest_laundromats
        
        except Exception as e:
            print(f"Error finding laundromats: {e}")
            return []
    
    def _get_walking_times(self, origin_lat: float, origin_lng: float, 
                          destinations: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
        """
        Get walking times from origin to multiple destinations using Distance Matrix API
        
        Args:
            origin_lat: Origin latitude
            origin_lng: Origin longitude
            destinations: List of (lat, lng) tuples for destinations
            
        Returns:
            List of dictionaries with duration_mins and distance_miles
        """
        if not destinations:
            return []
        
        try:
            # Distance Matrix API
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            
            origin = f"{origin_lat},{origin_lng}"
            dest_str = "|".join([f"{lat},{lng}" for lat, lng in destinations])
            
            params = {
                'origins': origin,
                'destinations': dest_str,
                'mode': 'walking',
                'key': self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            if data['status'] != 'OK':
                print(f"Distance Matrix API error: {data['status']}")
                return [{'duration_mins': None, 'distance_miles': None} for _ in destinations]
            
            results = []
            rows = data.get('rows', [])
            if rows and len(rows) > 0:
                elements = rows[0].get('elements', [])
                for element in elements:
                    if element['status'] == 'OK':
                        duration_secs = element['duration']['value']
                        distance_meters = element['distance']['value']
                        results.append({
                            'duration_mins': round(duration_secs / 60, 1),
                            'distance_miles': round(distance_meters / 1609.34, 2)
                        })
                    else:
                        results.append({
                            'duration_mins': None,
                            'distance_miles': None
                        })
            
            return results
        
        except Exception as e:
            print(f"Error getting walking times: {e}")
            return [{'duration_mins': None, 'distance_miles': None} for _ in destinations]
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points in miles using Haversine formula"""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 3959  # Earth's radius in miles
        
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        dlat = radians(lat2 - lat1)
        dlng = radians(lng2 - lng1)
        
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c

