"""
Debug script to understand why 1617 Noe St is showing as a safety violation
when it has a safety score of 7.5 and Neelie's veto threshold is >= 5.
"""

from pathlib import Path
from utils.google_sheets import GoogleSheetsClient
from preferences.evaluation_engine import PreferenceEvaluator
from preferences.schemas import PreferenceProfile
from preferences.integration import normalize_apartment_data
import config

def debug_noe_st_evaluation():
    print("=" * 80)
    print("DEBUG: 1617 Noe St Safety Evaluation")
    print("=" * 80)
    
    # Load Neelie's profile
    profile_path = Path("preferences/profiles/neelie.yaml")
    neelie_profile = PreferenceProfile.load(profile_path)
    
    print(f"\n📋 Neelie's Safety Criterion:")
    safety_criterion = next(c for c in neelie_profile.criteria if c.id == "safety")
    print(f"   Display Name: {safety_criterion.display_name}")
    print(f"   Priority: {safety_criterion.priority_order}")
    print(f"\n   Veto thresholds:")
    for threshold in safety_criterion.veto:
        print(f"      - field: {threshold.field}")
        print(f"        value: {threshold.value}")
        print(f"        operator: {threshold.operator}")
    print(f"\n   Acceptable thresholds:")
    for threshold in safety_criterion.acceptable:
        print(f"      - field: {threshold.field}")
        print(f"        value: {threshold.value}")
        print(f"        operator: {threshold.operator}")
    
    # Get apartment data from sheet
    print(f"\n📊 Fetching apartment data from Google Sheet...")
    client = GoogleSheetsClient()
    records = client.read_main_sheet()
    
    # Find 1617 Noe St
    noe_st_record = None
    for record in records:
        address = record.get(config.SHEET_COLUMNS["address"], "")
        if "1617 Noe St" in address:
            noe_st_record = record
            break
    
    if not noe_st_record:
        print("❌ Could not find 1617 Noe St in the sheet!")
        return
    
    print(f"✓ Found apartment: {noe_st_record.get(config.SHEET_COLUMNS['address'])}")
    
    # Show raw data
    print(f"\n📝 Raw Google Sheet Data:")
    safety_fields = [
        "Manual Safety Rating",
        "Safety Score (OpenData)",
        "Combined Safety",
    ]
    for field in safety_fields:
        value = noe_st_record.get(field, "N/A")
        print(f"   {field}: {value} (type: {type(value).__name__})")
    
    # Normalize the data
    print(f"\n🔄 Normalizing apartment data...")
    normalized = normalize_apartment_data(noe_st_record)
    
    print(f"\n📝 Normalized Data (safety-related fields):")
    safety_related = [
        "manual_safety",
        "manual_safety_rating", 
        "safety_score_opendata",
        "combined_safety",
        "safety_score",
    ]
    for field in safety_related:
        if field in normalized:
            value = normalized[field]
            print(f"   {field}: {value} (type: {type(value).__name__})")
    
    # Create evaluator
    print(f"\n🔍 Evaluating apartment against Neelie's preferences...")
    evaluator = PreferenceEvaluator({"Neelie": neelie_profile})
    
    # Manually resolve the safety_score field
    from preferences.schemas import resolve_field
    resolved_safety = resolve_field(normalized, "safety_score")
    print(f"\n🔎 Field Resolution:")
    print(f"   resolve_field(normalized, 'safety_score') = {resolved_safety}")
    
    # Test threshold evaluation
    print(f"\n🧪 Testing Threshold Evaluation:")
    for threshold in safety_criterion.veto:
        actual_value = resolve_field(normalized, threshold.field)
        result = threshold.evaluate(actual_value)
        print(f"   Veto threshold: {threshold.field} {threshold.operator.value} {threshold.value}")
        print(f"   Actual value: {actual_value}")
        print(f"   Evaluation result: {result}")
        print(f"   Violation? {not result}")
    
    # Evaluate tier
    from preferences.schemas import TierLevel
    tier = safety_criterion.evaluate_tier(normalized)
    print(f"\n📊 Safety Criterion Tier Result: {tier}")
    
    # Full evaluation
    evaluation = evaluator.evaluate_individual(
        apartment_id=normalized.get("apartment_id", "1617 Noe St"),
        apartment_data=normalized,
        profile=neelie_profile,
    )
    
    print(f"\n📋 Full Evaluation Results:")
    print(f"   Ideal count: {evaluation.ideal_count}")
    print(f"   Acceptable count: {evaluation.acceptable_count}")
    print(f"   Veto count: {evaluation.veto_count}")
    print(f"   Safety tier: {evaluation.tier_results.get('safety', 'N/A')}")
    
    if evaluation.first_violation:
        v = evaluation.first_violation
        print(f"\n⚠️  First Violation Detected:")
        print(f"   Criterion: {v.criterion_name} (Priority {v.priority_order})")
        print(f"   Field: {v.field}")
        operator_str = v.operator.value if hasattr(v.operator, 'value') else str(v.operator)
        print(f"   Expected: {operator_str} {v.expected_value}")
        print(f"   Actual: {v.actual_value}")
        print(f"   Tier: {v.tier}")
    else:
        print(f"\n✅ No veto violations detected (may have ACCEPTABLE violations)!")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    debug_noe_st_evaluation()

