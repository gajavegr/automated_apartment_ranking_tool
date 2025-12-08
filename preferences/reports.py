"""
Reporting and visualization for preference-based evaluations.

Provides human-readable reports, comparison tables, and data exports
for apartment evaluation results.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
from datetime import datetime

from .schemas import (
    JointEvaluation,
    ApartmentEvaluation,
    PreferenceProfile,
    TierLevel,
)


class EvaluationReporter:
    """
    Generates reports and visualizations for evaluation results.
    """
    
    def __init__(
        self,
        profiles: Dict[str, PreferenceProfile],
        evaluations: List[JointEvaluation],
    ):
        """
        Initialize reporter.
        
        Args:
            profiles: Dictionary of preference profiles by person name.
            evaluations: List of joint apartment evaluations.
        """
        self.profiles = profiles
        self.evaluations = evaluations
    
    def generate_summary_table(self) -> str:
        """
        Generate a summary table of all apartments.
        
        Returns:
            Formatted table string.
        """
        lines = []
        
        # Header
        person_names = list(self.profiles.keys())
        header = ["Rank", "Apartment"] + [f"{p} Score" for p in person_names] + [
            "Joint Score", "Vetoes", "Status"
        ]
        lines.append(" | ".join(f"{h:^15}" for h in header))
        lines.append("-" * (17 * len(header)))
        
        # Sort by rank
        sorted_evals = sorted(self.evaluations, key=lambda e: e.rank or 999)
        
        for evaluation in sorted_evals:
            row = [
                str(evaluation.rank or "-"),
                evaluation.apartment_id[:12] + "..." if len(evaluation.apartment_id) > 15 else evaluation.apartment_id,
            ]
            
            # Individual scores
            for person in person_names:
                if person in evaluation.individual_evaluations:
                    score = evaluation.individual_evaluations[person].tie_break_score
                    row.append(f"{score:.2f}")
                else:
                    row.append("-")
            
            # Joint metrics
            row.append(f"{evaluation.joint_satisfaction_score:.2f}")
            row.append(str(evaluation.joint_veto_count))
            row.append("✗ VETO" if evaluation.any_veto else "✓ OK")
            
            lines.append(" | ".join(f"{c:^15}" for c in row))
        
        return "\n".join(lines)
    
    def generate_apartment_detail(
        self,
        evaluation: JointEvaluation,
        apartment_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate detailed report for one apartment.
        
        Args:
            evaluation: Joint evaluation for the apartment.
            apartment_data: Optional raw apartment data for additional context.
            
        Returns:
            Formatted detail report.
        """
        lines = []
        
        lines.append("=" * 70)
        lines.append(f"APARTMENT: {evaluation.apartment_id}")
        lines.append(f"Overall Status: {'✗ HAS VETO VIOLATIONS' if evaluation.any_veto else '✓ PASSES ALL CHECKS'}")
        lines.append(f"Joint Satisfaction Score: {evaluation.joint_satisfaction_score:.2f}")
        lines.append(f"Rank: #{evaluation.rank}")
        lines.append("=" * 70)
        
        # Individual evaluations
        for person_name, individual in evaluation.individual_evaluations.items():
            lines.append("")
            lines.append(f"--- {person_name}'s Evaluation ---")
            lines.append(f"Score: {individual.tie_break_score:.2f}")
            lines.append(f"Ideal: {individual.ideal_count} | Acceptable: {individual.acceptable_count} | Veto: {individual.veto_count}")
            
            if individual.first_violation:
                v = individual.first_violation
                lines.append(f"First Violation: {v.criterion_name} (Priority {v.priority_order})")
            
            lines.append("")
            lines.append("Criteria Breakdown:")
            
            # Get profile for priority info
            profile = self.profiles.get(person_name)
            if profile:
                sorted_criteria = profile.get_criteria_by_priority()
                for criterion in sorted_criteria:
                    tier = individual.tier_results.get(criterion.id, TierLevel.VETO)
                    explanation = individual.explanations.get(criterion.id, "")
                    
                    tier_symbol = {
                        TierLevel.IDEAL: "✓ IDEAL",
                        TierLevel.ACCEPTABLE: "~ ACCEPTABLE",
                        TierLevel.VETO: "✗ VETO",
                    }.get(tier, "?")
                    
                    lines.append(f"  [{criterion.priority_order}] {criterion.display_name}: {tier_symbol}")
                    if explanation:
                        lines.append(f"      {explanation}")
        
        # Disagreements
        disagreements = evaluation.get_disagreements()
        if disagreements:
            lines.append("")
            lines.append("--- Areas of Disagreement ---")
            for d in disagreements:
                tiers_str = ", ".join(f"{p}: {t}" for p, t in d["tiers_by_person"].items())
                lines.append(f"  {d['criterion_id']}: {tiers_str}")
        
        # Raw data if provided
        if apartment_data:
            lines.append("")
            lines.append("--- Key Attributes ---")
            key_fields = [
                "price", "sqft", "bedrooms", "bathrooms",
                "commute_time_you", "commute_time_partner",
                "combined_safety", "gym_walk_time_mins",
                "parking_score", "laundry_type",
            ]
            for field in key_fields:
                if field in apartment_data and apartment_data[field]:
                    lines.append(f"  {field}: {apartment_data[field]}")
        
        return "\n".join(lines)
    
    def generate_violation_report(self) -> str:
        """
        Generate report focused on violations across all apartments.
        
        Returns:
            Formatted violation report.
        """
        lines = []
        lines.append("VIOLATION ANALYSIS REPORT")
        lines.append("=" * 70)
        
        # Collect violation statistics
        violation_counts: Dict[str, Dict[str, int]] = {}
        person_violation_counts: Dict[str, int] = {}
        
        for evaluation in self.evaluations:
            for person_name, individual in evaluation.individual_evaluations.items():
                if person_name not in person_violation_counts:
                    person_violation_counts[person_name] = 0
                person_violation_counts[person_name] += len(individual.all_violations)
                
                for v in individual.all_violations:
                    key = f"{v.criterion_id}:{v.field}"
                    if key not in violation_counts:
                        violation_counts[key] = {"count": 0, "people": set()}
                    violation_counts[key]["count"] += 1
                    violation_counts[key]["people"].add(person_name)
        
        # Most common violations
        lines.append("")
        lines.append("Most Common Violations (across all apartments):")
        sorted_violations = sorted(
            violation_counts.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        for key, stats in sorted_violations[:10]:
            criterion_id, field = key.split(":", 1)
            people = ", ".join(stats["people"])
            lines.append(f"  {criterion_id}/{field}: {stats['count']} violations ({people})")
        
        # Per-person summary
        lines.append("")
        lines.append("Violations by Person:")
        for person, count in person_violation_counts.items():
            lines.append(f"  {person}: {count} total violations")
        
        # Apartments with most violations
        lines.append("")
        lines.append("Apartments with Most Violations:")
        sorted_evals = sorted(
            self.evaluations,
            key=lambda e: e.joint_violation_count,
            reverse=True
        )
        for evaluation in sorted_evals[:5]:
            lines.append(f"  {evaluation.apartment_id}: {evaluation.joint_violation_count} violations")
        
        return "\n".join(lines)
    
    def generate_comparison_matrix(self) -> str:
        """
        Generate matrix showing which criteria are satisfied for each apartment.
        
        Returns:
            Formatted matrix string.
        """
        lines = []
        lines.append("CRITERIA SATISFACTION MATRIX")
        lines.append("Legend: ✓ = Ideal, ~ = Acceptable, ✗ = Veto, ? = Unknown")
        lines.append("=" * 70)
        
        # Get all criteria
        all_criteria = []
        for profile in self.profiles.values():
            for criterion in profile.criteria:
                if criterion.id not in [c.id for c in all_criteria]:
                    all_criteria.append(criterion)
        
        # Sort by priority (use first profile's priority)
        first_profile = next(iter(self.profiles.values()), None)
        if first_profile:
            priority_map = {c.id: c.priority_order for c in first_profile.criteria}
            all_criteria.sort(key=lambda c: priority_map.get(c.id, 999))
        
        # Header
        header = ["Apartment"] + [c.id[:8] for c in all_criteria]
        lines.append(" | ".join(f"{h:^10}" for h in header))
        lines.append("-" * (12 * len(header)))
        
        # Rows
        for evaluation in self.evaluations:
            row = [evaluation.apartment_id[:10]]
            
            for criterion in all_criteria:
                # Aggregate across all people
                tiers = []
                for individual in evaluation.individual_evaluations.values():
                    tier = individual.tier_results.get(criterion.id)
                    if tier:
                        tiers.append(tier)
                
                if not tiers:
                    row.append("?")
                elif all(t == TierLevel.IDEAL for t in tiers):
                    row.append("✓")
                elif any(t == TierLevel.VETO for t in tiers):
                    row.append("✗")
                else:
                    row.append("~")
            
            lines.append(" | ".join(f"{c:^10}" for c in row))
        
        return "\n".join(lines)
    
    def export_json(self, path: Path) -> None:
        """
        Export all evaluations to JSON file.
        
        Args:
            path: Output file path.
        """
        data = {
            "generated_at": datetime.now().isoformat(),
            "profiles": {name: p.to_dict() for name, p in self.profiles.items()},
            "evaluations": [e.to_dict() for e in self.evaluations],
            "summary": {
                "total_apartments": len(self.evaluations),
                "passing_apartments": sum(1 for e in self.evaluations if not e.any_veto),
                "vetoed_apartments": sum(1 for e in self.evaluations if e.any_veto),
            },
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    
    def export_csv(self, path: Path) -> None:
        """
        Export summary to CSV file.
        
        Args:
            path: Output file path.
        """
        import csv
        
        person_names = list(self.profiles.keys())
        
        headers = [
            "rank",
            "apartment_id",
            "joint_score",
            "joint_vetoes",
            "status",
        ] + [f"{p}_score" for p in person_names] + [f"{p}_vetoes" for p in person_names]
        
        rows = []
        for evaluation in sorted(self.evaluations, key=lambda e: e.rank or 999):
            row = {
                "rank": evaluation.rank,
                "apartment_id": evaluation.apartment_id,
                "joint_score": round(evaluation.joint_satisfaction_score, 3),
                "joint_vetoes": evaluation.joint_veto_count,
                "status": "VETO" if evaluation.any_veto else "OK",
            }
            
            for person in person_names:
                if person in evaluation.individual_evaluations:
                    ind = evaluation.individual_evaluations[person]
                    row[f"{person}_score"] = round(ind.tie_break_score, 3)
                    row[f"{person}_vetoes"] = ind.veto_count
                else:
                    row[f"{person}_score"] = ""
                    row[f"{person}_vetoes"] = ""
            
            rows.append(row)
        
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
    
    def generate_tour_shortlist(
        self,
        max_apartments: int = 10,
        include_reasons: bool = True,
    ) -> str:
        """
        Generate a shortlist of apartments to tour with reasons.
        
        Args:
            max_apartments: Maximum number of apartments to include.
            include_reasons: Include explanation for why each was selected.
            
        Returns:
            Formatted shortlist.
        """
        lines = []
        lines.append("APARTMENT TOUR SHORTLIST")
        lines.append("=" * 70)
        
        # Filter to non-veto apartments, sorted by rank
        passing = [e for e in self.evaluations if not e.any_veto]
        passing.sort(key=lambda e: e.rank or 999)
        
        if not passing:
            lines.append("")
            lines.append("No apartments pass all veto criteria!")
            lines.append("Consider relaxing some requirements.")
            
            # Show best vetoed apartments
            vetoed = [e for e in self.evaluations if e.any_veto]
            vetoed.sort(key=lambda e: e.joint_veto_count)
            
            if vetoed:
                lines.append("")
                lines.append("Apartments with fewest veto violations:")
                for i, evaluation in enumerate(vetoed[:5], 1):
                    lines.append(f"  {i}. {evaluation.apartment_id} ({evaluation.joint_veto_count} vetoes)")
            
            return "\n".join(lines)
        
        lines.append(f"Found {len(passing)} apartments meeting all criteria.")
        lines.append(f"Showing top {min(max_apartments, len(passing))}:")
        lines.append("")
        
        for i, evaluation in enumerate(passing[:max_apartments], 1):
            lines.append(f"{i}. {evaluation.apartment_id}")
            lines.append(f"   Joint Score: {evaluation.joint_satisfaction_score:.2f}")
            
            if include_reasons:
                # Summarize key strengths
                strengths = []
                for person_name, individual in evaluation.individual_evaluations.items():
                    ideal_criteria = [
                        cid for cid, tier in individual.tier_results.items()
                        if tier == TierLevel.IDEAL
                    ]
                    if ideal_criteria:
                        strengths.append(f"{person_name}: {len(ideal_criteria)} ideal criteria")
                
                if strengths:
                    lines.append(f"   Strengths: {'; '.join(strengths)}")
                
                # Note any acceptable (not ideal) criteria
                acceptable_notes = []
                for person_name, individual in evaluation.individual_evaluations.items():
                    acceptable_criteria = [
                        cid for cid, tier in individual.tier_results.items()
                        if tier == TierLevel.ACCEPTABLE
                    ]
                    if acceptable_criteria:
                        acceptable_notes.append(
                            f"{person_name}: {', '.join(acceptable_criteria[:3])} acceptable"
                        )
                
                if acceptable_notes:
                    lines.append(f"   Note: {'; '.join(acceptable_notes)}")
            
            lines.append("")
        
        return "\n".join(lines)


    def generate_text_report(self) -> str:
        """
        Generate a complete text report.
        
        Returns:
            Full text report.
        """
        sections = [
            self.generate_summary_table(),
            "",
            self.generate_violation_report(),
            "",
            self.generate_tour_shortlist(),
        ]
        return "\n\n".join(sections)
    
    def generate_markdown_report(self) -> str:
        """
        Generate a markdown-formatted report.
        
        Returns:
            Markdown report string.
        """
        lines = []
        
        lines.append("# Preference Evaluation Report")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        lines.append("")
        
        # Summary
        passing = sum(1 for e in self.evaluations if not e.any_veto)
        vetoed = len(self.evaluations) - passing
        
        lines.append("## Summary")
        lines.append(f"- **Total Apartments:** {len(self.evaluations)}")
        lines.append(f"- **Passing (No Vetoes):** {passing}")
        lines.append(f"- **Vetoed:** {vetoed}")
        lines.append(f"- **Profiles Used:** {', '.join(self.profiles.keys())}")
        lines.append("")
        
        # Shortlist
        lines.append("## Tour Shortlist")
        shortlist = [e for e in self.evaluations if not e.any_veto]
        shortlist.sort(key=lambda e: e.rank or 999)
        
        if shortlist:
            lines.append("| Rank | Apartment | Joint Score | Status |")
            lines.append("|------|-----------|-------------|--------|")
            for e in shortlist[:10]:
                lines.append(
                    f"| {e.rank} | {e.apartment_id} | "
                    f"{e.joint_satisfaction_score:.2f} | ✓ OK |"
                )
        else:
            lines.append("*No apartments pass all veto criteria.*")
        lines.append("")
        
        # Full results
        lines.append("## All Results")
        lines.append("| Rank | Apartment | Score | Vetoes | Status |")
        lines.append("|------|-----------|-------|--------|--------|")
        for e in sorted(self.evaluations, key=lambda x: x.rank or 999):
            status = "✗ VETO" if e.any_veto else "✓ OK"
            lines.append(
                f"| {e.rank or '-'} | {e.apartment_id} | "
                f"{e.joint_satisfaction_score:.2f} | {e.joint_veto_count} | {status} |"
            )
        
        return "\n".join(lines)


def format_tier_badge(tier: TierLevel) -> str:
    """Format tier as colored badge (for terminals supporting ANSI)."""
    colors = {
        TierLevel.IDEAL: "\033[92m",      # Green
        TierLevel.ACCEPTABLE: "\033[93m",  # Yellow
        TierLevel.VETO: "\033[91m",        # Red
    }
    reset = "\033[0m"
    
    return f"{colors.get(tier, '')}{tier.value.upper()}{reset}"


def format_score_bar(score: float, width: int = 20) -> str:
    """Format score as ASCII progress bar."""
    filled = int(score * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {score:.0%}"




