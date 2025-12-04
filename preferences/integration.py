"""
Integration module for connecting preference evaluation with existing apartment data.

Provides utilities for:
- Normalizing apartment data from Google Sheets
- Generating summary reports
- Bridging existing scoring system with preference evaluation
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import config

from .schemas import (
    PreferenceProfile,
    JointEvaluation,
    TierLevel,
    FIELD_ALIASES,
)


def normalize_apartment_data(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize apartment data from Google Sheets format to preference evaluation format.
    
    Handles:
    - Column name mapping from SHEET_COLUMNS
    - Type conversions (string to float, etc.)
    - Default values for missing fields
    
    Args:
        row: Raw row from Google Sheets.
        
    Returns:
        Normalized dictionary with standardized field names.
    """
    normalized = {}
    
    # Create reverse mapping from sheet column names to data keys
    reverse_mapping = {v: k for k, v in config.SHEET_COLUMNS.items()}
    
    # Process each field
    for key, value in row.items():
        # Get the standardized key
        std_key = reverse_mapping.get(key, key)
        
        # Convert value
        normalized[std_key] = _convert_value(value)
        
        # Also store under original key for compatibility
        if key != std_key:
            normalized[key] = _convert_value(value)
    
    # Create apartment ID from address
    address = normalized.get("address", "")
    normalized["apartment_id"] = address or str(hash(str(row)))[:8]
    
    # Map to preference field names
    for alias, original in FIELD_ALIASES.items():
        if original in normalized and alias not in normalized:
            normalized[alias] = normalized[original]
    
    # Compute derived fields
    _compute_derived_fields(normalized)
    
    return normalized


def _convert_value(value: Any) -> Any:
    """Convert a value to appropriate type."""
    if value is None or value == "":
        return None
    
    if isinstance(value, str):
        # Try to convert to number
        stripped = value.strip()
        
        # Handle boolean strings
        if stripped.lower() in ("true", "yes", "1"):
            return True
        if stripped.lower() in ("false", "no", "0"):
            return False
        
        # Handle currency
        if stripped.startswith("$"):
            try:
                return float(stripped.replace("$", "").replace(",", ""))
            except ValueError:
                pass
        
        # Try float
        try:
            return float(stripped)
        except ValueError:
            pass
        
        # Keep as string
        return stripped
    
    return value


def _compute_derived_fields(data: Dict[str, Any]) -> None:
    """Compute derived fields for preference evaluation."""
    
    # Combined safety score
    if "combined_safety" not in data or data["combined_safety"] is None:
        manual = data.get("manual_safety_rating") or data.get("manual_safety")
        opendata = data.get("safety_score_opendata")
        
        if manual is not None and opendata is not None:
            try:
                data["combined_safety"] = (float(manual) + float(opendata)) / 2
                data["safety_score"] = data["combined_safety"]
            except (ValueError, TypeError):
                pass
    else:
        data["safety_score"] = data["combined_safety"]
    
    # WFH score alias
    if "wfh_score" not in data and "wfh_quality_score" in data:
        data["wfh_score"] = data["wfh_quality_score"]
    
    # Price/monthly cost alias
    if "monthly_cost" not in data and "price" in data:
        data["monthly_cost"] = data["price"]
    
    # Gym walk time
    if "gym_walk_time" not in data and "gym_walk_time_mins" in data:
        data["gym_walk_time"] = data["gym_walk_time_mins"]
    
    # Commute duration mapping
    if "commute_duration" not in data:
        # Try commute_time_you first
        commute_you = data.get("commute_time_you")
        if commute_you is not None:
            data["commute_duration"] = commute_you


def generate_preference_summary(
    evaluations: List[JointEvaluation],
    profiles: Dict[str, PreferenceProfile],
) -> Dict[str, Any]:
    """
    Generate a summary of preference-based evaluation results.
    
    Args:
        evaluations: List of joint evaluations.
        profiles: Dictionary of preference profiles.
        
    Returns:
        Summary dictionary with statistics and insights.
    """
    if not evaluations:
        return {
            "summary": {
                "total_apartments": 0,
                "passing_apartments": 0,
                "vetoed_apartments": 0,
                "pass_rate": 0,
            },
            "profiles": list(profiles.keys()),
            "criteria_breakdown": {},
        }
    
    total = len(evaluations)
    passing = sum(1 for e in evaluations if not e.any_veto)
    vetoed = total - passing
    
    # Criteria breakdown
    criteria_breakdown = {}
    all_criteria = set()
    for profile in profiles.values():
        for c in profile.criteria:
            all_criteria.add(c.id)
    
    for criterion_id in all_criteria:
        ideal_count = 0
        acceptable_count = 0
        veto_count = 0
        
        for evaluation in evaluations:
            for person_eval in evaluation.individual_evaluations.values():
                tier = person_eval.tier_results.get(criterion_id)
                if tier == TierLevel.IDEAL:
                    ideal_count += 1
                elif tier == TierLevel.ACCEPTABLE:
                    acceptable_count += 1
                elif tier == TierLevel.VETO:
                    veto_count += 1
        
        criteria_breakdown[criterion_id] = {
            "ideal": ideal_count,
            "acceptable": acceptable_count,
            "veto": veto_count,
            "veto_rate": (veto_count / (total * len(profiles)) * 100) if total > 0 else 0,
        }
    
    # Most common veto reasons
    veto_reasons = {}
    for evaluation in evaluations:
        for person_name, person_eval in evaluation.individual_evaluations.items():
            if person_eval.first_violation and person_eval.first_violation.tier == TierLevel.VETO:
                criterion = person_eval.first_violation.criterion_name
                veto_reasons[criterion] = veto_reasons.get(criterion, 0) + 1
    
    top_veto_reasons = sorted(veto_reasons.items(), key=lambda x: -x[1])[:5]
    
    return {
        "summary": {
            "total_apartments": total,
            "passing_apartments": passing,
            "vetoed_apartments": vetoed,
            "pass_rate": round((passing / total) * 100, 1) if total > 0 else 0,
        },
        "profiles": list(profiles.keys()),
        "criteria_breakdown": criteria_breakdown,
        "top_veto_reasons": [{"criterion": k, "count": v} for k, v in top_veto_reasons],
    }


class PreferenceIntegration:
    """
    Integration layer between preference evaluation and the apartment analyzer.
    
    Provides methods to:
    - Load profiles from files
    - Evaluate apartments from the sheet
    - Generate comparison reports
    """
    
    def __init__(self, profiles_dir: Optional[Path] = None):
        """
        Initialize integration.
        
        Args:
            profiles_dir: Directory containing preference profile YAML files.
        """
        self.profiles_dir = profiles_dir or Path(__file__).parent / "profiles"
        self.profiles: Dict[str, PreferenceProfile] = {}
        self._load_profiles()
    
    def _load_profiles(self) -> None:
        """Load all profiles from the profiles directory."""
        if not self.profiles_dir.exists():
            self.profiles_dir.mkdir(parents=True, exist_ok=True)
            return
        
        for path in self.profiles_dir.glob("*.yaml"):
            try:
                profile = PreferenceProfile.load(path)
                self.profiles[profile.person_name] = profile
            except Exception as e:
                print(f"Error loading profile {path}: {e}")
    
    def reload_profiles(self) -> None:
        """Reload all profiles from disk."""
        self.profiles.clear()
        self._load_profiles()
    
    def get_profile(self, name: str) -> Optional[PreferenceProfile]:
        """Get a profile by name."""
        return self.profiles.get(name)
    
    def list_profiles(self) -> List[str]:
        """List all available profile names."""
        return list(self.profiles.keys())
    
    def evaluate_from_sheet_data(
        self,
        sheet_rows: List[Dict[str, Any]],
        profile_names: Optional[List[str]] = None,
    ) -> List[JointEvaluation]:
        """
        Evaluate apartments from sheet data.
        
        Args:
            sheet_rows: Raw rows from Google Sheets.
            profile_names: Names of profiles to use (None = all).
            
        Returns:
            List of joint evaluations.
        """
        from .evaluation_engine import PreferenceEvaluator
        
        # Select profiles
        if profile_names:
            profiles = {
                name: profile
                for name, profile in self.profiles.items()
                if name in profile_names
            }
        else:
            profiles = self.profiles
        
        if not profiles:
            raise ValueError("No profiles available for evaluation")
        
        # Normalize data
        normalized = [normalize_apartment_data(row) for row in sheet_rows]
        
        # Evaluate
        evaluator = PreferenceEvaluator(profiles)
        evaluations = evaluator.evaluate_all_apartments(normalized, id_field="apartment_id")
        
        return evaluations
    
    def get_shortlist(
        self,
        evaluations: List[JointEvaluation],
        max_vetoes: int = 0,
        top_n: int = 10,
    ) -> List[JointEvaluation]:
        """
        Get shortlist of apartments passing criteria.
        
        Args:
            evaluations: List of joint evaluations.
            max_vetoes: Maximum vetoes allowed.
            top_n: Number of apartments to return.
            
        Returns:
            Filtered and ranked list.
        """
        from .evaluation_engine import PreferenceEvaluator
        
        evaluator = PreferenceEvaluator(self.profiles)
        ranked = evaluator.rank_apartments(evaluations, sort_by="veto_first")
        shortlist = evaluator.get_shortlist(ranked, max_vetoes=max_vetoes, top_n=top_n)
        
        return shortlist
    
    def generate_report(
        self,
        evaluations: List[JointEvaluation],
        format: str = "text",
    ) -> str:
        """
        Generate a report from evaluations.
        
        Args:
            evaluations: List of joint evaluations.
            format: Output format ("text" or "markdown").
            
        Returns:
            Formatted report string.
        """
        from .reports import EvaluationReporter
        
        reporter = EvaluationReporter(self.profiles, evaluations)
        
        if format == "markdown":
            return reporter.generate_markdown_report()
        else:
            return reporter.generate_text_report()
