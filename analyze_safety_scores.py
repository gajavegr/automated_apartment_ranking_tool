"""
Analyze safety scores from the Google Sheet to understand current methodology and distributions

This script will:
1. Query the Google Sheet for all apartments
2. Analyze the distribution of open data safety scores
3. Provide statistics on the current methodology
4. Offer recommendations for improvements
"""

import statistics
from collections import Counter
from typing import List, Dict, Any
import json

from utils.google_sheets import GoogleSheetsClient
import config


def analyze_safety_data():
    """Query and analyze safety scores from Google Sheet"""
    
    print("=" * 80)
    print("SAFETY SCORE ANALYSIS")
    print("=" * 80)
    
    # Initialize Google Sheets client
    print("\n📊 Connecting to Google Sheet...")
    client = GoogleSheetsClient()
    
    # Read all apartment data
    print("📥 Reading apartment data...")
    records = client.read_main_sheet()
    
    # Filter to apartments with data
    apartments_with_data = []
    for record in records:
        address = record.get(config.SHEET_COLUMNS["address"], "").strip()
        if not address:
            continue
        
        opendata_score = record.get(config.SHEET_COLUMNS["safety_score_opendata"])
        if opendata_score and opendata_score != "":
            try:
                opendata_score_float = float(opendata_score)
                apartments_with_data.append({
                    'address': address,
                    'opendata_score': opendata_score_float,
                    'manual_score': record.get(config.SHEET_COLUMNS["manual_safety"], ""),
                    'combined_score': record.get(config.SHEET_COLUMNS["combined_safety"], ""),
                    'crime_details': record.get(config.SHEET_COLUMNS["crime_details"], ""),
                    'floor_level': record.get(config.SHEET_COLUMNS["floor_level"], ""),
                    'neighborhood': record.get(config.SHEET_COLUMNS["neighborhood"], ""),
                })
            except (ValueError, TypeError):
                continue
    
    print(f"\n✓ Found {len(apartments_with_data)} apartments with safety data")
    
    if not apartments_with_data:
        print("\n⚠️  No apartments with safety scores found!")
        return
    
    # Analyze distribution
    print("\n" + "=" * 80)
    print("OPEN DATA SAFETY SCORE DISTRIBUTION")
    print("=" * 80)
    
    opendata_scores = [apt['opendata_score'] for apt in apartments_with_data]
    
    # Basic statistics
    print(f"\n📈 Statistics:")
    print(f"   Count: {len(opendata_scores)}")
    print(f"   Mean: {statistics.mean(opendata_scores):.2f}")
    print(f"   Median: {statistics.median(opendata_scores):.2f}")
    print(f"   Min: {min(opendata_scores):.2f}")
    print(f"   Max: {max(opendata_scores):.2f}")
    print(f"   Std Dev: {statistics.stdev(opendata_scores):.2f}" if len(opendata_scores) > 1 else "   Std Dev: N/A")
    
    # Distribution by range
    print(f"\n📊 Distribution by range:")
    ranges = {
        "0-2": 0,
        "2-4": 0,
        "4-6": 0,
        "6-8": 0,
        "8-10": 0,
    }
    
    for score in opendata_scores:
        if score < 2:
            ranges["0-2"] += 1
        elif score < 4:
            ranges["2-4"] += 1
        elif score < 6:
            ranges["4-6"] += 1
        elif score < 8:
            ranges["6-8"] += 1
        else:
            ranges["8-10"] += 1
    
    for range_name, count in ranges.items():
        percentage = (count / len(opendata_scores)) * 100
        bar = "█" * int(percentage / 2)
        print(f"   {range_name}: {count:2d} ({percentage:5.1f}%) {bar}")
    
    # Check if ~3 is common
    near_3_count = sum(1 for s in opendata_scores if 2.5 <= s <= 3.5)
    near_3_percentage = (near_3_count / len(opendata_scores)) * 100
    print(f"\n⚠️  Scores between 2.5-3.5: {near_3_count} ({near_3_percentage:.1f}%)")
    
    # Analyze by neighborhood
    print("\n" + "=" * 80)
    print("SAFETY SCORES BY NEIGHBORHOOD")
    print("=" * 80)
    
    neighborhood_scores = {}
    for apt in apartments_with_data:
        neighborhood = apt['neighborhood']
        if neighborhood and neighborhood != "":
            if neighborhood not in neighborhood_scores:
                neighborhood_scores[neighborhood] = []
            neighborhood_scores[neighborhood].append(apt['opendata_score'])
    
    if neighborhood_scores:
        print(f"\n📍 Average scores by neighborhood:")
        sorted_neighborhoods = sorted(
            neighborhood_scores.items(),
            key=lambda x: statistics.mean(x[1]),
            reverse=True
        )
        
        for neighborhood, scores in sorted_neighborhoods[:10]:  # Top 10
            avg = statistics.mean(scores)
            print(f"   {neighborhood:30s}: {avg:.2f} (n={len(scores)})")
    
    # Analyze crime details to understand methodology
    print("\n" + "=" * 80)
    print("CURRENT METHODOLOGY ANALYSIS")
    print("=" * 80)
    
    print(f"\n🔍 Current settings:")
    print(f"   Radius: {config.CRIME_RADIUS_MILES} miles ({config.CRIME_RADIUS_MILES * 1609.34:.0f} meters)")
    print(f"   Lookback period: {config.CRIME_LOOKBACK_MONTHS} months")
    print(f"   SF Crime Baseline: {config.SF_CRIME_BASELINE} incidents/year")
    
    # Sample a few crime details
    print(f"\n📋 Sample crime details (first 3 apartments):")
    for i, apt in enumerate(apartments_with_data[:3]):
        crime_details = apt.get('crime_details', '')
        if crime_details:
            try:
                crime_data = json.loads(crime_details) if isinstance(crime_details, str) else crime_details
                total_incidents = crime_data.get('total_incidents', 0)
                weighted_score = crime_data.get('weighted_score', 0)
                print(f"\n   {i+1}. {apt['address'][:50]}")
                print(f"      Total incidents: {total_incidents}")
                print(f"      Weighted score: {weighted_score:.2f}")
                print(f"      OpenData safety score: {apt['opendata_score']:.2f}")
                
                # Show top crime categories
                by_category = crime_data.get('by_category', {})
                if by_category:
                    top_crimes = sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:3]
                    print(f"      Top crimes: {', '.join([f'{cat} ({count})' for cat, count in top_crimes])}")
            except:
                print(f"\n   {i+1}. {apt['address'][:50]} - Could not parse crime details")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    print(f"\n💡 Based on this analysis:")
    
    if near_3_percentage > 30:
        print(f"\n   ⚠️  {near_3_percentage:.1f}% of apartments score 2.5-3.5, suggesting the current")
        print(f"      methodology may be clustering scores in the low range.")
    
    print(f"\n   1. RADIUS CONSIDERATION:")
    print(f"      - Current: {config.CRIME_RADIUS_MILES} mile radius")
    print(f"      - Consider: Use multiple radii for more granular scoring")
    print(f"        • Immediate (0.1 mile): Highest weight")
    print(f"        • Near (0.25 mile): Medium weight")
    print(f"        • Neighborhood (0.5 mile): Lower weight")
    
    print(f"\n   2. BUILDING FEATURES:")
    print(f"      - Add security features to scoring:")
    print(f"        • 24/7 security/concierge: +1.5 points")
    print(f"        • Controlled access/digital locks: +1.0 points")
    print(f"        • Security cameras: +0.5 points")
    print(f"        • Gated parking: +0.5 points")
    
    print(f"\n   3. FLOOR LEVEL:")
    print(f"      - Higher floors = harder to access from outside")
    print(f"        • Ground floor: +0 points")
    print(f"        • 2nd-3rd floor: +0.3 points")
    print(f"        • 4th+ floor: +0.5 points")
    
    print(f"\n   4. PROXIMITY TO INSTITUTIONS:")
    print(f"      - Near schools, police stations, fire stations")
    print(f"        • Within 0.25 mile of school: +0.3 points")
    print(f"        • Within 0.5 mile of police station: +0.2 points")
    
    print(f"\n   5. HIGHWAY OVERPASSES:")
    print(f"      - Detect proximity to highway overpasses")
    print(f"        • Under/very near overpass: -0.5 points")
    print(f"        • This could be done using Google Maps API for roads")
    
    print(f"\n   6. TIME OF DAY VARIATION:")
    print(f"      - Weight crimes differently by time")
    print(f"        • Night crimes (8PM-6AM): 1.5x weight")
    print(f"        • Weekend crimes: 1.2x weight")
    
    # Show sample implementation
    print("\n" + "=" * 80)
    print("SAMPLE ENHANCED SCORING FORMULA")
    print("=" * 80)
    
    print("""
    Enhanced Safety Score = Base Score + Building Features + Floor Bonus + Proximity Bonuses
    
    Base Score (from crime data):
        - Weighted by distance rings
        - Immediate area (0.1mi): 50% weight
        - Near area (0.25mi): 30% weight  
        - Neighborhood (0.5mi): 20% weight
    
    Building Features (max +3 points):
        + 1.5 if has_24_7_security
        + 1.0 if has_digital_locks
        + 0.5 if has_security_cameras
        + 0.5 if has_gated_parking
    
    Floor Bonus (max +0.5 points):
        + 0.0 if ground floor
        + 0.3 if floor 2-3
        + 0.5 if floor 4+
    
    Proximity Bonuses (max +0.5 points):
        + 0.3 if school within 0.25mi
        + 0.2 if police station within 0.5mi
        - 0.5 if under/near highway overpass
    
    Final score capped at 0-10 scale
    """)
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    analyze_safety_data()










