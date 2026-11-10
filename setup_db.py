# Saudi Weekend Plans: creates the table, and adds sample plans to an empty table
# Run it once with: python setup_db.py   (optional: server.py also creates the table)
from server import DB_FILE, PlanStore

# a few sample outings
SAMPLES = [
    {'name': 'Boulevard World evening', 'city': 'Riyadh', 'category': 'Event',
     'budget': 250, 'plan_date': '2026-12-04', 'notes': 'Buy tickets online'},
    {'name': 'Breakfast at Al Balad', 'city': 'Jeddah', 'category': 'Restaurant',
     'budget': 120, 'plan_date': '2026-12-05', 'notes': 'Ful and tamees'},
    {'name': 'Camping in the dunes', 'city': 'Riyadh', 'category': 'Desert trip',
     'budget': 400, 'plan_date': '2026-12-11', 'notes': 'Take firewood and a tent'},
    {'name': 'Half Moon Bay swim', 'city': 'Khobar', 'category': 'Beach',
     'budget': 80, 'plan_date': '2026-12-12', 'notes': ''},
    {'name': 'Coffee at a mountain cafe', 'city': 'Abha', 'category': 'Cafe',
     'budget': 60, 'plan_date': '2026-12-18', 'notes': 'Go before sunset'},
]

store = PlanStore(DB_FILE)
store.create_table()

# only add the samples when no plan is saved yet
if store.all_plans():
    print('the table already has plans: nothing added')
else:
    for plan in SAMPLES:
        store.add_plan(plan)
    print('table ready with', len(SAMPLES), 'sample plans in', DB_FILE)
