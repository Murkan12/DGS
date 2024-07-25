import os
import json
from dotenv import load_dotenv
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import datetime
from dateutil import parser
import logging

# Setup logging
logging.basicConfig(filename='dgs.log', level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

# Setup loading enviromental variables
load_dotenv()

# Authenticate and connect to Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/drive', 
          'https://www.googleapis.com/auth/calendar.events']
TOKEN_FILE = 'token.json'
EMAIL = os.getenv('EMAIL')
CREDENTIALS_FILE = 'credentials.json'

def create_calendar():
    try:
        calendar_list = calendar_service.calendarList().list().execute()
        for calendar in calendar_list['items']:
            if calendar['summary'] == 'DGS':
                return calendar['id']
        
        calendar = {
            'summary': 'DGS',
            'timeZone': 'UTC'
        }
        
        created_calendar = calendar_service.calendars().insert(body=calendar).execute()
        calendar_id = created_calendar['id']
        
        logging.info(f'Calendar created: {created_calendar['id']}')
        
        return calendar_id
    
    except Exception as e:
        logging.error(f'An error occurred while creating the calendar: {e}')
        return None

def get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return creds

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
        logging.info(f"Row Data: {row}")
        # Check if row has empty values and if so skip to the next row
        empty_vals = row[1] == '' or row[2] == '' 
        if empty_vals:
            continue
        
        if not check_if_is_date(row[2], '%d.%m.%Y'):
            continue
        
        date_str = row[2]
        event_title = 'Koniec umowy: ' + row[1]
        date = datetime.datetime.strptime(date_str, '%d.%m.%Y')
        events.append({
            'summary': event_title,
            'start': {'dateTime': date.isoformat() + 'Z'},
            'end': {'dateTime': (date + datetime.timedelta(hours=1)).isoformat() + 'Z'},
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 30 * 24 * 60},
                ],
            },
        })
        
    return events

def compare_dates(date_str1, date_str2):
    try:
        date1 = parser.parse(date_str1)
        date2 = parser.parse(date_str2)
        
        return date1 == date2
    except ValueError as e:
        logging.error(f'Error parsing dates: {e}')
        return False

# Function to sync events with the dedicated calendar
def sync_with_calendar(events, calendar_id):
    existing_events = calendar_service.events().list(calendarId=calendar_id).execute().get('items', [])
    
    for event in events:
        event_exists = False
        for existing_event in existing_events:
            if existing_event['summary'] == event['summary']:
                event_exists = True
                logging.info(f'Event for {event['summary']} passed')
                if not compare_dates(existing_event['start']['dateTime'], event['start']['dateTime']):
                    existing_event['start'] = event['start']
                    existing_event['end'] = event['end']
                    calendar_service.events().update(calendarId=calendar_id, eventId=existing_event['id'], body=existing_event).execute()
                    logging.info(f'Updated event for {existing_event['summary']}')
                break
        if not event_exists:
            logging.info(f'Inserting event: {event['summary']}')
            created_event = calendar_service.events().insert(calendarId=calendar_id, body=event).execute()
            logging.info(f'Inserted event: {created_event}')

if __name__ == '__main__':
    logging.info('Script started')
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)

        # Open the Google Sheets file
        spreadsheet = gc.open('test2')
        worksheet = spreadsheet.sheet1

        # Authenticate and connect to Google Calendar
        calendar_service = build('calendar', 'v3', credentials=creds)
        
        calendar_id = create_calendar()
        if calendar_id is None:
            raise Exception(f'Calendar creation failed')
    
        # Fetch events from Google Sheets
        events = fetch_events_from_sheets()
    
        # Sync events with the new dedicated calendar
        sync_with_calendar(events, calendar_id)
        
        logging.info('Script completed successfully')
    except Exception as e:
        logging.error(f'An error occurred: {e}')
        logging.error(f'Script failed')