# Railway Deployment Guide

This guide will walk you through deploying your Apartment Analyzer to Railway with persistent cache storage.

## 📋 Prerequisites

Before you start, make sure you have:

- [ ] GitHub account (your code needs to be in a GitHub repo)
- [ ] Railway account ([sign up here](https://railway.app/))
- [ ] Credit card (for Railway - needed even for the $5/month credit)
- [ ] All your API keys and credentials ready:
  - Google Sheets credentials JSON file
  - Anthropic API key
  - Google Maps API key
  - Google Sheet ID

## 🚀 Deployment Steps

### Step 1: Prepare Your Repository

1. **Commit all deployment files:**
   ```bash
   git add Procfile railway.toml .railwayignore requirements.txt
   git commit -m "Add Railway deployment configuration"
   git push origin ggajavelli/deploy_to_railway
   ```

2. **Merge to main (or deploy from your branch):**
   ```bash
   git checkout main
   git merge ggajavelli/deploy_to_railway
   git push origin main
   ```

### Step 2: Create Railway Project

1. **Go to [Railway.app](https://railway.app/) and log in**

2. **Click "New Project"**

3. **Select "Deploy from GitHub repo"**
   - Authorize Railway to access your GitHub
   - Select your `automated_apartment_scraper` repository
   - Choose the branch (main or ggajavelli/deploy_to_railway)

4. **Railway will automatically detect it's a Python app and start building**

### Step 3: Add Persistent Volume for Cache

This is **CRITICAL** - without this, your cache will be lost on every deploy!

1. **In your Railway project, click on your service**

2. **Go to the "Variables" tab first** (we'll add the volume after env vars)

3. **Click "New Volume" button**
   - **Mount Path:** `/app/.cache`
   - **Size:** Start with 1GB (can increase later)
   - Click "Add"

4. **Important:** The cache will now persist across deployments! 🎉

### Step 4: Configure Environment Variables

In the Railway dashboard, go to "Variables" tab and add these:

#### Required Variables

```bash
# Google Sheets API
GOOGLE_SHEET_ID=<your-google-sheet-id>

# Anthropic Claude API  
ANTHROPIC_API_KEY=<your-anthropic-api-key>

# Google Maps API
GOOGLE_MAPS_API_KEY=<your-google-maps-api-key>
```

#### Optional Variables (use your local values from .env)

```bash
# Work locations
YOUR_WORK_ADDRESS=4100 E 3rd Ave, Foster City, CA 94404
PARTNER_WORK_ADDRESS=1355 Market St, San Francisco, CA 94103

# Commute preferences
PARTNER_COMMUTE_MODE=transit
PARTNER_COMMUTE_FALLBACK_MODE=walking

# Cache settings
CACHE_DIR=/app/.cache
CACHE_EXPIRE_HOURS=168

# SF OpenData
SF_OPENDATA_API_ENDPOINT=https://data.sfgov.org/resource/wg3w-h783.json
```

#### Google Sheets Credentials (IMPORTANT!)

You have two options:

**Option A: Store as Environment Variable (Recommended)**

1. Open your local `credentials/google_sheets_credentials.json`
2. Copy the ENTIRE contents (it's JSON)
3. In Railway, add a variable:
   - **Key:** `GOOGLE_SHEETS_CREDENTIALS_JSON`
   - **Value:** Paste the entire JSON (Railway handles multi-line)

4. Update `config.py` to support this (see Step 5)

**Option B: Upload via Railway CLI (Advanced)**

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Upload the credentials file
railway run --service=<your-service-name> bash -c "mkdir -p credentials && cat > credentials/google_sheets_credentials.json" < credentials/google_sheets_credentials.json
```

### Step 5: Update config.py for Environment-based Credentials

Add this code to `config.py` to support credentials from environment variables:

```python
# Near the top of config.py, after load_dotenv()

import json

# Google Sheets Credentials
# Try environment variable first (for Railway), fall back to file
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
if GOOGLE_SHEETS_CREDENTIALS_JSON:
    # Credentials provided as JSON string in environment variable
    # Save to file for gspread to use
    GOOGLE_SHEETS_CREDENTIALS_PATH = "/tmp/google_sheets_credentials.json"
    with open(GOOGLE_SHEETS_CREDENTIALS_PATH, 'w') as f:
        f.write(GOOGLE_SHEETS_CREDENTIALS_JSON)
else:
    # Use file path from environment or default
    GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv(
        "GOOGLE_SHEETS_CREDENTIALS_PATH", 
        "credentials/google_sheets_credentials.json"
    )
```

### Step 6: Deploy and Test

1. **Railway will automatically deploy after you add environment variables**
   - Watch the build logs in the "Deployments" tab
   - Build takes ~3-5 minutes

2. **Once deployed, Railway will give you a URL**
   - Look for something like: `https://your-app-name.up.railway.app`
   - Click "Generate Domain" if you don't see one

3. **Test your deployment:**
   - Visit the URL
   - Try adding a new apartment
   - Check if the cache is working (add same apartment twice, second time should be faster)

### Step 7: Enable Custom Domain (Optional)

1. **In Railway, go to Settings → Domains**
2. **Click "Add Domain"**
3. **Enter your domain (e.g., apartments.yourdomain.com)**
4. **Add the CNAME record to your DNS provider**
5. **Railway will provision SSL certificate automatically**

## 🔍 Monitoring and Debugging

### View Logs

1. In Railway dashboard, click on your service
2. Go to "Logs" tab
3. See real-time logs from your Flask app

### Check Resource Usage

1. Go to "Metrics" tab
2. Monitor:
   - Memory usage
   - CPU usage  
   - Network usage
   - Disk usage (your cache volume)

### Restart Service

If something goes wrong:
1. Go to "Settings" → "Service"
2. Click "Restart"

## 💰 Cost Monitoring

### View Current Usage

1. Go to your Railway dashboard
2. Click "Usage" at the top
3. See current month's usage and costs

### Expected Costs

**Light Usage** (5-10 apartments/month):
- Compute: ~$3-5/month
- Volume (1GB): $0.25/month
- **Total: ~$3-6/month**

**Heavy Usage** (50+ apartments/month):
- Compute: ~$8-12/month
- Volume (1-2GB): $0.25-0.50/month
- **Total: ~$9-13/month**

### Set Spending Limits

1. Go to Account Settings → Billing
2. Set usage alerts
3. Set monthly spending cap if desired

## 🔒 Security Best Practices

### Protect Your Deployment

1. **Don't commit `.env` or credentials to Git** (already in .gitignore)

2. **Rotate API keys periodically**
   - Google Maps API key
   - Anthropic API key
   - Update in Railway dashboard

3. **Use Railway's Environment Groups** (optional)
   - Create separate environments for "production" and "staging"

4. **Enable GitHub branch protection**
   - Require pull request reviews before merging to main

## 🐛 Troubleshooting

### Build Failed

**Problem:** Build fails with dependency errors

**Solution:**
```bash
# Test locally first
pip install -r requirements.txt

# Make sure all imports work
python -c "import flask; import anthropic; import gspread; print('OK')"
```

### Service Crashes on Start

**Problem:** App starts but crashes immediately

**Solution:**
1. Check logs in Railway dashboard
2. Common issues:
   - Missing environment variables (check Variables tab)
   - Invalid Google Sheets credentials
   - Missing API keys

### Cache Not Persisting

**Problem:** Cache is cleared on every deployment

**Solution:**
1. Verify volume is mounted at `/app/.cache`
2. Check `CACHE_DIR` environment variable is set to `/app/.cache`
3. Check logs to see where cache is being written

### Slow Response Times

**Problem:** First request after deploy is very slow

**Solution:**
- This is normal! Railway doesn't "sleep" your app, but the first request loads all modules
- Consider adding a health check endpoint that warms up the cache

### API Rate Limits

**Problem:** Google Maps or Anthropic API returns 429 errors

**Solution:**
1. Check your API quotas in their respective dashboards
2. Increase quotas if needed
3. Implement more aggressive caching (increase CACHE_EXPIRE_HOURS)

### Out of Memory

**Problem:** App crashes with "Out of memory" errors

**Solution:**
1. In Railway, increase memory allocation:
   - Settings → Resources → Memory
   - Upgrade to a higher tier if needed
2. Consider reducing `--workers` in Procfile from 2 to 1

## 🔄 Updating Your Deployment

### Deploy New Changes

1. **Make changes locally**
2. **Test locally first:**
   ```bash
   python web_app.py
   ```
3. **Commit and push:**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```
4. **Railway auto-deploys!** Watch the deployment in dashboard

### Rollback a Deployment

1. Go to "Deployments" tab
2. Find the previous working deployment
3. Click "..." → "Redeploy"

## 📱 Sharing with Your Partner

Once deployed, share the Railway URL with your partner:

1. **Share URL:** `https://your-app-name.up.railway.app`
2. **No auth needed** (app uses Google Sheets as the backend/auth)
3. **Both can use simultaneously** - Google Sheets handles conflicts

### Optional: Add Basic Password Protection

If you want to add simple password protection:

1. Install `Flask-HTTPAuth`:
   ```bash
   pip install Flask-HTTPAuth
   echo "Flask-HTTPAuth==4.8.0" >> requirements.txt
   ```

2. Add to `web_app.py`:
   ```python
   from flask_httpauth import HTTPBasicAuth
   
   auth = HTTPBasicAuth()
   
   users = {
       os.getenv("WEB_USERNAME", "admin"): os.getenv("WEB_PASSWORD", "changeme")
   }
   
   @auth.verify_password
   def verify_password(username, password):
       if username in users and users[username] == password:
           return username
   
   # Add @auth.login_required to routes you want to protect
   @app.route('/')
   @auth.login_required
   def index():
       # ... existing code
   ```

3. Add environment variables in Railway:
   ```
   WEB_USERNAME=yourname
   WEB_PASSWORD=secure_password_here
   ```

## 🎉 Success Checklist

Once deployed, verify everything works:

- [ ] App loads at Railway URL
- [ ] Can view existing apartments from Google Sheets
- [ ] Can add new apartment via web form
- [ ] Can run analysis (check logs for API calls)
- [ ] Cache persists (add same data twice, should be faster)
- [ ] Both you and partner can access simultaneously
- [ ] Preferences tab works
- [ ] All API calls succeed (Google Maps, Anthropic, etc.)

## 📚 Additional Resources

- [Railway Documentation](https://docs.railway.app/)
- [Railway Discord](https://discord.gg/railway) - Very helpful community
- [Flask Production Best Practices](https://flask.palletsprojects.com/en/3.0.x/deploying/)
- [Gunicorn Configuration](https://docs.gunicorn.org/en/stable/settings.html)

## 🆘 Getting Help

If you run into issues:

1. **Check Railway logs first** (most issues show up here)
2. **Search Railway Discord** (someone probably had the same issue)
3. **Railway support** is very responsive on Discord
4. **Check this repo's Issues** on GitHub

---

**Happy Apartment Hunting! 🏠** 

Let me know if you hit any issues during deployment!

