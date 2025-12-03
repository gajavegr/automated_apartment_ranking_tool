#!/bin/bash
# Quick test of photo_selector with system Chrome

cd "$(dirname "$0")"
source venv/bin/activate

echo "Testing photo selector with a simple URL..."
echo ""
echo "This should:"
echo "1. Open Chrome browser"
echo "2. Navigate to example.com (for testing)"
echo "3. Wait for you to press S (save) or Q (quit)"
echo ""

python photo_selector.py "https://example.com" --address "Test Address"

