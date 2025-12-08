# Preference-Based Apartment Evaluation System

A threshold-based evaluation system that identifies apartments meeting individual and joint preferences, with explainable violation tracking and quiz-derived weights.

## Overview

This system complements the existing weighted scoring approach by:

1. **Defining explicit thresholds** (ideal/acceptable/veto) for each criterion
2. **Tracking violations** to see exactly which deal-breakers each apartment crosses
3. **Supporting joint evaluation** for couples/roommates with different priorities
4. **Deriving weights objectively** through a preference elicitation quiz (AHP method)

## Quick Start

### 1. Create Preference Profiles

**Option A: Interactive Quiz (Recommended)**

```bash
cd /path/to/automated_apartment_scraper
python -m preferences.cli quiz "YourName"
```

The quiz guides you through:
- Priority ranking of criteria
- Setting threshold values (ideal/acceptable/veto)
- Pairwise comparison scenarios for weight derivation

**Option B: Start from Default Profile**

```bash
python -m preferences.cli default-profile "YourName"
# Then edit preferences/profiles/yourname.yaml
```

### 2. Evaluate Apartments

```bash
python -m preferences.cli evaluate \
  -p preferences/profiles/person_a.yaml preferences/profiles/person_b.yaml \
  -a apartments.json \
  -o results/evaluation.json \
  --max-vetoes 0 \
  --top 10
```

### 3. Compare Two Apartments

```bash
python -m preferences.cli compare \
  -p preferences/profiles/person_a.yaml preferences/profiles/person_b.yaml \
  -a apartments.json \
  "123-Main-St" "456-Oak-Ave"
```

## Profile Structure

Each person's preferences are stored in a YAML file:

```yaml
person_name: Alex
version: 1

criteria:
  - id: safety
    display_name: Safety
    priority_order: 1  # 1 = highest priority
    ideal:
      - field: safety_score
        value: 8.0
        operator: gte  # greater than or equal
    acceptable:
      - field: safety_score
        value: 6.0
        operator: gte
    veto:
      - field: safety_score
        value: 5.0
        operator: gte
    veto_reason: "Neighborhood safety below minimum acceptable level"

  - id: commute
    display_name: Commute
    priority_order: 2
    ideal:
      - field: commute_duration
        value: 30
        operator: lte  # less than or equal
    acceptable:
      - field: commute_duration
        value: 45
        operator: lte
    veto:
      - field: commute_duration
        value: 60
        operator: lte
    veto_reason: "Commute exceeds maximum acceptable time"

# ... more criteria ...

ahp_weights:
  safety: 0.25
  commute: 0.18
  # ... derived from quiz

ahp_consistency_ratio: 0.07  # < 0.10 is acceptable
```

### Threshold Tiers

| Tier | Meaning | Scoring |
|------|---------|---------|
| **Ideal** | Best case, fully meets preferences | 1.0 |
| **Acceptable** | Not perfect but workable | 0.7 |
| **Veto** | Deal-breaker, apartment is rejected | 0.0 |

### Comparison Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `lte` | Less than or equal | commute <= 30 min |
| `gte` | Greater than or equal | safety >= 8.0 |
| `lt` | Less than | price < 4000 |
| `gt` | Greater than | sqft > 700 |
| `eq` | Equal | laundry_type == "in_unit" |
| `in` | Value in list | laundry_type in ["in_unit", "in_unit_combo"] |
| `not_in` | Value not in list | neighborhood not in ["Tenderloin"] |

## Evaluation Output

### Summary Table

```
     Rank     |   Apartment    |  Alex Score   | Jamie Score   | Joint Score  |    Vetoes    |    Status    
-----------------------------------------------------------------------------------------------------------------
       1      | 123-Main-St    |     0.89      |     0.82      |     0.85     |      0       |    ✓ OK      
       2      | 456-Oak-Ave    |     0.76      |     0.91      |     0.84     |      0       |    ✓ OK      
       3      | 789-Pine-Rd    |     0.71      |     0.68      |     0.70     |      1       |   ✗ VETO     
```

### Detailed Evaluation

For each apartment, you get:
- Tier result for each criterion (ideal/acceptable/veto)
- First violation (the highest-priority criterion that missed ideal)
- All violations with specific values and distances from thresholds
- Human-readable explanations
- Tie-break score using AHP-derived weights

### Joint Evaluation

When evaluating for multiple people:
- **Joint veto count**: Total vetoes across all people
- **Joint satisfaction score**: Average of individual scores
- **Disagreements**: Criteria where people have different tier results
- **Pareto-optimal apartments**: Apartments not dominated by any other

## The Preference Quiz

### Phase 1: Priority Ranking

Rank criteria from most to least important. This sets the lexicographic evaluation order.

### Phase 2: Threshold Values

For each criterion, specify:
- **Ideal**: "I'd be very happy if..."
- **Acceptable**: "I could live with..."
- **Veto**: "Anything worse than this is a deal-breaker"

### Phase 3: Pairwise Comparisons

Concrete scenarios presenting trade-offs between criteria pairs:

> **Scenario**: Trade-off: Shorter commute vs Safer neighborhood
>
> **Option A (Commute)**: 25 minute commute, but the neighborhood has a moderate crime rate
>
> **Option B (Safety)**: 45 minute commute, but the neighborhood is very safe
>
> **Context**: Think about your typical exhausting Thursday evening after a long day.

Response scale:
1. Strongly prefer A
2. Moderately prefer A
3. Slightly prefer A
4. Weakly prefer A
5. Equal / No preference
6. Weakly prefer B
7. Slightly prefer B
8. Moderately prefer B
9. Strongly prefer B

### AHP Weight Calculation

The Analytic Hierarchy Process (AHP) converts pairwise comparisons into normalized weights:

1. Build comparison matrix from scenario responses
2. Calculate geometric mean of each row
3. Normalize to sum to 1.0
4. Check consistency ratio (CR ≤ 0.10 is acceptable)

If CR > 0.10, the quiz identifies inconsistent comparisons to revisit.

## Bias Guardrails

### Built-in Protections

1. **Concrete scenarios**: Questions use real-world context (e.g., "Think about an overtime week") to reduce abstract bias

2. **Randomized order**: Scenarios are shuffled to prevent anchoring effects

3. **Consistency checking**: AHP consistency ratio flags contradictory preferences

4. **Status quo awareness**: Some scenarios explicitly test if you're just defending your current situation

### Recommended Practices

1. **Take the quiz independently**: Each person should complete without discussing answers

2. **Re-calibrate after tours**: After seeing 3-5 apartments, re-run the quiz to see if priorities shifted

3. **Review disagreements**: Joint evaluation highlights where partners differ—discuss these explicitly

4. **Test edge cases**: If an apartment ranks highly but feels wrong, examine which threshold it barely passed

5. **Version profiles**: Keep dated copies when updating preferences to track evolution

## Integration with Existing System

### Using with Google Sheets Data

```python
from preferences.integration import PreferenceIntegration

# Initialize with profile directory
integration = PreferenceIntegration(profile_dir=Path("preferences/profiles"))

# Load apartment data from sheet
apartments = [...]  # List of dicts from Google Sheets

# Evaluate
evaluations = integration.evaluate_apartments(apartments, from_sheet=True)

# Get shortlist (no vetoes, top 10)
shortlist = integration.get_shortlist(evaluations, max_vetoes=0, top_n=10)

# Generate report
report = integration.generate_report(evaluations, output_dir=Path("results"))
```

### Field Mapping

The integration module maps Google Sheets columns to preference fields:

| Sheet Column | Preference Field |
|--------------|------------------|
| "Commute Time (You)" | commute_duration |
| "Combined Safety" | safety_score |
| "WFH Quality Score" | wfh_score |
| "Time to Nearest Gym (min)" | gym_walk_time |
| "Parking Score" | parking_score |
| "Square Feet" | sqft |
| "Price" | monthly_cost |
| ... | ... |

## File Structure

```
preferences/
├── __init__.py           # Package exports
├── schemas.py            # Data structures (PreferenceProfile, Threshold, etc.)
├── evaluation_engine.py  # Evaluation and ranking logic
├── quiz.py               # Quiz system and AHP calculator
├── reports.py            # Report generation
├── cli.py                # Command-line interface
├── integration.py        # Google Sheets integration
└── profiles/
    ├── sample_person_a.yaml
    └── sample_person_b.yaml
```

## Troubleshooting

### "No apartments pass all veto criteria"

Options:
1. Relax veto thresholds (but be honest about deal-breakers)
2. Use `--max-vetoes 1` to see apartments with minimal violations
3. Check if the data has quality issues (missing values → automatic veto)

### "Consistency ratio too high"

Your pairwise comparisons contain contradictions. The quiz will show which pairs to reconsider. Common causes:
- Fatigue during quiz
- Different interpretations of the same criterion
- True uncertainty about priorities (consider keeping equal weights)

### "Scores don't match intuition"

The preference system is designed to be explainable. Check:
1. Detailed evaluation shows exactly which thresholds passed/failed
2. AHP weights may not match your intuition—re-take quiz or adjust manually
3. Data quality issues can cause unexpected violations

## Philosophy

This system is designed around the principle that **knowing what you won't accept is more valuable than trying to optimize a composite score**.

The existing weighted scoring answers: "What's the best overall apartment?"

The preference system answers: "Which apartments meet our minimum requirements, and among those, which ones best balance our priorities?"

By making deal-breakers explicit, you avoid the trap of a high score masking a critical flaw. By using quiz-derived weights, you reduce arbitrary weight assignment. By tracking individual and joint preferences, you surface disagreements that need discussion rather than hiding them in an average.




