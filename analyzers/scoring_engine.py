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
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate commute score based on duration and route"""
        preferences = config_data.get("preferences", {})
        ideal_duration = preferences.get("ideal_duration", 30)
        acceptable_duration = preferences.get("acceptable_duration", 50)
        preferred_route = preferences.get("preferred_route", "280")
        route_bonus = preferences.get("route_bonus", 1.5)
        
        # Adjust duration for hill access difficulty
        effective_duration = self.duration_mins
        if self.on_steep_hill and config.TERRAIN_SCORING["commute_time_adjustment"]["enabled"]:
            hill_penalty = config.TERRAIN_SCORING["commute_time_adjustment"]["hill_access_penalty"]
            effective_duration += hill_penalty
            self.details['hill_access_penalty_mins'] = hill_penalty
        
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
        
        self.raw_value = min(10.0, duration_score + route_bonus_points)
        self.details = {
            "duration_mins": self.duration_mins,
            "effective_duration": effective_duration,
            "duration_score": round(duration_score, 2),
            "route": self.route,
            "route_bonus": round(route_bonus_points, 2),
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
        
        # Double pane windows reduce noise
        if self.has_double_pane:
            base += factors.get("double_pane_windows", 2.0)
        
        # Door type matters for study isolation
        door_scores = factors.get("door_types", {})
        base += door_scores.get(self.door_type, 0.0)
        
        # Street noise (inverse - lower street noise = higher score)
        base -= (10 - self.street_noise) * 0.3
        
        # Higher floors are quieter
        floor_bonuses = factors.get("floor_bonuses", {})
        base += floor_bonuses.get(self.floor_level, 0.0)
        
        self.raw_value = max(0.0, min(10.0, base))
        self.details = {
            "has_double_pane": self.has_double_pane,
            "door_type": self.door_type,
            "street_noise": self.street_noise,
            "floor_level": self.floor_level,
        }
        return self.raw_value


@dataclass
class LocationVibeScore(ScoreComponent):
    """How happening the neighborhood is"""
    restaurants: int = 0
    cafes: int = 0
    parks: int = 0
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate location vibe score"""
        sub_weights = config_data.get("sub_weights", {})
        normalization = config_data.get("normalization", {})
        
        # Normalize counts to 0-10 scale
        rest_score = min(10.0, self.restaurants / normalization.get("restaurants_divisor", 2.0))
        cafe_score = min(10.0, self.cafes / normalization.get("cafes_divisor", 1.5))
        park_score = min(10.0, self.parks * normalization.get("parks_multiplier", 3.0))
        
        self.raw_value = (
            rest_score * sub_weights.get("restaurants", 0.4) +
            cafe_score * sub_weights.get("cafes", 0.4) +
            park_score * sub_weights.get("parks", 0.2)
        )
        
        self.details = {
            "restaurants": self.restaurants,
            "cafes": self.cafes,
            "parks": self.parks,
            "rest_score": round(rest_score, 2),
            "cafe_score": round(cafe_score, 2),
            "park_score": round(park_score, 2),
        }
        return self.raw_value


@dataclass
class WFHQualityScore(ScoreComponent):
    """Work from home quality - composite score"""
    natural_light: float = 0.0
    desk_space: float = 0.0
    quietness_score: Optional[QuietnessScore] = None
    kitchen: float = 0.0
    location_vibe_score: Optional[LocationVibeScore] = None
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate WFH quality score"""
        self.dependencies = ["quietness", "location_vibe"]
        
        sub_weights = config_data.get("sub_weights", {})
        
        quietness_value = self.quietness_score.raw_value if self.quietness_score else 0.0
        location_vibe_value = self.location_vibe_score.raw_value if self.location_vibe_score else 0.0
        
        self.raw_value = (
            self.natural_light * sub_weights.get("natural_light", 0.25) +
            self.desk_space * sub_weights.get("desk_space", 0.25) +
            quietness_value * sub_weights.get("quietness", 0.20) +
            self.kitchen * sub_weights.get("kitchen", 0.15) +
            location_vibe_value * sub_weights.get("location_vibe", 0.15)
        )
        
        self.details = {
            "natural_light": self.natural_light,
            "desk_space": self.desk_space,
            "quietness": round(quietness_value, 2),
            "kitchen": self.kitchen,
            "location_vibe": round(location_vibe_value, 2),
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
    """Gym availability score"""
    gym_within_10min: bool = False
    gym_quality: float = 0.0
    elevation_gain_to_gym: Optional[float] = None
    
    def calculate(self, config_data: dict, **kwargs) -> float:
        """Calculate gym score"""
        scoring = config_data.get("scoring", {})
        
        if self.gym_within_10min and self.gym_quality >= 7.0:
            score = scoring.get("has_nearby_good_gym", 10.0)
        elif self.gym_within_10min:
            score = scoring.get("has_nearby_ok_gym", 6.0)
        else:
            score = scoring.get("no_nearby_gym", 0.0)
        
        # Adjust score for elevation gain (makes gym feel farther)
        if self.elevation_gain_to_gym is not None and config.TERRAIN_SCORING["gym_distance_penalty"]["enabled"]:
            penalty = self._calculate_hill_penalty()
            score -= penalty
            self.details['hill_penalty'] = round(penalty, 2)
        
        self.raw_value = max(0.0, min(10.0, score))
        self.details.update({
            "gym_within_10min": self.gym_within_10min,
            "gym_quality": self.gym_quality,
            "elevation_gain_to_gym": self.elevation_gain_to_gym,
        })
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
    
    # Quietness (used by WFH quality)
    quietness = QuietnessScore(
        name="quietness",
        raw_value=0.0,
        weight=0.0,
        has_double_pane=apartment_data.get("double_pane_windows", False),
        door_type=apartment_data.get("study_door_type", "none"),
        street_noise=apartment_data.get("street_noise_level", 5.0),
        floor_level=apartment_data.get("floor_level", "ground"),
    )
    quietness.calculate(config.SCORE_COMPONENTS["quietness"])
    components["quietness"] = quietness
    
    # Location vibe (used by WFH quality)
    location_vibe = LocationVibeScore(
        name="location_vibe",
        raw_value=0.0,
        weight=0.0,
        restaurants=apartment_data.get("restaurants_nearby", 0),
        cafes=apartment_data.get("cafes_nearby", 0),
        parks=apartment_data.get("parks_nearby", 0),
    )
    location_vibe.calculate(config.SCORE_COMPONENTS["location_vibe"])
    components["location_vibe"] = location_vibe
    
    # Commute
    commute = CommuteScore(
        name="commute",
        raw_value=0.0,
        weight=config.SCORE_COMPONENTS["commute"]["weight"],
        duration_mins=apartment_data.get("commute_duration", 999),
        route=apartment_data.get("commute_route", ""),
        on_steep_hill=apartment_data.get("on_steep_hill_from_work", False),
    )
    commute.calculate(config.SCORE_COMPONENTS["commute"])
    components["commute"] = commute
    
    # WFH Quality
    wfh_quality = WFHQualityScore(
        name="wfh_quality",
        raw_value=0.0,
        weight=config.SCORE_COMPONENTS["wfh_quality"]["weight"],
        natural_light=apartment_data.get("natural_light", 0.0),
        desk_space=apartment_data.get("desk_space_quality", 0.0),
        quietness_score=quietness,
        kitchen=apartment_data.get("kitchen_quality", 0.0),
        location_vibe_score=location_vibe,
    )
    wfh_quality.calculate(config.SCORE_COMPONENTS["wfh_quality"])
    components["wfh_quality"] = wfh_quality
    
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
        gym_quality=apartment_data.get("gym_quality", 0.0),
        elevation_gain_to_gym=apartment_data.get("elevation_to_gym"),
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
    
    # Build scorecard
    scorecard = ApartmentScoreCard(
        components=components,
        config_components=config.SCORE_COMPONENTS,
        raw_data=apartment_data,
    )
    
    return scorecard

