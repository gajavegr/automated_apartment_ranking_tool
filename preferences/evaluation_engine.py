"""
Preference-based apartment evaluation engine.

Evaluates apartments against individual preference profiles and produces
joint rankings with explainable violation tracking.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from .schemas import (
    PreferenceProfile,
    CriterionPreference,
    ApartmentEvaluation,
    JointEvaluation,
    ViolationRecord,
    TierLevel,
    resolve_field,
)


class PreferenceEvaluator:
    """
    Evaluates apartments against preference profiles.
    
    Supports:
    - Individual evaluation against one person's preferences
    - Joint evaluation across multiple people
    - Lexicographic ranking by priority-ordered violations
    - AHP-weighted tie-breaking scores
    """
    
    def __init__(self, profiles: Dict[str, PreferenceProfile]):
        """
        Initialize evaluator with preference profiles.
        
        Args:
            profiles: Dictionary mapping person names to their preference profiles.
        """
        self.profiles = profiles
    
    @classmethod
    def from_files(cls, profile_paths: List[Path]) -> "PreferenceEvaluator":
        """
        Create evaluator from profile YAML files.
        
        Args:
            profile_paths: List of paths to profile YAML files.
            
        Returns:
            Initialized PreferenceEvaluator.
        """
        profiles = {}
        for path in profile_paths:
            profile = PreferenceProfile.load(path)
            profiles[profile.person_name] = profile
        return cls(profiles)
    
    def evaluate_individual(
        self,
        apartment_id: str,
        apartment_data: Dict[str, Any],
        profile: PreferenceProfile,
    ) -> ApartmentEvaluation:
        """
        Evaluate one apartment against one person's preferences.
        
        Args:
            apartment_id: Unique identifier for the apartment.
            apartment_data: Dictionary with apartment attributes.
            profile: Preference profile to evaluate against.
            
        Returns:
            ApartmentEvaluation with violation details and scores.
        """
        evaluation = ApartmentEvaluation(
            apartment_id=apartment_id,
            person_name=profile.person_name,
            total_criteria=len(profile.criteria),
        )
        
        # Process criteria in priority order
        sorted_criteria = profile.get_criteria_by_priority()
        
        for criterion in sorted_criteria:
            # Resolve field aliases in apartment data
            resolved_data = self._resolve_apartment_data(apartment_data, criterion)
            
            # Evaluate tier for this criterion
            tier = criterion.evaluate_tier(resolved_data)
            evaluation.tier_results[criterion.id] = tier
            
            # Count tiers
            if tier == TierLevel.IDEAL:
                evaluation.ideal_count += 1
            elif tier == TierLevel.ACCEPTABLE:
                evaluation.acceptable_count += 1
            else:  # VETO
                evaluation.veto_count += 1
            
            # Record violations
            if tier != TierLevel.IDEAL:
                # Get violated thresholds for the tier we fell short of
                target_tier = TierLevel.IDEAL if tier == TierLevel.ACCEPTABLE else TierLevel.ACCEPTABLE
                violations = criterion.get_violated_thresholds(resolved_data, target_tier)
                
                # If acceptable and ideal has violations, record ideal violations
                # If veto, record acceptable violations (or veto violations)
                if tier == TierLevel.VETO:
                    # Check veto thresholds directly
                    veto_violations = criterion.get_violated_thresholds(resolved_data, TierLevel.VETO)
                    if veto_violations:
                        violations = veto_violations
                    else:
                        # Fell below acceptable
                        violations = criterion.get_violated_thresholds(resolved_data, TierLevel.ACCEPTABLE)
                
                for v in violations:
                    record = ViolationRecord(
                        criterion_id=criterion.id,
                        criterion_name=criterion.display_name,
                        priority_order=criterion.priority_order,
                        tier=tier,
                        field=v["field"],
                        expected_value=v["expected"],
                        actual_value=v["actual"],
                        operator=v["operator"],
                        distance=v["distance"],
                    )
                    evaluation.all_violations.append(record)
                    
                    # Track first violation (by priority)
                    if evaluation.first_violation is None:
                        evaluation.first_violation = record
            
            # Build explanation
            evaluation.explanations[criterion.id] = self._build_explanation(
                criterion, tier, resolved_data
            )
        
        # Calculate tie-break score using AHP weights
        evaluation.tie_break_score = self._calculate_tie_break_score(
            evaluation, profile
        )
        
        return evaluation
    
    def evaluate_joint(
        self,
        apartment_id: str,
        apartment_data: Dict[str, Any],
    ) -> JointEvaluation:
        """
        Evaluate one apartment across all loaded profiles.
        
        Args:
            apartment_id: Unique identifier for the apartment.
            apartment_data: Dictionary with apartment attributes.
            
        Returns:
            JointEvaluation with combined results.
        """
        joint = JointEvaluation(apartment_id=apartment_id)
        
        # Evaluate for each person
        for person_name, profile in self.profiles.items():
            individual = self.evaluate_individual(
                apartment_id, apartment_data, profile
            )
            joint.individual_evaluations[person_name] = individual
            
            # Aggregate joint metrics
            joint.joint_veto_count += individual.veto_count
            joint.joint_violation_count += len(individual.all_violations)
        
        # Calculate joint satisfaction score
        if joint.individual_evaluations:
            scores = [e.tie_break_score for e in joint.individual_evaluations.values()]
            joint.joint_satisfaction_score = sum(scores) / len(scores)
        
        # Build criteria satisfaction matrix
        joint.criteria_satisfaction = self._build_satisfaction_matrix(joint)
        
        return joint
    
    def evaluate_all_apartments(
        self,
        apartments: List[Dict[str, Any]],
        id_field: str = "apartment_id",
    ) -> List[JointEvaluation]:
        """
        Evaluate multiple apartments and return joint evaluations.
        
        Args:
            apartments: List of apartment data dictionaries.
            id_field: Field name to use as apartment ID.
            
        Returns:
            List of JointEvaluation objects.
        """
        evaluations = []
        for apt in apartments:
            apt_id = apt.get(id_field, str(hash(str(apt))))
            joint = self.evaluate_joint(apt_id, apt)
            evaluations.append(joint)
        
        return evaluations
    
    def rank_apartments(
        self,
        evaluations: List[JointEvaluation],
        sort_by: str = "lexicographic",
    ) -> List[JointEvaluation]:
        """
        Rank apartments based on evaluation results.
        
        Args:
            evaluations: List of joint evaluations.
            sort_by: Ranking strategy:
                - "lexicographic": Sort by first violation priority, then count
                - "violation_count": Sort by total violation count
                - "satisfaction": Sort by joint satisfaction score
                - "veto_first": Put non-veto apartments first, then by score
                
        Returns:
            Sorted list of evaluations with rank assigned.
        """
        if sort_by == "lexicographic":
            sorted_evals = self._sort_lexicographic(evaluations)
        elif sort_by == "violation_count":
            sorted_evals = sorted(evaluations, key=lambda e: e.joint_violation_count)
        elif sort_by == "satisfaction":
            sorted_evals = sorted(
                evaluations, key=lambda e: -e.joint_satisfaction_score
            )
        elif sort_by == "veto_first":
            sorted_evals = sorted(
                evaluations,
                key=lambda e: (e.any_veto, -e.joint_satisfaction_score),
            )
        else:
            sorted_evals = evaluations
        
        # Assign ranks
        for i, evaluation in enumerate(sorted_evals, 1):
            evaluation.rank = i
        
        return sorted_evals
    
    def get_shortlist(
        self,
        evaluations: List[JointEvaluation],
        max_vetoes: int = 0,
        top_n: Optional[int] = None,
    ) -> List[JointEvaluation]:
        """
        Get shortlist of apartments meeting minimum criteria.
        
        Args:
            evaluations: List of joint evaluations.
            max_vetoes: Maximum number of veto violations allowed (0 = none).
            top_n: Return only top N apartments (None = all passing).
            
        Returns:
            Filtered and ranked list of evaluations.
        """
        # Filter by veto count
        passing = [e for e in evaluations if e.joint_veto_count <= max_vetoes]
        
        # Rank
        ranked = self.rank_apartments(passing, sort_by="veto_first")
        
        # Limit to top N
        if top_n is not None:
            ranked = ranked[:top_n]
        
        return ranked
    
    def _resolve_apartment_data(
        self,
        apartment_data: Dict[str, Any],
        criterion: CriterionPreference,
    ) -> Dict[str, Any]:
        """
        Resolve field names for a criterion using aliases.
        
        Args:
            apartment_data: Raw apartment data.
            criterion: Criterion with threshold fields to resolve.
            
        Returns:
            Dictionary with resolved field values.
        """
        resolved = {}
        
        # Get all fields used by this criterion's thresholds
        all_fields = set()
        for threshold in criterion.ideal + criterion.acceptable + criterion.veto:
            all_fields.add(threshold.field)
        
        # Resolve each field
        for field in all_fields:
            resolved[field] = resolve_field(apartment_data, field)
        
        return resolved
    
    def _build_explanation(
        self,
        criterion: CriterionPreference,
        tier: TierLevel,
        data: Dict[str, Any],
    ) -> str:
        """
        Build human-readable explanation for a criterion evaluation.
        
        Args:
            criterion: The criterion evaluated.
            tier: Resulting tier level.
            data: Resolved apartment data.
            
        Returns:
            Explanation string.
        """
        if tier == TierLevel.IDEAL:
            return f"✓ {criterion.display_name}: Meets ideal requirements"
        elif tier == TierLevel.ACCEPTABLE:
            # Find what missed ideal
            ideal_violations = criterion.get_violated_thresholds(data, TierLevel.IDEAL)
            if ideal_violations:
                v = ideal_violations[0]
                return (
                    f"~ {criterion.display_name}: Acceptable "
                    f"({v['field']}: {v['actual']} vs ideal {v['expected']})"
                )
            return f"~ {criterion.display_name}: Meets acceptable but not ideal"
        else:  # VETO
            if criterion.veto_reason:
                return f"✗ {criterion.display_name}: {criterion.veto_reason}"
            acceptable_violations = criterion.get_violated_thresholds(
                data, TierLevel.ACCEPTABLE
            )
            if acceptable_violations:
                v = acceptable_violations[0]
                return (
                    f"✗ {criterion.display_name}: Below acceptable "
                    f"({v['field']}: {v['actual']} vs required {v['expected']})"
                )
            return f"✗ {criterion.display_name}: Does not meet minimum requirements"
    
    def _calculate_tie_break_score(
        self,
        evaluation: ApartmentEvaluation,
        profile: PreferenceProfile,
    ) -> float:
        """
        Calculate tie-break score using AHP weights.
        
        Scoring:
        - Ideal tier: 1.0
        - Acceptable tier: 0.7
        - Veto tier: 0.0
        
        Weighted by AHP weights if available, otherwise equal weights.
        
        Args:
            evaluation: Individual apartment evaluation.
            profile: Preference profile with AHP weights.
            
        Returns:
            Weighted satisfaction score (0-1 scale).
        """
        if not profile.criteria:
            return 0.0
        
        total_weighted = 0.0
        total_weight = 0.0
        
        for criterion in profile.criteria:
            tier = evaluation.tier_results.get(criterion.id, TierLevel.VETO)
            
            # Convert tier to score
            tier_score = {
                TierLevel.IDEAL: 1.0,
                TierLevel.ACCEPTABLE: 0.7,
                TierLevel.VETO: 0.0,
            }.get(tier, 0.0)
            
            # Get weight (AHP or equal)
            weight = profile.ahp_weights.get(criterion.id, 1.0 / len(profile.criteria))
            
            total_weighted += tier_score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return total_weighted / total_weight
    
    def _sort_lexicographic(
        self,
        evaluations: List[JointEvaluation],
    ) -> List[JointEvaluation]:
        """
        Sort evaluations lexicographically by first violation priority.
        
        Apartments are sorted by:
        1. Whether they have any veto (non-veto first)
        2. Priority order of first violation (higher priority = later violation = better)
        3. Total violation count (fewer = better)
        4. Joint satisfaction score (higher = better)
        
        Args:
            evaluations: List of joint evaluations.
            
        Returns:
            Sorted list.
        """
        def sort_key(e: JointEvaluation) -> Tuple:
            # Aggregate first breach priorities across people
            first_breaches = []
            for individual in e.individual_evaluations.values():
                if individual.first_violation:
                    first_breaches.append(individual.first_violation.priority_order)
            
            # Best case: no breaches → priority 999 (sorts last = best)
            # Worst case: breach at priority 1 → sorts first = worst
            worst_breach = min(first_breaches) if first_breaches else 999
            
            return (
                e.any_veto,  # False (0) < True (1), so non-veto sorts first
                -worst_breach,  # Negate so higher priority sorts later (better)
                e.joint_violation_count,  # Fewer violations = better
                -e.joint_satisfaction_score,  # Higher score = better
            )
        
        return sorted(evaluations, key=sort_key)
    
    def _build_satisfaction_matrix(
        self,
        joint: JointEvaluation,
    ) -> Dict[str, Dict[str, bool]]:
        """
        Build matrix of criterion satisfaction across all people.
        
        Args:
            joint: Joint evaluation.
            
        Returns:
            Dict mapping criterion_id → {person_name: satisfied_bool}
        """
        matrix = {}
        
        # Get all criteria across all profiles
        all_criteria = set()
        for profile in self.profiles.values():
            for criterion in profile.criteria:
                all_criteria.add(criterion.id)
        
        for criterion_id in all_criteria:
            matrix[criterion_id] = {}
            for person_name, individual in joint.individual_evaluations.items():
                tier = individual.tier_results.get(criterion_id)
                # Satisfied if ideal or acceptable (not veto)
                satisfied = tier in (TierLevel.IDEAL, TierLevel.ACCEPTABLE)
                matrix[criterion_id][person_name] = satisfied
        
        return matrix


class ComparisonEngine:
    """
    Engine for comparing apartments and understanding trade-offs.
    """
    
    def __init__(self, evaluator: PreferenceEvaluator):
        """
        Initialize comparison engine.
        
        Args:
            evaluator: PreferenceEvaluator with loaded profiles.
        """
        self.evaluator = evaluator
    
    def compare_two(
        self,
        eval_a: JointEvaluation,
        eval_b: JointEvaluation,
    ) -> Dict[str, Any]:
        """
        Compare two apartments head-to-head.
        
        Args:
            eval_a: First apartment evaluation.
            eval_b: Second apartment evaluation.
            
        Returns:
            Comparison summary with advantages/disadvantages.
        """
        comparison = {
            "apartment_a": eval_a.apartment_id,
            "apartment_b": eval_b.apartment_id,
            "a_advantages": [],
            "b_advantages": [],
            "ties": [],
            "recommendation": None,
        }
        
        # Compare per-person evaluations
        for person_name in eval_a.individual_evaluations:
            if person_name not in eval_b.individual_evaluations:
                continue
            
            ind_a = eval_a.individual_evaluations[person_name]
            ind_b = eval_b.individual_evaluations[person_name]
            
            # Compare each criterion
            all_criteria = set(ind_a.tier_results.keys()) | set(ind_b.tier_results.keys())
            
            for criterion_id in all_criteria:
                tier_a = ind_a.tier_results.get(criterion_id, TierLevel.VETO)
                tier_b = ind_b.tier_results.get(criterion_id, TierLevel.VETO)
                
                tier_rank = {TierLevel.IDEAL: 0, TierLevel.ACCEPTABLE: 1, TierLevel.VETO: 2}
                
                if tier_rank[tier_a] < tier_rank[tier_b]:
                    comparison["a_advantages"].append({
                        "criterion": criterion_id,
                        "person": person_name,
                        "a_tier": tier_a.value,
                        "b_tier": tier_b.value,
                    })
                elif tier_rank[tier_b] < tier_rank[tier_a]:
                    comparison["b_advantages"].append({
                        "criterion": criterion_id,
                        "person": person_name,
                        "a_tier": tier_a.value,
                        "b_tier": tier_b.value,
                    })
                else:
                    comparison["ties"].append({
                        "criterion": criterion_id,
                        "person": person_name,
                        "tier": tier_a.value,
                    })
        
        # Determine recommendation
        a_score = eval_a.joint_satisfaction_score
        b_score = eval_b.joint_satisfaction_score
        a_vetoes = eval_a.joint_veto_count
        b_vetoes = eval_b.joint_veto_count
        
        if a_vetoes < b_vetoes:
            comparison["recommendation"] = f"Apartment A ({eval_a.apartment_id}) - fewer veto violations"
        elif b_vetoes < a_vetoes:
            comparison["recommendation"] = f"Apartment B ({eval_b.apartment_id}) - fewer veto violations"
        elif a_score > b_score:
            comparison["recommendation"] = f"Apartment A ({eval_a.apartment_id}) - higher satisfaction score"
        elif b_score > a_score:
            comparison["recommendation"] = f"Apartment B ({eval_b.apartment_id}) - higher satisfaction score"
        else:
            comparison["recommendation"] = "Tie - apartments are roughly equivalent"
        
        return comparison
    
    def find_pareto_optimal(
        self,
        evaluations: List[JointEvaluation],
    ) -> List[JointEvaluation]:
        """
        Find Pareto-optimal apartments (not dominated by any other).
        
        An apartment is Pareto-optimal if no other apartment is:
        - Better in at least one person's evaluation
        - AND not worse in any person's evaluation
        
        Args:
            evaluations: List of joint evaluations.
            
        Returns:
            List of Pareto-optimal apartments.
        """
        pareto = []
        
        for candidate in evaluations:
            is_dominated = False
            
            for other in evaluations:
                if other.apartment_id == candidate.apartment_id:
                    continue
                
                # Check if other dominates candidate
                if self._dominates(other, candidate):
                    is_dominated = True
                    break
            
            if not is_dominated:
                pareto.append(candidate)
        
        return pareto
    
    def _dominates(
        self,
        a: JointEvaluation,
        b: JointEvaluation,
    ) -> bool:
        """
        Check if apartment A dominates apartment B.
        
        A dominates B if A is at least as good as B for all people,
        and strictly better for at least one person.
        
        Args:
            a: First apartment.
            b: Second apartment.
            
        Returns:
            True if A dominates B.
        """
        at_least_as_good = True
        strictly_better = False
        
        for person_name in a.individual_evaluations:
            if person_name not in b.individual_evaluations:
                continue
            
            score_a = a.individual_evaluations[person_name].tie_break_score
            score_b = b.individual_evaluations[person_name].tie_break_score
            
            if score_a < score_b:
                at_least_as_good = False
                break
            elif score_a > score_b:
                strictly_better = True
        
        return at_least_as_good and strictly_better





