# Saudi Weekend Planner: the client side of HTTP
# Every request of the window goes through ApiClient.send(), so all errors are handled in one place.
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SERVER = 'http://127.0.0.1:5050'


class ApiClient:
    """Talks to Flask. Returns (True, data) or (False, message, status) for every request."""

    def __init__(self, server=SERVER):
        self.server = server
        # the token from /login, sent in the Authorization header
        self.token = None
        self.username = None

    def send(self, path, values=None, params=None, timeout=20):
        url = self.server + path
        if params:
            url += '?' + urlencode(params)
        # without data the request is a GET; with data (bytes) it is a POST
        data = urlencode(values).encode('utf-8') if values is not None else None
        headers = {'Authorization': 'Bearer ' + self.token} if self.token else {}
        request = Request(url, data=data, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as reply:
                return True, json.loads(reply.read().decode('utf-8')), reply.status
        # 4xx and 5xx replies raise HTTPError: it must come before URLError
        except HTTPError as error:
            try:
                message = json.loads(error.read().decode('utf-8')).get('error', 'The server refused the request.')
            except ValueError:
                message = 'The server answered with status %d.' % error.code
            return False, message, error.code
        except URLError as error:
            if isinstance(error.reason, socket.timeout):
                return False, 'The server took too long to answer. Try again.', 0
            return False, 'Cannot reach the server. Start server.py, then try again.', 0
        except socket.timeout:
            return False, 'The server took too long to answer. Try again.', 0
        except ValueError:
            return False, 'The server sent a reply that is not JSON.', 0

    # ---- the calls of the window, one method per route
    def register(self, username, password):
        return self.send('/register', {'username': username, 'password': password})

    def login(self, username, password):
        result = self.send('/login', {'username': username, 'password': password})
        if result[0]:
            self.token = result[1]['token']
            self.username = result[1]['username']
        return result

    def logout(self):
        result = self.send('/logout', {})
        self.token = None
        return result

    def options(self):
        return self.send('/options')

    def places(self, city=''):
        return self.send('/places', params={'city': city} if city else None)

    def trips(self):
        return self.send('/trips')

    def trip(self, trip_id):
        return self.send('/trips/%d' % trip_id)

    def add_trip(self, values):
        return self.send('/trips/add', values)

    def edit_trip(self, trip_id, values):
        return self.send('/trips/edit/%d' % trip_id, values)

    def delete_trip(self, trip_id):
        return self.send('/trips/delete/%d' % trip_id, {})

    def add_activity(self, trip_id, values):
        return self.send('/trips/%d/activities/add' % trip_id, values)

    def edit_activity(self, activity_id, values):
        return self.send('/activities/edit/%d' % activity_id, values)

    def delete_activity(self, activity_id):
        return self.send('/activities/delete/%d' % activity_id, {})

    def my_places(self):
        return self.send('/my-places')

    def add_my_place(self, name, kind, lat, lng):
        return self.send('/my-places/add', {'name': name, 'kind': kind, 'lat': lat, 'lng': lng})

    def delete_my_place(self, place_id):
        return self.send('/my-places/delete/%d' % place_id, {})

    def autoplan(self, trip_id, interests, pace, engine):
        # Gemini can take a while, so this request waits longer
        return self.send('/trips/%d/autoplan' % trip_id,
                         {'interests': ','.join(interests), 'pace': pace, 'engine': engine}, timeout=90)
