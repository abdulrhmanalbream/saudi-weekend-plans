# Saudi Weekend Plans: the Tkinter front end
# Start server.py first, then run: python gui.py
import json
import socket
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

# the address of the Flask server
SERVER = 'http://127.0.0.1:5050'

# used until the server sends its own lists
CITIES = ['Riyadh', 'Jeddah', 'Makkah', 'Madinah', 'Dammam', 'Khobar',
          'AlUla', 'Abha', 'Taif', 'Al Ahsa', 'Tabuk', 'Hail']
CATEGORIES = ['Cafe', 'Restaurant', 'Desert trip', 'Beach', 'Mall',
              'Park', 'Event', 'Family visit', 'Other']

# the id of the plan chosen in the table, or None
selected_id = None


def send(path, values=None):
    """Sends one request to Flask. Returns (True, data) or (False, error message).

    Without values it is a GET. With values it is a POST with a form body.
    """
    url = SERVER + path
    try:
        if values is None:
            # no data: urlopen sends a GET
            with urlopen(url, timeout=5) as reply:
                text = reply.read().decode('utf-8')
        else:
            # the fields as bytes: urlopen sends a POST
            body = urlencode(values).encode('utf-8')
            with urlopen(url, data=body, timeout=5) as reply:
                text = reply.read().decode('utf-8')
        return True, json.loads(text)
    # 400 and 404 from Flask raise HTTPError; it must come before URLError
    except HTTPError as error:
        try:
            data = json.loads(error.read().decode('utf-8'))
            return False, data.get('error', 'The server refused the request.')
        except ValueError:
            return False, 'The server answered with status ' + str(error.code) + '.'
    except URLError as error:
        # the reason can be a timeout too
        if isinstance(error.reason, socket.timeout):
            return False, 'The server took too long to answer. Try again.'
        return False, 'Cannot reach the server. Start server.py, then try again.'
    except socket.timeout:
        return False, 'The server took too long to answer. Try again.'
    except ValueError:
        return False, 'The server sent a reply that is not JSON.'


def show_status(text, ok=True):
    # green for success, red for an error
    status_label.config(text=text, fg='#1b7f3b' if ok else '#b00020')


def form_values():
    # the fields of the form as a dictionary
    return {'name': name_entry.get(),
            'city': city_box.get(),
            'category': category_box.get(),
            'budget': budget_entry.get(),
            'plan_date': date_entry.get(),
            'notes': notes_entry.get()}


def clear_form():
    global selected_id
    selected_id = None
    name_entry.delete(0, tk.END)
    budget_entry.delete(0, tk.END)
    notes_entry.delete(0, tk.END)
    date_entry.delete(0, tk.END)
    date_entry.insert(0, date.today().isoformat())
    city_box.set('')
    category_box.set('')
    table.selection_remove(table.selection())
    chosen_label.config(text='No plan chosen. Fill the form and press Add.')


def load_options():
    # ask Flask for the lists of the drop-down boxes
    ok, data = send('/options')
    if ok:
        city_box.config(values=data['cities'])
        category_box.config(values=data['categories'])
        filter_city_box.config(values=['All'] + data['cities'])


def load_plans():
    # the filters of the extra feature
    params = {}
    if filter_city_box.get() not in ('', 'All'):
        params['city'] = filter_city_box.get()
    if filter_budget_entry.get().strip() != '':
        params['max_budget'] = filter_budget_entry.get().strip()
    path = '/plans'
    if params:
        path += '?' + urlencode(params)

    ok, data = send(path)
    if not ok:
        show_status(data, ok=False)
        return

    # empty the table, then add one row for each plan
    for item in table.get_children():
        table.delete(item)
    for plan in data['plans']:
        table.insert('', tk.END, iid=str(plan['id']),
                     values=(plan['id'], plan['name'], plan['city'], plan['category'],
                             plan['budget'], plan['plan_date']))

    # the summary under the table
    if data['count'] == 0:
        summary_label.config(text='No plans to show.')
        if params:
            show_status('No plans match this filter.')
        else:
            show_status('No plans saved yet. Add your first weekend plan.')
    else:
        summary_label.config(text=str(data['count']) + ' plan(s)   ·   total budget '
                             + str(data['total_budget']) + ' SAR')
        show_status('Loaded ' + str(data['count']) + ' plan(s).')


def on_select(event):
    global selected_id
    chosen = table.selection()
    if not chosen:
        return
    plan_id = int(chosen[0])
    # ask Flask for the full record, notes included
    ok, data = send('/plans/' + str(plan_id))
    if not ok:
        show_status(data, ok=False)
        load_plans()
        return
    plan = data['plan']
    selected_id = plan['id']
    # put the record in the form
    name_entry.delete(0, tk.END)
    name_entry.insert(0, plan['name'])
    city_box.set(plan['city'])
    category_box.set(plan['category'])
    budget_entry.delete(0, tk.END)
    budget_entry.insert(0, str(plan['budget']))
    date_entry.delete(0, tk.END)
    date_entry.insert(0, plan['plan_date'])
    notes_entry.delete(0, tk.END)
    notes_entry.insert(0, plan['notes'] or '')
    chosen_label.config(text='Chosen plan id ' + str(selected_id) + '. Edit it or delete it.')


def add_plan():
    ok, data = send('/plans/add', form_values())
    if not ok:
        show_status(data, ok=False)
        messagebox.showwarning('Not saved', data)
        return
    load_plans()
    clear_form()
    # select the new row so the user sees it
    new_id = str(data['plan']['id'])
    if table.exists(new_id):
        table.selection_set(new_id)
        table.see(new_id)
    show_status(data['message'])


def edit_plan():
    if selected_id is None:
        messagebox.showinfo('Edit', 'Choose a plan in the table first.')
        return
    ok, data = send('/plans/edit/' + str(selected_id), form_values())
    if not ok:
        show_status(data, ok=False)
        messagebox.showwarning('Not updated', data)
        return
    load_plans()
    show_status(data['message'])


def delete_plan():
    if selected_id is None:
        messagebox.showinfo('Delete', 'Choose a plan in the table first.')
        return
    # ask before deleting
    sure = messagebox.askyesno('Delete', 'Delete the plan "' + name_entry.get() + '"?')
    if not sure:
        show_status('Nothing was deleted.')
        return
    ok, data = send('/plans/delete/' + str(selected_id), {})
    if not ok:
        show_status(data, ok=False)
        messagebox.showwarning('Not deleted', data)
        load_plans()
        return
    clear_form()
    load_plans()
    show_status(data['message'])


def show_all():
    filter_city_box.set('All')
    filter_budget_entry.delete(0, tk.END)
    load_plans()


def refresh():
    # also used after the server was stopped and started again
    load_options()
    load_plans()


# the window
root = tk.Tk()
root.title('Saudi Weekend Plans')
root.resizable(False, False)

# ---- the form
form = tk.LabelFrame(root, text='Plan', padx=10, pady=5)
form.grid(row=0, column=0, padx=10, pady=10, sticky='n')

tk.Label(form, text='Name').grid(row=0, column=0, sticky='w', pady=3)
name_entry = tk.Entry(form, width=28)
name_entry.grid(row=0, column=1, pady=3)

tk.Label(form, text='City').grid(row=1, column=0, sticky='w', pady=3)
city_box = ttk.Combobox(form, values=CITIES, state='readonly', width=25)
city_box.grid(row=1, column=1, pady=3)

tk.Label(form, text='Category').grid(row=2, column=0, sticky='w', pady=3)
category_box = ttk.Combobox(form, values=CATEGORIES, state='readonly', width=25)
category_box.grid(row=2, column=1, pady=3)

tk.Label(form, text='Budget (SAR)').grid(row=3, column=0, sticky='w', pady=3)
budget_entry = tk.Entry(form, width=28)
budget_entry.grid(row=3, column=1, pady=3)

tk.Label(form, text='Date (YYYY-MM-DD)').grid(row=4, column=0, sticky='w', pady=3)
date_entry = tk.Entry(form, width=28)
date_entry.grid(row=4, column=1, pady=3)

tk.Label(form, text='Notes').grid(row=5, column=0, sticky='w', pady=3)
notes_entry = tk.Entry(form, width=28)
notes_entry.grid(row=5, column=1, pady=3)

buttons = tk.Frame(form)
buttons.grid(row=6, column=0, columnspan=2, pady=8)
tk.Button(buttons, text='Add', width=8, command=add_plan).grid(row=0, column=0, padx=2)
tk.Button(buttons, text='Save edit', width=8, command=edit_plan).grid(row=0, column=1, padx=2)
tk.Button(buttons, text='Delete', width=8, command=delete_plan).grid(row=0, column=2, padx=2)
tk.Button(buttons, text='Clear', width=8, command=clear_form).grid(row=0, column=3, padx=2)

chosen_label = tk.Label(form, text='', fg='gray30', wraplength=260, justify='left')
chosen_label.grid(row=7, column=0, columnspan=2, sticky='w')

# ---- the filter: the extra feature
filters = tk.LabelFrame(root, text='Filter by city or budget', padx=10, pady=5)
filters.grid(row=1, column=0, padx=10, pady=(0, 10), sticky='new')

tk.Label(filters, text='City').grid(row=0, column=0, sticky='w', pady=3)
filter_city_box = ttk.Combobox(filters, values=['All'] + CITIES, state='readonly', width=25)
filter_city_box.set('All')
filter_city_box.grid(row=0, column=1, pady=3)

tk.Label(filters, text='Max budget (SAR)').grid(row=1, column=0, sticky='w', pady=3)
filter_budget_entry = tk.Entry(filters, width=28)
filter_budget_entry.grid(row=1, column=1, pady=3)

filter_buttons = tk.Frame(filters)
filter_buttons.grid(row=2, column=0, columnspan=2, pady=5)
tk.Button(filter_buttons, text='Filter', width=10, command=load_plans).grid(row=0, column=0, padx=2)
tk.Button(filter_buttons, text='Show all', width=10, command=show_all).grid(row=0, column=1, padx=2)
tk.Button(filter_buttons, text='Refresh', width=10, command=refresh).grid(row=0, column=2, padx=2)

# ---- the table of the plans
right = tk.Frame(root)
right.grid(row=0, column=1, rowspan=2, padx=(0, 10), pady=10, sticky='ns')

columns = ('id', 'name', 'city', 'category', 'budget', 'plan_date')
table = ttk.Treeview(right, columns=columns, show='headings', height=16, selectmode='browse')
widths = {'id': 40, 'name': 180, 'city': 90, 'category': 100, 'budget': 80, 'plan_date': 95}
titles = {'id': 'ID', 'name': 'Name', 'city': 'City', 'category': 'Category',
          'budget': 'Budget', 'plan_date': 'Date'}
for column in columns:
    table.heading(column, text=titles[column])
    table.column(column, width=widths[column], anchor='w')
table.grid(row=0, column=0, sticky='ns')
table.bind('<<TreeviewSelect>>', on_select)

scroll = ttk.Scrollbar(right, orient='vertical', command=table.yview)
scroll.grid(row=0, column=1, sticky='ns')
table.config(yscrollcommand=scroll.set)

summary_label = tk.Label(right, text='', font=('Segoe UI', 10, 'bold'))
summary_label.grid(row=1, column=0, sticky='w', pady=(6, 0))

# ---- the status line at the bottom
status_label = tk.Label(root, text='', anchor='w')
status_label.grid(row=2, column=0, columnspan=2, sticky='we', padx=10, pady=(0, 8))

# fill the window from the server, then wait for the user
clear_form()
refresh()
root.mainloop()
