import base64
import json
import os
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

# Gmail API scope for read-only access
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
# Gemini API endpoint and key
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_API_KEY = "AIzaSyASa_YIxIFx_3tIfQgKpEDefOagYO_b8VE"  # Your confirmed API key

def authenticate_gmail():
    """Authenticate with Gmail API using OAuth 2.0."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
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
                raise
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_promotional_threads(service, user_id='me', max_threads=5):
    """Fetch up to five email threads labeled as Promotions."""
    try:
        # List threads with PROMOTIONS label
        results = service.users().threads().list(userId=user_id, labelIds=['CATEGORY_PROMOTIONS'], maxResults=max_threads).execute()
        threads = results.get('threads', [])
        
        if not threads:
            print("No promotional threads found.")
            return []
        
        # Fetch details for each thread
        thread_data = []
        for thread in threads:
            thread_id = thread['id']
            print(f"Fetching thread ID: {thread_id}")
            thread = service.users().threads().get(userId=user_id, id=thread_id).execute()
            messages = thread.get('messages', [])
            
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
                for header in headers:
                    if header['name'].lower() == 'from':
                        email_info['from'] = header['value']
                    if header['name'].lower() == 'to':
                        email_info['to'] = header['value']
                    if header['name'].lower() == 'subject':
                        email_info['subject'] = header['value']
                    if header['name'].lower() == 'date':
                        email_info['timestamp'] = header['value']
                
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
                    print(f"Error decoding body for thread {thread_id}: {e}")
                    email_info['body'] = 'Unable to decode message body.'
                
                email_data.append(email_info)
            
            thread_data.append({'thread_id': thread_id, 'emails': email_data})
        
        return thread_data
    except HttpError as error:
        print(f"An error occurred: {error}")
        if error.resp.status == 403:
            print("Access denied. Ensure mrhappy6600@gmail.com is a test user.")
        return []

def prepare_gemini_payload(email_thread):
    """Prepare payload for Gemini API from email thread."""
    combined_text = "\n".join([f"From: {email['from']}\nSubject: {email['subject']}\nBody: {email['body']}\n" for email in email_thread])
    
    prompt = f"""Analyze the following email thread and provide a JSON object with:
    - engagement_score: 'High' (3+ replies), 'Medium' (1-2 replies), or 'Low' (0 replies)
    - sentiment: 'Positive', 'Neutral', or 'Negative' based on the tone
    - risk_alerts: List of issues like 'Customer sounds unhappy' or 'Multiple follow-ups ignored'
    Thread:
    {combined_text}
    Return only the JSON object."""
    
    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

def call_gemini_api(payload):
    """Send email thread data to Gemini API for classification."""
    headers = {
        "Content-Type": "application/json"
    }
    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        print("Raw Gemini API Response:", json.dumps(result, indent=2))  # Debug output
        generated_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        if generated_text.startswith("```json\n") and generated_text.endswith("\n```"):
            generated_text = generated_text[8:-4]
        return json.loads(generated_text)
    except requests.RequestException as e:
        print(f"Gemini API call failed: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Status Code: {e.response.status_code}")
            print(f"Error Details: {e.response.text}")
        return {
            "engagement_score": "Unknown",
            "sentiment": "Unknown",
            "risk_alerts": ["API call failed"]
        }
    except json.JSONDecodeError as e:
        print(f"Failed to parse Gemini response as JSON: {e}")
        print(f"Raw response text: {generated_text}")
        return {
            "engagement_score": "Unknown",
            "sentiment": "Unknown",
            "risk_alerts": ["Invalid response format"]
        }

def main():
    try:
        # Authenticate with Gmail API
        service = authenticate_gmail()
        
        # Fetch up to five promotional threads
        threads = get_promotional_threads(service, max_threads=5)
        
        if not threads:
            print("No promotional threads to analyze.")
            return
        
        # Analyze each thread with Gemini
        for thread in threads:
            thread_id = thread['thread_id']
            email_thread = thread['emails']
            
            print(f"\nAnalyzing Thread ID: {thread_id}")
            print("Thread Details:")
            print(json.dumps(email_thread, indent=2))
            
            # Prepare Gemini API payload
            payload = prepare_gemini_payload(email_thread)
            
            # Send to Gemini API
            gemini_result = call_gemini_api(payload)
            
            # Print results
            print("Gemini API Classification:")
            print(json.dumps(gemini_result, indent=2))
        
    except Exception as e:
        print(f"Main error: {e}")

if __name__ == "__main__":
    main()