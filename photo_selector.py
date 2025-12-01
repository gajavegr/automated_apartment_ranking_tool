#!/usr/bin/env python3
"""
Interactive photo selector for apartment analysis

Opens Zillow listing in a browser, lets you select photos to analyze,
then sends them to Claude Vision for analysis.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any
import base64

from playwright.sync_api import sync_playwright, Page, Browser
from anthropic import Anthropic

import config
from utils.google_sheets import GoogleSheetsClient


class PhotoSelector:
    """Interactive tool for selecting and analyzing apartment photos"""
    
    def __init__(self):
        self.anthropic_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.temp_dir = tempfile.mkdtemp(prefix="apartment_photos_")
        self.selected_photos = []
        
    def select_photos_interactive(self, zillow_url: str) -> List[str]:
        """
        Open Zillow listing in browser and let user select photos
        
        Args:
            zillow_url: URL of Zillow listing
            
        Returns:
            List of paths to downloaded photos
        """
        print("\n" + "="*80)
        print("INTERACTIVE PHOTO SELECTOR")
        print("="*80)
        print(f"\nOpening: {zillow_url}")
        print("\nInstructions:")
        print("1. Browser will open to the Zillow listing")
        print("2. Click through the photo gallery")
        print("3. For each photo you want to analyze, press 'S' (Save)")
        print("4. When done, press 'Q' (Quit)")
        print("\nPress Enter to continue...")
        input()
        
        with sync_playwright() as p:
            # Launch browser (not headless so user can interact)
            browser = p.chromium.launch(headless=False, args=['--start-maximized'])
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=config.ZILLOW_USER_AGENT if hasattr(config, 'ZILLOW_USER_AGENT') else None
            )
            page = context.new_page()
            
            try:
                print(f"\n✓ Browser opened")
                print(f"✓ Navigating to listing...")
                
                # Navigate to Zillow
                page.goto(zillow_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)
                
                print(f"\n✓ Page loaded!")
                print("\n" + "-"*80)
                print("CONTROLS:")
                print("-"*80)
                print("  [S] = Save current photo for analysis")
                print("  [Q] = Quit and analyze selected photos")
                print("  [Arrow Keys] = Navigate through photos (if gallery open)")
                print("-"*80)
                print(f"\nPhotos selected: 0")
                
                # Try to find and click the main image to open gallery
                self._try_open_gallery(page)
                
                # Wait for user input
                photo_count = 0
                while True:
                    print(f"\n[Press S to save current photo, Q to finish] Selected: {photo_count}", end='\r')
                    
                    # Get keyboard input (non-blocking)
                    key = self._get_user_input()
                    
                    if key == 'q':
                        print("\n\n✓ Finished selecting photos")
                        break
                    elif key == 's':
                        # Screenshot current view
                        photo_path = os.path.join(self.temp_dir, f"photo_{photo_count + 1}.png")
                        
                        # Try to screenshot just the main image
                        try:
                            # Look for common Zillow image selectors
                            image_selectors = [
                                'img[class*="media-stream-photo"]',
                                'img[class*="ldb-media-browser"]',
                                'picture img',
                                '.media-stream img',
                            ]
                            
                            screenshot_taken = False
                            for selector in image_selectors:
                                try:
                                    element = page.query_selector(selector)
                                    if element and element.is_visible():
                                        element.screenshot(path=photo_path)
                                        screenshot_taken = True
                                        break
                                except:
                                    continue
                            
                            if not screenshot_taken:
                                # Fallback: full page screenshot
                                page.screenshot(path=photo_path)
                            
                            photo_count += 1
                            self.selected_photos.append(photo_path)
                            print(f"\n✓ Saved photo {photo_count}: {os.path.basename(photo_path)}")
                            
                        except Exception as e:
                            print(f"\n✗ Error saving photo: {e}")
                
            except Exception as e:
                print(f"\n✗ Error: {e}")
                return []
            finally:
                browser.close()
        
        return self.selected_photos
    
    def _try_open_gallery(self, page: Page):
        """Try to open the photo gallery"""
        try:
            # Common Zillow selectors for opening photo gallery
            gallery_selectors = [
                'button[data-test="home-detail-lightbox-trigger"]',
                'button[class*="MediaGallery"]',
                '.media-stream',
                'picture',
            ]
            
            for selector in gallery_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        element.click()
                        page.wait_for_timeout(1000)
                        print("✓ Photo gallery opened")
                        return
                except:
                    continue
        except:
            pass
    
    def _get_user_input(self) -> str:
        """Get single character input from user (cross-platform)"""
        try:
            import msvcrt
            # Windows
            if msvcrt.kbhit():
                return msvcrt.getch().decode('utf-8').lower()
        except ImportError:
            # Unix/Mac
            import select
            import sys
            import tty
            import termios
            
            if select.select([sys.stdin], [], [], 0.1)[0]:
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setraw(sys.stdin.fileno())
                    char = sys.stdin.read(1).lower()
                    return char
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        
        return ''
    
    def analyze_photos(self, photo_paths: List[str]) -> Dict[str, Any]:
        """
        Analyze selected photos with Claude Vision
        
        Args:
            photo_paths: List of paths to photo files
            
        Returns:
            Dictionary with analysis results
        """
        if not photo_paths:
            print("\n⚠ No photos selected for analysis")
            return {}
        
        print(f"\n{'='*80}")
        print(f"ANALYZING {len(photo_paths)} PHOTOS WITH CLAUDE VISION")
        print(f"{'='*80}")
        
        # Prepare images for Claude
        image_contents = []
        for i, path in enumerate(photo_paths, 1):
            print(f"\nLoading photo {i}/{len(photo_paths)}...")
            with open(path, 'rb') as f:
                image_data = base64.standard_b64encode(f.read()).decode('utf-8')
                image_contents.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data
                    }
                })
        
        # Create prompt for Claude
        prompt = """Analyze these apartment photos and provide ratings for the following:

1. **Natural Light** (0-10): How much natural light? Are there windows? What's the window size?

2. **Desk Space Quality** (0-10): Is there good space for a work-from-home desk? 
   - Look for: Areas near windows, quiet corners, dedicated rooms
   - Consider: Natural light, space size, noise isolation

3. **Kitchen Quality** (0-10): How nice is the kitchen?
   - Look for: Appliances, counter space, storage, condition

4. **View Quality** (0-10): What's the view like from windows?
   - Rate: City views, nature, open sky = high; walls, parking lots = low

5. **Floor Level**: Based on windows/views, estimate: "ground", "mid", or "high"

6. **Double-Pane Windows**: Can you tell if windows are double-pane? (true/false)
   - Look for: Thickness in window frames, reflections, modern construction

7. **Study Door Type**: If there's a potential study/office area, what's the door situation?
   - Options: "solid_door", "hollow_door", "sliding_door", "open", "none"

8. **Street Noise Level** (0-10): Based on windows and location visible, how noisy might it be?
   - 0 = very quiet, 10 = very loud street traffic

9. **Parking Visible**: Can you see parking? What type?
   - Options: "single_garage", "dedicated_spot", "street_parking", "none"

10. **Overall Impression**: Brief summary of apartment quality

Please respond in this exact format:
NATURAL_LIGHT: [score]/10
DESK_SPACE: [score]/10
KITCHEN: [score]/10
VIEW: [score]/10
FLOOR_LEVEL: [ground/mid/high]
DOUBLE_PANE: [true/false]
DOOR_TYPE: [solid_door/hollow_door/sliding_door/open/none]
NOISE: [score]/10
PARKING: [type]
SUMMARY: [2-3 sentences]"""

        try:
            # Call Claude API
            print("\n🤖 Sending to Claude for analysis...")
            
            message = self.anthropic_client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                temperature=config.CLAUDE_TEMPERATURE,
                messages=[{
                    "role": "user",
                    "content": image_contents + [{
                        "type": "text",
                        "text": prompt
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
            'parking_visible': 'none',
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
            elif line.startswith('PARKING:'):
                parking = line.split(':')[1].strip().lower()
                results['parking_visible'] = parking
            elif line.startswith('SUMMARY:'):
                results['summary'] = line.split(':', 1)[1].strip()
        
        return results
    
    def update_sheet_with_analysis(self, address: str, analysis: Dict[str, Any]):
        """Update Google Sheet with vision analysis results"""
        try:
            print(f"\n{'='*80}")
            print("UPDATING GOOGLE SHEET")
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
    print("\n" + "="*80)
    print("🖼️  APARTMENT PHOTO ANALYZER")
    print("="*80)
    print("\nThis tool lets you:")
    print("1. Open a Zillow listing in your browser")
    print("2. Manually select which photos to analyze")
    print("3. Send them to Claude Vision for intelligent analysis")
    print("4. Update your Google Sheet with the results")
    
    # Get Zillow URL
    if len(sys.argv) > 1:
        zillow_url = sys.argv[1]
    else:
        print("\nEnter the Zillow URL:")
        zillow_url = input("> ").strip()
    
    if not zillow_url:
        print("✗ No URL provided")
        sys.exit(1)
    
    # Get address for sheet lookup
    print("\nEnter the apartment address (as it appears in your Google Sheet):")
    address = input("> ").strip()
    
    if not address:
        print("✗ No address provided")
        sys.exit(1)
    
    # Initialize selector
    selector = PhotoSelector()
    
    try:
        # Select photos
        photo_paths = selector.select_photos_interactive(zillow_url)
        
        if not photo_paths:
            print("\n⚠ No photos selected. Exiting.")
            sys.exit(0)
        
        # Analyze
        analysis = selector.analyze_photos(photo_paths)
        
        if analysis:
            # Update sheet
            selector.update_sheet_with_analysis(address, analysis)
            
            print("\n" + "="*80)
            print("✅ COMPLETE!")
            print("="*80)
            print(f"\n✓ Analyzed {len(photo_paths)} photos")
            print(f"✓ Updated Google Sheet")
            print("\nNext steps:")
            print("  - Run: python main.py --analyze-new")
            print("  - This will incorporate the vision analysis into your scores")
        
    except KeyboardInterrupt:
        print("\n\n⚠ Cancelled by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        selector.cleanup()


if __name__ == '__main__':
    main()

