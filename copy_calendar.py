#!/usr/bin/env python3
"""
Google Calendar Copy Tool

Copies events from a subscribed/shared calendar to your primary calendar.
Useful when devices (like Garmin watches) only sync with calendars you own.

Usage:
    python copy_calendar.py copy [--limit N] [--test] [--dry-run]
    python copy_calendar.py delete [--dry-run]
    python copy_calendar.py list-calendars
    python copy_calendar.py show-source [--limit N]
    python copy_calendar.py show-copied
"""

# =============================================================================
# CONFIGURATION - Edit these values to customize behavior
# =============================================================================

# REQUIRED: The calendar ID to copy events FROM
# Find this in Google Calendar: Settings > [Calendar Name] > "Integrate calendar" section
# Examples:
#   - Resource calendar: 'c_1886ai526iqschc9mnpj6cu753n60@resource.calendar.google.com'
#   - Shared calendar: 'someone@example.com'
#   - Public calendar: 'en.usa#holiday@group.v.calendar.google.com'
SOURCE_CALENDAR_ID = ''

# Tag used to identify copied events (enables safe deletion of only copied events)
# Change this if you want to use different tags for different source calendars
COPY_TAG = 'copied_from_external'

# -----------------------------------------------------------------------------
# Event Field Options
# -----------------------------------------------------------------------------

# Copy the location field (room names, addresses, etc.)
INCLUDE_LOCATION = True

# Copy attendees to the new event
# WARNING: This may trigger booking systems or cause confusion if the event
# involves meeting rooms or resources that auto-accept based on attendees.
# Default False is the safe choice for most use cases.
INCLUDE_ATTENDEES = False

# Send calendar notifications to attendees when events are created/modified
# Only relevant if INCLUDE_ATTENDEES is True
# WARNING: Setting this to True will send emails to all attendees!
# This could confuse people or create duplicate notifications.
SEND_NOTIFICATIONS = False

# -----------------------------------------------------------------------------
# Description Template
# -----------------------------------------------------------------------------

# How to format the copied event's description
# Available placeholders:
#   {copy_tag}            - The COPY_TAG value (for identification)
#   {location}            - Original event location
#   {attendees}           - Comma-separated list of attendee names/emails
#   {original_description} - The original event description
#
# Set to None to keep only the original description (with copy tag prepended)
#
# Examples:
#   Full info:     "[{copy_tag}]\nRoom: {location}\nGuests: {attendees}\n\n{original_description}"
#   Minimal:       "[{copy_tag}]\n{original_description}"
#   Just tag:      "[{copy_tag}]"
DESCRIPTION_TEMPLATE = "[{copy_tag}]\nOriginal guests: {attendees}\n\n{original_description}"

# -----------------------------------------------------------------------------
# Time Range
# -----------------------------------------------------------------------------

# How far into the future to look for events (in days)
# Set to 0 for no limit (copies all future events from source)
FUTURE_DAYS = 365

# =============================================================================
# END OF CONFIGURATION - No need to edit below this line
# =============================================================================

import argparse
import os.path
import pickle
import sys
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# OAuth scope - full calendar access required to create events
SCOPES = ['https://www.googleapis.com/auth/calendar']


def authenticate():
    """
    Authenticate with Google Calendar API using OAuth 2.0.

    On first run, opens a browser for authentication. Subsequent runs
    use the cached token in token.pickle.

    Returns:
        Credentials object for API calls

    Raises:
        FileNotFoundError: If credentials.json is missing
    """
    creds = None

    # Load cached credentials if they exist
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # Refresh or get new credentials if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing access token...")
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json not found!")
                print("\nTo set up authentication:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a project and enable the Google Calendar API")
                print("3. Create OAuth 2.0 credentials (Desktop application)")
                print("4. Download and save as 'credentials.json' in this directory")
                sys.exit(1)

            print("Opening browser for authentication...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds


def validate_config():
    """
    Validate configuration and warn about potentially risky settings.

    Returns:
        bool: True if configuration is valid, False otherwise
    """
    if not SOURCE_CALENDAR_ID:
        print("Error: SOURCE_CALENDAR_ID is not set!")
        print("\nEdit copy_calendar.py and set SOURCE_CALENDAR_ID to your source calendar's ID.")
        print("Find the calendar ID in Google Calendar:")
        print("  Settings > [Calendar Name] > 'Integrate calendar' section")
        return False

    # Warn about risky combinations
    if INCLUDE_ATTENDEES and SEND_NOTIFICATIONS:
        print("=" * 60)
        print("WARNING: INCLUDE_ATTENDEES and SEND_NOTIFICATIONS are both enabled!")
        print("This will send calendar invitations to all attendees on copied events.")
        print("=" * 60)
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return False

    return True


def build_description(event):
    """
    Build the description for a copied event using the template.

    Args:
        event: The source event dictionary from Google Calendar API

    Returns:
        str: The formatted description
    """
    if DESCRIPTION_TEMPLATE is None:
        # Just prepend the copy tag to original description
        original = event.get('description', '')
        return f"[{COPY_TAG}]\n{original}" if original else f"[{COPY_TAG}]"

    # Gather values for template placeholders
    attendees = event.get('attendees', [])
    attendee_names = ', '.join([
        a.get('displayName', a.get('email', ''))
        for a in attendees
    ])

    values = {
        'copy_tag': COPY_TAG,
        'location': event.get('location', ''),
        'attendees': attendee_names,
        'original_description': event.get('description', ''),
    }

    try:
        return DESCRIPTION_TEMPLATE.format(**values)
    except KeyError as e:
        print(f"Warning: Unknown placeholder in DESCRIPTION_TEMPLATE: {e}")
        return f"[{COPY_TAG}]\n{event.get('description', '')}"


def get_existing_events(service, time_min, time_max):
    """
    Fetch existing events from primary calendar to check for duplicates.

    Args:
        service: Google Calendar API service object
        time_min: ISO format start time
        time_max: ISO format end time

    Returns:
        set: Set of (summary, start_time) tuples for duplicate detection
    """
    print("Checking for existing events...")
    existing = set()
    page_token = None
    pages = 0

    while True:
        events = service.events().list(
            calendarId='primary',
            maxResults=2500,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            pageToken=page_token
        ).execute()

        for e in events.get('items', []):
            existing.add((e.get('summary'), str(e.get('start'))))

        page_token = events.get('nextPageToken')
        pages += 1

        if not page_token or pages >= 5:
            break

    return existing


def copy_events(limit=None, dry_run=False):
    """
    Copy events from source calendar to primary calendar.

    Args:
        limit: Maximum number of events to copy (None for no limit)
        dry_run: If True, show what would be copied without making changes

    Returns:
        tuple: (copied_count, skipped_count, failed_count)
    """
    if not validate_config():
        return (0, 0, 0)

    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)

    # Calculate time range
    now = datetime.now()
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'

    if FUTURE_DAYS > 0:
        time_max = (now + timedelta(days=FUTURE_DAYS)).isoformat() + 'Z'
    else:
        time_max = (now + timedelta(days=365 * 5)).isoformat() + 'Z'  # 5 years max

    # Get existing events for duplicate checking
    existing = get_existing_events(service, time_min, time_max)
    print(f"Found {len(existing)} existing events on primary calendar")

    # Fetch source calendar events
    print(f"\nFetching events from source calendar...")
    source_events = service.events().list(
        calendarId=SOURCE_CALENDAR_ID,
        maxResults=2500,
        singleEvents=True,
        orderBy='startTime',
        timeMin=time_min,
        timeMax=time_max if FUTURE_DAYS > 0 else None
    ).execute()

    items = source_events.get('items', [])
    print(f"Found {len(items)} events on source calendar")

    if not items:
        print("No events to copy.")
        return (0, 0, 0)

    if limit:
        print(f"Will process up to {limit} events")

    if dry_run:
        print("\n[DRY RUN - No changes will be made]\n")

    # Process events
    copied = 0
    skipped = 0
    failed = 0

    for i, event in enumerate(items):
        if limit and copied >= limit:
            print(f"\nReached limit of {limit} events")
            break

        event_key = (event.get('summary'), str(event.get('start')))
        summary = event.get('summary', '(no title)')
        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))

        # Check for duplicates
        if event_key in existing:
            skipped += 1
            continue

        if dry_run:
            print(f"  Would copy: {summary} ({start})")
            copied += 1
            continue

        # Build the new event
        new_event = {
            'summary': event.get('summary', ''),
            'description': build_description(event),
            'start': event.get('start'),
            'end': event.get('end'),
        }

        if INCLUDE_LOCATION and event.get('location'):
            new_event['location'] = event.get('location')

        if INCLUDE_ATTENDEES and event.get('attendees'):
            new_event['attendees'] = event.get('attendees')

        try:
            service.events().insert(
                calendarId='primary',
                body=new_event,
                sendNotifications=SEND_NOTIFICATIONS
            ).execute()

            print(f"  Copied: {summary} ({start})")
            copied += 1

        except Exception as e:
            print(f"  Failed: {summary} - {e}")
            failed += 1

    # Summary
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Summary:")
    print(f"  Copied: {copied}")
    print(f"  Skipped (duplicates): {skipped}")
    if failed:
        print(f"  Failed: {failed}")

    return (copied, skipped, failed)


def delete_copied_events(dry_run=False):
    """
    Delete all events that were created by this tool (identified by COPY_TAG).

    Args:
        dry_run: If True, show what would be deleted without making changes

    Returns:
        int: Number of events deleted
    """
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)

    print("Finding copied events...")
    now = datetime.now()
    time_min = (now - timedelta(days=30)).isoformat() + 'Z'  # Include recent past

    # Collect all events with pagination
    all_events = []
    page_token = None
    pages = 0

    while True:
        events = service.events().list(
            calendarId='primary',
            maxResults=2500,
            timeMin=time_min,
            singleEvents=True,
            pageToken=page_token
        ).execute()

        all_events.extend(events.get('items', []))
        page_token = events.get('nextPageToken')
        pages += 1

        if not page_token or pages >= 10:
            break

    # Find events with our tag
    to_delete = []
    for event in all_events:
        description = event.get('description', '')
        if f'[{COPY_TAG}]' in description:
            to_delete.append(event)

    if not to_delete:
        print(f"No events found with tag [{COPY_TAG}]")
        return 0

    print(f"\nFound {len(to_delete)} copied events:")
    for event in to_delete[:10]:  # Show first 10
        summary = event.get('summary', '(no title)')
        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))
        print(f"  - {summary} ({start})")

    if len(to_delete) > 10:
        print(f"  ... and {len(to_delete) - 10} more")

    if dry_run:
        print(f"\n[DRY RUN] Would delete {len(to_delete)} events")
        return len(to_delete)

    # Confirmation prompt
    print()
    response = input(f"Delete {len(to_delete)} events? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        return 0

    # Delete events
    deleted = 0
    for event in to_delete:
        try:
            service.events().delete(
                calendarId='primary',
                eventId=event['id'],
                sendNotifications=False
            ).execute()
            deleted += 1
            print(f"  Deleted: {event.get('summary', '(no title)')}")
        except Exception as e:
            print(f"  Failed to delete {event.get('summary')}: {e}")

    print(f"\nDeleted {deleted} events")
    return deleted


def list_calendars():
    """
    List all calendars accessible to the authenticated account.
    Useful for finding the correct SOURCE_CALENDAR_ID.
    """
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)

    calendar_list = service.calendarList().list().execute()

    print("\nAccessible calendars:\n")
    for cal in calendar_list.get('items', []):
        name = cal.get('summary', '(unnamed)')
        cal_id = cal.get('id')
        primary = ' [PRIMARY]' if cal.get('primary') else ''
        access = cal.get('accessRole', '')

        print(f"  {name}{primary}")
        print(f"    ID: {cal_id}")
        print(f"    Access: {access}")
        print()


def show_source(limit=10):
    """
    Show upcoming events from the source calendar.

    Args:
        limit: Maximum number of events to display
    """
    if not SOURCE_CALENDAR_ID:
        print("Error: SOURCE_CALENDAR_ID is not set")
        return

    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)

    now = datetime.now()
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'

    print(f"\nUpcoming events from source calendar:\n")

    try:
        events = service.events().list(
            calendarId=SOURCE_CALENDAR_ID,
            maxResults=limit,
            singleEvents=True,
            orderBy='startTime',
            timeMin=time_min
        ).execute()
    except Exception as e:
        print(f"Error accessing source calendar: {e}")
        print("\nMake sure:")
        print("  - The calendar ID is correct")
        print("  - You have access to this calendar")
        print("  - The calendar is visible in your Google Calendar")
        return

    items = events.get('items', [])
    if not items:
        print("No upcoming events found.")
        return

    for event in items:
        summary = event.get('summary', '(no title)')
        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))
        location = event.get('location', '')
        attendees = event.get('attendees', [])

        print(f"  {summary}")
        print(f"    Start: {start}")
        if location:
            print(f"    Location: {location}")
        if attendees:
            print(f"    Attendees: {len(attendees)}")
        print()


def show_copied(limit=10):
    """
    Show events that were copied by this tool.

    Args:
        limit: Maximum number of events to display
    """
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)

    now = datetime.now()
    time_min = (now - timedelta(days=7)).isoformat() + 'Z'

    events = service.events().list(
        calendarId='primary',
        maxResults=100,
        singleEvents=True,
        orderBy='startTime',
        timeMin=time_min
    ).execute()

    print(f"\nCopied events (tag: [{COPY_TAG}]):\n")

    found = 0
    for event in events.get('items', []):
        if f'[{COPY_TAG}]' in event.get('description', ''):
            if found >= limit:
                print(f"  ... and more (use --limit to see more)")
                break

            summary = event.get('summary', '(no title)')
            start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))
            print(f"  {summary}")
            print(f"    Start: {start}")
            print()
            found += 1

    if found == 0:
        print("  No copied events found.")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Copy events from a shared/subscribed calendar to your primary calendar.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python copy_calendar.py copy                  Copy all future events
  python copy_calendar.py copy --limit 5        Copy up to 5 events
  python copy_calendar.py copy --test           Copy just 1 event (for testing)
  python copy_calendar.py copy --dry-run        Show what would be copied
  python copy_calendar.py delete                Delete all copied events
  python copy_calendar.py delete --dry-run      Show what would be deleted
  python copy_calendar.py list-calendars        List accessible calendars
  python copy_calendar.py show-source           Show source calendar events
  python copy_calendar.py show-copied           Show copied events
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Copy command
    copy_parser = subparsers.add_parser('copy', help='Copy events from source to primary calendar')
    copy_parser.add_argument('--limit', type=int, help='Maximum number of events to copy')
    copy_parser.add_argument('--test', action='store_true', help='Copy only 1 event (for testing)')
    copy_parser.add_argument('--dry-run', action='store_true', help='Show what would be copied without making changes')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete all copied events')
    delete_parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without making changes')

    # List calendars command
    subparsers.add_parser('list-calendars', help='List all accessible calendars')

    # Show source command
    show_source_parser = subparsers.add_parser('show-source', help='Show events from source calendar')
    show_source_parser.add_argument('--limit', type=int, default=10, help='Number of events to show')

    # Show copied command
    show_copied_parser = subparsers.add_parser('show-copied', help='Show events copied by this tool')
    show_copied_parser.add_argument('--limit', type=int, default=10, help='Number of events to show')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == 'copy':
        limit = 1 if args.test else args.limit
        copy_events(limit=limit, dry_run=args.dry_run)

    elif args.command == 'delete':
        delete_copied_events(dry_run=args.dry_run)

    elif args.command == 'list-calendars':
        list_calendars()

    elif args.command == 'show-source':
        show_source(limit=args.limit)

    elif args.command == 'show-copied':
        show_copied(limit=args.limit)


if __name__ == '__main__':
    main()
