import base64
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

# Gmail API scope for read-only access
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    """Authenticate with Gmail API using OAuth 2.0."""
    creds = None
    # Check if token.json exists from previous authentication
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If no valid credentials, prompt user to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}")
                creds = None
        if not creds:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("Missing credentials.json. Download it from Google Cloud Console.")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            try:
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"Authentication failed: {e}")
                print("Ensure mrhappy6600@gmail.com is added as a test user in Google Cloud Console.")
                raise
        # Save credentials for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_email_thread(service, user_id='me', thread_id=None):
    """Fetch an email thread by ID or list recent threads to select one."""
    try:
        if not thread_id:
            # List recent threads to find one (for demo purposes)
            results = service.users().threads().list(userId=user_id, maxResults=1).execute()
            threads = results.get('threads', [])
            if not threads:
                print("No threads found.")
                return None
            thread_id = threads[0]['id']
            print(f"Using thread ID: {thread_id}")
        
        # Fetch the thread
        thread = service.users().threads().get(userId=user_id, id=thread_id).execute()
        messages = thread.get('messages', [])
        
        # Extract relevant fields from each message
        email_data = []
        for message in messages:
            headers = message['payload']['headers']
            email_info = {
                'from': '',
                'to': '',
                'subject': '',
                'body': '',
                'timestamp': ''
            }
            # Extract headers
            for header in headers:
                if header['name'].lower() == 'from':
                    email_info['from'] = header['value']
                if header['name'].lower() == 'to':
                    email_info['to'] = header['value']
                if header['name'].lower() == 'subject':
                    email_info['subject'] = header['value']
                if header['name'].lower() == 'date':
                    email_info['timestamp'] = header['value']
            
            # Extract body (handle plain text or base64-encoded)
            try:
                if 'parts' in message['payload']:
                    for part in message['payload']['parts']:
                        if part['mimeType'] == 'text/plain':
                            body_data = part['body'].get('data', '')
                            if body_data:
                                email_info['body'] = base64.urlsafe_b64decode(body_data).decode('utf-8')
                                break
                else:
                    body_data = message['payload']['body'].get('data', '')
                    if body_data:
                        email_info['body'] = base64.urlsafe_b64decode(body_data).decode('utf-8')
            except Exception as e:
                print(f"Error decoding body: {e}")
                email_info['body'] = 'Unable to decode message body.'
            
            email_data.append(email_info)
        
        return email_data
    except HttpError as error:
        print(f"An error occurred: {error}")
        if error.resp.status == 403:
            print("Access denied. Ensure mrhappy6600@gmail.com is a test user and the app is in testing mode.")
        return None

def main():
    try:
        # Authenticate with Gmail API
        service = authenticate_gmail()
        
        # Fetch a thread (replace with your thread ID or leave as None to fetch a recent one)
        thread_id = None  # Example: '18c123456789abcd'
        email_thread = get_email_thread(service, thread_id=thread_id)
        
        if email_thread:
            # Print structured email data
            print("Fetched Email Thread:")
            print(json.dumps(email_thread, indent=2))
        else:
            print("Failed to fetch email thread.")
    except Exception as e:
        print(f"Main error: {e}")

if __name__ == "__main__":
    main()