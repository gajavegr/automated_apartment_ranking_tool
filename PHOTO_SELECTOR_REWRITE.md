# Photo Selector - Automated Rewrite Summary

## What Changed

The photo selector has been completely rewritten from a **manual screenshot tool** to a **fully automated analyzer**.

### Old Approach ❌
- Open browser window
- User manually clicks through photos
- Press 'S' to screenshot current view
- Screenshots were often cropped/partial
- Tedious and time-consuming

### New Approach ✅
- **Fully automated** - no user interaction needed
- Extracts all photo URLs from Zillow listing
- Downloads high-resolution versions
- **Uses Claude to filter relevant photos** (excludes closets, includes living rooms, etc.)
- Analyzes only WFH-relevant photos
- Updates Google Sheet automatically

## How It Works

### Step 1: Extract Photos
```python
# Scrapes Zillow page for all image URLs
# Gets high-res versions (1024x768)
# Filters out logos/icons
```

### Step 2: Download Photos
```python
# Downloads all photos to temp directory
# Handles JPEGs and PNGs
# Progress indicator
```

### Step 3: Filter Relevant Photos
```python
# Claude analyzes each photo
# Determines if relevant for WFH assessment
#
# RELEVANT: Living rooms, bedrooms, windows, kitchen, views, study areas
# NOT RELEVANT: Closets, hallways, storage, pure amenity photos
```

### Step 4: Analyze WFH Suitability
```python
# Claude Vision analyzes filtered photos
# Rates:
#   - Natural light (0-10)
#   - Desk space quality (0-10)
#   - Kitchen quality (0-10)
#   - View quality (0-10)
#   - Floor level (ground/mid/high)
#   - Double-pane windows (true/false)
#   - Study door type
#   - Street noise level (0-10)
```

### Step 5: Update Google Sheet
```python
# Automatically updates your sheet
# No manual data entry needed
```

## Usage

### Simple Command
```bash
python photo_selector.py "https://www.zillow.com/..." --address "Full Address"
```

### From Web App
1. Select apartment
2. Click "📸 Run Photo Analyzer"
3. Copy command
4. Paste in terminal
5. Wait for completion

## Benefits

✅ **Fully automated** - no manual clicking  
✅ **Smart filtering** - only analyzes relevant photos  
✅ **High-resolution** - uses best quality images  
✅ **Accurate** - analyzes actual listing photos, not screenshots  
✅ **Fast** - processes all photos in one go  
✅ **Headless** - runs in background, no browser window  

## Technical Details

### Dependencies
- `playwright` - Web scraping
- `anthropic` - Claude Vision API
- `requests` - Photo downloads
- `gspread` - Google Sheets updates

### API Calls
- 1x Claude call to filter photos (vision + text)
- 1x Claude call to analyze WFH suitability (vision + text)

### Cost Estimate
- ~$0.15-0.30 per apartment (depending on photo count)
- Claude Sonnet 3.5 vision pricing

## Example Output

```
================================================================================
🏠 AUTOMATED PHOTO EXTRACTOR
================================================================================

Extracting photos from: https://www.zillow.com/...
✓ Navigating to listing...
✓ Extracting image URLs...
✓ Found 24 photos

================================================================================
📥 DOWNLOADING 24 PHOTOS
================================================================================

✓ Downloaded 24 photos successfully

================================================================================
🔍 FILTERING RELEVANT PHOTOS
================================================================================

Asking Claude to identify photos relevant for WFH analysis...
✓ Photo 1: RELEVANT (living room)
✗ Photo 2: Not relevant (closet)
✓ Photo 3: RELEVANT (windows/view)
...
✓ Filtered to 12/24 relevant photos

================================================================================
🧠 ANALYZING WFH SUITABILITY (12 photos)
================================================================================

🤖 Sending to Claude Vision for WFH analysis...

✓ Analysis complete!
NATURAL_LIGHT: 8/10
DESK_SPACE: 7/10
KITCHEN: 6/10
VIEW: 9/10
...

================================================================================
📊 UPDATING GOOGLE SHEET
================================================================================

✓ Found apartment in row 45
✓ Updated 8 columns with vision analysis

================================================================================
✅ COMPLETE!
================================================================================
```

## Alternative: Manual Rating

If you prefer to manually rate WFH attributes instead of using automated photo analysis:

1. Open your Google Sheet
2. Manually fill in these columns:
   - Natural Light
   - Desk Space Quality  
   - Kitchen Quality
   - View Quality
   - Floor Level
   - Double Pane Windows
   - Study Door Type
   - Street Noise Level
3. Run `python main.py --analyze-new` to calculate composite scores

The automated analyzer is optional - all WFH fields can be manually entered.

## Files Modified

1. `photo_selector.py` - Complete rewrite (650+ lines changed)
2. `templates/entry_form.html` - Updated helper text
3. `PHOTO_SELECTOR_REWRITE.md` - This documentation

## Next Steps

1. Test the new automated analyzer
2. If accuracy is good: use for all apartments
3. If accuracy is poor: manually rate WFH attributes instead
4. Claude will still generate composite scores from your data

