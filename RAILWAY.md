# Railway Deployment

This project can be deployed to Railway for remote access.

## 🚀 Deploy to Railway

All Railway deployment files and documentation are in the **`railway/`** directory.

### Quick Start

1. **Read the guide:** [`railway/docs/READY_TO_DEPLOY.md`](railway/docs/READY_TO_DEPLOY.md)
2. **Test locally:** `./railway/test_deployment.sh`
3. **Deploy:** Push to GitHub, connect to Railway
4. **Configure:** Set environment variables, add persistent volume
5. **Access:** Get your Railway URL and start using remotely!

### What's in `railway/`?

```
railway/
├── README.md                    ← Overview and quick reference
├── env.railway.template         ← Environment variables template
├── test_deployment.sh          ← Pre-deployment test script
└── docs/                       ← Comprehensive guides
    ├── READY_TO_DEPLOY.md      ← START HERE
    ├── QUICK_START.md          ← Quick reference
    ├── DEPLOYMENT.md           ← Full deployment guide
    └── ...more guides
```

### Required Files (at project root)

These files must stay at the project root for Railway/Python:

- `Procfile` - Start command for Railway
- `runtime.txt` - Python version (3.11.9)
- `requirements.txt` - Python dependencies  
- `.railwayignore` - Deployment exclusions
- `railway.toml` - Railway configuration

## 👥 Multi-User Environment (parallel deployment)

The multi-user build (username login + per-user Google Sheet tabs) is meant to
run as a **separate Railway environment/service**, leaving the existing
single-user prod deployment untouched. It reuses the same `Procfile`,
`railway.toml`, and `/health` check.

To stand it up alongside prod:

1. **Create a new service** (or a new environment) in the same Railway project,
   pointing at this branch/repo. Do **not** modify the existing prod service.
2. **Set environment variables** from [`railway/env.railway.template`](railway/env.railway.template).
   In addition to the existing prod vars, the multi-user build **requires**:
   - `FLASK_SECRET_KEY` — a stable random value (signs the login session cookie;
     required so sessions survive restarts and are shared across gunicorn
     workers). Generate with `python -c "import secrets; print(secrets.token_hex(32))"`.
3. **Use a fresh Google Sheet** (a new `GOOGLE_SHEET_ID`) for this environment so
   multi-user tabs (`<username> - ...`, plus the `Users` registry) don't mix with
   prod's single-user tabs. The service account still needs edit access to it.
4. **Add the persistent volume** for `CACHE_DIR` just like prod.
5. Deploy. Visiting the new URL lands on the **login page**.

> ⚠️ Username login identifies users but does **not** authenticate them (no
> passwords). See the "Multi-User Mode" section of the main [README](README.md).

## 💰 Cost

- **Light usage:** $3-6/month
- **First $5/month free!**

## 🏥 Health Check

Railway monitors app health via:
- **Endpoint:** `https://your-app.up.railway.app/health`
- **Frequency:** Every 30 seconds
- **Auto-restart:** If health check fails 3 times

## 📚 Documentation

See [`railway/README.md`](railway/README.md) for complete documentation index.

## 🆘 Need Help?

- Check [`railway/docs/DEPLOYMENT.md`](railway/docs/DEPLOYMENT.md) for troubleshooting
- Railway Discord: https://discord.gg/railway
- Railway Docs: https://docs.railway.app

---

**Ready to deploy?** Start here: [`railway/docs/READY_TO_DEPLOY.md`](railway/docs/READY_TO_DEPLOY.md) 🚀

