#!/usr/bin/env python3
"""
Quick script to force recalculation of gym scores for all apartments.
Use this when the gym scoring methodology changes (e.g., distance → walking time).
"""

import requests
import sys

def force_gym_recalculation():
    """Clear gym scores for all apartments to force recalculation"""
    
    url = 'http://127.0.0.1:5000/admin/force_recalculate'
    
    print("🔄 Forcing gym score recalculation for all apartments...")
    print("   (This will clear gym_score to trigger re-analysis)")
    print()
    
    response = requests.post(url, json={
        'component': 'gym_score',
        'addresses': 'all'
    })
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            print(f"✅ Success!")
            print(f"   Cleared gym scores for {data['cleared_count']} apartments")
            print(f"   Columns cleared: {', '.join(data['columns'])}")
            print()
            print(f"💡 {data['message']}")
            print()
            print("Next step: Go to the Analysis tab and click 'Run Analysis'")
            return 0
        else:
            print(f"❌ Error: {data.get('error', 'Unknown error')}")
            return 1
    else:
        print(f"❌ HTTP Error {response.status_code}: {response.text}")
        return 1

if __name__ == '__main__':
    sys.exit(force_gym_recalculation())

