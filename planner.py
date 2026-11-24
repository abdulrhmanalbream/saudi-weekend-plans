# Saudi Weekend Planner: the planning engine
# It answers three questions about a trip:
#   1. How do I move from one activity to the next (distance, time, car or flight)?
#   2. What does the whole trip cost (activities, fuel, flights, hotels)?
#   3. Is the plan complete and possible (no conflicts, inside the budget, back home)?
import math
from datetime import date, timedelta

from places_data import CITIES

# the numbers behind every estimate, in one place so they are easy to explain and change
ROAD_FACTOR = 1.3          # without the road service: a road is about 30% longer than the straight line
CITY_SPEED = 40            # without the road service: km/h inside a city (traffic, lights)
HIGHWAY_SPEED = 100        # without the road service: km/h between cities
CITY_TRAFFIC = 1.25        # OSRM gives free-flow times: +25% for traffic inside a city
HIGHWAY_TRAFFIC = 1.05     # and +5% on the highway
CITY_LIMIT_KM = 40         # a leg shorter than this is a city drive
PARKING_MIN = 10           # minutes to park at each stop
FLIGHT_FROM_KM = 500       # a longer leg is flown when the trip allows flights
FLIGHT_AIR_MIN = 90        # minutes in the air
AIRPORT_MIN = 150          # check-in, boarding, taxi to and from the airports
FLIGHT_BASE_SAR = 250      # flight price per person = base + per km
FLIGHT_PER_KM = 0.35
FUEL_PRICES = {'91': 2.18, '95': 2.33}   # SAR per litre
CAR_KM_PER_LITRE = 12      # used when a trip gives no value
PEOPLE_PER_CAR = 4
PEOPLE_PER_ROOM = 2
DAY_END = 24 * 60          # midnight, in minutes


def haversine_km(lat1, lng1, lat2, lng2):
    """The straight-line distance between two points on the Earth, in km."""
    radius = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def to_minutes(text):
    # '14:30' -> 870
    hours, minutes = text.split(':')
    return int(hours) * 60 + int(minutes)


def to_clock(minutes):
    # 870 -> '14:30'; past midnight shows +1, the day before shows -1
    day, rest = divmod(int(minutes), DAY_END)
    clock = '%02d:%02d' % divmod(rest, 60)
    if day > 0:
        return clock + ' +' + str(day)
    if day < 0:
        return clock + ' ' + str(day)
    return clock


def trip_days(start_date, end_date):
    """The list of dates from the start to the end, both included."""
    first = date.fromisoformat(start_date)
    last = date.fromisoformat(end_date)
    return [(first + timedelta(days=n)).isoformat() for n in range((last - first).days + 1)]


class TripPlanner:
    """Works out travel, cost and the checks of one trip."""

    def __init__(self, trip, activities, router=None, homes=None):
        # trip: a dict of the trips table; activities: a list of dicts of the activities table
        # router: a RoadRouter for real roads, or None for the estimate only
        # homes: the user's saved places, {city: {'name', 'lat', 'lng'}}; without one, the city centre is used
        self.trip = trip
        self.homes = homes or {}
        self.router = router
        self.recording = None      # a list while the legs of the trip are being collected
        self.kmpl = float(trip.get('car_kmpl') or CAR_KM_PER_LITRE)
        self.fuel_price = FUEL_PRICES.get(str(trip.get('fuel') or '91'), FUEL_PRICES['91'])
        self.activities = activities
        self.people = int(trip['people'])
        self.cars = math.ceil(self.people / PEOPLE_PER_CAR)
        self.rooms = math.ceil(self.people / PEOPLE_PER_ROOM)
        self.allow_flights = trip['transport'] == 'flight'
        self.home = self.point(trip['home_city'], home_only=True)
        if not self.home['saved']:
            self.home['name'] = 'Home (' + trip['home_city'] + ')'
        # the cities where the group has a house or family, so a night there costs nothing
        self.stays = {c.strip() for c in (trip.get('stays') or '').split(',') if c.strip()}

    def point(self, city, home_only=False):
        """Where the group sleeps in a city: the saved place there, or the city centre.

        The start and the end of a trip use only a place of the kind Home.
        """
        if city in self.homes and (not home_only or self.homes[city].get('kind', 'Home') == 'Home'):
            home = self.homes[city]
            return {'lat': home['lat'], 'lng': home['lng'], 'name': home['name'], 'saved': True}
        centre = CITIES[city]
        return {'lat': centre['lat'], 'lng': centre['lng'], 'name': city + ' centre', 'saved': False}

    def leg(self, lat1, lng1, lat2, lng2):
        """One move between two points: km, minutes, mode, cost for the group and the shape for the map."""
        straight = [(lat1, lng1), (lat2, lng2)]
        km = haversine_km(lat1, lng1, lat2, lng2) * ROAD_FACTOR
        if km < 0.3:
            return {'km': 0.0, 'minutes': 0, 'mode': 'walk', 'cost': 0.0, 'source': 'road', 'geometry': straight}
        if km >= FLIGHT_FROM_KM and self.allow_flights:
            price = (FLIGHT_BASE_SAR + FLIGHT_PER_KM * km) * self.people
            return {'km': round(km, 1), 'minutes': FLIGHT_AIR_MIN + AIRPORT_MIN, 'mode': 'flight',
                    'cost': round(price, 2), 'source': 'estimate', 'geometry': straight}
        road = None
        if self.recording is not None:
            # first pass: only remember which legs the trip needs
            self.recording.append((lat1, lng1, lat2, lng2))
        elif self.router is not None:
            road = self.router.road(lat1, lng1, lat2, lng2)
        if road:
            # the real road from OSRM, plus traffic and parking
            km = road['km']
            traffic = CITY_TRAFFIC if km < CITY_LIMIT_KM else HIGHWAY_TRAFFIC
            minutes = round(road['minutes'] * traffic) + PARKING_MIN
            source, shape = 'road', road['geometry']
        else:
            # no road service: the estimate from the straight line
            speed = CITY_SPEED if km < CITY_LIMIT_KM else HIGHWAY_SPEED
            minutes = round(km / speed * 60) + PARKING_MIN
            source, shape = 'estimate', straight
        # fuel for every car: km / (km per litre) x price per litre
        fuel = km / self.kmpl * self.fuel_price * self.cars
        return {'km': round(km, 1), 'minutes': minutes, 'mode': 'car', 'cost': round(fuel, 2),
                'source': source, 'geometry': shape}

    def analyse(self):
        """The full picture of the trip: the days, the budget and the checks."""
        if self.router is not None and self.router.online():
            # pass 1 collects the legs, the router gets them all at once with threads, pass 2 uses them
            self.recording = []
            self.work_out()
            pairs, self.recording = self.recording, None
            self.router.prefetch(pairs)
        return self.work_out()

    def work_out(self):
        dates = trip_days(self.trip['start_date'], self.trip['end_date'])
        # the activities of each date, sorted by start time
        by_date = {day: [] for day in dates}
        outside = []
        for activity in self.activities:
            if activity['day'] in by_date:
                by_date[activity['day']].append(activity)
            else:
                outside.append(activity)
        for day in dates:
            by_date[day].sort(key=lambda a: to_minutes(a['start_time']))

        days = []
        conflicts = 0
        warnings = 0
        costs = {'activities': 0.0, 'fuel': 0.0, 'flights': 0.0, 'hotels': 0.0}
        by_category, by_city, by_day = {}, {}, {}
        actual_total = 0.0
        actual_count = 0
        total_km = 0.0
        # day 1 starts at home
        here = {'lat': self.home['lat'], 'lng': self.home['lng'], 'name': self.home['name'],
                'city': self.trip['home_city']}
        return_leg = None

        for number, day in enumerate(dates):
            items = []
            day_cost = 0.0
            clock = None
            for activity in by_date[day]:
                move = self.leg(here['lat'], here['lng'], activity['lat'], activity['lng'])
                start = to_minutes(activity['start_time'])
                # the earliest time we can be there
                if clock is None:
                    arrive = start
                    leave_at = start - move['minutes']
                else:
                    arrive = clock + move['minutes']
                    leave_at = clock
                end = max(arrive, start) + int(activity['duration_min'])
                issues = []
                if clock is None and leave_at < 0:
                    # the first move of the day would have to start the day before
                    conflicts += 1
                    issues.append({'level': 'conflict',
                                   'text': '%d h %02d min of %s from %s: you would leave the day before'
                                           % (move['minutes'] // 60, move['minutes'] % 60, move['mode'], here['name'])})
                elif clock is None and leave_at < 6 * 60 and move['minutes'] > 0:
                    warnings += 1
                    issues.append({'level': 'warning',
                                   'text': 'Leave %s at %s (%d min of %s)'
                                           % (here['name'], to_clock(leave_at), move['minutes'], move['mode'])})
                if clock is not None and arrive > start:
                    conflicts += 1
                    issues.append({'level': 'conflict',
                                   'text': 'Arrives %s, %d min after the start: %d min of %s from %s'
                                           % (to_clock(arrive), arrive - start, move['minutes'], move['mode'], here['name'])})
                opens, closes = to_minutes(activity['opens']), to_minutes(activity['closes'])
                if max(arrive, start) < opens or end > closes + (1 if closes == DAY_END - 1 else 0):
                    warnings += 1
                    issues.append({'level': 'warning',
                                   'text': 'Open %s to %s' % (activity['opens'], activity['closes'])})
                if end > DAY_END:
                    warnings += 1
                    issues.append({'level': 'warning', 'text': 'Ends after midnight'})

                # the cost of the activity for the whole group, and of the move to it
                cost = float(activity['cost_per_person']) * self.people
                costs['activities'] += cost
                costs['fuel' if move['mode'] == 'car' else 'flights'] += move['cost']
                total_km += move['km']
                day_cost += cost + move['cost']
                by_category[activity['category']] = by_category.get(activity['category'], 0) + cost
                by_city[activity['city']] = by_city.get(activity['city'], 0) + cost
                if activity.get('actual_cost') not in (None, ''):
                    actual_total += float(activity['actual_cost'])
                    actual_count += 1

                items.append({'activity': activity, 'travel': move, 'from': here['name'],
                              'leave_at': to_clock(leave_at), 'arrive': to_clock(arrive),
                              'end': to_clock(end), 'issues': issues})
                clock = end
                here = {'lat': activity['lat'], 'lng': activity['lng'], 'name': activity['name'],
                        'city': activity['city']}

            # the night: at home, at a free place (own house, family or friends), or in a hotel
            hotel = None
            if number < len(dates) - 1:
                city = here['city']
                spot = self.point(city)
                if city == self.trip['home_city']:
                    # sleep at home; the next day starts from home
                    here = {'lat': self.home['lat'], 'lng': self.home['lng'], 'name': self.home['name'], 'city': city}
                elif city in self.stays or spot['saved']:
                    # a saved place or a ticked city: no hotel to pay
                    name = spot['name'] if spot['saved'] else 'Your place (' + city + ')'
                    hotel = {'city': city, 'rooms': 0, 'cost': 0, 'own': True, 'place': name,
                             'lat': spot['lat'], 'lng': spot['lng']}
                    here = {'lat': spot['lat'], 'lng': spot['lng'], 'name': name, 'city': city}
                else:
                    centre = CITIES[city]
                    price = centre['hotel'] * self.rooms
                    costs['hotels'] += price
                    day_cost += price
                    hotel = {'city': city, 'rooms': self.rooms, 'cost': price, 'own': False,
                             'lat': centre['lat'], 'lng': centre['lng']}
                    here = {'lat': centre['lat'], 'lng': centre['lng'], 'name': 'Hotel (' + city + ')', 'city': city}

            # the last day ends with the way back home
            if number == len(dates) - 1:
                move = self.leg(here['lat'], here['lng'], self.home['lat'], self.home['lng'])
                costs['fuel' if move['mode'] == 'car' else 'flights'] += move['cost']
                total_km += move['km']
                day_cost += move['cost']
                start_back = clock if clock is not None else 12 * 60
                return_leg = dict(move, leave=to_clock(start_back), arrive=to_clock(start_back + move['minutes']),
                                  arrive_minutes=start_back + move['minutes'], **{'from': here['name']})

            by_day[day] = round(day_cost, 2)
            days.append({'date': day, 'items': items, 'hotel': hotel})

        total = round(sum(costs.values()), 2)
        budget = float(self.trip['budget'])
        empty_days = [d['date'] for d in days if not d['items']]

        # the checklist: the plan is complete when every check passes
        checks = [
            {'name': 'Every day has a plan', 'ok': not empty_days,
             'detail': 'All %d days planned' % len(days) if not empty_days else 'Empty: ' + ', '.join(empty_days)},
            {'name': 'No time conflicts', 'ok': conflicts == 0,
             'detail': 'Every activity can be reached in time' if conflicts == 0
             else '%d activity(ies) cannot be reached in time' % conflicts},
            {'name': 'Inside the budget', 'ok': total <= budget,
             'detail': '%.0f of %.0f SAR (%.0f left)' % (total, budget, budget - total) if total <= budget
             else '%.0f SAR over the %.0f SAR budget' % (total - budget, budget)},
            {'name': 'Back home on the last day', 'ok': return_leg is not None and return_leg['arrive_minutes'] <= DAY_END,
             'detail': 'Home at %s by %s' % (return_leg['arrive'], return_leg['mode']) if return_leg else 'No return'},
            {'name': 'All activities inside the trip dates', 'ok': not outside,
             'detail': 'OK' if not outside else '%d activity(ies) are outside the dates' % len(outside)},
        ]
        complete = all(check['ok'] for check in checks)

        return {
            'home': self.home,
            'days': days,
            'return_leg': return_leg,
            'budget': {'activities': round(costs['activities'], 2), 'fuel': round(costs['fuel'], 2),
                       'flights': round(costs['flights'], 2), 'hotels': round(costs['hotels'], 2),
                       'total': total, 'limit': budget, 'remaining': round(budget - total, 2),
                       'per_person': round(total / self.people, 2),
                       'actual': round(actual_total, 2), 'actual_count': actual_count},
            'by_category': by_category, 'by_city': by_city, 'by_day': by_day,
            'total_km': round(total_km, 1),
            'conflicts': conflicts, 'warnings': warnings,
            'checks': checks, 'complete': complete,
            'status': 'Complete' if complete else 'In progress',
        }


def local_plan(trip, places, interests, pace='normal', homes=None):
    """A plan made without AI: fills each day with nearby places that match the interests.

    It is the fallback when Gemini is not available, and it uses the same travel rules.
    """
    planner = TripPlanner(trip, [], homes=homes)
    dates = trip_days(trip['start_date'], trip['end_date'])
    cities = [c.strip() for c in trip['destinations'].split(',') if c.strip()] or [trip['home_city']]
    per_day = {'relaxed': 3, 'normal': 4, 'packed': 6}.get(pace, 4)
    used = set()
    plan = []
    here = (planner.home['lat'], planner.home['lng'])
    # spread the destination cities over the days, in order
    day_city = [cities[min(n * len(cities) // len(dates), len(cities) - 1)] for n in range(len(dates))]
    for number, day in enumerate(dates):
        city = day_city[number]
        options = [p for p in places if p['city'] == city and p['id'] not in used]
        # share the places of the city fairly between its remaining days
        days_left = day_city[number:].count(city)
        limit = min(per_day, max(1, math.ceil(len(options) / days_left)))
        # places that match the interests come first, then the cheaper ones
        options.sort(key=lambda p: (p['category'] not in interests, p['cost']))
        clock = 9 * 60
        first = True
        count = 0
        while options and count < limit:
            # the nearest of the best options
            best = sorted(options[:4], key=lambda p: haversine_km(here[0], here[1], p['lat'], p['lng']))[0]
            options.remove(best)
            move = planner.leg(here[0], here[1], best['lat'], best['lng'])
            if first:
                # leave at 6:00 at the earliest, so a long drive pushes the first start later
                arrive = max(9 * 60, 6 * 60 + move['minutes'])
            else:
                arrive = clock + move['minutes']
            start = max(arrive, to_minutes(best['opens']))
            end = start + best['duration_min']
            if end > to_minutes(best['closes']) or end > 23 * 60:
                continue
            if number == len(dates) - 1:
                # the last day must leave time to get home before midnight
                back = planner.leg(best['lat'], best['lng'], planner.home['lat'], planner.home['lng'])
                if end + back['minutes'] > 23 * 60 + 30:
                    continue
            # round the start up to the next quarter hour
            start = (start + 14) // 15 * 15
            plan.append({'place_id': best['id'], 'day': day, 'start_time': to_clock(start),
                         'note': 'Planned locally: ' + best['category'].lower() + ' in ' + city})
            used.add(best['id'])
            here = (best['lat'], best['lng'])
            clock = start + best['duration_min']
            first = False
            count += 1
    return plan


def fit_times(trip, activities, router=None, homes=None):
    """Moves start times later where the real travel time does not fit (used after every automatic plan).

    The activities are changed in place: an activity that cannot be reached in time starts at the next
    quarter hour after the arrival.
    """
    analysis = TripPlanner(trip, activities, router, homes).analyse()
    for day in analysis['days']:
        clock = None
        for item in day['items']:
            activity = item['activity']
            start = to_minutes(activity['start_time'])
            if clock is not None:
                arrive = clock + item['travel']['minutes']
                if arrive > start:
                    start = (arrive + 14) // 15 * 15
                    if start < DAY_END:
                        activity['start_time'] = to_clock(start)
            clock = start + int(activity['duration_min'])
    return activities
