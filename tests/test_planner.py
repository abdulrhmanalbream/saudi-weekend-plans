# Tests of the planning engine: distances, travel, budget and the checks
# Run all tests with: python -m unittest discover tests
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from planner import TripPlanner, fit_times, haversine_km, local_plan, to_clock, to_minutes, trip_days  # noqa: E402
from places_data import CITIES, PLACES  # noqa: E402

COLUMNS = ['name', 'city', 'category', 'lat', 'lng', 'cost', 'duration_min', 'opens', 'closes', 'description']
CATALOGUE = [dict(zip(COLUMNS, row), id=n + 1) for n, row in enumerate(PLACES)]


def trip(**changes):
    base = {'id': 1, 'name': 'Test', 'home_city': 'Riyadh', 'destinations': 'Riyadh', 'start_date': '2026-12-03',
            'end_date': '2026-12-04', 'people': 2, 'budget': 5000, 'transport': 'car', 'notes': ''}
    base.update(changes)
    return base


def activity(place_id, day, start, **changes):
    place = CATALOGUE[place_id - 1]
    row = {'id': place_id, 'place_id': place_id, 'day': day, 'start_time': start, 'name': place['name'],
           'city': place['city'], 'category': place['category'], 'lat': place['lat'], 'lng': place['lng'],
           'duration_min': place['duration_min'], 'cost_per_person': place['cost'], 'actual_cost': None,
           'opens': place['opens'], 'closes': place['closes'], 'notes': ''}
    row.update(changes)
    return row


class TestHelpers(unittest.TestCase):
    def test_haversine_riyadh_jeddah(self):
        # the straight line Riyadh-Jeddah is about 850 km
        km = haversine_km(CITIES['Riyadh']['lat'], CITIES['Riyadh']['lng'], CITIES['Jeddah']['lat'], CITIES['Jeddah']['lng'])
        self.assertAlmostEqual(km, 850, delta=15)

    def test_haversine_same_point(self):
        self.assertEqual(haversine_km(24.7, 46.6, 24.7, 46.6), 0)

    def test_clock(self):
        self.assertEqual(to_minutes('14:30'), 870)
        self.assertEqual(to_clock(870), '14:30')
        self.assertEqual(to_clock(24 * 60 + 90), '01:30 +1')
        self.assertEqual(to_clock(-60), '23:00 -1')

    def test_trip_days(self):
        self.assertEqual(trip_days('2026-12-03', '2026-12-05'), ['2026-12-03', '2026-12-04', '2026-12-05'])


class TestLegs(unittest.TestCase):
    def test_city_leg_uses_city_speed(self):
        planner = TripPlanner(trip(), [])
        move = planner.leg(24.7336, 46.5753, 24.6476, 46.7106)   # Diriyah -> National Museum
        self.assertEqual(move['mode'], 'car')
        self.assertLess(move['km'], 40)
        self.assertGreater(move['minutes'], 20)

    def test_far_leg_is_flown_when_allowed(self):
        planner = TripPlanner(trip(transport='flight', people=3), [])
        r, j = CITIES['Riyadh'], CITIES['Jeddah']
        move = planner.leg(r['lat'], r['lng'], j['lat'], j['lng'])
        self.assertEqual(move['mode'], 'flight')
        self.assertEqual(move['minutes'], 240)
        self.assertGreater(move['cost'], 3 * 250)

    def test_far_leg_is_driven_otherwise(self):
        planner = TripPlanner(trip(transport='car'), [])
        r, j = CITIES['Riyadh'], CITIES['Jeddah']
        move = planner.leg(r['lat'], r['lng'], j['lat'], j['lng'])
        self.assertEqual(move['mode'], 'car')
        self.assertGreater(move['minutes'], 10 * 60)

    def test_cars_and_rooms(self):
        planner = TripPlanner(trip(people=5), [])
        self.assertEqual(planner.cars, 2)
        self.assertEqual(planner.rooms, 3)


class TestAnalysis(unittest.TestCase):
    def test_good_plan_is_complete(self):
        acts = [activity(5, '2026-12-03', '10:00'), activity(6, '2026-12-03', '12:30'),
                activity(1, '2026-12-04', '16:00')]
        result = TripPlanner(trip(), acts).analyse()
        self.assertEqual(result['conflicts'], 0)
        self.assertTrue(result['complete'], result['checks'])

    def test_riyadh_then_jeddah_same_day_is_a_conflict(self):
        acts = [activity(1, '2026-12-03', '16:00'), activity(9, '2026-12-03', '19:30'),
                activity(10, '2026-12-04', '17:00')]
        result = TripPlanner(trip(destinations='Riyadh, Jeddah'), acts).analyse()
        self.assertEqual(result['conflicts'], 1)
        self.assertFalse(result['complete'])

    def test_empty_day_fails(self):
        result = TripPlanner(trip(), [activity(5, '2026-12-03', '10:00')]).analyse()
        failed = [c['name'] for c in result['checks'] if not c['ok']]
        self.assertIn('Every day has a plan', failed)

    def test_over_budget_fails(self):
        acts = [activity(27, '2026-12-03', '09:00'), activity(28, '2026-12-04', '16:00')]   # AlUla
        result = TripPlanner(trip(budget=100, destinations='AlUla', transport='flight'), acts).analyse()
        failed = [c['name'] for c in result['checks'] if not c['ok']]
        self.assertIn('Inside the budget', failed)

    def test_budget_adds_up(self):
        acts = [activity(5, '2026-12-03', '10:00'), activity(1, '2026-12-04', '16:00')]
        b = TripPlanner(trip(), acts).analyse()['budget']
        self.assertAlmostEqual(b['total'], b['activities'] + b['fuel'] + b['flights'] + b['hotels'], places=1)
        self.assertEqual(b['activities'], (10 + 100) * 2)

    def test_hotel_when_night_away(self):
        acts = [activity(9, '2026-12-03', '16:00'), activity(10, '2026-12-04', '17:00')]
        result = TripPlanner(trip(destinations='Jeddah', transport='flight', people=3), acts).analyse()
        self.assertEqual(result['days'][0]['hotel']['rooms'], 2)
        self.assertEqual(result['budget']['hotels'], 2 * CITIES['Jeddah']['hotel'])

    def test_opening_hours_warning(self):
        result = TripPlanner(trip(end_date='2026-12-03'), [activity(1, '2026-12-03', '10:00')]).analyse()
        self.assertGreaterEqual(result['warnings'], 1)

    def test_actual_cost_is_summed(self):
        acts = [activity(5, '2026-12-03', '10:00', actual_cost=35), activity(1, '2026-12-04', '16:00', actual_cost=210)]
        self.assertEqual(TripPlanner(trip(), acts).analyse()['budget']['actual'], 245)


class TestStaysAndCars(unittest.TestCase):
    def test_free_stay_has_no_hotel(self):
        acts = [activity(9, '2026-12-03', '16:00'), activity(10, '2026-12-04', '17:00')]
        result = TripPlanner(trip(destinations='Jeddah', transport='flight', stays='Jeddah'), acts).analyse()
        self.assertTrue(result['days'][0]['hotel']['own'])
        self.assertEqual(result['budget']['hotels'], 0)

    def test_next_day_starts_from_your_place(self):
        acts = [activity(9, '2026-12-03', '16:00'), activity(10, '2026-12-04', '17:00')]
        result = TripPlanner(trip(destinations='Jeddah', transport='flight', stays='Jeddah'), acts).analyse()
        self.assertEqual(result['days'][1]['items'][0]['from'], 'Your place (Jeddah)')

    def test_friends_house_is_a_free_night_at_its_pin(self):
        homes = {'Jeddah': {'name': 'Ahmed (friends)', 'lat': 21.60, 'lng': 39.14}}
        acts = [activity(9, '2026-12-03', '16:00'), activity(10, '2026-12-04', '17:00')]
        result = TripPlanner(trip(destinations='Jeddah', transport='flight'), acts, homes=homes).analyse()
        night = result['days'][0]['hotel']
        self.assertTrue(night['own'])
        self.assertEqual(night['place'], 'Ahmed (friends)')
        self.assertEqual(result['days'][1]['items'][0]['from'], 'Ahmed (friends)')

    def test_friends_house_is_not_the_start(self):
        homes = {'Riyadh': {'name': 'Omar (friends)', 'kind': 'Friends', 'lat': 24.80, 'lng': 46.70}}
        result = TripPlanner(trip(), [activity(5, '2026-12-03', '10:00')], homes=homes).analyse()
        self.assertEqual(result['home']['name'], 'Home (Riyadh)')

    def test_trip_can_end_in_another_city(self):
        # start at home in Jeddah, end at a saved home in Madinah
        homes = {'Madinah': {'name': 'Madinah house', 'kind': 'Home', 'lat': 24.48, 'lng': 39.58}}
        t = trip(home_city='Jeddah', end_city='Madinah', destinations='Jeddah, Madinah', transport='car',
                 start_date='2026-12-03', end_date='2026-12-04')
        acts = [activity(9, '2026-12-03', '16:00'), activity(19, '2026-12-04', '12:00')]
        result = TripPlanner(t, acts, homes=homes).analyse()
        self.assertEqual(result['end']['name'], 'Madinah house')
        self.assertLess(result['return_leg']['km'], 30)
        local = local_plan(t, CATALOGUE, ['Heritage'], 'normal', homes)
        self.assertEqual(CATALOGUE[local[-1]['place_id'] - 1]['city'], 'Madinah')

    def test_economical_car_uses_less_fuel(self):
        r, d = CITIES['Riyadh'], CITIES['Jeddah']
        thirsty = TripPlanner(trip(car_kmpl=8), []).leg(r['lat'], r['lng'], d['lat'], d['lng'])
        saver = TripPlanner(trip(car_kmpl=20), []).leg(r['lat'], r['lng'], d['lat'], d['lng'])
        self.assertAlmostEqual(thirsty['cost'] / saver['cost'], 20 / 8, places=2)

    def test_road_from_router_is_used(self):
        class FakeRouter:
            def online(self):
                return True

            def prefetch(self, pairs):
                self.pairs = pairs

            def road(self, *points):
                return {'km': 30.0, 'minutes': 20.0, 'geometry': [(1, 2), (3, 4), (5, 6)]}
        router = FakeRouter()
        move = TripPlanner(trip(), [], router).leg(24.7336, 46.5753, 24.6476, 46.7106)
        self.assertEqual(move['source'], 'road')
        self.assertEqual(move['km'], 30.0)
        self.assertEqual(move['minutes'], round(20 * 1.25) + 10)
        self.assertEqual(len(move['geometry']), 3)


class TestFitTimes(unittest.TestCase):
    def test_late_start_is_moved(self):
        # the museum starts 5 minutes after the sky bridge ends: not enough time to drive
        acts = [activity(4, '2026-12-03', '10:00'), activity(5, '2026-12-03', '11:05'),
                activity(1, '2026-12-04', '16:00')]
        self.assertGreater(TripPlanner(trip(), acts).analyse()['conflicts'], 0)
        fit_times(trip(), acts)
        self.assertEqual(TripPlanner(trip(), acts).analyse()['conflicts'], 0)
        self.assertEqual(to_minutes(acts[1]['start_time']) % 15, 0)


class TestLocalPlanner(unittest.TestCase):
    def test_local_plan_passes_its_own_checks(self):
        t = trip(destinations='Jeddah', transport='flight', start_date='2026-12-10', end_date='2026-12-12', budget=8000)
        plan = local_plan(t, CATALOGUE, ['Heritage', 'Beach'], 'normal')
        acts = [activity(step['place_id'], step['day'], step['start_time']) for step in plan]
        result = TripPlanner(t, acts).analyse()
        self.assertTrue(result['complete'], result['checks'])

    def test_local_plan_uses_each_place_once(self):
        t = trip(start_date='2026-12-03', end_date='2026-12-05')
        plan = local_plan(t, CATALOGUE, ['Heritage'], 'packed')
        ids = [step['place_id'] for step in plan]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == '__main__':
    unittest.main()
