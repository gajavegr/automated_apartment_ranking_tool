"""
Configuration for Apartment Value Analyzer

This file contains all scoring weights, thresholds, and ideal criteria definitions.
Adjust these values to match your priorities.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials/google_sheets_credentials.json")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# Work Locations
YOUR_WORK_ADDRESS = os.getenv("YOUR_WORK_ADDRESS", "4100 E 3rd Ave, Foster City, CA 94404")
PARTNER_WORK_ADDRESS = os.getenv("PARTNER_WORK_ADDRESS", "1355 Market St, San Francisco, CA 94103")
PARTNER_COMMUTE_MODE = os.getenv("PARTNER_COMMUTE_MODE", "transit").lower()
PARTNER_COMMUTE_FALLBACK_MODE = os.getenv("PARTNER_COMMUTE_FALLBACK_MODE", "walking").lower()

# Commute Departure Times (24-hour format, HH:MM)
AM_DEPARTURE_TIME = os.getenv("AM_DEPARTURE_TIME", "08:30")
PM_DEPARTURE_TIME = os.getenv("PM_DEPARTURE_TIME", "18:00")

# SF OpenData API
SF_OPENDATA_API_ENDPOINT = os.getenv("SF_OPENDATA_API_ENDPOINT", "https://data.sfgov.org/resource/wg3w-h783.json")
SF_OPENDATA_APP_TOKEN = os.getenv("SF_OPENDATA_APP_TOKEN")  # Get your token at: https://data.sfgov.org/profile/edit/developer_settings

# Cache Configuration
CACHE_DIR = os.getenv("CACHE_DIR", ".cache")
CACHE_EXPIRE_HOURS = int(os.getenv("CACHE_EXPIRE_HOURS", "168"))  # 1 week default

# Google Sheet Column Names
SHEET_COLUMNS = {
    # Input columns
    "zillow_url": "Zillow URL",
    "manual_safety": "Manual Safety Rating",
    
    # Basic info
    "address": "Address",
    "price": "Price",
    "bedrooms": "Bedrooms",
    "bathrooms": "Bathrooms",
    "sqft": "Square Feet",
    
    # Commute
    "commute_time_you": "Commute Time (You)",
    "commute_route": "Commute Route",
    "commute_time_partner": "Commute Time (Partner)",
    "route_annoyingness": "Route Annoyingness (0-10)",
    "commute_details": "Commute Details (JSON)",
    "commute_score": "Commute Score",
    
    # Safety
    "safety_score_opendata": "Safety Score (OpenData)",
    "combined_safety": "Combined Safety",
    "crime_details": "Crime Details (JSON)",
    
    # WFH Quality
    "wfh_quality_score": "WFH Quality Score",
    "natural_light": "Natural Light",
    "desk_space_quality": "Desk Space Quality",
    "quietness_score": "Quietness Score",
    "double_pane_windows": "Double Pane Windows",
    "study_door_type": "Study Door Type",
    "kitchen_quality": "Kitchen Quality",
    
    # Happening Score (formerly Location Vibe)
    "happening_score": "Happening Score",
    "restaurants_nearby": "Restaurants Nearby",
    "restaurants_list": "Restaurants List (JSON)",
    "cafes_nearby": "Cafes Nearby",
    "cafes_list": "Cafes List (JSON)",
    "parks_nearby": "Parks Nearby",
    "parks_list": "Parks List (JSON)",
    "pois_list": "POIs List (JSON)",
    "avg_walk_to_poi_mins": "Avg Walk to Top 5 POIs (min)",
    "nearest_poi_count": "Nearest POIs Count",
    "pois_within_1_mile": "POIs Within 1 Mile",
    
    # Parking
    "parking_type": "Parking Type",
    "parking_enclosure": "Parking Enclosure",
    "parking_distance": "Parking Distance",
    "parking_cost": "Parking Cost ($/month)",
    "street_parking_ease": "Street Parking Ease",
    "visitor_parking_ease": "Visitor Parking Ease",
    "parking_score": "Parking Score",
    
    # Other amenities
    "laundry_type": "Laundry Type",
    "laundry_score": "Laundry Score",
    "floor_level": "Floor Level",
    "view_quality": "View Quality",
    "gym_within_10min": "Gym Within 20min",  # Updated from 10min to 20min (any mode)
    "gym_walk_time_mins": "Gym Walk Time (min)",  # Walking time in minutes
    "gym_bike_time_mins": "Gym Bike Time (min)",  # Biking time in minutes (if >15min walk)
    "gym_transport_mode": "Gym Transport Mode",  # User's preferred mode: 'walk' or 'bike'
    "gym_effective_time_mins": "Gym Time Used for Score (min)",  # Effective time based on transport mode
    "gym_quality": "Gym Quality",
    "gym_score": "Gym Score",
    "office_gym_only": "Office Gym Only",  # New field for office-only option
    "rent_control": "Rent Control Protected",
    "year_built": "Year Built",
    "neighborhood": "Neighborhood",
    "neighborhoods": "Neighborhoods",  # Multi-select neighborhood list
    
    # Space & Luxury
    "sqft_min": "Square Feet (Min)",
    "sqft_max": "Square Feet (Max)",
    "has_double_vanity": "Has Double Vanity",
    "high_end_appliances": "High-End Appliances",
    "walk_in_closet": "Walk-In Closet",
    "has_balcony_patio": "Has Balcony/Patio",
    "has_fireplace": "Has Fireplace",
    "space_luxury_score": "Space & Luxury Score",
    
    # Score ranges and tour questions
    "tour_questions": "Tour Questions",
    "score_min": "Score Min",
    "score_max": "Score Max",
    "score_certainty": "Score Certainty (%)",
    "score_vs_max": "Score vs Max (%)",
    
    # Terrain/elevation data
    "apartment_elevation": "Apartment Elevation (m)",
    "elevation_to_gym": "Elevation Gain to Gym (m)",
    "elevation_to_work": "Elevation Gain to Work (m)",
    "hilliness_manual_override": "Hilliness Override (0-10)",
    
    # Gym selection
    "selected_gyms": "Selected Gyms",
    
    # Availability status
    "availability_status": "Availability Status",
    
    # Final scores
    "weighted_score": "Weighted Score",
    "value_ratio": "Value Ratio",
    "last_updated": "Last Updated",
    "last_analyzed": "Last Analyzed",
}

# San Francisco Neighborhoods
# Comprehensive list including official names and commonly-used informal names
# NOTE: This list includes both Google Maps API names AND common informal names
SF_NEIGHBORHOODS = [
    "Alamo Square",
    "Anza Vista",
    "Balboa Park",
    "Balboa Terrace",
    "Bayview",
    "Bernal Heights",
    "Castro",
    "Chinatown",
    "Civic Center",
    "Cole Valley",
    "Corona Heights",
    "Cow Hollow",
    "Crocker-Amazon",
    "Design District",
    "Diamond Heights",
    "Dogpatch",
    "Dolores Heights",  # Google Maps API name
    "Downtown",
    "Duboce Triangle",
    "Embarcadero",
    "Eureka Valley",
    "Excelsior",
    "FiDi",  # Financial District informal name
    "Fillmore",
    "Financial District",
    "Fisherman's Wharf",
    "Forest Hill",
    "Glen Park",
    "Golden Gate Heights",
    "Haight-Ashbury",
    "Hayes Valley",
    "Hunters Point",
    "Ingleside",
    "Inner Mission",
    "Inner Parkside",
    "Inner Richmond",
    "Inner Sunset",
    "Japantown",
    "Jordan Park",
    "Lake Street",
    "Lakeside",
    "Laurel Heights",
    "Lincoln Park",
    "Little Hollywood",
    "Lone Mountain",
    "Lower Haight",
    "Lower Nob Hill",
    "Lower Pacific Heights",
    "Marina",
    "Merced Heights",
    "Miraloma Park",
    "Mission",
    "Mission Bay",
    "Mission Dolores",
    "Mission Terrace",
    "Nob Hill",
    "NoPa",  # Informal name
    "Noe Valley",
    "North Beach",
    "North Embarcadero",
    "North of the Panhandle",  # Google Maps API name for NoPa
    "North Panhandle",
    "Oceanview",
    "OMI",  # Ocean View, Merced Heights, Ingleside
    "Outer Mission",
    "Outer Parkside",
    "Outer Richmond",
    "Outer Sunset",
    "Pacific Heights",
    "Panhandle",
    "Parkmerced",
    "Parkside",
    "Polk Gulch",
    "Portola",
    "Potrero Hill",
    "Presidio",
    "Presidio Heights",
    "Richmond",
    "Rincon Hill",
    "Russian Hill",
    "Sea Cliff",
    "Showplace Square",
    "SoMa",  # Informal name
    "South Beach",
    "South of Market",  # Google Maps API name for SoMa
    "St. Francis Wood",
    "Stonestown",
    "Sunnyside",
    "Sunset",
    "Telegraph Hill",
    "Tenderloin",
    "Tendernob",  # Tender Nob (between Tenderloin and Nob Hill)
    "The Castro",
    "The Haight",
    "The Marina",
    "The Mission",
    "The Richmond",
    "The Sunset",
    "Twin Peaks",
    "Union Square",
    "Upper Market",
    "Van Ness",
    "Visitacion Valley",
    "West Portal",
    "Western Addition",
    "Westwood Highlands",
    "Westwood Park",
]

# Scoring Components Configuration
SCORE_COMPONENTS = {
    "commute": {
        "weight": 0.10,  # Updated from 0.15 to 0.10 (QoL subsection)
        "preferences": {
            "ideal_duration": 30,  # Minutes
            "acceptable_duration": 60,  # Minutes (increased from 50 to allow more score variation)
            "preferred_route": "280",  # Highway preference
            "route_bonus": 1.5,  # Extra points for preferred route
            "annoyingness_penalty_weight": 0.35,  # (10-annoy) * weight = penalty in points
        }
    },
    "wfh_quality": {
        "weight": 0.15,  # Updated from 0.20 to 0.15
        "inputs": ["natural_light", "desk_space", "quietness", "kitchen"],
        "sub_weights": {
            "natural_light": 0.30,
            "desk_space": 0.30,
            "quietness": 0.25,
            "kitchen": 0.15,
        }
    },
    "quietness": {
        "weight": 0.0,  # Not a top-level category; input to wfh_quality
        "factors": {
            "double_pane_windows": 2.0,  # +2 points for double pane (noise reduction)
            "door_types": {
                "solid_door": 2.0,  # Best isolation for studying
                "sliding_door": 1.5,  # Good but not as sound-proof
                "open": 0.0,  # No door means no isolation
                "none": 0.0,  # No dedicated work space
            },
            "floor_bonuses": {
                "ground": 0.0,
                "mid": 0.5,
                "high": 1.0,
            }
        }
    },
    "happening": {
        "weight": 0.10,  # Standalone category weight
        "scoring": {
            "restaurants": {"max": 3, "weight": 0.20},
            "cafes": {"max": 3, "weight": 0.20},
            "avg_walk_to_poi": {"min_mins": 5, "max_mins": 25, "weight": 0.30},
            "pois_within_1_mile": {"max": 5, "weight": 0.25},
            "parks": {"max": 3, "weight": 0.15}
        }
    },
    "safety": {
        "weight": 0.30,  # Updated from 0.25 to 0.30
        "combine": ["manual_rating", "opendata_rating"],  # Average both
    },
    "parking": {
        "weight": 0.10,  # Updated from 0.13 to 0.10 for total balance (QoL subsection)
        "inputs": ["parking_type", "parking_enclosure", "distance", "street_ease"],
        "base_scores": {
            "two_parking_spaces": 11,  # Premium: 2 dedicated spots (superlative bonus)
            "single_garage": 10,
            "dedicated_spot_car_and_motorcycle": 9,
            "dedicated_spot_car_only": 7,
            "street_parking": 0,  # Base score, adjusted by street_ease
        },
        "enclosure_bonuses": {
            "enclosed": 1.0,    # Garage/underground - weather protection, security
            "covered": 0.5,     # Carport/overhang - some weather protection
            "open": 0.0,        # Outdoor/exposed - no protection
            "": 0.0,            # Unknown/not specified
        },
        "distance_penalties": {
            "onsite": 0,
            "2min_walk": -0.5,
            "5min_walk": -1.5,
            "10min_walk": -3.0,
            "15min_walk": -5.0,
        },
        "street_ease_factors": {
            # Numeric ratings from form (1-5 stars)
            "1": 0.5,   # Very Difficult
            "2": 2.0,   # Difficult
            "3": 3.0,   # Moderate
            "4": 5.0,   # Easy
            "5": 6.0,   # Very Easy
            # Legacy street type mappings (for backwards compatibility)
            "residential_one_way": 6.0,  # Quiet one-way street, easy parking
            "residential_small_street": 5.0,  # Small residential street
            "residential_main_street": 3.0,  # Busier residential street
            "mixed_use_moderate": 2.0,  # Some commercial, moderate traffic
            "busy_commercial": 0.5,  # Busy area, hard to find spots
        },
        "visitor_parking_bonus": {
            "enabled": True,
            "scale": 0.15,  # Street ease contributes 15% as much for dedicated parking (for visitors)
        }
    },
    "laundry": {
        "weight": 0.10,  # Updated to 0.10 (QoL subsection)
        "scoring": {
            "in_unit": 10,              # Separate washer and dryer
            "in_unit_combo": 8,         # Combined washer/dryer unit
            "shared_good": 7,           # Good ratio of machines to units
            "shared_poor": 4,           # Poor ratio, often wait times
            "none": 0,                  # No laundry facilities
        },
        "laundromat_penalty": {
            "enabled": True,
            "cost_per_load": 5.0,       # Average cost per load at laundromat
            "loads_per_week": 1,        # Assumed weekly laundry frequency
            "max_distance_miles": 0.5,  # Search radius for laundromats
        }
    },
    "gym_nearby": {
        "weight": 0.10,  # Updated from 0.05 to 0.10 (QoL subsection)
        "scoring": {
            "has_nearby_good_gym": 10,  # Within 10min and quality >= 7
            "has_nearby_ok_gym": 6,     # Within 10min but quality < 7
            "no_nearby_gym": 0,
            "office_gym_only": -5,      # Only office gym available (inconvenient)
        }
    },
    "rent_control": {
        "weight": 0.0,  # Updated from 0.02 to 0.0 (not part of main score)
        "scoring": {
            "protected": 10,
            "not_protected": 0,
        }
    },
    "space_luxury": {
        "weight": 0.05,  # Updated from 0.12 to 0.05 for total balance (QoL subsection)
        "scoring": {
            "sqft_weight": 0.40,  # 40% from square footage
            "bed_bath_weight": 0.30,  # 30% from bedrooms/bathrooms
            "luxury_weight": 0.30,  # 30% from luxury amenities
            "sqft_thresholds": {
                "min": 400,  # Minimum sqft for scoring (0 points)
                "max": 1000,  # Maximum sqft for full points (10 points)
            },
            "amenity_bonuses": {
                "double_vanity": 2.5,  # Points per amenity (out of 10)
                "high_end_appliances": 2.5,
                "walk_in_closet": 2.5,
                "balcony_patio": 2.5,
            }
        }
    },
}

# Binary "Ideal" Criteria Thresholds
# These define what counts as meeting each ideal criterion for the criteria matrix
IDEAL_CRITERIA = {
    "has_ideal_safety": {
        "condition": lambda scores: scores.get("combined_safety", 0) >= 8.0,
        "description": "Combined safety score ≥ 8/10"
    },
    "has_ideal_commute": {
        "condition": lambda scores: (
            scores.get("commute_duration", 999) <= 35 and 
            scores.get("commute_route", "") == "280"
        ),
        "description": "≤35min commute on 280"
    },
    "has_ideal_parking": {
        "condition": lambda scores: scores.get("parking_score", 0) >= 9.0,
        "description": "Parking score ≥ 9/10 (garage or car+MC spot)"
    },
    "has_ideal_wfh_space": {
        "condition": lambda scores: scores.get("wfh_quality", 0) >= 8.0,
        "description": "WFH quality score ≥ 8/10"
    },
    "has_inunit_laundry": {
        "condition": lambda scores: scores.get("laundry_type", "") == "in_unit",
        "description": "In-unit washer/dryer"
    },
    "has_good_gym": {
        "condition": lambda scores: (
            scores.get("gym_within_10min", False) and 
            scores.get("gym_quality", 0) >= 7.0
        ),
        "description": "Quality gym within 10min walk"
    },
    "is_rent_controlled": {
        "condition": lambda scores: scores.get("rent_control", False) == True,
        "description": "SF rent control protected"
    },
    "under_budget": {
        "condition": lambda scores: scores.get("price", 999999) <= 4000,
        "description": "Monthly rent ≤ $4,000"
    },
}

# Must-Have Requirements (Auto-reject if not met)
MUST_HAVES = {
    "max_price": 4500,
    "max_commute_mins": 50,
    "min_safety_score": 5,  # Combined safety must be at least 5/10
    "parking_required": "car",  # Must have at least car parking
}

# SF Rent Control
# Buildings built before June 13, 1979 are generally rent-controlled
SF_RENT_CONTROL_CUTOFF_YEAR = 1979

# Google Maps Settings
GOOGLE_MAPS_TRAVEL_MODE = "driving"
GOOGLE_MAPS_DEPARTURE_TIME = "08:00"  # 8 AM for rush hour
GOOGLE_MAPS_TRAFFIC_MODEL = "pessimistic"  # Worst-case traffic

# Places API Settings
PLACES_SEARCH_RADIUS = 805  # meters (0.5 mile)
GYM_SEARCH_RADIUS = 3219  # meters (2 miles) - Increased to find more gym options
GYM_MIN_RATING = 4.0
GYM_KEYWORDS = ["gym", "fitness", "weights", "squat rack"]
GYM_BIKE_THRESHOLD_MINS = 15.0  # If walking time > this, also calculate biking time

# SF OpenData Crime Settings
CRIME_RADIUS_MILES = 0.25
CRIME_LOOKBACK_MONTHS = 12

# Crime severity weights (higher = more serious)
# Based on SF crime categories
CRIME_SEVERITY_WEIGHTS = {
    # Violent crimes (highest weight)
    'Homicide': 10.0,
    'Rape': 10.0,
    'Robbery': 8.0,
    'Assault': 7.0,
    'Weapons Offense': 7.0,
    'Sex Offense': 8.0,
    'Human Trafficking': 10.0,
    'Kidnapping': 9.0,
    
    # Property crimes (medium-high weight)
    'Burglary': 6.0,
    'Motor Vehicle Theft': 5.0,
    'Arson': 7.0,
    'Vandalism': 3.0,
    'Stolen Property': 4.0,
    
    # Quality of life crimes (medium weight)
    'Drug Offense': 4.0,
    'Drug Violation': 4.0,
    'Prostitution': 3.0,
    'Disorderly Conduct': 2.0,
    'Suspicious': 1.0,
    'Suspicious Occ': 1.0,
    
    # Theft (medium weight)
    'Larceny Theft': 4.0,
    'Theft': 4.0,
    'Vehicle Theft': 5.0,
    
    # Lower priority
    'Lost Property': 1.0,
    'Found Property': 0.5,
    'Warrant': 2.0,
    'Traffic': 1.0,
    'Fire Report': 1.0,
    'Case for Other Agency': 0.5,
    'Non-Criminal': 0.5,
    'Missing Person': 3.0,
    'Civil': 1.0,
    'Miscellaneous': 1.0,
}

# SF average baseline (incidents per 0.25 mile radius per year)
# Based on SF crime data analysis - adjust this based on actual SF averages
SF_CRIME_BASELINE = 500  # Average incidents in 0.25 mile radius per year

# Claude Vision Settings
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
CLAUDE_MAX_TOKENS = 4096
CLAUDE_TEMPERATURE = 0.0  # Deterministic for consistent analysis

# Terrain-aware scoring configuration
TERRAIN_SCORING = {
    "elevation_thresholds": {
        "moderate_hill": 20,  # meters elevation gain
        "steep_hill": 40,     # meters elevation gain
    },
    "parking_safety_bonus": {
        "enabled": True,
        "moderate_hill": 0.5,  # +0.5 points for open parking on moderate hill
        "steep_hill": 1.2,     # +1.2 points for open parking on steep hill
        "scale_by_safety": True,  # Bonus scales with neighborhood safety
    },
    "gym_distance_penalty": {
        "enabled": True,
        "moderate_hill_multiplier": 1.3,  # 30% farther feeling
        "steep_hill_multiplier": 1.6,     # 60% farther feeling
    },
    "commute_time_adjustment": {
        "enabled": True,
        "hill_access_penalty": 2,  # +2 minutes if on steep hill (harder to reach highway)
    }
}

# Photo Download Settings (for future photo analysis feature)
PHOTO_DOWNLOAD_DIR = "photos_cache"
PHOTO_MAX_SIZE = 5  # MB
PHOTO_FORMATS = ["jpg", "jpeg", "png", "webp"]

