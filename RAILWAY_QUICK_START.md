# Railway Deployment - Quick Reference

## 🚀 Quick Start

1. **Push your code to GitHub**
2. **Create Railway project** from your GitHub repo
3. **Add persistent volume** at `/app/.cache` (1GB to start)
4. **Set environment variables** (see below)
5. **Deploy!**

## 📋 Environment Variables Checklist

Copy these into Railway's Variables tab:

### Required
```
GOOGLE_SHEET_ID=your_sheet_id_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GOOGLE_MAPS_API_KEY=your_google_maps_key_here
GOOGLE_SHEETS_CREDENTIALS_JSON=<paste entire JSON from credentials/google_sheets_credentials.json>
```

### Optional (if different from defaults)
```
YOUR_WORK_ADDRESS=4100 E 3rd Ave, Foster City, CA 94404
PARTNER_WORK_ADDRESS=1355 Market St, San Francisco, CA 94103
PARTNER_COMMUTE_MODE=transit
PARTNER_COMMUTE_FALLBACK_MODE=walking
CACHE_DIR=/app/.cache
CACHE_EXPIRE_HOURS=168
```

## 🗂️ Adding Google Sheets Credentials

**Method 1: Via Environment Variable (Easiest)**

1. Open `credentials/google_sheets_credentials.json` locally
2. Copy the entire contents (it's a JSON object)
3. In Railway Variables, create: `GOOGLE_SHEETS_CREDENTIALS_JSON`
4. Paste the entire JSON as the value
5. Railway handles multi-line values automatically ✅

**Method 2: Via Railway CLI**

```bash
railway login
railway link
railway run bash -c "mkdir -p credentials && cat > credentials/google_sheets_credentials.json" < credentials/google_sheets_credentials.json
```

## 💾 Persistent Volume Setup

**CRITICAL**: Without this, your cache will be lost on every deploy!

1. In Railway project → Click your service
2. Click "Variables" tab
3. Scroll down to "Volumes" section
4. Click "+ New Volume"
5. Set:
   - **Mount Path:** `/app/.cache`
   - **Size:** 1GB (can increase later)
6. Click "Add"

**Verify it works:**
- After deployment, analyze an apartment
- Redeploy your service
- Analyze the same apartment (should be instant = cache working!)

## 🧪 Local Testing Before Deploy

Test that everything works locally:

```bash
# Install gunicorn locally
pip install gunicorn==21.2.0

# Test with gunicorn (simulates production)
gunicorn web_app:app --bind 127.0.0.1:5001 --timeout 300 --workers 1 --access-logfile -

# Visit http://127.0.0.1:5001
```

If this works, Railway should work!

## 🔍 Common Issues

### Build Fails
- Check Railway logs for specific error
- Usually missing dependencies in requirements.txt
- Make sure all files are committed and pushed

### App Crashes on Start
- Check "Logs" tab in Railway
- Usually missing environment variables
- Check that `GOOGLE_SHEETS_CREDENTIALS_JSON` is set correctly

### Cache Not Persisting
- Verify volume is mounted at `/app/.cache`
- Check `CACHE_DIR` env var is set to `/app/.cache`
- Look in logs for "Writing cache to..." to verify path

### 502 Bad Gateway
- App is starting up (wait 30-60 seconds)
- Check logs for startup errors
- Verify all API keys are valid

### Timeout Errors
- Analysis takes a long time (expected for first run)
- Gunicorn timeout is set to 300 seconds (5 min)
- If you need longer, update `--timeout` in Procfile

## 📊 Monitoring

### Check Current Usage
1. Railway Dashboard → Click your project
2. "Usage" tab at top
3. See compute + storage costs

### View Logs
1. Click your service
2. "Logs" tab
3. Real-time streaming logs

### Restart Service
1. Service → "Settings"
2. Click "Restart"

## 💰 Expected Costs

**Light usage** (checking site daily, analyzing 5-10 apartments/month):
- ~$3-6/month

**Heavy usage** (analyzing 50+ apartments/month):
- ~$9-13/month

**Storage**: $0.25/GB/month for cache volume

## 🔗 Useful Railway URLs

- Dashboard: https://railway.app/dashboard
- Docs: https://docs.railway.app
- Discord: https://discord.gg/railway (great support!)
- Status: https://railway.statuspage.io

## 📱 Sharing Access

Once deployed, share your Railway URL with your partner:

1. Go to service → "Settings" → "Domains"
2. Click "Generate Domain" if not already done
3. Copy URL (e.g., `your-app-name.up.railway.app`)
4. Share with partner
5. Both can use simultaneously!

## 🛡️ Security Notes

- Don't commit `.env` or credentials to GitHub (already in .gitignore ✅)
- All environment variables in Railway are encrypted at rest
- Railway URLs are public but hard to guess
- Consider adding basic auth if worried about random access (see DEPLOYMENT.md)

## 🔄 Deploying Updates

**Automatic deployment:**
1. Make changes locally
2. Commit: `git commit -m "Your changes"`
3. Push: `git push origin main`
4. Railway auto-deploys! 🎉

**Watch deployment:**
- Go to "Deployments" tab
- See build progress
- Click on deployment to see logs

## ✅ Post-Deployment Checklist

- [ ] App loads at Railway URL
- [ ] Can view entry form
- [ ] Can add new apartment
- [ ] Can run analysis
- [ ] Cache persists (test by redeploying)
- [ ] Preferences tab works
- [ ] Partner can access same URL
- [ ] No errors in logs

---

Need help? Check [DEPLOYMENT.md](./DEPLOYMENT.md) for the full detailed guide!

