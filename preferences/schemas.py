"""
Data schemas for preference-based apartment evaluation.

Defines the structure for individual preference profiles, threshold tiers,
apartment evaluations, and joint rankings.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import json
import yaml
from pathlib import Path
from datetime import datetime


class TierLevel(Enum):
    """Threshold tier classification."""
    IDEAL = "ideal"
    ACCEPTABLE = "acceptable"
    VETO = "veto"


class ComparisonOperator(Enum):
    """Operators for threshold comparisons."""
    LTE = "lte"  # less than or equal
    GTE = "gte"  # greater than or equal
    LT = "lt"    # less than
    GT = "gt"    # greater than
    EQ = "eq"    # equal
    NEQ = "neq"  # not equal
    IN = "in"    # value in list
    NOT_IN = "not_in"  # value not in list


class CommuteMode(Enum):
    """Travel mode for commute calculations."""
    DRIVING = "driving"
    TRANSIT = "transit"
    WALKING = "walking"
    BICYCLING = "bicycling"


@dataclass
class AnnoyingnessWeights:
    """
    Configurable weights for calculating commute annoyingness.
    
    For transit users:
        - walk_time_weight: Penalty per minute of walking
        - transfer_weight: Penalty per transit transfer
        - duration_weight: Penalty per minute over ideal duration
        
    For drivers:
        - left_turn_weight: Penalty per left turn before highway
        - congestion_weight: Multiplier for congestion ratio
        - low_speed_weight: Penalty per low-speed segment
        - lane_split_weight: Penalty for non-highway portions
    """
    # Transit-specific weights
    walk_time_weight: float = 0.15  # Penalty per minute of walking
    transfer_weight: float = 0.8    # Penalty per transit transfer
    duration_weight: float = 0.1    # Penalty per minute over ideal
    
    # Driving-specific weights
    left_turn_weight: float = 0.6   # Penalty per left turn before highway
    congestion_weight: float = 10.0 # Multiplier for congestion ratio  
    low_speed_weight: float = 0.7   # Penalty per low-speed segment
    lane_split_weight: float = 2.5  # Multiplier for non-highway ratio
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "walk_time_weight": self.walk_time_weight,
            "transfer_weight": self.transfer_weight,
            "duration_weight": self.duration_weight,
            "left_turn_weight": self.left_turn_weight,
            "congestion_weight": self.congestion_weight,
            "low_speed_weight": self.low_speed_weight,
            "lane_split_weight": self.lane_split_weight,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AnnoyingnessWeights":
        """Deserialize from dictionary."""
        return cls(
            walk_time_weight=data.get("walk_time_weight", 0.15),
            transfer_weight=data.get("transfer_weight", 0.8),
            duration_weight=data.get("duration_weight", 0.1),
            left_turn_weight=data.get("left_turn_weight", 0.6),
            congestion_weight=data.get("congestion_weight", 10.0),
            low_speed_weight=data.get("low_speed_weight", 0.7),
            lane_split_weight=data.get("lane_split_weight", 2.5),
        )


@dataclass
class CommuteConfig:
    """
    Per-profile commute configuration.
    
    Allows each profile to specify:
    - Which data field to read commute duration from
    - The commute mode (for annoyingness calculation)
    - Whether to include commute_score in evaluation
    - Custom annoyingness weights
    """
    data_field: str = "commute_time_you"  # Column to read commute duration from
    mode: CommuteMode = CommuteMode.DRIVING
    include_commute_score: bool = True
    annoyingness_weights: AnnoyingnessWeights = field(default_factory=AnnoyingnessWeights)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "data_field": self.data_field,
            "mode": self.mode.value,
            "include_commute_score": self.include_commute_score,
            "annoyingness_weights": self.annoyingness_weights.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CommuteConfig":
        """Deserialize from dictionary."""
        mode_str = data.get("mode", "driving")
        try:
            mode = CommuteMode(mode_str)
        except ValueError:
            mode = CommuteMode.DRIVING
            
        weights_data = data.get("annoyingness_weights", {})
        weights = AnnoyingnessWeights.from_dict(weights_data) if weights_data else AnnoyingnessWeights()
        
        return cls(
            data_field=data.get("data_field", "commute_time_you"),
            mode=mode,
            include_commute_score=data.get("include_commute_score", True),
            annoyingness_weights=weights,
        )


@dataclass
class Threshold:
    """
    A single threshold condition for a criterion.
    
    Examples:
        - max_commute_minutes: 35, operator: LTE -> commute <= 35
        - min_safety_score: 7.0, operator: GTE -> safety >= 7.0
        - laundry_type: ["in_unit", "in_unit_combo"], operator: IN
    """
    field: str
    value: Union[float, int, str, List[str]]
    operator: ComparisonOperator = ComparisonOperator.LTE
    
    def evaluate(self, actual_value: Any) -> bool:
        """
        Check if actual_value satisfies this threshold.
        
        Returns:
            True if threshold is satisfied, False if violated.
        """
        if actual_value is None:
            return False  # Missing data fails threshold
        
        try:
            if self.operator == ComparisonOperator.LTE:
                return float(actual_value) <= float(self.value)
            elif self.operator == ComparisonOperator.GTE:
                return float(actual_value) >= float(self.value)
            elif self.operator == ComparisonOperator.LT:
                return float(actual_value) < float(self.value)
            elif self.operator == ComparisonOperator.GT:
                return float(actual_value) > float(self.value)
            elif self.operator == ComparisonOperator.EQ:
                return actual_value == self.value
            elif self.operator == ComparisonOperator.NEQ:
                return actual_value != self.value
            elif self.operator == ComparisonOperator.IN:
                if isinstance(self.value, list):
                    return actual_value in self.value
                return False
            elif self.operator == ComparisonOperator.NOT_IN:
                if isinstance(self.value, list):
                    return actual_value not in self.value
                return True
        except (ValueError, TypeError):
            return False
        
        return False
    
    def distance_from_threshold(self, actual_value: Any) -> Optional[float]:
        """
        Calculate how far actual_value is from satisfying the threshold.
        
        Returns:
            Positive value if violated (distance from threshold),
            Negative value if satisfied (margin beyond threshold),
            None if not applicable (categorical comparisons).
        """
        if actual_value is None:
            return None
        
        try:
            actual = float(actual_value)
            target = float(self.value)
            
            if self.operator in (ComparisonOperator.LTE, ComparisonOperator.LT):
                return actual - target  # Positive means over threshold
            elif self.operator in (ComparisonOperator.GTE, ComparisonOperator.GT):
                return target - actual  # Positive means under threshold
        except (ValueError, TypeError):
            return None
        
        return None
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "field": self.field,
            "value": self.value,
            "operator": self.operator.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Threshold":
        """Deserialize from dictionary."""
        return cls(
            field=data["field"],
            value=data["value"],
            operator=ComparisonOperator(data.get("operator", "lte")),
        )


@dataclass
class CriterionPreference:
    """
    Preference definition for a single criterion with tiered thresholds.
    
    Each criterion has:
    - id: unique identifier (e.g., "commute", "safety")
    - display_name: human-readable name
    - priority_order: 1 = highest priority
    - ideal: thresholds for "ideal" tier
    - acceptable: thresholds for "acceptable" tier  
    - veto: conditions that auto-reject apartment
    - veto_reason: explanation shown when veto triggered
    """
    id: str
    display_name: str
    priority_order: int
    ideal: List[Threshold] = field(default_factory=list)
    acceptable: List[Threshold] = field(default_factory=list)
    veto: List[Threshold] = field(default_factory=list)
    veto_reason: str = ""
    
    def evaluate_tier(self, apartment_data: Dict[str, Any]) -> TierLevel:
        """
        Determine which tier this apartment falls into for this criterion.
        
        Returns:
            TierLevel indicating ideal, acceptable, or veto status.
        """
        # Check veto conditions first (if ANY veto threshold is violated)
        for threshold in self.veto:
            if not threshold.evaluate(apartment_data.get(threshold.field)):
                return TierLevel.VETO
        
        # Check if all ideal thresholds are met
        ideal_met = all(
            threshold.evaluate(apartment_data.get(threshold.field))
            for threshold in self.ideal
        )
        if ideal_met and self.ideal:  # Only return IDEAL if there are ideal thresholds
            return TierLevel.IDEAL
        
        # Check if all acceptable thresholds are met
        acceptable_met = all(
            threshold.evaluate(apartment_data.get(threshold.field))
            for threshold in self.acceptable
        )
        if acceptable_met and self.acceptable:
            return TierLevel.ACCEPTABLE
        
        # Falls below acceptable but passed veto → still acceptable (just below threshold)
        # Only return VETO if we failed a veto check above
        return TierLevel.ACCEPTABLE
    
    def get_violated_thresholds(
        self, apartment_data: Dict[str, Any], tier: TierLevel
    ) -> List[Dict[str, Any]]:
        """
        Get list of violated thresholds for a specific tier.
        
        Returns:
            List of dicts with threshold info and violation details.
        """
        thresholds = {
            TierLevel.IDEAL: self.ideal,
            TierLevel.ACCEPTABLE: self.acceptable,
            TierLevel.VETO: self.veto,
        }.get(tier, [])
        
        violations = []
        for threshold in thresholds:
            actual = apartment_data.get(threshold.field)
            if not threshold.evaluate(actual):
                violations.append({
                    "field": threshold.field,
                    "expected": threshold.value,
                    "operator": threshold.operator.value,
                    "actual": actual,
                    "distance": threshold.distance_from_threshold(actual),
                })
        
        return violations
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "priority_order": self.priority_order,
            "ideal": [t.to_dict() for t in self.ideal],
            "acceptable": [t.to_dict() for t in self.acceptable],
            "veto": [t.to_dict() for t in self.veto],
            "veto_reason": self.veto_reason,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CriterionPreference":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            display_name=data["display_name"],
            priority_order=data["priority_order"],
            ideal=[Threshold.from_dict(t) for t in data.get("ideal", [])],
            acceptable=[Threshold.from_dict(t) for t in data.get("acceptable", [])],
            veto=[Threshold.from_dict(t) for t in data.get("veto", [])],
            veto_reason=data.get("veto_reason", ""),
        )


@dataclass
class PreferenceProfile:
    """
    Complete preference profile for one person.
    
    Contains all criteria preferences, AHP-derived weights for tie-breaking,
    commute configuration, and metadata about how the profile was generated.
    """
    person_name: str
    version: int = 1
    criteria: List[CriterionPreference] = field(default_factory=list)
    ahp_weights: Dict[str, float] = field(default_factory=dict)
    ahp_consistency_ratio: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""
    quiz_responses: Dict[str, Any] = field(default_factory=dict)
    commute_config: CommuteConfig = field(default_factory=CommuteConfig)
    
    def get_criterion(self, criterion_id: str) -> Optional[CriterionPreference]:
        """Get a criterion by ID."""
        for criterion in self.criteria:
            if criterion.id == criterion_id:
                return criterion
        return None
    
    def get_criteria_by_priority(self) -> List[CriterionPreference]:
        """Get criteria sorted by priority order (1 = highest)."""
        return sorted(self.criteria, key=lambda c: c.priority_order)
    
    def save(self, path: Union[str, Path]) -> None:
        """Save profile to YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self.to_dict()
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def load(cls, path: Union[str, Path]) -> "PreferenceProfile":
        """Load profile from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "person_name": self.person_name,
            "version": self.version,
            "criteria": [c.to_dict() for c in self.criteria],
            "ahp_weights": self.ahp_weights,
            "ahp_consistency_ratio": self.ahp_consistency_ratio,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "notes": self.notes,
            "quiz_responses": self.quiz_responses,
            "commute_config": self.commute_config.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PreferenceProfile":
        """Deserialize from dictionary."""
        commute_config_data = data.get("commute_config", {})
        commute_config = CommuteConfig.from_dict(commute_config_data) if commute_config_data else CommuteConfig()
        
        return cls(
            person_name=data["person_name"],
            version=data.get("version", 1),
            criteria=[CriterionPreference.from_dict(c) for c in data.get("criteria", [])],
            ahp_weights=data.get("ahp_weights", {}),
            ahp_consistency_ratio=data.get("ahp_consistency_ratio", 0.0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            notes=data.get("notes", ""),
            quiz_responses=data.get("quiz_responses", {}),
            commute_config=commute_config,
        )


@dataclass
class ViolationRecord:
    """
    Record of a single threshold violation.
    """
    criterion_id: str
    criterion_name: str
    priority_order: int
    tier: TierLevel
    field: str
    expected_value: Any
    actual_value: Any
    operator: str
    distance: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "criterion_id": self.criterion_id,
            "criterion_name": self.criterion_name,
            "priority_order": self.priority_order,
            "tier": self.tier.value,
            "field": self.field,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "operator": self.operator,
            "distance": self.distance,
        }


@dataclass
class ApartmentEvaluation:
    """
    Evaluation result for one apartment against one person's preferences.
    """
    apartment_id: str
    person_name: str
    
    # Violation tracking
    first_violation: Optional[ViolationRecord] = None
    all_violations: List[ViolationRecord] = field(default_factory=list)
    
    # Summary stats
    ideal_count: int = 0
    acceptable_count: int = 0
    veto_count: int = 0
    total_criteria: int = 0
    
    # Tier results per criterion
    tier_results: Dict[str, TierLevel] = field(default_factory=dict)
    
    # Tie-breaking score (AHP-weighted satisfaction)
    tie_break_score: float = 0.0
    
    # Explanations
    explanations: Dict[str, str] = field(default_factory=dict)
    
    @property
    def has_veto(self) -> bool:
        """Check if any veto-level violation exists."""
        return self.veto_count > 0
    
    @property
    def satisfaction_ratio(self) -> float:
        """Ratio of criteria at ideal or acceptable level."""
        if self.total_criteria == 0:
            return 0.0
        return (self.ideal_count + self.acceptable_count) / self.total_criteria
    
    @property
    def first_breach_priority(self) -> Optional[int]:
        """Priority order of first violation (lower = worse)."""
        if self.first_violation:
            return self.first_violation.priority_order
        return None
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "apartment_id": self.apartment_id,
            "person_name": self.person_name,
            "first_violation": self.first_violation.to_dict() if self.first_violation else None,
            "all_violations": [v.to_dict() for v in self.all_violations],
            "ideal_count": self.ideal_count,
            "acceptable_count": self.acceptable_count,
            "veto_count": self.veto_count,
            "total_criteria": self.total_criteria,
            "tier_results": {k: v.value for k, v in self.tier_results.items()},
            "tie_break_score": self.tie_break_score,
            "explanations": self.explanations,
            "has_veto": self.has_veto,
            "satisfaction_ratio": self.satisfaction_ratio,
            "first_breach_priority": self.first_breach_priority,
        }


@dataclass
class JointEvaluation:
    """
    Combined evaluation for an apartment across multiple people's preferences.
    """
    apartment_id: str
    individual_evaluations: Dict[str, ApartmentEvaluation] = field(default_factory=dict)
    
    # Joint metrics
    joint_veto_count: int = 0
    joint_violation_count: int = 0
    joint_satisfaction_score: float = 0.0
    
    # Criteria satisfaction across all people
    criteria_satisfaction: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    
    # Ranking info
    rank: Optional[int] = None
    
    @property
    def any_veto(self) -> bool:
        """Check if any person has a veto-level violation."""
        return any(e.has_veto for e in self.individual_evaluations.values())
    
    @property
    def all_satisfied(self) -> bool:
        """Check if all people have no vetoes."""
        return not self.any_veto
    
    def get_disagreements(self) -> List[Dict[str, Any]]:
        """
        Find criteria where people have different tier results.
        
        Returns:
            List of criteria with differing evaluations.
        """
        if len(self.individual_evaluations) < 2:
            return []
        
        disagreements = []
        all_criteria = set()
        for eval_result in self.individual_evaluations.values():
            all_criteria.update(eval_result.tier_results.keys())
        
        for criterion_id in all_criteria:
            tiers = {}
            for person, eval_result in self.individual_evaluations.items():
                tier = eval_result.tier_results.get(criterion_id)
                if tier:
                    tiers[person] = tier
            
            # Check if tiers differ
            unique_tiers = set(tiers.values())
            if len(unique_tiers) > 1:
                disagreements.append({
                    "criterion_id": criterion_id,
                    "tiers_by_person": {p: t.value for p, t in tiers.items()},
                })
        
        return disagreements
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "apartment_id": self.apartment_id,
            "individual_evaluations": {
                k: v.to_dict() for k, v in self.individual_evaluations.items()
            },
            "joint_veto_count": self.joint_veto_count,
            "joint_violation_count": self.joint_violation_count,
            "joint_satisfaction_score": self.joint_satisfaction_score,
            "criteria_satisfaction": self.criteria_satisfaction,
            "rank": self.rank,
            "any_veto": self.any_veto,
            "all_satisfied": self.all_satisfied,
            "disagreements": self.get_disagreements(),
        }


# Field mapping from existing scoring system to preference evaluation
FIELD_ALIASES = {
    # Commute (main driver commute)
    "commute_duration": "commute_time_you",
    "commute_duration_partner": "commute_time_partner",
    "commute_route": "commute_route",
    "route_annoyingness": "route_annoyingness",
    "commute_score": "commute_score",
    
    # Transit-specific fields (extracted from commute_details JSON)
    "transit_walking_minutes": "transit_walking_minutes",
    "transit_transfers": "transit_transfers",
    "transit_annoyingness": "transit_annoyingness",
    
    # Safety
    "safety_score": "combined_safety",
    "crime_index": "safety_score_opendata",
    
    # WFH
    "wfh_score": "wfh_quality_score",
    "natural_light": "natural_light",
    "desk_space": "desk_space_quality",
    "quietness": "quietness_score",
    
    # Gym
    "gym_walk_time": "gym_walk_time_mins",
    "gym_quality": "gym_quality",
    
    # Parking
    "parking_score": "parking_score",
    "parking_type": "parking_type",
    
    # Laundry
    "laundry_type": "laundry_type",
    "laundry_score": "laundry_score",
    
    # Space
    "sqft": "sqft",
    "sqft_min": "sqft_min",
    "sqft_max": "sqft_max",
    "space_luxury_score": "space_luxury_score",
    
    # Happening
    "happening_score": "happening_score",
    "restaurants_nearby": "restaurants_nearby",
    "cafes_nearby": "cafes_nearby",
    
    # Price (maps to total_monthly_cost which includes parking)
    "price": "price",
    "monthly_cost": "price",
    "total_monthly_cost": "total_monthly_cost",
    "base_rent": "base_rent",
    "parking_cost": "parking_cost",
}


def resolve_field(apartment_data: Dict[str, Any], field_name: str) -> Any:
    """
    Resolve a field name to its value, handling aliases.
    
    Args:
        apartment_data: Raw apartment data dictionary.
        field_name: Field name (may be an alias).
        
    Returns:
        Field value or None if not found.
    """
    # Try direct lookup first
    if field_name in apartment_data:
        return apartment_data[field_name]
    
    # Try alias
    alias = FIELD_ALIASES.get(field_name)
    if alias and alias in apartment_data:
        return apartment_data[alias]
    
    return None





