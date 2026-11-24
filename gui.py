# Saudi Weekend Planner: the Tkinter front end
# customtkinter is built on Tkinter: CTk is a subclass of tk.Tk, and every widget is a Tkinter widget.
# Start server.py first, then run: python gui.py
import ctypes
import glob
import os
import queue
import threading
import tkinter as tk
import webbrowser
from urllib.parse import urlencode
from datetime import date, timedelta
from tkinter import filedialog, ttk

import customtkinter as ctk
import tkintermapview
from matplotlib import font_manager
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from api_client import ApiClient
from exporters import export_excel, export_pdf

HERE = os.path.dirname(os.path.abspath(__file__))


def load_fonts():
    """Loads the Tajawal font files for this program only (nothing is installed on the computer)."""
    for path in glob.glob(os.path.join(HERE, 'fonts', '*.ttf')):
        try:
            # 0x10 = FR_PRIVATE: only this process sees the font (Windows)
            ctypes.windll.gdi32.AddFontResourceExW(path, 0x10, 0)
        except (AttributeError, OSError):
            pass
        try:
            font_manager.fontManager.addfont(path)
        except (OSError, ValueError):
            pass


load_fonts()

# ---------------------------------------------------------------- the design
BG = '#F5F4F0'          # page background: a soft warm white
PANEL = '#FFFFFF'       # cards
SOFTBG = '#F8F7F4'      # inner boxes and quiet buttons
INK = '#1E2B32'         # main text
INK2 = '#2B3A42'
MUTED = '#6C767B'       # secondary text
LINE = '#E5E2DB'        # borders
ACCENT = '#1F7A66'      # the one primary colour: a calm teal green
ACCENT2 = '#17614F'
TEAL = '#1F7A66'        # success uses the same green
TEAL2 = '#17614F'
TINT = '#DDEFE8'        # selected things: a light tint of the primary colour
TINT2 = '#CBE6DC'
ROSE = '#C24A35'        # errors and conflicts only
ROSE2 = '#A33A28'
GOLD = '#C9973F'        # hotels and warnings
DAY_COLOURS = ['#1F7A66', '#C9973F', '#3D6FA8', '#8A5BA0', '#C24A35', '#2E8E9C', '#6F8A34']
# OpenStreetMap-based map styles from Esri: (base tiles, label tiles or None)
ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/'
MAP_STYLES = {
    'Streets': (ESRI + 'World_Street_Map/MapServer/tile/{z}/{y}/{x}', None),
    'Light': (ESRI + 'Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
              ESRI + 'Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}'),
    'Satellite': (ESRI + 'World_Imagery/MapServer/tile/{z}/{y}/{x}',
                  ESRI + 'Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'),
}

FAMILY = 'Tajawal'
CUSTOM = 'My own activity...'

ctk.set_appearance_mode('light')


def font(size=14, weight='normal'):
    # 'bold' uses Tajawal Bold; 'heavy' uses Tajawal ExtraBold; 'medium' uses Tajawal Medium
    if weight == 'heavy':
        return ctk.CTkFont(family=FAMILY + ' ExtraBold', size=size)
    if weight == 'medium':
        return ctk.CTkFont(family=FAMILY + ' Medium', size=size)
    return ctk.CTkFont(family=FAMILY, size=size, weight='bold' if weight == 'bold' else 'normal')


def day_name(day):
    # '2026-12-03' -> 'Thu 03 Dec'
    return date.fromisoformat(day).strftime('%a %d %b')


def money(value):
    return '{:,.0f} SAR'.format(value)


def button(parent, text, command, kind='dark', width=0, height=38):
    """The buttons of the program: dark, accent, teal, danger or ghost."""
    colours = {'dark': (INK, INK2, 'white'), 'accent': (ACCENT, ACCENT2, 'white'), 'teal': (TEAL, TEAL2, 'white'),
               'danger': (ROSE, ROSE2, 'white'), 'ghost': (PANEL, SOFTBG, INK), 'side': (SOFTBG, TINT, INK)}
    fg, hover, text_colour = colours[kind]
    return ctk.CTkButton(parent, text=text, command=command, fg_color=fg, hover_color=hover, text_color=text_colour,
                         corner_radius=10, height=height, width=width, font=font(14, 'bold'),
                         border_width=1 if kind in ('ghost', 'side') else 0, border_color=LINE)


def entry(parent, placeholder='', width=140, show=None):
    return ctk.CTkEntry(parent, placeholder_text=placeholder, width=width, height=36, corner_radius=9,
                        border_color=LINE, fg_color='white', text_color=INK, font=font(14), show=show)


def choice(parent, values, width=140, command=None):
    return ctk.CTkOptionMenu(parent, values=values or [''], width=width, height=36, corner_radius=9,
                             fg_color='white', button_color=SOFTBG, button_hover_color=LINE, text_color=INK,
                             dropdown_font=font(13), font=font(14), command=command,
                             dropdown_fg_color='white', dropdown_text_color=INK, dropdown_hover_color=SOFTBG)


def caption(parent, text, size=12, colour=MUTED, weight='medium'):
    return ctk.CTkLabel(parent, text=text, font=font(size, weight), text_color=colour, anchor='w')


def panel(parent, colour=PANEL, radius=16):
    return ctk.CTkFrame(parent, fg_color=colour, corner_radius=radius, border_width=1 if colour == PANEL else 0,
                        border_color=LINE)


def set_text(widget, value):
    widget.delete(0, 'end')
    if value not in (None, ''):
        widget.insert(0, str(value))


class Message(ctk.CTkToplevel):
    """A small window for a message or a yes/no question, in the look of the program."""

    def __init__(self, parent, title, text, kind='info'):
        super().__init__(parent)
        self.result = False
        self.title(title)
        self.configure(fg_color=PANEL)
        self.resizable(False, False)
        self.transient(parent)
        box = ctk.CTkFrame(self, fg_color='transparent')
        box.pack(padx=26, pady=22)
        colour = {'warning': ROSE, 'question': INK}.get(kind, ACCENT)
        ctk.CTkLabel(box, text=title, font=font(18, 'heavy'), text_color=colour, anchor='w').pack(fill='x')
        ctk.CTkLabel(box, text=text, font=font(14), text_color=INK, wraplength=380, justify='left',
                     anchor='w').pack(fill='x', pady=(8, 18))
        row = ctk.CTkFrame(box, fg_color='transparent')
        row.pack(fill='x')
        if kind == 'question':
            button(row, 'Yes', lambda: self.close(True), 'danger' if 'elete' in title or 'emove' in title
                   else 'accent', 100).pack(side='right')
            button(row, 'No', lambda: self.close(False), 'ghost', 100).pack(side='right', padx=8)
        else:
            button(row, 'OK', lambda: self.close(True), 'accent', 100).pack(side='right')
        self.bind('<Return>', lambda event: self.close(True))
        self.bind('<Escape>', lambda event: self.close(False))
        # in the middle of the window that asked
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry('+%d+%d' % (max(x, 0), max(y, 0)))
        self.after(50, self.grab_set)
        self.wait_window()

    def close(self, result):
        self.result = result
        self.destroy()


def notice(title, text, parent=None):
    Message(parent, title, text, 'info')


def warn(title, text, parent=None):
    Message(parent, title, text, 'warning')


def confirm(title, text, parent=None):
    return Message(parent, title, text, 'question').result


def style_tables(root):
    """The ttk tables (Treeview) in the same look as the customtkinter widgets."""
    scale = ctk.ScalingTracker.get_window_scaling(root)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('Plan.Treeview', background='white', fieldbackground='white', foreground=INK,
                    rowheight=int(40 * scale), borderwidth=0, relief='flat', font=(FAMILY, 11))
    style.layout('Plan.Treeview', [('Plan.Treeview.treearea', {'sticky': 'nswe'})])
    style.map('Plan.Treeview', background=[('selected', TINT)], foreground=[('selected', INK)])
    style.configure('Plan.Treeview.Heading', background='white', foreground=MUTED, relief='flat',
                    font=(FAMILY + ' Medium', 10), padding=(10, 10), borderwidth=0)
    style.map('Plan.Treeview.Heading', background=[('active', 'white')])
    style.configure('Plan.Vertical.TScrollbar', background=LINE, troughcolor='white', bordercolor='white',
                    arrowcolor=MUTED, gripcount=0, relief='flat')


# ---------------------------------------------------------------- the login screen
class LoginView(ctk.CTkFrame):
    """Log in or create an account."""

    def __init__(self, app):
        super().__init__(app, fg_color=BG, corner_radius=0)
        self.app = app
        # the left half: the name of the program
        hero = ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=0)
        hero.place(relx=0, rely=0, relwidth=0.5, relheight=1)
        inner = ctk.CTkFrame(hero, fg_color='transparent')
        inner.place(relx=0.12, rely=0.5, anchor='w')
        ctk.CTkLabel(inner, text='☀', font=font(54), text_color='#FFE2A8').pack(anchor='w')
        ctk.CTkLabel(inner, text='Saudi Weekend\nPlanner', font=font(44, 'heavy'), text_color='white',
                     justify='left').pack(anchor='w')
        ctk.CTkLabel(inner, text='Plan the trip, see it on the map,\nand know it fits your time and budget.',
                     font=font(17), text_color='#D7EEE6', justify='left').pack(anchor='w', pady=(14, 28))
        for line in ['•  Real travel times between places and cities',
                     '•  Hotels, fuel and flights in the budget',
                     '•  Gemini AI builds the whole weekend']:
            ctk.CTkLabel(inner, text=line, font=font(15, 'medium'), text_color='#FFFFFF').pack(anchor='w', pady=2)

        # the right half: the form
        form = panel(self)
        form.place(relx=0.75, rely=0.5, anchor='center')
        box = ctk.CTkFrame(form, fg_color='transparent')
        box.pack(padx=40, pady=36)
        ctk.CTkLabel(box, text='Welcome back', font=font(28, 'heavy'), text_color=INK).pack(anchor='w')
        caption(box, 'Log in to see your trips', 14).pack(anchor='w', pady=(0, 20))
        caption(box, 'Username').pack(anchor='w')
        self.username = entry(box, 'e.g. demo', 320)
        self.username.pack(pady=(2, 12))
        caption(box, 'Password').pack(anchor='w')
        self.password = entry(box, '8+ characters, letters and digits', 320, show='•')
        self.password.pack(pady=(2, 20))
        self.password.bind('<Return>', lambda event: self.login())
        button(box, 'Log in', self.login, 'accent', 320, 42).pack()
        button(box, 'Create an account', self.register, 'ghost', 320, 42).pack(pady=(10, 0))
        self.message = ctk.CTkLabel(box, text='', font=font(13, 'medium'), text_color=ROSE, wraplength=320,
                                    justify='left')
        self.message.pack(anchor='w', pady=(14, 0))
        self.username.focus_set()

    def login(self):
        ok, data, status = self.app.api.login(self.username.get(), self.password.get())
        if not ok:
            self.message.configure(text=data, text_color=ROSE)
            return
        self.app.show_main()

    def register(self):
        ok, data, status = self.app.api.register(self.username.get(), self.password.get())
        if not ok:
            self.message.configure(text=data, text_color=ROSE)
            return
        # the account exists: log in straight away
        self.login()


# ---------------------------------------------------------------- the trip form
class TripDialog(ctk.CTkToplevel):
    """A window to create or edit a trip. Calls on_save(values); closes when it returns True."""

    def __init__(self, app, cities, on_save, trip=None):
        super().__init__(app)
        self.on_save = on_save
        self.title('Edit trip' if trip else 'New trip')
        self.configure(fg_color=PANEL)
        self.resizable(False, False)
        self.transient(app)
        self.after(150, self.grab_set)
        # never taller than the screen: the form scrolls when it does not fit
        height = min(800, self.winfo_screenheight() - 110)
        self.geometry('560x%d+%d+20' % (height, app.winfo_rootx() + 300))
        holder = ctk.CTkScrollableFrame(self, fg_color=PANEL, scrollbar_button_color=LINE)
        holder.pack(fill='both', expand=True)
        today = date.today()
        start = today + timedelta(days=(3 - today.weekday()) % 7)   # the next Thursday
        trip = trip or {'name': '', 'home_city': 'Riyadh', 'destinations': 'Riyadh',
                        'start_date': start.isoformat(), 'end_date': (start + timedelta(days=2)).isoformat(),
                        'people': 2, 'budget': 3000, 'transport': 'car', 'notes': '', 'stays': ''}
        box = ctk.CTkFrame(holder, fg_color='transparent')
        box.pack(padx=18, pady=16)
        ctk.CTkLabel(box, text='Edit trip' if trip.get('id') else 'New trip', font=font(24, 'heavy'),
                     text_color=INK).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))

        caption(box, 'Trip name').grid(row=1, column=0, columnspan=4, sticky='w')
        self.name = entry(box, 'e.g. Jeddah by the sea', 470)
        self.name.grid(row=2, column=0, columnspan=4, sticky='w')
        set_text(self.name, trip['name'])

        # the trip starts in one city and may end in another one
        caption(box, 'Start city').grid(row=3, column=0, sticky='w', pady=(12, 0))
        caption(box, 'End city').grid(row=3, column=1, sticky='w', pady=(12, 0), padx=(8, 0))
        caption(box, 'When far legs (500+ km)').grid(row=3, column=2, columnspan=2, sticky='w', pady=(12, 0))
        self.home = choice(box, cities, 110)
        self.home.set(trip['home_city'])
        self.home.grid(row=4, column=0, sticky='w')
        self.end_city = choice(box, cities, 110)
        self.end_city.set(trip.get('end_city') or trip['home_city'])
        self.end_city.grid(row=4, column=1, sticky='w', padx=(8, 0))
        self.transport = ctk.CTkSegmentedButton(box, values=['Drive', 'Fly'], font=font(13, 'bold'), height=36,
                                                selected_color=TINT, selected_hover_color=TINT2, unselected_color=SOFTBG, unselected_hover_color=LINE, text_color=INK, fg_color=SOFTBG)
        self.transport.set('Fly' if trip['transport'] == 'flight' else 'Drive')
        self.transport.grid(row=4, column=2, columnspan=2, sticky='we', padx=(10, 0))

        caption(box, 'Destination cities').grid(row=5, column=0, columnspan=4, sticky='w', pady=(12, 2))
        chosen = [c.strip() for c in trip['destinations'].split(',')]
        self.city_vars = {}
        for number, city in enumerate(cities):
            var = tk.BooleanVar(value=city in chosen)
            ctk.CTkCheckBox(box, text=city, variable=var, font=font(13), text_color=INK, fg_color=ACCENT,
                            hover_color=ACCENT2, border_color=LINE, corner_radius=6, checkbox_width=20,
                            checkbox_height=20).grid(row=6 + number // 4, column=number % 4, sticky='w', pady=3)
            self.city_vars[city] = var
        row = 6 + (len(cities) + 3) // 4

        # the cities with a house or family: a night there costs nothing
        caption(box, 'I have a house or family in (free nights)').grid(row=row, column=0, columnspan=4, sticky='w',
                                                                        pady=(12, 2))
        free = [c.strip() for c in (trip.get('stays') or '').split(',')]
        self.stay_vars = {}
        for number, city in enumerate(cities):
            var = tk.BooleanVar(value=city in free)
            ctk.CTkCheckBox(box, text=city, variable=var, font=font(13), text_color=INK, fg_color=TEAL,
                            hover_color=TEAL2, border_color=LINE, corner_radius=6, checkbox_width=20,
                            checkbox_height=20).grid(row=row + 1 + number // 4, column=number % 4, sticky='w', pady=3)
            self.stay_vars[city] = var
        row = row + 1 + (len(cities) + 3) // 4

        quick = ctk.CTkFrame(box, fg_color='transparent')
        quick.grid(row=row, column=0, columnspan=4, sticky='w', pady=(12, 0))
        caption(quick, 'Dates:').pack(side='left', padx=(0, 8))
        for text, weeks in (('This weekend', 0), ('Next weekend', 1)):
            ctk.CTkButton(quick, text=text, width=110, height=28, corner_radius=8, fg_color=SOFTBG, hover_color=TINT,
                          text_color=INK, border_width=1, border_color=LINE, font=font(12, 'bold'),
                          command=lambda w=weeks: self.weekend(w)).pack(side='left', padx=(0, 6))
        row += 1
        caption(box, 'Start (YYYY-MM-DD)').grid(row=row, column=0, sticky='w', pady=(8, 0))
        caption(box, 'End').grid(row=row, column=1, sticky='w', pady=(8, 0), padx=(8, 0))
        caption(box, 'People').grid(row=row, column=2, sticky='w', pady=(8, 0), padx=(8, 0))
        caption(box, 'Budget (SAR)').grid(row=row, column=3, sticky='w', pady=(8, 0), padx=(8, 0))
        self.start, self.end, self.people, self.budget = (entry(box, '', 110) for _ in range(4))
        for column, (widget, value) in enumerate([(self.start, trip['start_date']), (self.end, trip['end_date']),
                                                  (self.people, trip['people']), (self.budget, trip['budget'])]):
            widget.grid(row=row + 1, column=column, sticky='w', padx=(0 if column == 0 else 8, 0))
            set_text(widget, value)

        # the car: how many km it goes on one litre, and the petrol it uses
        caption(box, 'Car: km per litre').grid(row=row + 2, column=0, columnspan=2, sticky='w', pady=(12, 0))
        caption(box, 'Petrol').grid(row=row + 2, column=2, columnspan=2, sticky='w', pady=(12, 0), padx=(8, 0))
        self.kmpl = entry(box, 'e.g. 12 (SUV 8, small car 20)', 225)
        self.kmpl.grid(row=row + 3, column=0, columnspan=2, sticky='w')
        set_text(self.kmpl, trip.get('car_kmpl') or 12)
        self.fuel = ctk.CTkSegmentedButton(box, values=['91', '95'], font=font(13, 'bold'), height=36,
                                           selected_color=TINT, selected_hover_color=TINT2, unselected_color=SOFTBG, unselected_hover_color=LINE, text_color=INK, fg_color=SOFTBG)
        self.fuel.set(str(trip.get('fuel') or '91'))
        self.fuel.grid(row=row + 3, column=2, columnspan=2, sticky='we', padx=(8, 0))

        caption(box, 'Notes').grid(row=row + 4, column=0, columnspan=4, sticky='w', pady=(12, 0))
        self.notes = entry(box, 'optional', 470)
        self.notes.grid(row=row + 5, column=0, columnspan=4, sticky='w')
        set_text(self.notes, trip.get('notes'))
        button(box, 'Save trip', self.save, 'accent', 470, 42).grid(row=row + 6, column=0, columnspan=4, pady=(18, 0))
        self.name.focus_set()

    def weekend(self, weeks):
        # Thursday to Saturday of this week (or of a later week)
        today = date.today()
        thursday = today + timedelta(days=(3 - today.weekday()) % 7 + 7 * weeks)
        set_text(self.start, thursday.isoformat())
        set_text(self.end, (thursday + timedelta(days=2)).isoformat())

    def save(self):
        values = {'name': self.name.get(), 'home_city': self.home.get(),
                  'destinations': ', '.join(c for c, var in self.city_vars.items() if var.get()),
                  'start_date': self.start.get(), 'end_date': self.end.get(), 'people': self.people.get(),
                  'budget': self.budget.get(), 'transport': 'flight' if self.transport.get() == 'Fly' else 'car',
                  'end_city': self.end_city.get(),
                  'notes': self.notes.get(),
                  'stays': ', '.join(c for c, var in self.stay_vars.items() if var.get()),
                  'car_kmpl': self.kmpl.get(), 'fuel': self.fuel.get()}
        if self.on_save(values):
            self.destroy()


# ---------------------------------------------------------------- the AI form
class PlanDialog(ctk.CTkToplevel):
    """Choose interests and pace, then ask the server for a whole plan."""

    def __init__(self, app, categories, ai_on, on_run):
        super().__init__(app)
        self.on_run = on_run
        self.title('Plan my weekend')
        self.configure(fg_color=PANEL)
        self.resizable(False, False)
        self.transient(app)
        self.after(150, self.grab_set)
        box = ctk.CTkFrame(self, fg_color='transparent')
        box.pack(padx=28, pady=24)
        ctk.CTkLabel(box, text='Plan my weekend', font=font(24, 'heavy'), text_color=INK).pack(anchor='w')
        caption(box, 'The current activities of this trip will be replaced.', 13, GOLD).pack(anchor='w',
                                                                                             pady=(0, 14))
        caption(box, 'What do you enjoy?', 14, INK, 'bold').pack(anchor='w')
        grid = ctk.CTkFrame(box, fg_color='transparent')
        grid.pack(anchor='w', pady=(4, 14))
        self.vars = {}
        for number, category in enumerate(categories):
            var = tk.BooleanVar(value=category in ('Heritage', 'Food', 'Nature'))
            ctk.CTkCheckBox(grid, text=category, variable=var, font=font(13), text_color=INK, fg_color=ACCENT,
                            hover_color=ACCENT2, border_color=LINE, corner_radius=6, checkbox_width=20,
                            checkbox_height=20, width=110).grid(row=number // 4, column=number % 4, sticky='w', pady=3)
            self.vars[category] = var
        caption(box, 'Pace', 14, INK, 'bold').pack(anchor='w')
        self.pace = ctk.CTkSegmentedButton(box, values=['Relaxed', 'Normal', 'Packed'], font=font(13, 'bold'),
                                           height=36, selected_color=TINT, selected_hover_color=TINT2, unselected_color=SOFTBG, unselected_hover_color=LINE, text_color=INK, fg_color=SOFTBG)
        self.pace.set('Normal')
        self.pace.pack(fill='x', pady=(4, 14))
        caption(box, 'Planner', 14, INK, 'bold').pack(anchor='w')
        self.engine = ctk.CTkSegmentedButton(box, values=['Gemini AI', 'Local (offline)'], font=font(13, 'bold'),
                                             height=36, selected_color=TINT, selected_hover_color=TINT2, unselected_color=SOFTBG, unselected_hover_color=LINE, text_color=INK, fg_color=SOFTBG)
        self.engine.set('Gemini AI' if ai_on else 'Local (offline)')
        self.engine.pack(fill='x', pady=(4, 6))
        caption(box, ('' if ai_on else 'No Gemini key on the server: the local planner is used.  ') +
                'Both plans pass the same checks.', 12).pack(anchor='w', pady=(0, 16))
        button(box, 'Make the plan', self.run, 'accent', 460, 44).pack()

    def run(self):
        interests = [c for c, var in self.vars.items() if var.get()]
        pace = self.pace.get().lower()
        engine = 'ai' if self.engine.get() == 'Gemini AI' else 'local'
        self.destroy()
        self.on_run(interests, pace, engine)


# ---------------------------------------------------------------- my places: home, family, friends
class PlacesDialog(ctk.CTkToplevel):
    """A map where the user drops a pin on their home, a family house or a friend's house."""

    KIND_COLOURS = {'Home': INK, 'Family': TEAL, 'Friends': '#3E64B5'}

    def __init__(self, app, api, on_change):
        super().__init__(app)
        self.app = app
        self.api = api
        self.on_change = on_change
        self.pin = None        # the point clicked on the map, (lat, lng)
        self.title('My places')
        self.configure(fg_color=PANEL)
        width = min(1100, self.winfo_screenwidth() - 80)
        height = min(680, self.winfo_screenheight() - 110)
        self.geometry('%dx%d+%d+20' % (width, height, 40))
        self.transient(app)
        self.after(150, self.grab_set)

        # the left side: the form and the list
        side = ctk.CTkFrame(self, fg_color=PANEL, width=330)
        side.pack(side='left', fill='y', padx=(18, 8), pady=16)
        side.pack_propagate(False)
        ctk.CTkLabel(side, text='My places', font=font(22, 'heavy'), text_color=INK,
                     anchor='w').pack(fill='x')
        caption(side, 'Trips start and end at your Home. A night at a\nFamily or Friends place costs nothing.',
                12).pack(fill='x', pady=(0, 10))
        caption(side, '1. Find the area (optional)').pack(fill='x')
        row = ctk.CTkFrame(side, fg_color='transparent')
        row.pack(fill='x', pady=(2, 8))
        self.search = entry(row, 'e.g. Al Rawdah, Jeddah', 220)
        self.search.pack(side='left')
        self.search.bind('<Return>', lambda event: self.find())
        button(row, 'Find', self.find, 'dark', 80, 36).pack(side='right')
        caption(side, '2. Click on the exact place on the map').pack(fill='x')
        self.pin_label = caption(side, 'No point chosen yet', 12, GOLD)
        self.pin_label.pack(fill='x', pady=(2, 8))
        caption(side, '3. Name and kind').pack(fill='x')
        self.name = entry(side, 'e.g. Home, My uncle, Ahmed’s house', 310)
        self.name.pack(fill='x', pady=(2, 6))
        self.kind = ctk.CTkSegmentedButton(side, values=['Home', 'Family', 'Friends'], font=font(13, 'bold'),
                                           height=36, selected_color=TINT, selected_hover_color=TINT2, unselected_color=SOFTBG, unselected_hover_color=LINE, text_color=INK, fg_color=SOFTBG)
        self.kind.set('Home')
        self.kind.pack(fill='x', pady=(0, 8))
        button(side, 'Save place', self.save, 'accent', 310, 40).pack(fill='x')
        self.message = ctk.CTkLabel(side, text='', font=font(12, 'medium'), text_color=ROSE, wraplength=300,
                                    justify='left', anchor='w')
        self.message.pack(fill='x', pady=(6, 4))
        caption(side, 'SAVED', 11, MUTED, 'bold').pack(fill='x', pady=(4, 2))
        self.list = ctk.CTkScrollableFrame(side, fg_color=SOFTBG, corner_radius=12)
        self.list.pack(fill='both', expand=True)

        # the right side: the map
        holder = ctk.CTkFrame(self, fg_color=LINE, corner_radius=14)
        holder.pack(side='left', fill='both', expand=True, padx=(8, 18), pady=16)
        self.map = tkintermapview.TkinterMapView(holder, corner_radius=12)
        self.map.pack(fill='both', expand=True, padx=1, pady=1)
        base, labels = MAP_STYLES['Streets']
        self.map.set_tile_server(base, max_zoom=19)
        self.map.set_position(23.8859, 45.0792)
        self.map.set_zoom(5)
        # a left click on the map chooses the point
        self.map.add_left_click_map_command(self.choose)
        self.load()

    def choose(self, coords):
        self.pin = coords
        if hasattr(self, 'pin_marker') and self.pin_marker:
            self.pin_marker.delete()
        self.pin_marker = self.map.set_marker(coords[0], coords[1], text='New place', marker_color_outside=ACCENT,
                                              marker_color_circle='white', text_color=ACCENT2,
                                              font=(FAMILY + ' Bold', 10))
        self.pin_label.configure(text='Chosen: %.5f, %.5f' % coords, text_color=TEAL)

    def find(self):
        # moves the map to an address (OpenStreetMap search; needs internet)
        text = self.search.get().strip()
        if not text:
            return
        try:
            found = self.map.set_address(text + ', Saudi Arabia')
        except Exception:
            found = False
        if found:
            self.map.set_zoom(15)
            self.message.configure(text='Now click on the exact place.', text_color=TEAL)
        else:
            self.message.configure(text='Not found. Zoom and move the map by hand.', text_color=ROSE)

    def load(self):
        ok, data, status = self.api.my_places()
        if not ok:
            self.message.configure(text=data, text_color=ROSE)
            return
        self.draw(data['places'])

    def draw(self, places):
        for widget in self.list.winfo_children():
            widget.destroy()
        self.map.delete_all_marker()
        self.pin_marker = None
        icons = {'Home': 'Home', 'Family': 'Family', 'Friends': 'Friends'}
        if not places:
            caption(self.list, 'Nothing saved yet.', 12).pack(fill='x', padx=8, pady=8)
        for place in places:
            row = ctk.CTkFrame(self.list, fg_color=PANEL, corner_radius=10)
            row.pack(fill='x', pady=3, padx=2)
            ctk.CTkLabel(row, text=place['name'], font=font(13, 'bold'),
                         text_color=INK, anchor='w').pack(side='left', padx=(10, 4), pady=6)
            caption(row, icons[place['kind']] + ' \u00b7', 12, self.KIND_COLOURS[place['kind']], 'bold').pack(
                side='left', padx=(0, 4))
            caption(row, place['city'], 12).pack(side='left')
            ctk.CTkButton(row, text='✕', width=30, height=26, corner_radius=8, fg_color=SOFTBG,
                          hover_color='#F6D5CF', text_color=ROSE, font=font(12, 'bold'),
                          command=lambda p=place: self.remove(p)).pack(side='right', padx=6)
            self.map.set_marker(place['lat'], place['lng'], text=place['name'][:18],
                                marker_color_outside=self.KIND_COLOURS[place['kind']], marker_color_circle='white',
                                text_color=self.KIND_COLOURS[place['kind']], font=(FAMILY + ' Bold', 10))
        if places and self.pin is None:
            # wait until the window has its size, or the map cannot fit the view
            self.after(500, self.fit_view, places)

    def fit_view(self, places):
        lats = [p['lat'] for p in places]
        lngs = [p['lng'] for p in places]
        if len(places) == 1:
            self.map.set_position(lats[0], lngs[0])
            self.map.set_zoom(13)
        else:
            pad = max(0.05, (max(lats) - min(lats)) * 0.15)
            self.map.fit_bounding_box((max(lats) + pad, min(lngs) - pad), (min(lats) - pad, max(lngs) + pad))

    def save(self):
        if self.pin is None:
            self.message.configure(text='Click on the map first to choose the place.', text_color=ROSE)
            return
        ok, data, status = self.api.add_my_place(self.name.get(), self.kind.get(), self.pin[0], self.pin[1])
        if not ok:
            self.message.configure(text=data, text_color=ROSE)
            return
        self.message.configure(text=data['message'], text_color=TEAL)
        set_text(self.name, '')
        self.pin = None
        self.pin_label.configure(text='No point chosen yet', text_color=GOLD)
        self.draw(data['places'])
        self.on_change()

    def remove(self, place):
        if not confirm('Remove place', 'Remove "%s"?' % place['name'], parent=self):
            return
        ok, data, status = self.api.delete_my_place(place['id'])
        if not ok:
            self.message.configure(text=data, text_color=ROSE)
            self.load()
            return
        self.message.configure(text=data['message'], text_color=TEAL)
        self.draw(data['places'])
        self.on_change()


# ---------------------------------------------------------------- the main screen
class MainView(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app, fg_color=BG, corner_radius=0)
        self.app = app
        self.api = app.api
        self.trip_id = None        # the open trip
        self.full = None           # its data: trip, activities, analysis
        self.activity_id = None    # the activity in the editor
        self.places = []           # the catalogue of places
        self.trip_buttons = {}
        self.day_values = []
        self.build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color='transparent')
        self.content.pack(side='left', fill='both', expand=True, padx=22, pady=(18, 10))
        self.build_header()
        self.build_kpis()
        self.build_tabs()
        self.status = ctk.CTkLabel(self.content, text='', font=font(13, 'medium'), anchor='w')
        self.status.pack(fill='x', pady=(8, 0))

    # ---- feedback
    def say(self, text, ok=True):
        self.status.configure(text='●  ' + text, text_color=TEAL if ok else ROSE)

    def check(self, result, popup=True):
        """Shows the error of a failed request. Returns the data, or None."""
        ok, data, status = result
        if ok:
            return data
        self.say(data, ok=False)
        if status == 401:
            self.app.show_login()
        elif popup:
            warn('Saudi Weekend Planner', data, parent=self.app)
        return None

    # ---- the dark sidebar with the trips
    def build_sidebar(self):
        side = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, width=290, border_width=1, border_color=LINE)
        side.pack(side='left', fill='y')
        side.pack_propagate(False)
        brand = ctk.CTkFrame(side, fg_color='transparent')
        brand.pack(fill='x', padx=22, pady=(24, 18))
        ctk.CTkLabel(brand, text='☀', font=font(30), text_color=GOLD).pack(side='left')
        names = ctk.CTkFrame(brand, fg_color='transparent')
        names.pack(side='left', padx=10)
        ctk.CTkLabel(names, text='Weekend Planner', font=font(20, 'heavy'), text_color=INK).pack(anchor='w')
        ctk.CTkLabel(names, text='Saudi Arabia', font=font(12, 'medium'), text_color=MUTED).pack(anchor='w')
        button(side, '+  New trip', self.new_trip, 'accent', 246, 42).pack(padx=22, pady=(0, 8))
        button(side, 'My places  (home, family, friends)', self.my_places, 'side', 246, 38).pack(
            padx=22, pady=(0, 18))
        ctk.CTkLabel(side, text='MY TRIPS', font=font(11, 'bold'), text_color=MUTED).pack(anchor='w', padx=24)
        self.trip_box = ctk.CTkScrollableFrame(side, fg_color='transparent', scrollbar_button_color=LINE,
                                               scrollbar_button_hover_color=MUTED)
        self.trip_box.pack(fill='both', expand=True, padx=12, pady=(6, 10))
        user = ctk.CTkFrame(side, fg_color=SOFTBG, corner_radius=12, border_width=1, border_color=LINE)
        user.pack(fill='x', padx=16, pady=(0, 18))
        self.user_label = ctk.CTkLabel(user, text='', font=font(14, 'bold'), text_color=INK)
        self.user_label.pack(side='left', padx=14, pady=10)
        ctk.CTkButton(user, text='Log out', command=self.logout, width=70, height=30, corner_radius=8,
                      fg_color=PANEL, hover_color=TINT, text_color=INK, border_width=1, border_color=LINE,
                      font=font(12, 'bold')).pack(side='right', padx=10)

    def trip_card(self, trip):
        """One trip in the sidebar: a button with its name, dates and status."""
        mark = {'Complete': '✓'}.get(trip['status'], '✖' if trip['conflicts'] else '•')
        colour = {'✓': TEAL, '✖': ROSE}.get(mark, GOLD)
        frame = ctk.CTkFrame(self.trip_box, fg_color='transparent', corner_radius=12, cursor='hand2')
        frame.pack(fill='x', pady=3)
        top = ctk.CTkLabel(frame, text=trip['name'], font=font(14, 'bold'), text_color=INK, anchor='w')
        top.pack(fill='x', padx=12, pady=(9, 0))
        line = ctk.CTkLabel(frame, text='%s  ·  %s  %s' % (day_name(trip['start_date']), trip['destinations'][:18],
                                                               mark),
                            font=font(12, 'medium'), text_color=colour, anchor='w')
        line.pack(fill='x', padx=12, pady=(0, 9))
        for widget in (frame, top, line):
            widget.bind('<Button-1>', lambda event, t=trip['id']: self.open_trip(t))
        self.trip_buttons[trip['id']] = frame

    def mark_selected(self):
        for trip_id, frame in self.trip_buttons.items():
            frame.configure(fg_color=TINT if trip_id == self.trip_id else 'transparent')

    # ---- the title of the trip and its buttons
    def build_header(self):
        head = ctk.CTkFrame(self.content, fg_color='transparent')
        head.pack(fill='x')
        # the buttons are packed first, so a long line under the title never squeezes them
        button(head, 'PDF', self.to_pdf, 'ghost', 70).pack(side='right', anchor='n')
        button(head, 'Excel', self.to_excel, 'ghost', 70).pack(side='right', padx=8, anchor='n')
        button(head, 'Delete', self.delete_trip, 'ghost', 80).pack(side='right', anchor='n')
        button(head, 'Edit trip', self.edit_trip, 'ghost', 90).pack(side='right', padx=8, anchor='n')
        button(head, 'Plan my weekend', self.plan_dialog, 'accent', 160).pack(side='right', anchor='n')
        texts = ctk.CTkFrame(head, fg_color='transparent')
        texts.pack(side='left', fill='x', expand=True)
        self.trip_title = ctk.CTkLabel(texts, text='Choose or create a trip', font=font(30, 'heavy'),
                                       text_color=INK, anchor='w')
        self.trip_title.pack(anchor='w')
        self.trip_line = ctk.CTkLabel(texts, text='', font=font(14, 'medium'), text_color=MUTED, anchor='w',
                                      justify='left')
        self.trip_line.pack(anchor='w')

    def build_kpis(self):
        row = ctk.CTkFrame(self.content, fg_color='transparent')
        row.pack(fill='x', pady=(14, 0))
        self.kpis = {}
        for number, (key, title) in enumerate([('total', 'Total cost'),
                                               ('left', 'Budget left'),
                                               ('km', 'Distance'),
                                               ('status', 'Plan status')]):
            row.columnconfigure(number, weight=1, uniform='kpi')
            tile = panel(row)
            tile.grid(row=0, column=number, sticky='we', padx=(0 if number == 0 else 12, 0))
            top = ctk.CTkFrame(tile, fg_color='transparent')
            top.pack(fill='x', padx=18, pady=(14, 0))
            caption(top, title.upper(), 11).pack(side='left')
            value = ctk.CTkLabel(tile, text='–', font=font(26, 'heavy'), text_color=INK, anchor='w')
            value.pack(fill='x', padx=18)
            note = caption(tile, '', 12)
            note.pack(fill='x', padx=18, pady=(0, 14))
            self.kpis[key] = (value, note)

    # ---- the four tabs
    def build_tabs(self):
        self.tabs = ctk.CTkTabview(self.content, fg_color=PANEL, corner_radius=16, border_width=1,
                                   border_color=LINE, segmented_button_fg_color=SOFTBG,
                                   segmented_button_selected_color=TINT, segmented_button_selected_hover_color=TINT2,
                                   segmented_button_unselected_color=SOFTBG,
                                   segmented_button_unselected_hover_color=LINE, text_color=INK, anchor='w')
        self.tabs.pack(fill='both', expand=True, pady=(14, 0))
        for name in ('Itinerary', 'Map', 'Budget', 'Checks'):
            self.tabs.add(name)
        self.tabs._segmented_button.configure(font=font(14, 'bold'), height=36)
        self.build_itinerary(self.tabs.tab('Itinerary'))
        self.build_map(self.tabs.tab('Map'))
        self.build_budget(self.tabs.tab('Budget'))
        self.build_checks(self.tabs.tab('Checks'))

    def build_itinerary(self, page):
        # the editor is packed first, so it keeps its width; the table takes the rest
        self.build_editor(page)
        left = ctk.CTkFrame(page, fg_color='white', corner_radius=0)
        left.pack(side='left', fill='both', expand=True, padx=(4, 10), pady=4)
        columns = ('time', 'travel', 'city', 'cost', 'check')
        self.tree = ttk.Treeview(left, columns=columns, show='tree headings', selectmode='browse',
                                 style='Plan.Treeview')
        self.tree.heading('#0', text='ACTIVITY', anchor='w')
        for column, title, width in [('time', 'TIME', 105), ('travel', 'GETTING THERE', 140), ('city', 'CITY', 72),
                                     ('cost', 'COST', 82), ('check', '', 30)]:
            self.tree.heading(column, text=title, anchor='w')
            self.tree.column(column, width=width, minwidth=30, anchor='w', stretch=True)
        self.tree.column('#0', width=200, minwidth=120)
        self.tree.column('check', anchor='center')
        self.tree.tag_configure('day', background='#F1F5F3', foreground=INK, font=(FAMILY + ' ExtraBold', 11))
        self.tree.tag_configure('conflict', foreground=ROSE)
        self.tree.tag_configure('warning', foreground=GOLD)
        self.tree.tag_configure('extra', foreground=MUTED)
        scroll = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview, style='Plan.Vertical.TScrollbar')
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self.on_activity_select)

    def build_editor(self, page):
        box = ctk.CTkFrame(page, fg_color=SOFTBG, corner_radius=14, width=340)
        box.pack(side='right', fill='y', padx=(0, 4), pady=4)
        box.pack_propagate(False)
        inner = ctk.CTkScrollableFrame(box, fg_color='transparent', width=320,
                                       scrollbar_button_color=LINE, scrollbar_button_hover_color=MUTED)
        inner.pack(fill='both', expand=True, padx=4, pady=4)
        self.editor_title = ctk.CTkLabel(inner, text='Add an activity', font=font(18, 'heavy'), text_color=INK,
                                         anchor='w')
        self.editor_title.grid(row=0, column=0, columnspan=3, sticky='we', padx=6, pady=(4, 2))

        def put(widget, row, column, span, text):
            caption(inner, text, 11).grid(row=row, column=column, columnspan=span, sticky='w', padx=6, pady=(6, 0))
            widget.grid(row=row + 1, column=column, columnspan=span, sticky='we', padx=6)
            return widget

        self.day_box = put(choice(inner, [], 190), 1, 0, 2, 'Day')
        self.time_entry = put(entry(inner, '16:00', 90), 1, 2, 1, 'Start')
        self.city_box = put(choice(inner, [], 300, command=lambda value: self.fill_places()), 3, 0, 3, 'City')
        self.place_box = put(choice(inner, [], 300, command=lambda value: self.on_place_chosen()), 5, 0, 3,
                             'Place from the catalogue')
        self.place_info = ctk.CTkLabel(inner, text='', font=font(12), text_color=MUTED, wraplength=290,
                                       justify='left', anchor='w')
        self.place_info.grid(row=7, column=0, columnspan=3, sticky='we', padx=6, pady=(4, 0))
        self.custom_name = put(entry(inner, 'only for your own activity', 190), 8, 0, 2, 'Own activity')
        self.custom_category = put(choice(inner, [], 90), 8, 2, 1, 'Category')
        self.duration = put(entry(inner, 'min', 90), 10, 0, 1, 'Minutes')
        self.cost = put(entry(inner, 'SAR', 90), 10, 1, 1, 'Per person')
        self.actual = put(entry(inner, 'SAR', 90), 10, 2, 1, 'Paid (total)')
        self.notes = put(entry(inner, 'optional', 300), 12, 0, 3, 'Notes')
        button(inner, 'Add', self.add_activity, 'teal', 90).grid(row=14, column=0, sticky='we', padx=6, pady=(14, 0))
        button(inner, 'Save', self.save_activity, 'dark', 90).grid(row=14, column=1, sticky='we', padx=6, pady=(14, 0))
        button(inner, 'Remove', self.remove_activity, 'danger', 90).grid(row=14, column=2, sticky='we', padx=6,
                                                                       pady=(14, 0))
        button(inner, 'Clear the form', self.clear_editor, 'ghost').grid(row=15, column=0, columnspan=3, sticky='we',
                                                                        padx=6, pady=(8, 0))
        self.issue_label = ctk.CTkLabel(inner, text='', font=font(12, 'medium'), text_color=ROSE, wraplength=290,
                                        justify='left', anchor='w')
        self.issue_label.grid(row=16, column=0, columnspan=3, sticky='we', padx=6, pady=(10, 4))

    def build_map(self, page):
        bar = ctk.CTkFrame(page, fg_color='transparent')
        bar.pack(fill='x', padx=4, pady=(0, 8))
        self.map_day = choice(bar, ['All days'], 200, command=lambda value: self.draw_map())
        self.map_day.pack(side='left')
        self.map_legend = ctk.CTkFrame(bar, fg_color='transparent')
        self.map_legend.pack(side='left', padx=14)
        self.map_style = ctk.CTkSegmentedButton(bar, values=list(MAP_STYLES), command=self.set_map_style,
                                                font=font(13, 'bold'), height=34, selected_color=TINT, selected_hover_color=TINT2, unselected_color=SOFTBG, unselected_hover_color=LINE, fg_color=SOFTBG, text_color=INK)
        self.map_style.pack(side='right')
        button(bar, 'Open in Google Maps', self.open_google_maps, 'ghost', 170, 34).pack(side='right',
                                                                                                padx=10)
        holder = ctk.CTkFrame(page, fg_color=LINE, corner_radius=14)
        holder.pack(fill='both', expand=True, padx=4, pady=(0, 4))
        self.map = tkintermapview.TkinterMapView(holder, corner_radius=12)
        self.map.pack(fill='both', expand=True, padx=1, pady=1)
        self.map.set_position(23.8859, 45.0792)
        self.map.set_zoom(5)
        tk.Label(self.map, text='Tiles © Esri  ·  click a pin to see the activity', font=(FAMILY, 9),
                 bg='white', fg=MUTED).place(relx=1.0, rely=1.0, anchor='se')
        self.map_style.set('Light')
        self.set_map_style('Light')

    def open_google_maps(self):
        """Opens the route of the chosen day in Google Maps (live traffic, petrol stations, turn by turn)."""
        if not self.full:
            return
        days = self.full['analysis']['days']
        values = self.map_day.cget('values')
        index = max(0, values.index(self.map_day.get()) - 1) if self.map_day.get() in values else 0
        day = days[index]
        if not day['items']:
            notice('Google Maps', 'This day has no activities yet.', parent=self.app)
            return
        # the day starts where the first move starts (home, your place or the hotel)
        start = day['items'][0]['travel']['geometry'][0]
        stops = [(i['activity']['lat'], i['activity']['lng']) for i in day['items']]
        if index == len(days) - 1:
            end = self.full['analysis']['end']
            stops.append((end['lat'], end['lng']))
        end = stops.pop()
        # Google Maps directions link: no key is needed; it allows up to 9 stops in between
        params = {'api': '1', 'origin': '%f,%f' % tuple(start), 'destination': '%f,%f' % end,
                  'travelmode': 'driving'}
        if stops:
            params['waypoints'] = '|'.join('%f,%f' % p for p in stops[:9])
        webbrowser.open('https://www.google.com/maps/dir/?' + urlencode(params))
        self.say('Opened day %d in Google Maps.' % (index + 1))

    def set_map_style(self, name):
        # each style is a tile server; Light and Satellite add a layer of labels on top
        base, labels = MAP_STYLES[name]
        # the label layer is set first, because set_tile_server() clears the cache and redraws
        self.map.overlay_tile_server = labels
        self.map.set_tile_server(base, max_zoom=19)

    def build_budget(self, page):
        self.figure = Figure(figsize=(9, 4), dpi=100, facecolor='white')
        self.canvas = FigureCanvasTkAgg(self.figure, master=page)
        self.canvas.get_tk_widget().pack(fill='both', expand=True, padx=4, pady=4)
        self.budget_line = caption(page, '', 13, INK)
        self.budget_line.pack(fill='x', padx=10, pady=(0, 6))

    def build_checks(self, page):
        self.banner = ctk.CTkLabel(page, text='', font=font(18, 'heavy'), corner_radius=12, anchor='w', height=54)
        self.banner.pack(fill='x', padx=4, pady=(0, 10))
        self.check_rows = ctk.CTkFrame(page, fg_color='transparent')
        self.check_rows.pack(fill='x', padx=4)
        ctk.CTkLabel(page, text='What needs attention', font=font(16, 'heavy'), text_color=INK,
                     anchor='w').pack(fill='x', padx=8, pady=(12, 4))
        self.issue_text = ctk.CTkTextbox(page, font=font(13), fg_color=SOFTBG, text_color=INK, corner_radius=12,
                                         wrap='word')
        self.issue_text.pack(fill='both', expand=True, padx=4, pady=(0, 4))

    # ---------------------------------------------------------------- loading
    def start(self):
        """Called after login: the user, the lists, the catalogue and the trips."""
        self.user_label.configure(text=self.api.username or '')
        data = self.check(self.api.options(), popup=False)
        if data:
            self.cities = data['cities']
            self.centres = data['centres']
            self.categories = data['categories']
            self.ai_on = data['ai']
            self.custom_category.configure(values=self.categories)
        data = self.check(self.api.places(), popup=False)
        if data:
            self.places = data['places']
        self.load_trips()

    def load_trips(self, select=None):
        data = self.check(self.api.trips(), popup=False)
        if data is None:
            return
        for frame in self.trip_buttons.values():
            frame.destroy()
        self.trip_buttons = {}
        for trip in data['trips']:
            self.trip_card(trip)
        if not data['trips']:
            self.show_empty()
            self.say('No trips yet. Press + New trip to plan your first weekend.')
            return
        target = select or self.trip_id or data['trips'][0]['id']
        if target not in self.trip_buttons:
            target = data['trips'][0]['id']
        if target != self.trip_id or self.full is None:
            self.open_trip(target)
        self.mark_selected()

    def open_trip(self, trip_id):
        data = self.check(self.api.trip(trip_id))
        if data is None:
            self.load_trips()
            return
        self.trip_id = trip_id
        self.activity_id = None
        self.show(data)
        self.mark_selected()

    def show_empty(self):
        self.trip_id = None
        self.full = None
        self.trip_title.configure(text='Create your first trip')
        self.trip_line.configure(text='Press  + New trip  on the left. Then add places, or press Plan my weekend.')
        self.tree.delete(*self.tree.get_children())
        for value, note in self.kpis.values():
            value.configure(text='–', text_color=INK)
            note.configure(text='')

    def show(self, data):
        """Draws one trip in every part of the screen."""
        self.full = data
        trip, analysis = data['trip'], data['analysis']
        budget = analysis['budget']
        self.trip_title.configure(text=trip['name'])
        # line 1: when, where and who; line 2: how the group moves and where it sleeps for free
        self.trip_line.configure(text='%s → %s  ·  %s → %s  ·  %d people'
                                 % (day_name(trip['start_date']), day_name(trip['end_date']), trip['home_city'],
                                    trip.get('end_city') or trip['home_city'], trip['people'])
                                 + '\n%s  ·  car %s km/L, petrol %s'
                                 % ('flying far legs' if trip['transport'] == 'flight' else 'driving',
                                    trip.get('car_kmpl') or 12, trip.get('fuel') or '91')
                                 + ('  ·  free nights in ' + trip['stays'] if trip.get('stays') else ''))
        value, note = self.kpis['total']
        value.configure(text=money(budget['total']), text_color=INK)
        note.configure(text='%s per person' % money(budget['per_person']))
        value, note = self.kpis['left']
        value.configure(text=money(budget['remaining']), text_color=TEAL if budget['remaining'] >= 0 else ROSE)
        note.configure(text='of a %s budget' % money(budget['limit']))
        value, note = self.kpis['km']
        value.configure(text='{:,.0f} km'.format(analysis['total_km']), text_color=INK)
        note.configure(text='with the way to the end')
        value, note = self.kpis['status']
        value.configure(text=analysis['status'], text_color=TEAL if analysis['complete'] else GOLD)
        passed = sum(1 for c in analysis['checks'] if c['ok'])
        note.configure(text='%d of %d checks passed' % (passed, len(analysis['checks'])))

        # the lists of the editor and the map
        dates = [d['date'] for d in analysis['days']]
        self.day_values = [day_name(d) + '  ' + d for d in dates]
        self.day_box.configure(values=self.day_values)
        self.trip_cities = list(dict.fromkeys([trip['home_city']] +
                                              [c.strip() for c in trip['destinations'].split(',')]))
        self.city_box.configure(values=self.trip_cities)
        self.map_day.configure(values=['All days'] + ['Day %d  ·  %s' % (n + 1, day_name(d))
                                                      for n, d in enumerate(dates)])
        self.map_day.set('All days')
        self.draw_itinerary()
        self.draw_map()
        self.draw_budget()
        self.draw_checks()
        if not self.activity_id:
            self.clear_editor()

    # ---------------------------------------------------------------- the itinerary
    def draw_itinerary(self):
        self.tree.delete(*self.tree.get_children())
        analysis = self.full['analysis']
        people = self.full['trip']['people']
        icons = {'car': 'Car', 'flight': 'Flight', 'walk': 'Walk'}
        for number, day in enumerate(analysis['days']):
            cities = ', '.join(dict.fromkeys(i['activity']['city'] for i in day['items']))
            bad = sum(1 for i in day['items'] for x in i['issues'] if x['level'] == 'conflict')
            parent = self.tree.insert('', 'end', iid='day-' + day['date'], open=True, tags=('day',),
                                      text='  Day %d  \u00b7  %s' % (number + 1, day_name(day['date'])),
                                      values=('', '' if day['items'] else 'No activities yet', cities,
                                              money(analysis['by_day'][day['date']]), '\u2716' if bad else ''))
            for item in day['items']:
                a, move = item['activity'], item['travel']
                levels = [x['level'] for x in item['issues']]
                tag = 'conflict' if 'conflict' in levels else ('warning' if levels else '')
                # ≈ marks an estimate (no road service); without it the time is from the real road
                travel = ('%s  %s%d min  ·  %s km' % (icons[move['mode']],
                                                      '≈' if move.get('source') == 'estimate' else '',
                                                      move['minutes'],
                                                      ('%.1f' if move['km'] < 10 else '%.0f') % move['km'])
                          if move['minutes'] else 'same place')
                mark = '✖' if tag == 'conflict' else ('⚠' if tag == 'warning' else '✓')
                self.tree.insert(parent, 'end', iid='act-%d' % a['id'], tags=(tag,) if tag else (),
                                 text='   ' + a['name'],
                                 values=(a['start_time'] + ' – ' + item['end'], travel, a['city'],
                                         money(a['cost_per_person'] * people), mark))
            if day['hotel']:
                if day['hotel'].get('own'):
                    night = '   Night at %s  (free)' % day['hotel'].get('place', 'your place in ' +
                                                                                day['hotel']['city'])
                else:
                    night = '   Hotel in %s  (%d room(s))' % (day['hotel']['city'], day['hotel']['rooms'])
                self.tree.insert(parent, 'end', iid='hotel-' + day['date'], tags=('extra',), text=night,
                                 values=('night', '', day['hotel']['city'], money(day['hotel']['cost']), ''))
        back = analysis['return_leg']
        if back and analysis['days'] and back['km'] > 0:
            late = back['arrive_minutes'] > 24 * 60
            self.tree.insert('day-' + analysis['days'][-1]['date'], 'end', iid='return',
                             tags=('conflict',) if late else ('extra',),
                             text='   To the end: ' + analysis['end']['name'],
                             values=(back['leave'] + ' – ' + back['arrive'],
                                     '%s  %d min  ·  %.0f km' % (icons[back['mode']], back['minutes'], back['km']),
                                     self.full['trip'].get('end_city') or self.full['trip']['home_city'],
                                     money(back['cost']), '✖' if late else '✓'))

    def on_activity_select(self, event=None):
        chosen = self.tree.selection()
        if not chosen or not chosen[0].startswith('act-'):
            return
        activity_id = int(chosen[0][4:])
        for day in self.full['analysis']['days']:
            for item in day['items']:
                if item['activity']['id'] == activity_id:
                    self.fill_editor(item)
                    return

    # ---------------------------------------------------------------- the editor
    def fill_places(self, keep=None):
        city = self.city_box.get()
        names = [p['name'] for p in self.places if p['city'] == city]
        self.place_box.configure(values=names + [CUSTOM])
        self.place_box.set(keep or (names[0] if names else CUSTOM))
        if keep is None:
            self.on_place_chosen()

    def chosen_place(self):
        for place in self.places:
            if place['name'] == self.place_box.get() and place['city'] == self.city_box.get():
                return place
        return None

    def on_place_chosen(self):
        place = self.chosen_place()
        if place is None:
            self.place_info.configure(text='Type your own activity below. It is placed at the city centre.')
            return
        self.place_info.configure(text='%s\nOpen %s–%s  ·  about %d min  ·  %d SAR per person'
                                  % (place['description'], place['opens'], place['closes'],
                                     place['duration_min'], place['cost']))
        set_text(self.duration, place['duration_min'])
        set_text(self.cost, place['cost'])

    def fill_editor(self, item):
        a = item['activity']
        self.activity_id = a['id']
        self.editor_title.configure(text='Edit activity')
        self.day_box.set(day_name(a['day']) + '  ' + a['day'])
        set_text(self.time_entry, a['start_time'])
        self.city_box.set(a['city'])
        self.fill_places(keep=a['name'] if a['place_id'] else CUSTOM)
        place = self.chosen_place()
        self.place_info.configure(text=place['description'] if place else 'Your own activity')
        set_text(self.custom_name, '' if a['place_id'] else a['name'])
        self.custom_category.set('' if a['place_id'] else a['category'])
        set_text(self.duration, a['duration_min'])
        set_text(self.cost, a['cost_per_person'])
        set_text(self.actual, a['actual_cost'])
        set_text(self.notes, a['notes'])
        lines = ['From %s: leave %s, arrive %s.' % (item['from'], item['leave_at'], item['arrive'])]
        lines += [('✖ ' if x['level'] == 'conflict' else '⚠ ') + x['text'] for x in item['issues']]
        self.issue_label.configure(text='\n'.join(lines), text_color=ROSE if item['issues'] else TEAL)

    def clear_editor(self):
        self.activity_id = None
        self.editor_title.configure(text='Add an activity')
        for widget in (self.time_entry, self.custom_name, self.duration, self.cost, self.actual, self.notes):
            set_text(widget, '')
        set_text(self.time_entry, '16:00')
        if self.day_values:
            self.day_box.set(self.day_values[0])
        if getattr(self, 'trip_cities', None):
            self.city_box.set(self.trip_cities[-1])
            self.fill_places()
        self.custom_category.set('')
        self.issue_label.configure(text='')
        self.tree.selection_remove(self.tree.selection())

    def editor_values(self):
        place = self.chosen_place()
        values = {'day': self.day_box.get().split('  ')[-1], 'start_time': self.time_entry.get().strip(),
                  'duration_min': self.duration.get(), 'cost_per_person': self.cost.get(),
                  'actual_cost': self.actual.get(), 'notes': self.notes.get()}
        if place:
            values['place_id'] = place['id']
        else:
            values.update({'name': self.custom_name.get(), 'city': self.city_box.get(),
                           'category': self.custom_category.get()})
        return values

    def after_change(self, data):
        self.show(data)
        self.say(data['message'])
        self.load_trips(select=self.trip_id)

    def add_activity(self):
        if self.trip_id is None:
            notice('Add', 'Create or choose a trip first.', parent=self.app)
            return
        data = self.check(self.api.add_activity(self.trip_id, self.editor_values()))
        if data:
            self.activity_id = None
            self.after_change(data)

    def save_activity(self):
        if self.activity_id is None:
            notice('Save', 'Choose an activity in the itinerary first.', parent=self.app)
            return
        result = self.api.edit_activity(self.activity_id, self.editor_values())
        data = self.check(result)
        if data:
            self.after_change(data)
        elif result[2] == 404:
            self.activity_id = None
            self.open_trip(self.trip_id)

    def remove_activity(self):
        if self.activity_id is None:
            notice('Remove', 'Choose an activity in the itinerary first.', parent=self.app)
            return
        if not confirm('Remove', 'Remove this activity from the trip?', parent=self.app):
            return
        result = self.api.delete_activity(self.activity_id)
        self.activity_id = None
        data = self.check(result)
        if data:
            self.after_change(data)
        else:
            self.open_trip(self.trip_id)

    # ---------------------------------------------------------------- trips
    def my_places(self):
        PlacesDialog(self.app, self.api, self.places_changed)

    def places_changed(self):
        # a new or removed home changes where the trips start and sleep
        if self.trip_id is not None:
            self.open_trip(self.trip_id)

    def new_trip(self):
        TripDialog(self.app, self.cities, self.save_new_trip)

    def save_new_trip(self, values):
        data = self.check(self.api.add_trip(values))
        if data is None:
            return False
        self.trip_id = data['trip']['id']
        self.activity_id = None
        self.after_change(data)
        return True

    def edit_trip(self):
        if self.full is None:
            notice('Edit', 'Choose a trip first.', parent=self.app)
            return
        TripDialog(self.app, self.cities, self.save_edited_trip, trip=self.full['trip'])

    def save_edited_trip(self, values):
        result = self.api.edit_trip(self.trip_id, values)
        data = self.check(result)
        if data is None:
            if result[2] == 404:
                self.trip_id = None
                self.load_trips()
                return True
            return False
        self.after_change(data)
        return True

    def delete_trip(self):
        if self.full is None:
            notice('Delete', 'Choose a trip first.', parent=self.app)
            return
        if not confirm('Delete trip', 'Delete "%s" and all its activities?' % self.full['trip']['name'],
                                   parent=self.app):
            self.say('Nothing was deleted.')
            return
        data = self.check(self.api.delete_trip(self.trip_id))
        self.show_empty()
        if data:
            self.say(data['message'])
        self.load_trips()

    # ---------------------------------------------------------------- AI planning in a thread
    def plan_dialog(self):
        if self.trip_id is None:
            notice('Plan', 'Create or choose a trip first.', parent=self.app)
            return
        PlanDialog(self.app, self.categories, self.ai_on, self.run_plan)

    def run_plan(self, interests, pace, engine):
        """The request runs in a thread, so the window keeps moving while Gemini thinks."""
        self.say('Planning your weekend... Gemini can take up to a minute.')
        self.progress = ctk.CTkProgressBar(self.content, mode='indeterminate', progress_color=ACCENT,
                                           fg_color=LINE, height=6)
        self.progress.place(relx=1.0, rely=1.0, anchor='se', relwidth=0.3, y=-12)
        self.progress.start()
        results = queue.Queue()
        trip_id = self.trip_id
        worker = threading.Thread(target=lambda: results.put(self.api.autoplan(trip_id, interests, pace, engine)),
                                  daemon=True)
        worker.start()
        self.wait_for_plan(results)

    def wait_for_plan(self, results):
        try:
            result = results.get_nowait()
        except queue.Empty:
            # not ready yet: look again in 200 ms
            self.after(200, self.wait_for_plan, results)
            return
        self.progress.destroy()
        data = self.check(result)
        if data:
            self.activity_id = None
            self.after_change(data)
            notice('Plan ready', data['message'] + '\n\n' + data['summary'] +
                                '\n\nStatus: ' + data['analysis']['status'], parent=self.app)

    # ---------------------------------------------------------------- the map
    def draw_map(self):
        self.map.delete_all_marker()
        self.map.delete_all_path()
        for widget in self.map_legend.winfo_children():
            widget.destroy()
        if not self.full:
            return
        analysis = self.full['analysis']
        values = self.map_day.cget('values')
        choice_index = values.index(self.map_day.get()) if self.map_day.get() in values else 0
        # home: the saved home of the user, or the city centre
        home = analysis['home']
        self.map.set_marker(home['lat'], home['lng'], text=home['name'][:18], marker_color_circle='white',
                            marker_color_outside=INK, text_color=INK, font=(FAMILY + ' ExtraBold', 11))
        # the end of the trip, when it is not the start
        end = analysis['end']
        if (end['lat'], end['lng']) != (home['lat'], home['lng']):
            self.map.set_marker(end['lat'], end['lng'], text='End: ' + end['name'][:16], marker_color_circle='white',
                                marker_color_outside=INK, text_color=INK, font=(FAMILY + ' ExtraBold', 11))
        # the free nights (family, friends) and the hotels
        for day in analysis['days']:
            night = day['hotel']
            if night and 'lat' in night:
                self.map.set_marker(night['lat'], night['lng'],
                                    text=night.get('place', 'Hotel')[:18] if night['own'] else 'Hotel',
                                    marker_color_circle='white', marker_color_outside=TEAL if night['own'] else GOLD,
                                    text_color=TEAL if night['own'] else GOLD, font=(FAMILY + ' Bold', 10))
        points = []
        for number, day in enumerate(analysis['days']):
            if choice_index > 0 and number != choice_index - 1:
                continue
            colour = DAY_COLOURS[number % len(DAY_COLOURS)]
            path = []
            route = []
            for order, item in enumerate(day['items']):
                a = item['activity']
                bad = any(x['level'] == 'conflict' for x in item['issues'])
                # the pin shows day.order; a click writes the name and the time in the status line
                text = '%d.%d' % (number + 1, order + 1)
                info = '%s  %s, %s to %s' % (text, a['name'], a['start_time'], item['end'])
                self.map.set_marker(a['lat'], a['lng'], text=text, data=info,
                                    command=lambda marker: self.say(marker.data),
                                    marker_color_circle='white', marker_color_outside=ROSE if bad else colour,
                                    text_color=ROSE if bad else colour, font=(FAMILY + ' ExtraBold', 11))
                path.append((a['lat'], a['lng']))
                # the shape of the road to this activity (from OSRM), or a straight line
                route += [tuple(p) for p in item['travel']['geometry']]
            if number == len(analysis['days']) - 1 and analysis['return_leg']:
                route += [tuple(p) for p in analysis['return_leg']['geometry']]
            if len(route) > 1:
                self.map.set_path(route, color=colour, width=4)
            points += route or path
            ctk.CTkLabel(self.map_legend, text='● Day %d' % (number + 1), text_color=colour,
                         font=font(13, 'bold')).pack(side='left', padx=8)
        if choice_index == 0:
            points.append((home['lat'], home['lng']))
        if len(points) > 1:
            lats = [p[0] for p in points]
            lngs = [p[1] for p in points]
            pad = max(0.02, (max(lats) - min(lats)) * 0.12)
            self.map.fit_bounding_box((max(lats) + pad, min(lngs) - pad), (min(lats) - pad, max(lngs) + pad))
        else:
            self.map.set_position(home['lat'], home['lng'])
            self.map.set_zoom(11)

    # ---------------------------------------------------------------- the budget charts
    def draw_budget(self):
        budget = self.full['analysis']['budget']
        analysis = self.full['analysis']
        self.figure.clear()
        text = {'fontfamily': FAMILY, 'color': INK}

        # 1. where the money goes
        ax = self.figure.add_subplot(1, 3, 1)
        parts = [(name, budget[key]) for name, key in [('Activities', 'activities'), ('Fuel', 'fuel'),
                                                        ('Flights', 'flights'), ('Hotels', 'hotels')] if budget[key] > 0]
        colours = {'Activities': ACCENT, 'Fuel': '#3D6FA8', 'Flights': '#8A5BA0', 'Hotels': GOLD}
        if parts:
            ax.pie([v for _, v in parts], labels=['%s\n%s' % (n, money(v)) for n, v in parts],
                   colors=[colours[n] for n, _ in parts], startangle=90, counterclock=False,
                   wedgeprops={'width': 0.34, 'edgecolor': 'white', 'linewidth': 2},
                   textprops={'fontsize': 9, 'fontfamily': FAMILY, 'color': INK})
            ax.text(0, 0, money(budget['total']), ha='center', va='center', fontsize=12, fontweight='bold', **text)
        ax.set_title('Where the money goes', fontsize=12, fontweight='bold', loc='left', **text)

        # 2. the cost of each day
        ax = self.figure.add_subplot(1, 3, 2)
        days = list(analysis['by_day'].values())
        bars = ax.bar(['Day %d' % (n + 1) for n in range(len(days))], days, color=TEAL, width=0.5)
        for bar, value in zip(bars, days):
            ax.text(bar.get_x() + bar.get_width() / 2, value, '{:,.0f}'.format(value), ha='center', va='bottom',
                    fontsize=9, **text)
        ax.set_title('Cost per day (SAR)', fontsize=12, fontweight='bold', loc='left', **text)
        self.tidy(ax)

        # 3. the budget, the plan and what was paid
        ax = self.figure.add_subplot(1, 3, 3)
        values = [budget['limit'], budget['total'], budget['actual']]
        bars = ax.bar(['Budget', 'Planned', 'Paid so far'], values,
                      color=['#CFCBC2', ROSE if budget['total'] > budget['limit'] else ACCENT, GOLD], width=0.5)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value, '{:,.0f}'.format(value), ha='center', va='bottom',
                    fontsize=9, **text)
        ax.set_title('Budget vs plan vs actual', fontsize=12, fontweight='bold', loc='left', **text)
        self.tidy(ax)
        self.figure.tight_layout(pad=2)
        self.canvas.draw()
        self.budget_line.configure(text='Activities %s   ·   fuel %s   ·   flights %s   ·   hotels %s'
                                        '   ·   paid so far %s (%d activities)'
                                   % (money(budget['activities']), money(budget['fuel']), money(budget['flights']),
                                      money(budget['hotels']), money(budget['actual']), budget['actual_count']))

    def tidy(self, ax):
        for side in ('top', 'right', 'left'):
            ax.spines[side].set_visible(False)
        ax.spines['bottom'].set_color(LINE)
        ax.tick_params(colors=MUTED, labelsize=9, length=0)
        for tick in ax.get_xticklabels() + ax.get_yticklabels():
            tick.set_fontfamily(FAMILY)
        ax.grid(axis='y', color='#EFEAE0', linewidth=1)
        ax.set_axisbelow(True)

    # ---------------------------------------------------------------- the checks
    def draw_checks(self):
        analysis = self.full['analysis']
        if analysis['complete']:
            self.banner.configure(text='    ✓   This plan is complete: every check passes.', fg_color='#E1F2EC',
                                  text_color=TEAL)
        else:
            failed = sum(1 for c in analysis['checks'] if not c['ok'])
            self.banner.configure(text='    •   In progress: %d check(s) still fail.' % failed,
                                  fg_color='#F8EEDC', text_color=GOLD)
        for widget in self.check_rows.winfo_children():
            widget.destroy()
        for check in analysis['checks']:
            row = ctk.CTkFrame(self.check_rows, fg_color=SOFTBG, corner_radius=10)
            row.pack(fill='x', pady=3)
            ctk.CTkLabel(row, text='✓' if check['ok'] else '✖', font=font(16, 'heavy'), width=40,
                         text_color=TEAL if check['ok'] else ROSE).pack(side='left', padx=(8, 0), pady=6)
            ctk.CTkLabel(row, text=check['name'], font=font(14, 'bold'), text_color=INK, width=280,
                         anchor='w').pack(side='left')
            caption(row, check['detail'], 13).pack(side='left')
        self.issue_text.configure(state='normal')
        self.issue_text.delete('1.0', 'end')
        lines = []
        for number, day in enumerate(analysis['days']):
            for item in day['items']:
                for issue in item['issues']:
                    lines.append('%s   Day %d, %s  %s:  %s' % ('✖' if issue['level'] == 'conflict' else '⚠',
                                                              number + 1, item['activity']['start_time'],
                                                              item['activity']['name'], issue['text']))
        self.issue_text.insert('1.0', '\n'.join(lines) or 'Nothing. Every activity fits its time and opening hours.')
        self.issue_text.configure(state='disabled')

    # ---------------------------------------------------------------- export and logout
    def export(self, kind, writer):
        if self.full is None:
            notice('Export', 'Choose a trip first.', parent=self.app)
            return
        name = self.full['trip']['name'].replace(' ', '_')
        path = filedialog.asksaveasfilename(parent=self.app, defaultextension='.' + kind, initialfile=name,
                                            filetypes=[(kind.upper(), '*.' + kind)])
        if not path:
            return
        try:
            writer(self.full, path)
        except PermissionError:
            warn('Export', 'The file is open in another program. Close it and try again.',
                                   parent=self.app)
            return
        except OSError as problem:
            warn('Export', 'Could not save the file: %s' % problem, parent=self.app)
            return
        self.say('Saved ' + path)

    def to_excel(self):
        self.export('xlsx', export_excel)

    def to_pdf(self):
        self.export('pdf', export_pdf)

    def logout(self):
        self.api.logout()
        self.app.show_login()


# ---------------------------------------------------------------- the application
class App(ctk.CTk):
    """The window. It shows the login screen, then the main screen."""

    def __init__(self):
        super().__init__()
        self.title('Saudi Weekend Planner')
        self.configure(fg_color=BG)
        # as big as the screen allows
        width = min(1440, self.winfo_screenwidth() - 60)
        height = min(880, self.winfo_screenheight() - 100)
        self.geometry('%dx%d+20+10' % (width, height))
        self.minsize(1150, 680)
        style_tables(self)
        self.api = ApiClient()
        self.view = None
        self.show_login()

    def switch(self, view):
        if self.view is not None:
            self.view.destroy()
        self.view = view
        view.pack(fill='both', expand=True)

    def show_login(self):
        self.api.token = None
        self.switch(LoginView(self))

    def show_main(self):
        main = MainView(self)
        self.switch(main)
        main.start()


if __name__ == '__main__':
    App().mainloop()
