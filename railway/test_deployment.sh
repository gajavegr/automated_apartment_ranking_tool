#!/bin/bash
# Test deployment configuration locally before pushing to Railway

set -e  # Exit on error

echo "=========================================="
echo "Railway Deployment - Local Test"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in a virtual environment
echo "Checking virtual environment..."
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}✗${NC} Not in a virtual environment!"
    echo ""
    echo "Please activate your venv first:"
    echo "  $ source venv/bin/activate"
    echo ""
    echo "Or create one if it doesn't exist:"
    echo "  $ python3 -m venv venv"
    echo "  $ source venv/bin/activate"
    echo "  $ pip install -r requirements.txt"
    echo ""
    exit 1
else
    echo -e "${GREEN}✓${NC} Virtual environment active: $VIRTUAL_ENV"
fi
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "  Python version: $PYTHON_VERSION"

if [[ ! "$PYTHON_VERSION" =~ ^3\.11 ]]; then
    echo -e "${YELLOW}  ⚠️  Warning: Python version is $PYTHON_VERSION, Railway will use 3.11.9${NC}"
fi
echo ""

# Check if required files exist
echo "Checking deployment files..."
FILES=("Procfile" "railway.toml" "runtime.txt" "requirements.txt" ".railwayignore")
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file - MISSING!"
        exit 1
    fi
done
echo ""

# Check if .env exists (for local testing)
echo "Checking environment configuration..."
if [ -f ".env" ]; then
    echo -e "  ${GREEN}✓${NC} .env file exists"
    
    # Check for required variables
    REQUIRED_VARS=("GOOGLE_SHEET_ID" "ANTHROPIC_API_KEY" "GOOGLE_MAPS_API_KEY")
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -q "^$var=" .env && ! grep -q "^$var=$" .env && ! grep -q "^$var=.*your.*here" .env; then
            echo -e "  ${GREEN}✓${NC} $var is set"
        else
            echo -e "  ${YELLOW}⚠${NC}  $var is not set or uses placeholder"
        fi
    done
else
    echo -e "  ${RED}✗${NC} .env file not found"
    echo "     Create one from env.example for local testing"
    exit 1
fi
echo ""

# Check if Google Sheets credentials exist
echo "Checking credentials..."
if [ -f "credentials/google_sheets_credentials.json" ]; then
    echo -e "  ${GREEN}✓${NC} Google Sheets credentials found"
    
    # Validate it's valid JSON
    if python3 -c "import json; json.load(open('credentials/google_sheets_credentials.json'))" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Credentials file is valid JSON"
    else
        echo -e "  ${RED}✗${NC} Credentials file is not valid JSON!"
        exit 1
    fi
else
    echo -e "  ${RED}✗${NC} Google Sheets credentials not found"
    echo "     Expected at: credentials/google_sheets_credentials.json"
    exit 1
fi
echo ""

# Check if credentials are in .gitignore
echo "Checking .gitignore..."
if grep -q "credentials/google_sheets_credentials.json" .gitignore; then
    echo -e "  ${GREEN}✓${NC} Credentials are in .gitignore"
else
    echo -e "  ${RED}✗${NC} Credentials NOT in .gitignore!"
    echo "     Add 'credentials/google_sheets_credentials.json' to .gitignore"
    exit 1
fi

if grep -q "^\.env$" .gitignore; then
    echo -e "  ${GREEN}✓${NC} .env is in .gitignore"
else
    echo -e "  ${RED}✗${NC} .env NOT in .gitignore!"
    exit 1
fi
echo ""

# Check if gunicorn is in requirements
echo "Checking dependencies..."
if grep -q "gunicorn" requirements.txt; then
    echo -e "  ${GREEN}✓${NC} gunicorn is in requirements.txt"
else
    echo -e "  ${RED}✗${NC} gunicorn is NOT in requirements.txt!"
    echo "     Add: gunicorn==21.2.0"
    exit 1
fi
echo ""

# Test if gunicorn is installed
echo "Testing gunicorn installation..."
if python3 -m pip show gunicorn &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} gunicorn is installed"
else
    echo -e "  ${YELLOW}⚠${NC}  gunicorn is not installed locally"
    echo "     Run: pip install gunicorn==21.2.0"
fi
echo ""

# Check if Flask is installed
echo "Testing Flask installation..."
if python3 -c "import flask" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Flask is installed"
else
    echo -e "  ${RED}✗${NC} Flask is not installed!"
    echo "     Run: pip install -r requirements.txt"
    exit 1
fi
echo ""

# Test import of main modules
echo "Testing critical imports..."
MODULES=("anthropic" "gspread" "requests" "dotenv" "flask")
for module in "${MODULES[@]}"; do
    MODULE_IMPORT=$module
    if [ "$module" == "dotenv" ]; then
        MODULE_IMPORT="dotenv"
    fi
    
    if python3 -c "import $MODULE_IMPORT" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $module"
    else
        echo -e "  ${RED}✗${NC} $module - not installed"
        echo "     Run: pip install -r requirements.txt"
        exit 1
    fi
done
echo ""

# Check cache directory
echo "Checking cache configuration..."
CACHE_DIR=$(grep "^CACHE_DIR=" .env | cut -d'=' -f2 || echo ".cache")
echo "  Cache directory: $CACHE_DIR"

if [ -d "$CACHE_DIR" ]; then
    CACHE_SIZE=$(du -sh "$CACHE_DIR" 2>/dev/null | cut -f1 || echo "0")
    echo -e "  ${GREEN}✓${NC} Cache directory exists (size: $CACHE_SIZE)"
else
    echo -e "  ${YELLOW}⚠${NC}  Cache directory doesn't exist yet (will be created)"
fi
echo ""

# Verify web_app.py syntax
echo "Checking web_app.py syntax..."
if python3 -m py_compile web_app.py 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} web_app.py has valid syntax"
else
    echo -e "  ${RED}✗${NC} web_app.py has syntax errors!"
    exit 1
fi
echo ""

echo "=========================================="
echo -e "${GREEN}All checks passed! ✓${NC}"
echo "=========================================="
echo ""
echo -e "${YELLOW}Important:${NC} Railway will install dependencies fresh from requirements.txt"
echo "  Your local venv is only for testing - Railway builds its own environment"
echo ""
echo "Next steps:"
echo "  1. Test locally with gunicorn:"
echo "     $ gunicorn web_app:app --bind 127.0.0.1:5001 --timeout 300 --workers 1"
echo ""
echo "  2. Test health endpoint:"
echo "     $ curl http://127.0.0.1:5001/health"
echo ""
echo "  3. If all works, commit and push:"
echo "     $ git add ."
echo "     $ git commit -m 'Add Railway deployment configuration'"
echo "     $ git push origin ggajavelli/deploy_to_railway"
echo ""
echo "  4. Follow RAILWAY_QUICK_START.md to deploy!"
echo ""

