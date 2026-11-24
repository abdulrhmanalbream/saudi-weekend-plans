# Saudi Weekend Planner: creates the tables and an optional demo account
# Run it once with: python setup_db.py
# (server.py also creates the tables, so this step only adds the demo data)
from database import Database
from planner import local_plan
from security import hash_password

DEMO_USER = 'demo'
DEMO_PASSWORD = 'weekend2026'

db = Database()
db.create_tables()
print('tables ready,', len(db.places()), 'places in the catalogue')

if db.find_user(DEMO_USER):
    print('the demo account already exists: nothing added')
else:
    salt, digest = hash_password(DEMO_PASSWORD)
    user_id = db.add_user(DEMO_USER, salt, digest)
    trips = [
        {'name': 'Diriyah and Boulevard weekend', 'home_city': 'Riyadh', 'destinations': 'Riyadh',
         'start_date': '2026-12-03', 'end_date': '2026-12-05', 'people': 4, 'budget': 3500,
         'transport': 'car', 'notes': 'Family weekend at home'},
        {'name': 'Jeddah by the sea', 'home_city': 'Riyadh', 'destinations': 'Jeddah',
         'start_date': '2026-12-10', 'end_date': '2026-12-12', 'people': 2, 'budget': 6000,
         'transport': 'flight', 'notes': 'Fly on Thursday morning'},
    ]
    places = db.places()
    for trip in trips:
        trip_id = db.add_trip(user_id, trip)
        trip = db.trip(user_id, trip_id)
        plan = local_plan(trip, places, ['Heritage', 'Food', 'Beach', 'Entertainment'], 'normal')
        by_id = {p['id']: p for p in places}
        db.add_activities(trip_id, [{
            'place_id': step['place_id'], 'day': step['day'], 'start_time': step['start_time'],
            'name': by_id[step['place_id']]['name'], 'city': by_id[step['place_id']]['city'],
            'category': by_id[step['place_id']]['category'], 'lat': by_id[step['place_id']]['lat'],
            'lng': by_id[step['place_id']]['lng'], 'duration_min': by_id[step['place_id']]['duration_min'],
            'cost_per_person': by_id[step['place_id']]['cost'], 'actual_cost': None,
            'opens': by_id[step['place_id']]['opens'], 'closes': by_id[step['place_id']]['closes'],
            'notes': step['note']} for step in plan])
    print('demo account ready: username %s, password %s, %d trips' % (DEMO_USER, DEMO_PASSWORD, len(trips)))
