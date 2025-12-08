# Railway Deployment - Changes Summary

## Files Created

### Configuration Files
- ✅ **Procfile** - Tells Railway how to start the web server using gunicorn
- ✅ **railway.toml** - Railway-specific configuration (health checks, restart policy)
- ✅ **runtime.txt** - Specifies Python 3.11.9
- ✅ **.railwayignore** - Excludes unnecessary files from deployment (reduces build time)

### Documentation
- ✅ **DEPLOYMENT.md** - Comprehensive deployment guide with troubleshooting
- ✅ **RAILWAY_QUICK_START.md** - Quick reference for common tasks
- ✅ **env.railway.template** - Template for setting environment variables in Railway

## Files Modified

### requirements.txt
- ✅ Added `gunicorn==21.2.0` - Production web server

### config.py
- ✅ Added support for `GOOGLE_SHEETS_CREDENTIALS_JSON` environment variable
- ✅ Writes credentials to `/tmp/` when provided via env var (for Railway)
- ✅ Falls back to file-based credentials for local development
- ✅ Added helpful logging for credential loading

### web_app.py
- ✅ Added `/health` endpoint for Railway health checks
- ✅ Updated `if __name__ == '__main__'` to support production environment
- ✅ Reads `PORT` and `HOST` from environment variables
- ✅ Disables browser auto-open in production
- ✅ Respects `FLASK_DEBUG` environment variable

## Key Features

### Persistent Cache
- Cache directory configured to mount at `/app/.cache` in Railway
- Prevents loss of expensive API call results (Anthropic Claude, Google Maps)
- Volume persists across deployments

### Production-Ready
- Uses Gunicorn instead of Flask dev server
- 2 workers + 2 threads for concurrency
- 300-second timeout for long-running analysis
- Proper logging to stdout/stderr
- Health check endpoint for monitoring

### Environment Variable Support
- All configuration via environment variables
- Google Sheets credentials as JSON string (no file upload needed)
- Same `.env` values work for both local and production

### Security
- No credentials committed to Git
- All sensitive data via environment variables
- Credentials stored encrypted in Railway

## Testing Locally

Before deploying, test with production settings:

```bash
# Install gunicorn
pip install gunicorn==21.2.0

# Test with gunicorn (simulates production)
gunicorn web_app:app --bind 127.0.0.1:5001 --timeout 300 --workers 1 --access-logfile -

# In another terminal, test the health endpoint
curl http://127.0.0.1:5001/health

# Test the main app
open http://127.0.0.1:5001
```

## Deployment Checklist

### Before Deploying
- [ ] Code is committed to Git
- [ ] Code is pushed to GitHub
- [ ] requirements.txt includes gunicorn
- [ ] .env file is NOT committed (verify with `git status`)
- [ ] Local credentials work (test with `python web_app.py`)

### In Railway
- [ ] Project created from GitHub repo
- [ ] Persistent volume added at `/app/.cache` (1GB minimum)
- [ ] Environment variables set (see env.railway.template)
- [ ] `GOOGLE_SHEETS_CREDENTIALS_JSON` contains full JSON
- [ ] Build completes successfully
- [ ] Deployment shows "Active"
- [ ] Domain generated (or custom domain added)

### After Deploying
- [ ] Visit Railway URL - app loads
- [ ] Health check works: `https://your-app.railway.app/health`
- [ ] Can view entry form
- [ ] Can add new apartment
- [ ] Can run analysis
- [ ] Check logs - no errors
- [ ] Test cache persistence (redeploy, check if data persists)
- [ ] Share URL with partner - they can access

## Expected Costs

### Railway Pricing
- **Compute**: ~$0.000231/minute (~$10/month for always-on)
- **Volume**: $0.25/GB/month
- **Free $5 credit/month** for hobby tier

### Realistic Monthly Costs
- **Light usage**: $3-6/month (occasional use, small cache)
- **Medium usage**: $6-10/month (regular use, 1-2GB cache)
- **Heavy usage**: $9-15/month (daily use, large cache, multiple apartments)

### Cost Optimization
- Cache expires after 168 hours (1 week) by default
- Increase `CACHE_EXPIRE_HOURS` to reduce API costs
- Volume auto-scales, only pay for what you use
- No charges when not deploying/accessing

## Architecture

```
User's Browser
    ↓
Railway CDN (HTTPS)
    ↓
Gunicorn (2 workers)
    ↓
Flask App (web_app.py)
    ↓
┌──────────────────┬────────────────────┬─────────────────┐
│                  │                    │                 │
Google Sheets  Anthropic Claude   Google Maps      SF OpenData
    ↓                 ↓                 ↓                ↓
         Cached in /app/.cache (persistent volume)
```

## Rollback Plan

If deployment fails or has issues:

1. **Quick rollback**: Railway Dashboard → Deployments → Previous deployment → Redeploy
2. **Git rollback**: `git revert HEAD` and push
3. **Local testing**: Always test locally before deploying
4. **Logs**: Check Railway logs for specific errors

## Support Resources

- **Railway Docs**: https://docs.railway.app/
- **Railway Discord**: https://discord.gg/railway (very helpful!)
- **This repo**: Check DEPLOYMENT.md for detailed troubleshooting
- **Railway Status**: https://railway.statuspage.io

## Next Steps

1. **Review files**: Check all created/modified files
2. **Test locally**: Run with gunicorn to simulate production
3. **Commit changes**: `git add . && git commit -m "Add Railway deployment config"`
4. **Push to GitHub**: `git push origin ggajavelli/deploy_to_railway`
5. **Follow RAILWAY_QUICK_START.md**: Step-by-step deployment guide
6. **Deploy to Railway**: Create project and deploy!

---

**Questions or issues?** Check DEPLOYMENT.md for comprehensive troubleshooting!

