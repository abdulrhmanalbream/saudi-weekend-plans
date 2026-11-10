# Saudi Weekend Plans: the Flask back end
# Run it first with: python server.py   (it listens on port 5050)
import sqlite3
from datetime import datetime

from flask import Flask, request

# the database file, next to this program
DB_FILE = 'weekend.db'

# the values that the window may send for a city and a category
CITIES = ['Riyadh', 'Jeddah', 'Makkah', 'Madinah', 'Dammam', 'Khobar',
          'AlUla', 'Abha', 'Taif', 'Al Ahsa', 'Tabuk', 'Hail']
CATEGORIES = ['Cafe', 'Restaurant', 'Desert trip', 'Beach', 'Mall',
              'Park', 'Event', 'Family visit', 'Other']

# the limits of a budget, in Saudi riyals
MAX_BUDGET = 50000

# the columns of the table, in order
COLUMNS = ['id', 'name', 'city', 'category', 'budget', 'plan_date', 'notes']


class PlanStore:
    """Holds every database operation of the weekend plans."""

    def __init__(self, db_file):
        # the file of the SQLite database
        self.db_file = db_file

    def connect(self):
        # a new connection for each request
        return sqlite3.connect(self.db_file)

    def create_table(self):
        # IF NOT EXISTS keeps the records that are already saved
        sql = ('CREATE TABLE IF NOT EXISTS plan ('
               'id INTEGER PRIMARY KEY, '
               'name TEXT NOT NULL, '
               'city TEXT NOT NULL, '
               'category TEXT NOT NULL, '
               'budget INTEGER NOT NULL, '
               'plan_date TEXT NOT NULL, '
               'notes TEXT)')
        conn = self.connect()
        try:
            with conn:
                conn.execute(sql)
        finally:
            conn.close()

    def all_plans(self, city='', max_budget=None):
        # the base query, then one condition for each filter
        sql = 'SELECT * FROM plan WHERE 1 = 1'
        params = []
        if city:
            sql += ' AND city = ?'
            params.append(city)
        if max_budget is not None:
            sql += ' AND budget <= ?'
            params.append(max_budget)
        sql += ' ORDER BY plan_date, id'
        conn = self.connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        # a list of dictionaries, one for each row
        return [row_to_dict(row) for row in rows]

    def get_plan(self, plan_id):
        conn = self.connect()
        try:
            row = conn.execute('SELECT * FROM plan WHERE id = ?', (plan_id,)).fetchone()
        finally:
            conn.close()
        # None for an unknown id
        if row is None:
            return None
        return row_to_dict(row)

    def add_plan(self, values):
        sql = ('INSERT INTO plan (name, city, category, budget, plan_date, notes) '
               'VALUES (?, ?, ?, ?, ?, ?)')
        conn = self.connect()
        try:
            # with conn: saves the change with commit()
            with conn:
                cur = conn.execute(sql, (values['name'], values['city'], values['category'],
                                         values['budget'], values['plan_date'], values['notes']))
        finally:
            conn.close()
        # the id of the new row
        return cur.lastrowid

    def edit_plan(self, plan_id, values):
        sql = ('UPDATE plan SET name = ?, city = ?, category = ?, budget = ?, '
               'plan_date = ?, notes = ? WHERE id = ?')
        conn = self.connect()
        try:
            with conn:
                cur = conn.execute(sql, (values['name'], values['city'], values['category'],
                                         values['budget'], values['plan_date'], values['notes'],
                                         plan_id))
        finally:
            conn.close()
        # 0 rows changed means an unknown id
        return cur.rowcount

    def delete_plan(self, plan_id):
        conn = self.connect()
        try:
            with conn:
                cur = conn.execute('DELETE FROM plan WHERE id = ?', (plan_id,))
        finally:
            conn.close()
        # 0 rows deleted means an unknown id
        return cur.rowcount


def row_to_dict(row):
    # pairs each column name with its value: {'id': 1, 'name': ...}
    return dict(zip(COLUMNS, row))


def check_values(form):
    """Reads the fields of a POST. Returns (values, None) or (None, error message)."""
    # the text of each field, without spaces at the ends
    name = form.get('name', '').strip()
    city = form.get('city', '').strip()
    category = form.get('category', '').strip()
    budget_text = form.get('budget', '').strip()
    plan_date = form.get('plan_date', '').strip()
    notes = form.get('notes', '').strip()

    # the required fields
    if name == '':
        return None, 'The name of the plan is required.'
    if len(name) > 60:
        return None, 'The name must be 60 characters or fewer.'
    if city not in CITIES:
        return None, 'Choose a city from the list.'
    if category not in CATEGORIES:
        return None, 'Choose a category from the list.'

    # int() fails when the budget is not a whole number
    try:
        budget = int(budget_text)
    except ValueError:
        return None, 'The budget must be a whole number of riyals.'
    if budget < 0 or budget > MAX_BUDGET:
        return None, 'The budget must be between 0 and ' + str(MAX_BUDGET) + ' SAR.'

    # strptime() fails when the date is not a real YYYY-MM-DD date
    try:
        datetime.strptime(plan_date, '%Y-%m-%d')
    except ValueError:
        return None, 'The date must look like 2026-12-04 (year-month-day).'

    if len(notes) > 200:
        return None, 'The notes must be 200 characters or fewer.'

    values = {'name': name, 'city': city, 'category': category,
              'budget': budget, 'plan_date': plan_date, 'notes': notes}
    return values, None


# the application object and the store of the plans
app = Flask(__name__)
store = PlanStore(DB_FILE)


@app.route('/')
def home():
    # a dict is sent as JSON
    return {'message': 'the weekend plans server is ready'}


@app.route('/options')
def options():
    # the lists that the window puts in its drop-down boxes
    return {'cities': CITIES, 'categories': CATEGORIES}


@app.route('/plans')
def list_plans():
    # the filters, from the address: /plans?city=Riyadh&max_budget=300
    city = request.args.get('city', '').strip()
    max_text = request.args.get('max_budget', '').strip()

    if city != '' and city not in CITIES:
        return {'error': 'Unknown city: ' + city}, 400

    max_budget = None
    if max_text != '':
        try:
            max_budget = int(max_text)
        except ValueError:
            return {'error': 'The maximum budget must be a whole number.'}, 400
        if max_budget < 0:
            return {'error': 'The maximum budget cannot be negative.'}, 400

    try:
        plans = store.all_plans(city, max_budget)
    except sqlite3.Error as error:
        return {'error': 'Database error: ' + str(error)}, 500

    # the summary of the extra feature: how many plans and their total cost
    total = sum(plan['budget'] for plan in plans)
    return {'plans': plans, 'count': len(plans), 'total_budget': total}


@app.route('/plans/<int:plan_id>')
def one_plan(plan_id):
    plan = store.get_plan(plan_id)
    if plan is None:
        return {'error': 'No plan has the id ' + str(plan_id) + '.'}, 404
    return {'plan': plan}


@app.route('/plans/add', methods=['POST'])
def add_plan():
    values, error = check_values(request.form)
    if error:
        return {'error': error}, 400
    try:
        plan_id = store.add_plan(values)
    except sqlite3.Error as error:
        return {'error': 'Database error: ' + str(error)}, 500
    # the new record, so the window can show it
    return {'message': 'Saved "' + values['name'] + '".', 'plan': store.get_plan(plan_id)}


@app.route('/plans/edit/<int:plan_id>', methods=['POST'])
def edit_plan(plan_id):
    values, error = check_values(request.form)
    if error:
        return {'error': error}, 400
    try:
        changed = store.edit_plan(plan_id, values)
    except sqlite3.Error as error:
        return {'error': 'Database error: ' + str(error)}, 500
    if changed == 0:
        return {'error': 'No plan has the id ' + str(plan_id) + '. It may have been deleted.'}, 404
    return {'message': 'Updated "' + values['name'] + '".', 'plan': store.get_plan(plan_id)}


@app.route('/plans/delete/<int:plan_id>', methods=['POST'])
def delete_plan(plan_id):
    try:
        deleted = store.delete_plan(plan_id)
    except sqlite3.Error as error:
        return {'error': 'Database error: ' + str(error)}, 500
    if deleted == 0:
        return {'error': 'No plan has the id ' + str(plan_id) + '. It may have been deleted.'}, 404
    return {'message': 'Deleted plan ' + str(plan_id) + '.'}


@app.errorhandler(404)
def not_found(error):
    # a path in no route gets JSON too
    return {'error': 'No such page on the server.'}, 404


@app.errorhandler(405)
def wrong_method(error):
    return {'error': 'This page does not accept that method.'}, 405


if __name__ == '__main__':
    # make the table if it is missing, then start the server on port 5050
    store.create_table()
    print('weekend plans server on http://127.0.0.1:5050')
    app.run(port=5050)
