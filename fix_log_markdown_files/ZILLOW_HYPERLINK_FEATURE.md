# Zillow URL Hyperlink Feature

## Summary

Added support for embedding Zillow URLs as clickable hyperlinks in the Google Sheets Address column. This gives you the best of both worlds: manual data entry with easy access to full listing details.

## What Changed

### Web Interface (`web_app.py`)
- Added "Zillow URL" field at the top of the form (recommended)
- When both Zillow URL and Address are provided, the address becomes a clickable hyperlink in Google Sheets
- Uses Google Sheets `HYPERLINK()` formula: `=HYPERLINK("zillow_url", "address")`
- If no Zillow URL is provided, address is stored as plain text

### Terminal Interface (`manual_entry.py`)
- Updated to also create hyperlinked addresses
- Maintains same functionality as web interface

### HTML Form (`templates/entry_form.html`)
- Reordered fields: Zillow URL now appears first (before address)
- Added helpful tooltip: "💡 Paste the Zillow link here - it will be embedded in the address for easy access to photos and details"
- Changed section heading from "Basic Information" to "Listing Information" and "Property Details"

### Documentation
- **README.md**: Updated workflow to mention Zillow URL as step 1
- **WEB_INTERFACE_GUIDE.md**: Added Zillow URL to workflow, updated tips section

## Benefits

✅ **Easy Access to Photos**: Click address in Google Sheets → Opens Zillow listing  
✅ **Check Availability**: Quickly see if listing is still active  
✅ **Read Full Description**: No need to re-search for the listing  
✅ **Share Links**: Easy to share specific listings with your partner  
✅ **No Scraping**: Manually view the page, no anti-bot issues  
✅ **Optional**: Works with or without Zillow URL  

## How It Works

### In Google Sheets:

**With Zillow URL:**
```
Cell displays: 123 Mission St, San Francisco, CA (underlined, clickable)
Cell formula: =HYPERLINK("https://zillow.com/...", "123 Mission St, San Francisco, CA")
Click → Opens Zillow listing in new tab
```

**Without Zillow URL:**
```
Cell displays: 123 Mission St, San Francisco, CA (plain text)
Cell value: 123 Mission St, San Francisco, CA
```

## Example Workflow

1. **Find apartment on Zillow**
2. **Copy URL** (e.g., `https://www.zillow.com/homedetails/123-Mission-St-San-Francisco-CA/12345_zpid/`)
3. **Open web interface** (`python web_app.py`)
4. **Paste Zillow URL** in first field
5. **Enter address** (or paste from Zillow)
6. **Fill in details** (price, beds, parking, etc.)
7. **Submit**
8. **Check Google Sheets** - Address is now clickable!
9. **Later**: Click address in Sheets to review photos or check if still available

## Technical Details

### Google Sheets HYPERLINK Formula

```
=HYPERLINK(url, [label])
```

- `url`: The Zillow listing URL
- `label`: The address text to display

Example:
```
=HYPERLINK("https://www.zillow.com/homedetails/123-Mission-St-San-Francisco-CA-94103/12345_zpid/", "123 Mission St, San Francisco, CA 94103")
```

### Why Not Just Store URLs?

**Option 1: URL in separate column** ❌
- Takes up extra column space
- Need to look in two places
- Harder to share/read

**Option 2: Store URL instead of address** ❌
- Can't read address at a glance
- Hard to compare apartments
- Breaks sorting/filtering

**Option 3: Hyperlinked address** ✅
- Best of both worlds!
- Readable AND clickable
- Clean, professional look
- Easy to work with

## Compatibility

- ✅ Google Sheets (native support for HYPERLINK)
- ✅ Excel (HYPERLINK formula works)
- ✅ CSV export (stores as formula text)
- ⚠️ Plain text tools (will see formula, not rendered link)

## Future Enhancements

Potential additions:
- Auto-extract address from Zillow URL (using page metadata)
- Validate Zillow URL format
- Show preview thumbnail of listing
- Track price changes over time by re-visiting URL
- Batch import from multiple Zillow URLs

---

**Bottom Line**: You get easy access to full listing details while keeping your spreadsheet clean and readable! 🎉

