# Google Calendar Copy

Copy events from a subscribed or shared calendar to your primary calendar, so they sync to devices that only see calendars you own (like Garmin watches).

---

## Quick Q&A / Troubleshooting

**Q: I get 'Error: SOURCE_CALENDAR_ID is not set!'**
A: Open `copy_calendar.py` in a text editor and set the `SOURCE_CALENDAR_ID` variable near the top to your source calendar's ID. See below for how to find it.

**Q: I get 'access_denied' or 'app not verified' during authentication**
A: Make sure your Google account is added as a test user in the Google Cloud Console (OAuth consent screen > Test users). Only test users can use the app unless you submit for verification.

**Q: I get 'Token has been expired or revoked.'**
A: The script now automatically falls back to re-authentication when this happens. If needed, you can still delete `token.pickle` manually and run the command again.

**Q: The script says 'Copied: 0, Skipped (duplicates): N'**
A: All source events already exist in your primary calendar (as detected by the script). Add new events to your source calendar or delete previously copied events to test copying again.

**Q: How do I reset everything?**
A: Delete all events created by this tool with `python copy_calendar.py delete`. You can also delete `token.pickle` to force a new authentication.

**Q: How do I use this if I'm not a developer?**
A: You don't need to code! Just follow the steps below, and you can now use the included graphical interface (see 'Basic GUI' below).

---

## Why This Exists

Some devices only sync with calendars you own. They can't see subscribed calendars, resource calendars (conference rooms), or read-only shared calendars. This script copies events from those calendars to your primary calendar, where they'll sync everywhere.

## Setup

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Name it "Calendar Copy" and click **Create**
4. Select your new project

### Step 2: Enable the Calendar API

1. Go to **APIs & Services → Library**
2. Search for "Google Calendar API"
3. Click it and click **Enable**

### Step 3: Configure OAuth Consent

1. Go to **APIs & Services → OAuth consent screen**
2. Select **External** and click **Create**
3. Fill in:
   - App name: "Calendar Copy"
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue**
5. Click **Add or Remove Scopes**, find `https://www.googleapis.com/auth/calendar`, select it, click **Update**
6. Click **Save and Continue**
7. Click **Add Users**, add your Google email
8. Click **Save and Continue** → **Back to Dashboard**

### Step 4: Create Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Select **Desktop application**, name it anything
4. Click **Create**
5. Click **Download JSON**
6. Rename the file to `credentials.json` and put it in this directory

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 6: Find Your Source Calendar ID

Run:
```bash
python copy_calendar.py list-calendars
```

This lists all calendars you can access. Find the one you want to copy from and note its ID.

Or in Google Calendar: Settings → click on the calendar → scroll to "Integrate calendar" → copy the Calendar ID.

#### How to Update the Calendar ID

1. Open `copy_calendar.py` in a text editor (Notepad, VS Code, etc.).
2. Near the top, find the line:
   ```python
   SOURCE_CALENDAR_ID = ''
   ```
3. Replace the empty string with your calendar's ID, for example:
   ```python
   SOURCE_CALENDAR_ID = 'c_abc123@resource.calendar.google.com'
   ```
4. Save the file.

### Step 7: Configure

Open `copy_calendar.py` and set `SOURCE_CALENDAR_ID`:

```python
SOURCE_CALENDAR_ID = 'c_abc123@resource.calendar.google.com'  # your calendar ID
```

That's the only required change. See [Configuration](#configuration) below for optional settings.

### Step 8: Authenticate

Run:
```bash
python copy_calendar.py list-calendars
```

A browser opens. Sign in with the Google account you added as a test user and grant access. You'll see "The authentication flow has completed" - you can close that tab.

## Usage

```bash
# Copy all future events
python copy_calendar.py copy

# Preview what would be copied (no changes)
python copy_calendar.py copy --dry-run

# Copy just one event to test
python copy_calendar.py copy --test

# Copy events through a specific date (inclusive)
python copy_calendar.py copy --until 2026-06-30

# Delete all events created by this script
python copy_calendar.py delete

# Preview what would be deleted
python copy_calendar.py delete --dry-run
```

## Command Descriptions

**Copy Events**

`python copy_calendar.py copy`  
Copies all future events from your source calendar to your primary calendar, skipping any that already exist (to avoid duplicates).

**--dry-run**

`python copy_calendar.py copy --dry-run`  
Shows which events would be copied, but does not actually create or modify any events. Use this to preview changes safely.

**--limit N**

`python copy_calendar.py copy --limit 5`  
Copies up to N events (e.g., 5). Useful for testing or limiting the number of events copied in one run.

**--test**

`python copy_calendar.py copy --test`  
Copies only 1 event, for quick testing. Equivalent to `--limit 1`.

**--until YYYY-MM-DD**

`python copy_calendar.py copy --until 2026-06-30`  
Copies events up to and including the specified date.

**Delete Copied Events**

`python copy_calendar.py delete`  
Deletes all events from your primary calendar that were created by this tool (identified by the special tag in their description).

**Delete Copied Events (Dry Run)**

`python copy_calendar.py delete --dry-run`  
Shows which events would be deleted, but does not actually delete anything. Use this to preview deletions safely.

**List Calendars**

`python copy_calendar.py list-calendars`  
Lists all calendars you have access to, along with their IDs. Use this to find your source calendar ID.

**Show Source Events**

`python copy_calendar.py show-source`  
Displays upcoming events from your source calendar (does not copy them).

**Show Copied Events**

`python copy_calendar.py show-copied`  
Displays events in your primary calendar that were copied by this tool.

## Basic GUI (Graphical Interface)

For non-technical users, you can use a simple graphical interface:

1. Make sure you have Python installed and dependencies set up (see Setup above).
2. Double-click or run:
   ```bash
   python gui.py
   ```
3. A window will open with buttons for the most common actions (copy, delete, list, etc.).
4. When you click a copy action, you'll be prompted for an optional `YYYY-MM-DD` end date (`--until`); leave it blank to use the default range.

This makes it easier to use the tool without typing commands.

## Configuration

All settings are at the top of `copy_calendar.py`.

### SOURCE_CALENDAR_ID (required)

The calendar to copy events from.

### COPY_TAG

```python
COPY_TAG = 'copied_from_external'
```

Added to every copied event's description. This is how the `delete` command knows which events to remove. Change it if you're copying from multiple calendars and want to manage them separately.

### INCLUDE_LOCATION

```python
INCLUDE_LOCATION = True
```

Copies the location field (room names, addresses). Usually what you want.

### INCLUDE_ATTENDEES

```python
INCLUDE_ATTENDEES = False
```

**Default is False for good reason.** When True, copies attendees as actual event participants. This can cause problems:

- Room booking systems may interpret this as a new booking and auto-accept
- Some systems trigger workflows based on attendee lists
- Creates confusion about which event is "real"

Leave this False unless you specifically need attendees on the event. The attendee names are still recorded in the description for reference.

### SEND_NOTIFICATIONS

```python
SEND_NOTIFICATIONS = False
```

Only matters if `INCLUDE_ATTENDEES` is True. When True, sends calendar invitations to all attendees. Almost never what you want—everyone would get duplicate invites.

If you enable both `INCLUDE_ATTENDEES` and `SEND_NOTIFICATIONS`, the script will ask for confirmation before proceeding.

### DESCRIPTION_TEMPLATE

```python
DESCRIPTION_TEMPLATE = "[{copy_tag}]\nOriginal guests: {attendees}\n\n{original_description}"
```

Controls what goes in the copied event's description. Available placeholders:

- `{copy_tag}` - the COPY_TAG value (keep this so deletion works)
- `{location}` - original location
- `{attendees}` - comma-separated attendee names
- `{original_description}` - the original description

Examples:

```python
# Minimal - just the tag and original description
DESCRIPTION_TEMPLATE = "[{copy_tag}]\n{original_description}"

# Everything
DESCRIPTION_TEMPLATE = "[{copy_tag}]\nRoom: {location}\nAttendees: {attendees}\n\n{original_description}"

# Just the tag (set to None to use original description with tag prepended)
DESCRIPTION_TEMPLATE = None
```

### FUTURE_DAYS

```python
FUTURE_DAYS = 365
```

How far into the future to look for events. Set to 0 for no limit.

## Deleting Copied Events

If something goes wrong or you want to start fresh:

```bash
python copy_calendar.py delete
```

This finds all events with your `COPY_TAG` in the description and deletes them. It shows you what it found and asks for confirmation before deleting anything.

Use `--dry-run` first to see what would be deleted:

```bash
python copy_calendar.py delete --dry-run
```

## Running Automatically

To keep calendars in sync, run periodically with cron:

```bash
# Every day at 6 AM
0 6 * * * cd /path/to/google-calendar-copy && python copy_calendar.py copy
```

The script skips duplicates, so running it repeatedly is safe.

## Troubleshooting

**"credentials.json not found"** - Download OAuth credentials from Google Cloud Console (Step 4).

**"Access blocked" during auth** - Click "Advanced" → "Go to Calendar Copy (unsafe)". This warning appears because your app isn't published, which is fine for personal use.

**"Request had insufficient authentication scopes"** - Delete `token.pickle` and run again.

**"Not Found" error for calendar** - Check the calendar ID is correct and that you have access to it in Google Calendar.

See the Q&A section above for more help.

## License

MIT

---

