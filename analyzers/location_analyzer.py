"""
Location analyzer for apartments

Analyzes:
- Commute times and routes
- Neighborhood safety (SF OpenData crime statistics)
- Nearby amenities (gyms, restaurants, cafes, parks)
"""

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import time

import config
from utils.cache import get_cache
from utils.rate_limiter import get_rate_limiter


class LocationAnalyzer:
    """Analyzer for apartment location and surroundings"""
    
    def __init__(self, google_maps_api_key: str = None, sheets_client=None):
        """
        Initialize location analyzer
        
        Args:
            google_maps_api_key: Google Maps API key
            sheets_client: Optional GoogleSheetsClient for exclusion list
        """
        self.api_key = google_maps_api_key or config.GOOGLE_MAPS_API_KEY
        if not self.api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY not set. Please set it in .env file.")
        
        self.cache = get_cache()
        self.rate_limiter = get_rate_limiter()
        self.sheets_client = sheets_client
        self._excluded_places_cache = None
        self._excluded_places_cache_time = None
        self.http_session = self._init_http_session()
    
    def _init_http_session(self) -> requests.Session:
        """Create a shared HTTP session with retries for transient failures"""
        session = requests.Session()
        
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET"])
        )
        
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        # Helpful User-Agent for debugging traffic in logs/trace tools
        session.headers.update({"User-Agent": "ApartmentAnalyzer/1.0"})
        return session
    
    def _get_excluded_places(self) -> List[str]:
        """Get list of excluded place IDs with caching"""
        from datetime import datetime, timedelta
        
        # Cache for 5 minutes
        if (self._excluded_places_cache is not None and 
            self._excluded_places_cache_time is not None and
            datetime.now() - self._excluded_places_cache_time < timedelta(minutes=5)):
            return self._excluded_places_cache
        
        if self.sheets_client:
            try:
                self._excluded_places_cache = self.sheets_client.get_excluded_places()
                self._excluded_places_cache_time = datetime.now()
                return self._excluded_places_cache
            except Exception as e:
                print(f"Warning: Could not fetch excluded places: {e}")
        
        return []
    
    def _make_places_api_request(self, url: str, params: dict, timeout: int = 10, service: str = 'google_places') -> dict:
        """
        Make a rate-limited request to Google Places API
        
        Args:
            url: API endpoint URL
            params: Request parameters
            timeout: Request timeout in seconds
            service: Rate limiter bucket to use
            
        Returns:
            JSON response data
        """
        self.rate_limiter.wait_if_needed(service)
        try:
            response = self.http_session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  ⚠️  Places API request failed ({service}): {e}")
            return {'status': 'ERROR', 'error': str(e)}
    
    def analyze_location(self, address: str, analyze_commute: bool = True, analyze_safety: bool = True, analyze_amenities: bool = True) -> Dict[str, Any]:
        """
        Complete location analysis for an apartment
        
        Args:
            address: Apartment address
            analyze_commute: Whether to analyze commute times (default: True)
            analyze_safety: Whether to analyze safety/crime data (default: True)
            analyze_amenities: Whether to analyze nearby amenities/restaurants (default: True)
            
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
        if analyze_commute:
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
        if analyze_safety:
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
        if analyze_amenities:
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
        
        # Rate limit: Google Maps Geocoding API
        rate_limiter = get_rate_limiter()
        rate_limiter.wait_if_needed('google_maps_geocode')
        
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
                    
                    # Find the route with the fastest AM time to use as the "primary" route
                    # This ensures the "Fastest AM" label is accurate
                    fastest_am_route = combined_primary.copy()
                    fastest_am_time = combined_primary.get('duration_am_mins', 999)
                    
                    for route_key, route_data in combined_alternatives.items():
                        am_time = route_data.get('duration_am_mins', 999)
                        if am_time < fastest_am_time:
                            fastest_am_time = am_time
                            fastest_am_route = route_data.copy()
                            fastest_am_route['route'] = route_key
                    
                    result = {
                        'success': True,
                        'mode_used': current_mode,
                        **fastest_am_route,
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
        
        # Rate limit: Google Directions API
        self.rate_limiter.wait_if_needed('google_directions')
        
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
    
    def calculate_transit_annoyingness(
        self, 
        transit_details: Dict[str, Any],
        weights: Optional[Dict[str, float]] = None,
        ideal_duration: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate annoyingness score for transit routes based on walking time, transfers, and duration.
        
        Args:
            transit_details: Output from _extract_transit_details or commute_details['partner']['transit_details']
            weights: Optional custom weights dict with keys:
                - walk_time_weight: Penalty per minute of walking (default: 0.15)
                - transfer_weight: Penalty per transit transfer (default: 0.8)
                - duration_weight: Penalty per minute over ideal (default: 0.1)
            ideal_duration: Ideal commute duration in minutes for duration penalty (default: 30)
            
        Returns:
            Dict with annoyingness score and breakdown:
            {
                'score': float (0-10, higher is better/less annoying),
                'walking_minutes': int,
                'num_transfers': int,
                'walk_penalty': float,
                'transfer_penalty': float,
                'duration_penalty': float,
                'penalties': dict with detailed breakdown
            }
        """
        # Default weights if not provided
        default_weights = {
            'walk_time_weight': 0.15,  # Per minute of walking
            'transfer_weight': 0.8,    # Per transfer
            'duration_weight': 0.1,    # Per minute over ideal
        }
        w = {**default_weights, **(weights or {})}
        
        # Extract values from transit details
        walking_minutes = transit_details.get('walking_minutes', 0)
        transit_segments = transit_details.get('transit_segments', [])
        # Number of transfers = number of segments - 1 (first segment isn't a transfer)
        num_transfers = max(0, len(transit_segments) - 1)
        
        # Calculate penalties
        walk_penalty = walking_minutes * w['walk_time_weight']
        transfer_penalty = num_transfers * w['transfer_weight']
        
        # Duration penalty (requires total_duration_mins to be passed in transit_details)
        total_duration = transit_details.get('total_duration_mins', 0)
        duration_over_ideal = max(0, total_duration - ideal_duration)
        duration_penalty = duration_over_ideal * w['duration_weight']
        
        # Calculate total penalty and score
        total_penalty = walk_penalty + transfer_penalty + duration_penalty
        
        # Cap penalties to avoid negative scores
        walk_penalty = min(3.0, walk_penalty)
        transfer_penalty = min(3.0, transfer_penalty)
        duration_penalty = min(2.0, duration_penalty)
        total_penalty = min(10.0, walk_penalty + transfer_penalty + duration_penalty)
        
        score = max(0.0, 10.0 - total_penalty)
        
        return {
            'score': round(score, 2),
            'walking_minutes': walking_minutes,
            'num_transfers': num_transfers,
            'total_duration_mins': total_duration,
            'walk_penalty': round(walk_penalty, 2),
            'transfer_penalty': round(transfer_penalty, 2),
            'duration_penalty': round(duration_penalty, 2),
            'penalties': {
                'walking': round(walk_penalty, 2),
                'transfers': round(transfer_penalty, 2),
                'duration': round(duration_penalty, 2),
            }
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
    
    def get_nearby_amenities(self, lat: float, lng: float, return_details: bool = False, poi_names: List[str] = None) -> Dict[str, Any]:
        """
        Get count of nearby amenities (vegetarian-friendly restaurants/cafes with 4+ stars)
        
        Args:
            lat: Latitude
            lng: Longitude
            return_details: If True, return detailed lists of places; if False, return counts only
            poi_names: List of POI names to skip Claude verification (already known to be good)
            
        Returns:
            Dictionary with amenity counts (and details if return_details=True)
        """
        cache_key = f"amenities_{lat}_{lng}{'_details' if return_details else ''}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        result = {
            'restaurants': 0 if not return_details else [],
            'cafes': 0 if not return_details else [],
            'parks': 0 if not return_details else [],
        }
        
        try:
            # Search for vegetarian-friendly restaurants (4+ stars)
            print("🥗 Searching for vegetarian-friendly restaurants...")
            result['restaurants'] = self._search_vegetarian_places(
                lat, lng, 'restaurant', config.PLACES_SEARCH_RADIUS, return_details, poi_names
            )
            
            time.sleep(0.1)  # Rate limiting
            
            # Search for cafes (4+ stars)
            print("☕ Searching for quality cafes...")
            result['cafes'] = self._search_vegetarian_places(
                lat, lng, 'cafe', config.PLACES_SEARCH_RADIUS, return_details, poi_names
            )
            
            time.sleep(0.1)
            
            # Search for parks (no filtering needed)
            result['parks'] = self._search_places(
                lat, lng, 'park', config.PLACES_SEARCH_RADIUS, return_details
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
            
            data = self._make_places_api_request(url, params, timeout=10)
            
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
    
    def _search_places(self, lat: float, lng: float, place_type: str, radius: int, return_details: bool = False) -> Union[int, List[Dict]]:
        """
        Search for places and return count or detailed list
        
        Args:
            return_details: If True, return list of place dicts; if False, return count only
        """
        try:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': radius,
                'type': place_type,
                'key': self.api_key,
            }
            
            data = self._make_places_api_request(url, params, timeout=10)
            
            if data['status'] == 'OK':
                results = data.get('results', [])
                
                # Filter out excluded places
                excluded_place_ids = self._get_excluded_places()
                filtered_results = [p for p in results if p.get('place_id') not in excluded_place_ids]
                
                if return_details:
                    return [{
                        'name': p.get('name', 'Unknown'),
                        'place_id': p.get('place_id'),
                        'rating': p.get('rating', 0),
                        'address': p.get('vicinity', ''),
                        'types': p.get('types', [])
                    } for p in filtered_results]
                else:
                    return len(filtered_results)
        
        except Exception as e:
            print(f"Error searching for {place_type}: {e}")
        
        return [] if return_details else 0
    
    def _search_vegetarian_places(self, lat: float, lng: float, place_type: str, radius: int, return_details: bool = False, poi_names: List[str] = None) -> Union[int, List[Dict]]:
        """
        Search for vegetarian-friendly places with 4+ star rating using Claude to analyze menus
        
        Args:
            lat: Latitude
            lng: Longitude
            place_type: Type of place ('restaurant' or 'cafe')
            radius: Search radius in meters
            return_details: If True, return list of place dicts; if False, return count only
            poi_names: List of POI names to skip Claude verification (already known to be good)
            
        Returns:
            Count of vegetarian-friendly places with 4+ star rating, or list of place details if return_details=True
        """
        try:
            # First, get all places with 4+ star rating
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': radius,
                'type': place_type,
                'key': self.api_key,
            }
            
            data = self._make_places_api_request(url, params, timeout=10)
            
            if data['status'] != 'OK':
                return [] if return_details else 0
            
            places = data.get('results', [])
            
            # Filter by rating first (4+ stars)
            high_rated_places = [p for p in places if p.get('rating', 0) >= 4.0]
            
            if not high_rated_places:
                return [] if return_details else 0
            
            print(f"  Found {len(high_rated_places)} {place_type}s with 4+ stars, checking vegetarian options...")
            
            # Check vegetarian-friendliness using Claude for top-rated places
            # To avoid too many API calls, limit to checking top 20 by rating
            top_places = sorted(high_rated_places, key=lambda p: p.get('rating', 0), reverse=True)[:20]
            
            # Get exclusion list
            excluded_place_ids = self._get_excluded_places()
            
            # Normalize POI names for comparison (if provided)
            poi_names_normalized = set()
            if poi_names:
                poi_names_normalized = {name.lower().strip() for name in poi_names if name}
                if poi_names_normalized:
                    print(f"  ℹ️  Checking against {len(poi_names_normalized)} POI names for auto-inclusion")
            
            vegetarian_places = []
            claude_checks = 0
            poi_auto_includes = 0
            
            for place in top_places:
                place_id = place.get('place_id')
                place_name = place.get('name', 'Unknown')
                
                # Skip if excluded
                if place_id in excluded_place_ids:
                    continue
                
                # Check if this place is in the POI list - if so, auto-include without Claude check
                place_name_normalized = place_name.lower().strip()
                is_in_poi_list = place_name_normalized in poi_names_normalized
                
                # Try fuzzy matching if exact match fails (e.g., "Tartine Bakery" vs "Tartine")
                if not is_in_poi_list and poi_names_normalized:
                    for poi_name in poi_names_normalized:
                        # Check if POI name is a substring of place name or vice versa
                        if (poi_name in place_name_normalized or 
                            place_name_normalized in poi_name):
                            is_in_poi_list = True
                            break
                
                if is_in_poi_list:
                    # Auto-include places from POI list (no Claude API call needed!)
                    print(f"    ✓ {place_name} is in your POI list - auto-including (skipping Claude check)")
                    poi_auto_includes += 1
                    is_vegetarian = True
                else:
                    # Check with Claude
                    is_vegetarian = self._is_vegetarian_friendly(place_id, place_name, place_type)
                    claude_checks += 1
                    # Rate limit between Claude API calls
                    time.sleep(0.2)
                
                if is_vegetarian:
                    if return_details:
                        vegetarian_places.append({
                            'name': place_name,
                            'place_id': place_id,
                            'rating': place.get('rating', 0),
                            'address': place.get('vicinity', ''),
                            'types': place.get('types', [])
                        })
                    else:
                        vegetarian_places.append(place)
            
            if return_details:
                print(f"  ✓ Found {len(vegetarian_places)} vegetarian-friendly {place_type}s ({poi_auto_includes} from POI list, {claude_checks} Claude checks)")
                return vegetarian_places
            else:
                vegetarian_count = len(vegetarian_places)
                print(f"  ✓ Found {vegetarian_count} vegetarian-friendly {place_type}s ({poi_auto_includes} from POI list, {claude_checks} Claude checks)")
                return vegetarian_count
        
        except Exception as e:
            print(f"Error searching for vegetarian {place_type}: {e}")
            return [] if return_details else 0
    
    def _is_vegetarian_friendly(self, place_id: str, place_name: str, place_type: str) -> bool:
        """
        Use Claude to determine if a place is vegetarian-friendly based on available info
        
        Args:
            place_id: Google Place ID
            place_name: Name of the place
            place_type: Type ('restaurant' or 'cafe')
            
        Returns:
            True if vegetarian-friendly, False otherwise
        """
        cache_key = f"veg_friendly_{place_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            # Get place details from Google Places API
            details_url = "https://maps.googleapis.com/maps/api/place/details/json"
            params = {
                'place_id': place_id,
                'fields': 'name,types,editorial_summary,website,reviews',
                'key': self.api_key,
            }
            
            details_data = self._make_places_api_request(details_url, params, timeout=10, service='google_places')
            
            if details_data.get('status') != 'OK':
                error_msg = details_data.get('error_message') or details_data.get('status')
                print(f"    ⚠️  Places details not OK for {place_name}: {error_msg}")
                return False
            
            place_details = details_data.get('result', {})
            types = place_details.get('types', [])
            summary = place_details.get('editorial_summary', {}).get('overview', '')
            reviews = place_details.get('reviews', [])
            
            # Build context for Claude
            context = f"Restaurant: {place_name}\n"
            context += f"Type: {place_type}\n"
            context += f"Categories: {', '.join(types)}\n"
            if summary:
                context += f"Summary: {summary}\n"
            if reviews:
                context += "\nRecent reviews:\n"
                for review in reviews[:3]:  # First 3 reviews
                    context += f"- {review.get('text', '')[:200]}...\n"
            
            # Use Claude to analyze
            import anthropic
            import httpx
            claude_key = config.ANTHROPIC_API_KEY
            if not claude_key:
                print(f"  ⚠️  No Anthropic API key, skipping {place_name}")
                return False
            
            # NOTE: SSL verification disabled for corporate proxy/VPN environments
            # Re-enable by removing http_client parameter or setting verify=True
            http_client = httpx.Client(verify=False)
            client = anthropic.Anthropic(
                api_key=claude_key, 
                max_retries=2, 
                timeout=30,
                http_client=http_client
            )
            
            prompt = f"""Determine if this restaurant/cafe is suitable for vegetarians.

{context}

IMPORTANT: Vegetarian-friendly means:
- Has vegetarian options (dishes with NO meat/fish/poultry)
- Vegan options count as vegetarian-friendly (vegan ⊂ vegetarian)
- Places with dairy/eggs are fine (lacto-ovo vegetarian)
- **Bakeries, cafes, and dessert shops are ALWAYS vegetarian-friendly** (coffee, pastries, desserts)

Consider:
1. Explicit vegetarian/vegan menu items mentioned?
2. Cuisine type with good veg options (Indian, Mediterranean, Thai, Italian, Mexican, etc.)?
3. Reviews mention vegetarian/vegan dishes positively?
4. Is it a bakery, cafe, coffee shop, or dessert place? → **YES (automatically suitable)**

NOT suitable:
- Steakhouses or BBQ joints (primarily meat-focused)
- Fast food burger/chicken places with only meat options
- Seafood-only restaurants with no alternatives

Respond with ONLY the word "YES" or "NO" (nothing else)."""
            
            # Retry Claude calls to handle transient connection errors
            message = None
            last_error = None
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    message = client.messages.create(
                        model="claude-3-5-haiku-20241022",  # Latest Haiku 3.5 - fast, cheap, and most up-to-date
                        max_tokens=100,  # Allow reasoning for debugging
                        messages=[{"role": "user", "content": prompt}]
                    )
                    break
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        wait_time = 1.5 * (2 ** attempt)
                        print(f"    ⚠️  Claude request failed for {place_name} (attempt {attempt + 1}/{max_attempts}): {self._format_claude_error(e)}")
                        time.sleep(wait_time)
                    else:
                        print(f"    ❌  Claude request failed for {place_name} after {max_attempts} attempts: {self._format_claude_error(e)}")
                        return False
            
            if message is None:
                return False
            
            response_text = message.content[0].text.strip()
            
            # Parse only the first line for YES/NO decision
            first_line = response_text.split('\n')[0].strip().upper()
            is_veg_friendly = first_line.startswith("YES")
            
            # For debugging, show full response (but truncate if very long)
            response_preview = response_text if len(response_text) <= 100 else response_text[:100] + "..."
            print(f"    {'✓' if is_veg_friendly else '✗'} {place_name}: {response_preview}")
            
            # Cache result
            self.cache.set(cache_key, is_veg_friendly)
            return is_veg_friendly
            
        except Exception as e:
            print(f"    ⚠️  Error checking {place_name}: {e}")
            # On error, be conservative and return False
            return False
    
    def _format_claude_error(self, error: Exception) -> str:
        """
        Build a detailed error string for Claude API failures so we can debug
        network vs API errors (includes status, request_id, and payload if present).
        """
        try:
            err_type = error.__class__.__name__
            status = getattr(error, "status_code", None)
            request_id = getattr(error, "request_id", None)
            message = str(error)
            
            # Anthropic API errors often expose a .response attribute
            payload = None
            response = getattr(error, "response", None)
            if response is not None:
                try:
                    payload = response.json()
                except Exception:
                    payload = getattr(response, "text", None)
            
            parts = [f"type={err_type}"]
            if status is not None:
                parts.append(f"status={status}")
            if request_id:
                parts.append(f"request_id={request_id}")
            if message:
                parts.append(f"msg={message}")
            if payload:
                parts.append(f"payload={payload}")
            
            return " | ".join(parts)
        except Exception as format_err:
            return f"unformatted_error={error} | formatter_failed={format_err}"
    
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
        
        # Rate limit: Google Elevation API
        self.rate_limiter.wait_if_needed('google_elevation')
        
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
    
    def _strip_apartment_number(self, address: str) -> str:
        """
        Remove apartment/unit numbers from address while preserving essential components
        
        Handles various formats:
        - "123 Main St apt 4, City, CA 12345"
        - "123 Main St #456, City, CA 12345"
        - "123 Main St Unit 4B, City, CA 12345"
        - "123 Main St, Apt. 4, City, CA 12345"
        
        Args:
            address: Full address including apartment number
            
        Returns:
            Address with apartment number removed, validated to have city and zip
        """
        import re
        
        # Common apartment designators (case-insensitive)
        apt_patterns = [
            r'\s+apt\.?\s+\w+',          # apt 4, apt. 4
            r'\s+apartment\s+\w+',        # apartment 4
            r'\s+unit\.?\s+\w+',          # unit 4, unit. 4
            r'\s+#\s*\w+',                # #4, # 4
            r'\s+ste\.?\s+\w+',           # ste 4, ste. 4
            r'\s+suite\.?\s+\w+',         # suite 4, suite. 4
            r',\s*apt\.?\s+\w+',          # , apt 4
            r',\s*apartment\s+\w+',       # , apartment 4
            r',\s*unit\.?\s+\w+',         # , unit 4
            r',\s*#\s*\w+',               # , #4
            r',\s*ste\.?\s+\w+',          # , ste 4
            r',\s*suite\.?\s+\w+',        # , suite 4
        ]
        
        cleaned = address
        for pattern in apt_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Clean up any double commas or extra spaces
        cleaned = re.sub(r',\s*,', ',', cleaned)  # Remove double commas
        cleaned = re.sub(r'\s+', ' ', cleaned)     # Normalize whitespace
        cleaned = cleaned.strip()
        
        # Validate that we still have essential components
        # Must have: street address, city, state, and zip code
        # Pattern: "number street, city, state zip"
        essential_pattern = r'\d+\s+.+,\s*.+,\s*[A-Z]{2}\s+\d{5}'
        
        if re.search(essential_pattern, cleaned):
            return cleaned
        else:
            # If cleaning broke the address, return original
            # (better to have apartment number than invalid address)
            print(f"  ⚠️  Address cleaning may have removed too much, using original")
            return address
    
    def get_building_year(self, address: str) -> Optional[int]:
        """
        Attempt to find the year a building was built
        
        Uses multiple strategies:
        0. DataSF assessor roll (SF first-choice: authoritative, free, official)
        1. Google Places API (sometimes has this data)
        2. Claude AI web search and extraction (most reliable)
        3. Street View metadata (earliest available image as fallback)

        Args:
            address: Full address string (may include apartment number)

        Returns:
            Year as integer, or None if not found
        """
        cache_key = f"building_year_{address}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Strategy 0 — SF first-choice: the Assessor's secured property tax roll
        # via DataSF is authoritative and free. It falls through for non-SF
        # addresses (no match) or any DataSF hiccup, so the strategies below
        # still run as fallbacks.
        try:
            from utils import datasf_client
            record = datasf_client.lookup_by_address(address)
            if record and record.year_built:
                print(f"  🏛️  Building year from SF assessor roll: {record.year_built}")
                self.cache.set(cache_key, record.year_built)
                return record.year_built
        except Exception as e:
            print(f"  ⚠️  DataSF assessor lookup failed, using fallbacks: {e}")

        # Strip apartment number for better Claude search results
        # (Building records typically don't include apartment numbers)
        building_address = self._strip_apartment_number(address)
        if building_address != address:
            print(f"  🏢 Using building address for search: {building_address}")
        
        result = None
        
        try:
            # First try: Google Places API (quick but rarely has this data)
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
            
            # Second try: Use Claude to search and extract building year
            if not result:
                try:
                    import anthropic
                    import os
                    
                    api_key = os.getenv('ANTHROPIC_API_KEY')
                    if api_key:
                        client = anthropic.Anthropic(api_key=api_key)
                        
                        prompt = f"""You are helping find the construction year for a residential building in San Francisco.

Building Address: {building_address}

Please search for information about when this building was constructed. Look for:
- Property records
- Historical building databases
- Real estate listings
- San Francisco property assessor records
- Architectural databases

Respond with ONLY the 4-digit year (e.g., 1925) if you can find it with high confidence.
If you cannot find reliable information, respond with "UNKNOWN".

Do not include any explanation, just the year or "UNKNOWN"."""
                        
                        print(f"  🤖 Asking Claude to find building year for {building_address}...")
                        
                        # Try latest Sonnet first, fallback to older versions if not available
                        models_to_try = [
                            "claude-sonnet-4-5-20250929",  # Latest Sonnet 4.5 (September 2025)
                            "claude-3-5-sonnet-20241022",  # Sonnet 3.5 (October 2024)
                            "claude-3-5-sonnet-20240620",  # Earlier Sonnet 3.5
                            "claude-3-sonnet-20240229",    # Sonnet 3 fallback
                        ]
                        
                        response = None
                        last_error = None
                        
                        for model in models_to_try:
                            try:
                                response = client.messages.create(
                                    model=model,
                                    max_tokens=50,
                                    messages=[{
                                        "role": "user",
                                        "content": prompt
                                    }]
                                )
                                print(f"  ✓ Using model: {model}")
                                break
                            except Exception as model_error:
                                last_error = model_error
                                if "404" in str(model_error) or "not_found" in str(model_error):
                                    continue  # Try next model
                                else:
                                    raise  # Other error, don't retry
                        
                        if not response:
                            raise Exception(f"All Claude models failed. Last error: {last_error}")
                        
                        response_text = response.content[0].text.strip()
                        print(f"  Claude response: {response_text}")
                        
                        # Try to extract year from response
                        if response_text != "UNKNOWN":
                            # Look for 4-digit year
                            import re
                            year_match = re.search(r'\b(1[89]\d{2}|20[0-2]\d)\b', response_text)
                            if year_match:
                                result = int(year_match.group(1))
                                print(f"  ✓ Claude found building year: {result}")
                            
                except Exception as claude_error:
                    print(f"  ⚠️  Claude search failed: {claude_error}")
            
            # Third try: Street View metadata (earliest image date as proxy)
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
                print(f"  ✓ Found building year: {result}")
            else:
                print(f"  ❌ Could not determine building year automatically")
            
            return result
        
        except Exception as e:
            print(f"  Error finding building year: {e}")
            import traceback
            traceback.print_exc()
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
    
    def get_nearby_gyms_detailed(self, lat: float, lng: float, limit: int = 5, radius_miles: float = None) -> List[Dict[str, Any]]:
        """
        Get detailed information about nearby gyms for user selection
        
        Args:
            lat: Latitude
            lng: Longitude
            limit: Maximum number of gyms to return
            radius_miles: Search radius in miles (overrides default if provided)
        
        Returns:
            List of gym dictionaries with full details for user selection
        """
        # Use custom radius if provided, otherwise use config default
        search_radius_meters = int(radius_miles * 1609.34) if radius_miles else config.GYM_SEARCH_RADIUS
        
        cache_key = f"gyms_detailed_{lat}_{lng}_{limit}_{search_radius_meters}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        all_gyms = []
        gym_place_ids = set()  # Track unique gyms
        
        try:
            # Strategy 1: Search by type='gym'
            all_gyms_from_type = self._fetch_gyms_by_type(lat, lng, search_radius_meters, gym_place_ids)
            all_gyms.extend(all_gyms_from_type)
            
            # Strategy 2: Text search for 'gym' and 'fitness' to catch more results
            all_gyms_from_text = self._fetch_gyms_by_text(lat, lng, search_radius_meters, gym_place_ids)
            all_gyms.extend(all_gyms_from_text)
            
            # Sort by distance and take the closest ones
            all_gyms.sort(key=lambda g: g['distance_miles'])
            result = all_gyms[:limit]
            
            print(f"  Found {len(all_gyms)} unique gyms total within {search_radius_meters}m ({search_radius_meters/1609.34:.1f} mi), showing {len(result)} closest")
            if result:
                print(f"  Gyms found (sorted by distance):")
                for i, gym in enumerate(result[:10], 1):  # Show first 10
                    print(f"    {i}. {gym['name']} - {gym['distance_miles']} mi")
                if len(result) > 10:
                    print(f"    ... and {len(result) - 10} more")
            
            self.cache.set(cache_key, result)
        
        except Exception as e:
            print(f"Error getting detailed gym info: {e}")
            import traceback
            traceback.print_exc()
            result = []
        
        return result
    
    def _fetch_gyms_by_type(self, lat: float, lng: float, radius_meters: int, seen_place_ids: set) -> List[Dict[str, Any]]:
        """Fetch gyms using type='gym' search"""
        gyms = []
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{lat},{lng}",
            'radius': radius_meters,
            'type': 'gym',
            'key': self.api_key,
        }
        
        # Paginate through results
        page_count = 0
        while page_count < 3:  # Max 3 pages
            try:
                data = self._make_places_api_request(url, params, timeout=10)
                
                if data['status'] == 'OK':
                    for gym in data.get('results', []):
                        place_id = gym.get('place_id')
                        if place_id in seen_place_ids:
                            continue
                        seen_place_ids.add(place_id)
                        
                        gym_lat = gym['geometry']['location']['lat']
                        gym_lng = gym['geometry']['location']['lng']
                        distance = self._haversine_distance(lat, lng, gym_lat, gym_lng)
                        
                        gyms.append({
                            'name': gym.get('name'),
                            'place_id': place_id,
                            'address': gym.get('vicinity'),
                            'rating': gym.get('rating', 0),
                            'user_ratings_total': gym.get('user_ratings_total', 0),
                            'types': gym.get('types', []),
                            'distance_miles': round(distance, 2),
                            'lat': gym_lat,
                            'lng': gym_lng,
                        })
                    
                    # Check for next page
                    next_page_token = data.get('next_page_token')
                    if next_page_token:
                        import time
                        time.sleep(2)
                        params = {
                            'pagetoken': next_page_token,
                            'key': self.api_key,
                        }
                        page_count += 1
                    else:
                        break
                else:
                    print(f"  Type search status: {data['status']}")
                    break
            except Exception as e:
                print(f"  Error in type search: {e}")
                break
        
        return gyms
    
    def _fetch_gyms_by_text(self, lat: float, lng: float, radius_meters: int, seen_place_ids: set) -> List[Dict[str, Any]]:
        """Fetch gyms using text search (catches gyms with alternative classifications)"""
        gyms = []
        
        # Try multiple search terms - prioritize specific chains that might not show up in type search
        search_terms = [
            'Live Fit Gym',  # Specific chain that's missing from type search
            'LuxFit',        # LuxFit Mission Rock and LuxFit SF
            'Crunch Fitness',
            'Planet Fitness',
            '24 Hour Fitness',
            'gym',
            'fitness center',
            'fitness',
        ]
        
        for search_term in search_terms:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': radius_meters,
                'keyword': search_term,
                'key': self.api_key,
            }
            
            try:
                data = self._make_places_api_request(url, params, timeout=10)
                
                if data['status'] == 'OK':
                    for gym in data.get('results', []):
                        place_id = gym.get('place_id')
                        if place_id in seen_place_ids:
                            continue
                        
                        # Check if it's actually a gym-like place
                        types = gym.get('types', [])
                        name_lower = gym.get('name', '').lower()
                        
                        # More lenient filtering for keyword searches
                        is_gym_related = (
                            'gym' in types or 
                            'health' in types or 
                            'gym' in name_lower or 
                            'fitness' in name_lower or 
                            'training' in name_lower or
                            'crossfit' in name_lower or
                            'pilates' in name_lower or
                            'yoga' in name_lower or
                            'workout' in name_lower
                        )
                        
                        if is_gym_related:
                            seen_place_ids.add(place_id)
                            
                            gym_lat = gym['geometry']['location']['lat']
                            gym_lng = gym['geometry']['location']['lng']
                            distance = self._haversine_distance(lat, lng, gym_lat, gym_lng)
                            
                            gyms.append({
                                'name': gym.get('name'),
                                'place_id': place_id,
                                'address': gym.get('vicinity'),
                                'rating': gym.get('rating', 0),
                                'user_ratings_total': gym.get('user_ratings_total', 0),
                                'types': types,
                                'distance_miles': round(distance, 2),
                                'lat': gym_lat,
                                'lng': gym_lng,
                            })
                
            except Exception as e:
                print(f"  Error in text search for '{search_term}': {e}")
                continue
        
        return gyms
    
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
    
    def get_nearby_public_garages(self, lat: float, lng: float, radius_miles: float = 0.25) -> List[Dict[str, Any]]:
        """
        Find nearby SFMTA and public parking garages
        
        Args:
            lat: Latitude
            lng: Longitude
            radius_miles: Search radius in miles (default 0.25)
            
        Returns:
            List of garage dictionaries with details
        """
        cache_key = f"public_garages_{lat}_{lng}_{radius_miles}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            radius_meters = radius_miles * 1609.34
            
            # Search for parking facilities
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': int(radius_meters),
                'type': 'parking',
                'key': self.api_key,
            }
            
            data = self._make_places_api_request(url, params, timeout=10)
            
            if data['status'] != 'OK' and data['status'] != 'ZERO_RESULTS':
                print(f"Garage search error: {data['status']}")
                return []
            
            garages = []
            for place in data.get('results', []):
                name = place.get('name', '')
                
                # Filter for public/SFMTA garages
                # Look for keywords indicating public garages
                is_public = any(keyword in name.lower() for keyword in [
                    'sfmta', 'public', 'parking garage', 'parking structure',
                    'city parking', 'municipal', 'civic center garage',
                    'public garage', 'downtown garage'
                ])
                
                # Exclude private/residential/hotel parking
                is_private = any(keyword in name.lower() for keyword in [
                    'hotel', 'hospital', 'private', 'resident', 'employee only',
                    'permit', 'reserved', 'validation only'
                ])
                
                if not is_public or is_private:
                    continue
                
                place_lat = place['geometry']['location']['lat']
                place_lng = place['geometry']['location']['lng']
                distance_miles = self._haversine_distance(lat, lng, place_lat, place_lng)
                
                garages.append({
                    'name': name,
                    'address': place.get('vicinity', ''),
                    'distance_miles': round(distance_miles, 2),
                    'place_id': place.get('place_id'),
                    'rating': place.get('rating'),
                    'user_ratings_total': place.get('user_ratings_total', 0),
                })
            
            # Sort by distance
            garages.sort(key=lambda x: x['distance_miles'])
            
            self.cache.set(cache_key, garages)
            return garages
        
        except Exception as e:
            print(f"Error finding public garages: {e}")
            return []
    
    def estimate_visitor_parking_ease(self, lat: float, lng: float, address: str = "") -> Dict[str, Any]:
        """
        Estimate visitor parking ease based on SFMTA/public garages and street parking
        
        Focuses on short-term visitor parking options:
        - SFMTA garages (ideal for visitors)
        - Public parking structures
        - General area parking availability
        
        Args:
            lat: Latitude
            lng: Longitude
            address: Optional address for additional context
            
        Returns:
            Dictionary with parking_ease (1-10), reasoning, and garage details
        """
        cache_key = f"visitor_parking_{lat}_{lng}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Search for public garages within 0.25 miles
            garages = self.get_nearby_public_garages(lat, lng, radius_miles=0.25)
            
            # Also check general parking facilities
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': 500,  # 500m radius
                'key': self.api_key,
            }
            
            data = self._make_places_api_request(url, params, timeout=10)
            
            if data['status'] != 'OK' and data['status'] != 'ZERO_RESULTS':
                print(f"Places API error: {data['status']}")
                return {'parking_ease': 5, 'reasoning': f'Unable to determine ({data["status"]}), defaulting to moderate'}
            
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
            
            # Scoring (1-10 scale for visitor parking)
            score = 5  # Start with moderate
            reasoning_parts = []
            
            # SFMTA/public garages are a huge bonus for visitors
            if garages:
                closest_garage = garages[0]
                if closest_garage['distance_miles'] <= 0.1:
                    score += 3
                    reasoning_parts.append(f"{closest_garage['name']} within 0.1 mi")
                elif closest_garage['distance_miles'] <= 0.2:
                    score += 2
                    reasoning_parts.append(f"{closest_garage['name']} within 0.2 mi")
                else:
                    score += 1
                    reasoning_parts.append(f"{closest_garage['name']} within 0.25 mi")
            
            # Other parking facilities
            if parking_lots >= 3:
                score += 2
                reasoning_parts.append(f"{parking_lots} parking facilities nearby")
            elif parking_lots >= 1:
                score += 1
                reasoning_parts.append(f"{parking_lots} parking facility nearby")
            
            # Commercial activity affects visitor parking
            if commercial_count > 15:
                score -= 2
                reasoning_parts.append("busy commercial area (competitive parking)")
            elif commercial_count > 8:
                score -= 1
                reasoning_parts.append("moderate commercial activity")
            else:
                reasoning_parts.append("quiet area (easier street parking)")
            
            # Residential areas generally have some street parking
            if residential_count > commercial_count:
                score += 1
                reasoning_parts.append("primarily residential")
            
            # Clamp to 1-10 range
            score = max(1, min(10, round(score)))
            
            result = {
                'parking_ease': int(score),
                'reasoning': ', '.join(reasoning_parts) if reasoning_parts else 'Based on area characteristics',
                'public_garages': garages,
                'parking_facilities_count': parking_lots,
                'commercial_density': commercial_count,
            }
            
            self.cache.set(cache_key, result)
            return result
        
        except Exception as e:
            print(f"Error estimating visitor parking ease: {e}")
            import traceback
            traceback.print_exc()
            return {
                'parking_ease': 5,
                'reasoning': 'Error determining parking ease, defaulting to moderate'
            }
    
    def estimate_street_parking_ease(self, lat: float, lng: float, address: str = "") -> Dict[str, Any]:
        """
        Estimate STREET parking ease for residential parking (long-term, daily use)
        
        Focuses on finding street parking near your apartment consistently:
        - Residential vs commercial area (competition for spots)
        - Permit zones
        - Area density
        
        This is separate from visitor parking as it rates feasibility of parking
        your own car on the street regularly, not one-time visitor parking.
        
        Args:
            lat: Latitude
            lng: Longitude
            address: Optional address for additional context
            
        Returns:
            Dictionary with parking_ease (1-10) and reasoning
        """
        cache_key = f"street_parking_{lat}_{lng}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Search nearby area characteristics
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': 300,  # Smaller radius for street parking (about 1 block)
                'key': self.api_key,
            }
            
            data = self._make_places_api_request(url, params, timeout=10)
            
            if data['status'] != 'OK' and data['status'] != 'ZERO_RESULTS':
                print(f"Places API error: {data['status']}")
                return {'parking_ease': 5, 'reasoning': f'Unable to determine ({data["status"]}), defaulting to moderate'}
            
            places = data.get('results', [])
            
            # Analyze competition for street parking
            restaurants = 0
            bars = 0
            shops = 0
            residential = 0
            apartments = 0
            
            for place in places:
                types = place.get('types', [])
                name = place.get('name', '').lower()
                
                if 'restaurant' in types:
                    restaurants += 1
                if 'bar' in types or 'night_club' in types:
                    bars += 1
                if any(t in types for t in ['store', 'shopping_mall', 'supermarket']):
                    shops += 1
                if 'residential' in ' '.join(types):
                    residential += 1
                if any(keyword in name for keyword in ['apartment', 'residence', 'condos']):
                    apartments += 1
            
            # Street parking scoring (1-10)
            score = 6  # Start slightly above moderate (SF street parking baseline)
            reasoning_parts = []
            
            # High-density residential means more competition
            if apartments > 5:
                score -= 2
                reasoning_parts.append(f"{apartments} apartment buildings (high competition)")
            elif apartments > 2:
                score -= 1
                reasoning_parts.append(f"{apartments} apartment buildings nearby")
            
            # Commercial activity hurts street parking significantly
            total_commercial = restaurants + bars + shops
            if total_commercial > 10:
                score -= 3
                reasoning_parts.append(f"very busy area ({total_commercial} businesses)")
            elif total_commercial > 5:
                score -= 2
                reasoning_parts.append(f"busy area ({total_commercial} businesses)")
            elif total_commercial > 2:
                score -= 1
                reasoning_parts.append(f"moderate commercial activity")
            else:
                score += 1
                reasoning_parts.append("quiet residential area")
            
            # Bars/nightlife are especially bad (evening parking)
            if bars >= 3:
                score -= 1
                reasoning_parts.append("nightlife area (evening competition)")
            
            # Pure residential is best for street parking
            if residential > 5 and total_commercial < 3:
                score += 2
                reasoning_parts.append("primarily residential neighborhood")
            
            # Clamp to 1-10 range
            score = max(1, min(10, round(score)))
            
            result = {
                'parking_ease': int(score),
                'reasoning': ', '.join(reasoning_parts) if reasoning_parts else 'Based on area characteristics',
                'nearby_apartments': apartments,
                'commercial_count': total_commercial,
                'nightlife_count': bars,
            }
            
            self.cache.set(cache_key, result)
            return result
        
        except Exception as e:
            print(f"Error estimating street parking ease: {e}")
            import traceback
            traceback.print_exc()
            return {
                'parking_ease': 5,
                'reasoning': 'Error determining parking ease, defaulting to moderate'
            }
    
    def estimate_parking_ease(self, lat: float, lng: float, address: str = "") -> Dict[str, Any]:
        """
        Legacy method - now delegates to estimate_visitor_parking_ease for backward compatibility
        """
        return self.estimate_visitor_parking_ease(lat, lng, address)
    
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
            
            data = self._make_places_api_request(url, params, timeout=10)
            
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
    
    def _get_travel_times(self, origin_lat: float, origin_lng: float, 
                          destinations: List[Tuple[float, float]], 
                          mode: str = 'walking') -> List[Dict[str, Any]]:
        """
        Get travel times from origin to multiple destinations using Distance Matrix API
        
        Args:
            origin_lat: Origin latitude
            origin_lng: Origin longitude
            destinations: List of (lat, lng) tuples for destinations
            mode: Travel mode - 'walking' or 'bicycling'
            
        Returns:
            List of dictionaries with duration_mins and distance_miles
        """
        if not destinations:
            return []
        
        try:
            # Rate limit: Google Directions API (Distance Matrix uses same quota)
            self.rate_limiter.wait_if_needed('google_directions')
            
            # Distance Matrix API
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            
            origin = f"{origin_lat},{origin_lng}"
            dest_str = "|".join([f"{lat},{lng}" for lat, lng in destinations])
            
            params = {
                'origins': origin,
                'destinations': dest_str,
                'mode': mode,
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
            print(f"Error getting {mode} times: {e}")
            return [{'duration_mins': None, 'distance_miles': None} for _ in destinations]
    
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
        return self._get_travel_times(origin_lat, origin_lng, destinations, mode='walking')
    
    def _get_biking_times(self, origin_lat: float, origin_lng: float, 
                         destinations: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
        """
        Get biking times from origin to multiple destinations using Distance Matrix API
        
        Args:
            origin_lat: Origin latitude
            origin_lng: Origin longitude
            destinations: List of (lat, lng) tuples for destinations
            
        Returns:
            List of dictionaries with duration_mins and distance_miles
        """
        return self._get_travel_times(origin_lat, origin_lng, destinations, mode='bicycling')
    
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
    
    def get_avg_walk_time_to_places_of_interest(self, apartment_lat: float, apartment_lng: float, 
                                                 places_of_interest: List[Dict]) -> Dict[str, Any]:
        """
        Calculate average walking time to top 5 nearest places of interest
        
        Args:
            apartment_lat: Apartment latitude
            apartment_lng: Apartment longitude
            places_of_interest: List of dicts with 'Name', 'Latitude', 'Longitude'
            
        Returns:
            Dict with avg_walk_time_mins, nearest_places_info, and count
        """
        if not places_of_interest:
            return {
                'avg_walk_time_mins': None,
                'nearest_places': [],
                'count': 0
            }
        
        # Step 1: Build list of place coords and filter to SF area only
        place_coords = []
        for place in places_of_interest:
            try:
                lat = float(place.get('Latitude', 0))
                lng = float(place.get('Longitude', 0))
                if lat and lng:
                    # Basic SF bounds check (approximately)
                    if 37.7 <= lat <= 37.83 and -122.52 <= lng <= -122.35:
                        place_coords.append({
                            'name': place.get('Name', 'Unknown'),
                            'lat': lat,
                            'lng': lng
                        })
            except (ValueError, TypeError):
                continue
        
        if not place_coords:
            return {
                'avg_walk_time_mins': None,
                'nearest_places': [],
                'count': 0
            }
        
        # Step 2: Filter to places within ~2 miles using haversine (cheap, no API call)
        # This reduces the number of places we need to query with Distance Matrix API
        INITIAL_FILTER_RADIUS_MILES = 2.0
        nearby_places = []
        for place_data in place_coords:
            haversine_dist = self._calculate_distance(
                apartment_lat, apartment_lng,
                place_data['lat'], place_data['lng']
            )
            if haversine_dist <= INITIAL_FILTER_RADIUS_MILES:
                nearby_places.append({
                    **place_data,
                    'haversine_dist': haversine_dist
                })
        
        if not nearby_places:
            print(f"  ℹ️  No places of interest within {INITIAL_FILTER_RADIUS_MILES} miles (filtered from {len(place_coords)} total SF places)")
            return {
                'avg_walk_time_mins': None,
                'nearest_places': [],
                'count': 0
            }
        
        print(f"  ✓ Filtered to {len(nearby_places)} places within {INITIAL_FILTER_RADIUS_MILES} miles (from {len(place_coords)} total SF places)")
        
        # Step 3: Calculate walking times using Distance Matrix API
        # Batch requests if needed (API limit is 100 elements per request)
        MAX_DESTINATIONS_PER_BATCH = 25  # Conservative limit to avoid hitting API quotas
        
        all_walking_times = []
        for batch_start in range(0, len(nearby_places), MAX_DESTINATIONS_PER_BATCH):
            batch_end = min(batch_start + MAX_DESTINATIONS_PER_BATCH, len(nearby_places))
            batch_places = nearby_places[batch_start:batch_end]
            
            print(f"  📍 Fetching walking times for batch {batch_start//MAX_DESTINATIONS_PER_BATCH + 1} ({len(batch_places)} places)...")
            
            coords_list = [(p['lat'], p['lng']) for p in batch_places]
            batch_walking_times = self._get_walking_times(apartment_lat, apartment_lng, coords_list)
            all_walking_times.extend(batch_walking_times)
            
            # Brief pause between batches to respect rate limits
            if batch_end < len(nearby_places):
                time.sleep(0.5)
        
        # Step 4: Combine results and sort by walking time
        place_walk_times = []
        for i, place_data in enumerate(nearby_places):
            walk_time_data = all_walking_times[i]
            walk_time = walk_time_data.get('duration_mins')
            
            if walk_time is not None:
                place_walk_times.append({
                    'name': place_data['name'],
                    'walk_time_mins': walk_time,
                    'haversine_dist': place_data['haversine_dist'],
                    'distance_miles': walk_time_data.get('distance_miles')
                })
        
        if not place_walk_times:
            return {
                'avg_walk_time_mins': None,
                'nearest_places': [],
                'count': 0
            }
        
        # Sort by walk time and take top 5
        place_walk_times.sort(key=lambda x: x['walk_time_mins'])
        top_5 = place_walk_times[:5]
        
        # Calculate average
        avg_walk_time = sum(p['walk_time_mins'] for p in top_5) / len(top_5)
        
        return {
            'avg_walk_time_mins': round(avg_walk_time, 1),
            'nearest_places': top_5,
            'count': len(top_5)
        }

