# Project Documentation

This directory contains all project documentation, organized by type.

## 📁 Directory Structure

```
docs/
├── README.md                 ← You are here (documentation index)
├── IMPROVEMENTS_SUMMARY.md   ← Overview of all improvements
│
├── feature_guides/           ← Feature documentation & guides
│   ├── COLUMN_MANAGEMENT.md
│   ├── FORCE_RECALCULATION_GUIDE.md
│   ├── GYM_BIKING_FEATURE.md
│   ├── GYM_SCORE_DISPLAY_ENHANCEMENTS.md
│   ├── GYM_SCORE_RECALC_GUIDE.md
│   ├── PREFERENCE_EVALUATION_GUIDE.md
│   ├── SELECTIVE_RECALCULATION_UI.md
│   ├── SORTABLE_EVAL_TABLE_FEATURE.md
│   └── WEB_INTERFACE_GUIDE.md
│
└── bug_fixes/                ← Bug fix documentation
    ├── AVAILABILITY_FILTERING_FIX.md
    ├── FIX_ADMIN_TAB_ISSUE.md
    ├── GRACEFUL_SHUTDOWN.md
    ├── PARTIAL_RECALC_FIX.md
    ├── PHOTO_SELECTOR_REWRITE.md
    ├── PLAYWRIGHT_FIX_SUMMARY.md
    ├── RATE_LIMITING_FIX.md
    ├── RATE_LIMITING_IMPROVEMENTS.md
    ├── SELECTIVE_COMPONENT_FIX.md
    └── SYNC_AVAILABILITY_COLUMN.md
```

## 🚀 Feature Guides

Comprehensive guides for major features and functionality:

### Core Features
- **[Web Interface Guide](feature_guides/WEB_INTERFACE_GUIDE.md)** - Complete guide to the web interface
- **[Preference Evaluation](feature_guides/PREFERENCE_EVALUATION_GUIDE.md)** - How preference-based evaluation works

### Scoring & Analysis
- **[Gym Score Enhancements](feature_guides/GYM_SCORE_DISPLAY_ENHANCEMENTS.md)** - Gym scoring improvements
- **[Gym Biking Feature](feature_guides/GYM_BIKING_FEATURE.md)** - Biking time for gyms >15min walk
- **[Sortable Evaluation Table](feature_guides/SORTABLE_EVAL_TABLE_FEATURE.md)** - Interactive preference evaluation

### Data Management
- **[Column Management](feature_guides/COLUMN_MANAGEMENT.md)** - Managing Google Sheets columns
- **[Force Recalculation](feature_guides/FORCE_RECALCULATION_GUIDE.md)** - How to force score recalculation
- **[Selective Recalculation UI](feature_guides/SELECTIVE_RECALCULATION_UI.md)** - UI for selective updates
- **[Gym Score Recalc](feature_guides/GYM_SCORE_RECALC_GUIDE.md)** - Recalculating gym scores

## 🐛 Bug Fixes

Documentation for significant bug fixes and improvements:

### Performance & Reliability
- **[Rate Limiting Fix](bug_fixes/RATE_LIMITING_FIX.md)** - Google Maps API rate limiting
- **[Rate Limiting Improvements](bug_fixes/RATE_LIMITING_IMPROVEMENTS.md)** - Enhanced rate limiting
- **[Graceful Shutdown](bug_fixes/GRACEFUL_SHUTDOWN.md)** - Clean shutdown handling

### UI Fixes
- **[Admin Tab Issue](bug_fixes/FIX_ADMIN_TAB_ISSUE.md)** - Admin tab fixes
- **[Photo Selector Rewrite](bug_fixes/PHOTO_SELECTOR_REWRITE.md)** - Photo selector improvements
- **[Playwright Fix](bug_fixes/PLAYWRIGHT_FIX_SUMMARY.md)** - Playwright issues resolved

### Data Integrity
- **[Availability Filtering](bug_fixes/AVAILABILITY_FILTERING_FIX.md)** - Filtering by availability
- **[Sync Availability Column](bug_fixes/SYNC_AVAILABILITY_COLUMN.md)** - Availability sync
- **[Partial Recalc Fix](bug_fixes/PARTIAL_RECALC_FIX.md)** - Partial recalculation issues
- **[Selective Component Fix](bug_fixes/SELECTIVE_COMPONENT_FIX.md)** - Component-specific fixes

## 📊 Overview Documents

- **[IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md)** - Complete list of all improvements and changes

## 🔍 Quick Reference

### Looking for...

**How to use a feature?**
→ Check [`feature_guides/`](feature_guides/)

**What bug was fixed?**
→ Check [`bug_fixes/`](bug_fixes/)

**What's changed overall?**
→ Read [`IMPROVEMENTS_SUMMARY.md`](IMPROVEMENTS_SUMMARY.md)

**How to deploy?**
→ See [`../railway/docs/`](../railway/docs/) for Railway deployment

**Project README?**
→ See [`../README.md`](../README.md) at project root

## 📝 Contributing

When adding new documentation:

1. **Feature guides** → `feature_guides/FEATURE_NAME.md`
2. **Bug fixes** → `bug_fixes/FIX_NAME.md`
3. **Update this index** → Add links above

## 🗂️ Other Documentation

- **Railway Deployment:** See [`../railway/docs/`](../railway/docs/)
- **Project README:** See [`../README.md`](../README.md)
- **Railway Quick Link:** See [`../RAILWAY.md`](../RAILWAY.md)

---

**Need help?** Check the relevant guide above or the main README.

