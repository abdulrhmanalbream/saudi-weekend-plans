# Saudi Weekend Planner: real road distances, times and shapes from OSRM
# OSRM (Open Source Routing Machine) works on OpenStreetMap roads. The public server needs no key.
# Every answer is saved in SQLite, so the same leg is never asked twice.
import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OSRM_URL = 'https://router.project-osrm.org/route/v1/driving/{lng1},{lat1};{lng2},{lat2}' \
           '?overview=simplified&geometries=geojson'
HEADERS = {'User-Agent': 'SaudiWeekendPlanner/1.0 (student project)'}
# after a failed request, wait this long before trying OSRM again (no internet: do not wait on every leg)
RETRY_AFTER = 60


def leg_key(lat1, lng1, lat2, lng2):
    # about 10 m of precision is enough to reuse a saved route
    return '%.4f,%.4f;%.4f,%.4f' % (lat1, lng1, lat2, lng2)


class RoadRouter:
    """Asks OSRM for the road between two points, with a cache in the database."""

    def __init__(self, db, enabled=True, fetch=True):
        # fetch=False: only the saved roads are used (fast, for lists of many trips)
        self.db = db
        self.enabled = enabled
        self.fetch_new = fetch
        self.failed_at = 0
        self.lock = threading.Lock()

    def online(self):
        return self.enabled and self.fetch_new and time.time() - self.failed_at > RETRY_AFTER

    def fetch(self, lat1, lng1, lat2, lng2):
        """One request to OSRM. Returns {'km', 'minutes', 'geometry'} or None."""
        url = OSRM_URL.format(lat1=lat1, lng1=lng1, lat2=lat2, lng2=lng2)
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=8) as reply:
                data = json.loads(reply.read().decode('utf-8'))
        except (HTTPError, URLError, socket.timeout, ValueError):
            with self.lock:
                self.failed_at = time.time()
            return None
        if data.get('code') != 'Ok' or not data.get('routes'):
            return None
        route = data['routes'][0]
        # GeoJSON gives [lng, lat]; the map needs (lat, lng)
        shape = [(round(lat, 5), round(lng, 5)) for lng, lat in route['geometry']['coordinates']]
        return {'km': route['distance'] / 1000, 'minutes': route['duration'] / 60, 'geometry': shape}

    def road(self, lat1, lng1, lat2, lng2):
        """The road from the cache, or from OSRM when it is not saved yet. None when unknown."""
        key = leg_key(lat1, lng1, lat2, lng2)
        if not self.enabled:
            return None
        saved = self.db.cached_route(key)
        if saved:
            return saved
        if not self.online():
            return None
        found = self.fetch(lat1, lng1, lat2, lng2)
        if found:
            self.db.save_route(key, found)
        return found

    def prefetch(self, pairs):
        """Asks for many legs at the same time with threads, so the first view of a trip is fast."""
        missing = [p for p in dict.fromkeys(pairs) if not self.db.cached_route(leg_key(*p))]
        if not missing or not self.online():
            return
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda p: self.road(*p), missing))
