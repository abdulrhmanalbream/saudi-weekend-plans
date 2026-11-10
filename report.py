# Saudi Weekend Plans: the report helper (a threading demonstration)
# Start server.py first, then run: python report.py
import json
import socket
import threading
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

# the JSON route with the saved plans, and the report file
URL = 'http://127.0.0.1:5050/plans'
REPORT_FILE = 'weekend_report.txt'


class ReportWriter(threading.Thread):
    """A thread that writes the plans to a UTF-8 text report."""

    def __init__(self, plans, file_name):
        super().__init__(name='report writer')
        self.plans = plans
        self.file_name = file_name
        # the result, read after join()
        self.saved = False
        self.error = ''

    def run(self):
        # the plans of each city: {'Riyadh': [plan, plan], ...}
        by_city = {}
        for plan in self.plans:
            by_city.setdefault(plan['city'], []).append(plan)

        try:
            # with closes the file, even after an error
            with open(self.file_name, 'w', encoding='utf-8') as f:
                f.write('SAUDI WEEKEND PLANS REPORT\n')
                f.write('made on ' + datetime.now().strftime('%Y-%m-%d %H:%M') + '\n')
                f.write('=' * 50 + '\n\n')
                if not self.plans:
                    f.write('No plans are saved yet.\n')
                for city in sorted(by_city):
                    plans = by_city[city]
                    city_total = sum(plan['budget'] for plan in plans)
                    f.write(city + '  (' + str(len(plans)) + ' plan(s), '
                            + str(city_total) + ' SAR)\n')
                    for plan in plans:
                        f.write('  - ' + plan['plan_date'] + '  ' + plan['name']
                                + '  [' + plan['category'] + ']  '
                                + str(plan['budget']) + ' SAR\n')
                        if plan['notes']:
                            f.write('      notes: ' + plan['notes'] + '\n')
                    f.write('\n')
                total = sum(plan['budget'] for plan in self.plans)
                f.write('-' * 50 + '\n')
                f.write('Total: ' + str(len(self.plans)) + ' plan(s), ' + str(total) + ' SAR\n')
            self.saved = True
        except PermissionError:
            self.error = 'no permission to write ' + self.file_name + ' (is it open in another program?)'
        except OSError as error:
            self.error = str(error)


def fetch_plans():
    """Asks Flask for the saved plans. Returns the list, or None after an error."""
    try:
        with urlopen(URL, timeout=5) as reply:
            data = json.loads(reply.read().decode('utf-8'))
        return data['plans']
    except HTTPError as error:
        print('the server answered with status', error.code)
    except URLError:
        print('cannot reach the server: start server.py first')
    except socket.timeout:
        print('the server took too long to answer')
    return None


plans = fetch_plans()
if plans is not None:
    print('received', len(plans), 'plan(s) from the server')
    # start one thread, then wait for it with join()
    writer = ReportWriter(plans, REPORT_FILE)
    writer.start()
    writer.join()
    if writer.saved:
        print('report saved to', REPORT_FILE)
    else:
        print('report NOT saved:', writer.error)
