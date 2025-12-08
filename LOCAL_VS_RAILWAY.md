# Local vs Railway Environment Guide

## Understanding the Two Environments

Your apartment analyzer runs in **two different environments**:

### 1. **Local Development** (Your Computer)
- Uses **your local venv** (virtual environment)
- Dependencies from: `venv/lib/python3.11/site-packages/`
- Configuration from: `.env` file
- Credentials from: `credentials/google_sheets_credentials.json` file
- Cache at: `.cache/` directory (gitignored)

### 2. **Railway Production** (Cloud Hosting)
- Railway builds a **fresh environment** from scratch on each deploy
- Dependencies from: `requirements.txt` (Railway runs `pip install -r requirements.txt`)
- Configuration from: Environment variables in Railway dashboard
- Credentials from: `GOOGLE_SHEETS_CREDENTIALS_JSON` environment variable
- Cache at: `/app/.cache` (persistent volume, not in git)

## Key Differences

| Aspect | Local (venv) | Railway |
|--------|--------------|---------|
| **Python environment** | Your venv | Fresh virtualenv built by Railway |
| **Dependencies** | Installed once in venv | Installed fresh on every deploy |
| **Configuration** | .env file | Environment variables (Railway dashboard) |
| **Google Sheets creds** | File-based | JSON string in env var |
| **Cache persistence** | Always persists | Only persists if volume is mounted |
| **Code changes** | Instant (just save file) | Requires git push + build (~3-5 min) |

## Why Use venv Locally?

**For local development:**
```bash
# Activate venv
source venv/bin/activate

# Your shell now shows: (venv) $

# Python will use packages from venv/
python web_app.py
```

**Benefits:**
- ✅ Isolates project dependencies from system Python
- ✅ Prevents conflicts between projects
- ✅ Matches Railway's isolated environment approach
- ✅ Ensures `requirements.txt` is accurate (what you test is what Railway gets)

## Testing Before Deploy

**Always test with your venv activated:**

```bash
# 1. Activate venv
source venv/bin/activate

# 2. Run deployment test
./test_deployment.sh

# 3. Test with gunicorn (simulates Railway)
gunicorn web_app:app --bind 127.0.0.1:5001 --timeout 300 --workers 1

# 4. In another terminal, test it works
curl http://127.0.0.1:5001/health
open http://127.0.0.1:5001
```

If it works with gunicorn locally, it should work on Railway!

## How Railway Builds Your App

When you push to GitHub, Railway:

1. **Detects Python app** (sees `requirements.txt`)
2. **Creates fresh environment**:
   ```bash
   python -m venv /app/venv
   source /app/venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Reads environment variables** from Railway dashboard
4. **Mounts persistent volume** at `/app/.cache`
5. **Runs your app**:
   ```bash
   gunicorn web_app:app --bind 0.0.0.0:$PORT ...
   ```

## Common Questions

### Q: Do I need to commit my venv/ folder?

**No!** The `venv/` folder is in `.gitignore` and should never be committed.

- Your local venv is only for development
- Railway builds its own fresh environment
- Committing venv would make your repo huge and cause conflicts

### Q: What if I add a new dependency?

**Local:**
```bash
source venv/bin/activate
pip install new-package==1.2.3
pip freeze | grep new-package >> requirements.txt  # Add to requirements.txt
```

**Railway:**
- Push updated `requirements.txt` to GitHub
- Railway automatically installs it on next deploy

### Q: How do I know requirements.txt is complete?

Run the test script:
```bash
source venv/bin/activate
./test_deployment.sh
```

This checks that all imports work with just the venv dependencies.

### Q: What if Railway build fails with "ModuleNotFoundError"?

This means a package is missing from `requirements.txt`:

1. Check which module is missing in Railway logs
2. Add it to `requirements.txt` with version:
   ```
   missing-package==1.2.3
   ```
3. Commit and push
4. Railway will rebuild automatically

### Q: Can I use different package versions on Railway vs local?

**Not recommended!** Always keep them in sync:

- Use the same Python version (3.11.9, specified in `runtime.txt`)
- Use the same package versions (specified in `requirements.txt`)
- Test locally with gunicorn (Railway's production server)

This ensures "it works on my machine" = "it works on Railway"

## Workflow Summary

### Daily Development
```bash
# 1. Activate venv
source venv/bin/activate

# 2. Make changes
# Edit code, add features, etc.

# 3. Test locally
python web_app.py

# 4. When ready, test with production server
gunicorn web_app:app --bind 127.0.0.1:5001 --timeout 300 --workers 1
```

### Before Deploying
```bash
# 1. Ensure venv is active
source venv/bin/activate

# 2. Run deployment test
./test_deployment.sh

# 3. If it passes, commit and push
git add .
git commit -m "Your changes"
git push origin ggajavelli/deploy_to_railway

# 4. Railway auto-deploys
# Watch logs in Railway dashboard
```

## Troubleshooting

### "Command 'gunicorn' not found"

You forgot to activate venv:
```bash
source venv/bin/activate
```

### "ModuleNotFoundError: No module named 'X'"

Missing from requirements.txt:
```bash
# Activate venv first
source venv/bin/activate

# Install it
pip install package-name==1.2.3

# Add to requirements.txt
echo "package-name==1.2.3" >> requirements.txt
```

### Different behavior on Railway vs local

Check environment variables:
```bash
# Local uses .env file
cat .env

# Railway uses dashboard variables
# Go to Railway → Your service → Variables
```

Make sure they match!

---

**Key Takeaway:** Your local venv and Railway's environment are separate. The `requirements.txt` file is the contract between them - it ensures both have the same dependencies.

