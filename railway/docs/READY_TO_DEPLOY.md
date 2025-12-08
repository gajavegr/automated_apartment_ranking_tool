# 🚀 Railway Deployment - Complete!

## ✅ What We've Set Up

All files are ready for Railway deployment! Here's what was created and modified:

### 📁 New Configuration Files
- ✅ **Procfile** - Tells Railway how to start your app with gunicorn
- ✅ **railway.toml** - Railway configuration (health checks, restart policy)
- ✅ **runtime.txt** - Specifies Python 3.11.9
- ✅ **.railwayignore** - Excludes unnecessary files from deployment

### 📚 New Documentation
- ✅ **DEPLOYMENT.md** - Comprehensive deployment guide (411 lines!)
- ✅ **RAILWAY_QUICK_START.md** - Quick reference for common tasks
- ✅ **DEPLOYMENT_SUMMARY.md** - Overview of all changes
- ✅ **LOCAL_VS_RAILWAY.md** - Explains venv vs Railway environment
- ✅ **env.railway.template** - Template for Railway environment variables

### 🔧 Modified Files
- ✅ **requirements.txt** - Added gunicorn==21.2.0
- ✅ **config.py** - Added support for credentials from environment variables
- ✅ **web_app.py** - Added /health endpoint + production config support

### 🧪 New Testing Tools
- ✅ **test_deployment.sh** - Pre-flight check script (all tests passing!)

## 🎯 You're Ready to Deploy!

### Current Status
```
✅ All deployment files created
✅ All tests passing
✅ Gunicorn installed in venv
✅ Code ready to commit
```

## 📋 Next Steps (Choose Your Path)

### Path A: Deploy from Current Branch

```bash
# 1. Make sure venv is active
source venv/bin/activate

# 2. Commit changes
git add .
git commit -m "Add Railway deployment configuration"

# 3. Push to your branch
git push origin ggajavelli/deploy_to_railway

# 4. Deploy to Railway from this branch
# Go to railway.app → New Project → Deploy from GitHub repo
# Select branch: ggajavelli/deploy_to_railway
```

### Path B: Merge to Main First

```bash
# 1. Make sure venv is active
source venv/bin/activate

# 2. Commit changes on current branch
git add .
git commit -m "Add Railway deployment configuration"
git push origin ggajavelli/deploy_to_railway

# 3. Switch to main and merge
git checkout main
git merge ggajavelli/deploy_to_railway
git push origin main

# 4. Deploy to Railway from main branch
```

## 🌐 Railway Deployment Steps

### Step 1: Create Railway Project (5 minutes)

1. Go to [railway.app](https://railway.app) and sign in
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository
5. Select branch (main or ggajavelli/deploy_to_railway)
6. Railway starts building automatically!

### Step 2: Add Persistent Volume (CRITICAL!)

1. Click on your service in Railway
2. Go to "Variables" tab
3. Scroll to "Volumes" section
4. Click "+ New Volume"
5. Set:
   - **Mount Path:** `/app/.cache`
   - **Size:** 1GB
6. Click "Add"

**Why this matters:** Without this, your cache (Google Maps API calls, Anthropic responses) will be lost on every deploy! 💸

### Step 3: Set Environment Variables (15 minutes)

Click "New Variable" for each of these:

**Required:**
```
GOOGLE_SHEET_ID=<your_sheet_id>
ANTHROPIC_API_KEY=<your_key>
GOOGLE_MAPS_API_KEY=<your_key>
GOOGLE_SHEETS_CREDENTIALS_JSON=<paste entire JSON from credentials/google_sheets_credentials.json>
```

**Optional (if different from defaults):**
```
YOUR_WORK_ADDRESS=<your address>
PARTNER_WORK_ADDRESS=<partner address>
CACHE_DIR=/app/.cache
CACHE_EXPIRE_HOURS=168
```

**Pro tip:** For GOOGLE_SHEETS_CREDENTIALS_JSON:
1. Open `credentials/google_sheets_credentials.json`
2. Select ALL (Cmd+A)
3. Copy (Cmd+C)
4. Paste into Railway variable value field
5. Railway handles the multi-line JSON automatically!

**⚠️ Railway will show "suggested variables":**
- You may see `GOOGLE_SHEETS_CREDENTIALS_PATH` in suggestions
- **IGNORE IT** - do NOT set this variable in Railway!
- Our code automatically handles the path when you set `GOOGLE_SHEETS_CREDENTIALS_JSON`
- Only the 4 required variables above are needed

### Step 4: Deploy & Test

1. Railway auto-deploys after you add environment variables
2. Wait for build to complete (~3-5 minutes)
3. Click "Generate Domain" to get your URL
4. Visit: `https://your-app-name.up.railway.app`
5. Test: `https://your-app-name.up.railway.app/health`

Expected health check response:
```json
{
  "status": "healthy",
  "sheets_client": true,
  "location_analyzer": true,
  "cache_dir": true,
  "cache_dir_path": "/app/.cache"
}
```

## 🧪 Verify Everything Works

### Test Checklist
- [ ] App loads at Railway URL
- [ ] Health endpoint returns "healthy"
- [ ] Entry form loads with map
- [ ] Can view existing apartments
- [ ] Can add new apartment
- [ ] Can run analysis
- [ ] Check Railway logs - no errors
- [ ] Partner can access same URL
- [ ] Preferences tab works

### Test Cache Persistence
1. Add an apartment and run analysis
2. Go to Railway → Deployments → Click "Restart"
3. Wait for restart (~30 seconds)
4. View the same apartment - should load instantly (cache working!)

## 💰 Expected Costs

**First Month (with $5 free credit):**
- Light usage: $0-2 (covered by free credit!)
- Medium usage: $2-5
- Heavy usage: $5-10

**Ongoing:**
- Light usage: $3-6/month
- Medium usage: $6-10/month
- Heavy usage: $9-15/month

**What counts as "heavy usage"?**
- Analyzing 50+ apartments/month
- Daily site visits
- Large cache (2-3GB)

## 📱 Share with Your Partner

Once deployed:
1. Copy your Railway URL: `https://your-app-name.up.railway.app`
2. Share with partner via text/email
3. Both can use simultaneously!
4. All data syncs via Google Sheets

## 📚 Documentation Quick Links

- **Quick Start:** [RAILWAY_QUICK_START.md](RAILWAY_QUICK_START.md)
- **Full Guide:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Troubleshooting:** [DEPLOYMENT.md](DEPLOYMENT.md) (section at bottom)
- **Local vs Railway:** [LOCAL_VS_RAILWAY.md](LOCAL_VS_RAILWAY.md)
- **Summary:** [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md)

## 🆘 If Something Goes Wrong

### Build Fails
- Check Railway logs for specific error
- Usually missing package in requirements.txt
- Run `./test_deployment.sh` locally first

### App Crashes on Start
- Check "Logs" tab in Railway
- Usually missing environment variable
- Verify all required env vars are set

### Can't Connect to Google Sheets
- Check `GOOGLE_SHEETS_CREDENTIALS_JSON` is set correctly
- Make sure JSON is complete (starts with `{`, ends with `}`)
- Verify `GOOGLE_SHEET_ID` is correct

### Cache Not Working
- Verify volume is mounted at `/app/.cache`
- Check `CACHE_DIR` env var is set to `/app/.cache`
- Look for "Writing cache to..." in logs

### Get Help
- Railway Discord: [discord.gg/railway](https://discord.gg/railway) - very responsive!
- Railway Docs: [docs.railway.app](https://docs.railway.app)
- Check DEPLOYMENT.md troubleshooting section

## 🎉 You're All Set!

Everything is ready for deployment. The hard work is done - now it's just a matter of:
1. Committing these files
2. Pushing to GitHub
3. Creating a Railway project
4. Adding environment variables
5. Watching it deploy!

**Time estimate:** 20-30 minutes for first deployment

Good luck! 🚀 Happy apartment hunting! 🏠

---

**Pro tip:** Deploy on a weekday afternoon when you have time to troubleshoot if needed. Don't deploy late Friday night! 😄

