import tkinter as tk
from tkinter import messagebox, simpledialog
import subprocess
import sys
import os
from datetime import datetime

COMMANDS = {
    'Copy Events': {
        'cmd': ['python', 'copy_calendar.py', 'copy'],
        'desc': 'Copies future events to your primary calendar, skipping duplicates. Prompts for an optional end date.'
    },
    'Copy Events (Dry Run)': {
        'cmd': ['python', 'copy_calendar.py', 'copy', '--dry-run'],
        'desc': 'Shows what would be copied without making changes. Prompts for an optional end date.'
    },
    'Delete Copied Events': {
        'cmd': ['python', 'copy_calendar.py', 'delete'],
        'desc': 'Deletes all events created by this tool from your primary calendar.'
    },
    'Delete Copied Events (Dry Run)': {
        'cmd': ['python', 'copy_calendar.py', 'delete', '--dry-run'],
        'desc': 'Shows which events would be deleted, but does not actually delete them.'
    },
    'List Calendars': {
        'cmd': ['python', 'copy_calendar.py', 'list-calendars'],
        'desc': 'Lists all calendars you have access to, with their IDs.'
    },
    'Show Source Events': {
        'cmd': ['python', 'copy_calendar.py', 'show-source'],
        'desc': 'Displays upcoming events from your source calendar.'
    },
    'Show Copied Events': {
        'cmd': ['python', 'copy_calendar.py', 'show-copied'],
        'desc': 'Displays events in your primary calendar that were copied by this tool.'
    },
}


COPY_COMMAND_LABELS = {'Copy Events', 'Copy Events (Dry Run)'}


def run_command(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        output = result.stdout
    except subprocess.CalledProcessError as e:
        output = e.stdout + '\n' + e.stderr
    OutputWindow(output)

class OutputWindow(tk.Toplevel):
    def __init__(self, text):
        super().__init__()
        self.title('Command Output')
        text_widget = tk.Text(self, wrap='word', width=100, height=30)
        text_widget.insert('1.0', text)
        text_widget.config(state='disabled')
        text_widget.pack(expand=True, fill='both')
        tk.Button(self, text='Close', command=self.destroy).pack(pady=5)

class CalendarCopyGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Google Calendar Copy Tool')
        self.geometry('480x500')
        tk.Label(self, text='Google Calendar Copy Tool', font=('Arial', 16, 'bold')).pack(pady=10)

        # Startup checklist
        if not self.check_setup():
            self.disable_all = True
        else:
            self.disable_all = False

        self.buttons = []
        for label, info in COMMANDS.items():
            btn = tk.Button(
                self,
                text=label,
                width=40,
                command=lambda l=label, c=info['cmd']: self.handle_command(l, c)
            )
            btn.pack(pady=4)
            btn.bind("<Enter>", lambda e, d=info['desc']: self.show_status(d))
            btn.bind("<Leave>", lambda e: self.clear_status())
            if self.disable_all:
                btn.config(state='disabled')
            self.buttons.append(btn)
        tk.Button(self, text='Exit', width=40, command=self.destroy).pack(pady=10)
        self.status = tk.Label(self, text='', wraplength=400, fg='blue')
        self.status.pack(pady=5)

    def show_status(self, desc):
        self.status.config(text=desc)

    def clear_status(self):
        self.status.config(text='')

    def handle_command(self, label, base_command):
        command = list(base_command)

        if label in COPY_COMMAND_LABELS:
            until = self.prompt_until_date()
            if until is None:
                return
            if until:
                command.extend(['--until', until])

        run_command(command)

    def prompt_until_date(self):
        while True:
            value = simpledialog.askstring(
                'Optional End Date',
                'Copy through date (YYYY-MM-DD).\n'
                'Leave blank to use default future range.\n'
                'Cancel to abort.',
                parent=self
            )

            if value is None:
                return None

            value = value.strip()
            if not value:
                return ''

            try:
                datetime.strptime(value, '%Y-%m-%d')
                return value
            except ValueError:
                messagebox.showerror(
                    'Invalid Date',
                    "Please enter a valid date in YYYY-MM-DD format."
                )

    def check_setup(self):
        # Check for credentials.json
        if not os.path.exists('credentials.json'):
            messagebox.showerror('Setup Error', 'Missing credentials.json. Please follow the setup instructions in the README.')
            return False
        # Check for SOURCE_CALENDAR_ID in copy_calendar.py
        try:
            with open('copy_calendar.py', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines:
                if line.strip().startswith('SOURCE_CALENDAR_ID'):
                    if line.strip().endswith("''") or line.strip().endswith('""'):
                        messagebox.showerror('Setup Error', 'SOURCE_CALENDAR_ID is not set in copy_calendar.py. Please set it to your source calendar ID.')
                        return False
                    break
        except Exception:
            pass
        return True

if __name__ == '__main__':
    app = CalendarCopyGUI()
    app.mainloop()
