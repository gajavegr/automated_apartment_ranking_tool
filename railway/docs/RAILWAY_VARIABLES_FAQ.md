# Railway Environment Variables - Common Questions

## ❓ Railway Shows "GOOGLE_SHEETS_CREDENTIALS_PATH" as Suggested

**Short answer:** Ignore it! Don't set it in Railway.

### Why Railway Suggests It

Railway scans your code and finds this line in `config.py`:
```python
GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "...")
```

So it helpfully suggests you might want to set it. But our code has smart logic that handles both local and production cases automatically!

### The Smart Logic in config.py

```python
# Check if JSON content is provided (Railway way)
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")

if GOOGLE_SHEETS_CREDENTIALS_JSON:
    # ✅ Railway path: Write JSON to temp file
    GOOGLE_SHEETS_CREDENTIALS_PATH = "/tmp/google_sheets_credentials.json"
    with open(GOOGLE_SHEETS_CREDENTIALS_PATH, 'w') as f:
        f.write(GOOGLE_SHEETS_CREDENTIALS_JSON)
else:
    # ✅ Local path: Use existing file
    GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv(
        "GOOGLE_SHEETS_CREDENTIALS_PATH", 
        "credentials/google_sheets_credentials.json"
    )
```

### What This Means

| Scenario | What to Set | What Happens |
|----------|-------------|--------------|
| **Local development** | Nothing (or optionally `GOOGLE_SHEETS_CREDENTIALS_PATH` in .env) | Reads from `credentials/google_sheets_credentials.json` |
| **Railway** | Only `GOOGLE_SHEETS_CREDENTIALS_JSON` | Automatically writes to `/tmp/google_sheets_credentials.json` and uses that |

### Visual Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    config.py loads                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         Does GOOGLE_SHEETS_CREDENTIALS_JSON exist?
                       │
         ┌─────────────┴─────────────┐
         │                           │
        YES                         NO
    (Railway)                   (Local)
         │                           │
         ▼                           ▼
   Write JSON to              Use file path from
   /tmp/*.json                GOOGLE_SHEETS_CREDENTIALS_PATH
         │                     or default to
         │                     credentials/*.json
         │                           │
         └───────────┬───────────────┘
                     ▼
            gspread uses the file
```

## ✅ What to Set in Railway

### Required Variables (4)
```
GOOGLE_SHEET_ID=your_actual_sheet_id
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_MAPS_API_KEY=AIza...
GOOGLE_SHEETS_CREDENTIALS_JSON={"type":"service_account",...entire JSON...}
```

### Optional Variables
```
YOUR_WORK_ADDRESS=...
PARTNER_WORK_ADDRESS=...
CACHE_DIR=/app/.cache
CACHE_EXPIRE_HOURS=168
```

### Do NOT Set
```
❌ GOOGLE_SHEETS_CREDENTIALS_PATH
   (Our code handles this automatically)
```

## 🤔 What If I Set GOOGLE_SHEETS_CREDENTIALS_PATH Anyway?

**It won't break anything**, but it's unnecessary:
- If `GOOGLE_SHEETS_CREDENTIALS_JSON` is set, that takes priority
- The path you set would be ignored
- But it might confuse you later when debugging

**Best practice:** Keep it clean - only set what's needed!

## 📋 Railway Variable Checklist

When you look at Railway's "Variables" tab, you should see:

```
✅ GOOGLE_SHEET_ID                      (your sheet ID)
✅ ANTHROPIC_API_KEY                    (sk-ant-...)
✅ GOOGLE_MAPS_API_KEY                  (AIza...)
✅ GOOGLE_SHEETS_CREDENTIALS_JSON       ({"type":"service_account",...})
✅ CACHE_DIR                            (/app/.cache)
❓ YOUR_WORK_ADDRESS                    (optional, has default)
❓ PARTNER_WORK_ADDRESS                 (optional, has default)
❓ CACHE_EXPIRE_HOURS                   (optional, defaults to 168)

❌ GOOGLE_SHEETS_CREDENTIALS_PATH       (should NOT be set)
```

## 🔍 How to Verify in Railway Logs

After deployment, check logs for this line:
```
✓ Google Sheets credentials loaded from environment variable
```

If you see this, it means:
- ✅ `GOOGLE_SHEETS_CREDENTIALS_JSON` was found
- ✅ JSON was written to `/tmp/google_sheets_credentials.json`
- ✅ Path was set automatically
- ✅ Everything is working correctly!

## 🐛 Troubleshooting

### Error: "Could not find credentials file"

**Possible causes:**
1. `GOOGLE_SHEETS_CREDENTIALS_JSON` is not set in Railway
2. `GOOGLE_SHEETS_CREDENTIALS_JSON` has invalid JSON
3. `GOOGLE_SHEETS_CREDENTIALS_JSON` is truncated (didn't copy all of it)

**How to fix:**
1. Go to Railway → Variables
2. Check `GOOGLE_SHEETS_CREDENTIALS_JSON` exists
3. Open the value - verify it starts with `{` and ends with `}`
4. Compare with your local `credentials/google_sheets_credentials.json`
5. If different, copy-paste the entire local file again

### Error: "Permission denied writing to /tmp/"

**This is extremely rare on Railway**, but if it happens:
- Railway has issues with `/tmp/` permissions
- You can set `GOOGLE_SHEETS_CREDENTIALS_PATH=/app/credentials.json` as a workaround
- But report this to Railway support - `/tmp/` should always be writable

## 📚 Related Documentation

- **Full deployment guide:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Quick start:** [RAILWAY_QUICK_START.md](RAILWAY_QUICK_START.md)
- **Local vs Railway:** [LOCAL_VS_RAILWAY.md](LOCAL_VS_RAILWAY.md)
- **Complete checklist:** [READY_TO_DEPLOY.md](READY_TO_DEPLOY.md)

---

**TL;DR:** Railway suggests `GOOGLE_SHEETS_CREDENTIALS_PATH` because it's in the code, but you don't need to set it. Only set `GOOGLE_SHEETS_CREDENTIALS_JSON` (the actual JSON content), and our code handles the rest automatically! 🎉

