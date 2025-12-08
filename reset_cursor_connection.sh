#!/bin/bash

# Quick Cursor Connection Reset Script
# This automates the faster workaround steps

echo "Resetting Cursor connection state..."
echo ""

# Step 1: Flush DNS cache
echo "1. Flushing DNS cache..."
sudo dscacheutil -flushcache 2>/dev/null
sudo killall -HUP mDNSResponder 2>/dev/null
echo "✓ DNS cache flushed"
echo ""

# Step 2: Clear Cursor cache (non-destructive - only clears network-related cache)
echo "2. Clearing Cursor network cache..."
if [ -d ~/Library/Application\ Support/Cursor/Cache ]; then
    # Only clear specific cache subdirectories that might affect connections
    rm -rf ~/Library/Application\ Support/Cursor/Cache/Cache_Data/* 2>/dev/null
    rm -rf ~/Library/Application\ Support/Cursor/GPUCache/* 2>/dev/null
    echo "✓ Cache cleared"
else
    echo "⚠ Cache directory not found (may be OK)"
fi
echo ""

# Step 3: Kill any stuck Cursor processes (optional, commented out by default)
# Uncomment the next 3 lines if you want to force-quit Cursor:
# echo "3. Killing Cursor processes..."
# killall Cursor 2>/dev/null
# echo "✓ Cursor processes terminated"
# echo ""

echo "=========================================="
echo "Reset complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. If Cursor is still open, reload the window:"
echo "   Cmd+Shift+P -> 'Developer: Reload Window'"
echo ""
echo "2. If Cursor is closed, restart it normally"
echo ""
echo "3. If issues persist, run: ./debug_cursor_connection.sh"
echo ""












