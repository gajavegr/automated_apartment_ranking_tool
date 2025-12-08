# Photo Selector - Playwright Fix Summary

## Problem Identified
The Playwright-bundled Chromium browser was **crashing with a SIGSEGV (segmentation fault)** on your macOS system. This caused the browser to close immediately after launch, before any page could be created.

### Error Signature
```
Received signal 11 SEGV_ACCERR 000100000008
[process did exit: exitCode=null, signal=SIGSEGV]
```

## Root Cause
The Chromium binary bundled with Playwright (version 120.0.6099.28) is incompatible with your specific macOS system, causing a memory access violation crash.

## Solution Implemented
Updated `photo_selector.py` to use **system Chrome** instead of Playwright's bundled Chromium:

```python
browser = p.chromium.launch(
    headless=False,
    channel="chrome",  # Use system Chrome
)
```

## What Changed

### In `photo_selector.py`:
1. **Browser launch now uses system Chrome** via `channel="chrome"`
2. **Fallback to system Chromium** if Chrome isn't available
3. **Clear error message** if neither system browser is found
4. **Removed complex launch flags** that were unnecessary

### In `templates/entry_form.html`:
1. **Fixed address placeholder** in photo selector helper text
2. **Now shows actual address** instead of `<address>` placeholder
3. **Command text matches what gets copied** to clipboard

## Testing
✅ System Chrome launches successfully
✅ Page creation works
✅ Browser stays open
✅ Ready for interactive photo selection

## How to Use

### Method 1: From Web App
1. Open the web app
2. Select an apartment
3. Click "📸 Run Photo Analyzer"
4. Copy the command (now includes the correct address)
5. Paste and run in terminal

### Method 2: Direct Command
```bash
python photo_selector.py "https://www.zillow.com/homedetails/..." --address "Full Address"
```

### Method 3: Quick Test
```bash
./test_photo_selector_quick.sh
```

## Requirements
- **Google Chrome** must be installed on your system
  - Most Macs already have this
  - If not: https://www.google.com/chrome/
- **Alternative**: System Chromium (`brew install chromium`)

## Files Modified
1. `photo_selector.py` - Updated browser launch logic
2. `templates/entry_form.html` - Fixed address in helper text
3. `test_playwright_debug.py` - Created (diagnostic tool)
4. `test_photo_selector_quick.sh` - Created (quick test script)

## Debug Output
The script now includes detailed `[DEBUG]` logging that shows:
- Browser launch success/failure
- Which browser is being used (system Chrome vs bundled)
- Page creation steps
- Navigation progress

## Next Steps
1. Run the photo_selector with your Zillow URL
2. Press Enter when prompted
3. Chrome will open to the listing
4. Press 'S' to save photos you want to analyze
5. Press 'Q' when done
6. Claude Vision will analyze the selected photos
7. Results will be saved to your Google Sheet

## Troubleshooting
If you still have issues:
1. Make sure Google Chrome is installed and up to date
2. Run `./test_photo_selector_quick.sh` to test with a simple page
3. Check the [DEBUG] output for specific errors
4. The browser window should now actually appear on screen!

