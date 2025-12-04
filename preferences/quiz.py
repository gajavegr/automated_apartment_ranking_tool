"""
Preference elicitation quiz with AHP-based weight derivation.

Uses concrete scenarios and pairwise comparisons to derive:
1. Priority ordering of criteria
2. Threshold values for ideal/acceptable/veto tiers
3. AHP weights for tie-breaking
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum
import math
import random
from datetime import datetime

from .schemas import (
    PreferenceProfile,
    CriterionPreference,
    Threshold,
    ComparisonOperator,
    TierLevel,
)


class PreferenceStrength(Enum):
    """Intensity of preference in pairwise comparison."""
    STRONGLY_PREFER_A = 9
    MODERATELY_PREFER_A = 7
    SLIGHTLY_PREFER_A = 5
    WEAKLY_PREFER_A = 3
    EQUAL = 1
    WEAKLY_PREFER_B = 1/3
    SLIGHTLY_PREFER_B = 1/5
    MODERATELY_PREFER_B = 1/7
    STRONGLY_PREFER_B = 1/9


@dataclass
class Scenario:
    """
    A concrete scenario for preference elicitation.
    
    Presents a realistic trade-off between two criteria to help users
    understand their true preferences.
    """
    id: str
    criterion_a: str
    criterion_b: str
    description: str
    option_a_description: str
    option_b_description: str
    context: str = ""  # Additional context (e.g., "Imagine it's a busy work week")
    
    # Optional: specific attribute values for the scenario
    option_a_values: Dict[str, Any] = field(default_factory=dict)
    option_b_values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThresholdQuestion:
    """
    A question to elicit threshold values for a criterion.
    """
    id: str
    criterion_id: str
    field: str
    question: str
    unit: str = ""
    min_value: float = 0
    max_value: float = 100
    step: float = 1
    default_ideal: float = 0
    default_acceptable: float = 0
    default_veto: float = 0
    is_lower_better: bool = True  # True if lower values are better (e.g., commute time)


# Pre-defined scenario bank for apartment criteria
SCENARIO_BANK: List[Scenario] = [
    # Commute vs Safety
    Scenario(
        id="commute_vs_safety_1",
        criterion_a="commute",
        criterion_b="safety",
        description="Trade-off: Shorter commute vs Safer neighborhood",
        option_a_description="25 minute commute, but the neighborhood has a moderate crime rate (crime index 40/100, some property crime)",
        option_b_description="45 minute commute, but the neighborhood is very safe (crime index 15/100, minimal incidents)",
        context="Think about your typical exhausting Thursday evening after a long day.",
        option_a_values={"commute_duration": 25, "crime_index": 40},
        option_b_values={"commute_duration": 45, "crime_index": 15},
    ),
    Scenario(
        id="commute_vs_safety_2",
        criterion_a="commute",
        criterion_b="safety",
        description="Trade-off: Commute convenience vs Night safety",
        option_a_description="15 minute drive on 280 (your preferred route), neighborhood feels sketchy after dark",
        option_b_description="35 minute commute with traffic, but you'd feel comfortable walking home at midnight",
        context="Consider both your daily commute and occasional late nights out.",
    ),
    
    # WFH Quality vs Happening
    Scenario(
        id="wfh_vs_happening_1",
        criterion_a="wfh_quality",
        criterion_b="happening",
        description="Trade-off: Work-from-home setup vs Neighborhood vibe",
        option_a_description="Quiet residential area with a dedicated office space, double-pane windows, but no walkable restaurants or cafes",
        option_b_description="Lively neighborhood with great cafes and restaurants, but the apartment has an open floor plan and street noise",
        context="Think about a typical work week where you WFH 3 days.",
    ),
    Scenario(
        id="wfh_vs_happening_2",
        criterion_a="wfh_quality",
        criterion_b="happening",
        description="Trade-off: Focus space vs Social convenience",
        option_a_description="Apartment has a study with a solid door for calls, but nearest coffee shop is a 15-minute drive",
        option_b_description="5 great coffee shops within walking distance, but work calls happen in the living room",
        context="Consider your productivity needs vs weekend lifestyle.",
    ),
    
    # Parking vs Gym
    Scenario(
        id="parking_vs_gym_1",
        criterion_a="parking",
        criterion_b="gym",
        description="Trade-off: Parking situation vs Gym access",
        option_a_description="Dedicated garage parking spot, but nearest quality gym is 25 minutes away",
        option_b_description="Street parking only (moderate difficulty), but a great gym is 5 minutes walk",
        context="Think about your weekly routine including gym visits and car usage.",
    ),
    
    # Space vs Price (implicit through commute trade-off)
    Scenario(
        id="space_vs_commute_1",
        criterion_a="space_luxury",
        criterion_b="commute",
        description="Trade-off: Living space vs Commute time",
        option_a_description="Spacious 900 sq ft with walk-in closet and balcony, but 50 minute commute",
        option_b_description="Compact 650 sq ft with basic closets, but 20 minute commute",
        context="Consider how you use your home space vs time spent commuting.",
    ),
    
    # Laundry vs Happening
    Scenario(
        id="laundry_vs_happening_1",
        criterion_a="laundry",
        criterion_b="happening",
        description="Trade-off: Laundry convenience vs Location vibe",
        option_a_description="In-unit washer/dryer, but in a quiet suburban area with few walkable amenities",
        option_b_description="Shared laundry in building, but walking distance to great restaurants and nightlife",
        context="Think about your laundry habits and social preferences.",
    ),
    
    # Safety vs Happening
    Scenario(
        id="safety_vs_happening_1",
        criterion_a="safety",
        criterion_b="happening",
        description="Trade-off: Neighborhood safety vs Nightlife access",
        option_a_description="Very safe, quiet residential neighborhood - but 20 minute Uber to any bar or restaurant",
        option_b_description="Walking distance to great bars and restaurants, but you'd be cautious walking alone at night",
        context="Consider your typical weekend plans.",
    ),
    
    # Parking vs Space
    Scenario(
        id="parking_vs_space_1",
        criterion_a="parking",
        criterion_b="space_luxury",
        description="Trade-off: Parking vs Apartment size",
        option_a_description="Two parking spots (for car and motorcycle), but apartment is 600 sq ft",
        option_b_description="Street parking only, but apartment is 850 sq ft with walk-in closet",
        context="Think about your parking needs vs living space comfort.",
    ),
    
    # Commute vs WFH
    Scenario(
        id="commute_vs_wfh_1",
        criterion_a="commute",
        criterion_b="wfh_quality",
        description="Trade-off: Office commute vs WFH setup",
        option_a_description="15 minute commute to office, but WFH means working from a corner of the living room",
        option_b_description="45 minute commute, but you have a dedicated home office with great natural light",
        context="Assuming you go to office 2-3 days per week.",
    ),
    
    # Gym vs Safety
    Scenario(
        id="gym_vs_safety_1",
        criterion_a="gym",
        criterion_b="safety",
        description="Trade-off: Gym proximity vs Evening safety",
        option_a_description="5 minute walk to a great gym with squat racks, but you'd drive after dark",
        option_b_description="20 minute walk to decent gym, but the neighborhood feels safe at all hours",
        context="Consider your gym schedule (morning vs evening workouts).",
    ),
]

# Threshold questions for each criterion
THRESHOLD_QUESTIONS: List[ThresholdQuestion] = [
    # Commute
    ThresholdQuestion(
        id="commute_duration_ideal",
        criterion_id="commute",
        field="commute_duration",
        question="What's the longest commute you'd consider ideal?",
        unit="minutes",
        min_value=5,
        max_value=60,
        step=5,
        default_ideal=30,
        default_acceptable=45,
        default_veto=60,
        is_lower_better=True,
    ),
    
    # Safety
    ThresholdQuestion(
        id="safety_score_ideal",
        criterion_id="safety",
        field="safety_score",
        question="What's the minimum safety score you'd consider ideal? (10 = safest)",
        unit="/10",
        min_value=1,
        max_value=10,
        step=0.5,
        default_ideal=8,
        default_acceptable=6,
        default_veto=5,
        is_lower_better=False,
    ),
    
    # WFH
    ThresholdQuestion(
        id="wfh_score_ideal",
        criterion_id="wfh_quality",
        field="wfh_score",
        question="What's the minimum WFH quality score you'd consider ideal? (10 = best)",
        unit="/10",
        min_value=1,
        max_value=10,
        step=0.5,
        default_ideal=7,
        default_acceptable=5,
        default_veto=3,
        is_lower_better=False,
    ),
    
    # Gym
    ThresholdQuestion(
        id="gym_walk_time_ideal",
        criterion_id="gym",
        field="gym_walk_time",
        question="What's the maximum walk time to a gym you'd consider ideal?",
        unit="minutes",
        min_value=2,
        max_value=30,
        step=2,
        default_ideal=10,
        default_acceptable=15,
        default_veto=25,
        is_lower_better=True,
    ),
    
    # Parking
    ThresholdQuestion(
        id="parking_score_ideal",
        criterion_id="parking",
        field="parking_score",
        question="What's the minimum parking score you'd consider ideal? (10 = best)",
        unit="/10",
        min_value=0,
        max_value=10,
        step=1,
        default_ideal=8,
        default_acceptable=5,
        default_veto=3,
        is_lower_better=False,
    ),
    
    # Space
    ThresholdQuestion(
        id="sqft_ideal",
        criterion_id="space_luxury",
        field="sqft",
        question="What's the minimum square footage you'd consider ideal?",
        unit="sq ft",
        min_value=400,
        max_value=1500,
        step=50,
        default_ideal=800,
        default_acceptable=650,
        default_veto=500,
        is_lower_better=False,
    ),
    
    # Happening
    ThresholdQuestion(
        id="happening_score_ideal",
        criterion_id="happening",
        field="happening_score",
        question="What's the minimum 'happening' score for the neighborhood? (10 = very lively)",
        unit="/10",
        min_value=0,
        max_value=10,
        step=1,
        default_ideal=7,
        default_acceptable=4,
        default_veto=2,
        is_lower_better=False,
    ),
    
    # Laundry
    ThresholdQuestion(
        id="laundry_score_ideal",
        criterion_id="laundry",
        field="laundry_score",
        question="What's the minimum laundry score you'd accept? (10 = in-unit)",
        unit="/10",
        min_value=0,
        max_value=10,
        step=1,
        default_ideal=8,
        default_acceptable=5,
        default_veto=0,
        is_lower_better=False,
    ),
    
    # Price
    ThresholdQuestion(
        id="price_ideal",
        criterion_id="price",
        field="monthly_cost",
        question="What's the maximum monthly rent you'd consider ideal?",
        unit="$/month",
        min_value=2000,
        max_value=6000,
        step=100,
        default_ideal=3500,
        default_acceptable=4000,
        default_veto=4500,
        is_lower_better=True,
    ),
]


class AHPCalculator:
    """
    Analytic Hierarchy Process calculator for deriving weights from pairwise comparisons.
    """
    
    # Random Index values for consistency check (n x RI)
    RANDOM_INDEX = {
        1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90, 5: 1.12,
        6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49,
    }
    
    def __init__(self, criteria: List[str]):
        """
        Initialize AHP calculator.
        
        Args:
            criteria: List of criterion IDs to compare.
        """
        self.criteria = criteria
        self.n = len(criteria)
        self.comparison_matrix: List[List[float]] = [
            [1.0] * self.n for _ in range(self.n)
        ]
    
    def set_comparison(
        self,
        criterion_a: str,
        criterion_b: str,
        strength: PreferenceStrength,
    ) -> None:
        """
        Set a pairwise comparison.
        
        Args:
            criterion_a: First criterion.
            criterion_b: Second criterion.
            strength: How much A is preferred over B.
        """
        try:
            i = self.criteria.index(criterion_a)
            j = self.criteria.index(criterion_b)
        except ValueError:
            return
        
        value = strength.value if isinstance(strength.value, (int, float)) else float(strength.value)
        self.comparison_matrix[i][j] = value
        self.comparison_matrix[j][i] = 1.0 / value
    
    def set_comparison_value(
        self,
        criterion_a: str,
        criterion_b: str,
        value: float,
    ) -> None:
        """
        Set a pairwise comparison with raw value.
        
        Args:
            criterion_a: First criterion.
            criterion_b: Second criterion.
            value: Raw comparison value (A/B ratio).
        """
        try:
            i = self.criteria.index(criterion_a)
            j = self.criteria.index(criterion_b)
        except ValueError:
            return
        
        self.comparison_matrix[i][j] = value
        self.comparison_matrix[j][i] = 1.0 / value if value != 0 else 1.0
    
    def calculate_weights(self) -> Dict[str, float]:
        """
        Calculate priority weights using the geometric mean method.
        
        Returns:
            Dictionary mapping criterion IDs to weights (sum to 1.0).
        """
        # Calculate geometric mean of each row
        geometric_means = []
        for row in self.comparison_matrix:
            product = 1.0
            for val in row:
                product *= val
            geometric_means.append(product ** (1.0 / self.n))
        
        # Normalize
        total = sum(geometric_means)
        if total == 0:
            # Equal weights fallback
            return {c: 1.0 / self.n for c in self.criteria}
        
        weights = {}
        for i, criterion in enumerate(self.criteria):
            weights[criterion] = geometric_means[i] / total
        
        return weights
    
    def calculate_consistency_ratio(self) -> float:
        """
        Calculate the consistency ratio of the comparison matrix.
        
        A CR <= 0.10 indicates acceptable consistency.
        
        Returns:
            Consistency ratio (0.0 = perfectly consistent).
        """
        if self.n <= 2:
            return 0.0
        
        weights = self.calculate_weights()
        weight_vector = [weights[c] for c in self.criteria]
        
        # Calculate Aw (matrix times weight vector)
        aw = []
        for row in self.comparison_matrix:
            aw.append(sum(row[j] * weight_vector[j] for j in range(self.n)))
        
        # Calculate lambda_max
        lambda_max = sum(aw[i] / weight_vector[i] for i in range(self.n)) / self.n
        
        # Consistency Index
        ci = (lambda_max - self.n) / (self.n - 1)
        
        # Consistency Ratio
        ri = self.RANDOM_INDEX.get(self.n, 1.49)
        if ri == 0:
            return 0.0
        
        return ci / ri
    
    def get_inconsistent_pairs(self, threshold: float = 0.1) -> List[Tuple[str, str]]:
        """
        Find pairs that contribute most to inconsistency.
        
        Args:
            threshold: CR threshold for flagging.
            
        Returns:
            List of (criterion_a, criterion_b) pairs to reconsider.
        """
        inconsistent = []
        
        # Check transitivity violations
        for i in range(self.n):
            for j in range(i + 1, self.n):
                for k in range(j + 1, self.n):
                    # If A > B and B > C, then A should > C
                    ab = self.comparison_matrix[i][j]
                    bc = self.comparison_matrix[j][k]
                    ac = self.comparison_matrix[i][k]
                    
                    expected_ac = ab * bc
                    ratio = ac / expected_ac if expected_ac != 0 else 1.0
                    
                    # If ratio is far from 1, there's inconsistency
                    if ratio < 0.5 or ratio > 2.0:
                        inconsistent.append((self.criteria[i], self.criteria[k]))
        
        return inconsistent


@dataclass
class QuizResponse:
    """Record of a single quiz response."""
    question_id: str
    response_value: Any
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class PreferenceQuiz:
    """
    Interactive quiz for preference elicitation.
    
    Guides users through scenarios and threshold questions to build
    a complete preference profile.
    """
    
    def __init__(
        self,
        person_name: str,
        criteria_ids: Optional[List[str]] = None,
    ):
        """
        Initialize quiz.
        
        Args:
            person_name: Name of person taking the quiz.
            criteria_ids: List of criteria to include (None = all).
        """
        self.person_name = person_name
        self.criteria_ids = criteria_ids or [
            "commute", "safety", "wfh_quality", "gym",
            "parking", "space_luxury", "happening", "laundry", "price"
        ]
        
        self.responses: List[QuizResponse] = []
        self.pairwise_comparisons: Dict[Tuple[str, str], float] = {}
        self.threshold_values: Dict[str, Dict[str, float]] = {}
        self.priority_ranking: List[str] = []
        
        # Filter scenarios and questions to relevant criteria
        self.scenarios = [
            s for s in SCENARIO_BANK
            if s.criterion_a in self.criteria_ids and s.criterion_b in self.criteria_ids
        ]
        self.threshold_questions = [
            q for q in THRESHOLD_QUESTIONS
            if q.criterion_id in self.criteria_ids
        ]
    
    def get_pairwise_scenarios(self, shuffle: bool = True) -> List[Scenario]:
        """
        Get scenarios for pairwise comparisons.
        
        Args:
            shuffle: Randomize order to reduce bias.
            
        Returns:
            List of scenarios.
        """
        scenarios = self.scenarios.copy()
        if shuffle:
            random.shuffle(scenarios)
        return scenarios
    
    def record_pairwise_response(
        self,
        scenario_id: str,
        preference: PreferenceStrength,
    ) -> None:
        """
        Record response to a pairwise comparison scenario.
        
        Args:
            scenario_id: ID of the scenario.
            preference: User's preference strength.
        """
        scenario = next((s for s in self.scenarios if s.id == scenario_id), None)
        if not scenario:
            return
        
        # Store comparison
        key = (scenario.criterion_a, scenario.criterion_b)
        value = preference.value if isinstance(preference.value, (int, float)) else float(preference.value)
        self.pairwise_comparisons[key] = value
        
        # Record response
        self.responses.append(QuizResponse(
            question_id=scenario_id,
            response_value=preference.name,
        ))
    
    def record_threshold_response(
        self,
        question_id: str,
        ideal: float,
        acceptable: float,
        veto: float,
    ) -> None:
        """
        Record response to a threshold question.
        
        Args:
            question_id: ID of the question.
            ideal: Ideal threshold value.
            acceptable: Acceptable threshold value.
            veto: Veto threshold value.
        """
        question = next((q for q in self.threshold_questions if q.id == question_id), None)
        if not question:
            return
        
        self.threshold_values[question.criterion_id] = {
            "field": question.field,
            "ideal": ideal,
            "acceptable": acceptable,
            "veto": veto,
            "is_lower_better": question.is_lower_better,
        }
        
        self.responses.append(QuizResponse(
            question_id=question_id,
            response_value={"ideal": ideal, "acceptable": acceptable, "veto": veto},
        ))
    
    def record_priority_ranking(self, ranking: List[str]) -> None:
        """
        Record user's priority ranking of criteria.
        
        Args:
            ranking: List of criterion IDs in priority order (1st = highest).
        """
        self.priority_ranking = ranking
        self.responses.append(QuizResponse(
            question_id="priority_ranking",
            response_value=ranking,
        ))
    
    def calculate_ahp_weights(self) -> Tuple[Dict[str, float], float]:
        """
        Calculate AHP weights from pairwise comparisons.
        
        Returns:
            Tuple of (weights dict, consistency ratio).
        """
        ahp = AHPCalculator(self.criteria_ids)
        
        for (a, b), value in self.pairwise_comparisons.items():
            ahp.set_comparison_value(a, b, value)
        
        weights = ahp.calculate_weights()
        consistency = ahp.calculate_consistency_ratio()
        
        return weights, consistency
    
    def get_inconsistent_comparisons(self) -> List[Scenario]:
        """
        Get scenarios for comparisons that seem inconsistent.
        
        Returns:
            List of scenarios to re-ask.
        """
        ahp = AHPCalculator(self.criteria_ids)
        
        for (a, b), value in self.pairwise_comparisons.items():
            ahp.set_comparison_value(a, b, value)
        
        inconsistent_pairs = ahp.get_inconsistent_pairs()
        
        # Find scenarios for these pairs
        scenarios = []
        for a, b in inconsistent_pairs:
            for scenario in self.scenarios:
                if (scenario.criterion_a == a and scenario.criterion_b == b) or \
                   (scenario.criterion_a == b and scenario.criterion_b == a):
                    scenarios.append(scenario)
                    break
        
        return scenarios
    
    def build_profile(self) -> PreferenceProfile:
        """
        Build a PreferenceProfile from quiz responses.
        
        Returns:
            Complete PreferenceProfile.
        """
        # Calculate AHP weights
        ahp_weights, consistency = self.calculate_ahp_weights()
        
        # Build criteria preferences
        criteria = []
        
        # Use priority ranking if provided, otherwise sort by AHP weight
        if self.priority_ranking:
            sorted_criteria = self.priority_ranking
        else:
            sorted_criteria = sorted(
                self.criteria_ids,
                key=lambda c: ahp_weights.get(c, 0),
                reverse=True
            )
        
        for priority, criterion_id in enumerate(sorted_criteria, 1):
            thresholds = self.threshold_values.get(criterion_id, {})
            
            # Build threshold objects
            field = thresholds.get("field", criterion_id + "_score")
            is_lower_better = thresholds.get("is_lower_better", True)
            
            ideal_value = thresholds.get("ideal")
            acceptable_value = thresholds.get("acceptable")
            veto_value = thresholds.get("veto")
            
            ideal_thresholds = []
            acceptable_thresholds = []
            veto_thresholds = []
            
            if ideal_value is not None:
                op = ComparisonOperator.LTE if is_lower_better else ComparisonOperator.GTE
                ideal_thresholds.append(Threshold(field=field, value=ideal_value, operator=op))
            
            if acceptable_value is not None:
                op = ComparisonOperator.LTE if is_lower_better else ComparisonOperator.GTE
                acceptable_thresholds.append(Threshold(field=field, value=acceptable_value, operator=op))
            
            if veto_value is not None:
                # Veto: if lower is better, veto if > veto_value; if higher is better, veto if < veto_value
                op = ComparisonOperator.LTE if is_lower_better else ComparisonOperator.GTE
                veto_thresholds.append(Threshold(field=field, value=veto_value, operator=op))
            
            criterion_pref = CriterionPreference(
                id=criterion_id,
                display_name=criterion_id.replace("_", " ").title(),
                priority_order=priority,
                ideal=ideal_thresholds,
                acceptable=acceptable_thresholds,
                veto=veto_thresholds,
                veto_reason=f"Does not meet minimum {criterion_id} requirements",
            )
            criteria.append(criterion_pref)
        
        # Build profile
        profile = PreferenceProfile(
            person_name=self.person_name,
            version=1,
            criteria=criteria,
            ahp_weights=ahp_weights,
            ahp_consistency_ratio=consistency,
            notes=f"Generated from quiz on {datetime.now().strftime('%Y-%m-%d')}",
            quiz_responses={
                "pairwise_comparisons": {
                    f"{a}:{b}": v for (a, b), v in self.pairwise_comparisons.items()
                },
                "threshold_values": self.threshold_values,
                "priority_ranking": self.priority_ranking,
            },
        )
        
        return profile
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get quiz completion progress.
        
        Returns:
            Progress summary.
        """
        total_scenarios = len(self.scenarios)
        completed_scenarios = len([
            r for r in self.responses
            if r.question_id in [s.id for s in self.scenarios]
        ])
        
        total_thresholds = len(self.threshold_questions)
        completed_thresholds = len(self.threshold_values)
        
        return {
            "scenarios_completed": completed_scenarios,
            "scenarios_total": total_scenarios,
            "thresholds_completed": completed_thresholds,
            "thresholds_total": total_thresholds,
            "priority_set": len(self.priority_ranking) > 0,
            "overall_percent": (
                (completed_scenarios + completed_thresholds + (1 if self.priority_ranking else 0)) /
                (total_scenarios + total_thresholds + 1)
            ) * 100,
        }


def create_default_profile(
    person_name: str,
    priorities: Optional[List[str]] = None,
) -> PreferenceProfile:
    """
    Create a default preference profile with sensible defaults.
    
    Useful as a starting point before taking the quiz.
    
    Args:
        person_name: Name of the person.
        priorities: Optional priority ordering of criteria.
        
    Returns:
        PreferenceProfile with default values.
    """
    default_criteria = [
        CriterionPreference(
            id="safety",
            display_name="Safety",
            priority_order=1,
            ideal=[Threshold(field="safety_score", value=8.0, operator=ComparisonOperator.GTE)],
            acceptable=[Threshold(field="safety_score", value=6.0, operator=ComparisonOperator.GTE)],
            veto=[Threshold(field="safety_score", value=5.0, operator=ComparisonOperator.GTE)],
            veto_reason="Neighborhood safety below minimum acceptable level",
        ),
        CriterionPreference(
            id="commute",
            display_name="Commute",
            priority_order=2,
            ideal=[Threshold(field="commute_duration", value=30, operator=ComparisonOperator.LTE)],
            acceptable=[Threshold(field="commute_duration", value=45, operator=ComparisonOperator.LTE)],
            veto=[Threshold(field="commute_duration", value=60, operator=ComparisonOperator.LTE)],
            veto_reason="Commute time exceeds maximum acceptable",
        ),
        CriterionPreference(
            id="wfh_quality",
            display_name="WFH Quality",
            priority_order=3,
            ideal=[Threshold(field="wfh_score", value=7.0, operator=ComparisonOperator.GTE)],
            acceptable=[Threshold(field="wfh_score", value=5.0, operator=ComparisonOperator.GTE)],
            veto=[Threshold(field="wfh_score", value=3.0, operator=ComparisonOperator.GTE)],
            veto_reason="Work-from-home setup inadequate",
        ),
        CriterionPreference(
            id="parking",
            display_name="Parking",
            priority_order=4,
            ideal=[Threshold(field="parking_score", value=8.0, operator=ComparisonOperator.GTE)],
            acceptable=[Threshold(field="parking_score", value=5.0, operator=ComparisonOperator.GTE)],
            veto=[Threshold(field="parking_score", value=3.0, operator=ComparisonOperator.GTE)],
            veto_reason="Parking situation unacceptable",
        ),
        CriterionPreference(
            id="gym",
            display_name="Gym",
            priority_order=5,
            ideal=[Threshold(field="gym_walk_time", value=10, operator=ComparisonOperator.LTE)],
            acceptable=[Threshold(field="gym_walk_time", value=15, operator=ComparisonOperator.LTE)],
            veto=[Threshold(field="gym_walk_time", value=25, operator=ComparisonOperator.LTE)],
            veto_reason="No accessible gym nearby",
        ),
        CriterionPreference(
            id="space_luxury",
            display_name="Space & Luxury",
            priority_order=6,
            ideal=[Threshold(field="sqft", value=800, operator=ComparisonOperator.GTE)],
            acceptable=[Threshold(field="sqft", value=650, operator=ComparisonOperator.GTE)],
            veto=[Threshold(field="sqft", value=500, operator=ComparisonOperator.GTE)],
            veto_reason="Space too small",
        ),
        CriterionPreference(
            id="laundry",
            display_name="Laundry",
            priority_order=7,
            ideal=[Threshold(field="laundry_score", value=8.0, operator=ComparisonOperator.GTE)],
            acceptable=[Threshold(field="laundry_score", value=5.0, operator=ComparisonOperator.GTE)],
            veto=[],  # No veto for laundry
            veto_reason="",
        ),
        CriterionPreference(
            id="happening",
            display_name="Happening-ness",
            priority_order=8,
            ideal=[Threshold(field="happening_score", value=7.0, operator=ComparisonOperator.GTE)],
            acceptable=[Threshold(field="happening_score", value=4.0, operator=ComparisonOperator.GTE)],
            veto=[],  # No veto for happening
            veto_reason="",
        ),
        CriterionPreference(
            id="price",
            display_name="Price",
            priority_order=9,
            ideal=[Threshold(field="monthly_cost", value=3500, operator=ComparisonOperator.LTE)],
            acceptable=[Threshold(field="monthly_cost", value=4000, operator=ComparisonOperator.LTE)],
            veto=[Threshold(field="monthly_cost", value=4500, operator=ComparisonOperator.LTE)],
            veto_reason="Rent exceeds budget",
        ),
    ]
    
    # Reorder by provided priorities
    if priorities:
        criteria_map = {c.id: c for c in default_criteria}
        reordered = []
        for i, cid in enumerate(priorities, 1):
            if cid in criteria_map:
                criterion = criteria_map[cid]
                criterion.priority_order = i
                reordered.append(criterion)
        # Add any remaining criteria
        for c in default_criteria:
            if c.id not in priorities:
                c.priority_order = len(reordered) + 1
                reordered.append(c)
        default_criteria = reordered
    
    # Default equal weights
    n_criteria = len(default_criteria)
    ahp_weights = {c.id: 1.0 / n_criteria for c in default_criteria}
    
    return PreferenceProfile(
        person_name=person_name,
        version=1,
        criteria=default_criteria,
        ahp_weights=ahp_weights,
        ahp_consistency_ratio=0.0,
        notes="Default profile - customize thresholds and take quiz for personalized weights",
    )





