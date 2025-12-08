# Railway Deployment Files

This directory contains all Railway-specific configuration and documentation.

## 📁 Directory Structure

```
railway/
├── README.md                    ← You are here
├── env.railway.template         ← Template for environment variables
├── test_deployment.sh          ← Pre-deployment test script
└── docs/                       ← Comprehensive documentation
    ├── READY_TO_DEPLOY.md      ← 🎯 START HERE - Complete checklist
    ├── QUICK_START.md          ← Quick reference guide
    ├── DEPLOYMENT.md           ← Full deployment guide
    ├── VARIABLES_FAQ.md        ← Environment variables explained
    ├── LOCAL_VS_RAILWAY.md     ← Local vs production environments
    └── DEPLOYMENT_SUMMARY.md   ← Overview of all changes
```

## 🚀 Quick Start

### First Time Deploying?

**Start here:** [`docs/READY_TO_DEPLOY.md`](docs/READY_TO_DEPLOY.md)

This has everything you need:
- ✅ Pre-deployment checklist
- ✅ Step-by-step Railway setup
- ✅ Environment variable configuration
- ✅ Troubleshooting guide

### Already Deployed?

**Quick reference:** [`docs/QUICK_START.md`](docs/QUICK_START.md)

Common tasks:
- View logs
- Restart service
- Update environment variables
- Monitor costs

## 📋 Files at Project Root

Some files must stay at the project root for Railway/Python to work:

```
project_root/
├── Procfile                    ← Tells Railway how to start the app
├── runtime.txt                 ← Specifies Python version (3.11.9)
├── requirements.txt            ← Python dependencies
├── .railwayignore             ← Files to exclude from deployment
└── railway.toml               ← Railway configuration (can be moved)
```

## 🔧 Configuration Files

### Procfile
Tells Railway to use gunicorn with specific settings:
```bash
web: gunicorn web_app:app --bind 0.0.0.0:$PORT --timeout 300 --workers 2 --threads 2
```

### runtime.txt
Specifies Python version:
```
python-3.11.9
```

### railway.toml
Railway-specific configuration:
- Start command
- Restart policy
- **Health check endpoint: `/health`**
- Timeout settings

### .railwayignore
Excludes unnecessary files from deployment:
- Development files
- Cache directories
- Documentation
- Test files

## 🏥 Health Check

Railway is configured to call `/health` endpoint to verify the app is running:

```
GET https://your-app.up.railway.app/health

Response (healthy):
{
  "status": "healthy",
  "sheets_client": true,
  "location_analyzer": true,
  "cache_dir": true,
  "cache_dir_path": "/app/.cache"
}
```

**Configuration in `railway.toml`:**
```toml
healthcheckPath = "/health"
healthcheckTimeout = 100
```

Railway will:
- ✅ Call `/health` every 30 seconds
- ✅ Restart app if health check fails 3 times
- ✅ Show health status in dashboard

## 📚 Documentation Guide

### For Different Needs:

| What You Need | Read This |
|---------------|-----------|
| **First deployment** | [`READY_TO_DEPLOY.md`](docs/READY_TO_DEPLOY.md) |
| **Quick commands** | [`QUICK_START.md`](docs/QUICK_START.md) |
| **Full guide** | [`DEPLOYMENT.md`](docs/DEPLOYMENT.md) |
| **Env vars confusion** | [`VARIABLES_FAQ.md`](docs/VARIABLES_FAQ.md) |
| **Local vs Railway** | [`LOCAL_VS_RAILWAY.md`](docs/LOCAL_VS_RAILWAY.md) |
| **What changed?** | [`DEPLOYMENT_SUMMARY.md`](docs/DEPLOYMENT_SUMMARY.md) |

## 🧪 Pre-Deployment Testing

Before deploying, run:

```bash
# From project root
cd railway
./test_deployment.sh
```

This checks:
- ✅ Virtual environment active
- ✅ All deployment files present
- ✅ Environment variables configured
- ✅ Credentials valid
- ✅ Dependencies installed
- ✅ Python syntax valid

## 🌐 Deployment Workflow

```
1. Code changes
   ↓
2. Run tests: ./railway/test_deployment.sh
   ↓
3. Commit: git commit -m "Your changes"
   ↓
4. Push: git push origin ggajavelli/deploy_to_railway
   ↓
5. Railway auto-deploys
   ↓
6. Health check passes ✅
   ↓
7. New version live! 🎉
```

## 🛠️ Railway Configuration

### Environment Variables Required

See [`env.railway.template`](env.railway.template) for the complete list.

**Critical ones:**
```bash
GOOGLE_SHEET_ID=...
ANTHROPIC_API_KEY=...
GOOGLE_MAPS_API_KEY=...
GOOGLE_SHEETS_CREDENTIALS_JSON=...  # Full JSON content
```

**Note:** Railway may suggest `GOOGLE_SHEETS_CREDENTIALS_PATH` - **ignore it!**
See [`docs/VARIABLES_FAQ.md`](docs/VARIABLES_FAQ.md) for why.

### Persistent Storage

**Volume mounted at:** `/app/.cache`

This stores:
- Google Maps API responses
- Anthropic Claude responses
- Crime data
- Geocoding results

**Why it matters:** Without this, expensive API calls would re-run on every deployment!

## 🆘 Troubleshooting

### App won't start

1. Check Railway logs for errors
2. Verify all environment variables are set
3. Check `/health` endpoint shows `sheets_client: true`

### 500 errors

1. Check Railway logs for Python traceback
2. Common causes:
   - Missing environment variables
   - Invalid Google Sheets credentials
   - Missing dependencies

### Health check failing

1. Railway dashboard → Logs
2. Look for health check failures
3. Endpoint should return 200 status
4. Check if clients initialized correctly

**See full troubleshooting guide:** [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

## 💰 Cost Monitoring

Railway charges based on:
- **Compute:** ~$0.000231/min
- **Volume:** $0.25/GB/month

**Expected costs:**
- Light usage: $3-6/month
- Heavy usage: $9-15/month
- First $5/month free!

**Monitor in Railway:**
- Dashboard → Usage tab
- Set spending alerts
- View real-time usage

## 🔗 Useful Links

- **Railway Dashboard:** https://railway.app/dashboard
- **Railway Docs:** https://docs.railway.app
- **Railway Discord:** https://discord.gg/railway
- **Your App:** Check Railway for your generated domain

## 📝 Quick Commands

```bash
# Test before deploying
./railway/test_deployment.sh

# Deploy
git push origin ggajavelli/deploy_to_railway

# Check health
curl https://your-app.up.railway.app/health

# View logs (Railway CLI)
railway logs

# Restart service (Railway CLI)
railway restart
```

## 🎯 Summary

**Everything Railway-related is in this directory!**

- 📄 Config files for Railway
- 📚 Complete documentation
- 🧪 Pre-deployment testing
- 🔧 Environment variable templates

**Root directory files (Procfile, runtime.txt, etc.) are required at root by Railway/Python conventions.**

---

**Happy deploying! 🚀**

For questions or issues, check [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) or Railway's Discord.

