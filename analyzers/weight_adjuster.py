"""
Weight Adjustment Engine for Learning User Preferences

This module analyzes user edits to apartment scores and suggests
adjustments to scoring weights based on observed patterns.
"""

from typing import Dict, List, Any, Tuple
from collections import defaultdict
import statistics

import config


class WeightAdjuster:
    """Analyzes user edits and suggests weight adjustments"""
    
    def __init__(self, edit_history: List[Dict[str, Any]]):
        """
        Initialize with edit history
        
        Args:
            edit_history: List of edit records from User Edits Log sheet
        """
        self.edit_history = edit_history
        self.field_to_component = {
            # Commute fields
            'commute_duration': 'commute',
            'commute_duration_partner': 'commute',
            
            # Safety fields
            'safety_score_opendata': 'safety',
            
            # WFH Quality fields
            'natural_light': 'wfh_quality',
            'desk_space_quality': 'wfh_quality',
            'quietness_score': 'wfh_quality',
            'kitchen_quality': 'wfh_quality',
            
            # Location Vibe fields
            'restaurants_nearby': 'location_vibe',
            'cafes_nearby': 'location_vibe',
            'parks_nearby': 'location_vibe',
            
            # Parking fields
            'street_parking_ease': 'parking',
            'visitor_parking_ease': 'parking',
            
            # Gym fields
            'gym_quality': 'gym'
        }
    
    def analyze_edits(self) -> Dict[str, Dict[str, Any]]:
        """
        Analyze edit patterns to understand user preferences
        
        Returns:
            Dictionary mapping component names to analysis results
        """
        if not self.edit_history:
            return {}
        
        # Group edits by component
        component_edits = defaultdict(list)
        
        for edit in self.edit_history:
            field = edit.get('Field Changed', '')
            old_value = self._parse_value(edit.get('Original Value'))
            new_value = self._parse_value(edit.get('New Value'))
            
            if old_value is None or new_value is None:
                continue
            
            component = self.field_to_component.get(field)
            if component:
                delta = new_value - old_value
                component_edits[component].append({
                    'field': field,
                    'delta': delta,
                    'old_value': old_value,
                    'new_value': new_value,
                    'timestamp': edit.get('Timestamp'),
                    'address': edit.get('Apartment Address')
                })
        
        # Analyze each component
        analysis = {}
        for component, edits in component_edits.items():
            if not edits:
                continue
            
            deltas = [e['delta'] for e in edits]
            avg_delta = statistics.mean(deltas)
            median_delta = statistics.median(deltas)
            
            # Count direction of edits
            increases = sum(1 for d in deltas if d > 0)
            decreases = sum(1 for d in deltas if d < 0)
            
            # Determine if there's a clear pattern
            total = len(deltas)
            increase_ratio = increases / total if total > 0 else 0
            decrease_ratio = decreases / total if total > 0 else 0
            
            analysis[component] = {
                'edit_count': len(edits),
                'avg_delta': avg_delta,
                'median_delta': median_delta,
                'increases': increases,
                'decreases': decreases,
                'increase_ratio': increase_ratio,
                'decrease_ratio': decrease_ratio,
                'edits': edits
            }
        
        return analysis
    
    def suggest_weight_adjustments(self, threshold: float = 0.6) -> Dict[str, Dict[str, Any]]:
        """
        Suggest weight adjustments based on edit analysis
        
        Args:
            threshold: Minimum ratio of consistent edits to suggest adjustment (0.6 = 60%)
            
        Returns:
            Dictionary mapping component names to suggested adjustments
        """
        analysis = self.analyze_edits()
        suggestions = {}
        
        for component, data in analysis.items():
            # Skip if not enough edits to be confident
            if data['edit_count'] < 3:
                continue
            
            current_weight = config.SCORING_WEIGHTS.get(component, 0)
            
            # Determine if user consistently values this more or less
            if data['increase_ratio'] >= threshold:
                # User consistently increases this component's values
                # Suggests they value it more → increase weight
                adjustment_factor = 1.0 + (data['avg_delta'] * 0.1)
                suggested_weight = min(current_weight * adjustment_factor, 1.0)
                
                suggestions[component] = {
                    'current_weight': current_weight,
                    'suggested_weight': suggested_weight,
                    'adjustment_factor': adjustment_factor,
                    'reasoning': f"You increased {component} scores {data['increases']} out of {data['edit_count']} times (avg: +{data['avg_delta']:.2f}). This suggests you value {component} more than the current weight indicates.",
                    'confidence': data['increase_ratio'],
                    'direction': 'increase'
                }
            
            elif data['decrease_ratio'] >= threshold:
                # User consistently decreases this component's values
                # Suggests they value it less → decrease weight
                adjustment_factor = 1.0 + (data['avg_delta'] * 0.1)  # avg_delta will be negative
                suggested_weight = max(current_weight * adjustment_factor, 0.01)
                
                suggestions[component] = {
                    'current_weight': current_weight,
                    'suggested_weight': suggested_weight,
                    'adjustment_factor': adjustment_factor,
                    'reasoning': f"You decreased {component} scores {data['decreases']} out of {data['edit_count']} times (avg: {data['avg_delta']:.2f}). This suggests you value {component} less than the current weight indicates.",
                    'confidence': data['decrease_ratio'],
                    'direction': 'decrease'
                }
        
        # Normalize suggested weights to sum to 1.0
        if suggestions:
            suggestions = self._normalize_weights(suggestions)
        
        return suggestions
    
    def _normalize_weights(self, suggestions: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Normalize suggested weights so all weights sum to 1.0
        
        Args:
            suggestions: Dictionary of weight suggestions
            
        Returns:
            Updated suggestions with normalized weights
        """
        # Get all current weights
        all_weights = dict(config.SCORING_WEIGHTS)
        
        # Update with suggested weights
        for component, suggestion in suggestions.items():
            all_weights[component] = suggestion['suggested_weight']
        
        # Normalize
        total = sum(all_weights.values())
        if total > 0:
            normalized = {k: v / total for k, v in all_weights.items()}
            
            # Update suggestions with normalized values
            for component in suggestions:
                old_suggested = suggestions[component]['suggested_weight']
                new_suggested = normalized[component]
                suggestions[component]['suggested_weight_normalized'] = new_suggested
                suggestions[component]['normalization_factor'] = new_suggested / old_suggested if old_suggested > 0 else 1.0
        
        return suggestions
    
    def apply_weight_adjustments(self, suggestions: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """
        Apply suggested weight adjustments to get new weight configuration
        
        Args:
            suggestions: Dictionary of weight suggestions from suggest_weight_adjustments()
            
        Returns:
            New weight configuration dictionary
        """
        new_weights = dict(config.SCORING_WEIGHTS)
        
        for component, suggestion in suggestions.items():
            # Use normalized weight if available, otherwise use suggested weight
            new_weight = suggestion.get('suggested_weight_normalized', suggestion['suggested_weight'])
            new_weights[component] = new_weight
        
        return new_weights
    
    def get_adjustment_summary(self) -> str:
        """
        Get a human-readable summary of suggested adjustments
        
        Returns:
            Formatted string summarizing suggestions
        """
        suggestions = self.suggest_weight_adjustments()
        
        if not suggestions:
            return "No weight adjustments suggested. Need at least 3 consistent edits per component."
        
        lines = ["Suggested Weight Adjustments:", ""]
        
        for component, suggestion in suggestions.items():
            current = suggestion['current_weight']
            suggested = suggestion.get('suggested_weight_normalized', suggestion['suggested_weight'])
            change_pct = ((suggested - current) / current * 100) if current > 0 else 0
            
            lines.append(f"• {component.upper()}")
            lines.append(f"  Current: {current:.3f} ({current*100:.1f}%)")
            lines.append(f"  Suggested: {suggested:.3f} ({suggested*100:.1f}%)")
            lines.append(f"  Change: {change_pct:+.1f}%")
            lines.append(f"  Confidence: {suggestion['confidence']:.0%}")
            lines.append(f"  Reasoning: {suggestion['reasoning']}")
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def _parse_value(value_str: str) -> float:
        """
        Parse a value string to float
        
        Args:
            value_str: String representation of a value
            
        Returns:
            Float value or None if cannot parse
        """
        if not value_str or value_str == '':
            return None
        
        try:
            return float(value_str)
        except (ValueError, TypeError):
            return None

