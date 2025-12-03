"""
Rate limiter to prevent exceeding API quota limits

Tracks API calls across different services and enforces rate limits
"""

import time
from collections import deque
from threading import Lock
from typing import Dict, Optional


class RateLimiter:
    """
    Rate limiter for API calls with per-service tracking
    
    Prevents exceeding API quotas by tracking calls and enforcing delays
    """
    
    def __init__(self):
        self.locks: Dict[str, Lock] = {}
        self.call_times: Dict[str, deque] = {}
        
        # Rate limits per service (calls per minute)
        self.limits = {
            'google_sheets_read': 50,      # Google Sheets: 60/min, use 50 for safety
            'google_sheets_write': 50,     # Google Sheets: 60/min, use 50 for safety
            'google_maps_geocode': 50,     # Google Maps: varies by plan, conservative default
            'google_places': 100,          # Google Places: typically higher limit
            'google_directions': 50,       # Google Directions
            'google_elevation': 50,        # Google Elevation
        }
        
        # Initialize locks and deques for each service
        for service in self.limits.keys():
            self.locks[service] = Lock()
            self.call_times[service] = deque()
    
    def wait_if_needed(self, service: str) -> None:
        """
        Wait if necessary to respect rate limits
        
        Args:
            service: The API service name
        """
        if service not in self.limits:
            # Unknown service, use conservative default
            service = 'default'
            if service not in self.limits:
                self.limits[service] = 30
                self.locks[service] = Lock()
                self.call_times[service] = deque()
        
        with self.locks[service]:
            now = time.time()
            window_start = now - 60  # 60 seconds window
            
            # Remove calls older than 1 minute
            while self.call_times[service] and self.call_times[service][0] < window_start:
                self.call_times[service].popleft()
            
            # Check if we've hit the limit
            if len(self.call_times[service]) >= self.limits[service]:
                # Calculate how long to wait
                oldest_call = self.call_times[service][0]
                wait_time = 60 - (now - oldest_call) + 0.1  # Add small buffer
                
                if wait_time > 0:
                    print(f"⏳ Rate limit reached for {service} ({self.limits[service]}/min). Waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    
                    # Clean up old entries after waiting
                    now = time.time()
                    window_start = now - 60
                    while self.call_times[service] and self.call_times[service][0] < window_start:
                        self.call_times[service].popleft()
            
            # Record this call
            self.call_times[service].append(time.time())
    
    def get_stats(self, service: Optional[str] = None) -> Dict:
        """
        Get rate limit statistics
        
        Args:
            service: Specific service to get stats for, or None for all
            
        Returns:
            Dictionary with rate limit stats
        """
        stats = {}
        
        services = [service] if service else self.limits.keys()
        
        for svc in services:
            if svc not in self.call_times:
                continue
                
            with self.locks[svc]:
                now = time.time()
                window_start = now - 60
                
                # Count calls in the last minute
                recent_calls = sum(1 for t in self.call_times[svc] if t >= window_start)
                
                stats[svc] = {
                    'calls_last_minute': recent_calls,
                    'limit': self.limits[svc],
                    'remaining': max(0, self.limits[svc] - recent_calls),
                    'percentage_used': (recent_calls / self.limits[svc] * 100) if self.limits[svc] > 0 else 0
                }
        
        return stats
    
    def reset(self, service: Optional[str] = None) -> None:
        """
        Reset rate limit tracking for a service
        
        Args:
            service: Specific service to reset, or None for all
        """
        services = [service] if service else self.limits.keys()
        
        for svc in services:
            if svc in self.locks:
                with self.locks[svc]:
                    self.call_times[svc].clear()


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

