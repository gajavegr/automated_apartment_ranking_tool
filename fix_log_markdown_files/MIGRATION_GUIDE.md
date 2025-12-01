# Migration Guide: From Zillow Scraping to Manual Entry

## For Existing Users

If you were using the Zillow scraping version, here's how to migrate to the new manual entry system.

## What Changed?

**Old System:**
- Paste Zillow URLs → Automatic scraping → Analysis
- Often blocked by Zillow (HTTP 403)
- Required Playwright browser

**New System:**
- Web interface → Manual entry → Analysis
- 100% reliable, no blocking
- No browser automation needed

## Migration Steps

### 1. Update Dependencies

```bash
# Activate your virtual environment
source venv/bin/activate  # On Mac/Linux
# or
venv\Scripts\activate  # On Windows

# Update packages
pip install -r requirements.txt
```

**Note:** Playwright is no longer required! You can uninstall it if you want:
```bash
pip uninstall playwright
```

### 2. Update Your Google Sheet

**Before:** Sheet had "Zillow URL" in column A

**After:** Sheet needs these columns (web interface will fill them):
- Address (column A)
- Monthly Rent (column B)
- Bedrooms (column C)
- Bathrooms (column D)
- Square Feet (column E)
- Parking Type (column F)
- Laundry Type (column G)
- Rent Control Eligible (column H)
- Neighborhood (column I)
- Manual Safety Rating (column J)

**Action:** Run this to initialize your sheet with the correct structure:
```bash
python main.py --init-sheets
```

### 3. Re-enter Your Apartments

For each apartment you were tracking:

1. **Start the web interface:**
   ```bash
   python web_app.py
   ```

2. **Copy data from Zillow manually:**
   - Open Zillow listing
   - Copy address, price, beds, baths from listing
   - Paste into web form
   - Fill in parking/laundry from listing details

3. **Visual confirmation:**
   - Maps will show you the location
   - Street View lets you assess the neighborhood
   - Adjust safety rating based on what you see

4. **Submit:**
   - Click "Add Apartment"
   - Apartment is added to your Google Sheet

5. **Repeat** for all ~20 apartments (takes ~2-3 minutes each)

### 4. Run Analysis

Once all apartments are entered:

```bash
python main.py --analyze-new
```

This will:
- Calculate commute times ✓
- Fetch safety scores ✓
- Find nearby amenities ✓
- Score each apartment ✓
- Generate visualizations ✓

## What You Gain

✅ **No More Blocking** - Zillow can't stop you  
✅ **Faster** - 2-3 min per apartment vs. scraping failures  
✅ **Better UX** - Visual maps and street view  
✅ **More Reliable** - No website changes breaking scraper  
✅ **Lower Costs** - No photo scraping overhead  

## What You Lose

❌ **Automatic scraping** - But it rarely worked anyway!  
❌ **Photo analysis** - Can be added back later as optional upload feature  

## FAQ

**Q: Can I keep my old data?**  
A: Yes! The analysis columns are the same. Just re-enter the basic info via web interface.

**Q: Do I need to re-analyze apartments I already analyzed?**  
A: Only if you want updated commute times or safety scores. The cache will prevent redundant API calls.

**Q: What about the photos I had downloaded?**  
A: You can delete the `photos_cache/` directory - it's no longer used.

**Q: Is photo analysis gone forever?**  
A: No! The `vision_analyzer.py` code still exists. We can add photo upload to the web interface later.

**Q: Will this tool still update?**  
A: Yes! This is a more maintainable codebase focused on what works best: smart analysis with manual entry.

## Need Help?

Check the README.md for full documentation or open an issue!

