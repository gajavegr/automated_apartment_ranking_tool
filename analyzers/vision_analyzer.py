"""
Claude Vision analyzer for apartment photos

Analyzes apartment photos to extract:
- Natural light quality
- Desk space quality
- Kitchen quality
- View quality
- Floor level
- Double-pane windows
- Door type (study/work area)
- Street noise indicators
- Laundry machines (if visible)
- Parking situation
"""

import os
import base64
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

import anthropic

import config
from utils.cache import get_cache


class VisionAnalyzer:
    """Analyzer for apartment photos using Claude Vision"""
    
    def __init__(self, api_key: str = None):
        """
        Initialize vision analyzer
        
        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key or config.ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Please set it in .env file.")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.cache = get_cache()
    
    def _get_cache_key(self, photo_paths: List[str]) -> str:
        """Generate cache key for photo analysis"""
        # Use sorted paths to ensure consistent cache key
        paths_str = '|'.join(sorted(photo_paths))
        return f"vision_analysis_{abs(hash(paths_str))}"
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    def _get_media_type(self, image_path: str) -> str:
        """Get media type from file extension"""
        ext = Path(image_path).suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        elif ext == '.webp':
            return 'image/webp'
        elif ext == '.gif':
            return 'image/gif'
        return 'image/jpeg'  # Default
    
    def analyze_apartment_photos(
        self,
        photo_paths: List[str],
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze apartment photos using Claude Vision
        
        Args:
            photo_paths: List of paths to photo files
            force_refresh: Ignore cache and analyze fresh
            
        Returns:
            Dictionary with analysis results
        """
        # Check cache
        if not force_refresh:
            cached_result = self.cache.get(self._get_cache_key(photo_paths))
            if cached_result:
                print("Using cached vision analysis")
                return cached_result
        
        print(f"Analyzing {len(photo_paths)} photos with Claude Vision...")
        
        # Limit number of photos to avoid token limits
        photos_to_analyze = photo_paths[:15]
        
        # Build message content with images
        content = []
        
        # Add instruction text
        content.append({
            "type": "text",
            "text": self._get_analysis_prompt()
        })
        
        # Add images
        for photo_path in photos_to_analyze:
            if not os.path.exists(photo_path):
                print(f"Warning: Photo not found: {photo_path}")
                continue
            
            try:
                image_data = self._encode_image(photo_path)
                media_type = self._get_media_type(photo_path)
                
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    }
                })
            except Exception as e:
                print(f"Error encoding photo {photo_path}: {e}")
        
        # Call Claude API
        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                temperature=config.CLAUDE_TEMPERATURE,
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )
            
            # Parse response
            response_text = response.content[0].text
            result = self._parse_response(response_text)
            
            # Cache result
            self.cache.set(self._get_cache_key(photo_paths), result)
            
            return result
        
        except Exception as e:
            print(f"Error calling Claude Vision API: {e}")
            return self._get_default_analysis()
    
    def _get_analysis_prompt(self) -> str:
        """Get the analysis prompt for Claude"""
        return """Analyze these apartment photos and provide structured ratings. Return your response as a JSON object with the following fields (all numeric scores on 0-10 scale):

{
  "natural_light": <0-10, how bright and well-lit the space is>,
  "desk_space_quality": <0-10, quality of space for a work-from-home desk - consider placement, size, window access>,
  "kitchen_quality": <0-10, modern appliances, counter space, overall condition>,
  "view_quality": <0-10, what can be seen from windows - city skyline=high, brick wall=low>,
  "floor_level": <"ground", "mid", or "high" - based on views and visual indicators>,
  "double_pane_windows": <true/false, look for thick window frames, modern windows>,
  "study_door_type": <"hinged", "sliding", "open", or "none" - door type for study/work area>,
  "street_noise_level": <0-10, visual indicators of noise - 10=quiet residential, 0=busy street>,
  "laundry_machines_visible": <number of washers/dryers visible in photos>,
  "parking_visible": <"garage", "carport", "street", "none" - if parking is shown>,
  "street_type": <"residential_one_way", "residential_small_street", "residential_main_street", "mixed_use_moderate", "busy_commercial", or "unknown">,
  "overall_condition": <0-10, general condition and maintenance quality>,
  "notes": <brief text summary of key observations>
}

Be objective and base ratings on what you see in the photos. If you can't determine something, use neutral values (5 for scores, "unknown" for categories).

Return ONLY the JSON object, no additional text."""
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's JSON response"""
        try:
            # Try to extract JSON from response
            # Look for JSON block
            json_match = response_text.strip()
            if json_match.startswith('```'):
                # Remove code fence
                json_match = json_match.split('```')[1]
                if json_match.startswith('json'):
                    json_match = json_match[4:]
            
            result = json.loads(json_match.strip())
            
            # Ensure all required fields exist with defaults
            defaults = self._get_default_analysis()
            for key, default_value in defaults.items():
                if key not in result:
                    result[key] = default_value
            
            return result
        
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {e}")
            print(f"Response text: {response_text[:500]}")
            return self._get_default_analysis()
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """Get default analysis values when parsing fails"""
        return {
            "natural_light": 5.0,
            "desk_space_quality": 5.0,
            "kitchen_quality": 5.0,
            "view_quality": 5.0,
            "floor_level": "mid",
            "double_pane_windows": False,
            "study_door_type": "none",
            "street_noise_level": 5.0,
            "laundry_machines_visible": 0,
            "parking_visible": "none",
            "street_type": "unknown",
            "overall_condition": 5.0,
            "notes": "Unable to analyze photos",
        }
    
    def analyze_street_parking(self, street_photo_path: str) -> Dict[str, Any]:
        """
        Analyze a street photo for parking quality assessment
        
        Args:
            street_photo_path: Path to street view photo
            
        Returns:
            Dictionary with street parking analysis
        """
        print("Analyzing street parking conditions...")
        
        try:
            image_data = self._encode_image(street_photo_path)
            media_type = self._get_media_type(street_photo_path)
            
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=1024,
                temperature=0.0,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Analyze this street photo for parking conditions. Return JSON:
{
  "street_type": <"residential_one_way", "residential_small_street", "residential_main_street", "mixed_use_moderate", or "busy_commercial">,
  "parking_difficulty": <0-10, 0=impossible, 10=always easy>,
  "street_width": <"narrow", "medium", "wide">,
  "traffic_density": <"light", "moderate", "heavy">,
  "is_one_way": <true/false>,
  "notes": <brief observations>
}"""
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            }
                        }
                    ]
                }]
            )
            
            response_text = response.content[0].text
            return self._parse_response(response_text)
        
        except Exception as e:
            print(f"Error analyzing street parking: {e}")
            return {
                "street_type": "unknown",
                "parking_difficulty": 5.0,
                "street_width": "medium",
                "traffic_density": "moderate",
                "is_one_way": False,
                "notes": "Unable to analyze",
            }

