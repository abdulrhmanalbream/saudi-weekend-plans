# Saudi Weekend Planner: export a trip to Excel or PDF
from datetime import date

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

NIGHT = '1E2A2F'
AMBER = 'E9A15B'
SAND = 'F6F1E7'


def day_title(day):
    # '2026-12-03' -> 'Thu 03 Dec 2026'
    return date.fromisoformat(day).strftime('%a %d %b %Y')


def rows_of(full):
    """The itinerary as plain rows: day, time, activity, city, travel, group cost, notes."""
    rows = []
    for day in full['analysis']['days']:
        for item in day['items']:
            a, t = item['activity'], item['travel']
            travel = '%s %d min, %.1f km' % (t['mode'], t['minutes'], t['km']) if t['minutes'] else '-'
            issues = '; '.join(i['text'] for i in item['issues'])
            rows.append([day_title(day['date']), a['start_time'] + ' - ' + item['end'], a['name'], a['city'],
                         a['category'], travel, a['cost_per_person'] * full['trip']['people'], issues or 'OK'])
        if day['hotel']:
            rows.append([day_title(day['date']), 'night', 'Hotel in ' + day['hotel']['city'], day['hotel']['city'],
                         'Hotel', '%d room(s)' % day['hotel']['rooms'], day['hotel']['cost'], 'OK'])
    back = full['analysis']['return_leg']
    if back:
        rows.append(['', back['leave'] + ' - ' + back['arrive'], 'Back home', full['trip']['home_city'], 'Travel',
                     '%s %d min, %.1f km' % (back['mode'], back['minutes'], back['km']), back['cost'], ''])
    return rows


def export_excel(full, path):
    trip, budget = full['trip'], full['analysis']['budget']
    book = Workbook()
    sheet = book.active
    sheet.title = 'Itinerary'
    sheet.append([trip['name']])
    sheet['A1'].font = Font(size=16, bold=True, color=NIGHT)
    sheet.append(['%s to %s  |  %d people  |  %s  |  from %s' % (trip['start_date'], trip['end_date'], trip['people'],
                                                               trip['transport'], trip['home_city'])])
    sheet.append([])
    header = ['Day', 'Time', 'Activity', 'City', 'Category', 'Travel to it', 'Cost (SAR, group)', 'Checks']
    sheet.append(header)
    for cell in sheet[4]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor=NIGHT)
    for row in rows_of(full):
        sheet.append(row)
    for column, width in zip('ABCDEFGH', [18, 16, 32, 10, 13, 22, 17, 50]):
        sheet.column_dimensions[column].width = width

    money = book.create_sheet('Budget')
    money.append(['Part', 'SAR'])
    for part in ('activities', 'fuel', 'flights', 'hotels', 'total', 'limit', 'remaining', 'per_person', 'actual'):
        money.append([part.replace('_', ' ').title(), budget[part]])
    for cell in money[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor=NIGHT)
    money.column_dimensions['A'].width = 16
    money.column_dimensions['B'].width = 14

    checks = book.create_sheet('Checks')
    checks.append(['Check', 'Result', 'Detail'])
    for check in full['analysis']['checks']:
        checks.append([check['name'], 'PASS' if check['ok'] else 'FAIL', check['detail']])
    checks.column_dimensions['A'].width = 34
    checks.column_dimensions['C'].width = 50
    for row in sheet.iter_rows(min_row=5):
        for cell in row:
            cell.alignment = Alignment(vertical='top', wrap_text=True)
    book.save(path)


def latin(text):
    # the built-in PDF fonts only have Latin-1 letters
    return str(text).replace('’', "'").replace('–', '-').replace('·', '-') \
        .encode('latin-1', 'replace').decode('latin-1')


def export_pdf(full, path):
    trip, analysis = full['trip'], full['analysis']
    budget = analysis['budget']
    pdf = FPDF(orientation='L', format='A4')
    pdf.set_auto_page_break(True, margin=12)
    pdf.add_page()
    # the title band
    pdf.set_fill_color(0x1E, 0x2A, 0x2F)
    pdf.rect(0, 0, 297, 30, 'F')
    pdf.set_text_color(0xF6, 0xF1, 0xE7)
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_xy(12, 7)
    pdf.cell(0, 9, latin(trip['name']))
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(0xE9, 0xA1, 0x5B)
    pdf.set_xy(12, 18)
    pdf.cell(0, 6, latin('%s to %s  |  %d people  |  %s  |  from %s  |  status: %s'
                         % (trip['start_date'], trip['end_date'], trip['people'], trip['transport'],
                            trip['home_city'], analysis['status'])))
    # the budget line
    pdf.set_text_color(0x1E, 0x2A, 0x2F)
    pdf.set_xy(12, 36)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, latin('Total %.0f SAR of %.0f  |  activities %.0f  |  fuel %.0f  |  flights %.0f  |  hotels %.0f  '
                         '|  %.0f per person  |  %.0f km'
                         % (budget['total'], budget['limit'], budget['activities'], budget['fuel'],
                            budget['flights'], budget['hotels'], budget['per_person'], analysis['total_km'])))
    pdf.ln(10)
    # the table
    widths = [30, 26, 62, 20, 24, 38, 22, 51]
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(0x1E, 0x2A, 0x2F)
    pdf.set_text_color(255, 255, 255)
    for title, width in zip(['Day', 'Time', 'Activity', 'City', 'Category', 'Travel', 'SAR', 'Checks'], widths):
        pdf.cell(width, 8, title, border=0, fill=True)
    pdf.ln()
    pdf.set_font('Helvetica', '', 8.5)
    pdf.set_text_color(0x1E, 0x2A, 0x2F)
    for number, row in enumerate(rows_of(full)):
        pdf.set_fill_color(0xFA, 0xF6, 0xEE) if number % 2 else pdf.set_fill_color(255, 255, 255)
        row[6] = '%.0f' % row[6]
        for value, width in zip(row, widths):
            text = latin(value)
            while pdf.get_string_width(text) > width - 2 and len(text) > 3:
                text = text[:-4] + '...'
            pdf.cell(width, 7, text, fill=True)
        pdf.ln()
    pdf.ln(4)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 7, 'Checks')
    pdf.ln()
    pdf.set_font('Helvetica', '', 9)
    for check in analysis['checks']:
        pdf.cell(0, 6, latin(('PASS  ' if check['ok'] else 'FAIL  ') + check['name'] + ': ' + check['detail']))
        pdf.ln()
    pdf.output(path)
