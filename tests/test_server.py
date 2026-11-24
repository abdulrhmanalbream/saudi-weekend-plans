# Tests of the Flask routes: login, security, validation, CRUD and the planner route
# Run all tests with: python -m unittest discover tests
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import server  # noqa: E402
from database import Database  # noqa: E402
from routing import RoadRouter  # noqa: E402

TRIP = {'name': 'Test trip', 'home_city': 'Riyadh', 'destinations': 'Riyadh', 'start_date': '2026-12-03',
        'end_date': '2026-12-04', 'people': '2', 'budget': '3000', 'transport': 'car', 'notes': ''}


class ServerTest(unittest.TestCase):
    def setUp(self):
        # a fresh database file for every test
        handle, self.path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        server.db = Database(self.path)
        server.db.create_tables()
        server.limiter.fails.clear()
        server.gemini.key = ''          # the tests never call the internet
        server.router = RoadRouter(server.db, enabled=False)
        server.saved_roads = RoadRouter(server.db, enabled=False)
        self.client = server.app.test_client()

    def tearDown(self):
        os.remove(self.path)

    def login(self, name='sara', password='weekend2026'):
        self.client.post('/register', data={'username': name, 'password': password})
        token = self.client.post('/login', data={'username': name, 'password': password}).json['token']
        return {'Authorization': 'Bearer ' + token}

    def new_trip(self, headers, **changes):
        values = dict(TRIP, **changes)
        return self.client.post('/trips/add', headers=headers, data=values)


class TestAccounts(ServerTest):
    def test_register_and_login(self):
        self.assertEqual(self.client.post('/register', data={'username': 'sara', 'password': 'weekend2026'}).status_code, 200)
        reply = self.client.post('/login', data={'username': 'sara', 'password': 'weekend2026'})
        self.assertEqual(reply.status_code, 200)
        self.assertIn('token', reply.json)

    def test_weak_password_is_refused(self):
        self.assertEqual(self.client.post('/register', data={'username': 'sara', 'password': '12345678'}).status_code, 400)

    def test_duplicate_username_is_409(self):
        self.client.post('/register', data={'username': 'sara', 'password': 'weekend2026'})
        self.assertEqual(self.client.post('/register', data={'username': 'sara', 'password': 'weekend2026'}).status_code, 409)

    def test_password_is_not_stored_in_clear(self):
        self.client.post('/register', data={'username': 'sara', 'password': 'weekend2026'})
        user = server.db.find_user('sara')
        self.assertNotIn('weekend2026', user['password_hash'])
        self.assertEqual(len(user['password_hash']), 64)

    def test_wrong_password_is_401(self):
        self.client.post('/register', data={'username': 'sara', 'password': 'weekend2026'})
        self.assertEqual(self.client.post('/login', data={'username': 'sara', 'password': 'nope'}).status_code, 401)

    def test_lock_after_five_wrong_passwords(self):
        self.client.post('/register', data={'username': 'sara', 'password': 'weekend2026'})
        for _ in range(5):
            self.client.post('/login', data={'username': 'sara', 'password': 'nope'})
        reply = self.client.post('/login', data={'username': 'sara', 'password': 'weekend2026'})
        self.assertEqual(reply.status_code, 429)

    def test_no_token_is_401(self):
        self.assertEqual(self.client.get('/trips').status_code, 401)

    def test_logout_ends_the_token(self):
        headers = self.login()
        self.client.post('/logout', headers=headers)
        self.assertEqual(self.client.get('/trips', headers=headers).status_code, 401)


class TestTrips(ServerTest):
    def test_empty_list(self):
        reply = self.client.get('/trips', headers=self.login())
        self.assertEqual(reply.json['count'], 0)

    def test_add_view_edit_delete(self):
        headers = self.login()
        trip_id = self.new_trip(headers).json['trip']['id']
        self.assertEqual(self.client.get('/trips/%d' % trip_id, headers=headers).status_code, 200)
        edited = self.client.post('/trips/edit/%d' % trip_id, headers=headers, data=dict(TRIP, name='New name')).json
        self.assertEqual(edited['trip']['name'], 'New name')
        self.assertEqual(self.client.post('/trips/delete/%d' % trip_id, headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/trips/%d' % trip_id, headers=headers).status_code, 404)

    def test_data_remains_after_restart(self):
        headers = self.login()
        self.new_trip(headers)
        # a new Database object on the same file is like a restart of the server
        server.db = Database(self.path)
        self.assertEqual(self.client.get('/trips', headers=headers).json['count'], 1)

    def test_validation_errors_are_400(self):
        headers = self.login()
        for bad in ({'name': ''}, {'home_city': 'Paris'}, {'destinations': ''}, {'start_date': '2026-13-01'},
                    {'end_date': '2026-12-01'}, {'people': 'two'}, {'people': '0'}, {'budget': '-5'},
                    {'transport': 'boat'}, {'end_date': '2026-12-30'}):
            self.assertEqual(self.new_trip(headers, **bad).status_code, 400, bad)

    def test_free_stay_and_car_are_saved(self):
        headers = self.login()
        trip = self.new_trip(headers, destinations='Jeddah, Madinah', stays='Jeddah', car_kmpl='20', fuel='95').json
        self.assertEqual(trip['trip']['stays'], 'Jeddah')
        self.assertEqual(trip['trip']['car_kmpl'], 20)
        self.assertEqual(self.new_trip(headers, car_kmpl='2').status_code, 400)
        self.assertEqual(self.new_trip(headers, fuel='98').status_code, 400)
        self.assertEqual(self.new_trip(headers, stays='Paris').status_code, 400)

    def test_unknown_trip_is_404(self):
        headers = self.login()
        self.assertEqual(self.client.get('/trips/999', headers=headers).status_code, 404)
        self.assertEqual(self.client.post('/trips/edit/999', headers=headers, data=TRIP).status_code, 404)
        self.assertEqual(self.client.post('/trips/delete/999', headers=headers).status_code, 404)

    def test_users_cannot_see_each_other(self):
        sara = self.login('sara')
        trip_id = self.new_trip(sara).json['trip']['id']
        omar = self.login('omar')
        self.assertEqual(self.client.get('/trips/%d' % trip_id, headers=omar).status_code, 404)
        self.assertEqual(self.client.post('/trips/delete/%d' % trip_id, headers=omar).status_code, 404)
        self.assertEqual(self.client.get('/trips', headers=omar).json['count'], 0)

    def test_sql_injection_text_is_stored_as_text(self):
        headers = self.login()
        name = "x'); DROP TABLE trips; --"
        self.new_trip(headers, name=name)
        self.assertEqual(self.client.get('/trips', headers=headers).json['trips'][0]['name'], name)


class TestActivities(ServerTest):
    def test_add_edit_delete_activity(self):
        headers = self.login()
        trip_id = self.new_trip(headers).json['trip']['id']
        reply = self.client.post('/trips/%d/activities/add' % trip_id, headers=headers,
                                 data={'place_id': '5', 'day': '2026-12-03', 'start_time': '10:00'})
        self.assertEqual(reply.status_code, 200)
        activity_id = reply.json['activities'][0]['id']
        edited = self.client.post('/activities/edit/%d' % activity_id, headers=headers,
                                  data={'place_id': '5', 'day': '2026-12-03', 'start_time': '11:00', 'actual_cost': '25'})
        self.assertEqual(edited.json['activities'][0]['start_time'], '11:00')
        self.assertEqual(self.client.post('/activities/delete/%d' % activity_id, headers=headers).status_code, 200)
        self.assertEqual(self.client.post('/activities/delete/%d' % activity_id, headers=headers).status_code, 404)

    def test_bad_activity_values(self):
        headers = self.login()
        trip_id = self.new_trip(headers).json['trip']['id']
        for bad in ({'place_id': '5', 'day': '2027-01-01', 'start_time': '10:00'},
                    {'place_id': '5', 'day': '2026-12-03', 'start_time': '25:00'},
                    {'place_id': '999', 'day': '2026-12-03', 'start_time': '10:00'},
                    {'name': '', 'city': 'Riyadh', 'category': 'Food', 'day': '2026-12-03', 'start_time': '10:00',
                     'duration_min': '60'},
                    {'place_id': '5', 'day': '2026-12-03', 'start_time': '10:00', 'actual_cost': 'abc'}):
            reply = self.client.post('/trips/%d/activities/add' % trip_id, headers=headers, data=bad)
            self.assertEqual(reply.status_code, 400, bad)

    def test_custom_activity(self):
        headers = self.login()
        trip_id = self.new_trip(headers).json['trip']['id']
        reply = self.client.post('/trips/%d/activities/add' % trip_id, headers=headers,
                                 data={'name': 'Family dinner', 'city': 'Riyadh', 'category': 'Food',
                                       'day': '2026-12-03', 'start_time': '20:00', 'duration_min': '90',
                                       'cost_per_person': '50'})
        self.assertEqual(reply.status_code, 200)

    def test_autoplan_without_key_uses_local_planner(self):
        headers = self.login()
        trip_id = self.new_trip(headers).json['trip']['id']
        reply = self.client.post('/trips/%d/autoplan' % trip_id, headers=headers,
                                 data={'interests': 'Heritage,Food', 'pace': 'normal', 'engine': 'ai'})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json['source'], 'local')
        self.assertGreater(len(reply.json['activities']), 0)
        self.assertTrue(reply.json['analysis']['complete'], reply.json['analysis']['checks'])

    def test_unknown_path_is_json_404(self):
        reply = self.client.get('/nothing-here')
        self.assertEqual(reply.status_code, 404)
        self.assertIn('error', reply.json)


if __name__ == '__main__':
    unittest.main()
