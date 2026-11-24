# Saudi Weekend Planner: every SQLite operation of the server
import json
import sqlite3
import time

from places_data import PLACES
from security import TOKEN_HOURS

DB_FILE = 'planner.db'

SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires REAL NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS places (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL, city TEXT NOT NULL, category TEXT NOT NULL,
        lat REAL NOT NULL, lng REAL NOT NULL,
        cost INTEGER NOT NULL, duration_min INTEGER NOT NULL,
        opens TEXT NOT NULL, closes TEXT NOT NULL, description TEXT)''',
    '''CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        home_city TEXT NOT NULL,
        destinations TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        people INTEGER NOT NULL,
        budget INTEGER NOT NULL,
        transport TEXT NOT NULL,
        notes TEXT,
        stays TEXT NOT NULL DEFAULT '',
        car_kmpl INTEGER NOT NULL DEFAULT 12,
        fuel TEXT NOT NULL DEFAULT '91')''',
    '''CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY,
        trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        place_id INTEGER REFERENCES places(id),
        day TEXT NOT NULL,
        start_time TEXT NOT NULL,
        name TEXT NOT NULL, city TEXT NOT NULL, category TEXT NOT NULL,
        lat REAL NOT NULL, lng REAL NOT NULL,
        duration_min INTEGER NOT NULL,
        cost_per_person REAL NOT NULL,
        actual_cost REAL,
        opens TEXT NOT NULL, closes TEXT NOT NULL,
        notes TEXT)''',
    '''CREATE TABLE IF NOT EXISTS route_cache (
        leg TEXT PRIMARY KEY,
        km REAL NOT NULL,
        minutes REAL NOT NULL,
        geometry TEXT NOT NULL)''',
]

TRIP_FIELDS = ['name', 'home_city', 'destinations', 'start_date', 'end_date',
               'people', 'budget', 'transport', 'notes', 'stays', 'car_kmpl', 'fuel']
# columns added after the first version: an older planner.db gets them with ALTER TABLE
NEW_TRIP_COLUMNS = {'stays': "TEXT NOT NULL DEFAULT ''", 'car_kmpl': 'INTEGER NOT NULL DEFAULT 12',
                    'fuel': "TEXT NOT NULL DEFAULT '91'"}
ACTIVITY_FIELDS = ['place_id', 'day', 'start_time', 'name', 'city', 'category', 'lat', 'lng',
                   'duration_min', 'cost_per_person', 'actual_cost', 'opens', 'closes', 'notes']


class Database:
    """Opens a new connection for every call, saves with commit and always closes."""

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file

    def connect(self):
        conn = sqlite3.connect(self.db_file)
        # rows that can be read by column name, like a dict
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def run(self, sql, params=(), many=False):
        """Runs one change (INSERT, UPDATE, DELETE) and returns the cursor."""
        conn = self.connect()
        try:
            with conn:
                if many:
                    return conn.executemany(sql, params)
                return conn.execute(sql, params)
        finally:
            conn.close()

    def rows(self, sql, params=()):
        """Runs one SELECT and returns a list of dicts."""
        conn = self.connect()
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def row(self, sql, params=()):
        found = self.rows(sql, params)
        return found[0] if found else None

    # ---- setup
    def create_tables(self):
        # IF NOT EXISTS keeps every saved record
        conn = self.connect()
        try:
            with conn:
                for sql in SCHEMA:
                    conn.execute(sql)
                # an older planner.db misses the new columns: add them and keep every saved trip
                columns = [row[1] for row in conn.execute('PRAGMA table_info(trips)')]
                for column, kind in NEW_TRIP_COLUMNS.items():
                    if column not in columns:
                        conn.execute('ALTER TABLE trips ADD COLUMN %s %s' % (column, kind))
                # the catalogue of places is added once, when it is empty
                if conn.execute('SELECT count(*) FROM places').fetchone()[0] == 0:
                    conn.executemany('INSERT INTO places (name, city, category, lat, lng, cost, duration_min, '
                                     'opens, closes, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', PLACES)
        finally:
            conn.close()

    # ---- users and sessions
    def add_user(self, username, salt, password_hash):
        sql = 'INSERT INTO users (username, salt, password_hash, created_at) VALUES (?, ?, ?, ?)'
        return self.run(sql, (username, salt, password_hash, time.strftime('%Y-%m-%d %H:%M'))).lastrowid

    def find_user(self, username):
        return self.row('SELECT * FROM users WHERE username = ?', (username,))

    def add_session(self, token, user_id):
        # old tokens of the user are removed at each login
        self.run('DELETE FROM sessions WHERE expires < ?', (time.time(),))
        self.run('INSERT INTO sessions (token, user_id, expires) VALUES (?, ?, ?)',
                 (token, user_id, time.time() + TOKEN_HOURS * 3600))

    def user_of_token(self, token):
        sql = ('SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id '
               'WHERE sessions.token = ? AND sessions.expires > ?')
        return self.row(sql, (token, time.time()))

    def delete_session(self, token):
        self.run('DELETE FROM sessions WHERE token = ?', (token,))

    # ---- places
    def places(self, city=''):
        if city:
            return self.rows('SELECT * FROM places WHERE city = ? ORDER BY category, name', (city,))
        return self.rows('SELECT * FROM places ORDER BY city, category, name')

    def place(self, place_id):
        return self.row('SELECT * FROM places WHERE id = ?', (place_id,))

    # ---- the saved roads from OSRM
    def cached_route(self, key):
        row = self.row('SELECT km, minutes, geometry FROM route_cache WHERE leg = ?', (key,))
        if row is None:
            return None
        return {'km': row['km'], 'minutes': row['minutes'], 'geometry': json.loads(row['geometry'])}

    def save_route(self, key, route):
        self.run('INSERT OR REPLACE INTO route_cache (leg, km, minutes, geometry) VALUES (?, ?, ?, ?)',
                 (key, route['km'], route['minutes'], json.dumps(route['geometry'])))

    # ---- trips: every query has user_id, so a user only reaches their own trips
    def trips(self, user_id):
        sql = ('SELECT trips.*, (SELECT count(*) FROM activities WHERE trip_id = trips.id) AS activity_count '
               'FROM trips WHERE user_id = ? ORDER BY start_date, id')
        return self.rows(sql, (user_id,))

    def trip(self, user_id, trip_id):
        return self.row('SELECT * FROM trips WHERE id = ? AND user_id = ?', (trip_id, user_id))

    def add_trip(self, user_id, values):
        sql = ('INSERT INTO trips (user_id, ' + ', '.join(TRIP_FIELDS) + ') VALUES (?' + ', ?' * len(TRIP_FIELDS) + ')')
        return self.run(sql, [user_id] + [values.get(f, '') for f in TRIP_FIELDS]).lastrowid

    def edit_trip(self, user_id, trip_id, values):
        sql = ('UPDATE trips SET ' + ', '.join(f + ' = ?' for f in TRIP_FIELDS) + ' WHERE id = ? AND user_id = ?')
        return self.run(sql, [values.get(f, '') for f in TRIP_FIELDS] + [trip_id, user_id]).rowcount

    def delete_trip(self, user_id, trip_id):
        return self.run('DELETE FROM trips WHERE id = ? AND user_id = ?', (trip_id, user_id)).rowcount

    # ---- activities
    def activities(self, trip_id):
        return self.rows('SELECT * FROM activities WHERE trip_id = ? ORDER BY day, start_time', (trip_id,))

    def activity(self, user_id, activity_id):
        sql = ('SELECT activities.* FROM activities JOIN trips ON trips.id = activities.trip_id '
               'WHERE activities.id = ? AND trips.user_id = ?')
        return self.row(sql, (activity_id, user_id))

    def add_activities(self, trip_id, items):
        sql = ('INSERT INTO activities (trip_id, ' + ', '.join(ACTIVITY_FIELDS) + ') VALUES (?'
               + ', ?' * len(ACTIVITY_FIELDS) + ')')
        self.run(sql, [[trip_id] + [item.get(f) for f in ACTIVITY_FIELDS] for item in items], many=True)

    def edit_activity(self, activity_id, values):
        sql = 'UPDATE activities SET ' + ', '.join(f + ' = ?' for f in ACTIVITY_FIELDS) + ' WHERE id = ?'
        return self.run(sql, [values.get(f) for f in ACTIVITY_FIELDS] + [activity_id]).rowcount

    def delete_activity(self, activity_id):
        return self.run('DELETE FROM activities WHERE id = ?', (activity_id,)).rowcount

    def clear_activities(self, trip_id):
        return self.run('DELETE FROM activities WHERE trip_id = ?', (trip_id,)).rowcount
