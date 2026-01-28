# python copy_calendar.py 10



from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os.path
import pickle

SCOPES = ['https://www.googleapis.com/auth/calendar']
SOURCE_CALENDAR_ID = 'c_1886ai526iqschc9mnpj6cu753n60@resource.calendar.google.com'
COPY_TAG = 'copied_from_external'

def authenticate():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def copy_events(limit=5):
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    from datetime import datetime, timedelta
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
    far_future = (datetime.now() + timedelta(days=365*2)).isoformat() + 'Z'
    
    # Get existing events from your calendar - check future events with pagination
    print("Checking existing events...")
    existing_summaries = set()
    page_token = None
    pages = 0
    
    while True:
        existing = service.events().list(
            calendarId='primary',
            maxResults=2500,
            timeMin=today,
            timeMax=far_future,
            singleEvents=True,
            pageToken=page_token
        ).execute()
        
        for e in existing.get('items', []):
            existing_summaries.add((e.get('summary'), str(e.get('start'))))
        
        page_token = existing.get('nextPageToken')
        pages += 1
        
        if not page_token or pages >= 3:  # Check up to ~7500 events
            break
    
    print(f"Found {len(existing_summaries)} existing events on your calendar")
    
    # Get events from source calendar - ONLY from today onwards, IN CHRONOLOGICAL ORDER
    print("Fetching source calendar events...")
    
    source_events = service.events().list(
        calendarId=SOURCE_CALENDAR_ID, 
        maxResults=2500, 
        singleEvents=True,
        orderBy='startTime',
        timeMin=today
    ).execute()
    
    print(f"Found {len(source_events.get('items', []))} events from source")
    print(f"Will copy up to {limit} events in chronological order\n")
    
    copied = 0
    failed = 0
    for event in source_events.get('items', []):
        if copied >= limit:
            print(f"\nReached limit of {limit} events")
            break
            
        event_key = (event.get('summary'), str(event.get('start')))
        if event_key not in existing_summaries:
            try:
                # Extract room/resource info
                room_info = event.get('location', '')
                
                # Extract guest names as plain text
                attendees = event.get('attendees', [])
                guest_text = ', '.join([a.get('displayName', a.get('email', '')) for a in attendees])
                
                # Build ONLY these fields - NOTHING else
                new_event = {
                    'summary': event.get('summary', ''),
                    'location': room_info,
                    'description': f"[{COPY_TAG}]\nOriginal guests: {guest_text}\n\n{event.get('description', '')}",
                    'start': event.get('start'),
                    'end': event.get('end'),
                }
                
                result = service.events().insert(
                    calendarId='primary', 
                    body=new_event,
                    sendNotifications=False
                ).execute()
                
                print(f"Copied: {new_event.get('summary')} (Start: {event.get('start')})")
                copied += 1
                    
            except Exception as e:
                print(f"Failed: {e}")
                failed += 1
    
    print(f"\nDone! Copied {copied} events, failed {failed}.")
    
def delete_copied_events():
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    print("Finding copied events...")
    from datetime import datetime
    today = datetime.now().isoformat() + 'Z'
    
    all_events = []
    page_token = None
    pages = 0
    
    while True:
        events = service.events().list(
            calendarId='primary', 
            maxResults=2500,
            timeMin=today,
            singleEvents=True,
            pageToken=page_token
        ).execute()
        
        all_events.extend(events.get('items', []))
        page_token = events.get('nextPageToken')
        pages += 1
        
        print(f"Fetched page {pages}, total events so far: {len(all_events)}")
        
        if not page_token or pages >= 5:  # Safety limit
            break
    
    print(f"Total events retrieved: {len(all_events)}")
    
    deleted = 0
    for event in all_events:
        description = event.get('description', '')
        if COPY_TAG in description:
            try:
                service.events().delete(calendarId='primary', eventId=event['id']).execute()
                print(f"Deleted: {event.get('summary')}")
                deleted += 1
            except Exception as e:
                print(f"Failed to delete {event.get('summary')}: {e}")
    
    print(f"\nDone! Deleted {deleted} copied events.")

def inspect_event():
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    source_events = service.events().list(calendarId=SOURCE_CALENDAR_ID, maxResults=1).execute()
    event = source_events.get('items', [])[0]
    
    print("Event fields:")
    for key, value in event.items():
        print(f"{key}: {value}")

def inspect_copied_event():
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    events = service.events().list(calendarId='primary', maxResults=50).execute()
    
    for event in events.get('items', []):
        if COPY_TAG in event.get('description', ''):
            print("Copied event fields:")
            for key, value in event.items():
                print(f"{key}: {value}")
            break

def check_auth():
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    # Get calendar list to see which account
    calendar_list = service.calendarList().list().execute()
    
    print("Authenticated calendars:")
    for cal in calendar_list.get('items', []):
        print(f"- {cal.get('summary')} ({cal.get('id')})")
        if cal.get('primary'):
            print("  ^ This is your primary calendar")
    
    # Check recent events on primary
    print("\nRecent events on primary calendar:")
    events = service.events().list(calendarId='primary', maxResults=5, orderBy='updated').execute()
    for event in events.get('items', []):
        print(f"- {event.get('summary')} (ID: {event.get('id')})")

def show_recent():
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    from datetime import datetime, timedelta
    today = datetime.now()
    week_ago = (today - timedelta(days=7)).strftime('%Y-%m-%dT00:00:00Z')
    
    events = service.events().list(
        calendarId='primary',
        timeMin=week_ago,
        maxResults=20,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    print(f"\nYour upcoming events:")
    for event in events.get('items', []):
        print(f"\n{event.get('summary')}")
        print(f"  Start: {event.get('start')}")
        print(f"  Attendees: {event.get('attendees', 'None')}")
        desc = event.get('description', '')
        if COPY_TAG in desc:
            print(f"  *** This is a copied event ***")

def diagnose():
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    # Get ALL events including far future ones
    print("Searching ALL events on primary calendar...")
    from datetime import datetime, timedelta
    today = datetime.now()
    far_future = (today + timedelta(days=365*2)).isoformat() + 'Z'  # 2 years out
    
    events = service.events().list(
        calendarId='primary', 
        maxResults=2500,
        timeMax=far_future
    ).execute()
    
    print(f"Total events retrieved: {len(events.get('items', []))}")
    
    # Find events with our tag
    tagged = []
    for event in events.get('items', []):
        if COPY_TAG in event.get('description', ''):
            tagged.append(event)
    
    print(f"\nEvents with [{COPY_TAG}] tag: {len(tagged)}")
    for e in tagged:
        print(f"- {e.get('summary')}")
    
    # Look specifically for S26
    print("\n\nSearching for 'S26' events:")
    for event in events.get('items', []):
        if 'S26' in event.get('summary', ''):
            print(f"\nFound: {event.get('summary')}")
            print(f"ID: {event.get('id')}")
            print(f"Start: {event.get('start')}")
            print(f"Description: {event.get('description', 'NONE')[:300]}")

def delete_test():
    """Delete the test event we copied"""
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    events = service.events().list(calendarId='primary', maxResults=2500).execute()
    
    for event in events.get('items', []):
        if 'S26' in event.get('summary', ''):
            summary = event.get('summary')
            event_id = event.get('id')
            print(f"Deleting: {summary}")
            try:
                service.events().delete(calendarId='primary', eventId=event_id).execute()
                print("Deleted successfully")
            except Exception as e:
                print(f"Failed to delete: {e}")

def show_source():
    """Show events from source calendar"""
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    from datetime import datetime
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
    
    print(f"Events in source calendar from today onwards:")
    source_events = service.events().list(
        calendarId=SOURCE_CALENDAR_ID, 
        maxResults=50,
        singleEvents=True,
        timeMin=today,
        orderBy='startTime'
    ).execute()
    
    print(f"\nFound {len(source_events.get('items', []))} events\n")
    
    for event in source_events.get('items', []):
        print(f"{event.get('summary')}")
        print(f"  Start: {event.get('start')}")
        print(f"  Location: {event.get('location', 'None')}")
        print(f"  Attendees: {len(event.get('attendees', []))}")
        desc = event.get('description', '')
        print(f"  Description: {desc[:100] if desc else 'None'}")
        print()

def find_by_id():
    """Find the most recently copied event by ID"""
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    # Use the ID from the last copy operation
    event_id = "ghl8qbf1383ro6p5mitev5qj4o"
    
    # Get all calendars
    calendar_list = service.calendarList().list().execute()
    
    print(f"\nSearching for event {event_id}...\n")
    
    for cal in calendar_list.get('items', []):
        cal_id = cal.get('id')
        cal_name = cal.get('summary')
        try:
            event = service.events().get(calendarId=cal_id, eventId=event_id).execute()
            print(f"FOUND on calendar: {cal_name}")
            print(f"Summary: {event.get('summary')}")
            print(f"Start: {event.get('start')}")
            print(f"Description: {event.get('description', 'NONE')[:200]}")
            return
        except:
            pass
    
    print("Event not found on any calendar")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'delete':
        delete_copied_events()
    elif len(sys.argv) > 1 and sys.argv[1] == 'inspect':
        inspect_event()
    elif len(sys.argv) > 1 and sys.argv[1] == 'inspect-copied':
        inspect_copied_event()
    elif len(sys.argv) > 1 and sys.argv[1] == 'check':
        check_auth()
    elif len(sys.argv) > 1 and sys.argv[1] == 'recent':
        show_recent()
    elif len(sys.argv) > 1 and sys.argv[1] == 'diagnose':
        diagnose()
    elif len(sys.argv) > 1 and sys.argv[1] == 'delete-test':
        delete_test()
    elif len(sys.argv) > 1 and sys.argv[1] == 'show-source':
        show_source()
    elif len(sys.argv) > 1 and sys.argv[1] == 'find-by-id':
        find_by_id()
    else:
        # Allow optional limit argument: python copy_calendar.py 10
        limit = 5  # default
        if len(sys.argv) > 1:
            try:
                limit = int(sys.argv[1])
            except ValueError:
                print(f"Invalid limit: {sys.argv[1]}, using default of 5")
        copy_events(limit=limit)