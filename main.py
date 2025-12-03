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
            self.location_analyzer = LocationAnalyzer()
            self.cache = get_cache()
            
            print("✓ All components initialized successfully")
        except Exception as e:
            print(f"✗ Error initializing components: {e}")
            print("\nPlease check:")
            print("1. Google Sheets credentials are in place")
            print("2. API keys are set in .env file")
            print("3. All dependencies are installed")
            raise
    
    def analyze_apartment(self, row_data: Dict[str, Any], force_refresh: bool = False) -> Dict[str, Any]:
        """
        Analyze a single apartment
        
        Args:
            row_data: Row data from Google Sheets (must include basic info)
            force_refresh: Force re-analysis even if cached
            
        Returns:
            Dictionary with all analysis results
        """
        address = row_data.get(config.SHEET_COLUMNS["address"], "").strip()
        manual_safety = row_data.get(config.SHEET_COLUMNS["manual_safety"], 5.0)
        
        if not address:
            return {'error': 'No address provided'}
        
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
            print(f"\n[3/3] Analyzing location...")
            if result['address']:
                location_data = self.location_analyzer.analyze_location(result['address'])
                
                result['commute_duration'] = location_data.get('commute_duration', 999)
                result['commute_route'] = location_data.get('commute_route', '')
                result['commute_duration_partner'] = location_data.get('commute_duration_partner', 999)
                result['route_annoyingness'] = location_data.get('route_annoyingness', 10.0)
                commute_details = location_data.get('commute_details', {})
                result['commute_details'] = commute_details
                result['commute_details_json'] = json.dumps(commute_details) if commute_details else ""
                result['safety_score_opendata'] = location_data.get('safety_score_opendata', 5.0)
                result['incident_count'] = location_data.get('incident_count', 0)
                result['avg_severity'] = location_data.get('avg_severity')
                result['count_score'] = location_data.get('count_score')
                result['severity_score'] = location_data.get('severity_score')
                crime_details = location_data.get('crime_details')
                if crime_details:
                    result['crime_details'] = crime_details
                result['restaurants_nearby'] = location_data.get('restaurants_nearby', 0)
                result['cafes_nearby'] = location_data.get('cafes_nearby', 0)
                result['parks_nearby'] = location_data.get('parks_nearby', 0)
                
                # Check if user has pre-selected gyms
                selected_gyms_str = result.get('selected_gyms', '').strip()
                
                if selected_gyms_str:
                    # User has pre-selected gyms - calculate score based on nearest one
                    print(f"  Using selected gyms: {selected_gyms_str}")
                    selected_gym_names = [name.strip() for name in selected_gyms_str.split(',')]
                    
                    # Get approved gyms sheet to find coordinates
                    approved_gyms = self.sheets_client.get_approved_gyms()
                    
                    # Find nearest selected gym
                    apartment_coords = (location_data.get('latitude'), location_data.get('longitude'))
                    nearest_selected = None
                    min_distance = float('inf')
                    
                    for gym in approved_gyms:
                        if gym.get('Gym Name') in selected_gym_names:
                            gym_lat = gym.get('Latitude')
                            gym_lng = gym.get('Longitude')
                            if apartment_coords[0] and gym_lat:
                                distance = self.location_analyzer._haversine_distance(
                                    apartment_coords[0], apartment_coords[1],
                                    float(gym_lat), float(gym_lng)
                                )
                                if distance < min_distance:
                                    min_distance = distance
                                    nearest_selected = gym
                    
                    if nearest_selected:
                        result['gym_within_10min'] = min_distance <= 0.5  # ~10 min walk
                        result['gym_quality'] = float(nearest_selected.get('Rating', 0)) * 2
                        print(f"  Nearest selected gym: {nearest_selected.get('Gym Name')} ({min_distance:.2f} mi)")
                    else:
                        # Fall back to automatic detection
                        result['gym_within_10min'] = location_data.get('gym_within_10min', False)
                        result['gym_quality'] = location_data.get('gym_quality', 0.0)
                else:
                    # Use automatic detection
                    result['gym_within_10min'] = location_data.get('gym_within_10min', False)
                    result['gym_quality'] = location_data.get('gym_quality', 0.0)
                
                print(f"✓ Location analysis complete")
                print(f"  Your commute: {result['commute_duration']} min via {result['commute_route']}")
                print(f"  Partner commute: {result['commute_duration_partner']} min")
                if result.get('route_annoyingness') is not None:
                    print(f"  Route annoyingness: {result['route_annoyingness']:.1f}/10")
                print(f"  Safety score: {result['safety_score_opendata']:.1f}/10")
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
            scorecard = build_scorecard(result)
            
            # Calculate total score
            total_score = scorecard.calculate_total()
            result['weighted_score'] = round(total_score, 2)
            
            # Calculate score range (for uncertain data)
            score_min, score_max = scorecard.calculate_total_range()
            result['score_min'] = round(score_min, 2)
            result['score_max'] = round(score_max, 2)
            result['score_certainty'] = round(scorecard.get_certainty_percentage(), 1)
            
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
            result['location_vibe_score'] = scorecard.components['location_vibe'].raw_value
            result['parking_score'] = scorecard.components['parking'].raw_value
            
            # Prepare JSON fields for sheet storage
            if 'commute_details' in result:
                result['commute_details_json'] = result['commute_details']
            if 'crime_details' in result:
                result['crime_details_json'] = result['crime_details']
                try:
                    print(f"  -> Crime details prepared ({result['address']}): {json.dumps(result['crime_details'])[:200]}...")
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

