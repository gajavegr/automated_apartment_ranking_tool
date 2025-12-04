"""
Preference-based apartment evaluation system.

This module provides threshold-based evaluation of apartments against individual
and joint preference profiles, with explainable violation tracking.
"""

from .schemas import (
    PreferenceProfile,
    Threshold,
    CriterionPreference,
    ApartmentEvaluation,
    ViolationRecord,
    JointEvaluation,
    TierLevel,
    ComparisonOperator,
)
from .evaluation_engine import PreferenceEvaluator, ComparisonEngine
from .quiz import (
    PreferenceQuiz,
    AHPCalculator,
    PreferenceStrength,
    SCENARIO_BANK,
    THRESHOLD_QUESTIONS,
    create_default_profile,
)
from .reports import EvaluationReporter
from .integration import (
    normalize_apartment_data,
    generate_preference_summary,
    PreferenceIntegration,
)

__all__ = [
    # Schemas
    "PreferenceProfile",
    "Threshold",
    "CriterionPreference",
    "ApartmentEvaluation",
    "ViolationRecord",
    "JointEvaluation",
    "TierLevel",
    "ComparisonOperator",
    # Evaluation
    "PreferenceEvaluator",
    "ComparisonEngine",
    # Quiz
    "PreferenceQuiz",
    "AHPCalculator",
    "PreferenceStrength",
    "SCENARIO_BANK",
    "THRESHOLD_QUESTIONS",
    "create_default_profile",
    # Reports
    "EvaluationReporter",
    # Integration
    "normalize_apartment_data",
    "generate_preference_summary",
    "PreferenceIntegration",
]




