# Saudi Weekend Plans

Advanced Programming 462 · Individual Project · Client Server Project

A desktop app for planning weekend outings in Saudi cities. The user saves plans
(name, city, category, budget, date, notes) in a Tkinter window. The window talks
to a Flask server on port 5050. Flask checks the values and keeps the plans in SQLite.

```
Tkinter (gui.py)  <->  Flask (server.py, port 5050)  <->  SQLite (weekend.db)
```

**Extra feature:** filter the plans by city and/or a maximum budget. A summary line
shows how many plans match and their total budget in SAR.

## Files

| File | What it does |
|---|---|
| `server.py` | Flask back end, the `PlanStore` class (all SQL), input checks, JSON routes |
| `gui.py` | Tkinter front end: form, buttons, table, filter, messages |
| `report.py` | Report helper: gets the plans from Flask and writes `weekend_report.txt` in a thread |
| `setup_db.py` | Creates the table and adds 5 sample plans if the table is empty (optional) |
| `requirements.txt` | The package to install (Flask) |

## Setup and run

1. Install the package (Python 3.9 or newer):
   ```
   python -m pip install -r requirements.txt
   ```
2. Create the table, with sample plans (optional, since `server.py` also creates the table):
   ```
   python setup_db.py
   ```
3. Start Flask first, in terminal 1:
   ```
   python server.py
   ```
4. Start Tkinter, in terminal 2:
   ```
   python gui.py
   ```
5. Report helper, in terminal 3, with Flask running:
   ```
   python report.py
   ```
   It writes `weekend_report.txt`.

## Routes

| Method | Path | Reply |
|---|---|---|
| GET | `/` | server ready message |
| GET | `/options` | the lists of cities and categories |
| GET | `/plans?city=&max_budget=` | `{plans, count, total_budget}` (the JSON route the report uses) |
| GET | `/plans/<id>` | one plan, or 404 |
| POST | `/plans/add` | the new plan, or 400 |
| POST | `/plans/edit/<id>` | the updated plan, 400 or 404 |
| POST | `/plans/delete/<id>` | message, or 404 |

## Where each course topic appears

| Topic | Where |
|---|---|
| Python and collections | `server.py`: `row_to_dict()` (dict + zip), `PlanStore.all_plans()` (list of dicts, params list), `CITIES`/`CATEGORIES` lists. `report.py`: `ReportWriter.run()` groups plans in a dict of lists |
| Exceptions | `server.py`: `check_values()` (`ValueError` from `int()` and `strptime()`), `sqlite3.Error` in each route. `gui.py`: `send()` (`HTTPError`, `URLError`, `socket.timeout`). `report.py`: `PermissionError`, `OSError` |
| Classes | `server.py`: class `PlanStore` (all database work). `report.py`: class `ReportWriter(threading.Thread)` |
| SQLite | `server.py`: `PlanStore.create_table / all_plans / get_plan / add_plan / edit_plan / delete_plan`, with `?` placeholders, a new connection per call, `with conn:` commits, `close()` in `finally` |
| Threads and files | `report.py`: `ReportWriter.start()` and `join()`, `with open(..., encoding='utf-8')` |
| Tkinter | `gui.py`: Labels, Entries, Comboboxes, Buttons, Treeview, `messagebox.askyesno` before delete, status label |
| Client and server | `gui.py`: `send()` uses `urlopen` (GET without data, POST with `urlencode` bytes) and `json.loads` |
| Flask | `server.py`: routes `list_plans`, `one_plan`, `add_plan`, `edit_plan`, `delete_plan`; replies as JSON with 400/404 |

## Test results

| Test | Result |
|---|---|
| Add a valid plan | Saved, shown and selected in the table |
| Missing name | 400: "The name of the plan is required." |
| Budget `abc` | 400: "The budget must be a whole number of riyals." |
| Date `2026-13-40` | 400: "The date must look like 2026-12-04" |
| Edit a plan | Only that plan changed |
| Delete a plan | Asks first, then deleted |
| Edit/delete a deleted id | 404: "No plan has the id 6. It may have been deleted." |
| Unknown id `/plans/999` | 404 |
| Filter Riyadh + max 300 | 1 plan, total 250 SAR |
| Max budget `x` | 400 |
| Empty list / no match | "No plans saved yet" / "No plans match this filter." |
| Flask stopped, action in GUI | "Cannot reach the server. Start server.py, then try again." |
| Flask started again, press Refresh | Works without restarting the window |
| Restart both programs | Saved plans remain |
| `python report.py` | "report saved to weekend_report.txt" |
| `report.py` with Flask stopped | "cannot reach the server: start server.py first" |

## Credits

- Course slides and labs of Advanced Programming 462 (Dr. Majed Hariri).
- Built with help from an AI assistant (Claude). Declared here as the course
  academic integrity policy asks.
