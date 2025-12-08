"""
Composable scoring system with dependency tracking

Each score component can depend on other components without double-counting.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import json

import config


@dataclass
class ScoreComponent:
    """Base class for all score components"""
    name: str
    raw_value: float  # 0-10 scale
    raw_value_min: Optional[float] = None  # For uncertain data (min score)
    raw_value_max: Optional[float] = None  # For uncertain data (max score)
    weight: float = 0.0
    details: dict = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """
        Calculate the score
        
        Args:
            config_data: Configuration for this component
            **kwargs: Additional data needed for calculation
            
        Returns:
            Score on 0-10 scale
        """
        raise NotImplementedError("Subclasses must implement calculate()")
    
    def has_range(self) -> bool:
        """Check if this component has a score range (uncertain data)"""
        return self.raw_value_min is not None and self.raw_value_max is not None


@dataclass
class CommuteScore(ScoreComponent):
    """Commute quality assessment"""
    duration_mins: int = 0
    route: str = ""
    on_steep_hill: bool = False
    route_annoyingness: float = 10.0
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate commute score based on duration and route"""
        preferences = config_data.get("preferences", {})
        ideal_duration = preferences.get("ideal_duration", 30)
        acceptable_duration = preferences.get("acceptable_duration", 50)
        preferred_route = preferences.get("preferred_route", "280")
        route_bonus = preferences.get("route_bonus", 1.5)
        annoyingness_weight = preferences.get("annoyingness_penalty_weight", 0.0)
        
        # Adjust duration for hill access difficulty
        effective_duration = self.duration_mins
        hill_penalty = 0
        if self.on_steep_hill and config.TERRAIN_SCORING["commute_time_adjustment"]["enabled"]:
            hill_penalty = config.TERRAIN_SCORING["commute_time_adjustment"]["hill_access_penalty"]
            effective_duration += hill_penalty
        
        # Duration score
        if effective_duration <= ideal_duration:
            duration_score = 10.0
        elif effective_duration <= acceptable_duration:
            range_size = acceptable_duration - ideal_duration
            duration_score = 10.0 - ((effective_duration - ideal_duration) / range_size * 10.0)
        else:
            duration_score = 0.0
        
        # Route preference bonus
        route_bonus_points = route_bonus if self.route == preferred_route else 0.0
        
        annoyingness_score = self.route_annoyingness if self.route_annoyingness is not None else 10.0
        annoyingness_score = max(0.0, min(10.0, annoyingness_score))
        annoying_penalty = (10.0 - annoyingness_score) * max(0.0, annoyingness_weight)
        
        self.raw_value = max(0.0, min(10.0, duration_score + route_bonus_points - annoying_penalty))
        self.details = {
            "duration_mins": self.duration_mins,
            "effective_duration": effective_duration,
            "duration_score": round(duration_score, 2),
            "route": self.route,
            "route_bonus": round(route_bonus_points, 2),
            "annoyingness_score": round(annoyingness_score, 2),
            "annoyingness_penalty": round(annoying_penalty, 2),
            "hill_access_penalty_mins": hill_penalty,
        }
        return self.raw_value


@dataclass
class QuietnessScore(ScoreComponent):
    """How quiet the apartment is"""
    has_double_pane: bool = False
    door_type: str = "none"
    street_noise: float = 5.0  # 0-10 from vision (10 = quiet)
    floor_level: str = "ground"
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate quietness score"""
        factors = config_data.get("factors", {})
        
        base = 5.0
        contributions = {}
        
        # Double pane windows reduce noise
        double_pane_bonus = 0.0
        if self.has_double_pane:
            double_pane_bonus = factors.get("double_pane_windows", 2.0)
            base += double_pane_bonus
        contributions['double_pane'] = double_pane_bonus
        
        # Door type matters for study isolation
        door_scores = factors.get("door_types", {})
        door_bonus = door_scores.get(self.door_type, 0.0)
        base += door_bonus
        contributions['door'] = door_bonus
        
        # Street noise (inverse - lower street noise = higher score)
        street_penalty = (10 - self.street_noise) * 0.3
        base -= street_penalty
        contributions['street_noise'] = -street_penalty
        
        # Higher floors are quieter
        floor_bonuses = factors.get("floor_bonuses", {})
        floor_bonus = floor_bonuses.get(self.floor_level, 0.0)
        base += floor_bonus
        contributions['floor'] = floor_bonus
        
        self.raw_value = max(0.0, min(10.0, base))
        self.details = {
            "has_double_pane": self.has_double_pane,
            "door_type": self.door_type,
            "street_noise": self.street_noise,
            "floor_level": self.floor_level,
            "contributions": contributions,  # Add breakdown of what contributed
        }
        return self.raw_value


@dataclass
class HappeningScore(ScoreComponent):
    """How happening the neighborhood is - includes POI proximity"""
    restaurants: int = 0
    cafes: int = 0
    parks: int = 0
    avg_walk_to_poi_mins: Optional[float] = None
    pois_within_1_mile: int = 0
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate happening score with POI integration"""
        scoring = config_data.get("scoring", {})
        
        # Restaurants (20%): 0 = 0 pts, 3+ = 10 pts
        rest_max = scoring.get("restaurants", {}).get("max", 3)
        rest_score = min(self.restaurants / rest_max, 1.0) * 10 if rest_max > 0 else 0
        rest_weighted = rest_score * scoring.get("restaurants", {}).get("weight", 0.20)
        
        # Cafes (20%): 0 = 0 pts, 3+ = 10 pts
        cafe_max = scoring.get("cafes", {}).get("max", 3)
        cafe_score = min(self.cafes / cafe_max, 1.0) * 10 if cafe_max > 0 else 0
        cafe_weighted = cafe_score * scoring.get("cafes", {}).get("weight", 0.20)
        
        # Avg walk to POIs (30%): 5 min = 10 pts, 25+ min = 0 pts
        if self.avg_walk_to_poi_mins is not None:
            min_mins = scoring.get("avg_walk_to_poi", {}).get("min_mins", 5)
            max_mins = scoring.get("avg_walk_to_poi", {}).get("max_mins", 25)
            clamped = max(min_mins, min(self.avg_walk_to_poi_mins, max_mins))
            poi_walk_score = 10 * (1 - (clamped - min_mins) / (max_mins - min_mins))
        else:
            poi_walk_score = 0
        poi_walk_weighted = poi_walk_score * scoring.get("avg_walk_to_poi", {}).get("weight", 0.30)
        
        # POIs within 1 mile (25%): 0 = 0 pts, 5+ = 10 pts
        poi_count_max = scoring.get("pois_within_1_mile", {}).get("max", 5)
        poi_count_score = min(self.pois_within_1_mile / poi_count_max, 1.0) * 10 if poi_count_max > 0 else 0
        poi_count_weighted = poi_count_score * scoring.get("pois_within_1_mile", {}).get("weight", 0.25)
        
        # Parks (15%): 0 = 0 pts, 3+ = 10 pts
        park_max = scoring.get("parks", {}).get("max", 3)
        park_score = min(self.parks / park_max, 1.0) * 10 if park_max > 0 else 0
        park_weighted = park_score * scoring.get("parks", {}).get("weight", 0.15)
        
        # Sum weighted components
        total = rest_weighted + cafe_weighted + poi_walk_weighted + poi_count_weighted + park_weighted
        
        # Cap at 10 to keep it on the same 0-10 scale as other components
        # (prevents locations with many amenities from dominating the overall score)
        self.raw_value = min(total, 10.0)
        
        self.details = {
            "restaurants": self.restaurants,
            "restaurants_score": round(rest_score, 2),
            "restaurants_weighted": round(rest_weighted, 2),
            "cafes": self.cafes,
            "cafes_score": round(cafe_score, 2),
            "cafes_weighted": round(cafe_weighted, 2),
            "avg_walk_to_poi_mins": self.avg_walk_to_poi_mins,
            "poi_walk_score": round(poi_walk_score, 2),
            "poi_walk_weighted": round(poi_walk_weighted, 2),
            "pois_within_1_mile": self.pois_within_1_mile,
            "poi_count_score": round(poi_count_score, 2),
            "poi_count_weighted": round(poi_count_weighted, 2),
            "parks": self.parks,
            "parks_score": round(park_score, 2),
            "parks_weighted": round(park_weighted, 2),
            "total_uncapped": round(total, 2),  # For debugging
        }
        
        return self.raw_value


@dataclass
class WFHQualityScore(ScoreComponent):
    """Work from home quality - composite score"""
    natural_light: float = 0.0
    desk_space: float = 0.0
    quietness_score: Optional[QuietnessScore] = None
    kitchen: float = 0.0
    inputs_available: bool = True
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate WFH quality score"""
        self.dependencies = ["quietness"]
        
        sub_weights = config_data.get("sub_weights", {})
        
        quietness_value = self.quietness_score.raw_value if self.quietness_score else 0.0
        
        if not self.inputs_available:
            self.raw_value = 0.0
            self.details = {
                "natural_light": self.natural_light,
                "desk_space": self.desk_space,
                "quietness": round(quietness_value, 2),
                "kitchen": self.kitchen,
                "inputs_available": False,
            }
            return self.raw_value
        
        self.raw_value = (
            self.natural_light * sub_weights.get("natural_light", 0.30) +
            self.desk_space * sub_weights.get("desk_space", 0.30) +
            quietness_value * sub_weights.get("quietness", 0.25) +
            self.kitchen * sub_weights.get("kitchen", 0.15)
        )
        
        self.details = {
            "natural_light": self.natural_light,
            "desk_space": self.desk_space,
            "quietness": round(quietness_value, 2),
            "kitchen": self.kitchen,
            "inputs_available": True,
        }
        
        return self.raw_value


@dataclass
class ParkingScore(ScoreComponent):
    """Parking quality assessment"""
    parking_type: str = "none"
    parking_enclosure: str = ""
    distance: str = "onsite"
    street_ease: Optional[str] = None
    visitor_ease: Optional[str] = None
    apartment_elevation: Optional[float] = None
    neighborhood_safety: Optional[float] = None  # 0-10 scale
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate parking score"""
        base_scores = config_data.get("base_scores", {})
        distance_penalties = config_data.get("distance_penalties", {})
        street_ease_factors = config_data.get("street_ease_factors", {})
        visitor_parking_config = config_data.get("visitor_parking_bonus", {
            "enabled": True,
            "scale": 0.15,
        })
        enclosure_bonuses = config_data.get("enclosure_bonuses", {
            "enclosed": 1.0,    # Garage/underground - best protection
            "covered": 0.5,     # Carport - some protection
            "open": 0.0,        # No protection
            "": 0.0,            # Unknown
        })
        
        # Get base score for parking type
        base_score = base_scores.get(self.parking_type, 0.0)
        
        # Apply distance penalty (for dedicated parking)
        if self.parking_type != "street_parking":
            distance_penalty = distance_penalties.get(self.distance, 0.0)
            score = base_score + distance_penalty
            
            # Add enclosure bonus for dedicated parking
            enclosure_bonus = enclosure_bonuses.get(self.parking_enclosure, 0.0)
            score += enclosure_bonus
            
            # Terrain safety bonus for open/covered parking
            if self.parking_enclosure in ['open', 'covered', '']:
                terrain_bonus = self._calculate_terrain_safety_bonus()
                score += terrain_bonus
                self.details['terrain_safety_bonus'] = round(terrain_bonus, 2)
            
            # Add visitor parking bonus (separate rating for guest parking convenience)
            if visitor_parking_config.get("enabled", True) and self.visitor_ease:
                visitor_ease_value = street_ease_factors.get(str(self.visitor_ease), 0.0)
                visitor_bonus = visitor_ease_value * visitor_parking_config.get("scale", 0.15)
                score += visitor_bonus
                self.details['visitor_parking_bonus'] = round(visitor_bonus, 2)
        else:
            # Street parking: use street_ease factor as primary score
            score = street_ease_factors.get(str(self.street_ease), 0.0) if self.street_ease else 0.0
        
        self.raw_value = max(0.0, min(10.0, score))
        self.details = {
            "parking_type": self.parking_type,
            "parking_enclosure": self.parking_enclosure,
            "distance": self.distance,
            "street_ease": self.street_ease,
            "visitor_ease": self.visitor_ease,
            "base_score": base_score,
            "enclosure_bonus": enclosure_bonuses.get(self.parking_enclosure, 0.0),
        }
        return self.raw_value
    
    def _calculate_terrain_safety_bonus(self) -> float:
        """Calculate safety bonus for parking on hills"""
        if not config.TERRAIN_SCORING["parking_safety_bonus"]["enabled"]:
            return 0.0
        
        if self.apartment_elevation is None:
            return 0.0
        
        # Determine hill steepness based on absolute elevation
        # This is a simplified heuristic - real hilliness would compare to surroundings
        bonus = 0.0
        
        if self.apartment_elevation > 50:
            bonus = config.TERRAIN_SCORING["parking_safety_bonus"]["steep_hill"]
        elif self.apartment_elevation > 30:
            bonus = config.TERRAIN_SCORING["parking_safety_bonus"]["moderate_hill"]
        
        # Scale by neighborhood safety if enabled
        if config.TERRAIN_SCORING["parking_safety_bonus"]["scale_by_safety"]:
            if self.neighborhood_safety is not None:
                # Higher base safety = smaller bonus needed (parking already safe)
                # Lower base safety = larger bonus from hill (extra security matters more)
                safety_scale = 1.0 - (self.neighborhood_safety / 20.0)  # 0.5 to 1.0 range
                bonus *= safety_scale
        
        return bonus


@dataclass
class SafetyScore(ScoreComponent):
    """Combined safety score"""
    manual_rating: float = 0.0
    opendata_rating: float = 0.0
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate combined safety score"""
        # Simple average of manual and OpenData ratings
        self.raw_value = (self.manual_rating + self.opendata_rating) / 2.0
        self.details = {
            "manual_rating": self.manual_rating,
            "opendata_rating": self.opendata_rating,
        }
        return self.raw_value


@dataclass
class LaundryScore(ScoreComponent):
    """Laundry availability score"""
    laundry_type: str = "none"
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate laundry score"""
        scoring = config_data.get("scoring", {})
        self.raw_value = scoring.get(self.laundry_type, 0.0)
        self.details = {"laundry_type": self.laundry_type}
        return self.raw_value


@dataclass
class GymScore(ScoreComponent):
    """Gym availability score - scaled by travel time (walk or bike)"""
    gym_within_10min: bool = False  # Legacy field, kept for display
    gym_walk_time_mins: Optional[float] = None  # Walking time in minutes
    gym_bike_time_mins: Optional[float] = None  # Biking time in minutes (if calculated)
    gym_transport_mode: Optional[str] = None  # 'walk' or 'bike' - user's preferred mode
    gym_effective_time_mins: Optional[float] = None  # The time used for scoring based on transport_mode
    elevation_gain_to_gym: Optional[float] = None
    office_gym_only: bool = False
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """
        Calculate gym score based on travel time (walk or bike based on user preference).
        Quality/rating is ignored since gyms are hand-picked by user.
        Score scales smoothly from 10 (0 min) to 0 (20+ min).
        """
        scoring = config_data.get("scoring", {})
        
        print(f"    [GymScore.calculate] Input values:")
        print(f"      gym_walk_time_mins: {self.gym_walk_time_mins}")
        print(f"      gym_bike_time_mins: {self.gym_bike_time_mins}")
        print(f"      gym_transport_mode: {self.gym_transport_mode}")
        print(f"      gym_effective_time_mins: {self.gym_effective_time_mins}")
        print(f"      office_gym_only: {self.office_gym_only}")
        
        # If only office gym is available, apply negative score
        if self.office_gym_only:
            score = scoring.get("office_gym_only", -5.0)
            self.details.update({
                "gym_within_10min": False,
                "gym_walk_time_mins": None,
                "gym_bike_time_mins": None,
                "gym_transport_mode": None,
                "office_gym_only": True,
                "note": "No suitable nearby gyms - office gym only"
            })
            self.raw_value = score
            print(f"      → Using office_gym_only: score = {score}")
            return self.raw_value
        
        # Use effective time (based on transport mode) for scoring
        time_for_scoring = self.gym_effective_time_mins if self.gym_effective_time_mins is not None else self.gym_walk_time_mins
        
        if time_for_scoring is not None:
            # Linear scale: 0 min = 10 points, 20 min = 0 points
            max_acceptable_mins = 20.0
            
            if time_for_scoring <= 0:
                score = 10.0
            elif time_for_scoring >= max_acceptable_mins:
                score = 0.0
            else:
                # Linear interpolation based on travel time
                score = 10.0 * (1.0 - (time_for_scoring / max_acceptable_mins))
            
            # Build scoring method description
            if self.gym_transport_mode == 'bike' and self.gym_bike_time_mins is not None:
                scoring_desc = f"Biking: {round(self.gym_bike_time_mins, 1)} min = {round(score, 1)}/10"
            else:
                scoring_desc = f"Walking: {round(time_for_scoring, 1)} min = {round(score, 1)}/10"
            
            self.details.update({
                "gym_walk_time_mins": round(self.gym_walk_time_mins, 1) if self.gym_walk_time_mins else None,
                "gym_bike_time_mins": round(self.gym_bike_time_mins, 1) if self.gym_bike_time_mins else None,
                "gym_transport_mode": self.gym_transport_mode or 'walk',
                "gym_effective_time_mins": round(time_for_scoring, 1),
                "gym_within_10min": time_for_scoring <= max_acceptable_mins,
                "scoring_method": scoring_desc
            })
            print(f"      → Scoring: {self.gym_transport_mode or 'walk'} time={time_for_scoring} min, score = {score:.1f}")
        else:
            # Fallback: if no time data, assume no suitable gym
            score = 0.0
            print(f"      → No travel time data, assuming no suitable gym: score = {score}")
            
            self.details.update({
                "gym_within_10min": False,
                "gym_walk_time_mins": None,
                "gym_bike_time_mins": None,
                "gym_transport_mode": None,
                "note": "No travel time data available - needs recalculation"
            })
        
        self.raw_value = max(0.0, min(10.0, score))
        print(f"      → Final gym score: {self.raw_value}")
        return self.raw_value
    
    def _calculate_hill_penalty(self) -> float:
        """Calculate penalty for uphill gym access"""
        gain = abs(self.elevation_gain_to_gym)
        
        if gain > config.TERRAIN_SCORING["elevation_thresholds"]["steep_hill"]:
            # Steep hill: significant penalty (1.5-2 points)
            return 1.8
        elif gain > config.TERRAIN_SCORING["elevation_thresholds"]["moderate_hill"]:
            # Moderate hill: moderate penalty (0.5-1 points)
            return 0.8
        
        return 0.0


@dataclass
class RentControlScore(ScoreComponent):
    """Rent control protection score"""
    is_rent_controlled: bool = False
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate rent control score"""
        scoring = config_data.get("scoring", {})
        self.raw_value = scoring.get("protected" if self.is_rent_controlled else "not_protected", 0.0)
        self.details = {"is_rent_controlled": self.is_rent_controlled}
        return self.raw_value


@dataclass
class SpaceLuxuryScore(ScoreComponent):
    """Space and luxury amenities score"""
    sqft: Optional[float] = None
    bedrooms: float = 1.0
    bathrooms: float = 1.0
    has_double_vanity: bool = False
    high_end_appliances: bool = False
    walk_in_closet: bool = False
    has_balcony_patio: bool = False
    has_fireplace: bool = False
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate space & luxury score based on size, bed/bath, and amenities"""
        scoring = config_data.get("scoring", {})
        
        # Square footage scoring (40% of component)
        sqft_score = 0.0
        if self.sqft and self.sqft > 0:
            sqft_thresholds = scoring.get("sqft_thresholds", {})
            min_sqft = sqft_thresholds.get("min", 400)
            max_sqft = sqft_thresholds.get("max", 1000)
            
            if self.sqft <= min_sqft:
                sqft_score = 0.0
            elif self.sqft >= max_sqft:
                sqft_score = 10.0
            else:
                # Linear interpolation between min and max
                sqft_score = 10.0 * (self.sqft - min_sqft) / (max_sqft - min_sqft)
        
        sqft_weighted = sqft_score * scoring.get("sqft_weight", 0.40)
        
        # Bedrooms/Bathrooms scoring (30% of component)
        bed_bath_score = 0.0
        
        # Bedrooms: 1bd = 5pts, 2bd = 8pts, 3+bd = 10pts
        if self.bedrooms >= 3:
            bed_score = 10.0
        elif self.bedrooms >= 2:
            bed_score = 8.0
        elif self.bedrooms >= 1:
            bed_score = 5.0
        else:
            bed_score = 2.0  # Studio
        
        # Bathrooms: 1ba = 5pts, 1.5ba = 6.5pts, 2ba = 8pts, 2.5+ba = 10pts
        if self.bathrooms >= 2.5:
            bath_score = 10.0
        elif self.bathrooms >= 2.0:
            bath_score = 8.0
        elif self.bathrooms >= 1.5:
            bath_score = 6.5
        elif self.bathrooms >= 1.0:
            bath_score = 5.0
        else:
            bath_score = 3.0
        
        # Average bed and bath scores
        bed_bath_score = (bed_score + bath_score) / 2.0
        bed_bath_weighted = bed_bath_score * scoring.get("bed_bath_weight", 0.30)
        
        # Luxury amenities scoring (30% of component)
        # Each amenity contributes equally
        amenity_bonuses = scoring.get("amenity_bonuses", {})
        luxury_points = 0.0
        amenity_count = 0
        
        if self.has_double_vanity:
            luxury_points += amenity_bonuses.get("double_vanity", 2.5)
            amenity_count += 1
        if self.high_end_appliances:
            luxury_points += amenity_bonuses.get("high_end_appliances", 2.5)
            amenity_count += 1
        if self.walk_in_closet:
            luxury_points += amenity_bonuses.get("walk_in_closet", 2.5)
            amenity_count += 1
        if self.has_balcony_patio:
            luxury_points += amenity_bonuses.get("balcony_patio", 2.5)
            amenity_count += 1
        if self.has_fireplace:
            luxury_points += amenity_bonuses.get("fireplace", 2.5)
            amenity_count += 1
        
        luxury_weighted = luxury_points * scoring.get("luxury_weight", 0.30)
        
        # Calculate total (0-10 scale)
        self.raw_value = min(10.0, sqft_weighted + bed_bath_weighted + luxury_weighted)
        
        self.details = {
            "sqft": self.sqft,
            "sqft_score": round(sqft_score, 2),
            "sqft_weighted": round(sqft_weighted, 2),
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "bed_score": round(bed_score, 2),
            "bath_score": round(bath_score, 2),
            "bed_bath_score": round(bed_bath_score, 2),
            "bed_bath_weighted": round(bed_bath_weighted, 2),
            "luxury_amenities_count": amenity_count,
            "luxury_points": round(luxury_points, 2),
            "luxury_weighted": round(luxury_weighted, 2),
            "has_double_vanity": self.has_double_vanity,
            "high_end_appliances": self.high_end_appliances,
            "walk_in_closet": self.walk_in_closet,
            "has_balcony_patio": self.has_balcony_patio,
            "has_fireplace": self.has_fireplace,
        }
        
        return self.raw_value


@dataclass
class ApartmentScoreCard:
    """Complete scoring with dependency tracking to prevent double-counting"""
    components: Dict[str, ScoreComponent] = field(default_factory=dict)
    config_components: dict = field(default_factory=dict)
    raw_data: dict = field(default_factory=dict)
    
    def calculate_total(self) -> float:
        """Calculate weighted total (0-100 scale)"""
        counted = set()
        total = 0.0
        
        for name, component in self.components.items():
            weight = self.config_components.get(name, {}).get("weight", 0.0)
            if weight > 0 and name not in counted:
                # Multiply by weight and scale to 0-100
                total += component.raw_value * weight * 10.0
                counted.add(name)
                
                # Mark dependencies as counted to avoid double-counting
                for dep in component.dependencies:
                    counted.add(dep)
        
        return min(100.0, total)
    
    def evaluate_ideal_criteria(self) -> Dict[str, bool]:
        """Evaluate binary ideal criteria"""
        criteria_results = {}
        
        for criterion_name, criterion_config in config.IDEAL_CRITERIA.items():
            condition_func = criterion_config["condition"]
            try:
                criteria_results[criterion_name] = condition_func(self.raw_data)
            except Exception as e:
                print(f"Error evaluating criterion {criterion_name}: {e}")
                criteria_results[criterion_name] = False
        
        return criteria_results
    
    def count_criteria_met(self) -> int:
        """Count how many ideal criteria are met"""
        results = self.evaluate_ideal_criteria()
        return sum(results.values())
    
    def calculate_total_range(self) -> Tuple[float, float]:
        """
        Calculate min/max weighted totals for uncertain data
        
        Returns:
            Tuple of (min_score, max_score) on 0-100 scale
        """
        counted = set()
        total_min = 0.0
        total_max = 0.0
        
        for name, component in self.components.items():
            weight = self.config_components.get(name, {}).get("weight", 0.0)
            if weight > 0 and name not in counted:
                if component.has_range():
                    # Component has uncertain data - use min/max
                    total_min += component.raw_value_min * weight * 10.0
                    total_max += component.raw_value_max * weight * 10.0
                else:
                    # Component is certain - use same value for min and max
                    total_min += component.raw_value * weight * 10.0
                    total_max += component.raw_value * weight * 10.0
                
                counted.add(name)
                
                # Mark dependencies as counted to avoid double-counting
                for dep in component.dependencies:
                    counted.add(dep)
        
        return min(100.0, total_min), min(100.0, total_max)
    
    def get_certainty_percentage(self) -> float:
        """
        Calculate how certain we are (100% = all single values, 0% = all ranges)
        
        Returns:
            Certainty percentage (0-100)
        """
        if not self.components:
            return 100.0
        
        # Count weighted components only
        weighted_components = [c for name, c in self.components.items() 
                               if self.config_components.get(name, {}).get("weight", 0.0) > 0]
        
        if not weighted_components:
            return 100.0
        
        uncertain_components = sum(1 for c in weighted_components if c.has_range())
        total_components = len(weighted_components)
        
        certain_components = total_components - uncertain_components
        return (certain_components / total_components) * 100.0
    
    def calculate_score_vs_theoretical_max(self) -> Tuple[float, float, float]:
        """
        Calculate score as percentage of theoretical maximum for available data
        
        This shows how well the apartment performs relative to the best possible
        score it could achieve given the fields that have data.
        
        Returns:
            Tuple of (actual_score, theoretical_max, percentage)
        """
        counted = set()
        actual_total = 0.0
        theoretical_max = 0.0
        
        for name, component in self.components.items():
            weight = self.config_components.get(name, {}).get("weight", 0.0)
            if weight > 0 and name not in counted:
                # Theoretical max: perfect 10/10 score for this component
                theoretical_max += 10.0 * weight * 10.0
                
                # Actual score (use average if range exists)
                actual_total += component.raw_value * weight * 10.0
                
                counted.add(name)
                for dep in component.dependencies:
                    counted.add(dep)
        
        # Calculate percentage
        if theoretical_max > 0:
            percentage = (actual_total / theoretical_max) * 100.0
        else:
            percentage = 0.0
        
        return min(100.0, actual_total), min(100.0, theoretical_max), min(100.0, percentage)
    
    def get_breakdown(self) -> Dict[str, Any]:
        """Return detailed breakdown for display"""
        breakdown = {}
        for name, component in self.components.items():
            weight = self.config_components.get(name, {}).get("weight", 0.0)
            breakdown[name] = {
                "raw_value": round(component.raw_value, 2),
                "weight": weight,
                "weighted_contribution": round(component.raw_value * weight * 10.0, 2),
                "details": component.details,
            }
        return breakdown


def parse_multi_select(value: Any) -> List[str]:
    """
    Parse multi-select field from JSON, newline-separated, comma-separated, or single value
    
    Args:
        value: Value that could be a list, JSON string, newline/comma-separated string, or single value
        
    Returns:
        List of values
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # First try parsing as JSON (for backward compatibility)
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except (json.JSONDecodeError, ValueError):
            # Try newline-separated (new format)
            if '\n' in value:
                return [item.strip() for item in value.split('\n') if item.strip()]
            # Try comma-separated (old format)
            if ',' in value:
                return [item.strip() for item in value.split(',') if item.strip()]
            # Single value
            return [value] if value else []
    return []


def calculate_score_range_for_options(score_class, config_data, field_name, options, **fixed_kwargs):
    """
    Calculate min/max scores for multiple options of a field
    
    Args:
        score_class: The score class to instantiate
        config_data: Configuration dict for this component
        field_name: Name of the field that has multiple options
        options: List of possible values for the field
        **fixed_kwargs: Fixed keyword arguments for the score class
        
    Returns:
        Tuple of (score_instance, min_score, max_score)
    """
    if len(options) == 1:
        # Single option = certain
        kwargs = {**fixed_kwargs, field_name: options[0]}
        score = score_class(**kwargs)
        score.calculate(config_data)
        return score, score.raw_value, score.raw_value
    
    # Multiple options = calculate best and worst case
    scores = []
    for option in options:
        kwargs = {**fixed_kwargs, field_name: option}
        temp_score = score_class(**kwargs)
        temp_score.calculate(config_data)
        scores.append(temp_score.raw_value)
    
    # Use the first option as the base
    kwargs = {**fixed_kwargs, field_name: options[0]}
    score = score_class(**kwargs)
    score.calculate(config_data)
    
    score.raw_value_min = min(scores)
    score.raw_value_max = max(scores)
    score.raw_value = (score.raw_value_min + score.raw_value_max) / 2.0
    score.details['options'] = options
    score.details['score_range'] = f"{score.raw_value_min:.1f}-{score.raw_value_max:.1f}"
    
    return score, score.raw_value_min, score.raw_value_max


def _value_or_default(value, default=0.0):
    """
    Return default when value is None or empty; otherwise convert to float.
    
    Handles string values from Google Sheets by converting them to float.
    """
    if value is None or value == "" or value == []:
        return default
    
    # If it's already a number, return it
    if isinstance(value, (int, float)):
        return float(value)
    
    # Try to convert string to float
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def build_scorecard(apartment_data: Dict[str, Any]) -> ApartmentScoreCard:
    """
    Build a complete scorecard from apartment data
    
    Args:
        apartment_data: Dictionary with all apartment information
        
    Returns:
        ApartmentScoreCard with all components calculated
    """
    # Build component scores
    components = {}
    
    wfh_input_fields = [
        apartment_data.get("natural_light"),
        apartment_data.get("desk_space_quality"),
        apartment_data.get("kitchen_quality"),
        apartment_data.get("view_quality"),
        apartment_data.get("double_pane_windows"),
        apartment_data.get("study_door_type"),
        apartment_data.get("street_noise_level"),
        apartment_data.get("floor_level"),
    ]
    has_wfh_inputs = any(val not in (None, "", []) for val in wfh_input_fields)
    
    # Quietness (used by WFH quality)
    has_double_pane = apartment_data.get("double_pane_windows")
    door_types = parse_multi_select(apartment_data.get("study_door_type", "none"))
    
    # Handle multiple door types
    if len(door_types) > 1:
        quietness, min_score, max_score = calculate_score_range_for_options(
            QuietnessScore,
            config.SCORE_COMPONENTS["quietness"],
            "door_type",
            door_types,
            name="quietness",
            raw_value=0.0,
            weight=0.0,
            has_double_pane=bool(has_double_pane) if has_double_pane is not None else False,
            street_noise=_value_or_default(apartment_data.get("street_noise_level"), 5.0),
            floor_level=(apartment_data.get("floor_level") or "ground"),
        )
    else:
        quietness = QuietnessScore(
            name="quietness",
            raw_value=0.0,
            weight=0.0,
            has_double_pane=bool(has_double_pane) if has_double_pane is not None else False,
            door_type=door_types[0] if door_types else "none",
            street_noise=_value_or_default(apartment_data.get("street_noise_level"), 5.0),
            floor_level=(apartment_data.get("floor_level") or "ground"),
        )
        quietness.calculate(config.SCORE_COMPONENTS["quietness"])
    
    quietness.details['inputs_available'] = has_wfh_inputs
    if not has_wfh_inputs:
        quietness.raw_value = 0.0
    components["quietness"] = quietness
    
    # Commute
    commute = CommuteScore(
        name="commute",
        raw_value=0.0,
        weight=config.SCORE_COMPONENTS["commute"]["weight"],
        duration_mins=apartment_data.get("commute_duration", 999),
        route=apartment_data.get("commute_route", ""),
        on_steep_hill=apartment_data.get("on_steep_hill_from_work", False),
        route_annoyingness=apartment_data.get("route_annoyingness", 10.0),
    )
    commute.calculate(config.SCORE_COMPONENTS["commute"])
    components["commute"] = commute
    
    # WFH Quality
    wfh_quality = WFHQualityScore(
        name="wfh_quality",
        raw_value=0.0,
        weight=config.SCORE_COMPONENTS["wfh_quality"]["weight"],
        natural_light=_value_or_default(apartment_data.get("natural_light"), 0.0),
        desk_space=_value_or_default(apartment_data.get("desk_space_quality"), 0.0),
        quietness_score=quietness,
        kitchen=_value_or_default(apartment_data.get("kitchen_quality"), 0.0),
        inputs_available=has_wfh_inputs,
    )
    wfh_quality.calculate(config.SCORE_COMPONENTS["wfh_quality"])
    components["wfh_quality"] = wfh_quality
    
    # Happening (formerly Location Vibe, now standalone top-level category)
    happening = HappeningScore(
        name="happening",
        raw_value=0.0,
        weight=config.SCORE_COMPONENTS["happening"]["weight"],
        restaurants=apartment_data.get("restaurants_nearby", 0),
        cafes=apartment_data.get("cafes_nearby", 0),
        parks=apartment_data.get("parks_nearby", 0),
        avg_walk_to_poi_mins=apartment_data.get("avg_walk_to_poi_mins"),
        pois_within_1_mile=apartment_data.get("pois_within_1_mile", 0),
    )
    happening.calculate(config.SCORE_COMPONENTS["happening"])
    components["happening"] = happening
    
    # Safety
    safety = SafetyScore(
        name="safety",
        raw_value=0.0,
        weight=config.SCORE_COMPONENTS["safety"]["weight"],
        manual_rating=apartment_data.get("manual_safety_rating", 0.0),
        opendata_rating=apartment_data.get("safety_score_opendata", 0.0),
    )
    safety.calculate(config.SCORE_COMPONENTS["safety"])
    components["safety"] = safety
    
    # Parking (handle multi-select)
    parking_types = parse_multi_select(apartment_data.get("parking_type", "none"))
    parking_enclosures = parse_multi_select(apartment_data.get("parking_enclosure", ""))
    
    # If both parking type and enclosure have multiple options, we'll only vary parking type
    # (varying both would create too many combinations)
    if len(parking_types) > 1:
        parking, min_score, max_score = calculate_score_range_for_options(
            ParkingScore,
            config.SCORE_COMPONENTS["parking"],
            "parking_type",
            parking_types,
            name="parking",
            raw_value=0.0,
            weight=config.SCORE_COMPONENTS["parking"]["weight"],
            parking_enclosure=parking_enclosures[0] if parking_enclosures else "",
            distance=apartment_data.get("parking_distance", "onsite"),
            street_ease=apartment_data.get("street_parking_ease"),
            visitor_ease=apartment_data.get("visitor_parking_ease"),
            apartment_elevation=apartment_data.get("apartment_elevation"),
            neighborhood_safety=apartment_data.get("combined_safety"),
        )
    elif len(parking_enclosures) > 1:
        parking, min_score, max_score = calculate_score_range_for_options(
            ParkingScore,
            config.SCORE_COMPONENTS["parking"],
            "parking_enclosure",
            parking_enclosures,
            name="parking",
            raw_value=0.0,
            weight=config.SCORE_COMPONENTS["parking"]["weight"],
            parking_type=parking_types[0] if parking_types else "none",
            distance=apartment_data.get("parking_distance", "onsite"),
            street_ease=apartment_data.get("street_parking_ease"),
            visitor_ease=apartment_data.get("visitor_parking_ease"),
            apartment_elevation=apartment_data.get("apartment_elevation"),
            neighborhood_safety=apartment_data.get("combined_safety"),
        )
    else:
        parking = ParkingScore(
            name="parking",
            raw_value=0.0,
            weight=config.SCORE_COMPONENTS["parking"]["weight"],
            parking_type=parking_types[0] if parking_types else "none",
            parking_enclosure=parking_enclosures[0] if parking_enclosures else "",
            distance=apartment_data.get("parking_distance", "onsite"),
            street_ease=apartment_data.get("street_parking_ease"),
            visitor_ease=apartment_data.get("visitor_parking_ease"),
            apartment_elevation=apartment_data.get("apartment_elevation"),
            neighborhood_safety=apartment_data.get("combined_safety"),
        )
        parking.calculate(config.SCORE_COMPONENTS["parking"])
    
    components["parking"] = parking
    
    # Laundry (handle multi-select)
    laundry_types = parse_multi_select(apartment_data.get("laundry_type", "none"))
    
    if len(laundry_types) > 1:
        laundry, min_score, max_score = calculate_score_range_for_options(
            LaundryScore,
            config.SCORE_COMPONENTS["laundry"],
            "laundry_type",
            laundry_types,
            name="laundry",
            raw_value=0.0,
            weight=config.SCORE_COMPONENTS["laundry"]["weight"],
        )
    else:
        laundry = LaundryScore(
            name="laundry",
            raw_value=0.0,
            weight=config.SCORE_COMPONENTS["laundry"]["weight"],
            laundry_type=laundry_types[0] if laundry_types else "none",
        )
        laundry.calculate(config.SCORE_COMPONENTS["laundry"])
    
    components["laundry"] = laundry
    
    # Gym
    gym = GymScore(
        name="gym_nearby",
        raw_value=0.0,
        weight=config.SCORE_COMPONENTS["gym_nearby"]["weight"],
        gym_within_10min=apartment_data.get("gym_within_10min", False),
        gym_walk_time_mins=apartment_data.get("gym_walk_time_mins"),
        gym_bike_time_mins=apartment_data.get("gym_bike_time_mins"),
        gym_transport_mode=apartment_data.get("gym_transport_mode"),
        gym_effective_time_mins=apartment_data.get("gym_effective_time_mins"),
        elevation_gain_to_gym=apartment_data.get("elevation_to_gym"),
        office_gym_only=apartment_data.get("office_gym_only", False),
    )
    gym.calculate(config.SCORE_COMPONENTS["gym_nearby"])
    components["gym_nearby"] = gym
    
    # Rent Control
    rent_control = RentControlScore(
        name="rent_control",
        raw_value=0.0,
        weight=config.SCORE_COMPONENTS["rent_control"]["weight"],
        is_rent_controlled=apartment_data.get("rent_control", False),
    )
    rent_control.calculate(config.SCORE_COMPONENTS["rent_control"])
    components["rent_control"] = rent_control
    
    # Space & Luxury
    sqft = apartment_data.get("sqft")
    sqft_min = apartment_data.get("sqft_min")
    sqft_max = apartment_data.get("sqft_max")
    
    # Convert to float, handling strings from Google Sheets
    def safe_float(val):
        if val is None or val == "":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    
    sqft = safe_float(sqft)
    sqft_min = safe_float(sqft_min)
    sqft_max = safe_float(sqft_max)
    
    # Use sqft if available, otherwise use average of min/max if both provided
    if sqft:
        effective_sqft = sqft
    elif sqft_min and sqft_max:
        effective_sqft = (sqft_min + sqft_max) / 2.0
    elif sqft_min:
        effective_sqft = sqft_min
    elif sqft_max:
        effective_sqft = sqft_max
    else:
        effective_sqft = None
    
    # Convert bedrooms/bathrooms to float, handling strings
    bedrooms = safe_float(apartment_data.get("bedrooms")) or 1.0
    bathrooms = safe_float(apartment_data.get("bathrooms")) or 1.0
    
    space_luxury = SpaceLuxuryScore(
        name="space_luxury",
        raw_value=0.0,
        weight=config.SCORE_COMPONENTS["space_luxury"]["weight"],
        sqft=effective_sqft,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        has_double_vanity=apartment_data.get("has_double_vanity", False),
        high_end_appliances=apartment_data.get("high_end_appliances", False),
        walk_in_closet=apartment_data.get("walk_in_closet", False),
        has_balcony_patio=apartment_data.get("has_balcony_patio", False),
        has_fireplace=apartment_data.get("has_fireplace", False),
    )
    space_luxury.calculate(config.SCORE_COMPONENTS["space_luxury"])
    
    # If we have a sqft range, calculate min/max scores
    if sqft_min and sqft_max and sqft_min != sqft_max:
        # Create component with min sqft
        space_luxury_min = SpaceLuxuryScore(
            name="space_luxury",
            raw_value=0.0,
            weight=config.SCORE_COMPONENTS["space_luxury"]["weight"],
            sqft=sqft_min,
            bedrooms=apartment_data.get("bedrooms", 1.0),
            bathrooms=apartment_data.get("bathrooms", 1.0),
            has_double_vanity=apartment_data.get("has_double_vanity", False),
            high_end_appliances=apartment_data.get("high_end_appliances", False),
            walk_in_closet=apartment_data.get("walk_in_closet", False),
            has_balcony_patio=apartment_data.get("has_balcony_patio", False),
            has_fireplace=apartment_data.get("has_fireplace", False),
        )
        space_luxury_min.calculate(config.SCORE_COMPONENTS["space_luxury"])
        
        # Create component with max sqft
        space_luxury_max = SpaceLuxuryScore(
            name="space_luxury",
            raw_value=0.0,
            weight=config.SCORE_COMPONENTS["space_luxury"]["weight"],
            sqft=sqft_max,
            bedrooms=apartment_data.get("bedrooms", 1.0),
            bathrooms=apartment_data.get("bathrooms", 1.0),
            has_double_vanity=apartment_data.get("has_double_vanity", False),
            high_end_appliances=apartment_data.get("high_end_appliances", False),
            walk_in_closet=apartment_data.get("walk_in_closet", False),
            has_balcony_patio=apartment_data.get("has_balcony_patio", False),
            has_fireplace=apartment_data.get("has_fireplace", False),
        )
        space_luxury_max.calculate(config.SCORE_COMPONENTS["space_luxury"])
        
        # Set min/max on the component
        space_luxury.raw_value_min = space_luxury_min.raw_value
        space_luxury.raw_value_max = space_luxury_max.raw_value
    
    components["space_luxury"] = space_luxury
    
    # Build scorecard
    scorecard = ApartmentScoreCard(
        components=components,
        config_components=config.SCORE_COMPONENTS,
        raw_data=apartment_data,
    )
    
    return scorecard

