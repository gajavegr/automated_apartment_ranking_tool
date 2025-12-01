# Web Interface Quick Start Guide

## Starting the Web Interface

1. **Make sure Flask is installed:**
   ```bash
   pip install Flask==3.0.0
   ```

2. **Start the web server:**
   ```bash
   python web_app.py
   ```

3. **Your browser will automatically open** to `http://localhost:5000`

## Using the Interface

### Layout

```
┌─────────────────────┬───────────────────┐
│                     │                   │
│  📝 Entry Form      │  📍 Street View   │
│                     │                   │
│  • Address          │  (Live panorama)  │
│  • Price            │                   │
│  • Beds/Baths       ├───────────────────┤
│  • Parking (dropdown)│                  │
│  • Laundry (dropdown)│  🗺️ Map         │
│  • Safety slider    │  (Interactive)    │
│                     │                   │
│  [Submit Button]    │                   │
└─────────────────────┴───────────────────┘
```

### Step-by-Step Workflow

1. **Enter Zillow URL (Recommended):**
   - Paste the Zillow listing URL
   - This will be embedded as a hyperlink in your sheet
   - Click the address in Google Sheets to view photos, description, and check availability

2. **Enter Address:**
   - Start typing the apartment address
   - Autocomplete suggestions will appear
   - Select the correct address from suggestions

3. **View Location:**
   - Street View automatically updates
   - Interactive map shows location
   - Pan around in Street View to see neighborhood

4. **Fill in Details:**
   - Monthly rent (required)
   - Bedrooms/Bathrooms (required)
   - Square feet (optional but recommended)
   - Parking type (dropdown - no typing errors!)
   - Laundry type (dropdown)
   - Your safety rating (slider 0-10)
   - Neighborhood name (optional)
   - Year built (optional, for rent control)

5. **Submit:**
   - Click "Add Apartment"
   - Success message appears
   - Form clears for next entry

6. **Repeat** for all apartments

7. **Run Analysis:**
   ```bash
   python main.py --analyze-new
   ```

## Features

### ✅ No Typing Errors
- Address: Autocomplete with validation
- Parking/Laundry: Dropdown menus
- Safety: Slider (no out-of-range values)

### 🗺️ Visual Context
- See actual Street View before rating safety
- Confirm you have the right location
- Pan around to see neighborhood

### ⚡ Fast Workflow
- Average time per apartment: ~2 minutes
- Much faster than terminal entry
- No re-typing if you make mistakes

### 📊 Real-time Updates
- Maps update as you type
- Coordinates shown for verification
- Instant validation feedback

## After Adding Apartments

Run the analysis to fill in:
- Commute times (to your work and partner's)
- Safety scores (SF crime data)
- Nearby amenities (gyms, restaurants, cafes)
- Final weighted scores
- Criteria matrix

```bash
python main.py --analyze-new
```

This will:
1. Skip Zillow scraping (you already have the data!)
2. Calculate all location-based scores
3. Apply your scoring formula
4. Update Google Sheets with results
5. Generate visualizations

## Tips

- **Zillow URL First** - Paste Zillow link first, then the address becomes a clickable link in Sheets
- **Keep Zillow open** in another tab for easy copy-paste
- **Use Street View** to assess safety and neighborhood quality
- **Year built matters** - pre-1979 = rent control in SF
- **Be consistent** with parking categories across apartments
- **Save often** - each submission goes directly to Google Sheets
- **Click addresses in Google Sheets** to jump back to the Zillow listing anytime

## Troubleshooting

**Maps not loading?**
- Check `.env` has `GOOGLE_MAPS_API_KEY` set
- Ensure Maps JavaScript API is enabled
- Check browser console (F12) for errors

**Form won't submit?**
- Fill in all required fields (marked with *)
- Make sure address is selected from autocomplete
- Check browser console for errors

**Port 5000 already in use?**
```bash
lsof -ti:5000 | xargs kill -9
python web_app.py
```

---

**Happy apartment hunting! 🏠**

