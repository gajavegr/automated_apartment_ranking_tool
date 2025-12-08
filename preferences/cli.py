"""
Command-line interface for preference-based apartment evaluation.

Provides commands for:
- Taking the preference quiz
- Evaluating apartments against profiles
- Generating reports and shortlists
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

from .schemas import PreferenceProfile, JointEvaluation
from .evaluation_engine import PreferenceEvaluator, ComparisonEngine
from .quiz import PreferenceQuiz, PreferenceStrength, create_default_profile
from .reports import EvaluationReporter


def run_quiz_interactive(person_name: str, output_path: Path) -> PreferenceProfile:
    """
    Run the preference quiz interactively in the terminal.
    
    Args:
        person_name: Name of the person taking the quiz.
        output_path: Path to save the resulting profile.
        
    Returns:
        Generated PreferenceProfile.
    """
    print(f"\n{'='*60}")
    print(f"PREFERENCE QUIZ FOR: {person_name}")
    print(f"{'='*60}\n")
    
    quiz = PreferenceQuiz(person_name)
    
    # Phase 1: Priority Ranking
    print("PHASE 1: Priority Ranking")
    print("-" * 40)
    print("Rank these criteria from most important (1) to least important.")
    print("Enter numbers separated by commas (e.g., 1,3,5,2,4,6,7,8,9)\n")
    
    for i, cid in enumerate(quiz.criteria_ids, 1):
        print(f"  {i}. {cid.replace('_', ' ').title()}")
    
    print()
    while True:
        try:
            ranking_input = input("Your ranking: ").strip()
            indices = [int(x.strip()) - 1 for x in ranking_input.split(",")]
            if len(set(indices)) != len(quiz.criteria_ids):
                print("Please rank all criteria exactly once.")
                continue
            if any(i < 0 or i >= len(quiz.criteria_ids) for i in indices):
                print("Invalid criterion number.")
                continue
            ranking = [quiz.criteria_ids[i] for i in indices]
            break
        except (ValueError, IndexError):
            print("Invalid input. Enter numbers separated by commas.")
    
    quiz.record_priority_ranking(ranking)
    print(f"\nRecorded priority: {' > '.join(ranking)}\n")
    
    # Phase 2: Threshold Questions
    print("\nPHASE 2: Threshold Values")
    print("-" * 40)
    print("For each criterion, specify your ideal, acceptable, and veto thresholds.\n")
    
    for question in quiz.threshold_questions:
        print(f"\n{question.question}")
        print(f"  Range: {question.min_value} - {question.max_value} {question.unit}")
        print(f"  (Defaults: ideal={question.default_ideal}, acceptable={question.default_acceptable}, veto={question.default_veto})")
        
        def get_value(prompt: str, default: float) -> float:
            while True:
                try:
                    val = input(f"  {prompt} [{default}]: ").strip()
                    if not val:
                        return default
                    return float(val)
                except ValueError:
                    print("  Invalid number, try again.")
        
        ideal = get_value("Ideal", question.default_ideal)
        acceptable = get_value("Acceptable", question.default_acceptable)
        veto = get_value("Veto (deal-breaker)", question.default_veto)
        
        quiz.record_threshold_response(question.id, ideal, acceptable, veto)
    
    # Phase 3: Pairwise Comparisons
    print("\n\nPHASE 3: Trade-off Scenarios")
    print("-" * 40)
    print("For each scenario, indicate your preference strength.\n")
    print("Options:")
    print("  1 = Strongly prefer A")
    print("  2 = Moderately prefer A")
    print("  3 = Slightly prefer A")
    print("  4 = Weakly prefer A")
    print("  5 = Equal / No preference")
    print("  6 = Weakly prefer B")
    print("  7 = Slightly prefer B")
    print("  8 = Moderately prefer B")
    print("  9 = Strongly prefer B")
    
    strength_map = {
        "1": PreferenceStrength.STRONGLY_PREFER_A,
        "2": PreferenceStrength.MODERATELY_PREFER_A,
        "3": PreferenceStrength.SLIGHTLY_PREFER_A,
        "4": PreferenceStrength.WEAKLY_PREFER_A,
        "5": PreferenceStrength.EQUAL,
        "6": PreferenceStrength.WEAKLY_PREFER_B,
        "7": PreferenceStrength.SLIGHTLY_PREFER_B,
        "8": PreferenceStrength.MODERATELY_PREFER_B,
        "9": PreferenceStrength.STRONGLY_PREFER_B,
    }
    
    scenarios = quiz.get_pairwise_scenarios(shuffle=True)
    for scenario in scenarios:
        print(f"\n{'='*50}")
        print(f"Scenario: {scenario.description}")
        if scenario.context:
            print(f"Context: {scenario.context}")
        print()
        print(f"  Option A ({scenario.criterion_a}):")
        print(f"    {scenario.option_a_description}")
        print()
        print(f"  Option B ({scenario.criterion_b}):")
        print(f"    {scenario.option_b_description}")
        print()
        
        while True:
            choice = input("Your preference (1-9): ").strip()
            if choice in strength_map:
                quiz.record_pairwise_response(scenario.id, strength_map[choice])
                break
            print("Invalid input. Enter 1-9.")
    
    # Check consistency
    weights, consistency = quiz.calculate_ahp_weights()
    print(f"\n{'='*50}")
    print(f"RESULTS")
    print(f"{'='*50}")
    print(f"\nConsistency Ratio: {consistency:.3f}")
    
    if consistency > 0.1:
        print("⚠️  Your responses show some inconsistency.")
        print("Consider revisiting these comparisons:")
        for scenario in quiz.get_inconsistent_comparisons():
            print(f"  - {scenario.criterion_a} vs {scenario.criterion_b}")
    else:
        print("✓ Your responses are consistent.")
    
    print("\nDerived Weights:")
    for cid, weight in sorted(weights.items(), key=lambda x: -x[1]):
        print(f"  {cid}: {weight:.1%}")
    
    # Build and save profile
    profile = quiz.build_profile()
    profile.save(output_path)
    print(f"\n✓ Profile saved to: {output_path}")
    
    return profile


def evaluate_apartments(
    profile_paths: List[Path],
    apartments_path: Path,
    output_path: Optional[Path] = None,
    max_vetoes: int = 0,
    top_n: int = 10,
) -> List[JointEvaluation]:
    """
    Evaluate apartments against preference profiles.
    
    Args:
        profile_paths: Paths to preference profile YAML files.
        apartments_path: Path to apartments JSON file.
        output_path: Optional path to save results.
        max_vetoes: Maximum veto violations to include in shortlist.
        top_n: Number of top apartments to show.
        
    Returns:
        List of JointEvaluation results.
    """
    # Load profiles
    profiles = {}
    for path in profile_paths:
        profile = PreferenceProfile.load(path)
        profiles[profile.person_name] = profile
    
    # Load apartments
    with open(apartments_path) as f:
        apartments = json.load(f)
    
    if not isinstance(apartments, list):
        apartments = [apartments]
    
    # Create evaluator and evaluate
    evaluator = PreferenceEvaluator(profiles)
    evaluations = evaluator.evaluate_all_apartments(apartments)
    
    # Rank and filter
    ranked = evaluator.rank_apartments(evaluations, sort_by="veto_first")
    shortlist = evaluator.get_shortlist(ranked, max_vetoes=max_vetoes, top_n=top_n)
    
    # Generate reports
    reporter = EvaluationReporter(profiles, ranked)
    
    print("\n" + reporter.generate_summary_table())
    print("\n" + reporter.generate_tour_shortlist(max_apartments=top_n))
    
    # Save results if output path provided
    if output_path:
        reporter.export_json(output_path)
        print(f"\n✓ Results saved to: {output_path}")
    
    return shortlist


def compare_apartments(
    profile_paths: List[Path],
    apartments_path: Path,
    apt_a_id: str,
    apt_b_id: str,
) -> None:
    """
    Compare two specific apartments head-to-head.
    
    Args:
        profile_paths: Paths to preference profile YAML files.
        apartments_path: Path to apartments JSON file.
        apt_a_id: ID of first apartment.
        apt_b_id: ID of second apartment.
    """
    # Load profiles
    profiles = {}
    for path in profile_paths:
        profile = PreferenceProfile.load(path)
        profiles[profile.person_name] = profile
    
    # Load apartments
    with open(apartments_path) as f:
        apartments = json.load(f)
    
    if not isinstance(apartments, list):
        apartments = [apartments]
    
    # Find the two apartments
    apt_a = next((a for a in apartments if a.get("apartment_id") == apt_a_id), None)
    apt_b = next((a for a in apartments if a.get("apartment_id") == apt_b_id), None)
    
    if not apt_a:
        print(f"Apartment not found: {apt_a_id}")
        return
    if not apt_b:
        print(f"Apartment not found: {apt_b_id}")
        return
    
    # Evaluate
    evaluator = PreferenceEvaluator(profiles)
    eval_a = evaluator.evaluate_joint(apt_a_id, apt_a)
    eval_b = evaluator.evaluate_joint(apt_b_id, apt_b)
    
    # Compare
    engine = ComparisonEngine(evaluator)
    comparison = engine.compare_two(eval_a, eval_b)
    
    # Display
    print(f"\n{'='*60}")
    print(f"HEAD-TO-HEAD COMPARISON")
    print(f"{'='*60}")
    print(f"\nApartment A: {apt_a_id}")
    print(f"Apartment B: {apt_b_id}")
    
    print(f"\n--- Apartment A Advantages ---")
    for adv in comparison["a_advantages"]:
        print(f"  {adv['criterion']} ({adv['person']}): {adv['a_tier']} vs {adv['b_tier']}")
    
    print(f"\n--- Apartment B Advantages ---")
    for adv in comparison["b_advantages"]:
        print(f"  {adv['criterion']} ({adv['person']}): {adv['b_tier']} vs {adv['a_tier']}")
    
    print(f"\n--- Ties ---")
    for tie in comparison["ties"][:5]:
        print(f"  {tie['criterion']} ({tie['person']}): both {tie['tier']}")
    if len(comparison["ties"]) > 5:
        print(f"  ... and {len(comparison['ties']) - 5} more")
    
    print(f"\n>>> RECOMMENDATION: {comparison['recommendation']}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Preference-based apartment evaluation system"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Quiz command
    quiz_parser = subparsers.add_parser("quiz", help="Take the preference quiz")
    quiz_parser.add_argument("name", help="Your name")
    quiz_parser.add_argument(
        "-o", "--output",
        default="preferences/profiles",
        help="Output directory for profile"
    )
    
    # Default profile command
    default_parser = subparsers.add_parser(
        "default-profile",
        help="Create a default profile to customize"
    )
    default_parser.add_argument("name", help="Person's name")
    default_parser.add_argument(
        "-o", "--output",
        default="preferences/profiles",
        help="Output directory for profile"
    )
    
    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate apartments")
    eval_parser.add_argument(
        "-p", "--profiles",
        nargs="+",
        required=True,
        help="Paths to preference profile YAML files"
    )
    eval_parser.add_argument(
        "-a", "--apartments",
        required=True,
        help="Path to apartments JSON file"
    )
    eval_parser.add_argument(
        "-o", "--output",
        help="Path to save results JSON"
    )
    eval_parser.add_argument(
        "--max-vetoes",
        type=int,
        default=0,
        help="Maximum veto violations for shortlist"
    )
    eval_parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of top apartments to show"
    )
    
    # Compare command
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two apartments head-to-head"
    )
    compare_parser.add_argument(
        "-p", "--profiles",
        nargs="+",
        required=True,
        help="Paths to preference profile YAML files"
    )
    compare_parser.add_argument(
        "-a", "--apartments",
        required=True,
        help="Path to apartments JSON file"
    )
    compare_parser.add_argument("apt_a", help="First apartment ID")
    compare_parser.add_argument("apt_b", help="Second apartment ID")
    
    args = parser.parse_args()
    
    if args.command == "quiz":
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{args.name.lower().replace(' ', '_')}.yaml"
        run_quiz_interactive(args.name, output_path)
    
    elif args.command == "default-profile":
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{args.name.lower().replace(' ', '_')}.yaml"
        
        profile = create_default_profile(args.name)
        profile.save(output_path)
        print(f"✓ Default profile created: {output_path}")
        print("Edit this file to customize thresholds, or run 'quiz' for guided setup.")
    
    elif args.command == "evaluate":
        profile_paths = [Path(p) for p in args.profiles]
        output_path = Path(args.output) if args.output else None
        
        evaluate_apartments(
            profile_paths,
            Path(args.apartments),
            output_path,
            max_vetoes=args.max_vetoes,
            top_n=args.top,
        )
    
    elif args.command == "compare":
        profile_paths = [Path(p) for p in args.profiles]
        compare_apartments(
            profile_paths,
            Path(args.apartments),
            args.apt_a,
            args.apt_b,
        )
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()





