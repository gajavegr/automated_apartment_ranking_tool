# Apartment Value Analyzer

An intelligent tool that helps you find the best apartment deals by automatically analyzing your apartment candidates, scoring them based on your priorities, and visualizing the results in Google Sheets.

## Features

- **Web-Based Manual Entry**: Beautiful interface with Google Maps integration for easy data input
- **Optional Photo Analysis**: Interactive tool to select and analyze apartment photos with AI
- **Location Intelligence**: Calculates commute times, analyzes neighborhood safety using SF crime data, and finds nearby amenities
- **Flexible Scoring System**: Composable scoring with configurable weights and priorities
- **Dual Visualization**: 
  - Scatter plot showing price vs. value
  - Criteria matrix showing which apartments meet your "ideal" thresholds
- **Smart Caching**: Avoids redundant API calls
- **Google Sheets Integration**: All data automatically synced for easy sharing and editing

## How It Works

1. **Input**: Add apartments via web interface (with Google Maps for visual context)
2. **Analysis**: The tool automatically:
   - Calculates commute times to your work and partner's work
   - Checks neighborhood safety using SF crime statistics
   - Finds nearby gyms, restaurants, cafes, and parks
   - Scores the apartment based on your priorities
3. **Output**: All analysis results written back to Google Sheets with:
   - Detailed scores for each category
   - Weighted total score (0-100)
   - Value ratio (score per $1k rent)
   - Checkmarks for which "ideal" criteria are met

## Installation

### Prerequisites

- Python 3.8+
- Google Cloud account (for Sheets API)
- Anthropic API key (for Claude)
- Google Maps API key

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd automated_apartment_scraper
```

### 2. Create and Activate Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

**Note:** This step is optional and only needed if you plan to use photo analysis features in the future.

```bash
# Only if you want photo analysis capability
playwright install chromium
```

**For now, skip this step** - the web interface doesn't require browser automation.

**Note:** Make sure your virtual environment is activated when running all commands!

### 5. Set Up API Credentials

#### Google Sheets API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Sheets API and Google Drive API
4. Create a service account:
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Give it a name and click "Create"
   - Grant it "Editor" role
   - Click "Done"
5. Create a key:
   - Click on the service account you just created
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose JSON format
   - Save the file as `credentials/google_sheets_credentials.json`
6. Copy the service account email (looks like `name@project.iam.gserviceaccount.com`)

#### Anthropic API

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in
3. Go to "API Keys"
4. Create a new API key
5. Copy the key (starts with `sk-ant-...`)

#### Google Maps API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. In the same project, go to "APIs & Services" > "Library"
3. Enable these APIs (this tool needs all 5):
   - **Geocoding API** (converts addresses to coordinates)
   - **Distance Matrix API** (calculates commute times)
   - **Places API** (finds nearby gyms, restaurants, etc.)
   - **Directions API** (determines commute routes)
   - **Street View Static API** (optional: for street parking analysis)
   - **Elevation API** (calculates terrain/hilliness for parking and gym scoring)
   - **Geocoding API** (converts addresses to coordinates)
4. Go to "Credentials"
5. Click "Create Credentials" > "API Key"
6. Copy the API key
7. **Restrict the key (IMPORTANT for security):**
   - Click on the key you just created
   - Under "API restrictions", select "Restrict key"
   - Check all 6 APIs listed above
   - Save
   - **Note**: Don't use IP restrictions - they don't work well for local development since IPs can change

### 6. Configure Environment Variables

Copy the example env file:

```bash
cp env.example .env
```

Edit `.env` and fill in your credentials:

```bash
# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_PATH=credentials/google_sheets_credentials.json
GOOGLE_SHEET_ID=<your-google-sheet-id>

# Anthropic Claude
ANTHROPIC_API_KEY=<your-anthropic-api-key>

# Google Maps
GOOGLE_MAPS_API_KEY=<your-google-maps-api-key>

# Work addresses (edit these!)
YOUR_WORK_ADDRESS=4100 E 3rd Ave, Foster City, CA 94404
PARTNER_WORK_ADDRESS=1355 Market St, San Francisco, CA 94103

# Optional: cross-environment data sync (see "Cross-environment data sync" below)
PEER_GOOGLE_SHEET_ID=
PEER_IS_MULTI_USER=false
PEER_ENV_LABEL=production
```

**Finding your Google Sheet ID:**
- Create a new Google Sheet or use existing one
- The URL looks like: `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`
- Copy the `SHEET_ID_HERE` part

**Important:** Share your Google Sheet with the service account email!
- Open your Google Sheet
- Click "Share"
- Paste the service account email
- Give it "Editor" permissions

### 7. Initialize the Google Sheet

```bash
python main.py --init-sheets
```

This will create three tabs:
- **Apartment Data**: Main data sheet with all analysis results
- **Price vs Score**: Scatter plot data
- **Criteria Matrix**: Binary criteria checkmarks

## Usage

### Quick Start with Web Interface

The easiest way to add apartments is using the web interface:

```bash
# Install Flask if you haven't already
pip install Flask==3.0.0

# Start the web interface
python web_app.py
```

Your browser will automatically open to `http://localhost:5000`. You'll see:

- **Left side**: Entry form with dropdowns (no typing errors!)
- **Right side**: Live Google Maps Street View and interactive map

**Workflow:**
1. Paste Zillow URL (recommended - becomes clickable link in Sheets)
2. Paste or type the apartment address (autocomplete suggestions appear)
3. Maps update automatically showing the location and Street View
4. Fill in remaining details (price, beds, parking, etc.)
5. Adjust safety rating based on what you see in Street View
6. Click "Add Apartment"
7. Repeat for other apartments

After adding apartments via web interface:

```bash
python main.py --analyze-new
```

This will calculate commute times, safety scores, nearby amenities, and final rankings.

### Multi-User Mode (username login)

The web app supports lightweight multi-user usage so several people can keep
their apartment lists, weights, and settings separate on one deployment.

**How it works:**

- Visiting the app lands on a **login page**. Enter a username to continue.
- **New users** register on the **Create User** page. Usernames must be unique
  (the check is case-insensitive).
- Once logged in, the app remembers you via a Flask session cookie, and every
  screen operates on *your* data only.
- Each user's data lives in its own set of Google Sheet tabs, namespaced as
  `<username> - Apartment Data`, `<username> - Settings`, etc. A global `Users`
  tab holds the registry of usernames. Shared reference data (the `Approved
  Gyms` cache) stays global so expensive lookups aren't duplicated per user.
- Use the **Log out** link in the header (next to your username) to switch users.

> ⚠️ **This is identification, not authentication.** There are no passwords —
> anyone who knows a username can access that user's data. It's a
> convenience/personalization layer, **not** a security boundary. Don't store
> anything sensitive.

**Session secret key:** set `FLASK_SECRET_KEY` to a stable random value in any
production / multi-worker deployment (see `env.example`). Without it, sessions
don't survive restarts and won't be shared across gunicorn workers, so users get
logged out unexpectedly. Generate one with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

For local single-process development the app falls back to a random key if
`FLASK_SECRET_KEY` is unset.

### Getting started walkthrough (onboarding)

The first time a user logs in, a short **Getting started** walkthrough opens
automatically. It introduces the main features and the recommended workflow:

1. **Set your preferences** (Preferences tab) — weight what matters to you.
2. **Add apartments** (Entry tab) — with Google Maps assist and optional AI
   photo analysis.
3. **Run analysis** (Analysis tab) — score every candidate.
4. **Review results** — price-vs-score scatter plot and criteria matrix.
5. **Adjust weights and iterate.**

Users can step through it, **Skip** it, or finish and jump straight to the
Preferences tab. It can be reopened anytime via the **❔ Getting started** button
in the top-right. Whether a user has completed or dismissed it is tracked
per-user in the `Users` tab (an `Onboarded At` column), so returning users
aren't shown it again automatically.

### Cross-environment data sync (prod ↔ staging)

If you run more than one deployment (e.g. a single-user **production** app and a
multi-user **staging** app), each has its *own* Google Sheet. A user who already
entered apartments in one environment can import them into the other without a
manual script.

Set `PEER_GOOGLE_SHEET_ID` to the **other** environment's sheet ID (the shared
service account is already an Editor on both, so no new credentials are needed):

```bash
PEER_GOOGLE_SHEET_ID=<the-other-environments-sheet-id>
PEER_IS_MULTI_USER=false   # true if the peer uses per-user namespaced tabs
PEER_ENV_LABEL=production   # friendly name shown in the UI
```

With this configured:

- On first load, if the peer environment has apartments you don't have yet, a
  banner offers to **import your existing data**.
- The **Admin → Cross-Environment Sync** section lets you re-check anytime. It
  shows a diff (only in peer / only here / present-in-both-but-different), lets
  you pick which apartments to import and resolve conflicts, then applies it.

Sync is **additive by default** (nothing here is deleted), **previewable** (the
diff is a dry run), and **idempotent** (re-running with no changes is a no-op).
Optionally it backs up your target tab before merging. Importing *from* the peer
into your own tabs is the supported direction; pushing into the peer is
intentionally disabled to avoid clobbering its data. Apartments are matched by
Zillow listing id (zpid) when available, otherwise by normalized address. Leave
`PEER_GOOGLE_SHEET_ID` unset to hide the feature entirely.

### Alternative: Terminal Interface

If you prefer the terminal (though the web interface is recommended):

```bash
python manual_entry.py
```

### Optional: Photo Analysis

Want AI to rate apartment quality from photos?

```bash
# Install Playwright (one-time setup)
pip install playwright==1.40.0
playwright install chromium

# Analyze photos for a specific apartment
python photo_selector.py
```

This opens the Zillow listing in a browser, you select which photos to analyze (press 'S'), and Claude Vision rates natural light, WFH space quality, kitchen, etc.

**See [PHOTO_ANALYSIS_GUIDE.md](PHOTO_ANALYSIS_GUIDE.md) for detailed instructions.**

### Command Options

Once you've added apartments, analyze them:

```bash
# Analyze only new apartments (no existing scores)
python main.py --analyze-new

# Analyze all apartments (including those with scores)
python main.py --analyze-all

# Re-analyze a specific row (force fresh data)
python main.py --reanalyze-row 5

# Update visualizations only (no analysis)
python main.py --update-visualizations

# Clear all cached data
python main.py --clear-cache

# Show cache statistics
python main.py --cache-stats

# Force refresh (ignore cache, re-scrape everything)
python main.py --analyze-all --force-refresh
```

## Configuration

Edit `config.py` to adjust:

### Scoring Weights

Adjust the importance of each category (must sum to ~1.0):

```python
SCORE_COMPONENTS = {
    "safety": {"weight": 0.25},      # 25% of total score
    "wfh_quality": {"weight": 0.20}, # 20%
    "commute": {"weight": 0.15},     # 15%
    "parking": {"weight": 0.15},     # 15%
    "laundry": {"weight": 0.08},     # 8%
    "gym_nearby": {"weight": 0.05},  # 5%
    "rent_control": {"weight": 0.05},# 5%
}
```

### Ideal Criteria Thresholds

Define what counts as "ideal" for the criteria matrix:

```python
IDEAL_CRITERIA = {
    "has_ideal_safety": {
        "condition": lambda scores: scores["combined_safety"] >= 8.0,
        "description": "Combined safety score ≥ 8/10"
    },
    "has_ideal_commute": {
        "condition": lambda scores: (
            scores["commute_duration"] <= 35 and 
            scores["commute_route"] == "280"
        ),
        "description": "≤35min commute on 280"
    },
    # ... more criteria
}
```

### Must-Have Requirements

Set absolute requirements (auto-reject if not met):

```python
MUST_HAVES = {
    "max_price": 4500,
    "max_commute_mins": 50,
    "min_safety_score": 5,
    "parking_required": "car",
}
```

### Commute Preferences

```python
"commute": {
    "preferences": {
        "ideal_duration": 30,         # Minutes - gets 10/10 score
        "acceptable_duration": 50,    # Minutes - linear decay
        "preferred_route": "280",     # Bonus points for this route
        "route_bonus": 1.5,          # Extra score for preferred route
    }
}
```

## Understanding the Scores

### Component Scores (0-10 scale)

- **Safety**: Average of your manual rating + SF crime data
- **WFH Quality**: Composite of natural light, desk space, quietness, kitchen, location vibe
- **Commute**: Based on duration and route preference (280 vs 101)
- **Parking**: Type (garage > dedicated spot > street) + distance + street ease
- **Laundry**: In-unit (10) > shared-good (7) > shared-poor (4) > none (0)
- **Gym**: Nearby + quality rating
- **Rent Control**: Protected (10) vs not protected (0)

### Weighted Score (0-100)

Sum of all component scores × their weights × 10

Example:
- Safety: 8.5/10 × 0.25 × 10 = 21.25 points
- WFH: 7.0/10 × 0.20 × 10 = 14.00 points
- Commute: 9.0/10 × 0.15 × 10 = 13.50 points
- ...
- **Total: 78.2/100**

### Value Ratio

`Weighted Score / (Monthly Rent / 1000)`

Higher is better. Helps identify good deals.

Example:
- Apartment A: 80 score, $4000/mo → Ratio = 80 / 4 = 20
- Apartment B: 70 score, $3000/mo → Ratio = 70 / 3 = 23.3 (better value!)

## Troubleshooting

### Web Interface Issues

**Port already in use:**
```bash
# Kill process on port 5000
lsof -ti:5000 | xargs kill -9
```

**Maps not loading:**
- Check that `GOOGLE_MAPS_API_KEY` is set in `.env`
- Ensure JavaScript API and Places API are enabled in Google Cloud Console
- Check browser console (F12) for error messages

### Google Sheets Issues

**"Google Sheets credentials not found"**

Make sure:
1. You've created the service account and downloaded the JSON key
2. The file is saved at `credentials/google_sheets_credentials.json`
3. The path in `.env` is correct

### "GOOGLE_SHEET_ID not set"

1. Open your Google Sheet in a browser
2. Copy the ID from the URL
3. Set it in `.env` file

### "Permission denied" when accessing sheet

1. Open your Google Sheet
2. Click "Share"
3. Add the service account email with Editor permissions

**API quota exceeded:**
1. Check your quota in Google Cloud Console
2. Enable billing if needed (Maps APIs have free tier, then paid)
3. Consider caching results longer (edit `CACHE_EXPIRE_HOURS` in config)

### Claude API rate limits

1. Check your Anthropic API tier limits
2. Add delays between analysis runs
3. Use cache when possible

## Data Privacy

- All data is stored locally and in your Google Sheet
- No data is sent to third parties except:
  - Google Maps API (geocoding, directions, places)
  - Anthropic Claude API (optional photo analysis)
  - SF OpenData API (crime statistics)
- Cached data is stored in `.cache/` directory

## Cost Estimates

Analyzing 20 apartments:
- **Google Sheets API**: Free
- **Google Maps API**: ~$0.50-1.00 (geocoding, directions, places)
- **Anthropic Claude API**: ~$2-4 (if using photo analysis)
- **SF OpenData API**: Free
- **Total**: ~$0.50-5.00 per 20 apartments (depending on photo analysis usage)

Costs are cached, so re-running analysis on same apartments is free (unless you use `--force-refresh`).

## Limitations

1. **San Francisco Only**: Crime data and some assumptions (rent control year) are SF-specific. Can be adapted for other cities.
2. **Photo Analysis**: Optional AI analysis may not always be accurate if you choose to use it.
3. **Rate Limits**: Aggressive API usage may hit rate limits.

## Contributing

This tool was built for personal use. Feel free to fork and adapt for your needs!

## Documentation

### 📚 Comprehensive Guides

All feature guides, bug fix documentation, and improvement summaries are organized in the [`docs/`](docs/) directory:

- **[Documentation Index](docs/README.md)** - Complete list of all docs
- **[Feature Guides](docs/feature_guides/)** - How to use features
- **[Bug Fixes](docs/bug_fixes/)** - What's been fixed
- **[Improvements Summary](docs/IMPROVEMENTS_SUMMARY.md)** - All changes

### 🚀 Railway Deployment

Want to deploy this as a remote web app? See [`RAILWAY.md`](RAILWAY.md) or check the complete deployment docs in [`railway/docs/`](railway/docs/).

## License

MIT License - see LICENSE file for details

## Support

For issues or questions, please open a GitHub issue.

---

**Happy apartment hunting! 🏠**

