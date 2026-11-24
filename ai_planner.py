# Saudi Weekend Planner: the Gemini planner
# The server sends the trip and the catalogue of places to Gemini and asks for a plan in JSON.
# The plan is then checked by the same TripPlanner as a plan made by hand.
import json
import os
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from planner import TripPlanner, trip_days, to_minutes
from places_data import CITIES

API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'


class AIError(Exception):
    """Gemini could not give a usable plan."""


def read_env(path='.env'):
    """Reads KEY=value lines from .env into os.environ. The file is never sent to GitHub."""
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


class GeminiPlanner:
    """Asks Gemini for a weekend plan made only of places from the catalogue."""

    def __init__(self):
        read_env()
        self.key = os.environ.get('GEMINI_API_KEY', '')
        self.model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

    def available(self):
        return self.key != ''

    def build_prompt(self, trip, places, interests, pace):
        planner = TripPlanner(trip, [])
        cities = [trip['home_city']] + [c.strip() for c in trip['destinations'].split(',') if c.strip()]
        # the real travel times between the cities of the trip, from our own rules
        legs = []
        for a in dict.fromkeys(cities):
            for b in dict.fromkeys(cities):
                if a < b:
                    move = planner.leg(CITIES[a]['lat'], CITIES[a]['lng'], CITIES[b]['lat'], CITIES[b]['lng'])
                    legs.append('%s - %s: %.0f km, %d min by %s' % (a, b, move['km'], move['minutes'], move['mode']))
        catalogue = [{'id': p['id'], 'name': p['name'], 'city': p['city'], 'category': p['category'],
                      'cost_per_person': p['cost'], 'minutes': p['duration_min'],
                      'opens': p['opens'], 'closes': p['closes']} for p in places]
        return (
            'You plan weekend trips in Saudi Arabia. Make a realistic day-by-day plan.\n'
            'Trip: %s\n' % json.dumps({k: trip.get(k) for k in ('home_city', 'destinations', 'stays', 'start_date',
                                                                  'end_date', 'people', 'budget', 'transport')}) +
            'Dates: %s\n' % ', '.join(trip_days(trip['start_date'], trip['end_date'])) +
            'Interests: %s. Pace: %s.\n' % (', '.join(interests) or 'anything', pace) +
            'Travel between cities:\n' + ('\n'.join(legs) or 'one city only') + '\n'
            'Rules:\n'
            '- Use ONLY places from the catalogue, by their id.\n'
            '- The group starts at home in %s on the first day and goes back home at the end of the last day.\n'
            % trip['home_city'] +
            '- Visit each place inside its opening hours. Leave 20-40 minutes between places in a city.\n'
            '- When the plan changes city, leave the travel time above between the two activities.\n'
            '- The group has a free place to stay (house or family) in: %s. A night there costs nothing.\n'
            % (trip.get('stays') or 'none') +
            '- The total cost (cost_per_person x people, plus hotels about 400 SAR per room per night) '
            'must stay under the budget.\n'
            '- start_time is HH:MM, 24-hour.\n'
            'Answer with JSON only: {"summary": "two sentences", "activities": '
            '[{"place_id": 1, "day": "YYYY-MM-DD", "start_time": "HH:MM", "reason": "short"}]}\n'
            'Catalogue: ' + json.dumps(catalogue)
        )

    def ask(self, prompt):
        """One POST to Gemini; returns the text of its answer."""
        body = json.dumps({
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0.4},
        }).encode('utf-8')
        # the key goes in a header, not in the address, so it is not written in logs
        request = Request(API_URL.format(model=self.model), data=body,
                          headers={'Content-Type': 'application/json', 'x-goog-api-key': self.key})
        try:
            with urlopen(request, timeout=60) as reply:
                data = json.loads(reply.read().decode('utf-8'))
        except HTTPError as error:
            raise AIError('Gemini answered with status %d' % error.code)
        except URLError:
            raise AIError('Cannot reach Gemini (no internet?)')
        except socket.timeout:
            raise AIError('Gemini took too long to answer')
        try:
            return data['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError):
            raise AIError('Gemini gave an empty answer')

    def plan(self, trip, places, interests, pace):
        """Returns (summary, list of activities) after checking every item Gemini sent."""
        text = self.ask(self.build_prompt(trip, places, interests, pace))
        # some answers wrap the JSON in ``` marks
        text = re.sub(r'^```(json)?|```$', '', text.strip()).strip()
        try:
            answer = json.loads(text)
        except ValueError:
            raise AIError('Gemini did not answer with JSON')

        known = {p['id'] for p in places}
        dates = set(trip_days(trip['start_date'], trip['end_date']))
        plan = []
        for item in answer.get('activities', []):
            # keep only items with a real place, a trip date and a real time
            try:
                place_id = int(item['place_id'])
                to_minutes(item['start_time'])
            except (KeyError, ValueError, TypeError, AttributeError):
                continue
            if place_id in known and item.get('day') in dates:
                plan.append({'place_id': place_id, 'day': item['day'], 'start_time': item['start_time'][:5],
                             'note': 'AI: ' + str(item.get('reason', ''))[:150]})
        if not plan:
            raise AIError('Gemini gave no usable activity')
        return str(answer.get('summary', ''))[:400], plan
