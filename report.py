# Saudi Weekend Planner: the report helper (a threading demonstration)
# Start server.py first, then run: python report.py
# It logs in, asks Flask's JSON route for the saved trips, and one thread writes the text report.
import getpass
import threading
from datetime import datetime

from api_client import ApiClient

REPORT_FILE = 'weekend_report.txt'


class ReportWriter(threading.Thread):
    """A thread that writes every trip, day by day, to a UTF-8 text report."""

    def __init__(self, username, trips, file_name):
        super().__init__(name='report writer')
        self.username = username
        self.trips = trips          # a list of full trips: trip, activities, analysis
        self.file_name = file_name
        # the result, read after join()
        self.saved = False
        self.error = ''

    def run(self):
        try:
            # with closes the file, even after an error
            with open(self.file_name, 'w', encoding='utf-8') as f:
                f.write('SAUDI WEEKEND PLANNER  ·  REPORT\n')
                f.write('user: %s   made on: %s\n' % (self.username, datetime.now().strftime('%Y-%m-%d %H:%M')))
                f.write('=' * 72 + '\n')
                if not self.trips:
                    f.write('\nNo trips are saved yet.\n')
                grand = 0
                for full in self.trips:
                    trip, analysis = full['trip'], full['analysis']
                    budget = analysis['budget']
                    grand += budget['total']
                    f.write('\n%s   [%s]\n' % (trip['name'].upper(), analysis['status']))
                    f.write('  %s to %s  ·  %d people  ·  from %s to %s  ·  %s\n'
                            % (trip['start_date'], trip['end_date'], trip['people'], trip['home_city'],
                               trip['destinations'], trip['transport']))
                    for number, day in enumerate(analysis['days']):
                        f.write('  Day %d  %s\n' % (number + 1, day['date']))
                        if not day['items']:
                            f.write('     (nothing planned)\n')
                        for item in day['items']:
                            a = item['activity']
                            f.write('     %s-%-8s %-30s %-8s %7.0f SAR\n'
                                    % (a['start_time'], item['end'], a['name'][:30], a['city'],
                                       a['cost_per_person'] * trip['people']))
                            for issue in item['issues']:
                                f.write('        ! %s\n' % issue['text'])
                        if day['hotel']:
                            f.write('     night      Hotel in %-21s %-8s %7.0f SAR\n'
                                    % (day['hotel']['city'], '', day['hotel']['cost']))
                    f.write('  Cost: activities %.0f + fuel %.0f + flights %.0f + hotels %.0f = %.0f of %.0f SAR\n'
                            % (budget['activities'], budget['fuel'], budget['flights'], budget['hotels'],
                               budget['total'], budget['limit']))
                    for check in analysis['checks']:
                        f.write('  [%s] %s: %s\n' % ('x' if check['ok'] else ' ', check['name'], check['detail']))
                f.write('\n' + '-' * 72 + '\n')
                f.write('%d trip(s), %.0f SAR planned in total\n' % (len(self.trips), grand))
            self.saved = True
        except PermissionError:
            self.error = 'no permission to write %s (is it open in another program?)' % self.file_name
        except OSError as problem:
            self.error = str(problem)


def main():
    api = ApiClient()
    username = input('username: ').strip()
    password = getpass.getpass('password: ')
    ok, data, status = api.login(username, password)
    if not ok:
        print('login failed:', data)
        return
    # the JSON route of the saved records
    ok, data, status = api.trips()
    if not ok:
        print('could not read the trips:', data)
        return
    trips = []
    for trip in data['trips']:
        ok, full, status = api.trip(trip['id'])
        if ok:
            trips.append(full)
    print('received', len(trips), 'trip(s) from the server')

    # one thread writes the file; join() waits for it to finish
    writer = ReportWriter(username, trips, REPORT_FILE)
    writer.start()
    writer.join()
    if writer.saved:
        print('report saved to', REPORT_FILE)
    else:
        print('report NOT saved:', writer.error)
    api.logout()


if __name__ == '__main__':
    main()
