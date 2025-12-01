"""
Caching utility for storing scraped data to avoid redundant API calls
"""

import os
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import hashlib

import config


class Cache:
    """Simple file-based cache with expiration"""
    
    def __init__(self, cache_dir: str = None, expire_hours: int = None):
        """
        Initialize cache
        
        Args:
            cache_dir: Directory to store cache files
            expire_hours: Hours until cache entries expire
        """
        self.cache_dir = Path(cache_dir or config.CACHE_DIR)
        self.expire_hours = expire_hours or config.CACHE_EXPIRE_HOURS
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """Generate cache file path for a key"""
        # Hash the key to create a valid filename
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if exists and not expired, None otherwise
        """
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                cached_data = pickle.load(f)
            
            # Check if expired
            cached_time = cached_data.get('timestamp')
            if cached_time:
                expire_time = cached_time + timedelta(hours=self.expire_hours)
                if datetime.now() > expire_time:
                    # Expired, remove cache file
                    cache_path.unlink()
                    return None
            
            return cached_data.get('value')
        
        except Exception as e:
            print(f"Error reading cache for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
        """
        cache_path = self._get_cache_path(key)
        
        cached_data = {
            'timestamp': datetime.now(),
            'value': value,
            'key': key,
        }
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(cached_data, f)
        except Exception as e:
            print(f"Error writing cache for key {key}: {e}")
    
    def delete(self, key: str) -> None:
        """
        Delete value from cache
        
        Args:
            key: Cache key
        """
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
    
    def clear_expired(self) -> int:
        """
        Clear all expired cache entries
        
        Returns:
            Number of entries cleared
        """
        cleared = 0
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                
                cached_time = cached_data.get('timestamp')
                if cached_time:
                    expire_time = cached_time + timedelta(hours=self.expire_hours)
                    if datetime.now() > expire_time:
                        cache_file.unlink()
                        cleared += 1
            except Exception:
                # If we can't read it, delete it
                cache_file.unlink()
                cleared += 1
        
        return cleared
    
    def clear_all(self) -> int:
        """
        Clear all cache entries
        
        Returns:
            Number of entries cleared
        """
        cleared = 0
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink()
            cleared += 1
        return cleared
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = 0
        expired = 0
        valid = 0
        
        for cache_file in self.cache_dir.glob("*.cache"):
            total += 1
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                
                cached_time = cached_data.get('timestamp')
                if cached_time:
                    expire_time = cached_time + timedelta(hours=self.expire_hours)
                    if datetime.now() > expire_time:
                        expired += 1
                    else:
                        valid += 1
            except Exception:
                expired += 1
        
        return {
            'total': total,
            'valid': valid,
            'expired': expired,
        }


# Global cache instance
_cache = None


def get_cache() -> Cache:
    """Get global cache instance"""
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache

