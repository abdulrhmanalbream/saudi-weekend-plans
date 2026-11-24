# Saudi Weekend Planner: the Flask back end
# Run it first with: python server.py   (it listens on port 5050)
import sqlite3
from datetime import date
from functools import wraps

from flask import Flask, g, request

from ai_planner import AIError, GeminiPlanner
from database import Database
from places_data import CATEGORIES, CITIES
from planner import FUEL_PRICES, TripPlanner, fit_times, local_plan, to_minutes, trip_days
from routing import RoadRouter
from security import LoginLimiter, check_password, hash_password, new_token

MAX_DAYS = 7
MAX_PEOPLE = 20
MAX_BUDGET = 500_000

app = Flask(__name__)
db = Database()
limiter = LoginLimiter()
gemini = GeminiPlanner()
router = RoadRouter(db)
# the list of trips uses only the roads already saved, so it stays fast
saved_roads = RoadRouter(db, fetch=False)


# ---------------------------------------------------------------- helpers
def error(message, status=400):
    # every error is JSON with a status code
    return {'error': message}, status


def login_required(view):
    """Reads the token from the Authorization header and puts the user in g.user."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get('Authorization', '')
        token = header[7:] if header.startswith('Bearer ') else ''
        user = db.user_of_token(token) if token else None
        if user is None:
            return error('Please log in again.', 401)
        g.user = user
        g.token = token
        return view(*args, **kwargs)
    return wrapper


def whole_number(form, field, low, high, label):
    """Reads one whole number field. Returns (value, None) or (None, message)."""
    text = form.get(field, '').strip()
    try:
        value = int(text)
    except ValueError:
        return None, label + ' must be a whole number.'
    if value < low or value > high:
        return None, '%s must be between %d and %d.' % (label, low, high)
    return value, None


def check_trip(form):
    """Checks the fields of a trip. Returns (values, None) or (None, message)."""
    name = form.get('name', '').strip()
    home = form.get('home_city', '').strip()
    destinations = [c.strip() for c in form.get('destinations', '').split(',') if c.strip()]
    transport = form.get('transport', '').strip()
    notes = form.get('notes', '').strip()
    # optional: cities with a house or family, where a night costs nothing
    stays = [c.strip() for c in form.get('stays', '').split(',') if c.strip()]
    if not name:
        return None, 'The trip name is required.'
    if len(name) > 60:
        return None, 'The trip name must be 60 characters or fewer.'
    if home not in CITIES:
        return None, 'Choose the home city from the list.'
    if not destinations:
        return None, 'Choose at least one destination city.'
    for city in destinations:
        if city not in CITIES:
            return None, 'Unknown destination: ' + city
    for city in stays:
        if city not in CITIES:
            return None, 'Unknown city for a free stay: ' + city
    if transport not in ('car', 'flight'):
        return None, 'Transport must be car or flight.'
    try:
        start = date.fromisoformat(form.get('start_date', '').strip())
        end = date.fromisoformat(form.get('end_date', '').strip())
    except ValueError:
        return None, 'Dates must look like 2026-12-04 (year-month-day).'
    if end < start:
        return None, 'The end date is before the start date.'
    if (end - start).days + 1 > MAX_DAYS:
        return None, 'A trip can be %d days at most.' % MAX_DAYS
    people, problem = whole_number(form, 'people', 1, MAX_PEOPLE, 'People')
    if problem:
        return None, problem
    budget, problem = whole_number(form, 'budget', 0, MAX_BUDGET, 'The budget')
    if problem:
        return None, problem
    if len(notes) > 300:
        return None, 'Notes must be 300 characters or fewer.'
    # how far the car goes on one litre (a big car about 8, a small car about 20)
    car_kmpl, problem = whole_number(form, 'car_kmpl', 4, 40, 'Km per litre') if form.get('car_kmpl', '').strip()         else (12, None)
    if problem:
        return None, problem
    fuel = form.get('fuel', '91').strip() or '91'
    if fuel not in FUEL_PRICES:
        return None, 'Fuel must be 91 or 95.'
    return {'name': name, 'home_city': home, 'destinations': ', '.join(destinations),
            'start_date': start.isoformat(), 'end_date': end.isoformat(), 'people': people,
            'budget': budget, 'transport': transport, 'notes': notes,
            'stays': ', '.join(c for c in stays if c != home), 'car_kmpl': car_kmpl, 'fuel': fuel}, None


def check_activity(form, trip):
    """Checks an activity. It comes from a place of the catalogue or is a custom one."""
    day = form.get('day', '').strip()
    start_time = form.get('start_time', '').strip()
    if day not in trip_days(trip['start_date'], trip['end_date']):
        return None, 'The day must be one of the trip dates.'
    try:
        if len(start_time) != 5 or not 0 <= to_minutes(start_time) < 24 * 60:
            raise ValueError
    except ValueError:
        return None, 'The start time must look like 09:30.'

    actual_text = form.get('actual_cost', '').strip()
    actual = None
    if actual_text:
        try:
            actual = float(actual_text)
        except ValueError:
            return None, 'The actual cost must be a number.'
        if actual < 0:
            return None, 'The actual cost cannot be negative.'
    notes = form.get('notes', '').strip()[:200]

    place_text = form.get('place_id', '').strip()
    if place_text:
        # an activity at a known place copies the place's details
        try:
            place = db.place(int(place_text))
        except ValueError:
            place = None
        if place is None:
            return None, 'Unknown place.'
        duration, problem = whole_number(form, 'duration_min', 10, 720, 'The duration') \
            if form.get('duration_min', '').strip() else (place['duration_min'], None)
        if problem:
            return None, problem
        cost_text = form.get('cost_per_person', '').strip()
        try:
            cost = float(cost_text) if cost_text else float(place['cost'])
        except ValueError:
            return None, 'The cost must be a number.'
        if cost < 0:
            return None, 'The cost cannot be negative.'
        return {'place_id': place['id'], 'day': day, 'start_time': start_time, 'name': place['name'],
                'city': place['city'], 'category': place['category'], 'lat': place['lat'], 'lng': place['lng'],
                'duration_min': duration, 'cost_per_person': cost, 'actual_cost': actual,
                'opens': place['opens'], 'closes': place['closes'], 'notes': notes}, None

    # a custom activity: the user gives the name and city; the city centre is its location
    name = form.get('name', '').strip()
    city = form.get('city', '').strip()
    category = form.get('category', '').strip()
    if not name:
        return None, 'Choose a place, or type the name of your own activity.'
    if city not in CITIES:
        return None, 'Choose the city of the activity.'
    if category not in CATEGORIES:
        return None, 'Choose a category.'
    duration, problem = whole_number(form, 'duration_min', 10, 720, 'The duration')
    if problem:
        return None, problem
    try:
        cost = float(form.get('cost_per_person', '0').strip() or 0)
    except ValueError:
        return None, 'The cost must be a number.'
    if cost < 0:
        return None, 'The cost cannot be negative.'
    return {'place_id': None, 'day': day, 'start_time': start_time, 'name': name[:60], 'city': city,
            'category': category, 'lat': CITIES[city]['lat'], 'lng': CITIES[city]['lng'],
            'duration_min': duration, 'cost_per_person': cost, 'actual_cost': actual,
            'opens': '00:00', 'closes': '23:59', 'notes': notes}, None


def full_trip(trip):
    """The trip with its activities and the analysis of the planner."""
    activities = db.activities(trip['id'])
    return {'trip': trip, 'activities': activities, 'analysis': TripPlanner(trip, activities, router).analyse()}


def items_from_plan(plan):
    # turn [{place_id, day, start_time, note}] into full activity rows
    items = []
    for step in plan:
        place = db.place(step['place_id'])
        items.append({'place_id': place['id'], 'day': step['day'], 'start_time': step['start_time'],
                      'name': place['name'], 'city': place['city'], 'category': place['category'],
                      'lat': place['lat'], 'lng': place['lng'], 'duration_min': place['duration_min'],
                      'cost_per_person': place['cost'], 'actual_cost': None,
                      'opens': place['opens'], 'closes': place['closes'], 'notes': step['note']})
    return items


# ---------------------------------------------------------------- open routes
@app.route('/')
def home():
    return {'message': 'the weekend planner server is ready', 'ai': gemini.available()}


@app.route('/options')
def options():
    # the city names, their centres (for the map) and the categories
    return {'cities': list(CITIES), 'centres': CITIES, 'categories': CATEGORIES, 'ai': gemini.available()}


@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '')
    if not 3 <= len(username) <= 30 or not username.replace('_', '').isalnum():
        return error('The username must be 3 to 30 letters, digits or _.')
    if len(password) < 8 or password.isdigit() or password.isalpha():
        return error('The password must be at least 8 characters, with letters and digits.')
    salt, digest = hash_password(password)
    try:
        db.add_user(username, salt, digest)
    except sqlite3.IntegrityError:
        return error('This username is taken.', 409)
    return {'message': 'Account created. You can log in now.'}


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '')
    wait = limiter.locked_for(username)
    if wait:
        return error('Too many wrong passwords. Try again in %d seconds.' % wait, 429)
    user = db.find_user(username)
    # the same message for an unknown user and a wrong password, so usernames cannot be guessed
    if user is None or not check_password(password, user['salt'], user['password_hash']):
        limiter.failed(username)
        return error('Wrong username or password.', 401)
    limiter.succeeded(username)
    token = new_token()
    db.add_session(token, user['id'])
    return {'message': 'Welcome, ' + user['username'], 'token': token, 'username': user['username']}


# ---------------------------------------------------------------- routes that need a login
@app.route('/logout', methods=['POST'])
@login_required
def logout():
    db.delete_session(g.token)
    return {'message': 'Logged out.'}


@app.route('/places')
@login_required
def places():
    city = request.args.get('city', '').strip()
    if city and city not in CITIES:
        return error('Unknown city: ' + city)
    return {'places': db.places(city)}


@app.route('/trips')
@login_required
def list_trips():
    # the JSON route of the saved records; the report helper uses it too
    trips = db.trips(g.user['id'])
    result = []
    for trip in trips:
        analysis = TripPlanner(trip, db.activities(trip['id']), saved_roads).analyse()
        result.append(dict(trip, status=analysis['status'], total=analysis['budget']['total'],
                           conflicts=analysis['conflicts']))
    return {'trips': result, 'count': len(result)}


@app.route('/trips/<int:trip_id>')
@login_required
def one_trip(trip_id):
    trip = db.trip(g.user['id'], trip_id)
    if trip is None:
        return error('No trip has the id %d.' % trip_id, 404)
    return full_trip(trip)


@app.route('/trips/add', methods=['POST'])
@login_required
def add_trip():
    values, problem = check_trip(request.form)
    if problem:
        return error(problem)
    trip_id = db.add_trip(g.user['id'], values)
    return dict(full_trip(db.trip(g.user['id'], trip_id)), message='Trip "%s" created.' % values['name'])


@app.route('/trips/edit/<int:trip_id>', methods=['POST'])
@login_required
def edit_trip(trip_id):
    values, problem = check_trip(request.form)
    if problem:
        return error(problem)
    if db.edit_trip(g.user['id'], trip_id, values) == 0:
        return error('No trip has the id %d. It may have been deleted.' % trip_id, 404)
    return dict(full_trip(db.trip(g.user['id'], trip_id)), message='Trip updated.')


@app.route('/trips/delete/<int:trip_id>', methods=['POST'])
@login_required
def delete_trip(trip_id):
    if db.delete_trip(g.user['id'], trip_id) == 0:
        return error('No trip has the id %d. It may have been deleted.' % trip_id, 404)
    return {'message': 'Trip deleted.'}


@app.route('/trips/<int:trip_id>/activities/add', methods=['POST'])
@login_required
def add_activity(trip_id):
    trip = db.trip(g.user['id'], trip_id)
    if trip is None:
        return error('No trip has the id %d.' % trip_id, 404)
    values, problem = check_activity(request.form, trip)
    if problem:
        return error(problem)
    db.add_activities(trip_id, [values])
    return dict(full_trip(trip), message='Added "%s".' % values['name'])


@app.route('/activities/edit/<int:activity_id>', methods=['POST'])
@login_required
def edit_activity(activity_id):
    old = db.activity(g.user['id'], activity_id)
    if old is None:
        return error('No activity has the id %d. It may have been deleted.' % activity_id, 404)
    trip = db.trip(g.user['id'], old['trip_id'])
    values, problem = check_activity(request.form, trip)
    if problem:
        return error(problem)
    db.edit_activity(activity_id, values)
    return dict(full_trip(trip), message='Updated "%s".' % values['name'])


@app.route('/activities/delete/<int:activity_id>', methods=['POST'])
@login_required
def delete_activity(activity_id):
    old = db.activity(g.user['id'], activity_id)
    if old is None:
        return error('No activity has the id %d. It may have been deleted.' % activity_id, 404)
    db.delete_activity(activity_id)
    return dict(full_trip(db.trip(g.user['id'], old['trip_id'])), message='Removed "%s".' % old['name'])


@app.route('/trips/<int:trip_id>/autoplan', methods=['POST'])
@login_required
def autoplan(trip_id):
    """Fills the trip with a plan from Gemini, or from the local planner."""
    trip = db.trip(g.user['id'], trip_id)
    if trip is None:
        return error('No trip has the id %d.' % trip_id, 404)
    interests = [c for c in request.form.get('interests', '').split(',') if c in CATEGORIES]
    pace = request.form.get('pace', 'normal')
    if pace not in ('relaxed', 'normal', 'packed'):
        return error('Pace must be relaxed, normal or packed.')
    use_ai = request.form.get('engine', 'ai') == 'ai'
    cities = [trip['home_city']] + [c.strip() for c in trip['destinations'].split(',')]
    places = [p for p in db.places() if p['city'] in cities]

    source = 'local'
    summary = 'Planned by the local planner: nearest matching places, inside opening hours.'
    plan = None
    if use_ai and gemini.available():
        try:
            summary, plan = gemini.plan(trip, places, interests, pace)
            source = 'gemini'
        except AIError as problem:
            summary = 'Gemini was not used (%s). Planned by the local planner instead.' % problem
    elif use_ai:
        summary = 'No GEMINI_API_KEY in .env. Planned by the local planner instead.'
    if plan is None:
        plan = local_plan(trip, places, interests, pace)
    if not plan:
        return error('No place fits these dates and cities.')

    # replace the old activities with the new plan
    # move the starts later where the real road takes longer than planned
    items = fit_times(trip, items_from_plan(plan), router)
    db.clear_activities(trip_id)
    db.add_activities(trip_id, items)
    return dict(full_trip(trip), message='Plan ready (%s): %d activities.' % (source, len(plan)),
                source=source, summary=summary)


@app.errorhandler(404)
def not_found(problem):
    return error('No such page on the server.', 404)


@app.errorhandler(405)
def wrong_method(problem):
    return error('This page does not accept that method.', 405)


@app.errorhandler(500)
def server_error(problem):
    return error('The server had a problem. Try again.', 500)


if __name__ == '__main__':
    db.create_tables()
    print('weekend planner server on http://127.0.0.1:5050  (Gemini: %s)'
          % ('on, ' + gemini.model if gemini.available() else 'off, local planner'))
    app.run(port=5050)
