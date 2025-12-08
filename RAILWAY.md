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

