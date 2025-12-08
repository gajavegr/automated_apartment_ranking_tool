#!/bin/bash

# Cursor Connection Diagnostic Script
# Run this when Cursor chat is frozen to diagnose connection issues

echo "=========================================="
echo "Cursor Connection Diagnostics"
echo "=========================================="
echo ""

# 1. Check Cursor processes
echo "1. Cursor Processes:"
ps aux | grep -i cursor | grep -v grep
echo ""

# 2. Check network connections
echo "2. Active Network Connections:"
lsof -i -P | grep -i cursor | head -20
echo ""

# 3. Check DNS resolution
echo "3. DNS Resolution Test:"
echo "Testing api.cursor.sh..."
dig +short api.cursor.sh || echo "DNS lookup failed"
echo ""

# 4. Check network interface status
echo "4. Network Interface Status:"
ifconfig | grep -A 5 "en0\|en1" | head -20
echo ""

# 5. Check DNS cache
echo "5. DNS Cache Status:"
dscacheutil -statistics | grep -A 5 "Cache"
echo ""

# 6. Check Cursor cache directories
echo "6. Cursor Cache Directories:"
if [ -d ~/Library/Application\ Support/Cursor/Cache ]; then
    echo "Cache directory exists:"
    ls -lh ~/Library/Application\ Support/Cursor/Cache | head -10
else
    echo "Cache directory not found"
fi
echo ""

# 7. Check recent Cursor logs
echo "7. Recent Cursor Logs (last 20 lines):"
if [ -d ~/Library/Logs/Cursor ]; then
    find ~/Library/Logs/Cursor -name "*.log" -type f -exec tail -5 {} \; 2>/dev/null | head -20
else
    echo "Log directory not found"
fi
echo ""

# 8. Network connectivity test
echo "8. Network Connectivity:"
ping -c 2 8.8.8.8 > /dev/null 2>&1 && echo "✓ Internet connectivity OK" || echo "✗ Internet connectivity FAILED"
ping -c 2 api.cursor.sh > /dev/null 2>&1 && echo "✓ Cursor API reachable" || echo "✗ Cursor API unreachable"
echo ""

echo "=========================================="
echo "Quick Fix Suggestions:"
echo "=========================================="
echo "1. Reload Cursor window: Cmd+Shift+P -> 'Developer: Reload Window'"
echo "2. Clear cache: rm -rf ~/Library/Application\\ Support/Cursor/Cache/*"
echo "3. Flush DNS: sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder"
echo "4. Restart network: sudo ifconfig en0 down && sudo ifconfig en0 up"
echo ""












