"""
Versioned cache namespace for the live-room feed.

Instead of tracking and deleting every cached page/filter combination on
invalidation (unbounded key set), we prefix every key with a version counter
and bump the counter when any room is created or ended. Old keys simply
expire; readers never see stale data for longer than it takes to bump.
"""

from django.core.cache import cache

VERSION_KEY = "rooms:list:version"


def room_list_cache_key(query_string):
    version = cache.get(VERSION_KEY, 1)
    return f"rooms:list:v{version}:{query_string}"


def invalidate_room_list():
    try:
        cache.incr(VERSION_KEY)
    except ValueError:  # key not set yet
        cache.set(VERSION_KEY, 2, None)
