import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
import datetime

# Authenticate and connect to Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPES)
gc = gspread.authorize(creds)

# Open the Google Sheets file
spreadsheet = gc.open('test2')
worksheet = spreadsheet.sheet1

# Authenticate and connect to Google Calendar
calendar_service = build('calendar', 'v3', credentials=creds)

def check_if_is_date(val, date_format):
    try:
        datetime.datetime.strptime(val, date_format)
        return True
    except ValueError:
        return False

# Function to fetch events from Google Sheets file
def fetch_events_from_sheets():
    rows = worksheet.get_all_values()[1:]
    events = []
    
    for row in rows:
        # Check if row has empty values and if so skip to the next row
        empty_vals = row[1] == '' or row[2] == '' 
        if empty_vals:
            continue
        
        if not check_if_is_date(row[2], '%d.%m.%Y'):
            continue
        
        print(f'Row Data: {row}')
        date_str = row[2] 
        event_title = row[1]
        date = datetime.datetime.strptime(date_str, '%d.%m.%Y')
        events.append({
            'summary': event_title,
            'start': {'dateTime': date.isoformat() + 'Z'},
            'end': {'dateTime': (date + datetime.timedelta(hours=1)).isoformat() + 'Z'}
        })
        
    return events

# Function to create the dedicated calendar
def create_calendar():
    calendar = {
        'summary': 'DeadlineGS',
        'timeZone': 'UTC'
    }
    
    created_calendar = calendar_service.calendars().insert(body=calendar).execute()
    return created_calendar['id']

# Function to sync events with the dedicated calendar
def sync_with_calendar(events, calendar_id):
    existing_events = calendar_service.events().list(calendarId=calendar_id).execute().get('items', [])
    
    for event in events:
        event_exists = False
        for existing_event in existing_events:

            if existing_event['summary'] == event['summary']:
                event_exists = True
                print(f'Event for {event['summary']} passed')
                if existing_event['start']['dateTime'] != event['start']['dateTime']:
                    existing_event['start'] = event['start']
                    existing_event['end'] = event['end']
                    calendar_service.events().update(calendarId=calendar_id, eventId=existing_event['id'], body=existing_event).execute()
                    print(f'Updated event for {existing_event['summary']}')
                break
        if not event_exists:
            print('Inserting event')
            calendar_service.events().insert(calendarId=calendar_id, body=event).execute()

if __name__ == '__main__':
    # Create a new calendar and get its ID (deprecieted)
    # calendar_id = create_calendar()
    calendar_id = 'e6367906d08fac0bcf1354fa83c66fdbb77f51d1fee1d2bc324ffd8ae36f6a04@group.calendar.google.com'
    print(calendar_id)
    
    # Fetch events from Google Sheets
    events = fetch_events_from_sheets()
    
    # Sync events with the new dedicated calendar
    sync_with_calendar(events, calendar_id)