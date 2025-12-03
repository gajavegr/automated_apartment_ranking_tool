#!/usr/bin/env python3
"""
Automated photo analyzer for apartment WFH suitability

Automatically extracts photos from Zillow listings, filters relevant ones,
and analyzes them for work-from-home suitability.
"""

import argparse
import base64
import os
import sys
import tempfile
import requests
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse

from anthropic import Anthropic
from playwright.sync_api import sync_playwright

import config
from utils.google_sheets import GoogleSheetsClient


class AutomatedPhotoAnalyzer:
    """Automated tool for extracting and analyzing apartment photos for WFH suitability"""
    
    def __init__(self):
        self.anthropic_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.temp_dir = tempfile.mkdtemp(prefix="apartment_photos_")
        self.photo_urls = []
        self.relevant_photos = []
    
    def extract_photo_urls(self, zillow_url: str) -> List[str]:
        """
        Extract all photo URLs from Zillow listing
        
        Args:
            zillow_url: URL of Zillow listing
            
        Returns:
            List of photo URLs
        """
        print("\n" + "="*80)
        print("🏠 AUTOMATED PHOTO EXTRACTOR")
        print("="*80)
        print(f"\nExtracting photos from: {zillow_url}")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, channel="chrome")
                page = browser.new_page()
                page.set_default_timeout(60000)
                
                print("✓ Navigating to listing...")
                page.goto(zillow_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(3000)  # Wait for dynamic content
                
                print("✓ Extracting image URLs...")
                
                # Extract all image URLs from the page
                image_urls = page.evaluate("""
                    () => {
                        const urls = new Set();
                        
                        // Look for main photo gallery images
                        const selectors = [
                            'img[class*="media-stream"]',
                            'img[class*="photo"]',
                            'picture img',
                            '[data-test="light-box"] img',
                            '.media-photo img'
                        ];
                        
                        selectors.forEach(selector => {
                            document.querySelectorAll(selector).forEach(img => {
                                const src = img.src || img.getAttribute('data-src');
                                if (src && !src.includes('logo') && !src.includes('icon')) {
                                    // Get high-res version if available
                                    const highResSrc = src.replace('/p_e/', '/p_h/').replace(/\\d+x\\d+/, '1024x768');
                                    urls.add(highResSrc);
                                }
                            });
                        });
                        
                        return Array.from(urls);
                    }
                """)
                
                browser.close()
                
                # Filter out duplicates and invalid URLs
                valid_urls = [url for url in image_urls if url.startswith('http')]
                
                print(f"✓ Found {len(valid_urls)} photos")
                self.photo_urls = valid_urls
                return valid_urls
                
        except Exception as e:
            print(f"✗ Error extracting photos: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def download_photos(self, urls: List[str]) -> List[str]:
        """
        Download photos from URLs
        
        Args:
            urls: List of photo URLs
            
        Returns:
            List of local file paths to downloaded photos
        """
        if not urls:
            return []
        
        print(f"\n{'='*80}")
        print(f"📥 DOWNLOADING {len(urls)} PHOTOS")
        print(f"{'='*80}")
        
        downloaded = []
        for i, url in enumerate(urls, 1):
            try:
                print(f"Downloading photo {i}/{len(urls)}...", end='\r')
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                # Save to temp file
                ext = 'jpg' if 'jpeg' in url or 'jpg' in url else 'png'
                filepath = os.path.join(self.temp_dir, f"photo_{i}.{ext}")
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                downloaded.append(filepath)
            except Exception as e:
                print(f"\n⚠ Failed to download photo {i}: {e}")
                continue
        
        print(f"\n✓ Downloaded {len(downloaded)} photos successfully")
        return downloaded
    
    def filter_relevant_photos(self, photo_paths: List[str]) -> List[str]:
        """
        Use Claude to filter which photos are relevant for WFH analysis
        
        Args:
            photo_paths: List of paths to photo files
            
        Returns:
            List of paths to relevant photos
        """
        if not photo_paths:
            return []
        
        print(f"\n{'='*80}")
        print(f"🔍 FILTERING RELEVANT PHOTOS")
        print(f"{'='*80}")
        print("\nAsking Claude to identify photos relevant for WFH analysis...")
        
        # Prepare images for Claude
        image_contents = []
        for i, path in enumerate(photo_paths, 1):
            with open(path, 'rb') as f:
                image_data = base64.standard_b64encode(f.read()).decode('utf-8')
                # Determine media type
                media_type = "image/jpeg" if path.endswith('.jpg') or path.endswith('.jpeg') else "image/png"
                image_contents.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data
                    }
                })
        
        filter_prompt = """You are analyzing apartment photos to determine which ones are relevant for assessing work-from-home (WFH) suitability.

**RELEVANT** photos include:
- Living rooms (desk space potential, natural light)
- Bedrooms (potential home office)
- Windows and views (light, noise assessment)
- Kitchen (work breaks, quality of life)
- Common areas/courtyards (quiet, tucked away location)
- Den/study rooms
- Dining areas (convertible to workspace)
- Bathrooms (if spacious enough to indicate overall apartment quality)

**NOT RELEVANT** photos include:
- Closets
- Storage spaces
- Building exteriors (unless showing noise sources)
- Hallways
- Laundry rooms
- Pure amenity photos (gym, pool) unless relevant to noise

For each photo numbered 1 to %d, respond with ONLY:
YES or NO

One per line. Example:
YES
NO
YES
NO

Start now:""" % len(photo_paths)
        
        try:
            message = self.anthropic_client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=500,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": image_contents + [{
                        "type": "text",
                        "text": filter_prompt
                    }]
                }]
            )
            
            response_text = message.content[0].text
            lines = [line.strip().upper() for line in response_text.strip().split('\n') if line.strip()]
            
            # Filter photos based on Claude's response
            relevant_paths = []
            for i, (path, decision) in enumerate(zip(photo_paths, lines), 1):
                if 'YES' in decision:
                    relevant_paths.append(path)
                    print(f"✓ Photo {i}: RELEVANT")
                else:
                    print(f"✗ Photo {i}: Not relevant")
            
            print(f"\n✓ Filtered to {len(relevant_paths)}/{len(photo_paths)} relevant photos")
            self.relevant_photos = relevant_paths
            return relevant_paths
            
        except Exception as e:
            print(f"\n✗ Error filtering photos: {e}")
            # If filtering fails, use all photos
            print("⚠ Using all photos as fallback")
            return photo_paths
    
    def analyze_wfh_suitability(self, photo_paths: List[str]) -> Dict[str, Any]:
        """
        Analyze photos for WFH suitability
        
        Args:
            photo_paths: List of paths to relevant photo files
            
        Returns:
            Dictionary with WFH analysis results
        """
        if not photo_paths:
            print("\n⚠ No photos to analyze")
            return {}
        
        print(f"\n{'='*80}")
        print(f"🧠 ANALYZING WFH SUITABILITY ({len(photo_paths)} photos)")
        print(f"{'='*80}")
        
        # Prepare images for Claude
        image_contents = []
        for i, path in enumerate(photo_paths, 1):
            print(f"Loading photo {i}/{len(photo_paths)}...", end='\r')
            with open(path, 'rb') as f:
                image_data = base64.standard_b64encode(f.read()).decode('utf-8')
                media_type = "image/jpeg" if path.endswith('.jpg') or path.endswith('.jpeg') else "image/png"
                image_contents.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data
                    }
                })
        print()
        
        analysis_prompt = """Analyze these apartment photos for work-from-home (WFH) suitability. Provide ratings for:

1. **Natural Light** (0-10): Window size, brightness, natural light availability
2. **Desk Space Quality** (0-10): Space for desk + chair, areas near windows, dedicated office potential
3. **Kitchen Quality** (0-10): Appliances, counter space, storage, condition
4. **View Quality** (0-10): City/nature views = high; walls/parking lots = low
5. **Floor Level**: Estimate from windows/views: "ground", "mid", or "high"
6. **Double-Pane Windows**: Can you tell if windows are double-pane? (true/false) - look for thickness, modern construction
7. **Study Door Type**: Potential office/study door type: "solid_door", "hollow_door", "sliding_door", "open", or "none"
8. **Street Noise Level** (0-10): Based on visible location/windows. 0=very quiet, 10=loud traffic

Respond in EXACTLY this format:
NATURAL_LIGHT: [score]/10
DESK_SPACE: [score]/10
KITCHEN: [score]/10
VIEW: [score]/10
FLOOR_LEVEL: [ground/mid/high]
DOUBLE_PANE: [true/false]
DOOR_TYPE: [solid_door/hollow_door/sliding_door/open/none]
NOISE: [score]/10
SUMMARY: [2-3 sentence summary]"""
        
        try:
            print("🤖 Sending to Claude Vision for WFH analysis...")
            
            message = self.anthropic_client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                temperature=config.CLAUDE_TEMPERATURE,
                messages=[{
                    "role": "user",
                    "content": image_contents + [{
                        "type": "text",
                        "text": analysis_prompt
                    }]
                }]
            )
            
            response_text = message.content[0].text
            print("\n✓ Analysis complete!")
            print("\n" + "-"*80)
            print("RESULTS:")
            print("-"*80)
            print(response_text)
            print("-"*80)
            
            # Parse response
            results = self._parse_analysis(response_text)
            return results
            
        except Exception as e:
            print(f"\n✗ Error during analysis: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _parse_analysis(self, response: str) -> Dict[str, Any]:
        """Parse Claude's response into structured data"""
        results = {
            'natural_light': 5.0,
            'desk_space_quality': 5.0,
            'kitchen_quality': 5.0,
            'view_quality': 5.0,
            'floor_level': 'mid',
            'double_pane_windows': False,
            'study_door_type': 'none',
            'street_noise_level': 5.0,
            'summary': ''
        }
        
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            
            if line.startswith('NATURAL_LIGHT:'):
                try:
                    results['natural_light'] = float(line.split(':')[1].split('/')[0].strip())
                except:
                    pass
            elif line.startswith('DESK_SPACE:'):
                try:
                    results['desk_space_quality'] = float(line.split(':')[1].split('/')[0].strip())
                except:
                    pass
            elif line.startswith('KITCHEN:'):
                try:
                    results['kitchen_quality'] = float(line.split(':')[1].split('/')[0].strip())
                except:
                    pass
            elif line.startswith('VIEW:'):
                try:
                    results['view_quality'] = float(line.split(':')[1].split('/')[0].strip())
                except:
                    pass
            elif line.startswith('FLOOR_LEVEL:'):
                level = line.split(':')[1].strip().lower()
                if level in ['ground', 'mid', 'high']:
                    results['floor_level'] = level
            elif line.startswith('DOUBLE_PANE:'):
                value = line.split(':')[1].strip().lower()
                results['double_pane_windows'] = value == 'true'
            elif line.startswith('DOOR_TYPE:'):
                door = line.split(':')[1].strip().lower()
                if door in ['solid_door', 'hollow_door', 'sliding_door', 'open', 'none']:
                    results['study_door_type'] = door
            elif line.startswith('NOISE:'):
                try:
                    results['street_noise_level'] = float(line.split(':')[1].split('/')[0].strip())
                except:
                    pass
            elif line.startswith('SUMMARY:'):
                results['summary'] = line.split(':', 1)[1].strip()
        
        return results
    
    def update_sheet_with_analysis(self, address: str, analysis: Dict[str, Any]):
        """Update Google Sheet with vision analysis results"""
        try:
            print(f"\n{'='*80}")
            print("📊 UPDATING GOOGLE SHEET")
            print(f"{'='*80}")
            
            sheets_client = GoogleSheetsClient()
            records = sheets_client.read_main_sheet()
            
            # Find row with this address
            row_number = None
            for i, record in enumerate(records):
                if record.get(config.SHEET_COLUMNS['address'], '') == address:
                    row_number = i + 2  # +2 for header and 0-indexing
                    break
            
            if not row_number:
                print(f"⚠ Could not find apartment with address: {address}")
                return
            
            print(f"\n✓ Found apartment in row {row_number}")
            
            # Update vision-related columns
            sheet = sheets_client.spreadsheet.worksheet(sheets_client.MAIN_SHEET_NAME)
            headers = sheet.row_values(1)
            
            updates = []
            
            # Map analysis results to columns
            column_mapping = {
                'natural_light': 'natural_light',
                'desk_space_quality': 'desk_space_quality',
                'kitchen_quality': 'kitchen_quality',
                'view_quality': 'view_quality',
                'floor_level': 'floor_level',
                'double_pane_windows': 'double_pane_windows',
                'study_door_type': 'study_door_type',
                'street_noise_level': 'street_noise_level',
            }
            
            for data_key, col_key in column_mapping.items():
                if col_key in config.SHEET_COLUMNS and config.SHEET_COLUMNS[col_key] in headers:
                    col_idx = headers.index(config.SHEET_COLUMNS[col_key])
                    col_letter = chr(65 + col_idx)
                    updates.append({
                        'range': f'{col_letter}{row_number}',
                        'values': [[analysis[data_key]]]
                    })
            
            if updates:
                sheet.batch_update(updates)
                print(f"✓ Updated {len(updates)} columns with vision analysis")
            
        except Exception as e:
            print(f"\n✗ Error updating sheet: {e}")
            import traceback
            traceback.print_exc()
    
    def cleanup(self):
        """Clean up temporary files"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            print(f"\n✓ Cleaned up temporary files")
        except:
            pass


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Automated photo analyzer for apartment WFH suitability"
    )
    parser.add_argument(
        "zillow_url",
        nargs="?",
        help="Zillow listing URL"
    )
    parser.add_argument(
        "-a",
        "--address",
        help="Apartment address exactly as it appears in the Google Sheet"
    )
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🖼️  AUTOMATED WFH PHOTO ANALYZER")
    print("="*80)
    print("\nThis tool:")
    print("1. Extracts all photos from the Zillow listing")
    print("2. Filters for photos relevant to WFH analysis")
    print("3. Analyzes them with Claude Vision")
    print("4. Updates your Google Sheet with WFH scores")
    
    # Get Zillow URL
    zillow_url = args.zillow_url
    if not zillow_url:
        print("\nEnter the Zillow URL:")
        zillow_url = input("> ").strip()
    
    if not zillow_url:
        print("✗ No URL provided")
        sys.exit(1)
    
    # Get address for sheet lookup
    address = args.address
    if not address:
        print("\nEnter the apartment address (as it appears in your Google Sheet):")
        address = input("> ").strip()
    
    if not address:
        print("✗ No address provided")
        sys.exit(1)
    
    # Initialize analyzer
    analyzer = AutomatedPhotoAnalyzer()
    
    try:
        # Extract photo URLs
        photo_urls = analyzer.extract_photo_urls(zillow_url)
        
        if not photo_urls:
            print("\n⚠ No photos found. Exiting.")
            sys.exit(0)
        
        # Download photos
        photo_paths = analyzer.download_photos(photo_urls)
        
        if not photo_paths:
            print("\n⚠ No photos downloaded. Exiting.")
            sys.exit(0)
        
        # Filter relevant photos
        relevant_photos = analyzer.filter_relevant_photos(photo_paths)
        
        if not relevant_photos:
            print("\n⚠ No relevant photos found. Exiting.")
            sys.exit(0)
        
        # Analyze WFH suitability
        analysis = analyzer.analyze_wfh_suitability(relevant_photos)
        
        if analysis:
            # Update sheet
            analyzer.update_sheet_with_analysis(address, analysis)
            
            print("\n" + "="*80)
            print("✅ COMPLETE!")
            print("="*80)
            print(f"\n✓ Analyzed {len(relevant_photos)} relevant photos")
            print(f"✓ Updated Google Sheet with WFH scores")
            print("\nNext steps:")
            print("  - Review the scores in your sheet")
            print("  - Run: python main.py --analyze-new")
            print("  - This will incorporate the analysis into overall scores")
        
    except KeyboardInterrupt:
        print("\n\n⚠ Cancelled by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        analyzer.cleanup()


if __name__ == '__main__':
    main()
