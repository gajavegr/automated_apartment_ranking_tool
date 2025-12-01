# Photo Analysis Tool - User Guide

## Overview

The interactive photo selector lets you manually select apartment photos from Zillow and analyze them with Claude Vision AI. This gives you subjective quality ratings without automated scraping.

## Setup

### 1. Install Playwright (if not already installed)

```bash
# Uncomment playwright in requirements.txt, then:
pip install playwright==1.40.0

# Install browser
playwright install chromium
```

### 2. Make sure you have your API keys

Check your `.env` file has:
- `ANTHROPIC_API_KEY` - For Claude Vision
- `GOOGLE_SHEET_ID` - For updating results
- Google Sheets credentials in `credentials/`

## Usage

### Quick Start

```bash
python photo_selector.py
```

You'll be prompted for:
1. **Zillow URL** - The listing you want to analyze
2. **Address** - The address as it appears in your Google Sheet

### Command Line Usage

```bash
# Provide URL as argument
python photo_selector.py "https://www.zillow.com/homedetails/..."

# You'll still be prompted for the address
```

## Workflow

### Step-by-Step

1. **Run the tool:**
   ```bash
   python photo_selector.py
   ```

2. **Enter Zillow URL:**
   ```
   Enter the Zillow URL:
   > https://www.zillow.com/homedetails/123-Mission-St/12345_zpid/
   ```

3. **Enter Address:**
   ```
   Enter the apartment address (as it appears in your Google Sheet):
   > 123 Mission St, San Francisco, CA 94103
   ```

4. **Browser opens automatically:**
   - Zillow listing loads
   - Photo gallery may open automatically
   - If not, click on photos to open gallery

5. **Select photos:**
   - Navigate through photos (use arrow keys or click)
   - Press **S** to save current photo for analysis
   - Press **Q** when you're done selecting

6. **Analysis happens:**
   - Photos are sent to Claude Vision
   - AI analyzes each photo
   - Results are displayed in terminal

7. **Sheet updates:**
   - Results automatically written to your Google Sheet
   - Vision analysis fields populated

8. **Run main analysis:**
   ```bash
   python main.py --analyze-new
   ```
   This incorporates the vision data into your final scores

## Controls

While browser is open:

- **S** - Save current photo for analysis
- **Q** - Quit and start analysis
- **Arrow Keys** - Navigate photos (in gallery view)
- **Click** - Navigate/open gallery manually

## What Gets Analyzed

Claude Vision rates:

1. **Natural Light** (0-10) - Window size, brightness
2. **Desk Space Quality** (0-10) - WFH suitability
3. **Kitchen Quality** (0-10) - Appliances, counter space
4. **View Quality** (0-10) - What you see from windows
5. **Floor Level** - ground/mid/high
6. **Double-Pane Windows** - true/false
7. **Study Door Type** - solid/hollow/sliding/open/none
8. **Street Noise Level** (0-10) - Based on visible location
9. **Parking Visible** - What type of parking seen
10. **Summary** - Brief overall impression

## Tips

### Photo Selection Strategy

**Essential Photos (always include):**
- Living room (shows natural light, space)
- Kitchen (obvious)
- Bedroom or potential office space (WFH assessment)
- Windows showing the view (view quality, noise)
- Bathroom (shows quality/condition)

**Nice to Have:**
- Building exterior (shows floor level)
- Parking area (if visible)
- Multiple angles of main rooms
- Window close-ups (check for double-pane)

**Skip:**
- Duplicate angles
- Decorative/staging photos with no info
- Very dark or blurry photos

### Recommended: 5-10 Photos

- Too few (<3): Incomplete analysis
- Good range (5-10): Balanced accuracy
- Too many (>15): Expensive, diminishing returns

## Costs

Claude Vision pricing (as of Dec 2024):
- ~$0.50-1.50 per apartment (5-10 photos)
- Cached in Google Sheets (only pay once per apartment)

## Troubleshooting

### "Browser won't open"

```bash
# Reinstall Playwright browser
playwright install chromium
```

### "Can't find apartment in sheet"

Make sure the address you enter **exactly matches** what's in your Google Sheet:
- Copy/paste from your sheet
- Include full address with city, state, ZIP

### "Photos don't save"

- Try clicking on a photo first to focus it
- Make sure you press 'S' (not 's' with shift)
- Check terminal for error messages

### "Gallery won't open automatically"

That's fine! Just:
1. Manually click on photos
2. Navigate through them
3. Press 'S' to save each one

### "Analysis fails"

Check:
- `.env` has `ANTHROPIC_API_KEY`
- You have API credits in your Anthropic account
- Photos were actually saved (check terminal output)

## Example Session

```
$ python photo_selector.py

================================================================================
🖼️  APARTMENT PHOTO ANALYZER
================================================================================

This tool lets you:
1. Open a Zillow listing in your browser
2. Manually select which photos to analyze
3. Send them to Claude Vision for intelligent analysis
4. Update your Google Sheet with the results

Enter the Zillow URL:
> https://www.zillow.com/homedetails/123-Mission-St-San-Francisco-CA-94103/12345_zpid/

Enter the apartment address (as it appears in your Google Sheet):
> 123 Mission St, San Francisco, CA 94103

================================================================================
INTERACTIVE PHOTO SELECTOR
================================================================================

Opening: https://www.zillow.com/homedetails/...

Instructions:
1. Browser will open to the Zillow listing
2. Click through the photo gallery
3. For each photo you want to analyze, press 'S' (Save)
4. When done, press 'Q' (Quit)

Press Enter to continue...

✓ Browser opened
✓ Navigating to listing...
✓ Page loaded!

--------------------------------------------------------------------------------
CONTROLS:
--------------------------------------------------------------------------------
  [S] = Save current photo for analysis
  [Q] = Quit and analyze selected photos
  [Arrow Keys] = Navigate through photos (if gallery open)
--------------------------------------------------------------------------------

[Press S to save current photo, Q to finish] Selected: 0

✓ Saved photo 1: photo_1.png
✓ Saved photo 2: photo_2.png
✓ Saved photo 3: photo_3.png
✓ Saved photo 4: photo_4.png
✓ Saved photo 5: photo_5.png

✓ Finished selecting photos

================================================================================
ANALYZING 5 PHOTOS WITH CLAUDE VISION
================================================================================

Loading photo 1/5...
Loading photo 2/5...
Loading photo 3/5...
Loading photo 4/5...
Loading photo 5/5...

🤖 Sending to Claude for analysis...

✓ Analysis complete!

--------------------------------------------------------------------------------
RESULTS:
--------------------------------------------------------------------------------
NATURAL_LIGHT: 8/10
DESK_SPACE: 7/10
KITCHEN: 6/10
VIEW: 7/10
FLOOR_LEVEL: mid
DOUBLE_PANE: true
DOOR_TYPE: solid_door
NOISE: 4/10
PARKING: street_parking
SUMMARY: Bright apartment with good natural light and decent WFH space...
--------------------------------------------------------------------------------

================================================================================
UPDATING GOOGLE SHEET
================================================================================

✓ Found apartment in row 5
✓ Updated 8 columns with vision analysis

✓ Cleaned up temporary files

================================================================================
✅ COMPLETE!
================================================================================

✓ Analyzed 5 photos
✓ Updated Google Sheet

Next steps:
  - Run: python main.py --analyze-new
  - This will incorporate the vision analysis into your scores
```

## Integration with Main Tool

After using photo selector:

1. **Vision data is in your sheet** - Natural light, desk space, etc.
2. **Run main analysis:**
   ```bash
   python main.py --analyze-new
   ```
3. **This calculates final scores** using vision data + location data
4. **Check your visualizations** in Google Sheets

## Privacy & Cleanup

- Photos are saved to a **temporary directory**
- Automatically deleted after analysis
- Only analysis results are kept (in Google Sheet)
- No photos are uploaded or stored permanently

## When to Use This

**Use photo selector when:**
- ✅ You want subjective quality ratings
- ✅ WFH space quality is important
- ✅ Natural light matters
- ✅ You're comparing similar apartments

**Skip photo analysis when:**
- ❌ You've already toured (you know the quality)
- ❌ Budget is tight (save the API costs)
- ❌ You're only filtering on location/price

---

**Happy analyzing! 📸✨**

