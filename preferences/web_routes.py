"""
Flask routes for preference-based apartment evaluation.

Provides API endpoints for:
- Taking the preference quiz
- Managing preference profiles
- Running evaluations against apartments
- Generating reports and comparisons
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from flask import Blueprint, request, jsonify, render_template, current_app

from .schemas import PreferenceProfile, TierLevel
from .evaluation_engine import PreferenceEvaluator, ComparisonEngine
from .quiz import (
    PreferenceQuiz,
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

# Create blueprint
preferences_bp = Blueprint('preferences', __name__, url_prefix='/preferences')

# Profile storage directory
PROFILES_DIR = Path(__file__).parent / "profiles"


def get_profiles_dir() -> Path:
    """Get the profiles directory, creating if needed."""
    profiles_dir = PROFILES_DIR
    profiles_dir.mkdir(parents=True, exist_ok=True)
    return profiles_dir


def list_profiles() -> List[Dict[str, Any]]:
    """List all saved preference profiles."""
    profiles_dir = get_profiles_dir()
    profiles = []
    
    for path in profiles_dir.glob("*.yaml"):
        try:
            profile = PreferenceProfile.load(path)
            profiles.append({
                "name": profile.person_name,
                "filename": path.name,
                "filename_stem": path.stem,  # Filename without extension for lookup
                "version": profile.version,
                "criteria_count": len(profile.criteria),
                "updated_at": profile.updated_at,
                "ahp_consistency": profile.ahp_consistency_ratio,
            })
        except Exception as e:
            print(f"Error loading profile {path}: {e}")
    
    return profiles


@preferences_bp.route('/api/profiles', methods=['GET'])
def api_list_profiles():
    """List all preference profiles."""
    try:
        profiles = list_profiles()
        return jsonify({
            "success": True,
            "profiles": profiles,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def find_profile_path(name: str) -> Optional[Path]:
    """Find a profile by name, checking multiple naming patterns."""
    profiles_dir = get_profiles_dir()
    
    # Try exact match first (name used as filename)
    candidates = [
        f"{name.lower().replace(' ', '_')}.yaml",
        f"{name}.yaml",
        f"sample_{name.lower().replace(' ', '_')}.yaml",
    ]
    
    for candidate in candidates:
        path = profiles_dir / candidate
        if path.exists():
            return path
    
    # Search all profiles for matching person_name
    for path in profiles_dir.glob("*.yaml"):
        try:
            profile = PreferenceProfile.load(path)
            if profile.person_name == name or profile.person_name.lower() == name.lower():
                return path
        except Exception:
            pass
    
    return None


def load_profiles_by_names(profile_names: List[str]) -> Dict[str, PreferenceProfile]:
    """Load multiple profiles by their names."""
    profiles = {}
    for name in profile_names:
        path = find_profile_path(name)
        if path:
            profile = PreferenceProfile.load(path)
            profiles[profile.person_name] = profile
    return profiles


@preferences_bp.route('/api/profiles/<name>', methods=['GET'])
def api_get_profile(name: str):
    """Get a specific preference profile."""
    try:
        path = find_profile_path(name)
        
        if not path:
            return jsonify({"success": False, "error": "Profile not found"}), 404
        
        profile = PreferenceProfile.load(path)
        return jsonify({
            "success": True,
            "profile": profile.to_dict(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@preferences_bp.route('/api/profiles/<name>', methods=['PUT'])
def api_save_profile(name: str):
    """Save/update a preference profile."""
    try:
        data = request.get_json()
        
        profiles_dir = get_profiles_dir()
        
        # Try to find existing profile
        existing_path = find_profile_path(name)
        
        if existing_path:
            profile = PreferenceProfile.load(existing_path)
            # Update fields from data
            if "criteria" in data:
                from .schemas import CriterionPreference
                profile.criteria = [
                    CriterionPreference.from_dict(c) for c in data["criteria"]
                ]
            if "ahp_weights" in data:
                profile.ahp_weights = data["ahp_weights"]
            if "ahp_consistency_ratio" in data:
                profile.ahp_consistency_ratio = data["ahp_consistency_ratio"]
            if "notes" in data:
                profile.notes = data["notes"]
            profile.version += 1
            profile.updated_at = datetime.now().isoformat()
            profile.save(existing_path)
        else:
            # New profile
            filename = f"{name.lower().replace(' ', '_')}.yaml"
            path = profiles_dir / filename
            profile = PreferenceProfile.from_dict({
                "person_name": name,
                **data
            })
            profile.save(path)
        
        return jsonify({
            "success": True,
            "message": f"Profile '{name}' saved",
            "version": profile.version,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@preferences_bp.route('/api/profiles/<name>', methods=['DELETE'])
def api_delete_profile(name: str):
    """Delete a preference profile."""
    try:
        path = find_profile_path(name)
        
        if path:
            path.unlink()
            return jsonify({"success": True, "message": f"Profile '{name}' deleted"})
        else:
            return jsonify({"success": False, "error": "Profile not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@preferences_bp.route('/api/profiles/create-default', methods=['POST'])
def api_create_default_profile():
    """Create a default profile for a person."""
    try:
        data = request.get_json()
        name = data.get("name")
        priorities = data.get("priorities")  # Optional priority ordering
        
        if not name:
            return jsonify({"success": False, "error": "Name is required"}), 400
        
        profile = create_default_profile(name, priorities)
        
        profiles_dir = get_profiles_dir()
        filename = f"{name.lower().replace(' ', '_')}.yaml"
        path = profiles_dir / filename
        
        profile.save(path)
        
        return jsonify({
            "success": True,
            "message": f"Default profile created for '{name}'",
            "profile": profile.to_dict(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Quiz endpoints
@preferences_bp.route('/api/quiz/scenarios', methods=['GET'])
def api_get_quiz_scenarios():
    """Get all quiz scenarios for pairwise comparisons."""
    try:
        scenarios = []
        for s in SCENARIO_BANK:
            scenarios.append({
                "id": s.id,
                "criterion_a": s.criterion_a,
                "criterion_b": s.criterion_b,
                "description": s.description,
                "option_a_description": s.option_a_description,
                "option_b_description": s.option_b_description,
                "context": s.context,
            })
        
        return jsonify({
            "success": True,
            "scenarios": scenarios,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@preferences_bp.route('/api/quiz/threshold-questions', methods=['GET'])
def api_get_threshold_questions():
    """Get all threshold questions."""
    try:
        questions = []
        for q in THRESHOLD_QUESTIONS:
            questions.append({
                "id": q.id,
                "criterion_id": q.criterion_id,
                "field": q.field,
                "question": q.question,
                "unit": q.unit,
                "min_value": q.min_value,
                "max_value": q.max_value,
                "step": q.step,
                "default_ideal": q.default_ideal,
                "default_acceptable": q.default_acceptable,
                "default_veto": q.default_veto,
                "is_lower_better": q.is_lower_better,
            })
        
        return jsonify({
            "success": True,
            "questions": questions,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@preferences_bp.route('/api/quiz/submit', methods=['POST'])
def api_submit_quiz():
    """Submit quiz responses and generate profile."""
    try:
        data = request.get_json()
        
        person_name = data.get("person_name")
        priority_ranking = data.get("priority_ranking", [])
        pairwise_responses = data.get("pairwise_responses", {})
        threshold_responses = data.get("threshold_responses", {})
        
        if not person_name:
            return jsonify({"success": False, "error": "Person name is required"}), 400
        
        # Create quiz instance and populate responses
        quiz = PreferenceQuiz(person_name)
        
        # Record priority ranking
        if priority_ranking:
            quiz.record_priority_ranking(priority_ranking)
        
        # Record pairwise comparisons
        strength_map = {
            "STRONGLY_PREFER_A": PreferenceStrength.STRONGLY_PREFER_A,
            "MODERATELY_PREFER_A": PreferenceStrength.MODERATELY_PREFER_A,
            "SLIGHTLY_PREFER_A": PreferenceStrength.SLIGHTLY_PREFER_A,
            "WEAKLY_PREFER_A": PreferenceStrength.WEAKLY_PREFER_A,
            "EQUAL": PreferenceStrength.EQUAL,
            "WEAKLY_PREFER_B": PreferenceStrength.WEAKLY_PREFER_B,
            "SLIGHTLY_PREFER_B": PreferenceStrength.SLIGHTLY_PREFER_B,
            "MODERATELY_PREFER_B": PreferenceStrength.MODERATELY_PREFER_B,
            "STRONGLY_PREFER_B": PreferenceStrength.STRONGLY_PREFER_B,
        }
        
        for scenario_id, response in pairwise_responses.items():
            if response in strength_map:
                quiz.record_pairwise_response(scenario_id, strength_map[response])
        
        # Record threshold responses
        for question_id, values in threshold_responses.items():
            quiz.record_threshold_response(
                question_id,
                values.get("ideal", 0),
                values.get("acceptable", 0),
                values.get("veto", 0),
            )
        
        # Build and save profile
        profile = quiz.build_profile()
        
        profiles_dir = get_profiles_dir()
        filename = f"{person_name.lower().replace(' ', '_')}.yaml"
        path = profiles_dir / filename
        profile.save(path)
        
        # Calculate consistency info
        weights, consistency = quiz.calculate_ahp_weights()
        inconsistent_scenarios = quiz.get_inconsistent_comparisons()
        
        return jsonify({
            "success": True,
            "message": f"Profile created for '{person_name}'",
            "profile": profile.to_dict(),
            "ahp_weights": weights,
            "consistency_ratio": consistency,
            "is_consistent": consistency <= 0.1,
            "inconsistent_scenarios": [s.id for s in inconsistent_scenarios],
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# Evaluation endpoints
@preferences_bp.route('/api/evaluate', methods=['POST'])
def api_evaluate_apartments():
    """Evaluate apartments against preference profiles."""
    try:
        data = request.get_json()
        
        profile_names = data.get("profiles", [])
        apartments = data.get("apartments", [])
        max_vetoes = data.get("max_vetoes", 0)
        top_n = data.get("top_n", 20)
        
        if not profile_names:
            return jsonify({"success": False, "error": "At least one profile is required"}), 400
        
        if not apartments:
            return jsonify({"success": False, "error": "Apartments data is required"}), 400
        
        # Load profiles
        profiles = load_profiles_by_names(profile_names)
        
        if not profiles:
            return jsonify({"success": False, "error": "No valid profiles found"}), 400
        
        # Normalize apartments
        normalized = [normalize_apartment_data(apt) for apt in apartments]
        
        # Create evaluator and evaluate
        evaluator = PreferenceEvaluator(profiles)
        evaluations = evaluator.evaluate_all_apartments(normalized, id_field="apartment_id")
        ranked = evaluator.rank_apartments(evaluations, sort_by="veto_first")
        shortlist = evaluator.get_shortlist(ranked, max_vetoes=max_vetoes, top_n=top_n)
        
        # Generate summary (respect max vetoes in passing counts)
        summary = generate_preference_summary(ranked, profiles, max_vetoes=max_vetoes)
        
        # Serialize evaluations
        eval_results = [e.to_dict() for e in ranked]
        shortlist_results = [e.to_dict() for e in shortlist]
        
        return jsonify({
            "success": True,
            "evaluations": eval_results,
            "shortlist": shortlist_results,
            "summary": summary,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@preferences_bp.route('/api/evaluate-from-sheet', methods=['POST'])
def api_evaluate_from_sheet():
    """Evaluate apartments from Google Sheet against preference profiles."""
    try:
        # Import here to avoid circular imports
        from utils.google_sheets import GoogleSheetsClient
        import config
        
        data = request.get_json()
        profile_names = data.get("profiles", [])
        max_vetoes = data.get("max_vetoes", 0)
        top_n = data.get("top_n", 20)
        excluded_categories = data.get("excluded_categories", [])  # New parameter
        
        if not profile_names:
            return jsonify({"success": False, "error": "At least one profile is required"}), 400
        
        # Load profiles
        profiles = load_profiles_by_names(profile_names)
        
        if not profiles:
            return jsonify({"success": False, "error": "No valid profiles found"}), 400
        
        # Filter out excluded categories from profiles
        if excluded_categories:
            for profile in profiles.values():
                profile.criteria = [c for c in profile.criteria if c.id not in excluded_categories]
        
        # Read apartments from sheet
        sheets_client = GoogleSheetsClient()
        sheet_rows = sheets_client.read_main_sheet()
        
        if not sheet_rows:
            return jsonify({"success": False, "error": "No apartments found in sheet"}), 400
        
        # Filter out unavailable apartments
        availability_col = config.SHEET_COLUMNS.get("availability_status")
        available_rows = []
        for row in sheet_rows:
            # Include row if no availability status or if it's "Available"
            status = row.get(availability_col, "").strip().lower() if availability_col else ""
            if not status or status == "available":
                available_rows.append(row)
        
        # Normalize apartments
        normalized = [normalize_apartment_data(row) for row in available_rows]
        
        # Create evaluator and evaluate
        evaluator = PreferenceEvaluator(profiles)
        evaluations = evaluator.evaluate_all_apartments(normalized, id_field="apartment_id")
        ranked = evaluator.rank_apartments(evaluations, sort_by="veto_first")
        shortlist = evaluator.get_shortlist(ranked, max_vetoes=max_vetoes, top_n=top_n)
        
        # Generate summary
        summary = generate_preference_summary(ranked, profiles)
        
        # Serialize evaluations
        eval_results = [e.to_dict() for e in ranked]
        shortlist_results = [e.to_dict() for e in shortlist]
        
        return jsonify({
            "success": True,
            "total_apartments": len(sheet_rows),
            "available_apartments": len(available_rows),
            "unavailable_count": len(sheet_rows) - len(available_rows),
            "excluded_categories": excluded_categories,
            "evaluations": eval_results,
            "shortlist": shortlist_results,
            "summary": summary,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@preferences_bp.route('/api/compare', methods=['POST'])
def api_compare_apartments():
    """Compare two apartments head-to-head."""
    try:
        data = request.get_json()
        
        profile_names = data.get("profiles", [])
        apartment_a = data.get("apartment_a")
        apartment_b = data.get("apartment_b")
        
        if not profile_names:
            return jsonify({"success": False, "error": "At least one profile is required"}), 400
        
        if not apartment_a or not apartment_b:
            return jsonify({"success": False, "error": "Two apartments are required"}), 400
        
        # Load profiles
        profiles = load_profiles_by_names(profile_names)
        
        if not profiles:
            return jsonify({"success": False, "error": "No valid profiles found"}), 400
        
        # Normalize apartments
        norm_a = normalize_apartment_data(apartment_a)
        norm_b = normalize_apartment_data(apartment_b)
        
        # Evaluate
        evaluator = PreferenceEvaluator(profiles)
        eval_a = evaluator.evaluate_joint(norm_a.get("apartment_id", "A"), norm_a)
        eval_b = evaluator.evaluate_joint(norm_b.get("apartment_id", "B"), norm_b)
        
        # Compare
        engine = ComparisonEngine(evaluator)
        comparison = engine.compare_two(eval_a, eval_b)
        
        return jsonify({
            "success": True,
            "comparison": comparison,
            "eval_a": eval_a.to_dict(),
            "eval_b": eval_b.to_dict(),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@preferences_bp.route('/api/apartment/<apartment_id>/detail', methods=['POST'])
def api_apartment_detail(apartment_id: str):
    """Get detailed preference evaluation for a single apartment."""
    try:
        # Import here to avoid circular imports
        from utils.google_sheets import GoogleSheetsClient
        import config
        
        data = request.get_json()
        
        profile_names = data.get("profiles", [])
        apartment_data = data.get("apartment", {})
        
        if not profile_names:
            return jsonify({"success": False, "error": "At least one profile is required"}), 400
        
        # Load profiles
        profiles = load_profiles_by_names(profile_names)
        
        if not profiles:
            return jsonify({"success": False, "error": "No valid profiles found"}), 400
        
        # If apartment data is empty or minimal, try to load from sheet
        if not apartment_data or len(apartment_data) < 3:
            try:
                sheets_client = GoogleSheetsClient()
                sheet_rows = sheets_client.read_main_sheet()
                
                # Find the apartment by address
                address_col = config.SHEET_COLUMNS.get('address', 'Address')
                for row in sheet_rows:
                    row_address = row.get(address_col, '')
                    if row_address == apartment_id:
                        apartment_data = row
                        break
            except Exception as e:
                print(f"Warning: Could not load apartment from sheet: {e}")
        
        if not apartment_data:
            return jsonify({"success": False, "error": "Apartment data not found"}), 400
        
        # Normalize and evaluate
        normalized = normalize_apartment_data(apartment_data)
        evaluator = PreferenceEvaluator(profiles)
        evaluation = evaluator.evaluate_joint(apartment_id, normalized)
        
        # Generate detailed report
        reporter = EvaluationReporter(profiles, [evaluation])
        detail_text = reporter.generate_apartment_detail(evaluation, normalized)
        
        # Build threshold data for slider visualization
        threshold_data = _build_threshold_data(profiles, normalized)
        
        return jsonify({
            "success": True,
            "evaluation": evaluation.to_dict(),
            "detail_report": detail_text,
            "threshold_data": threshold_data,
            "apartment_values": _extract_apartment_values(normalized, profiles),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def _build_threshold_data(profiles: Dict[str, PreferenceProfile], apartment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build threshold data structure for slider visualization.
    
    Returns a dictionary mapping criterion_id to threshold info for all profiles.
    For commute criterion, uses profile-specific commute data fields.
    """
    from .schemas import resolve_field, CommuteMode
    
    threshold_data = {}
    
    # Collect all criteria across profiles
    all_criteria = {}
    for profile_name, profile in profiles.items():
        for criterion in profile.criteria:
            if criterion.id not in all_criteria:
                all_criteria[criterion.id] = {
                    "id": criterion.id,
                    "display_name": criterion.display_name,
                    "profiles": {},
                }
            
            # Get the field used for this criterion's thresholds
            # Assuming first threshold in each tier uses the main field
            field = None
            is_lower_better = True  # Default assumption
            
            if criterion.ideal:
                field = criterion.ideal[0].field
                # Check operator to determine if lower is better
                op = criterion.ideal[0].operator.value
                is_lower_better = op in ("lte", "lt")
            elif criterion.acceptable:
                field = criterion.acceptable[0].field
                op = criterion.acceptable[0].operator.value
                is_lower_better = op in ("lte", "lt")
            elif criterion.veto:
                field = criterion.veto[0].field
                op = criterion.veto[0].operator.value
                is_lower_better = op in ("lte", "lt")
            
            # Get threshold values
            ideal_val = criterion.ideal[0].value if criterion.ideal else None
            acceptable_val = criterion.acceptable[0].value if criterion.acceptable else None
            veto_val = criterion.veto[0].value if criterion.veto else None
            
            # Get actual value for this field
            # Special handling for commute: use profile's commute_config.data_field
            actual_val = None
            commute_extra = {}
            
            if criterion.id == "commute" and profile.commute_config:
                # Use profile-specific commute data field
                data_field = profile.commute_config.data_field
                actual_val = apartment_data.get(data_field)
                
                # Try alternative column names if not found
                if actual_val is None:
                    if data_field == "commute_time_partner":
                        actual_val = apartment_data.get("Commute Time (Partner)")
                    elif data_field == "commute_time_you":
                        actual_val = apartment_data.get("Commute Time (You)")
                        if actual_val is None:
                            actual_val = resolve_field(apartment_data, "commute_duration")
                
                # Add commute-specific extra data
                commute_mode = profile.commute_config.mode
                commute_extra = {
                    "commute_mode": commute_mode.value,
                    "data_field": data_field,
                }
                
                # Add annoyingness score based on mode
                if commute_mode == CommuteMode.TRANSIT:
                    transit_annoy = apartment_data.get("transit_annoyingness")
                    commute_extra["annoyingness_score"] = transit_annoy
                    commute_extra["transit_walking_mins"] = apartment_data.get("transit_walking_minutes")
                    commute_extra["transit_transfers"] = apartment_data.get("transit_transfers")
                else:
                    route_annoy = apartment_data.get("route_annoyingness")
                    commute_extra["annoyingness_score"] = route_annoy
                
                # Add commute score (overall quality)
                commute_extra["commute_score"] = apartment_data.get("commute_score")
            else:
                actual_val = resolve_field(apartment_data, field) if field else None
            
            profile_data = {
                "field": field,
                "ideal": ideal_val,
                "acceptable": acceptable_val,
                "veto": veto_val,
                "is_lower_better": is_lower_better,
                "actual_value": actual_val,
            }
            
            # Add commute-specific data if present
            if commute_extra:
                profile_data.update(commute_extra)
            
            all_criteria[criterion.id]["profiles"][profile_name] = profile_data
            
            # Store field info at criterion level for reference
            if "field" not in all_criteria[criterion.id]:
                all_criteria[criterion.id]["field"] = field
                all_criteria[criterion.id]["is_lower_better"] = is_lower_better
    
    return all_criteria


def _extract_apartment_values(apartment_data: Dict[str, Any], profiles: Dict[str, PreferenceProfile]) -> Dict[str, Any]:
    """
    Extract relevant apartment values for display in the modal.
    Includes profile-specific commute data.
    """
    from .schemas import resolve_field, CommuteMode
    
    values = {}
    
    # Common fields to extract
    common_fields = {
        "price": ("price", "$"),
        "total_monthly_cost": ("total_monthly_cost", "$"),
        "base_rent": ("base_rent", "$"),
        "parking_cost": ("parking_cost", "$"),
        "commute_duration": ("commute_duration", " min"),
        "safety_score": ("safety_score", "/10"),
        "wfh_score": ("wfh_score", "/10"),
        "gym_walk_time": ("gym_walk_time", " min"),
        "parking_score": ("parking_score", "/10"),
        "laundry_score": ("laundry_score", "/10"),
        "happening_score": ("happening_score", "/10"),
        "sqft": ("sqft", " sqft"),
        "commute_score": ("commute_score", "/10"),
        "route_annoyingness": ("route_annoyingness", "/10"),
        "transit_annoyingness": ("transit_annoyingness", "/10"),
        "transit_walking_minutes": ("transit_walking_minutes", " min"),
        "transit_transfers": ("transit_transfers", " transfers"),
    }
    
    for key, (field, unit) in common_fields.items():
        val = resolve_field(apartment_data, field)
        if val is not None:
            values[key] = {
                "value": val,
                "unit": unit,
                "display": f"{unit.strip('/')}{val}" if unit.startswith("$") else f"{val}{unit}"
            }
    
    # Add profile-specific commute data
    values["commute_by_profile"] = {}
    for profile_name, profile in profiles.items():
        commute_config = profile.commute_config
        data_field = commute_config.data_field
        
        # Get commute duration for this profile
        commute_val = apartment_data.get(data_field)
        if commute_val is None:
            if data_field == "commute_time_partner":
                commute_val = apartment_data.get("Commute Time (Partner)")
            elif data_field == "commute_time_you":
                commute_val = apartment_data.get("Commute Time (You)")
                if commute_val is None:
                    commute_val = resolve_field(apartment_data, "commute_duration")
        
        profile_commute = {
            "duration": commute_val,
            "mode": commute_config.mode.value,
            "data_field": data_field,
        }
        
        # Add mode-specific annoyingness
        if commute_config.mode == CommuteMode.TRANSIT:
            profile_commute["annoyingness"] = apartment_data.get("transit_annoyingness")
            profile_commute["walking_mins"] = apartment_data.get("transit_walking_minutes")
            profile_commute["transfers"] = apartment_data.get("transit_transfers")
        else:
            profile_commute["annoyingness"] = apartment_data.get("route_annoyingness")
        
        values["commute_by_profile"][profile_name] = profile_commute
    
    return values


def register_preference_routes(app):
    """Register preference blueprint with Flask app."""
    app.register_blueprint(preferences_bp)



