# Saudi Weekend Planner

Advanced Programming 462 · Individual Project (Client Server Project) · Dr. Majed Hariri

A desktop planner for weekend trips in Saudi Arabia. The user builds a trip day by day from a catalogue of
real places (or their own activities). The program then works out **how to move** between activities
(distance, drive or flight, minutes), **what the whole trip costs** (activities, fuel, flights, hotels), and
**whether the plan is possible**. It flags time conflicts, closed places and a late return home, and marks the
plan **Complete** only when every check passes. Gemini AI can build a whole weekend, and the same rules then
check its plan.

```
Tkinter window (gui.py, customtkinter)  ──HTTP GET/POST──▶  Flask (server.py, port 5050)  ──SQL──▶  SQLite (planner.db)
         ▲            JSON replies + status codes                 │
         └─────────────────────────────────────────────────────────┘── HTTPS ──▶ Gemini API (optional)
```

## Features

| Feature | Where |
|---|---|
| Accounts: register, log in, log out; PBKDF2 password hashes, session tokens, lock after 5 wrong passwords | `security.py`, `server.py` |
| Trips: add, view, edit, delete (with confirmation) | Sidebar and the *Edit trip* / *Delete* buttons |
| Activities: from 38 catalogue places in 8 cities, or your own; planned and actual cost | Itinerary tab, editor on the right |
| Travel between every two activities: km, minutes, car or flight, fuel or ticket cost | `planner.py` `TripPlanner.leg()` |
| Budget: activities × people + fuel + flights + hotels, planned vs actual | Budget tab (3 charts) |
| Checks: every day planned, no conflicts, inside the budget, home before midnight, dates | Checks tab, sidebar marks ✓ ✖ • |
| Interactive map: numbered pins, one coloured route per day, Streets / Light / Satellite styles | Map tab (`tkintermapview`) |
| **Extra feature: “Plan my weekend”** with Gemini AI, or the offline local planner | `ai_planner.py`, `planner.py` `local_plan()` |
| Export a trip to Excel and PDF | `exporters.py` |
| Threaded text report of all trips | `report.py` |

## How the planner calculates

* **Distance:** haversine distance between the two coordinates × 1.3 (a road is longer than a straight line).
* **Time:** under 40 km is a city drive at 40 km/h, otherwise 100 km/h, plus 10 min to park. A leg of 500 km or
  more is flown when the trip allows flights: 90 min in the air + 150 min at the airports.
* **Cost:** fuel = km ÷ 10 km/L × 2.33 SAR × cars (4 people per car); flight = (250 + 0.35 × km) × people;
  hotel = city price × rooms (2 people per room) for every night away from the home city.
* **Conflict:** the end of the previous activity + travel time is later than the start of the next one
  (or the first leg of a day would have to start the day before).
* **Complete:** all five checks pass. All the constants are at the top of `planner.py`.

## Setup and run

Python 3.10 or newer, on Windows (the Tajawal font is loaded from `fonts/` for the program only).

1. Install the packages:
   ```
   python -m pip install -r requirements.txt
   ```
2. Create the tables and the demo account (optional; `server.py` also creates the tables):
   ```
   python setup_db.py
   ```
   Demo login: **demo / weekend2026** (two ready trips).
3. Optional, for Gemini: copy `.env.example` to `.env` and put your key from https://aistudio.google.com/apikey.
   Without a key the local planner is used.
4. Start Flask first (terminal 1):
   ```
   python server.py
   ```
5. Start the window (terminal 2):
   ```
   python gui.py
   ```
6. Report helper (terminal 3, Flask running):
   ```
   python report.py
   ```
   It asks for the username and password, then writes `weekend_report.txt`.
7. Tests:
   ```
   python -m unittest discover tests
   ```

## Flask routes

| Method | Path | Login | Reply |
|---|---|---|---|
| GET | `/`, `/options` | no | server state, cities, categories |
| POST | `/register`, `/login` | no | 200, 400, 401, 409, 429 |
| POST | `/logout` | yes | ends the token |
| GET | `/places?city=` | yes | catalogue |
| GET | `/trips` | yes | **the JSON route of the saved records** (used by `report.py`) |
| GET | `/trips/<id>` | yes | trip + activities + analysis, or 404 |
| POST | `/trips/add`, `/trips/edit/<id>`, `/trips/delete/<id>` | yes | 400 / 404 on errors |
| POST | `/trips/<id>/activities/add`, `/activities/edit/<id>`, `/activities/delete/<id>` | yes | 400 / 404 on errors |
| POST | `/trips/<id>/autoplan` | yes | the plan from Gemini or the local planner |

The token goes in the `Authorization: Bearer …` header. Every query of a trip has `user_id = ?`, so a user can
only reach their own trips (another user's trip id gives 404).

## Where each course topic appears

| Topic | File and function or class |
|---|---|
| Python and collections | `planner.py` `TripPlanner.analyse()` (dicts `by_category`, `by_city`, `by_day`, lists of days and items), `local_plan()` (sets, sorting with `key=`), `places_data.py` (list of tuples, dict of cities) |
| Exceptions | `server.py` `check_trip()`, `check_activity()`, `whole_number()` (`ValueError`), `register()` (`sqlite3.IntegrityError`); `api_client.py` `ApiClient.send()` (`HTTPError`, `URLError`, `socket.timeout`); `ai_planner.py` (`AIError`); `gui.py` `MainView.export()` and `report.py` (`PermissionError`, `OSError`) |
| Classes | `Database`, `TripPlanner`, `GeminiPlanner`, `LoginLimiter`, `ApiClient`, `ReportWriter(threading.Thread)`, `App(ctk.CTk)`, `LoginView`, `MainView`, `TripDialog`, `PlanDialog` |
| SQLite | `database.py` `Database`: `create_tables()` (IF NOT EXISTS), `run()` / `rows()` with `?` placeholders, one connection per call, `with conn:` commit, `close()` in `finally`, foreign keys with `ON DELETE CASCADE` |
| Threads and files | `report.py` `ReportWriter` `start()` / `join()` and `with open(..., encoding='utf-8')`; `gui.py` `MainView.run_plan()` runs the AI request in a `Thread` and `wait_for_plan()` polls a `queue` |
| Tkinter | `gui.py`: customtkinter (built on Tkinter) entries, option menus, checkboxes, segmented buttons, tabs; ttk `Treeview`; `messagebox`, `filedialog`; `tkintermapview` map widget |
| Client and server | `api_client.py` `ApiClient.send()`: `urlopen` with `Request`, GET without data, POST with `urlencode(...).encode()`, `json.loads` of the reply |
| Flask | `server.py`: routes, `request.form`, `request.args`, `@login_required` decorator, JSON replies with 400/401/404/409/429, `@app.errorhandler` |

## Test results

`python -m unittest discover tests` → **38 tests, all passed** (planner rules, accounts and security, CRUD,
validation, 404s, user isolation, SQL injection text, data after restart, local planner).

Checks from the project sheet:

| Check | Result | How it was tested |
|---|---|---|
| Add, view, edit, delete a trip and an activity; only the chosen record changes | Pass | unit tests + window |
| Stop and start Flask: records remain | Pass | `test_data_remains_after_restart` + window |
| Missing name, budget `abc`, date `2026-13-40`, start `25:00` | 400 with a clear message | unit tests + window |
| Empty list | “No trips yet. Press + New trip…” | `test_empty_list` + window |
| Unknown id (record deleted elsewhere, then edited) | 404 “No activity has the id …”; the window reloads the trip | unit tests (delete twice, edit 999) |
| Flask stopped, then any action | “Cannot reach the server. Start server.py, then try again.” | window |
| Flask started again | The same button works without restarting the window | window |
| Riyadh at 16:00 then Jeddah at 19:30 the same day by car | ✖ conflict: 663 min of driving; plan stays *In progress* | `test_riyadh_then_jeddah_same_day_is_a_conflict` + window |
| `python report.py` | “report saved to weekend_report.txt” | terminal |

## Credits

* Map data © OpenStreetMap contributors; map tiles © Esri (World Street Map, Light Gray Canvas, World Imagery).
* Tajawal font by Boutros Fonts, SIL Open Font License (`fonts/OFL.txt`).
* Libraries: Flask, customtkinter, tkintermapview, matplotlib, openpyxl, fpdf2.
* Gemini API by Google (optional).
* Place coordinates and prices are approximate, taken from public maps and typical prices.
* Built with help from an AI assistant (Claude), declared as the course academic integrity policy asks.
